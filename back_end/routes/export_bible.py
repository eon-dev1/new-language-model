# export_bible.py
"""
USFM Bible export endpoint.

Exports translation data for a selected language to USFM files,
one file per book, written directly to a user-specified directory.
"""

import os
import re
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from db_connector.connection import MongoDBConnector
from constants import Collection
from .dependencies import get_db, api_error
from utils.usfm_parser.usfm_book_codes import USFM_BOOK_DATA

logger = logging.getLogger(__name__)
router = APIRouter()

# Build reverse map: db_book_code → (usfm_code, display_name, canonical_order)
_BOOK_EXPORT_MAP: dict[str, tuple[str, str, int]] = {
    db_code: (usfm_code, display_name, order + 1)
    for order, (usfm_code, (db_code, display_name)) in enumerate(USFM_BOOK_DATA.items())
}


def _build_usfm_content(
    book_code: str,
    verses: list,
    book_name: str,
    lang_name: str,
) -> list[str]:
    """
    Build USFM content lines for a single book.

    Returns list[str] — caller joins with '\\n'.join(lines) before writing.
    Verses with None/empty translated_text are skipped.
    \\c/\\p markers are emitted lazily — only before the first non-empty verse
    in each chapter, preventing orphaned chapter markers.
    """
    entry = _BOOK_EXPORT_MAP.get(book_code)
    if entry is None:
        return []

    usfm_code, display_name, _ = entry
    resolved_name = book_name if book_name else display_name

    lines: list[str] = [
        f"\\id {usfm_code} {lang_name}",
        "\\ide UTF-8",
        f"\\h {resolved_name}",
        f"\\toc1 {resolved_name}",
        f"\\toc2 {resolved_name}",
        f"\\toc3 {usfm_code}",
        f"\\mt1 {resolved_name}",
    ]

    current_chapter = None
    for doc in verses:
        text = doc.get("translated_text")
        if not text:
            continue
        if doc["chapter"] != current_chapter:
            current_chapter = doc["chapter"]
            lines.append(f"\\c {current_chapter}")
            lines.append("\\p")
        lines.append(f"\\v {doc['verse']} {text}")

    return lines


class ExportRequest(BaseModel):
    language_code: str
    output_dir: str


class ExportResponse(BaseModel):
    success: bool
    files_written: int
    message: str


@router.post("/export-usfm", response_model=ExportResponse)
async def export_usfm(
    request: ExportRequest,
    db: MongoDBConnector = Depends(get_db)
):
    """
    Export all books for a language to USFM files in the specified directory.

    Request: { language_code: str, output_dir: str }
    Response: { success: bool, files_written: int, message: str }
    """
    try:
        # 1. Validate language exists and is not a base language
        language_doc = await db.get_collection(Collection.LANGUAGES).find_one(
            {"language_code": request.language_code}
        )
        if not language_doc:
            raise HTTPException(
                status_code=400,
                detail=f"Language '{request.language_code}' not found"
            )
        if language_doc.get("is_base_language"):
            raise HTTPException(status_code=400, detail="Cannot export base language")

        lang_name = language_doc.get("language_name", request.language_code)

        # 2. Sanitize language_code for filename use (prevent path traversal)
        safe_lang = re.sub(r'[^a-z0-9_]', '_', request.language_code.lower())

        # 3. Validate output_dir
        real_path = os.path.realpath(request.output_dir)
        if not os.path.isdir(real_path):
            raise HTTPException(
                status_code=400,
                detail="output_dir does not exist or is not a directory"
            )
        if not os.access(real_path, os.W_OK):
            raise HTTPException(status_code=400, detail="output_dir is not writable")

        # 4. Single query for all verses — no N+1 per-book loop
        cursor = db.get_collection(Collection.BIBLE_TEXTS).find(
            {"language_code": request.language_code},
            projection={"book_code": 1, "chapter": 1, "verse": 1, "translated_text": 1, "_id": 0},
            sort=[("book_code", 1), ("chapter", 1), ("verse", 1)],
        )

        books: dict[str, list] = {}
        async for doc in cursor:
            books.setdefault(doc["book_code"], []).append(doc)

        # 5. Look up translated book names ($in query, single round-trip)
        book_names: dict[str, str] = {}
        if books:
            name_cursor = db.get_collection(Collection.BIBLE_BOOKS).find(
                {
                    "language_code": request.language_code,
                    "book_code": {"$in": list(books.keys())},
                },
                projection={"book_code": 1, "book_name": 1, "_id": 0},
            )
            async for doc in name_cursor:
                if doc.get("book_name"):
                    book_names[doc["book_code"]] = doc["book_name"]

        # 6. Write one USFM file per book
        files_written = 0
        for book_code, verses in books.items():
            entry = _BOOK_EXPORT_MAP.get(book_code)
            if entry is None:
                logger.warning(f"Skipping {book_code}: not in _BOOK_EXPORT_MAP")
                continue

            usfm_code, display_name, order = entry
            book_name = book_names.get(book_code) or display_name

            lines = _build_usfm_content(book_code, verses, book_name, lang_name)

            # 6c. Skip books with no translated verses
            if not any(line.startswith("\\v ") for line in lines):
                logger.warning(f"Skipping {book_code}: no translated verses")
                continue

            filename = f"{order:03d}-{usfm_code}{safe_lang}.usfm"
            filepath = os.path.join(real_path, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            files_written += 1

        return ExportResponse(
            success=True,
            files_written=files_written,
            message=f"Exported {files_written} book(s) to {real_path}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Export USFM for {request.language_code}", e)
