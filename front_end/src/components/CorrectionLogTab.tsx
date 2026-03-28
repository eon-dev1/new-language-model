// CorrectionLogTab.tsx
// Correction log viewer. Filter chip row (All / Bible / Dictionary / Grammar).
// Paginated list showing: type icon, reference, what was wrong, correction, date.
// Inline edit for what_was_wrong only — all other fields read-only.
// After a successful PUT, mutate the entry in local state by id — do NOT refetch.

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  Button,
  TextField,
  CircularProgress,
  Container,
  Pagination,
  Divider
} from '@mui/material';
import { MenuBook, Book, School, Edit, Save, Cancel } from '@mui/icons-material';
import {
  fetchCorrectionLog,
  updateCorrectionLog,
  CorrectionLogEntry,
  CorrectionContentType
} from '../renderer/api';

interface CorrectionLogTabProps {
  languageCode: string;
}

type FilterType = 'all' | CorrectionContentType;

const PAGE_SIZE = 20;

function formatReference(entry: CorrectionLogEntry): string {
  const ref = entry.content_reference;
  if (entry.content_type === 'bible_verse') {
    const book = String(ref.book_code ?? '').replace(/_/g, ' ');
    return `${book} ${ref.chapter}:${ref.verse}`;
  }
  if (entry.content_type === 'dictionary_entry') {
    return String(ref.word ?? '');
  }
  if (entry.content_type === 'grammar_category') {
    return String(ref.category ?? '');
  }
  return '';
}

function TypeIcon({ type }: { type: CorrectionContentType }) {
  if (type === 'bible_verse') return <MenuBook sx={{ fontSize: 18, color: '#4CAF50' }} />;
  if (type === 'dictionary_entry') return <Book sx={{ fontSize: 18, color: '#2196F3' }} />;
  return <School sx={{ fontSize: 18, color: '#9C27B0' }} />;
}

const FILTER_OPTIONS: { value: FilterType; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'bible_verse', label: 'Bible' },
  { value: 'dictionary_entry', label: 'Dictionary' },
  { value: 'grammar_category', label: 'Grammar' },
];

export function CorrectionLogTab({ languageCode }: CorrectionLogTabProps) {
  const [entries, setEntries] = useState<CorrectionLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<FilterType>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Inline edit state for what_was_wrong
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [editSaving, setEditSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchCorrectionLog(languageCode, {
      content_type: filter === 'all' ? undefined : filter,
      page,
      page_size: PAGE_SIZE,
    })
      .then(data => {
        if (!cancelled) {
          setEntries(data.entries);
          setTotal(data.total);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Failed to load correction log.');
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [languageCode, filter, page]);

  const handleFilterChange = (newFilter: FilterType) => {
    setFilter(newFilter);
    setPage(1);
  };

  const handleStartEdit = (entry: CorrectionLogEntry) => {
    setEditingId(entry.id);
    setEditText(entry.what_was_wrong);
  };

  const handleSaveEdit = async (entryId: string) => {
    setEditSaving(true);
    try {
      await updateCorrectionLog(languageCode, entryId, editText.trim());
      // Mutate local state by ID — do not refetch (preserves pagination position)
      setEntries(prev =>
        prev.map(e => e.id === entryId ? { ...e, what_was_wrong: editText.trim() } : e)
      );
      setEditingId(null);
    } catch (err) {
      console.error('Failed to update correction log entry:', err);
    } finally {
      setEditSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditText('');
  };

  const pageCount = Math.ceil(total / PAGE_SIZE);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <Container maxWidth="lg" sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>

        {/* Filter chips */}
        <Box sx={{ display: 'flex', gap: 1, pt: 2, pb: 1, flexShrink: 0, flexWrap: 'wrap' }}>
          {FILTER_OPTIONS.map(opt => (
            <Chip
              key={opt.value}
              label={opt.label}
              onClick={() => handleFilterChange(opt.value)}
              variant={filter === opt.value ? 'filled' : 'outlined'}
              sx={{
                color: 'white',
                borderColor: 'rgba(255,255,255,0.3)',
                bgcolor: filter === opt.value ? 'rgba(255,255,255,0.15)' : 'transparent',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' },
              }}
            />
          ))}
        </Box>

        {/* Scrollable entry list */}
        <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', py: 1 }}>
          {loading ? (
            <Box display="flex" justifyContent="center" py={8}>
              <CircularProgress color="primary" />
            </Box>
          ) : error ? (
            <Typography color="error" align="center" sx={{ py: 4 }}>{error}</Typography>
          ) : entries.length === 0 ? (
            <Paper sx={{ p: 4, bgcolor: 'rgba(255,255,255,0.05)', textAlign: 'center' }}>
              <Typography sx={{ color: 'rgba(255,255,255,0.5)' }}>
                No corrections logged yet. Corrections will appear here after editing AI-generated content.
              </Typography>
            </Paper>
          ) : (
            entries.map(entry => (
              <Paper key={entry.id} sx={{ p: 2, mb: 2, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 2 }}>

                {/* Header: type icon + reference + date */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                  <TypeIcon type={entry.content_type} />
                  <Typography variant="body2" sx={{ color: 'white', fontWeight: 600, flex: 1 }}>
                    {formatReference(entry)}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.4)' }}>
                    {new Date(entry.created_at).toLocaleDateString()}
                  </Typography>
                </Box>

                {/* Original AI text — read-only */}
                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', display: 'block', mb: 0.5 }}>
                  Original AI text
                </Typography>
                <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1.5, fontStyle: 'italic' }}>
                  {entry.original_text || <em style={{ opacity: 0.5 }}>—</em>}
                </Typography>

                {/* Correction — read-only */}
                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', display: 'block', mb: 0.5 }}>
                  Correction
                </Typography>
                <Typography variant="body2" sx={{ color: '#4CAF50', mb: 1.5 }}>
                  {entry.correction || <em style={{ opacity: 0.5 }}>—</em>}
                </Typography>

                <Divider sx={{ bgcolor: 'rgba(255,255,255,0.1)', mb: 1.5 }} />

                {/* What was wrong — editable inline */}
                {editingId === entry.id ? (
                  <Box>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', display: 'block', mb: 0.5 }}>
                      What was wrong
                    </Typography>
                    <TextField
                      fullWidth
                      multiline
                      rows={2}
                      value={editText}
                      onChange={e => setEditText(e.target.value)}
                      sx={{ mb: 1 }}
                      InputProps={{ sx: { color: 'white' } }}
                      autoFocus
                    />
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Button
                        size="small"
                        variant="contained"
                        startIcon={editSaving ? <CircularProgress size={14} /> : <Save />}
                        onClick={() => handleSaveEdit(entry.id)}
                        disabled={editSaving}
                      >
                        Save
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<Cancel />}
                        onClick={handleCancelEdit}
                        disabled={editSaving}
                        sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.3)' }}
                      >
                        Cancel
                      </Button>
                    </Box>
                  </Box>
                ) : (
                  <Box>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', display: 'block', mb: 0.5 }}>
                      What was wrong
                    </Typography>
                    <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.8)', mb: 1 }}>
                      {entry.what_was_wrong || <em style={{ opacity: 0.5 }}>No explanation provided</em>}
                    </Typography>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<Edit />}
                      onClick={() => handleStartEdit(entry)}
                      sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.3)' }}
                    >
                      Edit
                    </Button>
                  </Box>
                )}
              </Paper>
            ))
          )}
        </Box>

        {/* Pagination */}
        {pageCount > 1 && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 2, flexShrink: 0 }}>
            <Pagination
              count={pageCount}
              page={page}
              onChange={(_, p) => setPage(p)}
              sx={{ '& .MuiPaginationItem-root': { color: 'white' } }}
            />
          </Box>
        )}

      </Container>
    </Box>
  );
}
