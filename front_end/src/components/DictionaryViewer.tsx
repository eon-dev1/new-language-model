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
  Tabs,
  Tab,
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
  Person,
  SmartToy,
  Add
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import {
  fetchDictionaryEntries,
  saveDictionaryEntry,
  verifyDictionaryEntry,
  MergedDictionaryEntry,
  DictionaryEntryVersion
} from '../renderer/api';

interface DictionaryViewerProps {
  languageCode: string;
  languageName: string;
  onBack: () => void;
}

type ViewState = 'list' | 'detail';
type TabValue = 'human' | 'ai';

export function DictionaryViewer({ languageCode, languageName, onBack }: DictionaryViewerProps) {
  // Navigation state
  const [view, setView] = useState<ViewState>('list');
  const [selectedEntry, setSelectedEntry] = useState<MergedDictionaryEntry | null>(null);
  const [activeTab, setActiveTab] = useState<TabValue>('human');

  // Data state
  const [entries, setEntries] = useState<MergedDictionaryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState({
    word: '',
    definition: '',
    partOfSpeech: '',
    examples: ''
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
    return entries.filter(e => e.word.toLowerCase().includes(query));
  }, [entries, searchQuery]);

  const handleSelectEntry = (entry: MergedDictionaryEntry) => {
    setSelectedEntry(entry);
    // Default to human tab if exists, otherwise ai
    setActiveTab(entry.human ? 'human' : 'ai');
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

  const handleTabChange = (_: React.SyntheticEvent, newValue: TabValue) => {
    setActiveTab(newValue);
    setIsEditing(false);
  };

  const handleStartEdit = () => {
    const currentVersion = activeTab === 'human' ? selectedEntry?.human : selectedEntry?.ai;
    setEditForm({
      word: selectedEntry?.word || '',
      definition: currentVersion?.definition || '',
      partOfSpeech: currentVersion?.part_of_speech || '',
      examples: currentVersion?.examples?.join('\n') || ''
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
        setActiveTab('human'); // Saved entry is always human
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

    const currentVersion = activeTab === 'human' ? selectedEntry.human : selectedEntry.ai;
    if (!currentVersion) return;

    const newVerified = !currentVersion.human_verified;

    try {
      await verifyDictionaryEntry(languageCode, selectedEntry.word, activeTab, newVerified);

      // Update local state
      setEntries(prev => prev.map(e => {
        if (e.word === selectedEntry.word) {
          const updated = { ...e };
          if (activeTab === 'human' && updated.human) {
            updated.human = { ...updated.human, human_verified: newVerified };
          } else if (activeTab === 'ai' && updated.ai) {
            updated.ai = { ...updated.ai, human_verified: newVerified };
          }
          return updated;
        }
        return e;
      }));

      // Update selected entry
      setSelectedEntry(prev => {
        if (!prev) return prev;
        const updated = { ...prev };
        if (activeTab === 'human' && updated.human) {
          updated.human = { ...updated.human, human_verified: newVerified };
        } else if (activeTab === 'ai' && updated.ai) {
          updated.ai = { ...updated.ai, human_verified: newVerified };
        }
        return updated;
      });
    } catch (err) {
      console.error('Failed to verify entry:', err);
    }
  };

  // Get source badge for an entry
  const getSourceBadge = (entry: MergedDictionaryEntry) => {
    const sources = [];
    if (entry.human) sources.push('H');
    if (entry.ai) sources.push('AI');
    return sources.join('/');
  };

  // Get current version based on active tab
  const getCurrentVersion = (): DictionaryEntryVersion | undefined => {
    if (!selectedEntry) return undefined;
    return activeTab === 'human' ? selectedEntry.human : selectedEntry.ai;
  };

  // Render word list
  const renderWordList = () => (
    <Box>
      {/* Search bar */}
      <TextField
        fullWidth
        placeholder="Search words..."
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

      {/* Entry list */}
      <List sx={{ maxHeight: '60vh', overflow: 'auto' }}>
        {filteredEntries.map((entry) => (
          <motion.div key={entry.word} whileHover={{ x: 4 }}>
            <ListItemButton
              onClick={() => handleSelectEntry(entry)}
              sx={{
                mb: 0.5,
                borderRadius: 1,
                bgcolor: 'rgba(255,255,255,0.03)',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' }
              }}
            >
              <ListItemText
                primary={
                  <Typography sx={{ color: 'white', fontWeight: 500 }}>
                    {entry.word}
                  </Typography>
                }
                secondary={
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)' }}>
                    {(entry.human?.definition || entry.ai?.definition || '').slice(0, 60)}
                    {(entry.human?.definition || entry.ai?.definition || '').length > 60 ? '...' : ''}
                  </Typography>
                }
              />
              <Chip
                size="small"
                label={getSourceBadge(entry)}
                sx={{
                  bgcolor: entry.human ? 'rgba(33,150,243,0.3)' : 'rgba(255,152,0,0.3)',
                  color: 'white',
                  fontSize: '0.7rem'
                }}
              />
            </ListItemButton>
          </motion.div>
        ))}
      </List>

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
    const hasBothVersions = selectedEntry?.human && selectedEntry?.ai;

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
        {/* Tabs if both versions exist */}
        {hasBothVersions && (
          <Tabs
            value={activeTab}
            onChange={handleTabChange}
            sx={{ mb: 2, borderBottom: 1, borderColor: 'rgba(255,255,255,0.2)' }}
          >
            <Tab
              value="human"
              label={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Person fontSize="small" />
                  Human
                  {selectedEntry?.human?.human_verified && (
                    <CheckCircle sx={{ fontSize: 16, color: '#4CAF50' }} />
                  )}
                </Box>
              }
              sx={{ color: 'white', '&.Mui-selected': { color: '#2196F3' } }}
            />
            <Tab
              value="ai"
              label={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <SmartToy fontSize="small" />
                  AI
                  {selectedEntry?.ai?.human_verified && (
                    <CheckCircle sx={{ fontSize: 16, color: '#4CAF50' }} />
                  )}
                </Box>
              }
              sx={{ color: 'white', '&.Mui-selected': { color: '#FF9800' } }}
            />
          </Tabs>
        )}

        {/* Source badge if only one version */}
        {!hasBothVersions && (
          <Chip
            icon={activeTab === 'human' ? <Person /> : <SmartToy />}
            label={activeTab === 'human' ? 'Human Entry' : 'AI Entry'}
            sx={{
              mb: 2,
              bgcolor: activeTab === 'human' ? 'rgba(33,150,243,0.3)' : 'rgba(255,152,0,0.3)',
              color: 'white'
            }}
          />
        )}

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
            </Box>
          </Box>
        )}
      </Box>
    );
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #1A1A1A, #2D2D2D)',
        pt: 7,  // 56px to clear fixed TopBar (48px)
        pb: 4,
      }}
    >
      <Container maxWidth="lg">
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
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
          <Paper elevation={3} sx={{ p: 3, bgcolor: 'rgba(255,255,255,0.05)' }}>
            {view === 'list' && renderWordList()}
            {view === 'detail' && renderDetail()}
          </Paper>
        )}
      </Container>
    </Box>
  );
}
