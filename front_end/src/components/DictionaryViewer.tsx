// DictionaryViewer.tsx
/**
 * Dictionary Viewer component for unified human/AI dictionary views.
 *
 * Features:
 * - Word list with search/filter
 * - Detail view with Human/AI tabs when both exist
 * - Edit mode for creating/updating entries
 * - Verify button for marking entries as verified
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Typography,
  IconButton,
  Container,
  Paper,
  Chip,
  Grid,
  TextField,
  Button,
  CircularProgress,
  Divider,
  List,
  ListItemButton,
  ListItemText,
  InputAdornment
} from '@mui/material';
import {
  ArrowBack,
  Search,
  Edit,
  Save,
  Cancel,
  CheckCircle,
  CheckCircleOutline,
  Add
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import {
  fetchDictionaryEntries,
  saveDictionaryEntry,
  verifyDictionaryEntry,
  appendCorrectionLog,
  MergedDictionaryEntry,
} from '../renderer/api';
import { useChat } from '../renderer/contexts/ChatContext';
import { TOPBAR_HEIGHT } from '../renderer/constants';
import { CopyIconButton } from './CopyIconButton';

interface DictionaryViewerProps {
  languageCode: string;
  languageName: string;
  onBack: () => void;
}

type ViewState = 'list' | 'detail';

export function DictionaryViewer({ languageCode, languageName, onBack }: DictionaryViewerProps) {
  // Navigation state
  const [view, setView] = useState<ViewState>('list');
  const [selectedEntry, setSelectedEntry] = useState<MergedDictionaryEntry | null>(null);

  // Data state
  const [entries, setEntries] = useState<MergedDictionaryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Report context to chat
  const { setAppContext, injectContextNote } = useChat();
  useEffect(() => {
    setAppContext({ languageCode, bookCode: null, chapter: null, view: 'dictionary' });
  }, [languageCode, setAppContext]);

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState({
    word: '',
    definition: '',
    partOfSpeech: '',
    examples: '',
    whatWasWrong: ''
  });
  const [saving, setSaving] = useState(false);
  const [isCreatingNew, setIsCreatingNew] = useState(false);

  // Load entries on mount
  useEffect(() => {
    loadEntries();
  }, [languageCode]);

  const loadEntries = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDictionaryEntries(languageCode);
      setEntries(data.entries);
    } catch (err) {
      setError('Failed to load dictionary entries. Please check if the backend is running.');
      console.error('Failed to load entries:', err);
    } finally {
      setLoading(false);
    }
  };

  // Filter entries based on search
  const filteredEntries = useMemo(() => {
    if (!searchQuery.trim()) return entries;
    const query = searchQuery.toLowerCase();
    return entries.filter(e => {
      if (e.word.toLowerCase().includes(query)) return true;
      return (
        e.definition.toLowerCase().includes(query) ||
        (e.part_of_speech?.toLowerCase().includes(query) ?? false) ||
        e.examples.some(ex => ex.toLowerCase().includes(query))
      );
    });
  }, [entries, searchQuery]);

  const handleSelectEntry = (entry: MergedDictionaryEntry) => {
    setSelectedEntry(entry);
    setView('detail');
    setIsEditing(false);
  };

  const handleBack = () => {
    if (view === 'detail') {
      setView('list');
      setSelectedEntry(null);
      setIsEditing(false);
      setIsCreatingNew(false);
    } else {
      onBack();
    }
  };

  const handleCreateNew = () => {
    setEditForm({ word: '', definition: '', partOfSpeech: '', examples: '' });
    setIsCreatingNew(true);
    setIsEditing(true);
    setSelectedEntry(null);
    setView('detail');
  };

  const handleCardEdit = (entry: MergedDictionaryEntry, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedEntry(entry);
    setView('detail');
    setTimeout(() => {
      setEditForm({
        word: entry.word,
        definition: entry.definition || '',
        partOfSpeech: entry.part_of_speech || '',
        examples: entry.examples?.join('\n') || '',
        whatWasWrong: ''
      });
      setIsEditing(true);
    }, 0);
  };

  const handleCardVerify = async (entry: MergedDictionaryEntry, e: React.MouseEvent) => {
    e.stopPropagation();
    const newVerified = !entry.human_verified;

    try {
      await verifyDictionaryEntry(languageCode, entry.word, newVerified);

      setEntries(prev => prev.map(ent => {
        if (ent.word === entry.word) {
          return { ...ent, human_verified: newVerified };
        }
        return ent;
      }));
    } catch (err) {
      console.error('Failed to verify entry:', err);
    }
  };

  const handleStartEdit = () => {
    setEditForm({
      word: selectedEntry?.word || '',
      definition: selectedEntry?.definition || '',
      partOfSpeech: selectedEntry?.part_of_speech || '',
      examples: selectedEntry?.examples?.join('\n') || '',
      whatWasWrong: ''
    });
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    if (isCreatingNew) {
      setIsCreatingNew(false);
      setView('list');
    }
  };

  const handleSave = async () => {
    if (!editForm.word.trim() || !editForm.definition.trim()) return;

    setSaving(true);
    try {
      await saveDictionaryEntry(languageCode, {
        word: editForm.word.trim(),
        definition: editForm.definition.trim(),
        part_of_speech: editForm.partOfSpeech.trim() || undefined,
        examples: editForm.examples.split('\n').filter(e => e.trim())
      });

      // Reload entries to get updated data
      await loadEntries();

      // Find the updated entry and select it
      const updatedEntries = await fetchDictionaryEntries(languageCode);
      const updated = updatedEntries.entries.find(e => e.word === editForm.word.trim().toLowerCase());
      if (updated) {
        setSelectedEntry(updated);
      }

      if (!isCreatingNew && editForm.whatWasWrong.trim()) {
        injectContextNote(`[Correction note] ${editForm.word}: ${editForm.whatWasWrong}\nCorrected text: "${editForm.definition}"`);
        appendCorrectionLog(languageCode, {
          content_type: 'dictionary_entry',
          content_reference: { word: editForm.word },
          original_text: '',
          what_was_wrong: editForm.whatWasWrong.trim(),
          correction: editForm.definition,
        }).catch(err => console.error('Correction log save failed:', err));
      }

      setIsEditing(false);
      setIsCreatingNew(false);
    } catch (err) {
      console.error('Failed to save entry:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleVerify = async () => {
    if (!selectedEntry) return;

    const newVerified = !selectedEntry.human_verified;

    try {
      await verifyDictionaryEntry(languageCode, selectedEntry.word, newVerified);

      setEntries(prev => prev.map(e => {
        if (e.word === selectedEntry.word) {
          return { ...e, human_verified: newVerified };
        }
        return e;
      }));

      setSelectedEntry(prev => prev ? { ...prev, human_verified: newVerified } : prev);
    } catch (err) {
      console.error('Failed to verify entry:', err);
    }
  };

  // Get entry for display
  const getCurrentVersion = (): MergedDictionaryEntry | undefined => {
    return selectedEntry ?? undefined;
  };

  // Render word list
  const renderWordList = () => (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Search bar */}
      <TextField
        fullWidth
        placeholder="Search dictionary..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        sx={{
          mb: 2,
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

      {/* Entry list - enhanced cards with full details */}
      <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', overflowX: 'hidden' }}>
        {filteredEntries.map((entry) => {
          const displayVersion = entry;
          const isVerified = entry.human_verified;

          return (
            <motion.div key={entry.word} whileHover={{ scale: 1.005 }}>
              <Paper
                sx={{
                  mb: 1.5,
                  p: 2,
                  bgcolor: 'rgba(255,255,255,0.03)',
                  cursor: 'pointer',
                  borderRadius: 2,
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.06)' },
                  maxHeight: 220,
                  overflow: 'hidden',
                  position: 'relative'
                }}
                onClick={() => handleSelectEntry(entry)}
              >
                {/* Header: Word + Badges */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="body1" sx={{ color: 'white', fontWeight: 600 }}>
                    {entry.word}
                  </Typography>
                  {isVerified && (
                    <CheckCircle sx={{ color: '#4CAF50', fontSize: 18 }} />
                  )}
                </Box>

                {/* Part of Speech */}
                {displayVersion?.part_of_speech && (
                  <Chip
                    size="small"
                    label={displayVersion.part_of_speech}
                    sx={{
                      mb: 1,
                      bgcolor: 'rgba(255,255,255,0.1)',
                      color: 'rgba(255,255,255,0.7)'
                    }}
                  />
                )}

                {/* Definition */}
                <Typography
                  variant="body2"
                  sx={{
                    color: 'rgba(255,255,255,0.8)',
                    mb: 1,
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden'
                  }}
                >
                  {displayVersion?.definition || '(No definition)'}
                </Typography>

                {/* Examples (if any) */}
                {displayVersion?.examples && displayVersion.examples.length > 0 && (
                  <Box sx={{ mb: 1 }}>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', display: 'block', mb: 0.5 }}>
                      Examples:
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        color: 'rgba(255,255,255,0.7)',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden'
                      }}
                    >
                      {displayVersion.examples.slice(0, 3).map(ex => `• ${ex}`).join('  ')}
                    </Typography>
                  </Box>
                )}

                {/* Action buttons */}
                <Box sx={{ display: 'flex', gap: 1, mt: 1.5 }}>
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<Edit />}
                    onClick={(e) => handleCardEdit(entry, e)}
                    sx={{
                      color: 'white',
                      borderColor: 'rgba(255,255,255,0.3)',
                      '&:hover': { borderColor: 'rgba(255,255,255,0.5)' }
                    }}
                  >
                    Edit
                  </Button>
                  <Button
                    size="small"
                    variant={isVerified ? 'contained' : 'outlined'}
                    startIcon={isVerified ? <CheckCircle /> : <CheckCircleOutline />}
                    onClick={(e) => handleCardVerify(entry, e)}
                    color={isVerified ? 'success' : 'inherit'}
                    sx={!isVerified ? {
                      color: 'white',
                      borderColor: 'rgba(255,255,255,0.3)',
                      '&:hover': { borderColor: 'rgba(255,255,255,0.5)' }
                    } : {}}
                  >
                    {isVerified ? 'Verified' : 'Verify'}
                  </Button>
                  <Box component="span" onClick={(e) => e.stopPropagation()}>
                    <CopyIconButton
                      text={[entry.word, displayVersion?.part_of_speech, '', displayVersion?.definition, '', ...(displayVersion?.examples || [])].filter(Boolean).join('\n').trim()}
                    />
                  </Box>
                </Box>

                {/* Overflow indicator gradient */}
                <Box
                  sx={{
                    position: 'absolute',
                    bottom: 0,
                    left: 0,
                    right: 0,
                    height: 24,
                    background: 'linear-gradient(transparent, rgba(30,30,30,0.95))',
                    pointerEvents: 'none'
                  }}
                />
              </Paper>
            </motion.div>
          );
        })}
      </Box>

      {filteredEntries.length === 0 && !loading && (
        <Box sx={{ textAlign: 'center', py: 6 }}>
          {entries.length === 0 ? (
            <>
              <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 2 }}>
                No dictionary entries yet
              </Typography>
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.5)', mb: 3 }}>
                Start building your dictionary by adding the first entry.
              </Typography>
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={handleCreateNew}
                sx={{ bgcolor: '#2196F3' }}
              >
                Add First Entry
              </Button>
            </>
          ) : (
            <Typography sx={{ color: 'rgba(255,255,255,0.5)' }}>
              No matching entries found.
            </Typography>
          )}
        </Box>
      )}
    </Box>
  );

  // Render edit form (used for both editing and creating)
  const renderEditForm = () => (
    <Box>
      <TextField
        fullWidth
        label="Word"
        value={editForm.word}
        onChange={(e) => setEditForm(prev => ({ ...prev, word: e.target.value }))}
        sx={{ mb: 2 }}
        InputProps={{ sx: { color: 'white' } }}
        InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.7)' } }}
      />
      <TextField
        fullWidth
        label="Definition"
        value={editForm.definition}
        onChange={(e) => setEditForm(prev => ({ ...prev, definition: e.target.value }))}
        multiline
        rows={3}
        sx={{ mb: 2 }}
        InputProps={{ sx: { color: 'white' } }}
        InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.7)' } }}
      />
      <TextField
        fullWidth
        label="Part of Speech"
        value={editForm.partOfSpeech}
        onChange={(e) => setEditForm(prev => ({ ...prev, partOfSpeech: e.target.value }))}
        placeholder="e.g., noun, verb, adjective"
        sx={{ mb: 2 }}
        InputProps={{ sx: { color: 'white' } }}
        InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.7)' } }}
      />
      <TextField
        fullWidth
        label="Examples (one per line)"
        value={editForm.examples}
        onChange={(e) => setEditForm(prev => ({ ...prev, examples: e.target.value }))}
        multiline
        rows={3}
        sx={{ mb: 3 }}
        InputProps={{ sx: { color: 'white' } }}
        InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.7)' } }}
      />
      {!isCreatingNew && (
        <TextField
          fullWidth
          multiline
          rows={2}
          label="Optional: describe the correction"
          value={editForm.whatWasWrong}
          onChange={(e) => setEditForm(prev => ({ ...prev, whatWasWrong: e.target.value }))}
          sx={{ mb: 2 }}
          InputProps={{ sx: { color: 'white' } }}
          InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.7)' } }}
        />
      )}
      <Box sx={{ display: 'flex', gap: 2 }}>
        <Button
          variant="contained"
          startIcon={saving ? <CircularProgress size={16} /> : <Save />}
          onClick={handleSave}
          disabled={saving || !editForm.word.trim() || !editForm.definition.trim()}
        >
          Save
        </Button>
        <Button
          variant="outlined"
          startIcon={<Cancel />}
          onClick={handleCancelEdit}
          disabled={saving}
          sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.3)' }}
        >
          Cancel
        </Button>
      </Box>
    </Box>
  );

  // Render detail view
  const renderDetail = () => {
    const currentVersion = getCurrentVersion();

    // Creating new entry - show edit form with "New Entry" header
    if (isCreatingNew && !selectedEntry) {
      return (
        <Box>
          <Chip
            icon={<Add />}
            label="New Entry"
            sx={{ mb: 2, bgcolor: 'rgba(33,150,243,0.3)', color: 'white' }}
          />
          {renderEditForm()}
        </Box>
      );
    }

    return (
      <Box>

        {isEditing ? (
          renderEditForm()
        ) : (
          // Display view
          <Box>
            <Typography variant="h5" sx={{ color: 'white', mb: 1 }}>
              {selectedEntry?.word}
            </Typography>

            {currentVersion?.part_of_speech && (
              <Chip
                label={currentVersion.part_of_speech}
                size="small"
                sx={{ mb: 2, bgcolor: 'rgba(255,255,255,0.1)', color: 'white' }}
              />
            )}

            <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1, mt: 2 }}>
              Definition
            </Typography>
            <Typography sx={{ color: 'white', mb: 3 }}>
              {currentVersion?.definition || <em style={{ opacity: 0.5 }}>No definition</em>}
            </Typography>

            {currentVersion?.examples && currentVersion.examples.length > 0 && (
              <>
                <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1 }}>
                  Examples
                </Typography>
                <Box component="ul" sx={{ color: 'white', pl: 2 }}>
                  {currentVersion.examples.map((ex, i) => (
                    <li key={i}>{ex}</li>
                  ))}
                </Box>
              </>
            )}

            <Divider sx={{ my: 3, bgcolor: 'rgba(255,255,255,0.2)' }} />

            {/* Action buttons */}
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <Button
                variant="outlined"
                startIcon={<Edit />}
                onClick={handleStartEdit}
                sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.3)' }}
              >
                Edit
              </Button>
              <Button
                variant={currentVersion?.human_verified ? 'contained' : 'outlined'}
                startIcon={currentVersion?.human_verified ? <CheckCircle /> : <CheckCircleOutline />}
                onClick={handleVerify}
                color={currentVersion?.human_verified ? 'success' : 'inherit'}
                sx={!currentVersion?.human_verified ? { color: 'white', borderColor: 'rgba(255,255,255,0.3)' } : {}}
              >
                {currentVersion?.human_verified ? 'Verified' : 'Verify'}
              </Button>
              <CopyIconButton
                text={[selectedEntry?.word, currentVersion?.part_of_speech, '', currentVersion?.definition, '', ...(currentVersion?.examples || [])].filter(Boolean).join('\n').trim()}
              />
            </Box>
          </Box>
        )}
      </Box>
    );
  };

  return (
    <Box
      sx={{
        height: '100vh',
        overflow: 'hidden',  // Prevent page-level scroll
        background: 'linear-gradient(135deg, #1A1A1A, #2D2D2D)',
        pt: `${TOPBAR_HEIGHT + 8}px`,
        pb: 4,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Container maxWidth="lg" sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 3, flexShrink: 0 }}>
          <IconButton onClick={handleBack} sx={{ mr: 2, color: 'white' }}>
            <ArrowBack />
          </IconButton>
          <Typography variant="h4" component="h1" sx={{ color: 'white', flexGrow: 1 }}>
            {view === 'detail' && selectedEntry
              ? `Dictionary - ${selectedEntry.word}`
              : 'Dictionary'}
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
              <Button variant="outlined" onClick={loadEntries}>
                Retry
              </Button>
            </Box>
          </Paper>
        ) : (
          <Paper elevation={3} sx={{ p: 3, bgcolor: 'rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
            {view === 'list' && renderWordList()}
            {view === 'detail' && renderDetail()}
          </Paper>
        )}
      </Container>
    </Box>
  );
}
