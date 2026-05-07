"""Tests for ``/api/v1/meta/enums``."""

from __future__ import annotations

from fastapi.testclient import TestClient

from content_stack.db.models import (
    ARTICLE_STATUS_TRANSITIONS,
    INTERNAL_LINK_STATUS_TRANSITIONS,
    RUN_STATUS_TRANSITIONS,
    TOPIC_STATUS_TRANSITIONS,
    ArticleStatus,
    RunStatus,
    TopicStatus,
)


def test_meta_enums_returns_full_payload(api: TestClient) -> None:
    """Every enum class is represented as a list of values."""
    resp = api.get("/api/v1/meta/enums")
    assert resp.status_code == 200
    body = resp.json()
    expected_keys = {
        "topics_status",
        "topics_intent",
        "topics_source",
        "articles_status",
        "article_assets_kind",
        "article_publishes_status",
        "runs_status",
        "runs_kind",
        "run_steps_status",
        "procedure_run_steps_status",
        "clusters_type",
        "compliance_rules_kind",
        "compliance_rules_position",
        "eeat_criteria_tier",
        "eeat_criteria_category",
        "eeat_evaluations_verdict",
        "internal_links_status",
        "publish_targets_kind",
        "redirects_kind",
        "allowed_transitions",
    }
    assert expected_keys.issubset(body.keys())


def test_meta_enums_topic_status_matches_models(api: TestClient) -> None:
    """``topics_status`` mirrors the enum class declaration order."""
    resp = api.get("/api/v1/meta/enums")
    assert resp.status_code == 200
    assert resp.json()["topics_status"] == [m.value for m in TopicStatus]


def test_meta_enums_article_status_matches_models(api: TestClient) -> None:
    """``articles_status`` mirrors the enum class declaration order."""
    resp = api.get("/api/v1/meta/enums")
    assert resp.status_code == 200
    assert resp.json()["articles_status"] == [m.value for m in ArticleStatus]


def test_meta_enums_run_status_matches_models(api: TestClient) -> None:
    """``runs_status`` mirrors the enum class declaration order."""
    resp = api.get("/api/v1/meta/enums")
    assert resp.status_code == 200
    assert resp.json()["runs_status"] == [m.value for m in RunStatus]


def test_allowed_transitions_topics_match_map(api: TestClient) -> None:
    """``allowed_transitions.topics`` matches ``TOPIC_STATUS_TRANSITIONS``."""
    resp = api.get("/api/v1/meta/enums")
    assert resp.status_code == 200
    body = resp.json()
    expected = {k.value: sorted(v.value for v in vs) for k, vs in TOPIC_STATUS_TRANSITIONS.items()}
    assert body["allowed_transitions"]["topics"] == expected


def test_allowed_transitions_articles_match_map(api: TestClient) -> None:
    """``allowed_transitions.articles`` matches ``ARTICLE_STATUS_TRANSITIONS``."""
    resp = api.get("/api/v1/meta/enums")
    body = resp.json()
    expected = {
        k.value: sorted(v.value for v in vs) for k, vs in ARTICLE_STATUS_TRANSITIONS.items()
    }
    assert body["allowed_transitions"]["articles"] == expected


def test_allowed_transitions_internal_links_and_runs(api: TestClient) -> None:
    """Both other state machines are exposed."""
    body = api.get("/api/v1/meta/enums").json()
    expected_runs = {
        k.value: sorted(v.value for v in vs) for k, vs in RUN_STATUS_TRANSITIONS.items()
    }
    assert body["allowed_transitions"]["runs"] == expected_runs
    expected_il = {
        k.value: sorted(v.value for v in vs) for k, vs in INTERNAL_LINK_STATUS_TRANSITIONS.items()
    }
    assert body["allowed_transitions"]["internal_links"] == expected_il
