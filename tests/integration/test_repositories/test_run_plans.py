"""Repository tests for StackOS run plans and approval gates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlmodel import Session

from stackos.context.repository import ContextRepository
from stackos.db.models import (
    ApprovalRequestStatus,
    ContextSnapshot,
    Run,
    RunPlanStatus,
    RunPlanStepStatus,
    RunStatus,
)
from stackos.mcp.errors import ToolNotGrantedError
from stackos.mcp.permissions import active_run_plan_step
from stackos.repositories.base import ConflictError, ValidationError
from stackos.repositories.run_plans import RunPlanRepository
from stackos.workflows.template_loader import WorkflowTemplateLoader
from stackos.workflows.template_schema import WorkflowTemplateSpec


def _run_plan_json() -> dict:
    return {
        "schema_version": "stackos.run-plan.v1",
        "key": "media.launch.run",
        "title": "Launch Media Campaign",
        "approvals": [{"key": "launch-review", "title": "Launch review"}],
        "steps": [
            {
                "id": "create-campaign",
                "title": "Create campaign",
                "approval_refs": ["launch-review"],
                "action_refs": ["meta.campaign.create"],
                "action_payloads": [
                    {"campaign": {"name": "Agent selected"}, "credential_ref": "cred_abc"}
                ],
            }
        ],
    }


def _now() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


def _template(version: str = "0.1.0", *, name: str = "Company Review") -> WorkflowTemplateSpec:
    return WorkflowTemplateSpec.model_validate(
        {
            "schema_version": "stackos.workflow-template.v1",
            "key": "company.review",
            "name": name,
            "version": version,
            "steps": [{"id": "review", "title": "Review"}],
            "outputs": [{"key": "summary", "type": "object"}],
        }
    )


def test_create_run_plan_from_template(session: Session, project_id: int) -> None:
    plan = (
        RunPlanRepository(session)
        .create(
            project_id=project_id,
            template_key="core.project-memory-review",
            inputs_json={"goal": "Review recent project memory."},
        )
        .data
    )

    assert plan.template_key == "core.project-memory-review"
    assert plan.key == "core.project-memory-review.run"
    assert plan.template_snapshot_json["key"] == "core.project-memory-review"
    assert plan.steps
    assert plan.status == "draft"


def test_create_run_plan_requires_template_required_inputs(
    session: Session,
    project_id: int,
) -> None:
    repo = RunPlanRepository(session)

    with pytest.raises(ValidationError, match="goal"):
        repo.create(project_id=project_id, template_key="core.project-memory-review")

    structural = repo.validate_plan(
        project_id=project_id,
        template_key="core.project-memory-review",
    )
    concrete = repo.validate_plan(
        project_id=project_id,
        template_key="core.project-memory-review",
        enforce_required_inputs=True,
    )
    with_inputs = repo.validate_plan(
        project_id=project_id,
        template_key="core.project-memory-review",
        inputs_json={"goal": "Review project memory."},
        enforce_required_inputs=True,
    )

    assert structural.valid is True
    assert concrete.valid is False
    assert "goal" in concrete.errors[0].message
    assert with_inputs.valid is True


def test_create_run_plan_applies_project_workflow_extension(
    session: Session,
    project_id: int,
) -> None:
    base = WorkflowTemplateLoader(session).describe_template(
        project_id=project_id,
        key="communications.customer-feedback-intake",
        plugin_slug="communications",
        include_extension=False,
    )
    steps = [step.model_dump(mode="json") for step in base.spec.steps]
    canonical_step_override = next(
        step for step in steps if step["id"] == "establish-canonical-thread"
    )
    canonical_step_override["title"] = "Establish Project Canonical Thread"
    WorkflowTemplateLoader(session).upsert_extension(
        project_id=project_id,
        workflow_key="communications.customer-feedback-intake",
        plugin_slug="communications",
        required_input_keys_json=["feedback_summary", "communication_route_ref"],
        input_defaults_json={
            "communication_route_ref": "communication-route:support-feedback",
            "canonical_slack_target_ref": "communication-target:support-triage",
        },
        selected_context_json={
            "communication": {
                "route_ref": "communication-route:support-feedback",
                "target_ref": "communication-target:support-triage",
            }
        },
        step_overrides_json={
            "establish-canonical-thread": {
                "extra_instructions": [
                    "Use the project extension route and target refs before copying "
                    "non-Slack feedback."
                ]
            }
        },
        template_overrides_json={
            "description": "Project-specific support intake run.",
            "steps": steps,
        },
    )

    repo = RunPlanRepository(session)
    with pytest.raises(ValidationError, match="feedback_summary"):
        repo.create(
            project_id=project_id,
            template_key="communications.customer-feedback-intake",
            plugin_slug="communications",
        )

    plan = repo.create(
        project_id=project_id,
        template_key="communications.customer-feedback-intake",
        plugin_slug="communications",
        inputs_json={"feedback_summary": "Telegram report includes a screenshot."},
        selected_context_json={"operator": {"instruction_source": "same-thread"}},
    ).data
    canonical_step = next(
        step for step in plan.steps if step.step_id == "establish-canonical-thread"
    )

    assert plan.inputs_json["feedback_summary"] == "Telegram report includes a screenshot."
    assert plan.inputs_json["communication_route_ref"] == "communication-route:support-feedback"
    assert plan.goal == "Project-specific support intake run."
    assert plan.selected_context_json == {
        "communication": {
            "route_ref": "communication-route:support-feedback",
            "target_ref": "communication-target:support-triage",
        },
        "operator": {"instruction_source": "same-thread"},
    }
    assert plan.metadata_json["workflow_extension"]["workflow_key"] == (
        "communications.customer-feedback-intake"
    )
    assert "template_overrides_json" in plan.metadata_json["workflow_extension"]
    assert canonical_step.title == "Establish Project Canonical Thread"
    assert "project extension route" in " ".join(canonical_step.instructions_json)


def test_started_run_plan_keeps_template_snapshot_after_template_changes(
    session: Session,
    project_id: int,
) -> None:
    templates = WorkflowTemplateLoader(session)
    templates.save_project_template(project_id=project_id, spec=_template("0.1.0", name="Old"))
    plan = (
        RunPlanRepository(session)
        .create(
            project_id=project_id,
            template_key="company.review",
        )
        .data
    )
    started = RunPlanRepository(session).start(plan.id, project_id=project_id).data

    templates.save_project_template(project_id=project_id, spec=_template("0.2.0", name="New"))
    fetched = RunPlanRepository(session).get(started.plan.id)

    assert fetched.template_snapshot_json["name"] == "Old"
    assert fetched.template_version == "0.1.0"


def test_start_links_selected_context_snapshot(session: Session, project_id: int) -> None:
    snapshot = (
        ContextRepository(session)
        .create_snapshot(
            project_id=project_id,
            name="Recent learnings",
            selected_sources_json=[{"source": "learnings", "ids": [1, 2]}],
        )
        .data
    )
    plan = (
        RunPlanRepository(session)
        .create(
            project_id=project_id,
            template_key="core.project-memory-review",
            context_snapshot_id=snapshot.id,
            inputs_json={"goal": "Review recent project memory."},
        )
        .data
    )

    started = RunPlanRepository(session).start(plan.id, project_id=project_id).data
    row = session.get(ContextSnapshot, snapshot.id)

    assert started.plan.context_snapshot_id == snapshot.id
    assert row is not None
    assert row.run_id == started.run_id


def test_approval_gate_transition_then_step_completion(
    session: Session,
    project_id: int,
) -> None:
    repo = RunPlanRepository(session)
    plan = repo.create(project_id=project_id, run_plan_json=_run_plan_json()).data
    started = repo.start(plan.id, project_id=project_id).data

    with pytest.raises(ConflictError):
        repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="create-campaign")

    approved = repo.update(
        run_plan_id=plan.id,
        approval_key="launch-review",
        approval_status=ApprovalRequestStatus.APPROVED,
        decided_by="operator",
        decision_json={"approved": True},
    ).data
    step = repo.claim_step(
        run_plan_id=plan.id,
        run_id=started.run_id,
        step_id="create-campaign",
        claimed_by="agent",
    ).data
    completed = repo.record_step(
        run_plan_id=plan.id,
        run_id=started.run_id,
        step_id="create-campaign",
        status=RunPlanStepStatus.SUCCESS,
        result_json={"campaign_id": "cmp_123"},
    ).data
    run = session.get(Run, started.run_id)

    assert approved.approval_requests[0].status == "approved"
    assert step.status == "running"
    assert completed.status == "completed"
    assert completed.steps[0].result_json == {"campaign_id": "cmp_123"}
    assert run is not None
    assert run.status == RunStatus.SUCCESS


def test_claimed_step_exposes_static_mcp_tool_grants(session: Session, project_id: int) -> None:
    repo = RunPlanRepository(session)
    plan = repo.create(
        project_id=project_id,
        run_plan_json={
            "schema_version": "stackos.run-plan.v1",
            "key": "ops.resource-write.run",
            "title": "Resource write",
            "grants": {"step_tools": {"write": ["resource.upsert"]}},
            "steps": [{"id": "write", "title": "Write resource"}],
        },
    ).data
    started = repo.start(plan.id, project_id=project_id).data

    step = repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="write").data
    fetched = repo.get(plan.id)

    assert step.allowed_tools == ["resource.upsert"]
    assert fetched.steps[0].allowed_tools == ["resource.upsert"]


def test_claim_step_refreshes_linked_run_heartbeat(
    session: Session,
    project_id: int,
) -> None:
    repo = RunPlanRepository(session)
    plan = repo.create(
        project_id=project_id,
        run_plan_json={
            "schema_version": "stackos.run-plan.v1",
            "key": "heartbeat.claim.run",
            "title": "Heartbeat Claim",
            "steps": [{"id": "write", "title": "Write"}],
        },
    ).data
    started = repo.start(plan.id, project_id=project_id).data
    run = session.get(Run, started.run_id)
    assert run is not None
    stale_at = _now() - timedelta(minutes=10)
    run.heartbeat_at = stale_at
    session.add(run)
    session.commit()

    repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="write")

    refreshed = session.get(Run, started.run_id)
    assert refreshed is not None
    assert refreshed.heartbeat_at is not None
    assert refreshed.heartbeat_at > stale_at


def test_claim_step_rejects_terminal_linked_run(session: Session, project_id: int) -> None:
    repo = RunPlanRepository(session)
    plan = repo.create(
        project_id=project_id,
        run_plan_json={
            "schema_version": "stackos.run-plan.v1",
            "key": "terminal-run.claim.run",
            "title": "Terminal Run Claim",
            "steps": [{"id": "write", "title": "Write"}],
        },
    ).data
    started = repo.start(plan.id, project_id=project_id).data
    run = session.get(Run, started.run_id)
    assert run is not None
    run.status = RunStatus.ABORTED
    run.error = "daemon-restart-orphan"
    session.add(run)
    session.commit()

    with pytest.raises(ConflictError) as exc_info:
        repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="write")

    assert exc_info.value.data["run_id"] == started.run_id
    assert exc_info.value.data["run_status"] == "aborted"
    assert "runPlan.checkConsistency" in exc_info.value.data["next_operations"]


def test_record_step_rejects_terminal_linked_run(session: Session, project_id: int) -> None:
    repo = RunPlanRepository(session)
    plan = repo.create(
        project_id=project_id,
        run_plan_json={
            "schema_version": "stackos.run-plan.v1",
            "key": "terminal-run.record.run",
            "title": "Terminal Run Record",
            "steps": [{"id": "write", "title": "Write"}],
        },
    ).data
    started = repo.start(plan.id, project_id=project_id).data
    repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="write")
    run = session.get(Run, started.run_id)
    assert run is not None
    run.status = RunStatus.ABORTED
    run.error = "daemon-restart-orphan"
    session.add(run)
    session.commit()

    with pytest.raises(ConflictError) as exc_info:
        repo.record_step(
            run_plan_id=plan.id,
            run_id=started.run_id,
            step_id="write",
            status=RunPlanStepStatus.SUCCESS,
        )

    assert exc_info.value.data["run_id"] == started.run_id
    assert exc_info.value.data["run_status"] == "aborted"
    assert session.get(Run, started.run_id).status == RunStatus.ABORTED
    assert repo.get(plan.id).status == RunPlanStatus.STARTED


def test_run_plan_grant_gate_rejects_terminal_linked_run(
    session: Session,
    project_id: int,
) -> None:
    repo = RunPlanRepository(session)
    plan = repo.create(
        project_id=project_id,
        run_plan_json={
            "schema_version": "stackos.run-plan.v1",
            "key": "terminal-run.grant.run",
            "title": "Terminal Run Grant",
            "steps": [{"id": "write", "title": "Write"}],
        },
    ).data
    started = repo.start(plan.id, project_id=project_id).data
    repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="write")
    run = session.get(Run, started.run_id)
    assert run is not None
    run.status = RunStatus.ABORTED
    run.error = "daemon-restart-orphan"
    session.add(run)
    session.commit()

    with pytest.raises(ToolNotGrantedError) as exc_info:
        active_run_plan_step(
            SimpleNamespace(run=run, run_id=started.run_id, session=session),
            "resource.upsert",
        )

    assert exc_info.value.data["run_id"] == started.run_id
    assert "running audit run" in str(exc_info.value)


def test_run_plan_get_surfaces_consistency_issues_for_terminal_run(
    session: Session,
    project_id: int,
) -> None:
    repo = RunPlanRepository(session)
    plan = repo.create(
        project_id=project_id,
        run_plan_json={
            "schema_version": "stackos.run-plan.v1",
            "key": "terminal-run.diagnostic.run",
            "title": "Terminal Run Diagnostic",
            "steps": [{"id": "write", "title": "Write"}],
        },
    ).data
    started = repo.start(plan.id, project_id=project_id).data
    run = session.get(Run, started.run_id)
    assert run is not None
    run.status = RunStatus.ABORTED
    run.error = "daemon-restart-orphan"
    session.add(run)
    session.commit()

    fetched = repo.get(plan.id)

    assert fetched.consistency_issues
    assert fetched.consistency_issues[0].code == "terminal-run-live-plan"
    assert fetched.consistency_issues[0].severity == "error"


def test_step_linked_approval_gate_blocks_claim(session: Session, project_id: int) -> None:
    repo = RunPlanRepository(session)
    plan = repo.create(
        project_id=project_id,
        run_plan_json={
            "schema_version": "stackos.run-plan.v1",
            "key": "media.step-linked-approval.run",
            "title": "Step linked approval",
            "approvals": [
                {
                    "key": "launch-review",
                    "title": "Launch review",
                    "step_id": "create-campaign",
                }
            ],
            "steps": [{"id": "create-campaign", "title": "Create campaign"}],
        },
    ).data
    started = repo.start(plan.id, project_id=project_id).data

    with pytest.raises(ConflictError):
        repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="create-campaign")

    repo.update(
        run_plan_id=plan.id,
        approval_key="launch-review",
        approval_status=ApprovalRequestStatus.APPROVED,
    )
    step = repo.claim_step(
        run_plan_id=plan.id,
        run_id=started.run_id,
        step_id="create-campaign",
    ).data

    assert step.status == RunPlanStepStatus.RUNNING


def test_started_plan_cannot_be_started_again_or_return_token(
    session: Session,
    project_id: int,
) -> None:
    repo = RunPlanRepository(session)
    plan = repo.create(project_id=project_id, run_plan_json=_run_plan_json()).data
    first = repo.start(plan.id, project_id=project_id).data

    with pytest.raises(ConflictError) as exc_info:
        repo.start(plan.id, project_id=project_id)

    assert first.run_token
    assert "run_token" not in str(exc_info.value.data)


def test_run_plan_late_writes_reject_secrets(session: Session, project_id: int) -> None:
    repo = RunPlanRepository(session)
    plan = repo.create(project_id=project_id, run_plan_json=_run_plan_json()).data
    started = repo.start(plan.id, project_id=project_id).data
    repo.update(
        run_plan_id=plan.id,
        approval_key="launch-review",
        approval_status=ApprovalRequestStatus.APPROVED,
    )
    repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="create-campaign")

    with pytest.raises(ValidationError) as meta_exc:
        repo.update(run_plan_id=plan.id, metadata_json={"api_key": "secret"})
    with pytest.raises(ValidationError) as decision_exc:
        repo.update(
            run_plan_id=plan.id,
            approval_key="launch-review",
            approval_status=ApprovalRequestStatus.APPROVED,
            decision_json={"authorization": "Bearer abc"},
        )
    with pytest.raises(ValidationError) as result_exc:
        repo.record_step(
            run_plan_id=plan.id,
            run_id=started.run_id,
            step_id="create-campaign",
            status=RunPlanStepStatus.SUCCESS,
            result_json={"refresh_token": "secret"},
        )

    assert "must not contain secrets" in str(meta_exc.value)
    assert "must not contain secrets" in str(decision_exc.value)
    assert "must not contain secrets" in str(result_exc.value)


def test_explicit_step_claim_enforces_dependencies(session: Session, project_id: int) -> None:
    repo = RunPlanRepository(session)
    plan = repo.create(
        project_id=project_id,
        run_plan_json={
            "schema_version": "stackos.run-plan.v1",
            "key": "ops.dependency.run",
            "title": "Dependency run",
            "steps": [
                {"id": "first", "title": "First"},
                {"id": "second", "title": "Second", "depends_on": ["first"]},
            ],
        },
    ).data
    started = repo.start(plan.id, project_id=project_id).data

    with pytest.raises(ConflictError):
        repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="second")

    repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="first")
    repo.record_step(
        run_plan_id=plan.id,
        run_id=started.run_id,
        step_id="first",
        status=RunPlanStepStatus.SUCCESS,
    )
    second = repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="second").data

    assert second.status == RunPlanStepStatus.RUNNING


def test_run_plan_allows_only_one_running_step(session: Session, project_id: int) -> None:
    repo = RunPlanRepository(session)
    plan = repo.create(
        project_id=project_id,
        run_plan_json={
            "schema_version": "stackos.run-plan.v1",
            "key": "ops.single-running-step.run",
            "title": "Single running step",
            "steps": [
                {"id": "first", "title": "First"},
                {"id": "second", "title": "Second"},
            ],
        },
    ).data
    started = repo.start(plan.id, project_id=project_id).data

    first = repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="first").data
    with pytest.raises(ConflictError, match="already has a running step") as exc_info:
        repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="second")

    assert first.status == RunPlanStepStatus.RUNNING
    assert exc_info.value.data["step_id"] == "first"

    repo.record_step(
        run_plan_id=plan.id,
        run_id=started.run_id,
        step_id="first",
        status=RunPlanStepStatus.SUCCESS,
    )
    second = repo.claim_step(run_plan_id=plan.id, run_id=started.run_id, step_id="second").data

    assert second.status == RunPlanStepStatus.RUNNING
