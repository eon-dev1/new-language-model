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

### Collection Purposes

| Collection | Used By | Purpose |
|------------|---------|---------|
| `bible_books` | Routes, Frontend | Language-specific book metadata for display |
| `base_structure_bible` | Generator scripts | Canonical structure for seeding new databases |
| `bible_texts` | Routes, Frontend | Individual verse content for reading/editing |

---

## Collection: languages

Stores metadata for each language in the system, including translation progress tracking for both human and AI versions.

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
  "translation_levels": {
    "human": {
      "books_started": Number,
      "books_completed": Number,
      "verses_translated": Number,
      "last_updated": ISODate | null
    },
    "ai": {                        // null for English
      "books_started": Number,
      "books_completed": Number,
      "verses_translated": Number,
      "last_updated": ISODate | null,
      "model_version": String      // e.g., "nlm-v1.0"
    }
  },
  "metadata": {
    "creator": String,             // "nlm_fastapi_endpoint"
    "version": String,             // "1.0"
    "description": String,
    "dual_level_support": Boolean  // false for English
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
  "translation_levels": {
    "human": {
      "books_started": 0,
      "books_completed": 0,
      "verses_translated": 0,
      "last_updated": null
    },
    "ai": {
      "books_started": 0,
      "books_completed": 0,
      "verses_translated": 0,
      "last_updated": null,
      "model_version": "nlm-v1.0"
    }
  },
  "metadata": {
    "creator": "nlm_fastapi_endpoint",
    "version": "1.0",
    "description": "Biblical translation project for Kope",
    "dual_level_support": true
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
(language, book, translation_type) combination. This is the primary collection for book lists
shown in the frontend.

> **See**: `utils/schema_enforcer/schema_definition.py` for authoritative field definitions

### Indexes

```javascript
// Unique book lookup
{ "language_code": 1, "book_code": 1, "translation_type": 1 }
// unique: true, name: "book_lookup"

// Language + type filtering
{ "language_code": 1, "translation_type": 1 }
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
  "translation_type": String,     // "human" | "ai"
  "total_chapters": Number,       // e.g., 50 for Genesis
  "total_verses": Number,         // e.g., 1533 for Genesis
  "chapters": [                   // Embedded chapter data
    { "chapter": Number, "verse_count": Number }
  ],
  "created_at": ISODate,
  "updated_at": ISODate,          // Optional
  "translation_status": String,   // "complete" | "in_progress" | "draft"
  "metadata": {
    "testament": String,          // "old" | "new"
    "canonical_order": Number,    // 1-66
    "translator_type": String,    // "human" | "ai"
    "ai_model": String            // Optional, for AI translations
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
  "translation_type": "human",
  "total_chapters": 50,
  "total_verses": 1533,
  "chapters": [
    { "chapter": 1, "verse_count": 31 },
    { "chapter": 2, "verse_count": 25 },
    // ... all 50 chapters
  ],
  "created_at": ISODate("2024-01-15T10:30:00.000Z"),
  "translation_status": "in_progress",
  "metadata": {
    "testament": "old",
    "canonical_order": 1,
    "translator_type": "human"
  }
}
```

---

## Collection: bible_texts

Stores individual verses for efficient querying and search. This is the primary collection
for verse content across all languages.

> **See**: `utils/schema_enforcer/schema_definition.py` for authoritative field definitions

### Schema

```javascript
{
  "_id": ObjectId,
  "language_code": String,          // e.g., "english", "kope"
  "book_code": String,              // e.g., "genesis", "1_chronicles" (lowercase + underscores)
  "chapter": Number,
  "verse": Number,
  "translation_type": String,       // "human" | "ai"
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
{ "language_code": 1, "book_code": 1, "chapter": 1, "verse": 1, "translation_type": 1 }
// unique: true, name: "verse_lookup"

// Language + type filtering
{ "language_code": 1, "translation_type": 1 }
// name: "language_type_filter"

// Book + type filtering
{ "book_code": 1, "translation_type": 1 }
// name: "book_type_filter"
```

### Example Query Patterns

```javascript
// Get specific verse
db.bible_texts.findOne({
  language_code: "kope",
  book_code: "genesis",
  chapter: 1,
  verse: 1,
  translation_type: "human"
})

// Get all verses in a chapter
db.bible_texts.find({
  language_code: "kope",
  book_code: "genesis",
  chapter: 1,
  translation_type: "human"
}).sort({ verse: 1 })

// Get all AI translations for a book
db.bible_texts.find({
  language_code: "kope",
  book_code: "genesis",
  translation_type: "ai"
})

// Count translated verses
db.bible_texts.countDocuments({
  language_code: "kope",
  translation_type: "human",
  translated_text: { $ne: "" }
})
```

---

## Collection: dictionaries

Stores dictionary frameworks for each language, with separate documents for human and AI versions.
Currently empty - structure exists but no entries have been created yet.

> **See**: `utils/schema_enforcer/schema_definition.py` for authoritative field definitions

### Indexes

```javascript
// Unique lookup by language and type
{ "language_code": 1, "translation_type": 1 }
// unique: true, name: "dict_lookup"
```

### Schema

```javascript
{
  "_id": ObjectId,
  "language_code": String,
  "language_name": String,
  "translation_type": String,       // "human" | "ai"
  "dictionary_name": String,        // e.g., "Kope Human Dictionary"
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
    "status": String,               // "active"
    "generation_method": String,    // "human" | "ai"
    "ai_model": String | null
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
  "translation_type": "human",
  "dictionary_name": "Kope Human Dictionary",
  "entries": [],
  "entry_count": 0,
  "created_at": ISODate("2024-01-15T10:30:00.000Z"),
  "categories": [
    "noun", "verb", "adjective", "adverb", "preposition",
    "conjunction", "interjection", "pronoun", "article", "other"
  ],
  "metadata": {
    "description": "Human dictionary for Kope translation work",
    "version": "1.0",
    "status": "active",
    "generation_method": "human",
    "ai_model": null
  }
}
```

---

## Collection: grammar_systems

Stores comprehensive grammar frameworks organized by linguistic categories.
Currently empty - structure exists but no grammar data has been created yet.

> **See**: `utils/schema_enforcer/schema_definition.py` for authoritative field definitions

### Indexes

```javascript
// Unique lookup by language and type
{ "language_code": 1, "translation_type": 1 }
// unique: true, name: "grammar_lookup"
```

### Schema

```javascript
{
  "_id": ObjectId,
  "language_code": String,
  "language_name": String,
  "translation_type": String,       // "human" | "ai"
  "grammar_system_name": String,
  "created_at": ISODate,
  "categories": {
    "phonology": {
      "description": String,
      "subcategories": [String],
      "notes": [String],
      "examples": [String],
      "ai_confidence": Number | null  // null for human, 0.0-1.0 for AI
    },
    "morphology": {/* same structure */},
    "syntax": {/* same structure */},
    "semantics": {/* same structure */},
    "discourse": {/* same structure */}
  },
  "metadata": {
    "version": String,
    "status": String,
    "description": String,
    "generation_method": String,
    "ai_model": String | null,
    "human_review_status": String   // "pending" | "reviewed" | "n/a"
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
  "translation_type": "ai",
  "grammar_system_name": "Kope NLM-Generated Grammar System",
  "created_at": ISODate("2024-01-15T10:30:00.000Z"),
  "categories": {
    "phonology": {
      "description": "Sound system and pronunciation rules",
      "subcategories": ["consonants", "vowels", "tone", "stress", "phonotactics"],
      "notes": [],
      "examples": [],
      "ai_confidence": 0.0
    },
    "morphology": {
      "description": "Word structure and formation",
      "subcategories": ["noun_morphology", "verb_morphology", "adjective_morphology", "derivation"],
      "notes": [],
      "examples": [],
      "ai_confidence": 0.0
    },
    "syntax": {
      "description": "Sentence structure and word order",
      "subcategories": ["word_order", "clause_structure", "phrase_structure", "agreement"],
      "notes": [],
      "examples": [],
      "ai_confidence": 0.0
    },
    "semantics": {
      "description": "Meaning and interpretation",
      "subcategories": ["lexical_semantics", "compositional_semantics", "pragmatics"],
      "notes": [],
      "examples": [],
      "ai_confidence": 0.0
    },
    "discourse": {
      "description": "Text-level organization and coherence",
      "subcategories": ["paragraph_structure", "narrative_patterns", "discourse_markers"],
      "notes": [],
      "examples": [],
      "ai_confidence": 0.0
    }
  },
  "metadata": {
    "version": "1.0",
    "status": "active",
    "description": "NLM-Generated comprehensive grammar system for Kope",
    "generation_method": "ai",
    "ai_model": "nlm-v1.0",
    "human_review_status": "pending"
  }
}
```

---

## Human Verification Fields

The platform supports verification workflows for AI-generated or imported content. The `human_verified` field appears in multiple collections:

### Verification by Collection

| Collection | Field Location | Default | Notes |
|------------|----------------|---------|-------|
| `bible_texts` | Document root | `false` | Only for non-English verses |
| `dictionaries` | `entries[].human_verified` | `false` | Per-entry verification |
| `grammar_systems` | `metadata.human_review_status` | `"pending"` | Document-level status |

### bible_texts Verification

For non-English verses, `human_verified` indicates whether a human translator has reviewed and approved the verse:

```javascript
{
  "language_code": "bughotu",
  "book_code": "matthew",
  "chapter": 1,
  "verse": 1,
  "translation_type": "ai",
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

### Grammar System Verification

Grammar systems use document-level review status in metadata:

```javascript
{
  "metadata": {
    "human_review_status": "pending"  // "pending" | "reviewed" | "n/a"
  }
}
```

---

## Dual-Level Translation Model

### Document Relationship

For each non-English language, the system maintains parallel document sets:

```
Language: Kope
|
+-- bible_books (132 documents)
|   +-- Genesis (human)
|   +-- Genesis (ai)
|   +-- Exodus (human)
|   +-- Exodus (ai)
|   +-- ... (66 books x 2 types)
|
+-- dictionaries (2 documents)
|   +-- Kope Human Dictionary
|   +-- Kope NLM-Generated Dictionary
|
+-- grammar_systems (2 documents)
    +-- Kope Human Grammar System
    +-- Kope NLM-Generated Grammar System
```

### Translation Types

| Type | Code | Description |
|------|------|-------------|
| Human | `"human"` | Human-translated/curated content |
| AI | `"ai"` | LLM/NLM-generated content |

### Querying by Translation Type

```javascript
// Get all human translations for a language
db.bible_books.find({
  language_code: "kope",
  translation_type: "human"
})

// Get AI grammar system
db.grammar_systems.findOne({
  language_code: "kope",
  translation_type: "ai"
})

// Compare human vs AI for same book
const humanGenesis = db.bible_books.findOne({
  language_code: "kope",
  book_code: "genesis",
  translation_type: "human"
})

const aiGenesis = db.bible_books.findOne({
  language_code: "kope",
  book_code: "genesis",
  translation_type: "ai"
})
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
| bible_books | 66 | 132 |
| dictionaries | 1 | 2 |
| grammar_systems | 1 | 2 |
| **Total** | **69** | **137** |

---

## Migration Notes

### From PostgreSQL

The project is transitioning from a PostgreSQL schema where:
- Each language had its own database (e.g., `kope_bible`)
- Books were individual tables (e.g., `book_genesis`)
- Grammar used dynamic columns

### Current MongoDB Approach

- Single database with language-based filtering
- Embedded documents for chapters/verses in `bible_books`
- Separate indexed collection (`bible_texts`) for verse-level queries
- Flexible schema for grammar categories


##  USFM Import for English NET (Base Language)


cd back_end

# Import entire engnet directory
python -m utils.usfm_parser.usfm_importer \
    ../data/bibles/engnet_usfm/ \
    english \
    human
