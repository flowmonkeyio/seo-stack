"""APScheduler jobs.

M4 lands the ``oauth_refresh`` worker (refresh GSC tokens before they
expire). The remaining jobs (``gsc_pull``, ``drift_check``,
``refresh_detector``) ship in M8 with the scheduler subsystem.
"""

from __future__ import annotations
