# MongoDB Schema Documentation

> **IMPORTANT: Single Source of Truth**
>
> The authoritative schema definition is in:
> ```
> utils/schema_enforcer/schema_definition.py
> ```
> This documentation should match that file. If there are discrepancies,
> `schema_definition.py` is correct. Run `python -m utils.schema_enforcer --dry-run`
> to verify schema compliance.

## Database Overview

**Database Name**: `nlm_db`

The NLM platform uses MongoDB as its primary database, storing Bible translations, dictionaries, and grammar systems for multiple languages.

## Collections

| Collection | Purpose | Status |
|------------|---------|--------|
| `languages` | Language metadata and translation progress | Active |
| `bible_books` | Language-specific book metadata with embedded chapters | Active |
| `bible_texts` | Individual verse storage (indexed) | Active |
| `base_structure_bible` | Canonical Bible structure (31,102 verses) | Active (generators only) |
| `dictionaries` | Word entries with definitions | Active (empty) |
| `grammar_systems` | Grammar rules organized by category | Active (empty) |
| `word_index` | Word frequency and dictionary gap tracking | Active |
| `correction_log` | Log of text corrections | Active |
| `language_notes` | Notes attached to languages | Active |
| `chat_conversations` | AI chat conversation history | Active |

### Collection Purposes

| Collection | Used By | Purpose |
|------------|---------|---------|
| `bible_books` | Routes, Frontend | Language-specific book metadata for display |
| `base_structure_bible` | Generator scripts | Canonical structure for seeding new databases |
| `bible_texts` | Routes, Frontend | Individual verse content for reading/editing |

---

## Collection: languages

Stores metadata for each language in the system, including translation progress tracking.

> **See**: `utils/schema_enforcer/schema_definition.py` for authoritative field definitions

### Indexes

```javascript
// Unique language code lookup
{ "language_code": 1 }
// unique: true, name: "language_code_1"
```

### Schema

```javascript
{
  "_id": ObjectId,
  "language_name": String,         // Display name (e.g., "Kope")
  "language_code": String,         // Normalized code (e.g., "kope")
  "is_base_language": Boolean,     // true for English only
  "created_at": ISODate,
  "updated_at": ISODate,           // Optional, set on updates
  "status": String,                // "active" | "inactive"
  "bible_books_count": Number,     // Always 66
  "total_verses": Number,          // 31,102
  "translation_stats": {
    "books_started": Number,
    "books_completed": Number,
    "verses_translated": Number,
    "verses_verified": Number,     // Verses with human_verified: true
    "last_updated": ISODate | null
  },
  "metadata": {
    "creator": String,             // "nlm_fastapi_endpoint"
    "version": String,             // "1.0"
    "description": String
  }
}
```

### Example Document

```javascript
{
  "_id": ObjectId("65a1b2c3d4e5f6a7b8c9d0e1"),
  "language_name": "Kope",
  "language_code": "kope",
  "is_base_language": false,
  "created_at": ISODate("2024-01-15T10:30:00.000Z"),
  "status": "active",
  "bible_books_count": 66,
  "total_verses": 31102,
  "translation_stats": {
    "books_started": 0,
    "books_completed": 0,
    "verses_translated": 0,
    "verses_verified": 0,
    "last_updated": null
  },
  "metadata": {
    "creator": "nlm_fastapi_endpoint",
    "version": "1.0",
    "description": "Biblical translation project for Kope"
  }
}
```

---

## Collection: base_structure_bible

Stores the canonical Bible structure with 31,102 verses. This is the reference structure
for all languages - actual translations are stored in `bible_texts`.

> **See**: `utils/schema_enforcer/schema_definition.py` for authoritative field definitions

### Schema

```javascript
{
  "_id": ObjectId,
  "book": String,           // e.g., "genesis", "1_chronicles" (lowercase with underscores)
  "chapter": Number,        // Chapter number
  "verse": Number,          // Verse number
  "book_order": Number,     // Canonical order 1-66
  "testament": String,      // "old" | "new"
  "language_code": String,  // Always "base"
  "is_base_structure": Boolean  // Always true
}
```

### Indexes

```javascript
// Unique verse lookup
{ "book": 1, "chapter": 1, "verse": 1 }  // unique: true, name: "verse_structure"

// Canonical book ordering
{ "book_order": 1 }  // name: "canonical_order"
```

### Book Count Reference

| Testament | Books | Range | book_order |
|-----------|-------|-------|------------|
| Old Testament | 39 | Genesis - Malachi | 1-39 |
| New Testament | 27 | Matthew - Revelation | 40-66 |
| **Total** | **66** | | |

---

## Collection: bible_books

Stores language-specific book metadata with embedded chapter information. One document per
(language, book) combination. This is the primary collection for book lists shown in the frontend.

> **See**: `utils/schema_enforcer/schema_definition.py` for authoritative field definitions

### Indexes

```javascript
// Unique book lookup
{ "language_code": 1, "book_code": 1 }
// unique: true, name: "book_lookup"

// Language filtering
{ "language_code": 1 }
// name: "language_type_filter"
```

### Schema

```javascript
{
  "_id": ObjectId,
  "language_code": String,        // e.g., "kope", "english"
  "language_name": String,        // e.g., "Kope", "English"
  "book_name": String,            // Localized name (e.g., "Genesis", "בראשית")
  "book_code": String,            // e.g., "genesis", "1_chronicles"
  "total_chapters": Number,       // e.g., 50 for Genesis
  "total_verses": Number,         // e.g., 1533 for Genesis
  "chapters": [                   // Embedded chapter data
    { "chapter_number": Number, "verse_count": Number, "verses": [Number] }
  ],
  "created_at": ISODate,
  "updated_at": ISODate,          // Optional
  "translation_status": String,   // "not_started" | "imported" | "in_progress" | "complete" | "draft"
  "metadata": {
    "testament": String,          // "old" | "new"
    "canonical_order": Number,    // 1-66
    "ai_model": String            // Optional
  }
}
```

### Example Document

```javascript
{
  "_id": ObjectId("65a1b2c3d4e5f6a7b8c9d0e2"),
  "language_code": "kope",
  "language_name": "Kope",
  "book_name": "Genesis",
  "book_code": "genesis",
  "total_chapters": 50,
  "total_verses": 1533,
  "chapters": [
    { "chapter_number": 1, "verse_count": 31, "verses": [1, 2, ..., 31] },
    { "chapter_number": 2, "verse_count": 25, "verses": [1, 2, ..., 25] },
    // ... all 50 chapters
  ],
  "created_at": ISODate("2024-01-15T10:30:00.000Z"),
  "translation_status": "in_progress",
  "metadata": {
    "testament": "old",
    "canonical_order": 1
  }
}
```

---

## Collection: bible_texts

Stores individual verses for efficient querying and search. This is the primary collection
for verse content across all languages. One document per (language, book, chapter, verse).

> **See**: `utils/schema_enforcer/schema_definition.py` for authoritative field definitions

### Schema

```javascript
{
  "_id": ObjectId,
  "language_code": String,          // e.g., "english", "kope"
  "book_code": String,              // e.g., "genesis", "1_chronicles" (lowercase + underscores)
  "chapter": Number,
  "verse": Number,
  "created_at": ISODate,

  // English verses only:
  "english_text": String,           // The source text

  // Non-English verses only:
  "translated_text": String,        // The translation
  "human_verified": Boolean         // Verification status
}
```

> **Note**: Field presence varies by language. English verses have `english_text`.
> Non-English verses have `translated_text` and `human_verified`.

### Indexes

```javascript
// Unique compound index for verse lookup
{ "language_code": 1, "book_code": 1, "chapter": 1, "verse": 1 }
// unique: true, name: "verse_lookup"

// Language filtering
{ "language_code": 1 }
// name: "language_type_filter"

// Book filtering
{ "book_code": 1 }
// name: "book_type_filter"
```

### Example Query Patterns

```javascript
// Get specific verse
db.bible_texts.findOne({
  language_code: "kope",
  book_code: "genesis",
  chapter: 1,
  verse: 1
})

// Get all verses in a chapter
db.bible_texts.find({
  language_code: "kope",
  book_code: "genesis",
  chapter: 1
}).sort({ verse: 1 })

// Count translated verses
db.bible_texts.countDocuments({
  language_code: "kope",
  translated_text: { $ne: "" }
})
```

---

## Collection: dictionaries

Stores dictionary entries for each language. One document per language with entries embedded.

> **See**: `utils/schema_enforcer/schema_definition.py` for authoritative field definitions

### Indexes

```javascript
// Unique lookup by language
{ "language_code": 1 }
// unique: true, name: "dict_lookup"
```

### Schema

```javascript
{
  "_id": ObjectId,
  "language_code": String,
  "language_name": String,
  "dictionary_name": String,        // e.g., "Kope Dictionary"
  "entries": [
    {
      "word": String,               // Required
      "definition": String,         // Required
      "part_of_speech": String,     // Optional
      "etymology": String,          // Optional
      "examples": [String],         // Optional
      "human_verified": Boolean,    // Optional - verification status
      "created_at": ISODate,        // Optional
      "updated_at": ISODate         // Optional
    }
  ],
  "entry_count": Number,
  "created_at": ISODate,
  "categories": [String],           // Part of speech categories
  "metadata": {
    "description": String,
    "version": String,
    "status": String                // "active"
  }
}
```

### Default Categories

```javascript
[
  "noun",
  "verb",
  "adjective",
  "adverb",
  "preposition",
  "conjunction",
  "interjection",
  "pronoun",
  "article",
  "other"
]
```

### Example Document

```javascript
{
  "_id": ObjectId("65a1b2c3d4e5f6a7b8c9d0e3"),
  "language_code": "kope",
  "language_name": "Kope",
  "dictionary_name": "Kope Dictionary",
  "entries": [],
  "entry_count": 0,
  "created_at": ISODate("2024-01-15T10:30:00.000Z"),
  "categories": [
    "noun", "verb", "adjective", "adverb", "preposition",
    "conjunction", "interjection", "pronoun", "article", "other"
  ],
  "metadata": {
    "description": "Dictionary for Kope translation work",
    "version": "1.0",
    "status": "active"
  }
}
```

---

## Collection: grammar_systems

Stores comprehensive grammar frameworks organized by linguistic categories.
One document per language.

> **See**: `utils/schema_enforcer/schema_definition.py` for authoritative field definitions

### Indexes

```javascript
// Unique lookup by language
{ "language_code": 1 }
// unique: true, name: "grammar_lookup"
```

### Schema

```javascript
{
  "_id": ObjectId,
  "language_code": String,
  "language_name": String,
  "grammar_system_name": String,
  "created_at": ISODate,
  "categories": {
    "phonology": {
      "description": String,
      "subcategories": [String | Object],  // rich format: {name, content, examples, human_verified}
      "notes": [String | Object],          // rich format: {text, human_verified}
      "examples": [String | Object],       // rich format: {source_text, english, analysis, human_verified}
      "ai_confidence": Number | null,
      "human_verified": Boolean,
      "updated_at": ISODate | null
    },
    "morphology": {/* same structure */},
    "syntax": {/* same structure */},
    "semantics": {/* same structure */},
    "discourse": {/* same structure */}
  },
  "metadata": {
    "version": String,
    "status": String,
    "description": String
  }
}
```

### Grammar Categories Detail

| Category | Description | Subcategories |
|----------|-------------|---------------|
| phonology | Sound system and pronunciation | consonants, vowels, tone, stress, phonotactics |
| morphology | Word structure and formation | noun_morphology, verb_morphology, adjective_morphology, derivation |
| syntax | Sentence structure | word_order, clause_structure, phrase_structure, agreement |
| semantics | Meaning and interpretation | lexical_semantics, compositional_semantics, pragmatics |
| discourse | Text-level organization | paragraph_structure, narrative_patterns, discourse_markers |

### Example Document

```javascript
{
  "_id": ObjectId("65a1b2c3d4e5f6a7b8c9d0e4"),
  "language_code": "kope",
  "language_name": "Kope",
  "grammar_system_name": "Kope Grammar System",
  "created_at": ISODate("2024-01-15T10:30:00.000Z"),
  "categories": {
    "phonology": {
      "description": "Sound system and pronunciation rules",
      "subcategories": [],
      "notes": [],
      "examples": [],
      "ai_confidence": null,
      "human_verified": false,
      "updated_at": null
    },
    // ... other categories same structure
  },
  "metadata": {
    "version": "1.0",
    "status": "active",
    "description": "Grammar system for Kope"
  }
}
```

---

## Human Verification Fields

The platform supports verification workflows for content. The `human_verified` field appears in multiple collections:

### Verification by Collection

| Collection | Field Location | Default | Notes |
|------------|----------------|---------|-------|
| `bible_texts` | Document root | `false` | Only for non-English verses |
| `dictionaries` | `entries[].human_verified` | `false` | Per-entry verification |
| `grammar_systems` | `categories.<name>.human_verified` | `false` | Per-category verification |

### bible_texts Verification

For non-English verses, `human_verified` indicates whether a human translator has reviewed and approved the verse:

```javascript
{
  "language_code": "bughotu",
  "book_code": "matthew",
  "chapter": 1,
  "verse": 1,
  "translated_text": "...",
  "human_verified": false  // Awaiting human review
}
```

**Note**: English verses (the source text) do not have this field since they are the reference.

### Dictionary Entry Verification

Each dictionary entry can be individually verified:

```javascript
{
  "entries": [
    {
      "word": "example",
      "definition": "...",
      "human_verified": true  // This entry has been verified
    },
    {
      "word": "pending",
      "definition": "...",
      "human_verified": false  // This entry awaits verification
    }
  ]
}
```

### Grammar Category Verification

Grammar categories track verification at the category level:

```javascript
{
  "categories": {
    "phonology": {
      "human_verified": true,   // Category reviewed by human
      "updated_at": ISODate("...")
    }
  }
}
```

---

## Collection: word_index

Tracks word frequency across all verses for a language, with dictionary gap detection. One document per (language, word) pair. Rebuilt asynchronously when verse text is edited.

### Indexes

```javascript
{ "language_code": 1, "word": 1 }  // unique: true
{ "language_code": 1, "total_count": -1 }  // frequency lookup
{ "language_code": 1, "in_dictionary": 1 }  // name: "dictionary_gap"
```

### Schema

```javascript
{
  "_id": ObjectId,
  "language_code": String,
  "word": String,
  "total_count": Number,           // Total occurrences across all verses
  "book_count": Number,            // Number of distinct books containing this word
  "chapter_count": Number,         // Number of distinct chapters
  "in_dictionary": Boolean,        // Whether the word exists in the dictionary
  "first_seen": {                  // First occurrence location
    "book_code": String,
    "chapter": Number,
    "verse": Number
  },
  "last_rebuilt": ISODate,         // When this word's index was last rebuilt
  "occurrences": [                 // Sample occurrences (capped)
    { "book_code": String, "chapter": Number, "verse": Number }
  ]
}
```

---

## Collection: language_notes

Per-language notes and observations. One document per language with embedded notes array.

### Indexes

```javascript
{ "language_code": 1 }  // unique: true
```

### Schema

```javascript
{
  "_id": ObjectId,
  "language_code": String,
  "notes": [
    {
      "id": String,                // UUID
      "text": String,
      "created_at": ISODate,
      "updated_at": ISODate
    }
  ],
  "updated_at": ISODate            // Optional
}
```

---

## Collection: correction_log

Log of text corrections across Bible verses, dictionary entries, and grammar categories. One document per correction event.

### Indexes

```javascript
{ "language_code": 1, "created_at": -1 }
{ "language_code": 1, "content_type": 1, "created_at": -1 }
```

### Schema

```javascript
{
  "_id": ObjectId,
  "language_code": String,
  "content_type": String,          // "bible_verse" | "dictionary_entry" | "grammar_category"
  "content_reference": {           // Varies by content_type
    "book_code": String,           // For bible_verse
    "chapter": Number,
    "verse": Number,
    "word": String,                // For dictionary_entry
    "category": String             // For grammar_category
  },
  "original_text": String,
  "what_was_wrong": String,
  "correction": String,
  "created_at": ISODate
}
```

---

## Collection: chat_conversations

AI chat conversation history. One document per conversation, with embedded message array. Also stores pending tool call state for the write-tool approval gate.

### Indexes

```javascript
{ "updated_at": -1 }  // Newest-first listing
```

### Schema

```javascript
{
  "_id": ObjectId,
  "title": String,
  "messages": [
    {
      "role": String,              // "user" | "assistant"
      "content": String,
      "timestamp": String,         // ISO 8601
      "tool_calls": [String],      // Optional, tool names used
      "thinking_content": String   // Optional, assistant thinking text
    }
  ],
  "message_count": Number,
  "created_at": String,            // ISO 8601
  "updated_at": String,            // ISO 8601
  "pending_tool_call": {           // Present only when a write-tool is awaiting approval
    "call_id": String,
    "tool_name": String,
    "input": Object,
    "messages_snapshot": Array,    // Full Anthropic-format message history
    "system_prompt": String,       // Optional
    "thinking_enabled": Boolean,
    "created_at": String
  }
}
```

---

## Data Statistics

### Bible Structure Constants

| Metric | Value |
|--------|-------|
| Total Books | 66 |
| Old Testament Books | 39 |
| New Testament Books | 27 |
| Total Chapters | 1,189 |
| Total Verses | 31,102 |

### Documents Per Language

| Collection | English | Non-English |
|------------|---------|-------------|
| languages | 1 | 1 |
| bible_books | 66 | 66 |
| dictionaries | 1 | 1 |
| grammar_systems | 1 | 1 |
| **Total** | **69** | **69** |

---

## Migration Notes

The MongoDB migration from the original PostgreSQL prototype is complete. The current approach uses:

- Single database with language-based filtering
- Embedded documents for chapters/verses in `bible_books`
- Separate indexed collection (`bible_texts`) for verse-level queries
- Flexible schema for grammar categories


##  USFM Import for English NET (Base Language)


cd /filepath/back_end

# Import entire eng-web directory
python -m utils.usfm_parser.usfm_importer \
    ../data/bibles/eng-web_usfm/ \
    english
