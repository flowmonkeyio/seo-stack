"""Runtime configuration — XDG paths, daemon port, log level.

Centralised so every subsystem (server, CLI, doctor, migrations) reads the
same source of truth. Loopback-only enforcement happens in `BaseSettings`
validation rather than the CLI alone, so a misconfigured `.env` is also
rejected.
"""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})


def _default_data_dir() -> Path:
    """Return the XDG-style data directory.

    `~/.local/share/content-stack/` matches the spec and the gitignore
    expectation that DB files live outside the repo.
    """
    return Path.home() / ".local" / "share" / "content-stack"


def _default_state_dir() -> Path:
    """Return the XDG-style state directory.

    `~/.local/state/content-stack/` is where transient or rotateable state
    lives — seed, auth token, PID, logs.
    """
    return Path.home() / ".local" / "state" / "content-stack"


class Settings(BaseSettings):
    """Top-level settings, env-prefixed with `CONTENT_STACK_`."""

    model_config = SettingsConfigDict(
        env_prefix="CONTENT_STACK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Network
    host: str = "127.0.0.1"
    port: int = 5180

    # Logging
    log_level: str = "INFO"

    # Paths (overridable via env for tests / non-default installs)
    data_dir: Path = _default_data_dir()
    state_dir: Path = _default_state_dir()

    # ---- M7 procedure runner --------------------------------------------
    # Selection of the LLM dispatcher behind the procedure runner. The
    # ``stub`` value is the M7.A default — it lets the runner prove the
    # daemon-orchestrated dispatch contract (D4) end-to-end without burning
    # OpenAI / Anthropic tokens. Production deployments switch to
    # ``openai`` or ``anthropic`` once the real provider dispatchers land
    # (M7 follow-up). The corresponding integration credential row
    # (``kind='openai-procedure-runner'`` or
    # ``kind='anthropic-procedure-runner'``) holds the API key, separate
    # from any other integration credential per audit M-11.
    procedure_runner_llm: Literal["stub", "openai", "anthropic"] = "stub"

    # The maximum number of FIX-loop iterations the runner takes before
    # aborting a procedure. Per audit BLOCKER-09 the default of 3 stops
    # the editor + eeat-gate cycle from running away when the editor
    # cannot satisfy the gate.
    procedure_runner_max_loop_iterations: int = 3

    # Default ceiling on parallel runs of the same procedure. Each
    # procedure can override via ``concurrency_limit:`` in its
    # PROCEDURE.md frontmatter; this setting is the runtime fallback
    # when a procedure doesn't declare its own.
    procedure_runner_default_concurrency: int = 4

    @field_validator("host")
    @classmethod
    def _reject_non_loopback(cls, v: str) -> str:
        """Reject any host that is not a loopback address.

        We bind by name *or* IP, so accept the canonical loopback names plus
        anything that parses as an IPv4/IPv6 loopback. Cross-machine binding
        is a single-user-product class-of-bug we explicitly close at parse
        time.
        """
        if v in _LOOPBACK_HOSTS:
            return v
        try:
            addr = ipaddress.ip_address(v)
        except ValueError as exc:
            raise ValueError(
                f"host {v!r} is not a loopback address (use 127.0.0.1, ::1, or localhost)"
            ) from exc
        if not addr.is_loopback:
            raise ValueError(f"host {v!r} is not a loopback address — refusing to bind")
        return v

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, v: str) -> str:
        """Normalise log level to upper-case and validate against logging stdlib."""
        upper = v.upper()
        if upper not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}:
            raise ValueError(f"invalid log_level {v!r}")
        return upper

    # ---- Derived paths --------------------------------------------------

    @property
    def db_path(self) -> Path:
        """SQLite DB file (created on first migrate)."""
        return self.data_dir / "content-stack.db"

    @property
    def seed_path(self) -> Path:
        """32-byte HKDF seed for integration-credential encryption (M5)."""
        return self.state_dir / "seed.bin"

    @property
    def token_path(self) -> Path:
        """Per-install bearer token used by REST + MCP middleware."""
        return self.state_dir / "auth.token"

    @property
    def log_path(self) -> Path:
        """Daemon log file — rotated by RotatingFileHandler at 10 MB x 5."""
        return self.state_dir / "daemon.log"

    @property
    def pid_path(self) -> Path:
        """PID file written by the daemon at startup (M9 launchd integration)."""
        return self.state_dir / "daemon.pid"

    # ---- Side-effecting helpers ----------------------------------------

    def ensure_dirs(self) -> None:
        """Create data + state directories with mode 0700.

        We use `os.makedirs` + explicit chmod rather than `Path.mkdir(mode=...)`
        because the latter is filtered through umask and can land at 0750 or
        wider on a default-umask system. Re-running adjusts the mode of an
        existing dir, which is what we want.
        """
        for d in (self.data_dir, self.state_dir):
            d.mkdir(parents=True, exist_ok=True)
            os.chmod(d, 0o700)


def get_settings() -> Settings:
    """Build a Settings instance — kept callable so tests can patch env first."""
    return Settings()
