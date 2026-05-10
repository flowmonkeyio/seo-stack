"""Concurrency + B-07 acceptance benchmark for ``ArticleRepository``.

Two purposes:

- ``test_etag_mismatch_rejects_concurrent_set_draft`` — locks down the
  optimistic concurrency contract: two callers reading the same etag
  cannot both write; the second gets ``ConflictError``.
- ``test_100_sequential_set_draft_under_2s`` — the audit B-07 / PLAN.md
  L1615 acceptance benchmark: 100 sequential 200 KB ``set_draft`` calls
  must complete in under 2 seconds on a 2020 MBP-class machine.
  Marked ``benchmark`` so CI can run it explicitly via
  ``pytest -m benchmark``.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel

from content_stack.db.connection import make_engine, make_memory_engine
from content_stack.repositories.articles import ArticleRepository
from content_stack.repositories.base import ConflictError
from content_stack.repositories.projects import ProjectRepository


@pytest.fixture
def session() -> Iterator[Session]:
    """Fresh in-memory engine for each concurrency test."""
    engine = make_memory_engine()
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_article_slug ON articles(project_id, slug)")
        )
    with Session(engine) as s:
        yield s


@pytest.fixture
def project_id(session: Session) -> int:
    """A seeded project to host benchmark articles."""
    repo = ProjectRepository(session)
    env = repo.create(slug="bench", name="bench", domain="example.com", locale="en-US")
    pid = env.data.id
    assert pid is not None
    return pid


def test_etag_mismatch_rejects_concurrent_set_draft(session: Session, project_id: int) -> None:
    """Two writers sharing the same expected_etag — only the first wins."""
    repo = ArticleRepository(session)
    art = repo.create(project_id=project_id, topic_id=None, title="C", slug="concurrent").data
    e = art.step_etag
    e = repo.set_brief(art.id, {"x": 1}, expected_etag=e).data.step_etag
    e = repo.set_outline(art.id, "outline", expected_etag=e).data.step_etag

    # Two callers read the same etag.
    shared_etag = e
    out1 = repo.set_draft(art.id, "first writer", expected_etag=shared_etag)
    assert out1.data.draft_md == "first writer"
    # The second writer is operating on a stale etag.
    with pytest.raises(ConflictError) as exc_info:
        repo.set_draft(art.id, "second writer", expected_etag=shared_etag)
    assert exc_info.value.code == -32008
    assert "expected_etag" in exc_info.value.detail


def test_stale_session_etag_compare_and_swap_is_atomic(tmp_path: Path) -> None:
    """A stale identity-map row cannot overwrite a committed etag change."""
    engine = make_engine(tmp_path / "article-concurrency.sqlite")
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_article_slug ON articles(project_id, slug)")
        )

    with Session(engine) as setup:
        project_id = (
            ProjectRepository(setup)
            .create(
                slug="atomic",
                name="atomic",
                domain="example.com",
                locale="en-US",
            )
            .data.id
        )
        assert project_id is not None
        repo = ArticleRepository(setup)
        art = repo.create(project_id=project_id, topic_id=None, title="C", slug="atomic-art").data
        assert art.id is not None
        etag = art.step_etag
        etag = repo.set_brief(art.id, {"x": 1}, expected_etag=etag).data.step_etag
        shared_etag = repo.set_outline(art.id, "outline", expected_etag=etag).data.step_etag
        article_id = art.id

    with Session(engine) as s1, Session(engine) as s2:
        repo1 = ArticleRepository(s1)
        repo2 = ArticleRepository(s2)
        repo2.get(article_id)

        out = repo1.set_draft(article_id, "first writer", expected_etag=shared_etag)
        assert out.data.draft_md == "first writer"

        with pytest.raises(ConflictError):
            repo2.set_draft(article_id, "second writer", expected_etag=shared_etag)

    with Session(engine) as check:
        assert ArticleRepository(check).get(article_id).draft_md == "first writer"


@pytest.mark.benchmark
def test_100_sequential_set_draft_under_2s(session: Session, project_id: int) -> None:
    """Audit B-07 acceptance: 100 sequential set_draft of 200 KB each < 2s."""
    repo = ArticleRepository(session)
    art = repo.create(project_id=project_id, topic_id=None, title="B", slug="bench-art").data
    e = art.step_etag
    e = repo.set_brief(art.id, {"x": 1}, expected_etag=e).data.step_etag
    e = repo.set_outline(art.id, "outline", expected_etag=e).data.step_etag

    # 200 KB markdown per call.
    body = "x" * (200 * 1024)
    start = time.perf_counter()
    for _ in range(100):
        out = repo.set_draft(art.id, body, expected_etag=e, append=False)
        e = out.data.step_etag
    elapsed = time.perf_counter() - start
    # Write the wall-clock to the captured-stdout for the deliverable report.
    print(f"\nbenchmark: 100 set_draft calls took {elapsed:.3f}s")
    assert elapsed < 2.0, f"benchmark exceeded 2.0s ceiling: {elapsed:.3f}s"


# Where to write the benchmark log so the deliverable can quote it.
_BENCHMARK_LOG = Path(__file__).parent / "_benchmark.log"
