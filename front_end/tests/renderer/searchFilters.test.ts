/**
 * Tests for search filter functions used by BibleReader and GrammarViewer.
 *
 * Three critical tests targeting real failure modes identified during design.
 * See: __plans__/search-bible-grammar.md § 4. Critical Tests
 */

import { describe, it, expect } from 'vitest';
import { filterVerses, filterBooks, filterSubcategories, filterCategoryByContent } from '../../src/components/searchFilters';
import type { VerseData, BibleBookInfo, SubcategoryData, MergedGrammarCategory } from '../../src/renderer/api';

// --- Test 1: Verse filter handles null translated_text without throwing ---

describe('filterVerses', () => {
  const verses: VerseData[] = [
    { verse: 1, english_text: 'In the beginning', translated_text: 'Na vunaghini', human_verified: false },
    { verse: 2, english_text: 'The earth was formless', translated_text: null, human_verified: false },
    { verse: 3, english_text: 'And God said let there be light', translated_text: '', human_verified: false },
  ];

  it('matches verse 2 via english_text even though translated_text is null', () => {
    const result = filterVerses(verses, 'formless');
    expect(result).toHaveLength(1);
    expect(result[0].verse).toBe(2);
  });

  it('does not throw TypeError when translated_text is null', () => {
    expect(() => filterVerses(verses, 'formless')).not.toThrow();
  });

  it('matches verse 3 via english_text when translated_text is empty string', () => {
    const result = filterVerses(verses, 'light');
    expect(result).toHaveLength(1);
    expect(result[0].verse).toBe(3);
  });

  it('returns all verses when query is empty', () => {
    expect(filterVerses(verses, '')).toHaveLength(3);
    expect(filterVerses(verses, '   ')).toHaveLength(3);
  });
});

// --- Test 2: Grammar filter preserves originalIndex for verify handler ---

describe('filterSubcategories', () => {
  const subcategories: SubcategoryData[] = [
    { name: 'Vowels', content: 'Five vowel system', examples: [] },       // index 0
    { name: 'Consonants', content: 'Fifteen consonants', examples: [] },  // index 1
    { name: 'Tone', content: 'No lexical tone', examples: [] },           // index 2
  ];

  it('returns only the matching subcategory', () => {
    const filtered = filterSubcategories(subcategories, 'consonant');
    expect(filtered).toHaveLength(1);
    expect(filtered[0].item.name).toBe('Consonants');
  });

  it('preserves originalIndex from source array (NOT the filtered position)', () => {
    const filtered = filterSubcategories(subcategories, 'consonant');
    // Consonants is at source index 1, not 0
    expect(filtered[0].originalIndex).toBe(1);
  });

  it('returns all items with their original indices when query is empty', () => {
    const filtered = filterSubcategories(subcategories, '');
    expect(filtered).toHaveLength(3);
    expect(filtered[0].originalIndex).toBe(0);
    expect(filtered[1].originalIndex).toBe(1);
    expect(filtered[2].originalIndex).toBe(2);
  });
});

// --- Test 3: Book filter matches book_name, not book_code ---

describe('filterBooks', () => {
  const books: BibleBookInfo[] = [
    { book_name: 'Genesis', book_code: 'genesis', total_chapters: 50, total_verses: 1533, has_data: true },
    { book_name: '1 Chronicles', book_code: '1_chronicles', total_chapters: 29, total_verses: 942, has_data: true },
    { book_name: 'Revelation', book_code: 'revelation', total_chapters: 22, total_verses: 404, has_data: true },
  ];

  it('"gene" matches Genesis by display name', () => {
    const result = filterBooks(books, 'gene');
    expect(result).toHaveLength(1);
    expect(result[0].book_name).toBe('Genesis');
  });

  it('"chron" matches 1 Chronicles by display name', () => {
    expect(filterBooks(books, 'chron')).toHaveLength(1);
  });

  it('"1_chr" matches nothing — book_code is not searched', () => {
    expect(filterBooks(books, '1_chr')).toHaveLength(0);
  });

  it('returns all books when query is empty', () => {
    expect(filterBooks(books, '')).toHaveLength(3);
  });
});

// --- Test 4: filterCategoryByContent ---

describe('filterCategoryByContent', () => {
  const phonologyCategory: MergedGrammarCategory = {
    name: 'phonology',
    description: 'Sound system',
    subcategories: [{ name: 'Vowels', content: 'Five vowel system', examples: [] }],
    notes: ['Stress falls on the first syllable'],
    examples: [],
    human_verified: false,
  };

  const syntaxCategory: MergedGrammarCategory = {
    name: 'syntax',
    description: 'Sentence structure',
    subcategories: ['Subject-verb-object order'],
    notes: [],
    examples: [{ source_text: 'Ana kata', english: 'He walks', analysis: 'SVO pattern' }],
    human_verified: false,
  };

  const emptyCategory: MergedGrammarCategory = {
    name: 'morphology',
    description: '',
    subcategories: [],
    notes: [],
    examples: [],
    human_verified: false,
  };

  const allCategories = [phonologyCategory, syntaxCategory, emptyCategory];

  it('returns category whose subcategory content matches the query', () => {
    const result = filterCategoryByContent(allCategories, 'vowel');
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('phonology');
  });

  it('returns empty array when no category has matching content', () => {
    const result = filterCategoryByContent(allCategories, 'xyznonexistent');
    expect(result).toHaveLength(0);
  });

  it('returns all categories when query is empty', () => {
    expect(filterCategoryByContent(allCategories, '')).toHaveLength(3);
    expect(filterCategoryByContent(allCategories, '   ')).toHaveLength(3);
  });

  it('matches content in examples (analysis field)', () => {
    // 'svo' is in syntax's example analysis
    const result = filterCategoryByContent(allCategories, 'svo');
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('syntax');
  });
});
