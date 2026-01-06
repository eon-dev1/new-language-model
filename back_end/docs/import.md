# Bible Import Documentation

This document covers importing Bible data into the NLM platform from various file formats.

## Overview

The NLM backend supports two import formats:
- **USFM** (Unified Standard Format Markers) - Standard Bible text format
- **HTML** - Custom HTML format used by some translation projects

Both methods:
- Support upsert behavior (safe to re-import)
- Create/update the language document automatically
- Track import statistics (inserted vs updated)

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
  "usfm_directory": "/path/to/usfm/files",
  "translation_type": "human"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `language_code` | string | Yes | - | Unique identifier (e.g., "bughotu", "kope") |
| `language_name` | string | Yes | - | Display name (e.g., "Bughotu", "Kope") |
| `usfm_directory` | string | Yes | - | Absolute path to directory containing USFM files |
| `translation_type` | string | No | "human" | Either "human" or "ai" |

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

# Import English NET Bible
python -m utils.usfm_parser.usfm_importer \
    ../data/bibles/engnet_usfm/ \
    english \
    human

# Import a target language
python -m utils.usfm_parser.usfm_importer \
    ../data/bibles/bughotu_usfm/ \
    bughotu \
    human
```

---

## HTML Import

### Endpoint

```
POST /api/import-html-bible
```

### Request Schema

```json
{
  "language_code": "bughotu",
  "language_name": "Bughotu",
  "html_directory": "/path/to/html/files",
  "translation_type": "human"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `language_code` | string | Yes | - | Unique identifier |
| `language_name` | string | Yes | - | Display name |
| `html_directory` | string | Yes | - | Absolute path to directory containing HTML files |
| `translation_type` | string | No | "human" | Either "human" or "ai" |

### Response Schema

```json
{
  "success": true,
  "language_code": "bughotu",
  "message": "Imported 7957 verses from 260 chapters",
  "verses_imported": 7957,
  "verses_updated": 0,
  "chapters_processed": 260,
  "is_reimport": false
}
```

### Required File Naming Pattern

HTML files **must** follow this naming convention:

```
{BOOK_CODE}{CHAPTER}.htm
```

Where:
- `{BOOK_CODE}` is a 3-character USFM book code (case-insensitive)
- `{CHAPTER}` is a 2-digit chapter number (01-99)
- Extension must be `.htm`

**Regex pattern**: `^([A-Z0-9]{3})(\d{2})\.htm$`

### Examples

| Filename | Book | Chapter |
|----------|------|---------|
| `GEN01.htm` | Genesis | 1 |
| `GEN50.htm` | Genesis | 50 |
| `MAT01.htm` | Matthew | 1 |
| `JHN03.htm` | John | 3 |
| `1CO13.htm` | 1 Corinthians | 13 |
| `REV22.htm` | Revelation | 22 |

### Directory Structure

```
html_directory/
├── GEN00.htm    # Introduction (SKIPPED)
├── GEN01.htm    # Genesis chapter 1
├── GEN02.htm    # Genesis chapter 2
├── ...
├── GEN50.htm    # Genesis chapter 50
├── EXO00.htm    # Introduction (SKIPPED)
├── EXO01.htm    # Exodus chapter 1
├── ...
└── REV22.htm    # Revelation chapter 22
```

**Note**: Chapter 00 files (introductions) are automatically skipped.

### Standard USFM Book Codes

| Code | Book | Code | Book |
|------|------|------|------|
| GEN | Genesis | MAT | Matthew |
| EXO | Exodus | MRK | Mark |
| LEV | Leviticus | LUK | Luke |
| NUM | Numbers | JHN | John |
| DEU | Deuteronomy | ACT | Acts |
| JOS | Joshua | ROM | Romans |
| JDG | Judges | 1CO | 1 Corinthians |
| RUT | Ruth | 2CO | 2 Corinthians |
| 1SA | 1 Samuel | GAL | Galatians |
| 2SA | 2 Samuel | EPH | Ephesians |
| 1KI | 1 Kings | PHP | Philippians |
| 2KI | 2 Kings | COL | Colossians |
| 1CH | 1 Chronicles | 1TH | 1 Thessalonians |
| 2CH | 2 Chronicles | 2TH | 2 Thessalonians |
| EZR | Ezra | 1TI | 1 Timothy |
| NEH | Nehemiah | 2TI | 2 Timothy |
| EST | Esther | TIT | Titus |
| JOB | Job | PHM | Philemon |
| PSA | Psalms | HEB | Hebrews |
| PRO | Proverbs | JAS | James |
| ECC | Ecclesiastes | 1PE | 1 Peter |
| SNG | Song of Solomon | 2PE | 2 Peter |
| ISA | Isaiah | 1JN | 1 John |
| JER | Jeremiah | 2JN | 2 John |
| LAM | Lamentations | 3JN | 3 John |
| EZK | Ezekiel | JUD | Jude |
| DAN | Daniel | REV | Revelation |
| HOS | Hosea | | |
| JOL | Joel | | |
| AMO | Amos | | |
| OBA | Obadiah | | |
| JON | Jonah | | |
| MIC | Micah | | |
| NAM | Nahum | | |
| HAB | Habakkuk | | |
| ZEP | Zephaniah | | |
| HAG | Haggai | | |
| ZEC | Zechariah | | |
| MAL | Malachi | | |

### CLI Usage

```bash
cd back_end

# Import HTML Bible
python -m utils.html_parser.html_importer \
    ../data/bibles/bgt_html/ \
    bughotu \
    human
```

---

## Import Behavior

### Upsert Logic

Both importers use MongoDB upsert operations:
- **New verses**: Inserted with `created_at` timestamp
- **Existing verses**: Updated with new text, `updated_at` timestamp preserved
- **Unique key**: `(language_code, book_code, chapter, verse, translation_type)`

This makes re-imports safe and idempotent.

### Language Document Creation

If the language doesn't exist, the import automatically creates a language document:

```javascript
{
  "language_code": "bughotu",
  "language_name": "Bughotu",
  "is_base_language": false,
  "status": "active",
  "translation_levels": {
    "human": {
      "books_started": 27,
      "verses_translated": 7957,
      "last_updated": ISODate("...")
    },
    "ai": { /* zeroed */ }
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
  "translation_type": "human",
  "english_text": "",           // Empty for non-English
  "translated_text": "...",     // The imported text
  "human_verified": false,      // Defaults to false
  "created_at": ISODate("...")
}
```

For English imports, text goes to `english_text` instead.

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Directory not found" | Invalid path | Check the path exists |
| "No USFM files found" | Wrong directory or extension | Verify file extensions |
| "No valid HTML chapter files found" | Files don't match naming pattern | Rename files to `{CODE}{NN}.htm` |

### Partial Import Handling

If an import fails partway through:
- Already-imported verses are retained
- Re-run the import to complete (upsert handles duplicates)
- Check the `errors` array in the response for details

---

## Best Practices

1. **Use absolute paths** for directory arguments
2. **Verify file naming** before HTML imports
3. **Check response statistics** to confirm expected verse counts
4. **Re-import is safe** - run again if something seems wrong
5. **Translation type** defaults to "human" - specify "ai" for AI-generated content
