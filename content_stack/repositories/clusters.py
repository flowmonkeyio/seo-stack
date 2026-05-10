"""Clusters + topics repository module.

Two tables, two classes. The TopicRepository implements the
``(priority DESC, created_at ASC, id ASC)`` tiebreaker per audit B-16
and exposes a ``bulk_create`` that returns IDs in input order per
audit M-13.

State-machine: topics use ``TOPIC_STATUS_TRANSITIONS`` from
``content_stack.db.models``; ``approve`` / ``reject`` are convenience
wrappers. ``bulk_update_status`` validates *every* transition before
mutating any row.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from content_stack.db.models import (
    TOPIC_STATUS_TRANSITIONS,
    Cluster,
    ClusterType,
    Topic,
    TopicIntent,
    TopicSource,
    TopicStatus,
)
from content_stack.repositories.base import (
    ConflictError,
    Envelope,
    NotFoundError,
    Page,
    ValidationError,
    cursor_paginate,
    validate_transition,
)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Output models.
# ---------------------------------------------------------------------------


class ClusterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    type: ClusterType
    parent_id: int | None
    created_at: datetime


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    cluster_id: int | None
    title: str
    primary_kw: str
    secondary_kws: list[str] | None
    intent: TopicIntent
    status: TopicStatus
    priority: int | None
    source: TopicSource
    created_at: datetime
    updated_at: datetime


class TopicCreate(BaseModel):
    """Input for ``TopicRepository.create`` / ``bulk_create``."""

    title: str
    primary_kw: str = ""
    secondary_kws: list[str] | None = None
    intent: TopicIntent = TopicIntent.INFORMATIONAL
    status: TopicStatus = TopicStatus.QUEUED
    priority: int | None = None
    source: TopicSource = TopicSource.MANUAL
    cluster_id: int | None = None


# ---------------------------------------------------------------------------
# ClusterRepository.
# ---------------------------------------------------------------------------


class ClusterRepository:
    """Topical map. Self-FK for hierarchy."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def create(
        self,
        *,
        project_id: int,
        name: str,
        type: ClusterType,
        parent_id: int | None = None,
    ) -> Envelope[ClusterOut]:
        """Insert a cluster row."""
        if parent_id is not None:
            parent = self._s.get(Cluster, parent_id)
            if parent is None:
                raise NotFoundError(f"parent cluster {parent_id} not found")
            if parent.project_id != project_id:
                raise ConflictError(
                    "parent cluster belongs to a different project",
                    data={"parent_id": parent_id, "project_id": project_id},
                )
        row = Cluster(project_id=project_id, name=name, type=type, parent_id=parent_id)
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=ClusterOut.model_validate(row), project_id=project_id)

    def list(
        self, project_id: int, *, limit: int | None = None, after_id: int | None = None
    ) -> Page[ClusterOut]:
        """Cursor-paginated list."""
        stmt = select(Cluster).where(Cluster.project_id == project_id)
        return cursor_paginate(
            self._s,
            stmt,
            id_col=Cluster.id,
            limit=limit,
            after_id=after_id,
            converter=ClusterOut.model_validate,
        )

    def get(self, cluster_id: int) -> ClusterOut:
        """Fetch one cluster by id."""
        row = self._s.get(Cluster, cluster_id)
        if row is None:
            raise NotFoundError(f"cluster {cluster_id} not found")
        return ClusterOut.model_validate(row)


# ---------------------------------------------------------------------------
# TopicRepository.
# ---------------------------------------------------------------------------


_TOPIC_SORT_KEYS: dict[str, Sequence[Any]] = {}


class TopicRepository:
    """Topic queue with provenance + state machine."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def create(self, project_id: int, item: TopicCreate) -> Envelope[TopicOut]:
        """Insert a single topic."""
        row = self._build(project_id, item)
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=TopicOut.model_validate(row), project_id=project_id)

    def bulk_create(
        self, project_id: int, items: Iterable[TopicCreate]
    ) -> Envelope[list[TopicOut]]:
        """Insert N topics in input order; return IDs in input order.

        Per audit M-13 we preserve insertion order in the response so
        callers can map ``inputs[i] → outputs[i]`` without an extra
        round-trip.
        """
        materialised = list(items)
        rows = [self._build(project_id, it) for it in materialised]
        for r in rows:
            self._s.add(r)
        self._s.commit()
        for r in rows:
            self._s.refresh(r)
        return Envelope(
            data=[TopicOut.model_validate(r) for r in rows],
            project_id=project_id,
        )

    def list(
        self,
        project_id: int,
        *,
        status: TopicStatus | None = None,
        source: TopicSource | None = None,
        cluster_id: int | None = None,
        sort: Literal["priority", "-priority", "id", "-id"] = "priority",
        limit: int | None = None,
        after_id: int | None = None,
    ) -> Page[TopicOut]:
        """Cursor-paginated list with the queue tiebreaker.

        Default sort is ``priority`` which expands to
        ``ORDER BY priority DESC NULLS LAST, created_at ASC, id ASC``
        per audit B-16. ``id`` / ``-id`` are simple ordering for
        debug + stable cursoring.
        """
        stmt = select(Topic).where(Topic.project_id == project_id)
        if status is not None:
            stmt = stmt.where(Topic.status == status)
        if source is not None:
            stmt = stmt.where(Topic.source == source)
        if cluster_id is not None:
            stmt = stmt.where(Topic.cluster_id == cluster_id)
        # The cursor pagination orders by id ASC; since the queue
        # tiebreaker requires (priority DESC, created_at ASC, id ASC)
        # and our cursor model is monotonic on id, we apply the queue
        # ordering only when the caller asks for it AND short-circuit
        # to a non-cursor path with an in-memory cap. This keeps the
        # cursor invariant simple while still letting `sort='priority'`
        # be the documented behaviour.
        if sort in ("id", "-id"):
            return cursor_paginate(
                self._s,
                stmt,
                id_col=Topic.id,
                limit=limit,
                after_id=after_id,
                converter=TopicOut.model_validate,
            )
        # Queue ordering — apply directly. Cap at limit; ``after_id`` is
        # honoured as ``id > after_id`` for stable continuation.
        if after_id is not None:
            stmt = stmt.where(Topic.id > after_id)  # type: ignore[operator]
        from content_stack.repositories.base import _normalise_limit

        n = _normalise_limit(limit)
        # Add the audit B-16 tiebreaker. NULL priority sorts last so the
        # caller-prioritised rows surface first.
        stmt = stmt.order_by(
            Topic.priority.desc().nullslast(),  # type: ignore[union-attr,attr-defined]
            Topic.created_at.asc(),  # type: ignore[union-attr,attr-defined]
            Topic.id.asc(),  # type: ignore[union-attr,attr-defined]
        ).limit(n + 1)
        rows = list(self._s.exec(stmt))
        items_rows = rows[:n]
        items = [TopicOut.model_validate(r) for r in items_rows]
        next_cursor = int(items_rows[-1].id) if len(rows) > n and items_rows else None  # type: ignore[arg-type]
        # total_estimate uses the unfiltered (by cursor) WHERE.
        total_stmt = select(Topic.id).where(Topic.project_id == project_id)
        if status is not None:
            total_stmt = total_stmt.where(Topic.status == status)
        if source is not None:
            total_stmt = total_stmt.where(Topic.source == source)
        if cluster_id is not None:
            total_stmt = total_stmt.where(Topic.cluster_id == cluster_id)
        total = len(list(self._s.exec(total_stmt)))
        return Page(items=items, next_cursor=next_cursor, total_estimate=total)

    def update(self, topic_id: int, **patch: Any) -> Envelope[TopicOut]:
        """Partial update; status changes go through ``validate_transition``."""
        row = self._fetch(topic_id)
        if "status" in patch:
            new_status = patch["status"]
            if not isinstance(new_status, TopicStatus):
                new_status = TopicStatus(new_status)
            validate_transition(
                row.status, new_status, TOPIC_STATUS_TRANSITIONS, label="topic.status"
            )
            patch["status"] = new_status
        for k, v in patch.items():
            if k in {"id", "project_id", "created_at"}:
                continue
            if not hasattr(row, k):
                raise ValidationError(f"unknown field {k!r}")
            setattr(row, k, v)
        row.updated_at = _utcnow()
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=TopicOut.model_validate(row), project_id=row.project_id)

    def bulk_update_status(
        self, project_id: int, ids: Iterable[int], status: TopicStatus
    ) -> Envelope[list[TopicOut]]:  # type: ignore[valid-type]
        """Move N topics to ``status`` if every transition is legal.

        Validates *all* transitions first so the batch is all-or-nothing.
        """
        ids_list = list(ids)
        rows = self._s.exec(
            select(Topic).where(
                Topic.project_id == project_id,
                Topic.id.in_(ids_list),  # type: ignore[union-attr,attr-defined]
            )
        ).all()
        if len(rows) != len(ids_list):
            found = {r.id for r in rows}
            missing = sorted(set(ids_list) - found)
            raise NotFoundError(
                f"topics not found: {missing}",
                data={"missing": missing, "project_id": project_id},
            )
        for r in rows:
            validate_transition(r.status, status, TOPIC_STATUS_TRANSITIONS, label="topic.status")
        for r in rows:
            r.status = status
            r.updated_at = _utcnow()
            self._s.add(r)
        self._s.commit()
        for r in rows:
            self._s.refresh(r)
        return Envelope(
            data=[TopicOut.model_validate(r) for r in rows],
            project_id=project_id,
        )

    def assign_cluster(self, topic_id: int, cluster_id: int | None) -> Envelope[TopicOut]:
        """Assign a topic to a cluster without changing lifecycle status."""
        return self.update(topic_id, cluster_id=cluster_id)

    def approve(self, topic_id: int) -> Envelope[TopicOut]:
        """Convenience: ``status='approved'``. Wraps ``update``."""
        return self.update(topic_id, status=TopicStatus.APPROVED)

    def reject(self, topic_id: int) -> Envelope[TopicOut]:
        """Convenience: ``status='rejected'``. Wraps ``update``."""
        return self.update(topic_id, status=TopicStatus.REJECTED)

    def get(self, topic_id: int) -> TopicOut:
        """Single-row fetch."""
        return TopicOut.model_validate(self._fetch(topic_id))

    # -------- Internal --------

    def _build(self, project_id: int, item: TopicCreate) -> Topic:
        if item.priority is not None and not (0 <= item.priority <= 100):
            raise ValidationError("priority must be 0..100", data={"priority": item.priority})
        return Topic(
            project_id=project_id,
            cluster_id=item.cluster_id,
            title=item.title,
            primary_kw=item.primary_kw,
            secondary_kws=item.secondary_kws,
            intent=item.intent,
            status=item.status,
            priority=item.priority,
            source=item.source,
        )

    def _fetch(self, topic_id: int) -> Topic:
        row = self._s.get(Topic, topic_id)
        if row is None:
            raise NotFoundError(f"topic {topic_id} not found")
        return row


__all__ = [
    "ClusterOut",
    "ClusterRepository",
    "TopicCreate",
    "TopicOut",
    "TopicRepository",
]
