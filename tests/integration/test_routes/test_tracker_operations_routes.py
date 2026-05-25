from __future__ import annotations

from fastapi.testclient import TestClient


def test_tracker_operations_rest_vertical_slice(api: TestClient, project_id: int) -> None:
    created_task = api.post(
        "/api/v1/operations/tracker.createTask/call",
        json={
            "arguments": {
                "project_id": project_id,
                "key": "rest-tracker",
                "title": "REST tracker",
                "created_by": "route-test",
            }
        },
    )
    assert created_task.status_code == 200, created_task.text
    assert created_task.json()["data"]["task"]["key"] == "rest-tracker"

    created_ticket = api.post(
        "/api/v1/operations/tracker.createTicket/call",
        json={
            "arguments": {
                "project_id": project_id,
                "task_key": "rest-tracker",
                "key": "rest-ticket",
                "title": "REST ticket",
                "definition_of_done_json": ["operation call succeeds"],
                "created_by": "route-test",
            }
        },
    )
    assert created_ticket.status_code == 200, created_ticket.text
    assert created_ticket.json()["data"]["ticket"]["key"] == "rest-ticket"

    next_work = api.post(
        "/api/v1/operations/tracker.next/call",
        json={"arguments": {"project_id": project_id}},
    )
    assert next_work.status_code == 200, next_work.text
    assert next_work.json()["tickets"][0]["key"] == "rest-ticket"

    snapshot = api.post(
        "/api/v1/operations/tracker.get/call",
        json={"arguments": {"project_id": project_id, "include_graph": True}},
    )
    assert snapshot.status_code == 200, snapshot.text
    assert {node["id"] for node in snapshot.json()["graph"]["nodes"]} >= {
        "task:rest-tracker",
        "ticket:rest-ticket",
    }
