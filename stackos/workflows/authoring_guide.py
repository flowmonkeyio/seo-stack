"""Canonical workflow authoring guidance for StackOS agents."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

WORKFLOW_AUTHORING_GUIDE_VERSION = "stackos.workflow-authoring-guide.v1"
WORKFLOW_AUTHORING_GUIDE_OPERATION = "workflowTemplate.authoringGuide"

MINIMAL_WORKFLOW_TEMPLATE_YAML = """schema_version: stackos.workflow-template.v1
key: core.example-review
name: Example Review
version: 0.1.0
description: Review bounded project context and produce a next-step plan.
domain: core
owner:
  team: StackOS
when_to_use:
  - A reusable agent workflow should review context before planning.
when_not_to_use:
  - The user asked for one direct provider action with no durable workflow state.
skill_requirements:
  - skill_ref: stackos:stackos
    requirement: recommended
    purpose: Teach the main agent StackOS workflow, run-plan, tracker, and evidence mechanics.
inputs:
  - key: goal
    name: Goal
    type: string
    required: true
context_requirements:
  - id: recent_runs
    source: runs
    fields: [kind, status, last_step, metadata_json]
    max_items: 10
    return_mode: compact
policies:
  - key: agent-decides
    kind: boundary
    description: StackOS stores state and executes explicit calls; the agent decides strategy.
steps:
  - id: clarify-goal
    title: Clarify Goal
    purpose: Restate the goal, assumptions, constraints, and missing inputs.
    input_refs: [goal]
    output_refs: [context_summary]
  - id: review-context
    title: Review Context
    purpose: Read bounded prior evidence before recommending next work.
    context_refs: [recent_runs]
    depends_on: [clarify-goal]
    output_refs: [recommended_plan]
outputs:
  - key: context_summary
    name: Context Summary
    type: object
    required: true
  - key: recommended_plan
    name: Recommended Plan
    type: object
    required: true
failure_handling:
  - If context is insufficient, return missing context requirements instead of inventing facts.
metadata:
  builtin: true
"""


class WorkflowAuthoringOperationRef(BaseModel):
    """One operation in the canonical workflow authoring path."""

    model_config = ConfigDict(extra="forbid")

    name: str
    purpose: str


class WorkflowAuthoringExample(BaseModel):
    """Minimal operation example for agents building workflows."""

    model_config = ConfigDict(extra="forbid")

    title: str
    operation: str
    arguments: dict[str, object] = Field(default_factory=dict)


class WorkflowAuthoringGuideOut(BaseModel):
    """Agent-facing workflow authoring contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = WORKFLOW_AUTHORING_GUIDE_VERSION
    source_of_truth_operation: str = WORKFLOW_AUTHORING_GUIDE_OPERATION
    title: str
    summary: str
    audience: list[str]
    principles: list[str]
    decision_path: list[str]
    template_contract_fields: list[str]
    template_must_not_include: list[str]
    extension_uses: list[str]
    execution_path: list[str]
    canonical_operations: list[WorkflowAuthoringOperationRef]
    minimal_template_yaml: str
    examples: list[WorkflowAuthoringExample]


def workflow_authoring_guide() -> WorkflowAuthoringGuideOut:
    """Return the single StackOS workflow authoring contract."""

    return WorkflowAuthoringGuideOut(
        title="StackOS Workflow Authoring Guide",
        summary=(
            "Use this operation as the canonical guide for building, extending, "
            "validating, saving, forking, and executing StackOS workflows from any "
            "repository. Repository docs and installed skills should point here instead "
            "of duplicating the authoring path."
        ),
        audience=[
            "Agents working outside the StackOS source checkout",
            "Operators reviewing reusable workflow templates",
            "Plugin authors shipping built-in workflow templates",
        ],
        principles=[
            "Projects store durable state, workflow templates define reusable methods, "
            "and run plans are concrete execution instances.",
            "Templates are inert contracts. Agents decide strategy; StackOS validates "
            "state, resolves safe refs, executes explicit calls, and records audit.",
            "Create a new template only when the reusable method is genuinely new.",
            "Use a workflow extension when an existing workflow only needs project "
            "defaults, selected context, guardrails, agent/skill requirements, or step guidance.",
            "Use a one-off run plan when the work is not reusable.",
            "Keep domain behavior in plugins through manifests, resources, actions, "
            "templates, and extensions.",
        ],
        decision_path=[
            "Choose the workflow identity: new template, project extension, or one-off run plan.",
            "Draft the reusable contract with stable key, inputs, bounded context, "
            "agent/skill requirements, action/resource contracts, policies, approval "
            "gates, ordered steps, outputs, learning hooks, and failure handling.",
            "Validate drafts with workflowTemplate.validate before saving, forking, or "
            "creating a run.",
            "For project-specific setup on an existing workflow, validate and save a "
            "workflow extension instead of copying the template.",
            "Before execution, describe the effective workflow, resolve agent and skill "
            "presets, check readiness, create and validate a run plan, then execute "
            "through step-scoped grants.",
        ],
        template_contract_fields=[
            "schema_version",
            "key",
            "name",
            "version",
            "description",
            "domain",
            "owner",
            "when_to_use",
            "when_not_to_use",
            "inputs",
            "context_requirements",
            "agent_requirements",
            "skill_requirements",
            "skill_preset_requirements",
            "capability_requirements",
            "auth_requirements",
            "action_contracts",
            "resource_contracts",
            "policies",
            "approval_gates",
            "steps",
            "outputs",
            "learning_hooks",
            "failure_handling",
            "metadata",
        ],
        template_must_not_include=[
            "Raw secrets or credentials",
            "Run tokens",
            "Concrete credential refs",
            "Exact provider payloads for one execution",
            "One-off task state",
            "Selected variants or final business decisions",
            "Provider object ids that belong to a concrete run",
            "Repository-local documentation copies of this authoring guide",
        ],
        extension_uses=[
            "Stable project refs such as communication routes or named targets",
            "Project guidance, channel purpose, audience, data-scope boundaries, and "
            "safe external refs",
            "Required input keys that must be present after defaults and run inputs merge",
            "Project guardrails the agent must preserve in run-plan metadata",
            "Additive step guidance such as instructions_prepend, extra_instructions, "
            "success_criteria, or metadata",
            "Atomic top-level workflow field overrides such as agent_requirements, "
            "skill_requirements, skill_preset_requirements, policies, approval_gates, or steps",
        ],
        execution_path=[
            "workflowTemplate.authoringGuide",
            "workflowTemplate.validate",
            "workflowTemplate.save or workflowTemplate.fork only with explicit "
            "local-admin authority",
            "workflowExtension.validate and workflowExtension.upsert for project-specific overlays",
            "workflowTemplate.describe",
            "agentPreset.resolveForWorkflow",
            "skillPreset.resolveForWorkflow",
            "readiness.check",
            "runPlan.create",
            "runPlan.validate",
            "runPlan.start",
            "runPlan.claimStep",
            "step-granted toolbox.call or action.execute",
            "tracker evidence and runPlan.recordStep",
        ],
        canonical_operations=[
            WorkflowAuthoringOperationRef(
                name="workflowTemplate.authoringGuide",
                purpose="Return this canonical workflow authoring contract.",
            ),
            WorkflowAuthoringOperationRef(
                name="workflowTemplate.validate",
                purpose="Validate a draft template or installed template key without saving state.",
            ),
            WorkflowAuthoringOperationRef(
                name="workflowTemplate.describe",
                purpose=(
                    "Inspect the effective workflow, including enabled project extension layering."
                ),
            ),
            WorkflowAuthoringOperationRef(
                name="workflowExtension.validate",
                purpose=(
                    "Validate project defaults, selected context, guardrails, step "
                    "overrides, and atomic workflow-field overrides."
                ),
            ),
            WorkflowAuthoringOperationRef(
                name="workflowExtension.upsert",
                purpose=(
                    "Persist reviewed project-specific workflow setup without "
                    "duplicating the base template."
                ),
            ),
            WorkflowAuthoringOperationRef(
                name="workflowTemplate.save",
                purpose=(
                    "Persist a reviewed project/user template with explicit local-admin authority."
                ),
            ),
            WorkflowAuthoringOperationRef(
                name="workflowTemplate.fork",
                purpose=(
                    "Create a separately named reusable workflow identity with "
                    "explicit local-admin authority."
                ),
            ),
            WorkflowAuthoringOperationRef(
                name="runPlan.create",
                purpose="Materialize a reusable workflow into concrete project execution state.",
            ),
        ],
        minimal_template_yaml=MINIMAL_WORKFLOW_TEMPLATE_YAML,
        examples=[
            WorkflowAuthoringExample(
                title="Read the canonical authoring guide",
                operation="workflowTemplate.authoringGuide",
                arguments={},
            ),
            WorkflowAuthoringExample(
                title="Validate an existing workflow by key",
                operation="workflowTemplate.validate",
                arguments={"key": "engineering.tracked-delivery"},
            ),
            WorkflowAuthoringExample(
                title="Validate a draft template",
                operation="workflowTemplate.validate",
                arguments={"template_yaml": MINIMAL_WORKFLOW_TEMPLATE_YAML},
            ),
            WorkflowAuthoringExample(
                title="Inspect effective workflow setup before execution",
                operation="workflowTemplate.describe",
                arguments={"key": "engineering.tracked-delivery", "project_id": 1},
            ),
        ],
    )


__all__ = [
    "WORKFLOW_AUTHORING_GUIDE_OPERATION",
    "WORKFLOW_AUTHORING_GUIDE_VERSION",
    "WorkflowAuthoringExample",
    "WorkflowAuthoringGuideOut",
    "WorkflowAuthoringOperationRef",
    "workflow_authoring_guide",
]
