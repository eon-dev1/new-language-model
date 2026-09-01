"""
Debounced rebuild scheduler for phrase_index.

Coalesces bursts of PUT /verses / PATCH /verify calls into a single rebuild
per language after the debounce window settles.

Discipline:
- Single global _rebuild_lock (not per-language) — matches word_index's
  discipline in bible_reader.py; a translator works one language at a time
  and language collisions are rare.
- English short-circuits: English text is treated as immutable in normal
  operation; bulk-path rebuilds are triggered by load_base_language.py.
- Fire-and-forget errors are logged, never crash the event loop.
"""

import asyncio
import logging

from db_connector.connection import get_mongodb_connector
from routes.load_base_language import ENGLISH_LANGUAGE_CODE
from utils.phrase_index.builder import build_phrase_index

logger = logging.getLogger(__name__)

# Debounce window — module-level so tests can monkeypatch to ~0.05 s.
DEBOUNCE_SECONDS = 60

# Pending debounced tasks, keyed by language_code.
_pending: dict[str, asyncio.Task] = {}

# Single global lock — mirrors bible_reader.py's _rebuild_lock for word_index.
# Serializes an in-app debounced rebuild against a concurrent CLI or against
# another language's rebuild. Two consecutive rebuilds in the worst case
# (verify burst during in-flight build) is acceptable.
_rebuild_lock = asyncio.Lock()


async def schedule(language_code: str) -> None:
    """
    Schedule a debounced phrase_index rebuild for the given language.

    Cancels any pending task for this language and starts a fresh timer.
    Safe to call on every PUT/PATCH; the actual rebuild fires
    DEBOUNCE_SECONDS after the last call for that language.

    English is short-circuited — no rebuild is scheduled. The English text is
    immutable in normal operation; bulk reloads trigger the rebuild via
    routes/load_base_language.py directly.
    """
    # Defensive lowercase — current callers already lowercase the path param,
    # but a future caller that forgets would silently bypass the English
    # short-circuit and rebuild English on every save. Mirrors
    # word_index/builder.py's own defensive lowercase.
    language_code = language_code.lower()

    # Hard-coded base-language short-circuit. Uses the existing constant
    # rather than a DB is_base_language lookup per commit — the DB lookup
    # adds latency and introduces a footgun where a misused sync helper
    # silently truthy-returns on every language and disables all rebuilds.
    if language_code == ENGLISH_LANGUAGE_CODE:
        return

    # Cancel any pending task for this language — new activity resets the
    # window. The cancelled task raises CancelledError inside its sleep()
    # and unwinds cleanly.
    existing = _pending.get(language_code)
    if existing is not None and not existing.done():
        existing.cancel()

    task = asyncio.create_task(_debounced_rebuild(language_code))
    _pending[language_code] = task

    def _cleanup(t: asyncio.Task) -> None:
        # Identity check — a bare _pending.pop(language_code) would pop a
        # *replacement* task scheduled between the old task's cancellation
        # and this callback's turn, causing concurrent rebuilds and silently
        # defeating debouncing.
        if _pending.get(language_code) is t:
            _pending.pop(language_code, None)

    task.add_done_callback(_cleanup)


async def _debounced_rebuild(language_code: str) -> None:
    """
    Sleep for the debounce window, then rebuild under the global lock.

    Any exception is logged and swallowed — a fire-and-forget task must not
    crash the event loop.
    """
    try:
        await asyncio.sleep(DEBOUNCE_SECONDS)
        # Global connector: the request-scoped db from FastAPI's Depends is
        # closed when the request ends, so we must not capture it for a task
        # that runs DEBOUNCE_SECONDS later.
        db = await get_mongodb_connector()
        async with _rebuild_lock:
            await build_phrase_index(db, language_code)
    except asyncio.CancelledError:
        # Debounce reset — a newer schedule() cancelled us. Not an error.
        raise
    except Exception as e:
        logger.warning(
            f"phrase_index debounced rebuild failed for '{language_code}' "
            f"(non-fatal): {e}"
        )
