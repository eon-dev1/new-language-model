// api.ts

/**
 * API service module for communication with the FastAPI backend.
 *
 * This module provides a simple HTTP layer for making requests to the backend.
 * Authentication has been disabled for local development - the server binds
 * to localhost only and MongoDB provides its own authentication.
 */

const API_BASE_URL = 'http://127.0.0.1:8221/api';

/**
 * Thrown by makeRequest on any non-2xx response. Carries the parsed JSON body
 * intact (structured or string `detail`) so callers can discriminate on it,
 * rather than collapsing it into a stringified message.
 */
export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

/**
 * Makes a request to the API with error handling.
 *
 * @param {string} endpoint - The API endpoint (relative to base URL)
 * @param {RequestInit} options - Fetch options (method, body, etc.)
 * @returns {Promise<Response>} The fetch response
 * @throws {ApiError} If the response status is not ok
 * @throws {Error} If the request itself fails (network, invalid endpoint, etc.)
 */
async function makeRequest(endpoint: string, options: RequestInit = {}): Promise<Response> {
  try {
    if (!endpoint || typeof endpoint !== 'string') {
      throw new Error('Invalid endpoint provided');
    }

    const requestOptions: RequestInit = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    };

    const fullUrl = `${API_BASE_URL}${endpoint}`;
    console.debug(`[API] Making request to ${fullUrl}`);

    const response = await fetch(fullUrl, requestOptions);

    if (!response.ok) {
      let body: unknown = null;
      try { body = await response.json(); } catch {}
      const detail = (body as { detail?: unknown } | null)?.detail;
      // Only interpolate `detail` into the message when it's a string — an
      // object-shaped detail (e.g. a 409 conflict body) stays on `.body`,
      // where it survives intact instead of collapsing to "[object Object]".
      const message = typeof detail === 'string' ? detail : `${response.status} - ${response.statusText}`;
      console.error(`[API] Request failed: ${message}`);
      throw new ApiError(response.status, body, `HTTP error! ${message}`);
    }

    console.debug(`[API] Request successful: ${endpoint}`);
    return response;

  } catch (error) {
    console.error(`[API] Request to ${endpoint} failed:`, error);
    throw error;
  }
}


/**
 * Verification progress breakdown by testament.
 */
interface VerificationProgress {
  old_testament: number;  // 0-100 percentage
  new_testament: number;  // 0-100 percentage
  total: number;          // 0-100 percentage
}

/**
 * Language data returned from /api/languages endpoint.
 */
export interface Language {
  language_code: string;
  language_name: string;
  total_verses: number;
  verified_count: number;
  verification_progress: VerificationProgress;
  status: string;
  is_base_language: boolean;
}

/**
 * Fetch the list of languages from the backend.
 *
 * Returns language objects with verification progress for each language project.
 *
 * @returns {Promise<Language[]>} A promise that resolves to an array of language objects
 * @throws {Error} Throws an error if the API request fails
 */
export async function fetchLanguages(): Promise<Language[]> {
  try {
    console.info('[API] Fetching languages...');
    const response = await makeRequest('/languages');

    let data;
    try {
      data = await response.json();
    } catch (parseError) {
      console.error('[API] Failed to parse JSON response:', parseError);
      throw new Error('Invalid JSON response from server');
    }

    if (!data || typeof data !== 'object') {
      throw new Error('Invalid response format from server');
    }

    const languages: Language[] = data.languages || [];

    if (!Array.isArray(languages)) {
      console.warn('[API] Languages field is not an array, returning empty array');
      return [];
    }

    console.info(`[API] Successfully fetched ${languages.length} languages`);
    return languages;

  } catch (error) {
    console.error('[API] Failed to fetch languages:', error);
    throw new Error(`Failed to fetch languages: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Opens native folder selection dialog via Electron IPC.
 *
 * @returns Selected folder path, or null if cancelled
 */
export const selectFolder = (): Promise<string | null> => {
  return window.api.selectFolder();
};

/**
 * Import Bible request payload.
 */
interface ImportBibleRequest {
  language_code: string;
  language_name: string;
  usfm_directory: string;
  human_verified?: boolean;
}

/**
 * Import Bible response from backend.
 */
interface ImportBibleResponse {
  success: boolean;
  language_code: string;
  message: string;
  verses_imported: number;
  verses_updated: number;
  books_processed: number;
  is_reimport: boolean;
}

/**
 * Import USFM Bible files from a directory.
 *
 * @param request - Import configuration
 * @returns Import result with verse counts and status
 * @throws Error if import fails
 */
export async function importBible(request: ImportBibleRequest): Promise<ImportBibleResponse> {
  try {
    console.info('[API] Starting Bible import...');
    const response = await makeRequest('/import-bible', {
      method: 'POST',
      body: JSON.stringify(request)
    });

    const data = await response.json();
    console.info(`[API] Import complete: ${data.message}`);
    return data as ImportBibleResponse;

  } catch (error) {
    console.error('[API] Bible import failed:', error);
    throw new Error(`Bible import failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// ── Base Language ─────────────────────────────────────────────────────────────

interface EnsureBaseLanguageResponse {
  success: boolean;
  already_loaded: boolean;
  language_code: string;
  message: string;
  verses_imported: number;
  verses_updated: number;
  books_processed: number;
  warnings: string[];
}

/**
 * Ensure the selected base language is loaded in the database.
 * Idempotent — returns immediately if already loaded.
 * May take ~30s on first run (31k verse import).
 */
export async function ensureBaseLanguage(languageCode: string): Promise<EnsureBaseLanguageResponse> {
  try {
    console.info(`[API] Ensuring base language: ${languageCode}...`);
    const response = await makeRequest('/ensure-base-language', {
      method: 'POST',
      body: JSON.stringify({ language_code: languageCode })
    });
    const data: EnsureBaseLanguageResponse = await response.json();
    console.info(`[API] Base language ${languageCode}: already_loaded=${data.already_loaded}`);
    if (data.warnings?.length) {
      data.warnings.forEach(w => console.warn(`[API] Base language warning: ${w}`));
    }
    return data;
  } catch (error) {
    console.error('[API] Failed to ensure base language:', error);
    throw new Error(`Failed to ensure base language: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// ============================================================================
// Bible Reader API
// ============================================================================

/**
 * Individual verse with paired English and translation text.
 */
export interface VerseData {
  verse: number;
  english_text: string;
  translated_text: string | null;
  human_verified: boolean;
}

/**
 * Response containing all verses for a chapter.
 */
interface ChapterResponse {
  language_code: string;
  book_code: string;
  chapter: number;
  verses: VerseData[];
  count: number;
}

/**
 * Bible book information from /api/bible-books endpoint.
 */
export interface BibleBookInfo {
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

/**
 * Response from /api/bible-books endpoint.
 */
interface BibleBooksResponse {
  language: string;
  books: BibleBookInfo[];
  count: number;
}

/**
 * Single verse result from a cross-book text search.
 */
export interface VerseSearchResult {
  book_code: string;
  chapter: number;
  verse: number;
  english_text: string;
  translated_text: string | null;
}

/**
 * Response from /api/verses/{language}/search endpoint.
 */
interface VerseSearchResponse {
  results: VerseSearchResult[];
  count: number;
  query: string;
}

/**
 * Fetch Bible books for a language.
 *
 * @param languageCode - The language code to fetch books for
 * @returns Array of Bible book information
 * @throws Error if fetch fails
 */
export async function fetchBibleBooks(languageCode: string): Promise<BibleBookInfo[]> {
  try {
    console.info(`[API] Fetching Bible books for ${languageCode}...`);
    const response = await makeRequest(`/bible-books/${languageCode}`);
    const data: BibleBooksResponse = await response.json();
    console.info(`[API] Successfully fetched ${data.count} Bible books`);
    return data.books || [];
  } catch (error) {
    console.error('[API] Failed to fetch Bible books:', error);
    throw new Error(`Failed to fetch Bible books: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Fetch verses for a specific chapter with paired English and translation.
 *
 * @param languageCode - Target language code
 * @param bookCode - Bible book code (e.g., 'GEN', 'MAT')
 * @param chapter - Chapter number (1-based)
 * @returns Chapter response with paired verses
 * @throws Error if fetch fails
 */
export async function fetchChapterVerses(
  languageCode: string,
  bookCode: string,
  chapter: number
): Promise<ChapterResponse> {
  try {
    console.info(`[API] Fetching verses for ${languageCode}/${bookCode} chapter ${chapter}...`);
    const response = await makeRequest(`/verses/${languageCode}/${bookCode}/${chapter}`);
    const data: ChapterResponse = await response.json();
    console.info(`[API] Successfully fetched ${data.count} verses`);
    return data;
  } catch (error) {
    console.error('[API] Failed to fetch chapter verses:', error);
    throw new Error(`Failed to fetch verses: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Update the human_verified status for a specific verse.
 *
 * @param languageCode - Target language code
 * @param bookCode - Bible book code
 * @param chapter - Chapter number
 * @param verse - Verse number
 * @param humanVerified - New verification status
 * @returns Success response
 * @throws Error if update fails
 */
export async function updateVerseVerification(
  languageCode: string,
  bookCode: string,
  chapter: number,
  verse: number,
  humanVerified: boolean
): Promise<{ success: boolean }> {
  try {
    console.info(`[API] Updating verification for ${languageCode}/${bookCode} ${chapter}:${verse}...`);
    const response = await makeRequest(
      `/verses/${languageCode}/${bookCode}/${chapter}/${verse}/verify`,
      {
        method: 'PATCH',
        body: JSON.stringify({ human_verified: humanVerified })
      }
    );
    const data = await response.json();
    console.info(`[API] Verification updated to ${humanVerified}`);
    return { success: data.success };
  } catch (error) {
    console.error('[API] Failed to update verse verification:', error);
    throw new Error(`Failed to update verification: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Update the translated text for a specific verse.
 * Auto-marks the verse as human_verified = true.
 *
 * @param languageCode - Target language code
 * @param bookCode - Bible book code
 * @param chapter - Chapter number
 * @param verse - Verse number
 * @param translatedText - New translation text
 * @returns Response with updated verse info
 * @throws Error if update fails
 */
export async function updateVerseText(
  languageCode: string,
  bookCode: string,
  chapter: number,
  verse: number,
  translatedText: string
): Promise<{ success: boolean; translated_text: string; human_verified: boolean }> {
  try {
    console.info(`[API] Updating text for ${languageCode}/${bookCode} ${chapter}:${verse}...`);
    const response = await makeRequest(
      `/verses/${languageCode}/${bookCode}/${chapter}/${verse}`,
      {
        method: 'PUT',
        body: JSON.stringify({ translated_text: translatedText })
      }
    );
    const data = await response.json();
    console.info(`[API] Verse text updated`);
    return {
      success: data.success,
      translated_text: data.translated_text,
      human_verified: data.human_verified
    };
  } catch (error) {
    console.error('[API] Failed to update verse text:', error);
    throw new Error(`Failed to update verse text: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Search verse text across all books in both English and the target language.
 *
 * @param languageCode - Target language code
 * @param query - Search query (min 2 chars)
 * @param limit - Max results to return (default 50)
 * @returns Array of matching verses with location info
 * @throws Error if fetch fails (zero results returns [] not an error)
 */
export async function searchBibleVerses(
  languageCode: string,
  query: string,
  limit = 50
): Promise<VerseSearchResult[]> {
  try {
    console.info(`[API] Searching verses for "${query}" in ${languageCode}...`);
    const response = await makeRequest(
      `/verses/${languageCode}/search?q=${encodeURIComponent(query)}&limit=${limit}`
    );
    const data: VerseSearchResponse = await response.json();
    console.info(`[API] Verse search returned ${data.count} results`);
    return data.results;
  } catch (error) {
    console.error('[API] Failed to search verses:', error);
    throw new Error(`Failed to search verses: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// ============================================================================
// Dictionary API
// ============================================================================

/**
 * Dictionary entry — single document per word, no human/AI split.
 */
export interface MergedDictionaryEntry {
  word: string;
  definition: string;
  part_of_speech?: string;
  examples: string[];
  human_verified: boolean;
  created_at?: string;
  updated_at?: string;
}


/**
 * Response from /api/dictionary/{language}/entries endpoint.
 */
interface DictionaryEntriesResponse {
  language_code: string;
  entries: MergedDictionaryEntry[];
  count: number;
}

/**
 * Request to create or update a dictionary entry.
 */
interface SaveDictionaryEntryRequest {
  word: string;
  definition: string;
  part_of_speech?: string;
  examples?: string[];
  original_word?: string;
}

/**
 * Fetch merged dictionary entries for a language.
 *
 * @param languageCode - The language code
 * @returns Merged entries from both human and AI sources
 */
export async function fetchDictionaryEntries(languageCode: string): Promise<DictionaryEntriesResponse> {
  try {
    console.info(`[API] Fetching dictionary entries for ${languageCode}...`);
    const response = await makeRequest(`/dictionary/${languageCode}/entries`);
    const data: DictionaryEntriesResponse = await response.json();
    console.info(`[API] Successfully fetched ${data.count} dictionary entries`);
    return data;
  } catch (error) {
    console.error('[API] Failed to fetch dictionary entries:', error);
    throw new Error(`Failed to fetch dictionary entries: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Create or update a human dictionary entry.
 *
 * @param languageCode - The language code
 * @param entry - Entry data (word, definition, etc.)
 * @returns Success response with action taken
 */
export async function saveDictionaryEntry(
  languageCode: string,
  entry: SaveDictionaryEntryRequest
): Promise<{ success: boolean; word: string; action: string }> {
  // Deliberately no try/catch here: a non-2xx response throws ApiError (with
  // .status/.body intact) from makeRequest, and callers need that structure
  // to discriminate a 409 conflict from other failures. Rewrapping it in a
  // plain Error would strip .status/.body and silently break that.
  console.info(`[API] Saving dictionary entry '${entry.word}' for ${languageCode}...`);
  const response = await makeRequest(`/dictionary/${languageCode}/entries`, {
    method: 'POST',
    body: JSON.stringify(entry)
  });
  const data = await response.json();
  console.info(`[API] Dictionary entry ${data.action}: ${entry.word}`);
  return data;
}

/**
 * Update verification status for a dictionary entry.
 *
 * @param languageCode - The language code
 * @param word - The word to verify
 * @param translationType - Which version to verify ('human' or 'ai')
 * @param humanVerified - New verification status
 */
interface DeleteDictionaryEntriesResponse {
  success: boolean;
  language_code: string;
  absent: string[];
}

/**
 * Delete one or more dictionary entries by word (hard delete, no undo).
 *
 * @param languageCode - The language code
 * @param words - Words to delete (single or bulk, via the same endpoint)
 * @returns `absent` — every requested word, normalized, confirmed no longer in the dictionary
 */
export async function deleteDictionaryEntries(
  languageCode: string,
  words: string[]
): Promise<DeleteDictionaryEntriesResponse> {
  // Deliberately no try/catch here — same reasoning as saveDictionaryEntry: a
  // non-2xx response must propagate as ApiError (with .status/.body intact)
  // so the caller can show the real server-provided error and let the user retry.
  const response = await makeRequest(`/dictionary/${languageCode}/entries/delete`, {
    method: 'POST',
    body: JSON.stringify({ words })
  });
  return response.json();
}

export async function verifyDictionaryEntry(
  languageCode: string,
  word: string,
  humanVerified: boolean
): Promise<{ success: boolean }> {
  try {
    console.info(`[API] Verifying dictionary entry '${word}' for ${languageCode}...`);
    const response = await makeRequest(`/dictionary/${languageCode}/entries/${encodeURIComponent(word)}/verify`, {
      method: 'PATCH',
      body: JSON.stringify({ human_verified: humanVerified })
    });
    const data = await response.json();
    console.info(`[API] Dictionary entry verification updated: ${humanVerified}`);
    return { success: data.success };
  } catch (error) {
    console.error('[API] Failed to verify dictionary entry:', error);
    throw new Error(`Failed to verify dictionary entry: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// ============================================================================
// Grammar API
// ============================================================================

/**
 * Rich subcategory data structure (AI-generated).
 */
export interface SubcategoryData {
  name: string;
  content: string;
  examples: string[];
  human_verified?: boolean;
}

/**
 * Rich note data structure with verification.
 */
export interface NoteData {
  text: string;
  human_verified?: boolean;
}

/**
 * Rich example data structure (AI-generated).
 */
export interface ExampleData {
  source_text?: string;  // New language-agnostic field name
  bughotu?: string;      // Legacy field name (for backward compat on read)
  english: string;
  analysis: string;
  human_verified?: boolean;
}

/** Subcategory can be a simple string (human) or rich object (AI). */
export type SubcategoryItem = string | SubcategoryData;

/** Note can be a simple string (legacy) or rich object with verification. */
export type NoteItem = string | NoteData;

/** Example can be a simple string (human) or rich object (AI). */
export type ExampleItem = string | ExampleData;

/**
 * Grammar category — single document per category, no human/AI split.
 */
export interface MergedGrammarCategory {
  name: string;
  description: string;
  subcategories: SubcategoryItem[];
  notes: NoteItem[];
  examples: ExampleItem[];
  human_verified: boolean;
  updated_at?: string;
}

/** Alias for backward compatibility within this file. */
export type GrammarCategoryVersion = MergedGrammarCategory;

/**
 * Response from /api/grammar/{language}/categories endpoint.
 */
interface GrammarCategoriesResponse {
  language_code: string;
  categories: MergedGrammarCategory[];
  count: number;
}

/**
 * Request to update grammar category content.
 * Write path accepts rich format only.
 */
interface SaveGrammarCategoryRequest {
  notes: NoteData[];  // Rich only with verification
  subcategories: SubcategoryData[];  // Rich only
  examples: ExampleData[];           // Rich only
}

/**
 * Fetch merged grammar categories for a language.
 *
 * @param languageCode - The language code
 * @returns Merged categories from both human and AI sources
 */
export async function fetchGrammarCategories(languageCode: string): Promise<GrammarCategoriesResponse> {
  try {
    console.info(`[API] Fetching grammar categories for ${languageCode}...`);
    const response = await makeRequest(`/grammar/${languageCode}/categories`);
    const data: GrammarCategoriesResponse = await response.json();
    console.info(`[API] Successfully fetched ${data.count} grammar categories`);
    return data;
  } catch (error) {
    console.error('[API] Failed to fetch grammar categories:', error);
    throw new Error(`Failed to fetch grammar categories: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Update human grammar category content.
 *
 * @param languageCode - The language code
 * @param categoryName - Category name (phonology, morphology, etc.)
 * @param content - Notes and examples to save
 * @returns Success response
 */
export async function saveGrammarCategory(
  languageCode: string,
  categoryName: string,
  content: SaveGrammarCategoryRequest
): Promise<{ success: boolean; action: string }> {
  try {
    console.info(`[API] Saving grammar category '${categoryName}' for ${languageCode}...`);
    const response = await makeRequest(`/grammar/${languageCode}/categories/${categoryName}`, {
      method: 'POST',
      body: JSON.stringify(content)
    });
    const data = await response.json();
    console.info(`[API] Grammar category ${data.action}: ${categoryName}`);
    return data;
  } catch (error) {
    console.error('[API] Failed to save grammar category:', error);
    throw new Error(`Failed to save grammar category: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Update verification status for a grammar category.
 *
 * @param languageCode - The language code
 * @param categoryName - Category name
 * @param translationType - Which version to verify ('human' or 'ai')
 * @param humanVerified - New verification status
 */
export async function verifyGrammarCategory(
  languageCode: string,
  categoryName: string,
  humanVerified: boolean
): Promise<{ success: boolean }> {
  try {
    console.info(`[API] Verifying grammar category '${categoryName}' for ${languageCode}...`);
    const response = await makeRequest(`/grammar/${languageCode}/categories/${categoryName}/verify`, {
      method: 'PATCH',
      body: JSON.stringify({ human_verified: humanVerified })
    });
    const data = await response.json();
    console.info(`[API] Grammar category verification updated: ${humanVerified}`);
    return { success: data.success };
  } catch (error) {
    console.error('[API] Failed to verify grammar category:', error);
    throw new Error(`Failed to verify grammar category: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Update verification status for a specific subcategory within a grammar category.
 *
 * @param languageCode - The language code
 * @param categoryName - Category name (phonology, morphology, etc.)
 * @param subcategoryIndex - Index of the subcategory in the array
 * @param translationType - Which version to verify ('human' or 'ai')
 * @param humanVerified - New verification status
 */
export async function verifyGrammarSubcategory(
  languageCode: string,
  categoryName: string,
  subcategoryIndex: number,
  humanVerified: boolean
): Promise<{ success: boolean; subcategory_name: string }> {
  try {
    console.info(`[API] Verifying subcategory ${subcategoryIndex} in '${categoryName}' for ${languageCode}...`);
    const response = await makeRequest(
      `/grammar/${languageCode}/categories/${categoryName}/subcategories/${subcategoryIndex}/verify`,
      {
        method: 'PATCH',
        body: JSON.stringify({ human_verified: humanVerified })
      }
    );
    const data = await response.json();
    console.info(`[API] Subcategory verification updated: ${humanVerified}`);
    return { success: data.success, subcategory_name: data.subcategory_name };
  } catch (error) {
    console.error('[API] Failed to verify grammar subcategory:', error);
    throw new Error(`Failed to verify subcategory: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Verify a grammar note.
 *
 * @param languageCode - The language code
 * @param categoryName - Category name (phonology, morphology, etc.)
 * @param noteIndex - Index of the note in the array
 * @param translationType - Which version to verify ('human' or 'ai')
 * @param humanVerified - New verification status
 */
export async function verifyGrammarNote(
  languageCode: string,
  categoryName: string,
  noteIndex: number,
  humanVerified: boolean
): Promise<{ success: boolean }> {
  try {
    console.info(`[API] Verifying note ${noteIndex} in '${categoryName}' for ${languageCode}...`);
    const response = await makeRequest(
      `/grammar/${languageCode}/categories/${categoryName}/notes/${noteIndex}/verify`,
      {
        method: 'PATCH',
        body: JSON.stringify({ human_verified: humanVerified })
      }
    );
    const data = await response.json();
    console.info(`[API] Note verification updated: ${humanVerified}`);
    return { success: data.success };
  } catch (error) {
    console.error('[API] Failed to verify grammar note:', error);
    throw new Error(`Failed to verify note: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Verify a grammar example.
 *
 * @param languageCode - The language code
 * @param categoryName - Category name (phonology, morphology, etc.)
 * @param exampleIndex - Index of the example in the array
 * @param translationType - Which version to verify ('human' or 'ai')
 * @param humanVerified - New verification status
 */
export async function verifyGrammarExample(
  languageCode: string,
  categoryName: string,
  exampleIndex: number,
  humanVerified: boolean
): Promise<{ success: boolean }> {
  try {
    console.info(`[API] Verifying example ${exampleIndex} in '${categoryName}' for ${languageCode}...`);
    const response = await makeRequest(
      `/grammar/${languageCode}/categories/${categoryName}/examples/${exampleIndex}/verify`,
      {
        method: 'PATCH',
        body: JSON.stringify({ human_verified: humanVerified })
      }
    );
    const data = await response.json();
    console.info(`[API] Example verification updated: ${humanVerified}`);
    return { success: data.success };
  } catch (error) {
    console.error('[API] Failed to verify grammar example:', error);
    throw new Error(`Failed to verify example: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// ============================================================================
// Chat API
// ============================================================================

/**
 * SSE event from the chat stream endpoint.
 */
export interface ChatStreamEvent {
  type: 'text' | 'tool_call' | 'tool_result' | 'tool_approval' | 'error' | 'done' | 'thinking_delta' | 'context_usage' | 'batch_system_prompt';
  content?: string;
  name?: string;
  preview?: string;       // present when type === 'tool_result'
  call_id?: string;
  tool_name?: string;
  input?: Record<string, unknown>;
  input_tokens?: number;
  max_tokens?: number;
  messages_snapshot?: unknown[];  // injected by _messages_snapshot_gen in translate.py on tool_approval events
}

/**
 * Chat context describing what the user is currently viewing.
 */
interface ChatRequestContext {
  language_code?: string;
  book_code?: string;
  chapter?: number;
  view?: string;
}

/**
 * Stream a chat response from the backend via SSE.
 *
 * Uses fetch + ReadableStream (not EventSource) because we POST.
 * Yields parsed SSE events. Supports AbortController for cancellation.
 */
export async function* streamChat(
  messages: Array<{ role: string; content: string }>,
  context?: ChatRequestContext,
  signal?: AbortSignal,
  conversationId?: string,
  thinkingEnabled?: boolean,
  chatMode?: string | null,
): AsyncGenerator<ChatStreamEvent> {
  const fullUrl = `${API_BASE_URL}/chat/stream`;

  const body: Record<string, unknown> = { messages };
  if (context) body.context = context;
  if (conversationId) body.conversation_id = conversationId;
  if (thinkingEnabled) body.thinking_enabled = true;
  if (chatMode) body.chat_mode = chatMode;

  const response = await fetch(fullUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Chat stream failed: ${response.status} ${response.statusText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE lines: "data: {...}\n\n"
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';  // Keep incomplete line in buffer

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data: ')) continue;

        try {
          const event: ChatStreamEvent = JSON.parse(trimmed.slice(6));
          if (event.type === 'done') return;
          yield event;
        } catch {
          // Skip malformed lines
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Submit a tool approval/rejection and resume the chat stream via SSE.
 */
export async function* submitToolResult(
  conversationId: string,
  callId: string,
  decision: 'approve' | 'reject',
  modifiedInput?: Record<string, unknown>,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const fullUrl = `${API_BASE_URL}/chat/tool-result`;

  const body: Record<string, unknown> = {
    conversation_id: conversationId,
    call_id: callId,
    decision,
  };
  if (modifiedInput) body.modified_input = modifiedInput;

  const response = await fetch(fullUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Tool result stream failed: ${response.status} ${response.statusText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data: ')) continue;

        try {
          const event: ChatStreamEvent = JSON.parse(trimmed.slice(6));
          if (event.type === 'done') return;
          yield event;
        } catch {
          // Skip malformed lines
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// ============================================================================
// Chat Conversations API
// ============================================================================

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
  tool_calls?: string[];
  thinking_content?: string;
  timestamp: string;
}

interface ConversationDetail {
  id: string;
  title: string;
  messages: ConversationMessage[];
  created_at: string;
  updated_at: string;
}

export async function fetchConversations(): Promise<ConversationSummary[]> {
  const response = await makeRequest('/chat/conversations');
  return response.json();
}

export async function createConversation(title?: string): Promise<{ id: string }> {
  const response = await makeRequest('/chat/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  });
  return response.json();
}

export async function fetchConversation(id: string): Promise<ConversationDetail> {
  const response = await makeRequest(`/chat/conversations/${id}`);
  return response.json();
}

export async function deleteConversation(id: string): Promise<void> {
  await makeRequest(`/chat/conversations/${id}`, { method: 'DELETE' });
}


// ============================================================================
// Word Index API
// ============================================================================

export async function rebuildWordIndex(languageCode: string): Promise<{
  success: boolean;
  words_indexed: number;
  verses_processed: number;
  duration_ms: number;
}> {
  const response = await makeRequest('/word-index/rebuild', {
    method: 'POST',
    body: JSON.stringify({ language_code: languageCode }),
  });
  return response.json();
}

// ============================================================================
// Export USFM API
// ============================================================================

interface ExportUsfmRequest {
  language_code: string;
  output_dir: string;
}

interface ExportUsfmResponse {
  success: boolean;
  files_written: number;
  message: string;
}

export async function exportUsfm(request: ExportUsfmRequest): Promise<ExportUsfmResponse> {
  const response = await makeRequest('/export-usfm', {
    method: 'POST',
    body: JSON.stringify(request),
  });
  return response.json();
}

// ============================================================================
// Chat Config API
// ============================================================================

export interface ChatConfig {
  llm_provider: string;
  local_base_url: string;
  local_model: string;
  has_openrouter_key: boolean;
  openrouter_key_preview: string;
  openrouter_model: string;
  thinking_enabled: boolean;
}

export async function fetchChatConfig(): Promise<ChatConfig> {
  const response = await makeRequest('/chat/config');
  return response.json();
}

export interface QuickActionSkill {
  key: string;
  label: string;
  views: string[];
  prompt: string;
}

export async function fetchChatSkills(): Promise<QuickActionSkill[]> {
  const response = await makeRequest('/chat/skills');
  return response.json();
}

export async function saveChatConfig(updates: Record<string, string | boolean>): Promise<ChatConfig> {
  const response = await makeRequest('/chat/config', {
    method: 'POST',
    body: JSON.stringify(updates),
  });
  return response.json();
}

export async function testChatConnection(): Promise<{ success: boolean; error?: string }> {
  const response = await makeRequest('/chat/test-connection', { method: 'POST' });
  return response.json();
}

// ============================================================================
// Translation API
// ============================================================================

/**
 * A single verse in a batch translation request.
 */
export interface BatchVerseItem {
  verse_number: number;
  english_text: string;
}

/**
 * Private SSE reader shared by translation stream functions.
 * Parses "data: {...}\n\n" lines from a fetch Response body.
 * Yields events until type === 'done' or the stream ends.
 */
async function* readSseStream(response: Response): AsyncGenerator<ChatStreamEvent> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data: ')) continue;

        try {
          const event: ChatStreamEvent = JSON.parse(trimmed.slice(6));
          if (event.type === 'done') return;
          yield event;
        } catch {
          // Skip malformed lines
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Stream a single-verse translation via SSE.
 *
 * LLM gathers context then calls propose_verse_translation (write tool).
 * Yields a tool_approval event when the proposal is ready for user review.
 */
export async function* streamVerseTranslation(
  languageCode: string,
  bookCode: string,
  chapter: number,
  verse: number,
  englishText: string,
  languageName: string,
  bookName: string,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const url = `${API_BASE_URL}/verses/${languageCode}/${bookCode}/${chapter}/${verse}/translate-stream`;

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ english_text: englishText, language_name: languageName, book_name: bookName }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Translation stream failed: ${response.status} ${response.statusText}`);
  }

  yield* readSseStream(response);
}

/**
 * Start a multi-verse batch translation session via SSE.
 *
 * LLM receives all verses, gathers shared context, then proposes the first verse.
 * Emits a batch_system_prompt event first (frontend must capture and store it).
 * Pauses at tool_approval with messages_snapshot for the first verse proposal.
 */
export async function* streamBatchTranslation(
  languageCode: string,
  bookCode: string,
  chapter: number,
  verses: BatchVerseItem[],
  languageName: string,
  bookName: string,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const url = `${API_BASE_URL}/verses/${languageCode}/${bookCode}/${chapter}/translate-batch-stream`;

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ verses, language_name: languageName, book_name: bookName }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Batch translation stream failed: ${response.status} ${response.statusText}`);
  }

  yield* readSseStream(response);
}

/**
 * Resume a batch session after a verse proposal decision via SSE.
 *
 * Replaces the awaiting_approval placeholder in messages, optionally injects
 * translator feedback, then runs the LLM again for the next verse.
 * Pauses at tool_approval with messages_snapshot for the next verse proposal.
 *
 * Note: remainingVerses is frontend state — do NOT include in this call.
 */
export async function* streamBatchResume(
  languageCode: string,
  bookCode: string,
  chapter: number,
  messages: unknown[],
  callId: string,
  verseNumber: number,
  decision: 'approve' | 'reject',
  systemPrompt: string,
  systemPromptSig: string,
  feedback?: string,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const url = `${API_BASE_URL}/verses/${languageCode}/${bookCode}/${chapter}/translate-batch-resume`;

  const body: Record<string, unknown> = {
    messages,
    system_prompt: systemPrompt,
    system_prompt_sig: systemPromptSig,
    call_id: callId,
    verse_number: verseNumber,
    decision,
  };
  if (feedback) body.feedback = feedback;

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Batch resume stream failed: ${response.status} ${response.statusText}`);
  }

  yield* readSseStream(response);
}

// ============================================================================
// Memories API — Notes
// ============================================================================

/**
 * A single note in the language_notes collection.
 * All notes are trusted on write — no human_verified field.
 */
export interface LanguageNote {
  id: string;
  title: string;
  text: string;
  created_at: string;
  updated_at: string;
}

/** Response from GET /api/memories/{language}/notes */
interface LanguageNotesResponse {
  language_code: string;
  notes: LanguageNote[];
  count: number;
}

/** Response from note mutation endpoints (POST/PUT/DELETE) */
interface NoteActionResponse {
  success: boolean;
  note_id: string;
  language_code: string;
}

export async function fetchNotes(languageCode: string): Promise<LanguageNotesResponse> {
  const response = await makeRequest(`/memories/${languageCode}/notes`);
  return response.json();
}

export async function addNote(
  languageCode: string,
  title: string,
  text: string,
): Promise<NoteActionResponse> {
  const response = await makeRequest(`/memories/${languageCode}/notes`, {
    method: 'POST',
    body: JSON.stringify({ title, text }),
  });
  return response.json();
}

export async function updateNote(
  languageCode: string,
  noteId: string,
  title: string,
  text: string,
): Promise<NoteActionResponse> {
  const response = await makeRequest(`/memories/${languageCode}/notes/${noteId}`, {
    method: 'PUT',
    body: JSON.stringify({ title, text }),
  });
  return response.json();
}

export async function deleteNote(
  languageCode: string,
  noteId: string
): Promise<NoteActionResponse> {
  const response = await makeRequest(`/memories/${languageCode}/notes/${noteId}`, {
    method: 'DELETE',
  });
  return response.json();
}

// ============================================================================
// Memories API — Correction Log
// ============================================================================

export type CorrectionContentType = 'bible_verse' | 'dictionary_entry' | 'grammar_category';

/** A single correction log entry as returned by GET. */
export interface CorrectionLogEntry {
  id: string;
  content_type: CorrectionContentType;
  content_reference: Record<string, unknown>;
  original_text: string;
  what_was_wrong: string;
  correction: string;
  created_at: string;
}

/** Request body for POST /api/correction-log/{language} */
export interface AppendCorrectionLogRequest {
  content_type: CorrectionContentType;
  content_reference: Record<string, unknown>;
  original_text: string;
  what_was_wrong: string;
  correction: string;
}

/** Per-entry correction data for dictionary approval submissions */
export interface PerEntryCorrection {
  word: string;
  comment: string;
  originalText: string;    // full original entry: "word: definition (pos)"
  correctedText: string;   // full corrected entry: "word: definition (pos)"
}

/** Response from GET /api/correction-log/{language} */
interface CorrectionLogResponse {
  language_code: string;
  entries: CorrectionLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export async function appendCorrectionLog(
  languageCode: string,
  entry: AppendCorrectionLogRequest
): Promise<{ success: boolean; log_id: string; language_code: string }> {
  const response = await makeRequest(`/correction-log/${languageCode}`, {
    method: 'POST',
    body: JSON.stringify(entry),
  });
  return response.json();
}

export async function fetchCorrectionLog(
  languageCode: string,
  params?: { content_type?: CorrectionContentType; page?: number; page_size?: number }
): Promise<CorrectionLogResponse> {
  const query = new URLSearchParams();
  if (params?.content_type) query.set('content_type', params.content_type);
  if (params?.page !== undefined) query.set('page', String(params.page));
  if (params?.page_size !== undefined) query.set('page_size', String(params.page_size));
  const qs = query.toString();
  const response = await makeRequest(`/correction-log/${languageCode}${qs ? `?${qs}` : ''}`);
  return response.json();
}

export async function updateCorrectionLog(
  languageCode: string,
  logId: string,
  whatWasWrong: string
): Promise<{ success: boolean; log_id: string; language_code: string }> {
  const response = await makeRequest(`/correction-log/${languageCode}/${logId}`, {
    method: 'PUT',
    body: JSON.stringify({ what_was_wrong: whatWasWrong }),
  });
  return response.json();
}

// ============================================================================
// Database Backup API
// ============================================================================

interface BackupDatabaseResponse {
  success: boolean;
  backup_dir: string;
  message: string;
  duration_ms: number;
}

export async function backupDatabase(output_dir: string): Promise<BackupDatabaseResponse> {
  const response = await makeRequest('/backup-database', {
    method: 'POST',
    body: JSON.stringify({ output_dir }),
  });
  return response.json();
}