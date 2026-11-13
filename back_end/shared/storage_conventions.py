# shared/storage_conventions.py
"""
Canonical stored forms for values whose comparison rules SQL cannot enforce.

Not wired into the database layer yet. The word-index tokenizer is the only
importer today.

SQLite's ``lower()`` is ASCII-only and SQLite has no Unicode normalization, so
case-insensitive and normalization-insensitive behavior must be produced in
Python before a value is written or compared. Every writer and every lookup
must go through these functions, so that two code paths never produce
different stored forms for the same input.
"""

import unicodedata
from datetime import datetime, timezone


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def normalize_word(word: str) -> str:
    """
    Return the stored form of a dictionary word: stripped, lowercased, NFC.

    The result is part of the ``entries`` primary key, so canonically
    equivalent or case-variant spellings (``Tok``/``tok``, ``e`` + combining
    acute vs. precomposed ``é``) must collapse to one key. The word-index
    tokenizer lowercases each token with this same function, so a dictionary
    word equals the token for that word in verse text. That equality holds
    only for words the tokenizer emits as a single token: the tokenizer also
    splits on dashes and slashes and strips boundary punctuation, which this
    function does not, so an entry like ``-tok`` or ``a b`` never matches a
    token.

    ``lower()`` rather than ``casefold()`` because the stored word is shown
    back to the translator: ``casefold()`` would turn ``Straße`` into
    ``strasse`` and a word-final ``ς`` into ``σ``.

    NFC is applied after ``lower()``, not before, because lowercasing can
    produce a non-NFC string (``T`` + combining diaeresis lowercases to ``t`` +
    combining diaeresis, which NFC composes to ``ẗ``). Normalizing last makes
    the function idempotent, so a stored word that is read back and
    re-normalized (pasted into a lookup, or re-submitted by an upsert) maps to
    the same key. NFC after ``lower()`` also covers decomposed input, so no
    NFC is needed before it.

    Internal whitespace is kept as typed. Blank or whitespace-only input
    returns ``""``; callers must reject that rather than store an empty word.
    """
    return _nfc(word.strip().lower())


def fold_for_search(text: str) -> str:
    """
    Return the search-only folded form of text, for stored shadow columns and
    for search terms alike.

    ``casefold()`` rather than ``lower()`` because the folded value is never
    displayed and both sides of a match pass through this function. Its
    mappings are context-free: ``ΑΣ`` and ``ας`` fold to the same string,
    while ``lower()`` would give a word-final ``ς`` that a search for ``σ``
    misses. A consequence: ``ß`` folds to ``ss``, so searching ``s`` matches
    ``ß``.

    NFC is applied both before and after ``casefold()``. Before, because
    ``casefold()`` maps some decomposed sequences differently from their
    precomposed equivalents (Greek letters with iota subscript plus another
    mark), so NFD and NFC input would otherwise fold apart. After, because
    ``casefold()`` can itself decompose (``ΐ`` becomes ``ι`` + two combining
    marks), which would make a precomposed search term miss text that folds
    to the composed form; it also makes the function idempotent.

    No ``strip()``: a search term's leading or trailing space is intentional.
    """
    return _nfc(_nfc(text).casefold())


def to_utc_iso(moment: datetime) -> str:
    """
    Format an aware datetime as ``YYYY-MM-DDTHH:MM:SS.ffffff+00:00``.

    Timestamps are stored as text and sorted as strings, so every stored
    timestamp must have one shape: always UTC, always the ``+00:00`` suffix
    (never ``Z``), always six fractional digits. Mixing suffixes or naive
    strings in one column breaks string order. A bare ``isoformat()`` omits the
    fraction when microseconds are 0, so fixed width also needs
    ``timespec="microseconds"``; fixed width keeps exact-equality and
    string-bound comparisons reliable.

    Raises ``ValueError`` for a naive datetime: it has no defined instant, and
    ``astimezone`` would silently interpret it as local time. Values known to
    be UTC but read back naive (pymongo's default) must have
    ``tzinfo=timezone.utc`` attached by the caller. "Naive" uses Python's
    definition, ``utcoffset() is None``, which also covers a tzinfo that
    reports no offset.
    """
    if moment.utcoffset() is None:
        raise ValueError(f"naive datetime has no defined instant: {moment!r}")
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds")


def utc_now_iso() -> str:
    """Return the current time in the stored timestamp form (see ``to_utc_iso``)."""
    return to_utc_iso(datetime.now(timezone.utc))
