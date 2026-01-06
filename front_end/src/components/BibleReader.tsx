// BibleReader.tsx
/**
 * Bible Reader component for viewing and verifying translations.
 *
 * Provides a three-view navigation:
 * 1. Books - Grid of 66 Bible book cards
 * 2. Chapters - Grid of chapter number buttons
 * 3. Verses - Side-by-side English/translation with verification checkboxes
 */

import React, { useState, useEffect } from 'react';
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
  Button
} from '@mui/material';
import { ArrowBack, CheckCircle, CheckCircleOutline } from '@mui/icons-material';
import { motion } from 'framer-motion';
import {
  fetchBibleBooks,
  fetchChapterVerses,
  updateVerseVerification,
  BibleBookInfo,
  VerseData
} from '../renderer/api';

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
    setView('chapters');
  };

  const handleSelectChapter = async (chapter: number) => {
    if (!selectedBook) return;

    setSelectedChapter(chapter);
    setLoading(true);
    setError(null);

    try {
      const chapterData = await fetchChapterVerses(
        languageCode,
        selectedBook.book_code,
        chapter
      );
      setVerses(chapterData.verses);
      setView('verses');
    } catch (err) {
      setError(`Failed to load verses for chapter ${chapter}.`);
      console.error('Failed to load verses:', err);
    } finally {
      setLoading(false);
    }
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

  const handleBack = () => {
    if (view === 'verses') {
      setView('chapters');
      setVerses([]);
    } else if (view === 'chapters') {
      setView('books');
      setSelectedBook(null);
    } else {
      onBack();
    }
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

  // Render book selection grid
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
                bgcolor: 'rgba(255,255,255,0.05)',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' },
                borderLeft: book.metadata?.testament === 'old'
                  ? '3px solid #8B7355'
                  : '3px solid #5B8C5A'
              }}
              onClick={() => handleSelectBook(book)}
            >
              <Typography variant="body1" sx={{ color: 'white', fontWeight: 500 }}>
                {book.book_name}
              </Typography>
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)' }}>
                {book.total_chapters} ch
              </Typography>
            </Paper>
          </motion.div>
        </Grid>
      ))}
    </Grid>
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
      {/* Header row */}
      <Grid container spacing={2} sx={{ mb: 2, px: 2 }}>
        <Grid item xs={0.5}>
          <Typography variant="subtitle2" sx={{ color: 'rgba(255,255,255,0.7)' }}>
            #
          </Typography>
        </Grid>
        <Grid item xs={5}>
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

      <Divider sx={{ bgcolor: 'rgba(255,255,255,0.2)', mb: 2 }} />

      {/* Verses */}
      {verses.map((verse) => (
        <Paper
          key={verse.verse}
          elevation={1}
          sx={{
            p: 2,
            mb: 1,
            bgcolor: verse.human_verified
              ? 'rgba(76,175,80,0.15)'
              : 'rgba(255,255,255,0.03)',
            transition: 'background-color 0.3s ease'
          }}
        >
          <Grid container spacing={2} alignItems="flex-start">
            <Grid item xs={0.5}>
              <Typography
                variant="body2"
                sx={{ color: 'rgba(255,255,255,0.5)', fontWeight: 600 }}
              >
                {verse.verse}
              </Typography>
            </Grid>
            <Grid item xs={5}>
              <Typography variant="body1" sx={{ color: 'rgba(255,255,255,0.85)', lineHeight: 1.7 }}>
                {verse.english_text || <em style={{ opacity: 0.5 }}>(No English text)</em>}
              </Typography>
            </Grid>
            <Grid item xs={5.5}>
              <Typography variant="body1" sx={{ color: 'white', lineHeight: 1.7 }}>
                {verse.translated_text || <em style={{ opacity: 0.5 }}>(No translation)</em>}
              </Typography>
            </Grid>
            <Grid item xs={1} sx={{ textAlign: 'center' }}>
              <Checkbox
                checked={verse.human_verified}
                onChange={(e) => handleVerseVerification(verse.verse, e.target.checked)}
                icon={<CheckCircleOutline sx={{ color: 'rgba(255,255,255,0.3)' }} />}
                checkedIcon={<CheckCircle sx={{ color: '#4CAF50' }} />}
                sx={{ p: 0.5 }}
              />
            </Grid>
          </Grid>
        </Paper>
      ))}

      {verses.length === 0 && !loading && (
        <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
          No verses found for this chapter.
        </Typography>
      )}
    </Box>
  );

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #1A1A1A, #2D2D2D)',
        pt: 7,  // 56px to clear fixed TopBar (48px)
        pb: 4,
      }}
    >
      <Container maxWidth="xl">
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
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
          <Paper elevation={3} sx={{ p: 3, bgcolor: 'rgba(255,255,255,0.05)' }}>
            {view === 'books' && renderBookSelection()}
            {view === 'chapters' && renderChapterSelection()}
            {view === 'verses' && renderVerses()}
          </Paper>
        )}
      </Container>
    </Box>
  );
}
