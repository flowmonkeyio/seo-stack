"""Procedures router tests — list, run (live in M7.A), runs/{id}."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_procedures_returns_array(api: TestClient) -> None:
    """``GET /procedures`` returns a list (empty until M7 drops PROCEDURE.md files)."""
    resp = api.get("/api/v1/procedures")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_run_procedure_unknown_slug_returns_404(api: TestClient, project_id: int) -> None:
    """``POST /procedures/{slug}/run`` 404s when the slug isn't registered."""
    resp = api.post(
        "/api/v1/procedures/bootstrap-not-real/run",
        json={"project_id": project_id, "args": {}},
    )
    assert resp.status_code == 404
    body = resp.json()["detail"]
    assert "bootstrap-not-real" in body["detail"]


def test_get_procedure_run_404_for_missing(api: TestClient) -> None:
    """Polling a non-existent run returns 404."""
    resp = api.get("/api/v1/procedures/runs/9999")
    assert resp.status_code == 404


def test_get_procedure_run_returns_run_plus_steps(api: TestClient, project_id: int) -> None:
    """Polling a real run returns ``{run, steps}``."""
    from sqlmodel import Session

    from content_stack.db.models import (
        ProcedureRunStep,
        ProcedureRunStepStatus,
        Run,
        RunKind,
        RunStatus,
    )

    engine = api.app.state.engine  # type: ignore[attr-defined]
    with Session(engine) as s:
        run = Run(
            project_id=project_id,
            kind=RunKind.PROCEDURE,
            status=RunStatus.RUNNING,
            procedure_slug="bootstrap",
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        assert run.id is not None
        run_id = run.id
        step = ProcedureRunStep(
            run_id=run_id,
            step_index=0,
            step_id="step-zero",
            status=ProcedureRunStepStatus.PENDING,
        )
        s.add(step)
        s.commit()

    resp = api.get(f"/api/v1/procedures/runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run"]["id"] == run_id
    assert len(body["steps"]) == 1
