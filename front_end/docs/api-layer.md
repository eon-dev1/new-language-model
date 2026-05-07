# API Layer

This document describes the API communication layer, including request handling and error management.

## Overview

The API layer (`src/renderer/api.ts`) handles communication between the Electron renderer process and the FastAPI backend. The layer provides a simple HTTP interface for making API requests.

**Note**: API authentication has been disabled for local development. The server binds to localhost only (127.0.0.1) and MongoDB provides its own authentication layer.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Renderer Process                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                        api.ts                             │   │
│  │                                                           │   │
│  │  makeRequest(endpoint, options)                           │   │
│  │  - Simple HTTP layer                                      │   │
│  │  - No authentication required                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                                                │
                                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend                            │
│                                                                    │
│  Endpoint: http://localhost:8221/api/                             │
│  Authentication: Disabled for local development                    │
│  Security: Localhost-only binding (127.0.0.1)                      │
└───────────────────────────────────────────────────────────────────┘
```

## Configuration

### Base URL

The API base URL is hardcoded in `src/renderer/api.ts`:

```typescript
const API_BASE_URL = 'http://127.0.0.1:8221/api';
```

No `.env` file or environment variable is required. To change the URL, edit the constant directly.

**Note**: No credential files are required. API authentication has been disabled for local development.

## Core Functions

### makeRequest(endpoint, options)

Makes an HTTP request to the backend.

```typescript
async function makeRequest(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response>
```

**Parameters**:
- `endpoint`: API path relative to base URL (e.g., `/languages`)
- `options`: Standard fetch options (method, body, etc.)

**Returns**: Fetch Response object

**Behavior**:
1. Validates endpoint is a non-empty string
2. Adds default Content-Type header
3. Makes fetch request to `${API_BASE_URL}${endpoint}`
4. Throws on non-OK responses with status detail

## Exported API Functions

### testApiConnection()

Tests connectivity with the backend.

```typescript
export async function testApiConnection(): Promise<boolean>
```

**Returns**: `true` if connection succeeds, `false` otherwise

**Usage**:
```typescript
const isConnected = await testApiConnection();
if (!isConnected) {
  console.error('Backend not available');
}
```

### fetchLanguages()

Fetches the list of available languages from the backend.

```typescript
export async function fetchLanguages(): Promise<Language[]>
```

**Language Interface**:
```typescript
export interface VerificationProgress {
  old_testament: number;  // 0-100 percentage
  new_testament: number;  // 0-100 percentage
  total: number;          // 0-100 percentage
}

export interface Language {
  language_code: string;
  language_name: string;
  total_verses: number;
  verified_count: number;
  verification_progress: VerificationProgress;
  status: string;
  is_base_language: boolean;
}
```

**Returns**: Array of `Language` objects

**Throws**: Error if request fails or response is invalid

**Usage**:
```typescript
try {
  const languages = await fetchLanguages();
  console.log(`Found ${languages.length} languages`);
} catch (error) {
  console.error('Failed to fetch languages:', error);
}
```

---

## IPC Functions

`selectFolder()` wraps `window.api.selectFolder()` for use in the renderer. See [Types — selectFolder](./types.md#selectfolder) for the full contract and IPC channel details.

---

## Bible Import API

### importBible()

Import USFM Bible files from a directory.

```typescript
export async function importBible(request: ImportBibleRequest): Promise<ImportBibleResponse>
```

**Request Interface**:
```typescript
interface ImportBibleRequest {
  language_code: string;
  language_name: string;
  usfm_directory: string;
}
```

**Response Interface**:
```typescript
interface ImportBibleResponse {
  success: boolean;
  language_code: string;
  message: string;
  verses_imported: number;
  verses_updated: number;
  books_processed: number;
  is_reimport: boolean;
}
```

### importHtmlBible()

Import HTML Bible files from a directory.

```typescript
export async function importHtmlBible(request: ImportHtmlBibleRequest): Promise<ImportBibleResponse>
```

**Request Interface**:
```typescript
interface ImportHtmlBibleRequest {
  language_code: string;
  language_name: string;
  html_directory: string;
}
```

---

## Bible Reader API

### fetchBibleBooks()

Fetch Bible books metadata for a language.

```typescript
export async function fetchBibleBooks(languageCode: string): Promise<BibleBookInfo[]>
```

**Response Item Interface**:
```typescript
interface BibleBookInfo {
  book_name: string;
  book_code: string;
  total_chapters: number;
  total_verses: number;
  translation_status?: string;
  has_data: boolean;
  metadata?: {
    testament: string;
    canonical_order: number;
  };
}
```

### fetchChapterVerses()

Fetch verses for a specific chapter with paired English and translation.

```typescript
export async function fetchChapterVerses(
  languageCode: string,
  bookCode: string,
  chapter: number
): Promise<ChapterResponse>
```

**Response Interface**:
```typescript
interface ChapterResponse {
  language_code: string;
  book_code: string;
  chapter: number;
  verses: VerseData[];
  count: number;
}

interface VerseData {
  verse: number;
  english_text: string;
  translated_text: string | null;  // null for untranslated verses
  human_verified: boolean;
}
```

### updateVerseVerification()

Update the `human_verified` status for a verse.

```typescript
export async function updateVerseVerification(
  languageCode: string,
  bookCode: string,
  chapter: number,
  verse: number,
  humanVerified: boolean
): Promise<{ success: boolean }>
```

---

## Dictionary API

### fetchDictionaryEntries()

Fetch dictionary entries for a language. Entries are flat documents — one per word, no human/AI split.

```typescript
export async function fetchDictionaryEntries(languageCode: string): Promise<DictionaryEntriesResponse>
```

**Response Interface**:
```typescript
interface DictionaryEntriesResponse {
  language_code: string;
  entries: MergedDictionaryEntry[];
  count: number;
}

interface MergedDictionaryEntry {
  word: string;
  definition: string;
  part_of_speech?: string;
  examples: string[];
  human_verified: boolean;
  created_at?: string;
  updated_at?: string;
}
```

### saveDictionaryEntry()

Create or update a human dictionary entry.

```typescript
export async function saveDictionaryEntry(
  languageCode: string,
  entry: SaveDictionaryEntryRequest
): Promise<{ success: boolean; word: string; action: string }>
```

**Request Interface**:
```typescript
interface SaveDictionaryEntryRequest {
  word: string;
  definition: string;
  part_of_speech?: string;
  examples?: string[];
}
```

### verifyDictionaryEntry()

Update verification status for a dictionary entry.

```typescript
export async function verifyDictionaryEntry(
  languageCode: string,
  word: string,
  humanVerified: boolean
): Promise<{ success: boolean }>
```

---

## Grammar API

### fetchGrammarCategories()

Fetch grammar categories for a language. Categories are flat documents — one per category name, no human/AI split.

```typescript
export async function fetchGrammarCategories(languageCode: string): Promise<GrammarCategoriesResponse>
```

**Response Interface**:
```typescript
interface GrammarCategoriesResponse {
  language_code: string;
  categories: MergedGrammarCategory[];
  count: number;
}

interface MergedGrammarCategory {
  name: string;
  description: string;
  subcategories: SubcategoryItem[];  // string | SubcategoryData
  notes: NoteItem[];                 // string | NoteData
  examples: ExampleItem[];           // string | ExampleData
  human_verified: boolean;
  updated_at?: string;
}
```

Type guards for the union item types are in `src/components/searchFilters.ts` (`isSubcategoryData`, `isExampleData`, `isNoteData`).

### saveGrammarCategory()

Update human grammar category content.

```typescript
export async function saveGrammarCategory(
  languageCode: string,
  categoryName: string,
  content: SaveGrammarCategoryRequest
): Promise<{ success: boolean; action: string }>
```

**Request Interface**:
```typescript
interface SaveGrammarCategoryRequest {
  notes: NoteData[];            // Rich format only
  subcategories: SubcategoryData[];  // Rich format only
  examples: ExampleData[];      // Rich format only
}
```

### verifyGrammarCategory()

Update verification status for a grammar category.

```typescript
export async function verifyGrammarCategory(
  languageCode: string,
  categoryName: string,
  humanVerified: boolean
): Promise<{ success: boolean }>
```

---

## Error Handling

### Error Types

| Error Scenario | Behavior | User Impact |
|----------------|----------|-------------|
| Network error | Throws with fetch error details | Check backend is running |
| Invalid JSON | Throws "Invalid JSON response from server" | Backend issue |
| HTTP error | Throws with status code and detail | Check request/backend |
| Invalid endpoint | Throws immediately | Caller bug |

### Logging Levels

The API layer uses different console methods for different scenarios:

| Method | Usage |
|--------|-------|
| `console.debug` | Routine operations (request start/end) |
| `console.info` | Successful operations (connection test, fetch complete) |
| `console.warn` | Connection issues |
| `console.error` | Fatal errors (parse failures, network issues) |

## Request Flow Example

Complete flow for `fetchLanguages()`:

```
1. Homepage component calls fetchLanguages()
     │
2. api.ts: makeRequest('/languages')
     │
     ├─→ Add Content-Type header
     │
     └─→ fetch('http://127.0.0.1:8221/api/languages', { headers })
     │
3. Response handling
     │
     ├─→ [Success] Parse JSON, return languages array (Language[])
     │
     └─→ [Error] Throw error with status
     │
4. Homepage component updates state with languages
```

## Backend API Reference

### Base URL

```
http://127.0.0.1:8221/api
```

### Endpoints Used

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/check-connection` | Health check endpoint |
| GET | `/languages` | List available languages with progress |
| GET | `/bible-books/{language}` | Get Bible books for a language |
| GET | `/verses/{language}/{book}/{chapter}` | Get chapter verses |
| PUT | `/verses/{language}/{book}/{chapter}/{verse}` | Update verse text |
| PATCH | `/verses/{language}/{book}/{chapter}/{verse}/verify` | Update verse verification |
| GET | `/verses/{language}/search` | Cross-book verse text search |
| POST | `/import-bible` | Import USFM Bible files |
| POST | `/import-html-bible` | Import HTML Bible files |
| POST | `/ensure-base-language` | Load base language into database |
| GET | `/dictionary/{language}/entries` | Get dictionary entries |
| POST | `/dictionary/{language}/entries` | Create/update dictionary entry |
| PATCH | `/dictionary/{language}/entries/{word}/verify` | Update entry verification |
| GET | `/grammar/{language}/categories` | Get grammar categories |
| POST | `/grammar/{language}/categories/{name}` | Update grammar category |
| PATCH | `/grammar/{language}/categories/{name}/verify` | Update category verification |

### Response Formats

**GET /languages**
```json
{
  "languages": [
    {
      "language_code": "bughotu",
      "language_name": "Bughotu",
      "total_verses": 31102,
      "verified_count": 1500,
      "verification_progress": {
        "old_testament": 2.1,
        "new_testament": 8.4,
        "total": 4.8
      },
      "status": "active",
      "is_base_language": false
    }
  ]
}
```

**GET /check-connection**
```json
{
  "status": "ok"
}
```

### Error Responses

```json
{
  "detail": "Error message describing what went wrong"
}
```

## Security Considerations

### Localhost-Only Access

The FastAPI backend binds to localhost only (127.0.0.1), which means:
- No external network access to the API
- Communication is restricted to the local machine
- MongoDB provides its own authentication layer for database operations

### Request Headers

Only necessary headers are sent:
- `Content-Type`: application/json

No sensitive data (cookies, session tokens, API keys) is transmitted.

## Testing

### Manual Testing

1. Start backend: `cd back_end && python main.py`
2. Start frontend: `cd front_end && npm run dev`
3. Open DevTools console
4. Observe API logs for connection test and language fetch

### Connection Testing

```typescript
const isConnected = await testApiConnection();
console.log('Backend connected:', isConnected);
```

## Troubleshooting

| Issue | Check |
|-------|-------|
| Network errors | Ensure backend is running on port 8221 |
| Connection refused | Verify backend started: `python main.py` |
| Invalid JSON response | Check backend logs for errors |
