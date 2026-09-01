// BibleReader.tsx
/**
 * Bible Reader component for viewing and verifying translations.
 *
 * Provides a three-view navigation:
 * 1. Books - Grid of 66 Bible book cards
 * 2. Chapters - Grid of chapter number buttons
 * 3. Verses - Side-by-side English/translation with verification checkboxes
 *
 * AI generation, batch session, verse selection, and proposal state live in
 * useBatchTranslation. BibleReader owns navigation, data loading, and inline edit.
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box,
  Typography,
  IconButton,
  Container,
  Paper,
  Chip,
  Grid,
  Checkbox,
  CircularProgress,
  Divider,
  Button,
  TextField,
  InputAdornment,
} from '@mui/material';
import {
  ArrowBack,
  CheckCircle,
  CheckCircleOutline,
  Search,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import {
  fetchBibleBooks,
  fetchChapterVerses,
  updateVerseVerification,
  updateVerseText,
  searchBibleVerses,
  type BibleBookInfo,
  type VerseData,
  type VerseSearchResult,
} from '../renderer/api';
import { useChat } from '../renderer/contexts/ChatContext';
import { TOPBAR_HEIGHT } from '../renderer/constants';
import { filterVerses } from './searchFilters';
import { CopyIconButton } from './CopyIconButton';
import { useBatchTranslation } from './useBatchTranslation';
import { VerseTranslationCell } from './VerseTranslationCell';
import { VerseSelectionToolbar } from './VerseSelectionToolbar';

interface BibleReaderProps {
  languageCode: string;
  languageName: string;
  onBack: () => void;
}

type ViewState = 'books' | 'chapters' | 'verses';


export function BibleReader({ languageCode, languageName, onBack }: BibleReaderProps) {
  // Navigation state
  const [view, setView] = useState<ViewState>('books');
  const [selectedBook, setSelectedBook] = useState<BibleBookInfo | null>(null);
  const [selectedChapter, setSelectedChapter] = useState<number>(1);

  // Data state
  const [books, setBooks] = useState<BibleBookInfo[]>([]);
  const [verses, setVerses] = useState<VerseData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Verse edit state
  const [editingVerse, setEditingVerse] = useState<number | null>(null);
  const [editText, setEditText] = useState('');
  const [savingVerse, setSavingVerse] = useState(false);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<VerseSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  // Chat context
  const { setAppContext, openChat, pipeToChat, isStreaming,
          registerProposalHandler, unregisterProposalHandler,
          approveToolCall, rejectToolCall, injectContextNote } = useChat();

  // Debounced cross-book verse search — fires only in books view with a query
  useEffect(() => {
    if (view !== 'books' || !searchQuery.trim()) {
      setSearchResults([]);
      setSearchLoading(false);
      return;
    }
    setSearchLoading(true);
    const timer = setTimeout(async () => {
      try {
        const results = await searchBibleVerses(languageCode, searchQuery);
        setSearchResults(results);
      } catch {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [searchQuery, view, languageCode]);

  const filteredVerses = useMemo(() => {
    if (view !== 'verses') return verses;
    return filterVerses(verses, searchQuery);
  }, [verses, searchQuery, view]);

  // Report context to chat
  useEffect(() => {
    setAppContext({
      languageCode,
      bookCode: selectedBook?.book_code || null,
      chapter: view === 'verses' ? selectedChapter : null,
      view: 'bible_reader',
    });
  }, [languageCode, selectedBook, selectedChapter, view, setAppContext]);

  // Load books on mount
  useEffect(() => {
    loadBooks();
  }, [languageCode]);

  const loadBooks = async () => {
    setLoading(true);
    setError(null);
    try {
      const booksData = await fetchBibleBooks(languageCode);
      setBooks(booksData);
    } catch (err) {
      setError('Failed to load Bible books. Please check if the backend is running.');
      console.error('Failed to load books:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectBook = (book: BibleBookInfo) => {
    setSelectedBook(book);
    setSearchQuery('');
    setView('chapters');
  };

  const handleSelectChapter = async (chapter: number) => {
    if (!selectedBook) return;
    await loadChapter(selectedBook, chapter);
  };

  const handleVerseVerification = async (verseNum: number, verified: boolean) => {
    if (!selectedBook) return;

    try {
      await updateVerseVerification(
        languageCode,
        selectedBook.book_code,
        selectedChapter,
        verseNum,
        verified
      );

      // Update local state
      setVerses(prev =>
        prev.map(v =>
          v.verse === verseNum ? { ...v, human_verified: verified } : v
        )
      );
    } catch (err) {
      console.error('Failed to update verification:', err);
    }
  };

  const handleStartVerseEdit = (verse: VerseData) => {
    setEditingVerse(verse.verse);
    setEditText(verse.translated_text || '');
  };

  const handleCancelVerseEdit = () => {
    setEditingVerse(null);
    setEditText('');
  };

  /**
   * Save a verse translation. If textOverride is provided (from proposal accept/edit),
   * saves that text directly without touching the editText state.
   */
  const handleSaveVerseEdit = async (verseNum: number, textOverride?: string) => {
    if (!selectedBook) return;
    const textToSave = textOverride ?? editText;

    setSavingVerse(true);
    try {
      const result = await updateVerseText(
        languageCode,
        selectedBook.book_code,
        selectedChapter,
        verseNum,
        textToSave
      );

      // Update local state from server response (human_verified depends on whether text is empty)
      setVerses(prev =>
        prev.map(v =>
          v.verse === verseNum
            ? { ...v, translated_text: result.translated_text, human_verified: result.human_verified }
            : v
        )
      );

      // Only clear manual-edit UI state when this is NOT a proposal save
      if (textOverride === undefined) {
        setEditingVerse(null);
        setEditText('');
      }
    } catch (err) {
      console.error('Failed to update verse text:', err);
    } finally {
      setSavingVerse(false);
    }
  };

  // Stable callbacks passed to useBatchTranslation (defined after handleSaveVerseEdit)
  const handleSaveVerseEditStable = useCallback(
    (verseNum: number, text: string) => handleSaveVerseEdit(verseNum, text),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selectedBook, selectedChapter, languageCode]
  );
  const handleClearVerseEdit = useCallback((verseNum: number) => {
    if (editingVerse === verseNum) { setEditingVerse(null); setEditText(''); }
  }, [editingVerse]);

  // ---- useBatchTranslation hook ----
  const { generation, selection, proposal } = useBatchTranslation({
    languageCode,
    languageName,
    selectedBook,
    selectedChapter,
    filteredVerses,
    isStreaming,
    isVersesView: view === 'verses',
    pipeToChat,
    openChat,
    registerProposalHandler,
    unregisterProposalHandler,
    approveToolCall,
    rejectToolCall,
    onSaveVerse: handleSaveVerseEditStable,
    onClearVerseEdit: handleClearVerseEdit,
    onEditedProposal: (ref, _originalText, correctedText, feedbackText) => {
      const refStr = `${ref.book_code} ${ref.chapter}:${ref.verse}`;
      const note = feedbackText.trim()
        ? `[Correction note] ${refStr}: ${feedbackText}\nCorrected text: "${correctedText}"`
        : `[Correction note] ${refStr} corrected. Corrected text: "${correctedText}"`;
      injectContextNote(note);
    },
  });

  const loadChapter = async (book: BibleBookInfo, chapter: number) => {
    generation.clearAllGenStates();
    setSelectedChapter(chapter);
    setLoading(true);
    setError(null);
    try {
      const data = await fetchChapterVerses(languageCode, book.book_code, chapter);
      setVerses(data.verses);
      setSearchQuery('');
      setView('verses');
    } catch {
      setError(`Failed to load ${book.book_name} chapter ${chapter}.`);
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    setSearchQuery('');
    if (view === 'verses') {
      generation.clearAllGenStates();
      setView('chapters');
      setVerses([]);
    } else if (view === 'chapters') {
      setView('books');
      setSelectedBook(null);
    } else {
      onBack();
    }
  };

  const navigateToResult = async (result: VerseSearchResult) => {
    const book = books.find(b => b.book_code === result.book_code);
    if (!book) return;
    setSelectedBook(book);
    setSearchQuery('');
    await loadChapter(book, result.chapter);
  };

  // Generate chapter numbers array
  const getChapterNumbers = (): number[] => {
    if (!selectedBook) return [];
    return Array.from({ length: selectedBook.total_chapters }, (_, i) => i + 1);
  };

  // Get breadcrumb text
  const getBreadcrumb = (): string => {
    if (view === 'verses' && selectedBook) {
      return `${selectedBook.book_name} - Chapter ${selectedChapter}`;
    }
    if (view === 'chapters' && selectedBook) {
      return `${selectedBook.book_name} - Select Chapter`;
    }
    return 'Select Book';
  };

  // ============================================================================
  // Render helpers
  // ============================================================================

  // Render book selection grid (shown when no search query is active)
  const renderBookSelection = () => (
    <Grid container spacing={1.5}>
      {books.map((book) => (
        <Grid item xs={6} sm={4} md={3} lg={2} key={book.book_code}>
        <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.98 }}>
          <Paper
            elevation={2}
            sx={{
              p: 1.5,
              cursor: 'pointer',
              opacity: book.has_data ? 1 : 0.45,
              bgcolor: 'rgba(255,255,255,0.05)',
              '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' },
              borderLeft: book.metadata?.testament === 'old'
                ? '3px solid #8B7355'
                : '3px solid #5B8C5A'
            }}
            onClick={() => handleSelectBook(book)}
          >
            <Typography
              variant="body1"
              sx={{
                color: 'white',
                fontWeight: 500,
                fontStyle: book.has_data ? 'normal' : 'italic'
              }}
            >
              {book.book_name}
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)' }}>
              {book.has_data ? `${book.total_chapters} ch` : 'Not started'}
            </Typography>
          </Paper>
          </motion.div>
        </Grid>
      ))}
    </Grid>
  );

  // Render cross-book search results (shown when search query is active)
  const renderSearchResults = () => (
    <Box>
      {searchLoading && (
        <Box display="flex" justifyContent="center" py={4}>
          <CircularProgress size={32} color="primary" />
        </Box>
      )}
      {!searchLoading && searchResults.length === 0 && (
        <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
          No verses found matching &ldquo;{searchQuery}&rdquo;
        </Typography>
      )}
      {searchResults.map((result) => {
        const bookName = books.find(b => b.book_code === result.book_code)?.book_name ?? result.book_code;
        return (
          <Paper
            key={`${result.book_code}-${result.chapter}-${result.verse}`}
            onClick={() => navigateToResult(result)}
            sx={{ p: 2, mb: 1, cursor: 'pointer', bgcolor: 'rgba(255,255,255,0.03)', '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' } }}
          >
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)' }}>
              {bookName} {result.chapter}:{result.verse}
            </Typography>
            <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.85)', mt: 0.5 }}>
              {result.english_text}
            </Typography>
            {result.translated_text && (
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.6)', mt: 0.25 }}>
                {result.translated_text}
              </Typography>
            )}
          </Paper>
        );
      })}
    </Box>
  );

  // Render chapter selection grid
  const renderChapterSelection = () => (
    <Box>
      <Grid container spacing={1}>
        {getChapterNumbers().map((chapter) => (
          <Grid item xs={2} sm={1.5} md={1} key={chapter}>
            <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
              <Button
                variant="outlined"
                fullWidth
                onClick={() => handleSelectChapter(chapter)}
                sx={{
                  minWidth: 0,
                  py: 1.5,
                  color: 'white',
                  borderColor: 'rgba(255,255,255,0.3)',
                  '&:hover': {
                    borderColor: 'white',
                    bgcolor: 'rgba(255,255,255,0.1)'
                  }
                }}
              >
                {chapter}
              </Button>
            </motion.div>
          </Grid>
        ))}
      </Grid>
    </Box>
  );

  // Render verse display with side-by-side comparison
  const renderVerses = () => (
    <Box>
      {/* Verses */}
      {filteredVerses.map((verse) => {
        const genState = generation.verseGenStates.get(verse.verse);
        const isSelectableCheckbox = !generation.generatingBatch && !genState;

        return (
          <Paper
            key={verse.verse}
            elevation={1}
            sx={{
              p: 2,
              mb: 1,
              bgcolor: verse.human_verified
                ? 'rgba(76,175,80,0.15)'
                : genState?.status === 'proposal_ready'
                ? 'rgba(100,150,255,0.08)'
                : 'rgba(255,255,255,0.03)',
              transition: 'background-color 0.3s ease'
            }}
          >
            <Grid container spacing={2} alignItems="flex-start">
              {/* Selection checkbox */}
              <Grid item xs={0.5}>
                {isSelectableCheckbox && (
                  <Checkbox
                    size="small"
                    checked={selection.selectedVerses.has(verse.verse)}
                    onChange={(e) => selection.handleVerseSelection(verse.verse, e.target.checked)}
                    sx={{ p: 0, color: 'rgba(255,255,255,0.3)', '&.Mui-checked': { color: 'rgba(180,140,255,0.8)' } }}
                  />
                )}
              </Grid>

              {/* Verse number */}
              <Grid item xs={0.5}>
                <Typography
                  variant="body2"
                  sx={{ color: 'rgba(255,255,255,0.5)', fontWeight: 600 }}
                >
                  {verse.verse}
                </Typography>
              </Grid>

              {/* English text */}
              <Grid item xs={4.5}>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
                  <Typography variant="body1" sx={{ color: 'rgba(255,255,255,0.85)', lineHeight: 1.7, flexGrow: 1 }}>
                    {verse.english_text || <em style={{ opacity: 0.5 }}>(No English text)</em>}
                  </Typography>
                  {verse.english_text && <CopyIconButton text={verse.english_text} />}
                </Box>
              </Grid>

              {/* Translation cell */}
              <Grid item xs={5.5}>
                <VerseTranslationCell
                  verse={verse}
                  generation={generation}
                  proposal={proposal}
                  editingVerse={editingVerse}
                  editText={editText}
                  savingVerse={savingVerse}
                  onStartEdit={handleStartVerseEdit}
                  onCancelEdit={handleCancelVerseEdit}
                  onSaveEdit={handleSaveVerseEdit}
                  onEditTextChange={setEditText}
                />
              </Grid>

              {/* Verification checkbox */}
              <Grid item xs={1} sx={{ textAlign: 'center' }}>
                <Checkbox
                  checked={verse.human_verified}
                  onChange={(e) => handleVerseVerification(verse.verse, e.target.checked)}
                  disabled={!verse.translated_text}
                  icon={<CheckCircleOutline sx={{ color: 'rgba(255,255,255,0.3)' }} />}
                  checkedIcon={<CheckCircle sx={{ color: '#4CAF50' }} />}
                  sx={{ p: 0.5 }}
                />
              </Grid>
            </Grid>
          </Paper>
        );
      })}

      {filteredVerses.length === 0 && !loading && (
        <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
          {searchQuery.trim() && verses.length > 0
            ? `No verses match "${searchQuery}"`
            : 'No verses found for this chapter.'}
        </Typography>
      )}
    </Box>
  );

  return (
    <Box
      sx={{
        height: '100vh',
        overflow: 'hidden',
        background: 'linear-gradient(135deg, #1A1A1A, #2D2D2D)',
        pt: `${TOPBAR_HEIGHT + 8}px`,
        pb: 4,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Container maxWidth="xl" sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 3, flexShrink: 0 }}>
          <IconButton onClick={handleBack} sx={{ mr: 2, color: 'white' }}>
            <ArrowBack />
          </IconButton>
          <Typography variant="h4" component="h1" sx={{ color: 'white', flexGrow: 1 }}>
            {getBreadcrumb()}
          </Typography>
          <Chip
            label={languageName}
            sx={{ bgcolor: 'rgba(255,255,255,0.1)', color: 'white' }}
          />
        </Box>

        {/* Content */}
        {loading ? (
          <Box display="flex" justifyContent="center" py={8}>
            <CircularProgress color="primary" />
          </Box>
        ) : error ? (
          <Paper sx={{ p: 4, bgcolor: 'rgba(255,255,255,0.05)' }}>
            <Typography color="error" align="center">{error}</Typography>
            <Box display="flex" justifyContent="center" mt={2}>
              <Button variant="outlined" onClick={loadBooks}>
                Retry
              </Button>
            </Box>
          </Paper>
        ) : (
          <Paper elevation={3} sx={{ p: 3, pt: view === 'verses' ? 0 : 3, bgcolor: 'rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflowY: 'auto', overflowX: 'hidden' }}>
            {/* Books view: sticky search bar, scrolling content below */}
            {view === 'books' && (
              <>
                <TextField
                  fullWidth
                  placeholder="Search verse content..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  sx={{
                    mb: 2,
                    position: 'sticky',
                    top: 0,
                    zIndex: 10,
                    bgcolor: 'rgba(30,30,40,1)',
                    '& .MuiOutlinedInput-root': {
                      bgcolor: 'rgba(255,255,255,0.05)',
                      '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
                      '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.4)' },
                    },
                    '& .MuiInputBase-input': { color: 'white' }
                  }}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Search sx={{ color: 'rgba(255,255,255,0.5)' }} />
                      </InputAdornment>
                    )
                  }}
                />
                {!searchQuery.trim() && renderBookSelection()}
                {!!searchQuery.trim() && renderSearchResults()}
              </>
            )}

            {/* Chapters view: no search, no sticky needed */}
            {view === 'chapters' && renderChapterSelection()}

            {/* Verses view: unified sticky header + scrolling verse cards */}
            {view === 'verses' && (
              <>
                {/* Unified sticky block: search + toolbar + column headers */}
                <Box
                  sx={{
                    position: 'sticky',
                    top: 0,
                    zIndex: 20,
                    bgcolor: 'background.paper',
                    backgroundImage: 'inherit',
                    mx: -3,
                    px: 3,
                    pb: 1,
                  }}
                >
                  <TextField
                    fullWidth
                    placeholder="Search verses..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    sx={{
                      mb: 1,
                      '& .MuiOutlinedInput-root': {
                        bgcolor: 'rgba(255,255,255,0.05)',
                        '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
                        '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.4)' },
                      },
                      '& .MuiInputBase-input': { color: 'white' }
                    }}
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <Search sx={{ color: 'rgba(255,255,255,0.5)' }} />
                        </InputAdornment>
                      )
                    }}
                  />

                  {(selection.selectedVerses.size > 0 || generation.generatingBatch) && (
                    <VerseSelectionToolbar
                      selectedCount={selection.selectedVerses.size}
                      generatingBatch={generation.generatingBatch}
                      onGenerate={generation.handleGenerateBatch}
                      onSelectAll={selection.handleSelectAll}
                      onSelectUnverified={selection.handleSelectAllUnverified}
                      onClearSelection={selection.handleClearSelection}
                      onAbort={generation.handleAbortBatch}
                    />
                  )}

                </Box>

                <Grid container spacing={2} sx={{ mb: 1, px: 2 }}>
                  <Grid item xs={0.5}>
                    {/* checkbox column — no header label */}
                  </Grid>
                  <Grid item xs={0.5}>
                    <Typography variant="subtitle2" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                      #
                    </Typography>
                  </Grid>
                  <Grid item xs={4.5}>
                    <Typography variant="subtitle2" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                      English (Base)
                    </Typography>
                  </Grid>
                  <Grid item xs={5.5}>
                    <Typography variant="subtitle2" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                      {languageName} Translation
                    </Typography>
                  </Grid>
                  <Grid item xs={1}>
                    <Typography variant="subtitle2" sx={{ color: 'rgba(255,255,255,0.7)', textAlign: 'center' }}>
                      Verified
                    </Typography>
                  </Grid>
                </Grid>
                <Divider sx={{ bgcolor: 'rgba(255,255,255,0.2)', mb: 1 }} />

                {renderVerses()}
              </>
            )}
          </Paper>
        )}
      </Container>

    </Box>
  );
}
