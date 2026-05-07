"""Shared fixtures for the M1.B repository integration tests.

Each repository test gets a fresh in-memory SQLite engine + Session
created via SQLModel's metadata.create_all (rather than running
Alembic — these tests focus on the repository contract, not the
migration flow which has its own coverage in ``test_schema.py``).

The schema is created once per session and partial-unique indexes are
emitted alongside so the audit B-08 / B-09 / M-20 invariants are
exercised in tests.

M4 addition: a session-scoped fixture wires ``configure_seed_path`` to a
tmp seed file so the AES-GCM round-trip in
``IntegrationCredentialRepository`` succeeds without leaking real seeds.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel

from content_stack.crypto.aes_gcm import configure_seed_path
from content_stack.crypto.seed import ensure_seed_file
from content_stack.db.connection import make_memory_engine


@pytest.fixture(scope="session", autouse=True)
def _crypto_seed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Configure a deterministic per-session seed file.

    M4: ``IntegrationCredentialRepository.set`` now calls into
    ``content_stack.crypto.aes_gcm.encrypt``. That helper requires
    ``configure_seed_path`` to have been called at daemon startup. The
    autouse fixture mirrors what ``server.create_app`` does.
    """
    seed_dir = tmp_path_factory.mktemp("crypto-seed")
    seed_path = seed_dir / "seed.bin"
    ensure_seed_file(seed_path)
    configure_seed_path(seed_path)
    yield seed_path


def _emit_partial_indexes(engine: object) -> None:
    """Issue the migration-only partial-unique indexes against an in-memory DB.

    Mirrors the SQL run by ``0002_initial_schema``'s post-create block. We
    keep the list short — only the partial uniques tests reference; new
    tests can add to this if needed.
    """
    statements = [
        # Partial unique on internal_links (audit B-09)
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_internal_links_unique "
        "ON internal_links(from_article_id, to_article_id, anchor_text, position) "
        "WHERE status != 'dismissed'",
        # Primary publish target (audit B-08)
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_publish_targets_primary "
        "ON publish_targets(project_id) WHERE is_primary = 1",
        # GSC dedup composite (PLAN.md L483)
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_gsc_metrics_dedup "
        "ON gsc_metrics(project_id, article_id, captured_at, dimensions_hash)",
        # Idempotency (audit M-20)
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_idempotency "
        "ON idempotency_keys(project_id, tool_name, idempotency_key)",
        # Article slug uniqueness (PLAN.md L484)
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_article_slug ON articles(project_id, slug)",
    ]
    with engine.begin() as conn:  # type: ignore[attr-defined]
        for s in statements:
            conn.execute(text(s))


@pytest.fixture
def session() -> Iterator[Session]:
    """Yield a fresh ``Session`` bound to an in-memory SQLite engine."""
    engine = make_memory_engine()
    SQLModel.metadata.create_all(engine)
    _emit_partial_indexes(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def project_id(session: Session) -> int:
    """Create a project with EEAT seeded; return its id.

    Uses ``ProjectRepository.create`` so the EEAT seeding path is
    exercised across the suite.
    """
    from content_stack.repositories.projects import ProjectRepository

    repo = ProjectRepository(session)
    env = repo.create(
        slug="t-proj",
        name="Test Project",
        domain="example.com",
        locale="en-US",
    )
    pid = env.data.id
    assert pid is not None
    return pid
