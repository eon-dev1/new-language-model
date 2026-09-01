# Bible Import Documentation

This document covers importing Bible data into the NLM platform.

## Overview

The NLM backend supports importing Bible text via **USFM** (Unified Standard Format Markers), the standard Bible text format.

Import:
- Supports upsert behavior (safe to re-import)
- Creates/updates the language document automatically
- Tracks import statistics (inserted vs updated)

---

## USFM Import

### Endpoint

```
POST /api/import-bible
```

### Request Schema

```json
{
  "language_code": "bughotu",
  "language_name": "Bughotu",
  "usfm_directory": "/path/to/usfm/files"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `language_code` | string | Yes | Unique identifier (e.g., "bughotu", "kope") |
| `language_name` | string | Yes | Display name (e.g., "Bughotu", "Kope") |
| `usfm_directory` | string | Yes | Absolute path to directory containing USFM files |
| `human_verified` | boolean | No | Mark all imported verses as pre-verified (default: `false`) |

### Response Schema

```json
{
  "success": true,
  "language_code": "bughotu",
  "message": "Imported 7957 verses from 27 books",
  "verses_imported": 7957,
  "verses_updated": 0,
  "books_processed": 27,
  "is_reimport": false
}
```

### Supported File Extensions

The importer auto-detects USFM files by trying these patterns in order:
1. `*.usfm`
2. `*.SFM`
3. `*.sfm`
4. `*.USFM`

Falls back to `*.usfm` if no files match.

### Directory Structure

```
usfm_directory/
├── 01-GENbook.usfm    # Genesis
├── 02-EXObook.usfm    # Exodus
├── ...
├── 40-MATbook.usfm    # Matthew
├── ...
└── 66-REVbook.usfm    # Revelation
```

File naming is flexible - the parser reads USFM markers inside the file to determine book identity.

### USFM File Format

Standard USFM markers are supported:

```usfm
\id GEN - Genesis
\h Genesis
\c 1
\v 1 In the beginning God created the heavens and the earth.
\v 2 The earth was formless and empty...
\c 2
\v 1 The heavens and the earth were completed...
```

Key markers:
- `\id` - Book identification
- `\h` - Header/book name
- `\c` - Chapter number
- `\v` - Verse number and text
- `\f ... \f*` - Footnotes (captured but stored separately)

### CLI Usage

```bash
cd back_end

# Import English base language
python -m utils.usfm_parser.usfm_importer \
    ../data/bibles/eng-web_usfm/ \
    english

# Import a target language
python -m utils.usfm_parser.usfm_importer \
    ../data/bibles/bughotu_usfm/ \
    bughotu
```

---

## Import Behavior

### Verification Status at Import

The `human_verified` flag controls whether imported verses are marked as already reviewed.

| Value | Meaning |
|-------|---------|
| `false` (default) | Verses require in-app verification before use |
| `true` | Verses are pre-approved and skip the verification workflow |

**When to use `human_verified: true`**: The translation has already been reviewed externally (e.g., by a translation committee) and does not need re-verification inside the NLM workflow.

**Re-import behavior**: Re-importing always overwrites `human_verified` to the caller-supplied value using `$set`. This means:
- Re-importing with `human_verified: true` marks all verses verified, even if they were unverified before.
- Re-importing with `human_verified: false` (default) clears verification on any previously-verified verses.

This is intentional — it allows correcting a mis-classified import. Be aware that re-importing with the default `false` will reset any in-app verification work done since the last import.

**Mixed batches (two-folder import)**: To import some verses as pre-verified and others as unverified, perform two sequential POST requests pointing to different folders — one with `human_verified: true` and one with `human_verified: false`. The folders must contain *different* verses: if both contain the same verse, the second request overwrites the first.

### Upsert Logic

Both importers use MongoDB upsert operations:
- **New verses**: Inserted with `created_at` timestamp
- **Existing verses**: Updated with new text, `updated_at` timestamp preserved
- **Unique key**: `(language_code, book_code, chapter, verse)`

This makes re-imports safe and idempotent.

### Language Document Creation

If the language doesn't exist, the import automatically creates a language document:

```javascript
{
  "language_code": "bughotu",
  "language_name": "Bughotu",
  "is_base_language": false,
  "status": "active",
  "translation_stats": {
    "books_started": 27,
    "books_completed": 0,
    "verses_translated": 7957,
    "verses_verified": 0,
    "last_updated": ISODate("...")
  }
}
```

If the language exists, the import updates the translation stats.

### Data Storage

Imported verses are stored in the `bible_texts` collection:

```javascript
{
  "language_code": "bughotu",
  "book_code": "matthew",
  "chapter": 1,
  "verse": 1,
  "translated_text": "...",     // The imported text
  "human_verified": false,      // Defaults to false
  "created_at": ISODate("...")
}
```

For English imports, text goes to `english_text` instead of `translated_text`. The `human_verified` field is always stored (defaults to `false`) regardless of language.

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Directory not found" | Invalid path | Check the path exists |
| "No USFM files found" | Wrong directory or extension | Verify file extensions |

### Partial Import Handling

If an import fails partway through:
- Already-imported verses are retained
- Re-run the import to complete (upsert handles duplicates)
- Check the `errors` array in the response for details

---

## Best Practices

1. **Use absolute paths** for directory arguments
2. **Check response statistics** to confirm expected verse counts
3. **Re-import is safe** - run again if something seems wrong
