# Ad-hoc mongosh Queries

Quick reference for inspecting or purging a language's data directly via `mongosh`. Connect with:

```bash
mongosh --port 27019
```

## Preview a language's data

```javascript
db.bible_texts.find({ language_code: "<language_code>" })
```

## Purge a language's data

Every collection with a `language_code` field needs a matching delete — see `EXPECTED_COLLECTIONS` in `utils/schema_enforcer/schema_definition.py` for the authoritative list (excludes `base_structure_bible`, whose `language_code` is always the constant `"base"`, and `chat_conversations`, which isn't language-scoped).

```javascript
use nlm_translator

const languageCode = "<language_code>";
const collections = [
  "bible_texts", "bible_books", "languages", "dictionaries",
  "grammar_systems", "word_index", "correction_log",
  "language_notes", "phrase_index"
];

collections.forEach(c =>
  print(c + ": " + db[c].deleteMany({ language_code: languageCode }).deletedCount + " deleted")
);
```

As a one-liner (note: `use` is a shell-only helper and doesn't work inside `--eval`; use `db.getSiblingDB()` instead):

```bash
mongosh --port 27019 --eval '
  const db = db.getSiblingDB("nlm_translator");
  const languageCode = "<language_code>";
  ["bible_texts","bible_books","languages","dictionaries","grammar_systems","word_index","correction_log","language_notes","phrase_index"]
    .forEach(c => print(c + ": " + db[c].deleteMany({language_code: languageCode}).deletedCount + " deleted"))
'
```
