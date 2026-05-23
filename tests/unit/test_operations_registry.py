from __future__ import annotations

from content_stack.operations.registry import build_operation_registry


def test_operation_registry_documents_core_operations() -> None:
    registry = build_operation_registry()

    names = [item.name for item in registry.all()]
    assert names == [
        "action.describe",
        "action.execute",
        "action.validate",
        "runPlan.claimStep",
        "runPlan.create",
        "runPlan.get",
        "runPlan.list",
        "runPlan.recordStep",
        "runPlan.start",
        "runPlan.update",
        "runPlan.validate",
    ]

    described = registry.get("action.execute").describe_out()

    assert described.name == "action.execute"
    assert described.mutating is True
    assert described.surfaces["mcp"].enabled is True
    assert described.surfaces["rest"].enabled is True
    assert described.surfaces["cli"].enabled is True
    assert described.grant_policy == "run-plan-step-action-ref"
    assert "properties" in described.input_schema
    assert "project_id" in described.input_schema["properties"]
    assert "WriteEnvelope" in described.output_schema["title"]
    assert any("run_token" in item for item in described.prerequisites)
    assert described.examples[0].arguments["action_ref"] == "utils.sitemap.fetch"

    run_plan = registry.get("runPlan.claimStep").describe_out()
    assert run_plan.surfaces["mcp"].enabled is True
    assert run_plan.surfaces["rest"].enabled is True
    assert run_plan.surfaces["cli"].command == "run-plans claim-step"
    assert run_plan.grant_policy == "run-plan-controller"
    assert any("run_token" in item for item in run_plan.prerequisites)


def test_operation_registry_surface_filter() -> None:
    registry = build_operation_registry()

    assert [item.name for item in registry.by_surface("cli")] == [
        "action.describe",
        "action.execute",
        "action.validate",
        "runPlan.claimStep",
        "runPlan.create",
        "runPlan.get",
        "runPlan.list",
        "runPlan.recordStep",
        "runPlan.start",
        "runPlan.validate",
    ]
    assert registry.get("runPlan.update").surfaces.cli.enabled is False
    assert registry.list_out(surface="rest").items[0].surfaces["rest"].enabled is True
