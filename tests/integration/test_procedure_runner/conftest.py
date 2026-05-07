"""Fixtures for the M7.A procedure-runner integration tests.

Each test runs against an in-memory SQLite engine with the same
schema-priming pattern repository tests use (``SQLModel.metadata.create_all``
plus the partial-unique indexes that Alembic emits in 0002). The
``ProcedureRunner`` is constructed against that engine with a fresh
``StubDispatcher`` per test so handler overrides don't bleed across.

The shared ``scenario`` fixture seeds a project + topic + the publish
target the procedure-04 publish step expects so tests don't have to
re-encode that boilerplate.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel

from content_stack.config import Settings
from content_stack.crypto.aes_gcm import configure_seed_path
from content_stack.crypto.seed import ensure_seed_file
from content_stack.db.connection import make_memory_engine
from content_stack.db.models import (
    PublishTarget,
    PublishTargetKind,
    Topic,
    TopicIntent,
    TopicSource,
    TopicStatus,
)
from content_stack.procedures.llm import StubDispatcher
from content_stack.procedures.runner import ProcedureRunner
from content_stack.repositories.projects import ProjectRepository


@pytest.fixture(scope="session", autouse=True)
def _crypto_seed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    seed_dir = tmp_path_factory.mktemp("runner-crypto-seed")
    seed_path = seed_dir / "seed.bin"
    ensure_seed_file(seed_path)
    configure_seed_path(seed_path)
    yield seed_path


def _emit_partial_indexes(engine: object) -> None:
    """Emit the partial-unique indexes the runner exercises."""
    statements = [
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_internal_links_unique "
        "ON internal_links(from_article_id, to_article_id, anchor_text, position) "
        "WHERE status != 'dismissed'",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_publish_targets_primary "
        "ON publish_targets(project_id) WHERE is_primary = 1",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_idempotency "
        "ON idempotency_keys(project_id, tool_name, idempotency_key)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_article_slug ON articles(project_id, slug)",
    ]
    with engine.begin() as conn:  # type: ignore[attr-defined]
        for s in statements:
            conn.execute(text(s))


@pytest.fixture
def engine() -> Iterator[object]:
    """In-memory SQLite engine with the full schema."""
    eng = make_memory_engine()
    SQLModel.metadata.create_all(eng)
    _emit_partial_indexes(eng)
    yield eng


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Lightweight Settings pointed at tmp dirs."""
    return Settings(
        host="127.0.0.1",
        port=5180,
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
    )


@pytest.fixture
def dispatcher() -> StubDispatcher:
    """One ``StubDispatcher`` per test — fresh handler registry each run."""
    return StubDispatcher()


@pytest.fixture
def runner(
    engine: object,
    settings: Settings,
    dispatcher: StubDispatcher,
) -> ProcedureRunner:
    """``ProcedureRunner`` bound to the test engine + stub dispatcher.

    Uses the repo-root ``procedures/`` directory so the M7.A
    procedure-04 spec loads automatically. The runner picks up the
    sibling ``skills/`` directory for SKILL.md bodies; missing skills
    are tolerated (the stub doesn't read them).
    """
    repo_root = Path(__file__).resolve().parents[3]
    return ProcedureRunner(
        settings=settings,
        engine=engine,
        dispatcher=dispatcher,
        procedures_dir=repo_root / "procedures",
    )


@pytest.fixture
def scenario(engine: object) -> dict[str, int]:
    """Seed a project + topic + primary publish target.

    Procedure 4 reads the project's primary publish target to pick the
    publish skill at dispatch time; we wire a default ``nuxt-content``
    target so the runner doesn't trip on a missing publisher. Tests
    that need a different publisher kind override after this fixture.
    """
    with Session(engine) as s:
        project_repo = ProjectRepository(s)
        env = project_repo.create(
            slug="m7-test",
            name="M7 Test",
            domain="m7-test.example",
            locale="en-US",
        )
        pid = env.data.id
        assert pid is not None

        topic = Topic(
            project_id=pid,
            title="A test topic for the workhorse procedure",
            primary_kw="test topic",
            intent=TopicIntent.INFORMATIONAL,
            source=TopicSource.MANUAL,
            status=TopicStatus.APPROVED,
        )
        s.add(topic)
        s.commit()
        s.refresh(topic)
        topic_id = topic.id
        assert topic_id is not None

        target = PublishTarget(
            project_id=pid,
            kind=PublishTargetKind.NUXT_CONTENT,
            config_json={"repo": "test/site"},
            is_primary=True,
            is_active=True,
        )
        s.add(target)
        s.commit()

    return {"project_id": pid, "topic_id": topic_id}
