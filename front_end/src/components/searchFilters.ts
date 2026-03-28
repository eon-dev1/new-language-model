/**
 * Pure filter functions for client-side search in BibleReader and GrammarViewer.
 *
 * Extracted as standalone functions so they can be:
 * - Tested independently without rendering components
 * - Reused if other components need similar filtering
 *
 * All functions are safe against null/undefined values.
 */

import {
  BibleBookInfo,
  VerseData,
  SubcategoryItem,
  SubcategoryData,
  NoteItem,
  NoteData,
  ExampleItem,
  ExampleData,
  MergedGrammarCategory
} from '../renderer/api';

// --- IndexedItem wrapper (preserves source array position through filtering) ---

export interface IndexedItem<T> { item: T; originalIndex: number; }

// --- Type Guards (operate on API types, belong alongside filter logic) ---

export function isSubcategoryData(item: SubcategoryItem): item is SubcategoryData {
  return typeof item === 'object' && item !== null && 'name' in item;
}

export function isExampleData(item: ExampleItem): item is ExampleData {
  return typeof item === 'object' && item !== null && ('source_text' in item || 'bughotu' in item);
}

export function isNoteData(item: NoteItem): item is NoteData {
  return typeof item === 'object' && item !== null && 'text' in item;
}

// --- Helpers ---

export function getNoteText(item: NoteItem): string {
  return isNoteData(item) ? item.text : String(item);
}

export function getSubcategoryLabel(item: SubcategoryItem): string {
  return isSubcategoryData(item)
    ? item.name.replace(/_/g, ' ')
    : String(item).replace(/_/g, ' ');
}

export function getExampleSourceText(item: ExampleData): string {
  return item.source_text || item.bughotu || '';
}

// --- BibleReader filter functions ---

/** Filter book list by user-facing book_name only (not book_code). */
export function filterBooks(books: BibleBookInfo[], query: string): BibleBookInfo[] {
  if (!query.trim()) return books;
  const q = query.toLowerCase();
  return books.filter(b => b.book_name.toLowerCase().includes(q));
}

/**
 * Filter verses by english_text or translated_text.
 * Safe against null translated_text (common for untranslated verses).
 */
export function filterVerses(verses: VerseData[], query: string): VerseData[] {
  if (!query.trim()) return verses;
  const q = query.toLowerCase();
  return verses.filter(v =>
    (v.english_text?.toLowerCase().includes(q)) ||
    (v.translated_text?.toLowerCase().includes(q))
  );
}

// --- GrammarViewer filter functions (return IndexedItem[] to preserve source position) ---

export function filterSubcategories(
  subcategories: SubcategoryItem[],
  query: string
): IndexedItem<SubcategoryItem>[] {
  const all = subcategories.map((item, i) => ({ item, originalIndex: i }));
  if (!query.trim()) return all;
  const q = query.toLowerCase();
  return all.filter(({ item: sub }) => {
    if (isSubcategoryData(sub)) {
      return sub.name.toLowerCase().includes(q) ||
        sub.content.toLowerCase().includes(q) ||
        sub.examples.some(ex => ex.toLowerCase().includes(q));
    }
    return String(sub).toLowerCase().includes(q);
  });
}

export function filterNotes(notes: NoteItem[], query: string): IndexedItem<NoteItem>[] {
  const all = notes.map((item, i) => ({ item, originalIndex: i }));
  if (!query.trim()) return all;
  const q = query.toLowerCase();
  return all.filter(({ item: note }) => getNoteText(note).toLowerCase().includes(q));
}

export function filterExamples(examples: ExampleItem[], query: string): IndexedItem<ExampleItem>[] {
  const all = examples.map((item, i) => ({ item, originalIndex: i }));
  if (!query.trim()) return all;
  const q = query.toLowerCase();
  return all.filter(({ item: ex }) => {
    if (isExampleData(ex)) {
      return getExampleSourceText(ex).toLowerCase().includes(q) ||
        ex.english.toLowerCase().includes(q) ||
        (ex.analysis?.toLowerCase().includes(q) ?? false);
    }
    return String(ex).toLowerCase().includes(q);
  });
}

// --- Top-level grammar category filter ---

/**
 * Filter the 5 grammar category cards by matching against all content
 * in both human and AI versions (name, subcategories, notes, examples).
 * Used by GrammarViewer's category grid search.
 */
export function filterCategoryByContent(
  categories: MergedGrammarCategory[],
  query: string
): MergedGrammarCategory[] {
  if (!query.trim()) return categories;
  const q = query.toLowerCase();
  return categories.filter(category => {
    if (category.name.toLowerCase().includes(q)) return true;
    for (const sub of category.subcategories || []) {
      if (isSubcategoryData(sub)) {
        if (sub.name.toLowerCase().includes(q) ||
            sub.content.toLowerCase().includes(q) ||
            sub.examples.some(ex => ex.toLowerCase().includes(q))) return true;
      } else if (String(sub).toLowerCase().includes(q)) return true;
    }
    for (const note of category.notes || []) {
      if (getNoteText(note).toLowerCase().includes(q)) return true;
    }
    for (const ex of category.examples || []) {
      if (isExampleData(ex)) {
        if (getExampleSourceText(ex).toLowerCase().includes(q) ||
            ex.english.toLowerCase().includes(q) ||
            (ex.analysis?.toLowerCase().includes(q) ?? false)) return true;
      } else if (String(ex).toLowerCase().includes(q)) return true;
    }
    return false;
  });
}
