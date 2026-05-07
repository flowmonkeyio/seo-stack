"""Tests for the topics + clusters repositories."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from content_stack.db.models import (
    ClusterType,
    TopicIntent,
    TopicSource,
    TopicStatus,
)
from content_stack.repositories.base import ConflictError
from content_stack.repositories.clusters import (
    ClusterRepository,
    TopicCreate,
    TopicRepository,
)


def test_cluster_hierarchy(session: Session, project_id: int) -> None:
    repo = ClusterRepository(session)
    pillar = repo.create(project_id=project_id, name="Casinos", type=ClusterType.PILLAR).data
    spoke = repo.create(
        project_id=project_id,
        name="Roulette",
        type=ClusterType.SPOKE,
        parent_id=pillar.id,
    ).data
    assert spoke.parent_id == pillar.id


def test_bulk_create_preserves_input_order(session: Session, project_id: int) -> None:
    repo = TopicRepository(session)
    items = [TopicCreate(title=f"Topic {i}", priority=10 - i) for i in range(5)]
    env = repo.bulk_create(project_id, items)
    assert [t.title for t in env.data] == [f"Topic {i}" for i in range(5)]
    # IDs should be monotonic.
    assert env.data == sorted(env.data, key=lambda t: t.id)


def test_topic_queue_tiebreaker(session: Session, project_id: int) -> None:
    """``priority DESC, created_at ASC, id ASC`` per audit B-16."""
    repo = TopicRepository(session)
    repo.create(project_id, TopicCreate(title="lowprio", priority=10))
    repo.create(project_id, TopicCreate(title="highprio", priority=90))
    repo.create(project_id, TopicCreate(title="midprio", priority=50))
    repo.create(project_id, TopicCreate(title="nullprio"))  # null priority

    page = repo.list(project_id, sort="priority")
    titles = [t.title for t in page.items]
    # high (90) → mid (50) → low (10) → null (NULLS LAST)
    assert titles == ["highprio", "midprio", "lowprio", "nullprio"]


def test_topic_status_transition(session: Session, project_id: int) -> None:
    repo = TopicRepository(session)
    env = repo.create(project_id, TopicCreate(title="t"))
    out = repo.approve(env.data.id)
    assert out.data.status == TopicStatus.APPROVED


def test_topic_illegal_transition_raises(session: Session, project_id: int) -> None:
    repo = TopicRepository(session)
    env = repo.create(project_id, TopicCreate(title="t"))
    repo.approve(env.data.id)
    # Can't go approved → published directly per the legal map.
    with pytest.raises(ConflictError):
        repo.update(env.data.id, status=TopicStatus.PUBLISHED)


def test_bulk_update_status_atomic(session: Session, project_id: int) -> None:
    repo = TopicRepository(session)
    a = repo.create(project_id, TopicCreate(title="a")).data
    b = repo.create(project_id, TopicCreate(title="b")).data
    env = repo.bulk_update_status(project_id, [a.id, b.id], TopicStatus.APPROVED)
    assert all(t.status == TopicStatus.APPROVED for t in env.data)


def test_filter_by_status(session: Session, project_id: int) -> None:
    repo = TopicRepository(session)
    a = repo.create(project_id, TopicCreate(title="x")).data
    repo.create(project_id, TopicCreate(title="y"))
    repo.approve(a.id)
    page = repo.list(project_id, status=TopicStatus.APPROVED)
    assert len(page.items) == 1


def test_topic_with_intent_and_source(session: Session, project_id: int) -> None:
    repo = TopicRepository(session)
    env = repo.create(
        project_id,
        TopicCreate(
            title="t",
            intent=TopicIntent.COMMERCIAL,
            source=TopicSource.DATAFORSEO,
        ),
    )
    assert env.data.intent == TopicIntent.COMMERCIAL
    assert env.data.source == TopicSource.DATAFORSEO
