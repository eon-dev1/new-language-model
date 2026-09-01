"""
Verification Step 12 — the startup auth gate must finish inside the window
Electron's backend-manager gives it before declaring startup failed.

The gate spends AUTH_BUDGET_S TWICE (anonymous probe, then authenticated
connect), then ENFORCE_BUDGET_S once. The factor of two is not cosmetic:
writing it as a plain sum would leave AUTH_BUDGET_S of drift headroom that
does not exist.

The ceiling mirrors backend-manager.ts's MAX_RETRIES (30) * RETRY_INTERVAL
(1000ms) = 30s. If either budget or the frontend retry window drifts, this
fails loudly.
"""

import main

FRONTEND_STARTUP_WINDOW_S = 30  # backend-manager.ts: MAX_RETRIES * RETRY_INTERVAL


def test_auth_gate_budget_fits_frontend_startup_window():
    worst_case = 2 * main.AUTH_BUDGET_S + main.ENFORCE_BUDGET_S
    assert worst_case < FRONTEND_STARTUP_WINDOW_S, (
        f"auth gate worst case {worst_case}s must stay under the "
        f"{FRONTEND_STARTUP_WINDOW_S}s frontend startup window"
    )
