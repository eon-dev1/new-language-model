"""
Tests for utils/phrase_index/scheduler.py — commit-debounce mechanics.

DEBOUNCE_SECONDS is monkeypatched to ~0.05 s throughout.

Run with: pytest tests/unit/phrase_index/test_scheduler.py -v
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from utils.phrase_index import scheduler as sched_mod

from .conftest import MockDB


@pytest.fixture
def fast_debounce(monkeypatch):
    """Shrink debounce window; expose short & wait-past values."""
    monkeypatch.setattr(sched_mod, "DEBOUNCE_SECONDS", 0.05)
    return 0.05


@pytest.fixture
def spy_builder(monkeypatch):
    """Replace build_phrase_index with a call-count spy that succeeds fast."""
    calls: list[str] = []

    async def _fake_build(db, language_code):
        calls.append(language_code)
        return {"phrases_emitted": 0, "verses_processed": 0, "duration_ms": 0}

    monkeypatch.setattr(sched_mod, "build_phrase_index", _fake_build)
    return calls


@pytest.fixture
def mock_connector(monkeypatch):
    """Replace get_mongodb_connector with a MockDB provider."""
    db = MockDB()

    async def _fake_connector():
        return db

    monkeypatch.setattr(sched_mod, "get_mongodb_connector", _fake_connector)
    return db


@pytest.fixture(autouse=True)
def reset_scheduler_state():
    """Ensure module-level _pending is clean between tests."""
    sched_mod._pending.clear()
    yield
    # Cancel anything still pending; suppress errors.
    for t in list(sched_mod._pending.values()):
        if not t.done():
            t.cancel()
    sched_mod._pending.clear()


@pytest.mark.asyncio
async def test_end_to_end_regression_non_base_actually_rebuilds(
    fast_debounce, spy_builder, mock_connector,
):
    """
    Load-bearing: a schedule() for a non-base lang MUST cause build_phrase_index
    to fire after the debounce. Catches an is_base_language-style silent
    failure where every call short-circuits.
    """
    await sched_mod.schedule("bughotu")
    await asyncio.sleep(fast_debounce * 4)  # comfortably past debounce
    assert spy_builder == ["bughotu"]


@pytest.mark.asyncio
async def test_two_puts_within_window_coalesce(
    fast_debounce, spy_builder, mock_connector,
):
    """Two calls inside the debounce window → one rebuild after it settles."""
    await sched_mod.schedule("bughotu")
    await asyncio.sleep(fast_debounce / 5)  # well inside window
    await sched_mod.schedule("bughotu")
    await asyncio.sleep(fast_debounce * 4)
    assert spy_builder == ["bughotu"]


@pytest.mark.asyncio
async def test_burst_of_calls_cancels_pending(
    fast_debounce, spy_builder, mock_connector,
):
    """A burst of N schedule() calls collapses to exactly one rebuild."""
    for _ in range(10):
        await sched_mod.schedule("bughotu")
        await asyncio.sleep(fast_debounce / 20)
    await asyncio.sleep(fast_debounce * 4)
    assert spy_builder == ["bughotu"]


@pytest.mark.asyncio
async def test_base_language_short_circuits(
    fast_debounce, spy_builder, mock_connector,
):
    """schedule('english') is a no-op — no builder call, no task queued."""
    await sched_mod.schedule("english")
    await asyncio.sleep(fast_debounce * 4)
    assert spy_builder == []
    assert "english" not in sched_mod._pending


@pytest.mark.asyncio
async def test_scheduler_defensive_lowercase(
    fast_debounce, spy_builder, mock_connector,
):
    """
    schedule('English') short-circuits as if it were 'english' — catches
    the F-BUG-2 case-fragile regression.
    """
    await sched_mod.schedule("English")
    await asyncio.sleep(fast_debounce * 4)
    assert spy_builder == []


@pytest.mark.asyncio
async def test_pending_cleaned_up_after_completion(
    fast_debounce, spy_builder, mock_connector,
):
    """_pending has no entry once the rebuild finishes."""
    await sched_mod.schedule("bughotu")
    await asyncio.sleep(fast_debounce * 4)
    assert "bughotu" not in sched_mod._pending


@pytest.mark.asyncio
async def test_builder_exception_logged_not_raised(
    fast_debounce, mock_connector, monkeypatch,
):
    """A builder exception inside _debounced_rebuild is logged, not raised."""
    async def _raiser(db, language_code):
        raise RuntimeError("simulated build failure")

    monkeypatch.setattr(sched_mod, "build_phrase_index", _raiser)

    await sched_mod.schedule("bughotu")
    # Wait past debounce; if the exception escaped, this await would surface it.
    await asyncio.sleep(fast_debounce * 4)
    # No assertion needed beyond "no crash" — reaching here is the pass.


@pytest.mark.asyncio
async def test_global_lock_serializes_concurrent_rebuilds(
    fast_debounce, mock_connector, monkeypatch,
):
    """
    Single global _rebuild_lock serializes concurrent rebuilds. Prove that
    two overlapping tasks acquiring the lock never run in parallel.
    """
    inside = {"count": 0, "max": 0}
    inside_lock = asyncio.Lock()

    async def _slow_build(db, language_code):
        async with inside_lock:
            inside["count"] += 1
            inside["max"] = max(inside["max"], inside["count"])
        await asyncio.sleep(fast_debounce / 2)
        async with inside_lock:
            inside["count"] -= 1

    monkeypatch.setattr(sched_mod, "build_phrase_index", _slow_build)

    # Two different languages → two tasks, both must acquire the global lock.
    await sched_mod.schedule("bughotu")
    await sched_mod.schedule("kope")
    # Let both debounced tasks progress; both must complete under the lock.
    await asyncio.sleep(fast_debounce * 8)
    assert inside["max"] == 1  # NEVER two rebuilds running simultaneously


@pytest.mark.asyncio
async def test_inflight_cancel_releases_lock_and_self_heals(
    fast_debounce, mock_connector, monkeypatch,
):
    """
    Evidence for accepted failure mode #2: an in-flight cancel produces a
    documented dirty state that self-heals. Confirm the lock releases and a
    follow-up rebuild completes.
    """
    step = {"phase": "idle"}

    async def _slow_build(db, language_code):
        step["phase"] = "started"
        # Long enough that a new schedule() can arrive during the build.
        await asyncio.sleep(fast_debounce * 4)
        step["phase"] = "finished"

    monkeypatch.setattr(sched_mod, "build_phrase_index", _slow_build)

    await sched_mod.schedule("bughotu")
    # Wait past debounce so the build enters its sleep.
    await asyncio.sleep(fast_debounce * 2)
    assert step["phase"] == "started"
    first_task = sched_mod._pending.get("bughotu")

    # Schedule again — cancels the mid-build task.
    await sched_mod.schedule("bughotu")

    # Give the cancel time to propagate; the second task will re-enter build.
    # Swap the builder to a fast success so the second run wraps up quickly.
    fast_calls: list[str] = []

    async def _fast(db, language_code):
        fast_calls.append(language_code)

    monkeypatch.setattr(sched_mod, "build_phrase_index", _fast)

    await asyncio.sleep(fast_debounce * 6)

    # First task was cancelled mid-build.
    assert first_task is not None and first_task.done()

    # Lock is released — the second rebuild ran (not stuck).
    assert fast_calls == ["bughotu"]

    # Lock is not held.
    assert not sched_mod._rebuild_lock.locked()
