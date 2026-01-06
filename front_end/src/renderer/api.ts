// api.ts

/**
 * API service module for communication with the FastAPI backend.
 *
 * This module provides a simple HTTP layer for making requests to the backend.
 * Authentication has been disabled for local development - the server binds
 * to localhost only and MongoDB provides its own authentication.
 */

const API_BASE_URL: string | undefined = import.meta.env.VITE_API_BASE_URL;

if (!API_BASE_URL) {
  console.error('[API] VITE_API_BASE_URL is not defined. Please define it in your .env file.');
  throw new Error('VITE_API_BASE_URL is not defined.');
}

/**
 * Makes a request to the API with error handling.
 *
 * @param {string} endpoint - The API endpoint (relative to base URL)
 * @param {RequestInit} options - Fetch options (method, body, etc.)
 * @returns {Promise<Response>} The fetch response
 * @throws {Error} If the request fails
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
      console.error(`[API] Request failed: ${response.status} ${response.statusText}`);
      throw new Error(`HTTP error! status: ${response.status} - ${response.statusText}`);
    }

    console.debug(`[API] Request successful: ${endpoint}`);
    return response;

  } catch (error) {
    console.error(`[API] Request to ${endpoint} failed:`, error);
    throw error;
  }
}

/**
 * Test API connectivity.
 *
 * @returns {Promise<boolean>} True if connection is successful
 */
export async function testApiConnection(): Promise<boolean> {
  try {
    console.info('[API] Testing connection...');
    await makeRequest('/check-connection');
    console.info('[API] Connection test successful');
    return true;
  } catch (error) {
    console.warn('[API] Connection test failed:', error);
    return false;
  }
}

/**
 * Language data returned from /api/languages endpoint.
 */
export interface Language {
  language_code: string;
  language_name: string;
  total_verses: number;
  verified_count: number;
  verification_progress: number;  // 0-100 percentage
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
export interface ImportBibleRequest {
  language_code: string;
  language_name: string;
  usfm_directory: string;
  translation_type: 'human' | 'ai';
}

/**
 * Import Bible response from backend.
 */
export interface ImportBibleResponse {
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

/**
 * Import HTML Bible request payload.
 */
export interface ImportHtmlBibleRequest {
  language_code: string;
  language_name: string;
  html_directory: string;
  translation_type: 'human' | 'ai';
}

/**
 * Import HTML Bible files from a directory.
 *
 * @param request - Import configuration
 * @returns Import result with verse counts and status
 * @throws Error if import fails
 */
export async function importHtmlBible(request: ImportHtmlBibleRequest): Promise<ImportBibleResponse> {
  try {
    console.info('[API] Starting HTML Bible import...');
    const response = await makeRequest('/import-html-bible', {
      method: 'POST',
      body: JSON.stringify(request)
    });

    const data = await response.json();
    console.info(`[API] HTML Import complete: ${data.message}`);
    return data as ImportBibleResponse;

  } catch (error) {
    console.error('[API] HTML Bible import failed:', error);
    throw new Error(`HTML Bible import failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
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
  translated_text: string;
  human_verified: boolean;
}

/**
 * Response containing all verses for a chapter.
 */
export interface ChapterResponse {
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
  translation_type: string;
  total_chapters: number;
  total_verses: number;
  translation_status?: string;
  metadata?: {
    testament: string;
    canonical_order: number;
  };
}

/**
 * Response from /api/bible-books endpoint.
 */
export interface BibleBooksResponse {
  language: string;
  books: BibleBookInfo[];
  count: number;
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

// ============================================================================
// Dictionary API
// ============================================================================

/**
 * Single version (human or AI) of a dictionary entry.
 */
export interface DictionaryEntryVersion {
  definition: string;
  part_of_speech?: string;
  examples: string[];
  human_verified: boolean;
  created_at?: string;
  updated_at?: string;
}

/**
 * Merged dictionary entry with optional human and AI versions.
 */
export interface MergedDictionaryEntry {
  word: string;
  human?: DictionaryEntryVersion;
  ai?: DictionaryEntryVersion;
}

/**
 * Response from /api/dictionary/{language}/entries endpoint.
 */
export interface DictionaryEntriesResponse {
  language_code: string;
  entries: MergedDictionaryEntry[];
  count: number;
}

/**
 * Request to create or update a dictionary entry.
 */
export interface SaveDictionaryEntryRequest {
  word: string;
  definition: string;
  part_of_speech?: string;
  examples?: string[];
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
  try {
    console.info(`[API] Saving dictionary entry '${entry.word}' for ${languageCode}...`);
    const response = await makeRequest(`/dictionary/${languageCode}/entries`, {
      method: 'POST',
      body: JSON.stringify(entry)
    });
    const data = await response.json();
    console.info(`[API] Dictionary entry ${data.action}: ${entry.word}`);
    return data;
  } catch (error) {
    console.error('[API] Failed to save dictionary entry:', error);
    throw new Error(`Failed to save dictionary entry: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Update verification status for a dictionary entry.
 *
 * @param languageCode - The language code
 * @param word - The word to verify
 * @param translationType - Which version to verify ('human' or 'ai')
 * @param humanVerified - New verification status
 */
export async function verifyDictionaryEntry(
  languageCode: string,
  word: string,
  translationType: 'human' | 'ai',
  humanVerified: boolean
): Promise<{ success: boolean }> {
  try {
    console.info(`[API] Verifying dictionary entry '${word}' (${translationType}) for ${languageCode}...`);
    const response = await makeRequest(`/dictionary/${languageCode}/entries/${encodeURIComponent(word)}/verify`, {
      method: 'PATCH',
      body: JSON.stringify({ translation_type: translationType, human_verified: humanVerified })
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
}

/**
 * Rich example data structure (AI-generated).
 */
export interface ExampleData {
  bughotu: string;
  english: string;
  analysis: string;
}

/** Subcategory can be a simple string (human) or rich object (AI). */
export type SubcategoryItem = string | SubcategoryData;

/** Example can be a simple string (human) or rich object (AI). */
export type ExampleItem = string | ExampleData;

/**
 * Single version (human or AI) of a grammar category.
 */
export interface GrammarCategoryVersion {
  description: string;
  subcategories: SubcategoryItem[];
  notes: string[];
  examples: ExampleItem[];
  ai_confidence?: number;
  human_verified: boolean;
  updated_at?: string;
}

/**
 * Merged grammar category with optional human and AI versions.
 */
export interface MergedGrammarCategory {
  name: string;
  human?: GrammarCategoryVersion;
  ai?: GrammarCategoryVersion;
}

/**
 * Response from /api/grammar/{language}/categories endpoint.
 */
export interface GrammarCategoriesResponse {
  language_code: string;
  categories: MergedGrammarCategory[];
  count: number;
}

/**
 * Request to update grammar category content.
 */
export interface SaveGrammarCategoryRequest {
  notes: string[];
  examples: string[];
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
  translationType: 'human' | 'ai',
  humanVerified: boolean
): Promise<{ success: boolean }> {
  try {
    console.info(`[API] Verifying grammar category '${categoryName}' (${translationType}) for ${languageCode}...`);
    const response = await makeRequest(`/grammar/${languageCode}/categories/${categoryName}/verify`, {
      method: 'PATCH',
      body: JSON.stringify({ translation_type: translationType, human_verified: humanVerified })
    });
    const data = await response.json();
    console.info(`[API] Grammar category verification updated: ${humanVerified}`);
    return { success: data.success };
  } catch (error) {
    console.error('[API] Failed to verify grammar category:', error);
    throw new Error(`Failed to verify grammar category: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}