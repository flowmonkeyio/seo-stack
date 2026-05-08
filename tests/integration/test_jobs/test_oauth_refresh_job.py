"""OAuth refresh job — verifies the M4 worker plays cleanly with APScheduler.

We don't run a real refresh against Google here — the M4 worker has its
own integration tests for that. M8's job is to verify:

- The worker function imports cleanly + the lifespan registers it.
- Calling it with no expiring credentials returns the empty counter.
"""

from __future__ import annotations

from sqlmodel import Session

from content_stack.jobs.oauth_refresh import refresh_expiring_gsc_tokens


async def test_oauth_refresh_returns_empty_counter_with_no_creds(engine: object) -> None:
    """No GSC credentials → ``checked=refreshed=failed=0``."""
    with Session(engine) as s:  # type: ignore[arg-type]
        counter = await refresh_expiring_gsc_tokens(s)
    assert counter == {"checked": 0, "refreshed": 0, "failed": 0}
