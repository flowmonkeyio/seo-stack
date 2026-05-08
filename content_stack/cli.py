"""Typer CLI surface for the daemon.

Subcommand inventory matches PLAN.md's CLI reference. M0 implements `serve`
and a minimal `doctor`; later subcommands deliberately raise `NotImplementedError`
or print the milestone tag and exit, so the CLI shape is fixed from day one.
"""

from __future__ import annotations

import json
import os
import socket
import stat
from pathlib import Path
from typing import Annotated, Literal

import typer

from content_stack import __milestone__, __version__
from content_stack.config import Settings, get_settings

app = typer.Typer(
    name="content-stack",
    help=(
        "content-stack daemon CLI — `serve` runs the daemon, `doctor` diagnoses "
        "an install. Other subcommands stub to milestone tags until implemented."
    ),
    no_args_is_help=True,
    add_completion=False,
)


_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})


def _exit(code: int) -> None:
    """Exit via typer.Exit so context managers (e.g. uvicorn) unwind cleanly."""
    raise typer.Exit(code=code)


def _print_version(value: bool) -> None:
    """Eager `--version` callback — short-circuits before subcommand resolution."""
    if value:
        typer.echo(f"content-stack {__version__} ({__milestone__})")
        raise typer.Exit(code=0)


@app.callback()
def _root(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Print version and exit",
            callback=_print_version,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Top-level options. `--version` short-circuits the help-on-no-args flow."""
    _ = ctx
    _ = version


# ---- serve ----------------------------------------------------------------


@app.command()
def serve(
    host: Annotated[
        str,
        typer.Option("--host", help="Loopback address to bind"),
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="TCP port")] = 5180,
    log_level: Annotated[
        str,
        typer.Option("--log-level", help="Log level (DEBUG/INFO/WARNING/ERROR)"),
    ] = "INFO",
) -> None:
    """Run the daemon foreground.

    Refuses non-loopback hosts at parse time per PLAN.md M-37 — `0.0.0.0`
    exits with code 1 and a one-line explanation rather than uvicorn binding
    publicly and the host-header middleware paper-clipping the leak.
    """
    if host not in _LOOPBACK_HOSTS:
        # Try one more parse for edge cases like 0:0:0:0:0:0:0:1.
        import ipaddress

        ok = False
        try:
            addr = ipaddress.ip_address(host)
            ok = addr.is_loopback
        except ValueError:
            ok = False
        if not ok:
            # PLAN.md L1267 mandates exit code 1 for misuse, distinct from
            # typer.BadParameter's default 2. We emit a one-line stderr
            # message and exit 1 directly.
            typer.echo(
                f"error: --host {host!r} is not a loopback address; refusing to bind. "
                "Use 127.0.0.1, ::1, or localhost.",
                err=True,
            )
            raise typer.Exit(code=1)

    # Override settings with CLI flags by stuffing into env *before* importing
    # uvicorn — pydantic-settings will read these.
    os.environ["CONTENT_STACK_HOST"] = host
    os.environ["CONTENT_STACK_PORT"] = str(port)
    os.environ["CONTENT_STACK_LOG_LEVEL"] = log_level.upper()

    # Late-import uvicorn so `--help` is fast and the heavy import only
    # happens on actual serve.
    import uvicorn

    uvicorn.run(
        "content_stack.server:create_app",
        host=host,
        port=port,
        factory=True,
        log_level=log_level.lower(),
        reload=False,
    )


# ---- doctor ---------------------------------------------------------------


def _tcp_can_connect(host: str, port: int, timeout: float = 0.5) -> bool:
    """Return True iff a TCP connect to (host, port) succeeds within `timeout`."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _file_mode_or_none(path: Path) -> int | None:
    """Return the file's permission bits or None if it does not exist."""
    if not path.exists():
        return None
    return stat.S_IMODE(path.stat().st_mode)


def _check_credentials_decrypt(
    settings: Settings,
    db_present: bool,
) -> tuple[bool, list[dict[str, object]]]:
    """Return ``(all_ok, [issues])`` for every integration_credentials row.

    Each issue is ``{credential_id, kind, project_id, error}``. Returns
    ``(True, [])`` when there are zero rows or when the DB does not
    exist yet — those are not failures, just a fresh install.
    """
    if not db_present:
        return True, []
    try:
        from sqlmodel import Session, select

        from content_stack.crypto.aes_gcm import (
            CryptoError,
            configure_seed_path,
        )
        from content_stack.db.connection import make_engine
        from content_stack.db.models import IntegrationCredential
        from content_stack.repositories.projects import IntegrationCredentialRepository

        configure_seed_path(settings.seed_path)
        engine = make_engine(settings.db_path)
        issues: list[dict[str, object]] = []
        try:
            with Session(engine) as session:
                rows = session.exec(select(IntegrationCredential)).all()
                repo = IntegrationCredentialRepository(session)
                for row in rows:
                    if row.id is None:
                        continue
                    try:
                        repo.get_decrypted(row.id)
                    except CryptoError as exc:
                        issues.append(
                            {
                                "credential_id": row.id,
                                "kind": row.kind,
                                "project_id": row.project_id,
                                "error": str(exc.detail),
                            }
                        )
        finally:
            engine.dispose()
    except Exception as exc:  # pragma: no cover — defensive
        return False, [{"error": f"doctor probe failed: {exc}"}]
    return len(issues) == 0, issues


def _check_alembic_at_head(settings: Settings, db_present: bool) -> tuple[bool, str | None]:
    """Confirm ``alembic_version`` row matches the expected head.

    Returns ``(ok, version_or_None)``. A missing DB (fresh install) is
    treated as a non-failure — ``code=4`` only fires when the DB exists
    AND the version table is missing or stale.
    """
    if not db_present:
        return True, None
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from sqlalchemy import text as sa_text

        from content_stack.db.connection import make_engine

        engine = make_engine(settings.db_path)
        try:
            with engine.connect() as conn:
                row = conn.execute(sa_text("SELECT version_num FROM alembic_version")).first()
                current = row[0] if row else None
            cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
            script = ScriptDirectory.from_config(cfg)
            head = script.get_current_head()
            return current == head, current
        finally:
            engine.dispose()
    except Exception:  # pragma: no cover — defensive
        return False, None


def _check_scheduler_jobs(settings: Settings) -> tuple[bool, int]:
    """Lightweight liveness check for APScheduler.

    M8 doesn't expose an out-of-band query for scheduled jobs (the
    daemon owns the scheduler instance), so for the doctor we fall back
    to checking that the daemon is up — when it is, we trust the
    lifespan registered the four ops jobs.
    """
    daemon_up = _tcp_can_connect(settings.host, settings.port)
    return daemon_up, 4 if daemon_up else 0


@app.command()
def doctor(
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON")] = False,
) -> None:
    """Diagnose the install — M8 expanded.

    Exit codes (subset of PLAN.md L1271):
      0 all green
      1 daemon down
      4 alembic head mismatch
      7 auth token missing or wrong mode
      8 seed file missing or wrong mode

    The DB-not-yet-created case is a *warning*, not a failure — first install
    has no DB until `make migrate` runs.
    """
    settings = get_settings()

    daemon_up = _tcp_can_connect(settings.host, settings.port)

    seed_mode = _file_mode_or_none(settings.seed_path)
    seed_ok = seed_mode == 0o600

    token_mode = _file_mode_or_none(settings.token_path)
    token_ok = token_mode == 0o600

    db_present = settings.db_path.exists()

    # M4: walk every integration_credentials row and confirm it
    # decrypts cleanly. A failure here usually means the seed file was
    # rotated outside the CLI or restored from a backup that doesn't
    # match the DB's credentials. We surface it as an issue list rather
    # than crashing doctor — operators want a full report, not a
    # half-finished one.
    credentials_ok, credential_issues = _check_credentials_decrypt(settings, db_present)

    # M8: alembic-head + scheduler-jobs probes.
    alembic_ok, alembic_version = _check_alembic_at_head(settings, db_present)
    scheduler_ok, scheduler_job_count = _check_scheduler_jobs(settings)

    checks = {
        "daemon_up": daemon_up,
        "seed_file_present": seed_mode is not None,
        "seed_file_mode_0600": seed_ok,
        "auth_token_present": token_mode is not None,
        "auth_token_mode_0600": token_ok,
        "db_file_present": db_present,
        "credentials_decrypt": credentials_ok,
        "alembic_at_head": alembic_ok,
        "scheduler_jobs_healthy": scheduler_ok,
    }
    info = {
        "host": settings.host,
        "port": settings.port,
        "data_dir": str(settings.data_dir),
        "state_dir": str(settings.state_dir),
        "seed_mode": oct(seed_mode) if seed_mode is not None else None,
        "token_mode": oct(token_mode) if token_mode is not None else None,
        "version": __version__,
        "milestone": __milestone__,
        "credential_issues": credential_issues,
        "alembic_version": alembic_version,
        "scheduler_job_count": scheduler_job_count,
    }

    # Compute exit code with the highest-priority failure winning so a single
    # `doctor` invocation gives the operator the most actionable signal.
    # Credential decrypt failures imply seed mismatch (operator restored a
    # DB without the seed, or seed was overwritten); we surface that as
    # the same exit-code 8 as a missing seed since the remediation is
    # identical (find the right seed or rotate).
    if seed_mode is None or not seed_ok or not credentials_ok:
        code = 8
    elif token_mode is None or not token_ok:
        code = 7
    elif not alembic_ok:
        code = 4
    elif not daemon_up:
        code = 1
    else:
        code = 0

    if json_output:
        typer.echo(json.dumps({"ok": code == 0, "code": code, "checks": checks, "info": info}))
    else:
        status = "OK" if code == 0 else "ISSUES"
        typer.echo(f"content-stack doctor: {status} (exit code {code})")
        for name, val in checks.items():
            mark = "  ok " if val else " FAIL"
            typer.echo(f"  [{mark}] {name}: {val}")
        if not db_present:
            typer.echo("  note: DB not yet created — run `make migrate` after first install.")
        if credential_issues:
            typer.echo(
                f"  note: {len(credential_issues)} credential row(s) failed to decrypt — "
                "see --json output for details."
            )

    _exit(code)


# ---- stubbed subcommands --------------------------------------------------


def _stub(milestone: str, name: str) -> None:
    """Print a milestone tag and exit 0 — uniform format for stubbed CLIs."""
    typer.echo(f"`content-stack {name}` not yet implemented ({milestone}).")


@app.command()
def init(
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing config")] = False,
) -> None:
    """Initialize XDG dirs, seed, and bearer token.

    Idempotent: re-running on a populated state dir is a no-op (the
    seed and token are read but not regenerated). ``--force`` is
    accepted for symmetry with PLAN.md L1268; it is rejected here as
    too dangerous to wire blindly — operators wanting to rotate seed
    should call ``content-stack rotate-seed`` and ``rotate-token``
    explicitly so the side-effects (re-encryption, MCP re-registration)
    cannot be skipped accidentally.
    """
    if force:
        typer.echo(
            "error: --force on `init` is intentionally not implemented. "
            "Use `content-stack rotate-seed --reencrypt` or `rotate-token --yes`.",
            err=True,
        )
        raise typer.Exit(code=2)

    from content_stack.auth import ensure_token
    from content_stack.crypto.seed import ensure_seed_file

    settings = get_settings()
    settings.ensure_dirs()
    ensure_seed_file(settings.seed_path)
    ensure_token(settings.token_path)
    typer.echo(f"init: state dir at {settings.state_dir}; seed + auth.token present (mode 0600).")


@app.command()
def migrate() -> None:
    """Run alembic migrations forward to head."""
    from alembic import command
    from alembic.config import Config

    settings = get_settings()
    settings.ensure_dirs()
    cfg_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    cfg = Config(str(cfg_path))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{settings.db_path}")
    command.upgrade(cfg, "head")
    typer.echo(f"migrate: alembic upgraded to head ({settings.db_path}).")


@app.command()
def install(
    skills_only: Annotated[
        bool,
        typer.Option("--skills-only", help="Only mirror skills/ into the runtimes."),
    ] = False,
    procedures_only: Annotated[
        bool,
        typer.Option("--procedures-only", help="Only mirror procedures/ into the runtimes."),
    ] = False,
    mcp_only: Annotated[
        bool,
        typer.Option("--mcp-only", help="Only register the MCP server."),
    ] = False,
    launchd: Annotated[
        bool,
        typer.Option("--launchd", help="Also install the launchd plist (macOS)."),
    ] = False,
    skip_doctor: Annotated[
        bool,
        typer.Option("--skip-doctor", help="Skip the post-install doctor check."),
    ] = False,
) -> None:
    """End-user one-liner install — clone-mode or pipx-mode.

    Auto-detects whether the package was installed from a checked-out
    repo (uses the bash scripts under ``scripts/``) or via pipx (resolves
    bundled assets via ``importlib.resources``). The two paths land at
    the same end state.

    Re-running is idempotent (audit B-24): skills + procedures use
    rsync-style ``--delete`` mirroring, and MCP registration upserts
    existing entries.
    """
    from content_stack import install as installer

    selectors = [skills_only, procedures_only, mcp_only]
    if sum(1 for s in selectors if s) > 1:
        typer.echo(
            "error: --skills-only, --procedures-only, and --mcp-only are mutually exclusive.",
            err=True,
        )
        raise typer.Exit(code=2)
    do_skills = skills_only or not (procedures_only or mcp_only)
    do_procedures = procedures_only or not (skills_only or mcp_only)
    do_mcp = mcp_only or not (skills_only or procedures_only)

    mode = installer.detect_mode()
    typer.echo(f"==> Install mode: {mode}")

    settings = get_settings()
    settings.ensure_dirs()
    home = Path.home()

    runtimes: tuple[Literal["codex", "claude"], ...] = ("codex", "claude")
    if do_skills:
        for runtime in runtimes:
            target, count = installer.copy_skills(runtime, home=home)
            typer.echo(f"==> Installed {count} skills -> {target}")

    if do_procedures:
        for runtime in runtimes:
            target, count = installer.copy_procedures(runtime, home=home)
            typer.echo(f"==> Installed {count} procedures -> {target}")

    if do_mcp:
        # Codex first; it prints its own skip-line if not on PATH.
        msg = installer.register_mcp_codex(home=home, port=settings.port)
        typer.echo(f"==> {msg}")
        msg = installer.register_mcp_claude(home=home, port=settings.port)
        typer.echo(f"==> {msg}")

    if launchd:
        # Defer to the bash script; pipx-mode users still get launchd
        # via the script if they have a clone of the repo. Without a
        # repo we cannot generate a sensible plist (the daemon needs a
        # working directory) — surface that explicitly.
        scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
        plist_script = scripts_dir / "install-launchd.sh"
        if plist_script.is_file():
            import subprocess

            subprocess.run(["bash", str(plist_script)], check=True)
        else:
            typer.echo(
                "warning: --launchd requires a checked-out repo (script not in wheel).",
                err=True,
            )

    if not skip_doctor:
        typer.echo("==> Running doctor")
        # Re-enter the doctor command in-process so the exit code
        # propagates. We delegate to the underlying typer command via
        # the same module to avoid duplicating the logic.
        try:
            doctor(json_output=False)
        except typer.Exit as exc:
            # Surface the doctor exit code as the install exit code so
            # `make install` fails loudly when the daemon is not yet up.
            if exc.exit_code not in (0, None):
                raise
    typer.echo("==> install complete")


@app.command(name="rotate-seed")
def rotate_seed(
    reencrypt: Annotated[
        bool,
        typer.Option(
            "--reencrypt",
            help="Required — re-encrypt every integration_credentials row under a fresh seed.",
        ),
    ] = False,
) -> None:
    """Rotate the integration-credentials seed.

    Per PLAN.md L1136-L1142: writes a fresh 32-byte seed, re-encrypts
    every credential row in a single SQLite transaction, and keeps the
    old seed at ``seed.bin.bak`` for one daemon boot. ``--reencrypt`` is
    mandatory because rotating without re-encrypting would orphan every
    existing credential.
    """
    if not reencrypt:
        typer.echo(
            "error: rotate-seed requires --reencrypt (rotating without re-encryption "
            "would orphan every credential row).",
            err=True,
        )
        raise typer.Exit(code=2)

    from sqlmodel import Session

    from content_stack.crypto.aes_gcm import configure_seed_path
    from content_stack.crypto.seed import rotate_seed as crypto_rotate_seed
    from content_stack.db.connection import make_engine
    from content_stack.db.models import IntegrationCredential

    settings = get_settings()
    settings.ensure_dirs()
    configure_seed_path(settings.seed_path)
    engine = make_engine(settings.db_path)
    try:
        with Session(engine) as session:
            from sqlmodel import select

            rows = list(session.exec(select(IntegrationCredential)).all())
            row_dicts = [
                {
                    "id": r.id,
                    "project_id": r.project_id,
                    "kind": r.kind,
                    "encrypted_payload": r.encrypted_payload,
                    "nonce": r.nonce,
                }
                for r in rows
            ]
            _, rotated = crypto_rotate_seed(settings.seed_path, rows=row_dicts)
            id_to_row = {r.id: r for r in rows}
            for rotated_row in rotated:
                row = id_to_row[rotated_row["id"]]
                row.encrypted_payload = rotated_row["encrypted_payload"]
                row.nonce = rotated_row["nonce"]
                session.add(row)
            session.commit()
        # Drop any cached key from the old seed so subsequent calls in
        # this process re-derive from the fresh seed file.
        configure_seed_path(settings.seed_path)
        typer.echo(f"rotate-seed: rotated {len(rows)} row(s); old seed → seed.bin.bak")
    finally:
        engine.dispose()


@app.command(name="rotate-token")
def rotate_token(
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help="Required — rotating without confirmation invalidates every existing MCP config.",
        ),
    ] = False,
) -> None:
    """Rotate the bearer auth token and re-register MCP configs.

    Per PLAN.md L1273: writes a fresh 32 bytes to ``auth.token`` (mode
    0600) then re-registers Codex + Claude Code so their saved
    Authorization headers match the new token. Existing tokens become
    invalid the moment this completes — that is the whole point.
    """
    if not yes:
        typer.echo(
            "error: rotate-token requires --yes (rotating invalidates every existing "
            "MCP config until the registration scripts re-run).",
            err=True,
        )
        raise typer.Exit(code=2)

    import secrets

    from content_stack import install as installer

    settings = get_settings()
    settings.ensure_dirs()
    new_token = secrets.token_hex(32)
    token_path = settings.token_path
    # Write under temp + rename for atomicity, mode 0600 enforced.
    fd = os.open(
        str(token_path) + ".new",
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(new_token)
        f.write("\n")
    os.replace(str(token_path) + ".new", token_path)

    # Re-register so saved Authorization headers refresh.
    msg = installer.register_mcp_codex(port=settings.port, force=True)
    typer.echo(msg)
    msg = installer.register_mcp_claude(port=settings.port)
    typer.echo(msg)
    typer.echo("rotate-token: token rotated; MCP configs updated.")


@app.command()
def backup() -> None:
    """Atomic SQLite .backup + copy seed/auth-token (M9)."""
    _stub("M9: jobs/scheduling", "backup")


@app.command()
def restore(
    file: Annotated[Path, typer.Argument(help="Path to a .db backup")],
) -> None:
    """Halt daemon, restore DB from backup, restart (M9)."""
    _ = file
    _stub("M9: jobs/scheduling", "restore")


# Re-export Settings on the module so tests can `from content_stack.cli import Settings`
# (handy for end-to-end smoke tests that want to assert on env-derived paths).
__all__ = ["Settings", "app"]
