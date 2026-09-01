# API Layer

This document describes the stable core of `src/renderer/api.ts`, the front-end's HTTP communication layer with the FastAPI backend. It intentionally does not document the full API surface — see Scope below.

## Configuration

```typescript
const API_BASE_URL = 'http://127.0.0.1:8221/api';
```

Hardcoded. No `.env` file or environment variable is involved — to point at a different backend, edit this constant directly. No authentication: the backend binds to `127.0.0.1` only. See [Architecture — Security Model](./architecture.md#security-model) for the rationale.

## Scope

This document covers the stable, CRUD-shaped surface: language management, Bible import/reading, dictionary, and grammar. `api.ts` also exports functions for Chat & Chat Conversations, Chat Config/Skills, translation streaming (single-verse and batch), Notes, Correction Log, Word Index rebuild, Export USFM, and Database Backup — these move faster than this doc can usefully track, so read `api.ts` and `back_end/routes/` directly for them rather than relying on a doc that will chase the churn.

## Error Handling

Every request goes through `makeRequest()`, which throws `ApiError` on any non-2xx response:

```typescript
export class ApiError extends Error {
  status: number;  // HTTP status code
  body: unknown;   // Parsed response body (structured object, or a string `detail`)
}
```

Callers rely on `.status`/`.body` to discriminate specific failures (e.g. a 409 conflict on a duplicate word) from generic errors — don't rewrap this in a plain `Error`, it strips the information callers need.

## Language Management

| Function | Endpoint | Notes |
|----------|----------|-------|
| `fetchLanguages()` | `GET /languages` | Returns `Language[]`, each with per-language verification progress |
| `ensureBaseLanguage(languageCode)` | `POST /ensure-base-language` | Idempotent — returns immediately if already loaded; may take ~30s on first run (full base-language import) |

## Bible Import & Reading

| Function | Endpoint | Notes |
|----------|----------|-------|
| `importBible(request)` | `POST /import-bible` | USFM import; `request` includes optional `human_verified?: boolean` |
| `fetchBibleBooks(languageCode)` | `GET /bible-books/{language}` | |
| `fetchChapterVerses(languageCode, bookCode, chapter)` | `GET /verses/{language}/{book}/{chapter}` | Returns paired English + translated text per verse |
| `updateVerseVerification(languageCode, bookCode, chapter, verse, humanVerified)` | `PATCH /verses/{language}/{book}/{chapter}/{verse}/verify` | |
| `updateVerseText(languageCode, bookCode, chapter, verse, translatedText)` | `PUT /verses/{language}/{book}/{chapter}/{verse}` | Auto-marks the verse `human_verified: true` |
| `searchBibleVerses(languageCode, query, limit = 50)` | `GET /verses/{language}/search` | Cross-book text search; zero results returns `[]`, not an error |

## Dictionary

Flat documents, one per word — no human/AI split.

| Function | Endpoint | Notes |
|----------|----------|-------|
| `fetchDictionaryEntries(languageCode)` | `GET /dictionary/{language}/entries` | |
| `saveDictionaryEntry(languageCode, entry)` | `POST /dictionary/{language}/entries` | `entry` accepts optional `original_word?` (rename) and `part_of_speech?`/`examples?` |
| `deleteDictionaryEntries(languageCode, words)` | `POST /dictionary/{language}/entries/delete` | Hard delete, no undo; same endpoint handles single or bulk |
| `verifyDictionaryEntry(languageCode, word, humanVerified)` | `PATCH /dictionary/{language}/entries/{word}/verify` | |

## Grammar

Flat documents, one per category — no human/AI split. Each content item (subcategory/note/example) is either a plain string (human-authored) or a rich object (AI-generated); type guards in `src/components/searchFilters.ts` (`isSubcategoryData`, `isNoteData`, `isExampleData`) distinguish them.

| Function | Endpoint | Notes |
|----------|----------|-------|
| `fetchGrammarCategories(languageCode)` | `GET /grammar/{language}/categories` | |
| `saveGrammarCategory(languageCode, categoryName, content)` | `POST /grammar/{language}/categories/{name}` | Write path accepts rich format only |
| `verifyGrammarCategory(languageCode, categoryName, humanVerified)` | `PATCH /grammar/{language}/categories/{name}/verify` | |
| `verifyGrammarSubcategory(languageCode, categoryName, subcategoryIndex, humanVerified)` | `PATCH .../subcategories/{index}/verify` | |
| `verifyGrammarNote(languageCode, categoryName, noteIndex, humanVerified)` | `PATCH .../notes/{index}/verify` | |
| `verifyGrammarExample(languageCode, categoryName, exampleIndex, humanVerified)` | `PATCH .../examples/{index}/verify` | |

## Security

The backend binds to `127.0.0.1` only — no external network access, no credentials transmitted. Full rationale lives in [Architecture — Security Model](./architecture.md#security-model), not repeated here.
