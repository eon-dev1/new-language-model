// types/LanguageProject.ts
// Type definitions for the Language Project framework

export interface Language {
  id: string;
  name: string;
  code?: string; // ISO language code if available
}

export interface BibleResource {
  id: string;
  title: string;
  version: string;
  books: BibleBook[];
  available: boolean;
}

export interface BibleBook {
  id: string;
  name: string;
  chapters: BibleChapter[];
}

export interface BibleChapter {
  number: number;
  verses: BibleVerse[];
}

export interface BibleVerse {
  number: number;
  text: string;
}

// --- Dictionary Types (Unified View) ---

export interface DictionaryEntryVersion {
  definition: string;
  partOfSpeech?: string;
  examples: string[];
  humanVerified: boolean;
  createdAt?: string;
  updatedAt?: string;
}

export interface MergedDictionaryEntry {
  word: string;
  definition?: string;
  partOfSpeech?: string;
  examples?: string[];
  humanVerified?: boolean;
  createdAt?: string;
  updatedAt?: string;
}

export interface DictionaryEntriesResponse {
  languageCode: string;
  entries: MergedDictionaryEntry[];
  count: number;
}

// --- Grammar Types (Unified View) ---

/** Rich subcategory data structure (AI-generated). */
export interface SubcategoryData {
  name: string;
  content: string;
  examples: string[];
}

/** Rich example data structure (AI-generated). */
export interface ExampleData {
  bughotu: string;
  english: string;
  analysis: string;
}

/** Subcategory can be a simple string (human) or rich object (AI). */
export type SubcategoryItem = string | SubcategoryData;

/** Example can be a simple string (human) or rich object (AI). */
export type ExampleItem = string | ExampleData;

export interface GrammarCategoryVersion {
  description: string;
  subcategories: SubcategoryItem[];
  notes: string[];
  examples: ExampleItem[];
  aiConfidence?: number;
  humanVerified: boolean;
  updatedAt?: string;
}

export interface MergedGrammarCategory {
  name: string;
  description?: string;
  subcategories?: SubcategoryItem[];
  notes?: string[];
  examples?: ExampleItem[];
  humanVerified?: boolean;
  updatedAt?: string;
}

export interface GrammarCategoriesResponse {
  languageCode: string;
  categories: MergedGrammarCategory[];
  count: number;
}

// --- Legacy Types (kept for compatibility) ---

export interface Dictionary {
  id: string;
  title: string;
  type: 'human' | 'nlm-generated';
  entries: DictionaryEntry[];
  available: boolean;
}

export interface DictionaryEntry {
  id: string;
  word: string;
  definition: string;
  examples?: string[];
  partOfSpeech?: string;
}

export interface Grammar {
  id: string;
  title: string;
  type: 'human' | 'nlm-generated';
  sections: GrammarSection[];
  available: boolean;
}

export interface GrammarSection {
  id: string;
  title: string;
  content: string;
  examples?: string[];
}

// --- Project Resources ---

export interface ProjectResources {
  bible: BibleResource | null;
  dictionary: { available: boolean } | null;
  grammar: { available: boolean } | null;
}

export interface LanguageProject {
  language: Language;
  resources: ProjectResources;
  progress: ProjectProgress;
}

export interface ProjectProgress {
  oldTestamentCompletion: number;  // 0-100
  newTestamentCompletion: number;  // 0-100
  overallCompletion: number;       // 0-100
}

// Simplified resource type (unified views)
export type ResourceType = 'bible' | 'dictionary' | 'memories';

export interface NavigationState {
  currentView: 'home' | 'project';
  selectedProject: LanguageProject | null;
  selectedResource: ResourceType | null;
}
