// GrammarViewer.tsx
/**
 * Grammar Viewer component for unified human/AI grammar views.
 *
 * Features:
 * - Category grid (5 categories: phonology, morphology, syntax, semantics, discourse)
 * - Detail view with Human/AI tabs when both exist
 * - Edit mode for updating notes and examples
 * - Verify button for marking categories as verified
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
  Card,
  CardContent,
  CardActionArea,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  InputAdornment
} from '@mui/material';
import {
  ArrowBack,
  Edit,
  Save,
  Cancel,
  CheckCircle,
  CheckCircleOutline,
  RecordVoiceOver,
  Extension,
  AccountTree,
  Psychology,
  Forum,
  Add,
  Delete,
  Search
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import {
  fetchGrammarCategories,
  saveGrammarCategory,
  verifyGrammarCategory,
  verifyGrammarSubcategory,
  verifyGrammarNote,
  verifyGrammarExample,
  appendCorrectionLog,
  MergedGrammarCategory,
  GrammarCategoryVersion,
  SubcategoryItem,
  SubcategoryData,
  NoteItem,
  NoteData,
  ExampleItem,
  ExampleData
} from '../renderer/api';
import { useChat } from '../renderer/contexts/ChatContext';
import { TOPBAR_HEIGHT } from '../renderer/constants';
import {
  IndexedItem,
  isSubcategoryData,
  isExampleData,
  isNoteData,
  getNoteText,
  getSubcategoryLabel,
  getExampleSourceText,
  filterSubcategories,
  filterNotes,
  filterExamples,
  filterCategoryByContent
} from './searchFilters';
import { CopyIconButton } from './CopyIconButton';

interface GrammarViewerProps {
  languageCode: string;
  languageName: string;
  onBack: () => void;
  embeddedMode?: boolean;
}

type ViewState = 'categories' | 'detail';

// Category display configuration
const CATEGORY_CONFIG: Record<string, { icon: React.ReactNode; color: string; description: string }> = {
  phonology: {
    icon: <RecordVoiceOver />,
    color: '#E91E63',
    description: 'Sound system and pronunciation rules'
  },
  morphology: {
    icon: <Extension />,
    color: '#9C27B0',
    description: 'Word structure and formation'
  },
  syntax: {
    icon: <AccountTree />,
    color: '#2196F3',
    description: 'Sentence structure and word order'
  },
  semantics: {
    icon: <Psychology />,
    color: '#00BCD4',
    description: 'Meaning and interpretation'
  },
  discourse: {
    icon: <Forum />,
    color: '#4CAF50',
    description: 'Text-level organization and coherence'
  }
};

// --- Rich Edit Form Types ---

interface EditFormState {
  notes: NoteData[];
  subcategories: SubcategoryData[];
  examples: ExampleData[];
}

// --- Generic Nested Item Editor ---

interface FieldConfig {
  name: string;
  label: string;
  multiline?: boolean;
  rows?: number;
  isArray?: boolean;  // If true, split/join by newlines
}

interface NestedItemEditorProps<T extends Record<string, unknown>> {
  items: T[];
  onChange: (items: T[]) => void;
  fields: FieldConfig[];
  addLabel: string;
  emptyItem: T;
}

function NestedItemEditor<T extends Record<string, unknown>>({
  items,
  onChange,
  fields,
  addLabel,
  emptyItem
}: NestedItemEditorProps<T>) {
  const handleAdd = () => onChange([...items, { ...emptyItem }]);

  const handleUpdate = (index: number, field: string, value: unknown) => {
    const updated = [...items];
    updated[index] = { ...updated[index], [field]: value };
    onChange(updated);
  };

  const handleRemove = (index: number) => {
    onChange(items.filter((_, i) => i !== index));
  };

  return (
    <Box>
      {items.map((item, i) => (
        <Paper key={i} sx={{ p: 2, mb: 2, bgcolor: 'rgba(255,255,255,0.05)' }}>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
            <IconButton onClick={() => handleRemove(i)} size="small" sx={{ color: '#f44336' }}>
              <Delete />
            </IconButton>
          </Box>
          {fields.map(field => (
            <TextField
              key={field.name}
              label={field.label}
              value={field.isArray
                ? ((item[field.name] as string[] | undefined) || []).join('\n')
                : ((item[field.name] as string | undefined) || '')}
              onChange={(e) => handleUpdate(
                i,
                field.name,
                field.isArray ? e.target.value.split('\n') : e.target.value
              )}
              fullWidth
              multiline={field.multiline}
              rows={field.rows || 3}
              sx={{ mb: 2 }}
              InputProps={{ sx: { color: 'white' } }}
              InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.5)' } }}
            />
          ))}
        </Paper>
      ))}
      <Button startIcon={<Add />} onClick={handleAdd} variant="outlined" sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.3)' }}>
        {addLabel}
      </Button>
    </Box>
  );
}

export function GrammarViewer({ languageCode, languageName, onBack, embeddedMode = false }: GrammarViewerProps) {
  // Navigation state
  const [view, setView] = useState<ViewState>('categories');
  const [selectedCategory, setSelectedCategory] = useState<MergedGrammarCategory | null>(null);

  // Data state
  const [categories, setCategories] = useState<MergedGrammarCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<EditFormState>({
    notes: [],
    subcategories: [],
    examples: []
  });
  const [saving, setSaving] = useState(false);
  const [correctionNote, setCorrectionNote] = useState('');

  // Search state
  const [searchQuery, setSearchQuery] = useState('');

  // Modal edit state
  const [editModal, setEditModal] = useState<{
    type: 'subcategory' | 'note' | 'example';
    index: number;
    value: SubcategoryData | NoteData | ExampleData;
  } | null>(null);
  const [modalSaving, setModalSaving] = useState(false);

  // Report context to chat
  const { setAppContext, injectContextNote } = useChat();
  useEffect(() => {
    setAppContext({ languageCode, bookCode: null, chapter: null, view: 'grammar' });
  }, [languageCode, setAppContext]);

  // Load categories on mount
  useEffect(() => {
    loadCategories();
  }, [languageCode]);

  const loadCategories = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchGrammarCategories(languageCode);
      setCategories(data.categories);
    } catch (err) {
      setError('Failed to load grammar categories. Please check if the backend is running.');
      console.error('Failed to load categories:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCategory = (category: MergedGrammarCategory) => {
    setSelectedCategory(category);
    setSearchQuery('');
    setView('detail');
    setIsEditing(false);
  };

  const handleBack = () => {
    setSearchQuery('');
    if (view === 'detail') {
      setView('categories');
      setSelectedCategory(null);
      setIsEditing(false);
    } else {
      onBack();
    }
  };

  const handleStartEdit = () => {
    setCorrectionNote('');

    // Convert flat strings to rich format (legacy support on READ only)
    const notes: NoteData[] = (selectedCategory?.notes || []).map(note =>
      isNoteData(note) ? note : { text: String(note), human_verified: false }
    );

    const subcategories = (selectedCategory?.subcategories || []).map(sub =>
      isSubcategoryData(sub) ? sub : { name: String(sub), content: '', examples: [] }
    );

    const examples = (selectedCategory?.examples || []).map(ex =>
      isExampleData(ex)
        ? { source_text: getExampleSourceText(ex), english: ex.english, analysis: ex.analysis, human_verified: ex.human_verified }
        : { source_text: String(ex), english: '', analysis: '', human_verified: false }
    );

    setEditForm({ notes, subcategories, examples });
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setCorrectionNote('');
  };

  const handleSave = async () => {
    if (!selectedCategory) return;

    setSaving(true);
    try {
      await saveGrammarCategory(languageCode, selectedCategory.name, {
        notes: editForm.notes,
        subcategories: editForm.subcategories,
        examples: editForm.examples
      });

      // Reload categories to get updated data
      await loadCategories();

      // Find the updated category and select it
      const updatedCategories = await fetchGrammarCategories(languageCode);
      const updated = updatedCategories.categories.find(c => c.name === selectedCategory.name);
      if (updated) {
        setSelectedCategory(updated);
      }

      if (correctionNote.trim()) {
        const correctedContent = editForm.notes.map(n => n.text).join(' ');
        injectContextNote(`[Correction note] Grammar/${selectedCategory.name}: ${correctionNote}\nCorrected text: "${correctedContent}"`);
        appendCorrectionLog(languageCode, {
          content_type: 'grammar_category',
          content_reference: { category: selectedCategory.name },
          original_text: '',
          what_was_wrong: correctionNote.trim(),
          correction: correctedContent,
        }).catch(err => console.error('Correction log save failed:', err));
      }
      setCorrectionNote('');

      setIsEditing(false);
    } catch (err) {
      console.error('Failed to save category:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleVerify = async () => {
    if (!selectedCategory) return;

    const newVerified = !selectedCategory.human_verified;

    try {
      await verifyGrammarCategory(languageCode, selectedCategory.name, newVerified);

      setCategories(prev => prev.map(c => {
        if (c.name === selectedCategory.name) {
          return { ...c, human_verified: newVerified };
        }
        return c;
      }));

      setSelectedCategory(prev => prev ? { ...prev, human_verified: newVerified } : prev);
    } catch (err) {
      console.error('Failed to verify category:', err);
    }
  };

  const handleSubcategoryVerify = async (subcategoryIndex: number, currentlyVerified: boolean) => {
    if (!selectedCategory) return;

    const newVerified = !currentlyVerified;

    try {
      await verifyGrammarSubcategory(
        languageCode,
        selectedCategory.name,
        subcategoryIndex,
        newVerified
      );

      const updateSubcategories = (subcats: SubcategoryItem[]): SubcategoryItem[] => {
        return subcats.map((sub, i) => {
          if (i === subcategoryIndex && isSubcategoryData(sub)) {
            return { ...sub, human_verified: newVerified };
          }
          return sub;
        });
      };

      setCategories(prev => prev.map(c => {
        if (c.name === selectedCategory.name) {
          return { ...c, subcategories: updateSubcategories(c.subcategories) };
        }
        return c;
      }));

      setSelectedCategory(prev => {
        if (!prev) return prev;
        return { ...prev, subcategories: updateSubcategories(prev.subcategories) };
      });
    } catch (err) {
      console.error('Failed to verify subcategory:', err);
    }
  };

  const handleNoteVerify = async (noteIndex: number, currentlyVerified: boolean) => {
    if (!selectedCategory) return;

    const newVerified = !currentlyVerified;

    try {
      await verifyGrammarNote(languageCode, selectedCategory.name, noteIndex, newVerified);

      const updateNotes = (notes: NoteItem[]): NoteItem[] => {
        return notes.map((note, i) => {
          if (i === noteIndex) {
            if (isNoteData(note)) {
              return { ...note, human_verified: newVerified };
            }
            return { text: String(note), human_verified: newVerified };
          }
          return note;
        });
      };

      setCategories(prev => prev.map(c => {
        if (c.name === selectedCategory.name) {
          return { ...c, notes: updateNotes(c.notes) };
        }
        return c;
      }));

      setSelectedCategory(prev => {
        if (!prev) return prev;
        return { ...prev, notes: updateNotes(prev.notes) };
      });
    } catch (err) {
      console.error('Failed to verify note:', err);
    }
  };

  const handleExampleVerify = async (exampleIndex: number, currentlyVerified: boolean) => {
    if (!selectedCategory) return;

    const newVerified = !currentlyVerified;

    try {
      await verifyGrammarExample(languageCode, selectedCategory.name, exampleIndex, newVerified);

      const updateExamples = (examples: ExampleItem[]): ExampleItem[] => {
        return examples.map((ex, i) => {
          if (i === exampleIndex && isExampleData(ex)) {
            return { ...ex, human_verified: newVerified };
          }
          return ex;
        });
      };

      setCategories(prev => prev.map(c => {
        if (c.name === selectedCategory.name) {
          return { ...c, examples: updateExamples(c.examples) };
        }
        return c;
      }));

      setSelectedCategory(prev => {
        if (!prev) return prev;
        return { ...prev, examples: updateExamples(prev.examples) };
      });
    } catch (err) {
      console.error('Failed to verify example:', err);
    }
  };

  // Modal handlers for per-item editing
  const handleOpenEditModal = (
    type: 'subcategory' | 'note' | 'example',
    index: number,
    value: SubcategoryData | NoteItem | ExampleData
  ) => {
    // For notes, convert to NoteData if string
    if (type === 'note') {
      const noteValue = isNoteData(value as NoteItem)
        ? { ...(value as NoteData) }
        : { text: String(value), human_verified: false };
      setEditModal({ type, index, value: noteValue });
      return;
    }
    // For subcategories/examples, clone to avoid direct mutation
    const clonedValue = { ...(value as SubcategoryData | ExampleData) };
    setEditModal({ type, index, value: clonedValue });
  };

  const handleCloseEditModal = () => {
    setEditModal(null);
  };

  const handleSaveEditModal = async () => {
    if (!editModal || !selectedCategory) return;

    const currentVersion = getCurrentVersion();
    if (!currentVersion) return;

    setModalSaving(true);

    try {
      // Build updated arrays based on modal type - convert to rich format
      let updatedNotes: NoteData[] = (currentVersion.notes || []).map(note =>
        isNoteData(note) ? note : { text: String(note), human_verified: false }
      );
      let updatedSubcategories = (currentVersion.subcategories || []).map(sub =>
        isSubcategoryData(sub) ? sub : { name: String(sub), content: '', examples: [] }
      );
      let updatedExamples = (currentVersion.examples || []).map(ex =>
        isExampleData(ex)
          ? { source_text: getExampleSourceText(ex), english: ex.english, analysis: ex.analysis, human_verified: ex.human_verified }
          : { source_text: String(ex), english: '', analysis: '', human_verified: false }
      );

      if (editModal.type === 'note') {
        updatedNotes = [...updatedNotes];
        updatedNotes[editModal.index] = editModal.value as NoteData;
      } else if (editModal.type === 'subcategory') {
        updatedSubcategories = [...updatedSubcategories];
        updatedSubcategories[editModal.index] = editModal.value as SubcategoryData;
      } else if (editModal.type === 'example') {
        updatedExamples = [...updatedExamples];
        updatedExamples[editModal.index] = editModal.value as ExampleData;
      }

      // Save to backend
      await saveGrammarCategory(languageCode, selectedCategory.name, {
        notes: updatedNotes,
        subcategories: updatedSubcategories,
        examples: updatedExamples
      });

      // Reload to get fresh data
      const updatedCategories = await fetchGrammarCategories(languageCode);
      setCategories(updatedCategories.categories);
      const updated = updatedCategories.categories.find(c => c.name === selectedCategory.name);
      if (updated) {
        setSelectedCategory(updated);
      }

      setEditModal(null);
    } catch (err) {
      console.error('Failed to save item:', err);
    } finally {
      setModalSaving(false);
    }
  };

  // Get current category data
  const getCurrentVersion = (): MergedGrammarCategory | undefined => {
    return selectedCategory ?? undefined;
  };

  // Filtered content for detail view search
  const filteredContent = useMemo(() => {
    if (!selectedCategory) {
      return {
        subcategories: [] as IndexedItem<SubcategoryItem>[],
        notes: [] as IndexedItem<NoteItem>[],
        examples: [] as IndexedItem<ExampleItem>[],
        hasResults: false,
      };
    }
    const subcategories = filterSubcategories(selectedCategory.subcategories || [], searchQuery);
    const notes = filterNotes(selectedCategory.notes || [], searchQuery);
    const examples = filterExamples(selectedCategory.examples || [], searchQuery);
    return {
      subcategories, notes, examples,
      hasResults: subcategories.length > 0 || notes.length > 0 || examples.length > 0,
    };
  }, [selectedCategory, searchQuery]);

  // Filtered categories for top-level grid search
  const filteredCategories = useMemo(
    () => filterCategoryByContent(categories, searchQuery),
    [categories, searchQuery]
  );

  // Format category name for display
  const formatCategoryName = (name: string): string => {
    return name.charAt(0).toUpperCase() + name.slice(1);
  };

  // Render category grid
  const renderCategoryGrid = () => (
    <>
      <TextField
        fullWidth
        placeholder="Search grammar..."
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
      <Grid container spacing={2}>
        {filteredCategories.map((category) => {
          const config = CATEGORY_CONFIG[category.name] || {
            icon: <Psychology />,
            color: '#9E9E9E',
            description: category.name
          };
          const hasContent = !!(category.description || (category.subcategories?.length ?? 0) > 0 || (category.notes?.length ?? 0) > 0 || (category.examples?.length ?? 0) > 0);
          const isVerified = category.human_verified;

          return (
            <Grid item xs={12} sm={6} md={4} key={category.name}>
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                <Card
                  sx={{
                    bgcolor: 'rgba(255,255,255,0.05)',
                    borderLeft: `4px solid ${config.color}`,
                    cursor: 'pointer',
                    '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' }
                  }}
                >
                  <CardActionArea onClick={() => handleSelectCategory(category)}>
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                        <Box sx={{ color: config.color, mr: 1 }}>
                          {config.icon}
                        </Box>
                        <Typography variant="h6" sx={{ color: 'white', flexGrow: 1 }}>
                          {formatCategoryName(category.name)}
                        </Typography>
                      </Box>
                      <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.6)', mb: 1 }}>
                        {config.description}
                      </Typography>
                    </CardContent>
                  </CardActionArea>
                </Card>
              </motion.div>
            </Grid>
          );
        })}
      </Grid>
      {filteredCategories.length === 0 && searchQuery.trim() && (
        <Typography
          align="center"
          sx={{ color: 'rgba(255,255,255,0.5)', fontStyle: 'italic', py: 4 }}
        >
          No grammar content matches &ldquo;{searchQuery}&rdquo;
        </Typography>
      )}
    </>
  );

  // Render detail view
  const renderDetail = () => {
    const currentVersion = getCurrentVersion();
    const config = selectedCategory ? CATEGORY_CONFIG[selectedCategory.name] : null;
    const hasContent = !!(currentVersion?.description || (currentVersion?.subcategories?.length ?? 0) > 0 || (currentVersion?.notes?.length ?? 0) > 0 || (currentVersion?.examples?.length ?? 0) > 0);

    return (
      <Box>
        {/* Category header */}
        {config && (
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Box sx={{ color: config.color, mr: 1, fontSize: 32 }}>
              {config.icon}
            </Box>
            <Box>
              <Typography variant="h5" sx={{ color: 'white' }}>
                {formatCategoryName(selectedCategory?.name || '')}
              </Typography>
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.6)' }}>
                {config.description}
              </Typography>
            </Box>
          </Box>
        )}

        <Divider sx={{ mb: 2, bgcolor: 'rgba(255,255,255,0.2)' }} />


        {/* Empty state - no human or AI content */}
        {!hasContent && !isEditing && (
          <Box sx={{ textAlign: 'center', py: 6 }}>
            <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 2 }}>
              No content yet for {formatCategoryName(selectedCategory?.name || '')}
            </Typography>
            <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.5)', mb: 3 }}>
              Start documenting this grammar category by adding notes and examples.
            </Typography>
            <Button
              variant="contained"
              startIcon={<Edit />}
              onClick={handleStartEdit}
              sx={{ bgcolor: config?.color || '#9C27B0' }}
            >
              Add Notes & Examples
            </Button>
          </Box>
        )}

        {isEditing ? (
          // Edit form with rich structured editors
          <Box>
            {/* Show "New Content" badge when creating from empty state */}
            {!currentVersion && (
              <Chip
                icon={<Edit />}
                label="New Content"
                sx={{ mb: 2, bgcolor: 'rgba(33,150,243,0.3)', color: 'white' }}
              />
            )}

            {/* Notes Section */}
            <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1 }}>
              Notes (one per line)
            </Typography>
            <TextField
              fullWidth
              value={editForm.notes.map(n => n.text).join('\n')}
              onChange={(e) => setEditForm(prev => ({
                ...prev,
                notes: e.target.value.split('\n').map(text => ({ text, human_verified: false }))
              }))}
              multiline
              rows={4}
              placeholder="Enter grammar notes..."
              sx={{ mb: 3 }}
              InputProps={{ sx: { color: 'white', bgcolor: 'rgba(255,255,255,0.05)' } }}
            />

            {/* Subcategories Section */}
            <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1 }}>
              Subcategories
            </Typography>
            <Box sx={{ mb: 3 }}>
              <NestedItemEditor
                items={editForm.subcategories}
                onChange={subcats => setEditForm(prev => ({ ...prev, subcategories: subcats }))}
                fields={[
                  { name: 'name', label: 'Name', multiline: false },
                  { name: 'content', label: 'Content', multiline: true, rows: 4 },
                  { name: 'examples', label: 'Examples (one per line)', multiline: true, rows: 3, isArray: true }
                ]}
                addLabel="Add Subcategory"
                emptyItem={{ name: '', content: '', examples: [] }}
              />
            </Box>

            {/* Examples Section */}
            <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1 }}>
              Examples
            </Typography>
            <Box sx={{ mb: 3 }}>
              <NestedItemEditor
                items={editForm.examples}
                onChange={exs => setEditForm(prev => ({ ...prev, examples: exs }))}
                fields={[
                  { name: 'source_text', label: languageName, multiline: true, rows: 2 },
                  { name: 'english', label: 'English', multiline: true, rows: 2 },
                  { name: 'analysis', label: 'Analysis', multiline: true, rows: 2 }
                ]}
                addLabel="Add Example"
                emptyItem={{ source_text: '', english: '', analysis: '' }}
              />
            </Box>

            <TextField
              fullWidth
              multiline
              rows={2}
              label="Optional: describe the correction"
              value={correctionNote}
              onChange={(e) => setCorrectionNote(e.target.value)}
              sx={{ mb: 2 }}
              InputProps={{ sx: { color: 'white', bgcolor: 'rgba(255,255,255,0.05)' } }}
              InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.5)' } }}
            />

            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                startIcon={saving ? <CircularProgress size={16} /> : <Save />}
                onClick={handleSave}
                disabled={saving}
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
        ) : currentVersion ? (
          // Display view (only when there's content)
          <Box>
            {/* Subcategories */}
            {filteredContent.subcategories.length > 0 && (
              <>
                <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1 }}>
                  Subcategories
                </Typography>
                {/* Check if subcategories are rich objects (AI) or simple strings (human) */}
                {filteredContent.subcategories.some(({ item }) => isSubcategoryData(item)) ? (
                  // Rich format: render as expandable sections
                  <Box sx={{ mb: 3 }}>
                    {filteredContent.subcategories.map(({ item: sub, originalIndex }) => {
                      if (isSubcategoryData(sub)) {
                        const isVerified = sub.human_verified ?? false;
                        return (
                          <Box key={originalIndex} sx={{ mb: 2, p: 2, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1 }}>
                            {/* Header with name, edit and verify buttons */}
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                              <Typography variant="subtitle1" sx={{ color: 'white', fontWeight: 'bold' }}>
                                {sub.name.replace(/_/g, ' ')}
                              </Typography>
                              <Box sx={{ display: 'flex', gap: 1 }}>
                                <IconButton
                                  size="small"
                                  onClick={() => handleOpenEditModal('subcategory', originalIndex, sub)}
                                  sx={{ color: 'rgba(255,255,255,0.7)', '&:hover': { color: 'white' } }}
                                >
                                  <Edit fontSize="small" />
                                </IconButton>
                                <CopyIconButton
                                  text={[sub.name.replace(/_/g, ' '), '', sub.content, ...(sub.examples?.length ? ['', ...sub.examples] : [])].join('\n').trim()}
                                />
                                <Button
                                  size="small"
                                  variant={isVerified ? 'contained' : 'outlined'}
                                  startIcon={isVerified ? <CheckCircle /> : <CheckCircleOutline />}
                                  onClick={() => handleSubcategoryVerify(originalIndex, isVerified)}
                                  color={isVerified ? 'success' : 'inherit'}
                                  sx={!isVerified ? {
                                    color: 'rgba(255,255,255,0.7)',
                                    borderColor: 'rgba(255,255,255,0.3)',
                                    '&:hover': { borderColor: 'rgba(255,255,255,0.5)' }
                                  } : {}}
                                >
                                  {isVerified ? 'Verified' : 'Verify'}
                                </Button>
                              </Box>
                            </Box>
                            <Typography sx={{ color: 'rgba(255,255,255,0.8)', mb: 1 }}>
                              {sub.content}
                            </Typography>
                            {sub.examples && sub.examples.length > 0 && (
                              <Box sx={{ pl: 2, borderLeft: '2px solid rgba(255,255,255,0.2)' }}>
                                {sub.examples.map((ex, j) => (
                                  <Typography key={j} sx={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.9rem' }}>
                                    {ex}
                                  </Typography>
                                ))}
                              </Box>
                            )}
                          </Box>
                        );
                      }
                      // Fallback for mixed arrays
                      return (
                        <Chip
                          key={originalIndex}
                          label={getSubcategoryLabel(sub)}
                          size="small"
                          sx={{ bgcolor: 'rgba(255,255,255,0.1)', color: 'white', mr: 1, mb: 1 }}
                        />
                      );
                    })}
                  </Box>
                ) : (
                  // Simple format: render as chips
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
                    {filteredContent.subcategories.map(({ item: sub, originalIndex }) => (
                      <Chip
                        key={originalIndex}
                        label={getSubcategoryLabel(sub)}
                        size="small"
                        sx={{ bgcolor: 'rgba(255,255,255,0.1)', color: 'white' }}
                      />
                    ))}
                  </Box>
                )}
              </>
            )}

            {/* Notes */}
            <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1 }}>
              Notes
            </Typography>
            {filteredContent.notes.length > 0 ? (
              <Box sx={{ mb: 3 }}>
                {filteredContent.notes.map(({ item: note, originalIndex }) => {
                  const noteText = getNoteText(note);
                  const isVerified = isNoteData(note) ? (note.human_verified ?? false) : false;
                  return (
                    <Box key={originalIndex} sx={{ mb: 1.5, p: 2, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <Typography sx={{ color: 'white', flex: 1 }}>{noteText}</Typography>
                        <Box sx={{ display: 'flex', gap: 1, ml: 1, flexShrink: 0 }}>
                          <IconButton
                            size="small"
                            onClick={() => handleOpenEditModal('note', originalIndex, note)}
                            sx={{ color: 'rgba(255,255,255,0.7)', '&:hover': { color: 'white' } }}
                          >
                            <Edit fontSize="small" />
                          </IconButton>
                          <Button
                            size="small"
                            variant={isVerified ? 'contained' : 'outlined'}
                            startIcon={isVerified ? <CheckCircle /> : <CheckCircleOutline />}
                            onClick={() => handleNoteVerify(originalIndex, isVerified)}
                            color={isVerified ? 'success' : 'inherit'}
                            sx={!isVerified ? {
                              color: 'rgba(255,255,255,0.7)',
                              borderColor: 'rgba(255,255,255,0.3)',
                              '&:hover': { borderColor: 'rgba(255,255,255,0.5)' }
                            } : {}}
                          >
                            {isVerified ? 'Verified' : 'Verify'}
                          </Button>
                        </Box>
                      </Box>
                    </Box>
                  );
                })}
              </Box>
            ) : (
              <Typography sx={{ color: 'rgba(255,255,255,0.5)', fontStyle: 'italic', mb: 3 }}>
                {searchQuery.trim() ? `No notes matching "${searchQuery}"` : 'No notes yet'}
              </Typography>
            )}

            {/* Examples */}
            <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1 }}>
              Examples
            </Typography>
            {filteredContent.examples.length > 0 ? (
              filteredContent.examples.some(({ item }) => isExampleData(item)) ? (
                // Rich format: render structured examples (AI-generated)
                <Box sx={{ mb: 3 }}>
                  {filteredContent.examples.map(({ item: ex, originalIndex }) => {
                    if (isExampleData(ex)) {
                      const isVerified = ex.human_verified ?? false;
                      const exampleData: ExampleData = {
                        source_text: getExampleSourceText(ex),
                        english: ex.english,
                        analysis: ex.analysis,
                        human_verified: isVerified
                      };
                      return (
                        <Box key={originalIndex} sx={{ mb: 2, p: 2, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1 }}>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                            <Box sx={{ flex: 1 }}>
                              <Typography sx={{ color: 'white', fontWeight: 'bold' }}>
                                {getExampleSourceText(ex)}
                              </Typography>
                              <Typography sx={{ color: 'rgba(255,255,255,0.8)' }}>
                                {ex.english}
                              </Typography>
                              {ex.analysis && (
                                <Typography sx={{ color: 'rgba(255,255,255,0.6)', fontStyle: 'italic', fontSize: '0.9rem', mt: 0.5 }}>
                                  {ex.analysis}
                                </Typography>
                              )}
                            </Box>
                            <Box sx={{ display: 'flex', gap: 1, ml: 1, flexShrink: 0 }}>
                              <IconButton
                                size="small"
                                onClick={() => handleOpenEditModal('example', originalIndex, exampleData)}
                                sx={{ color: 'rgba(255,255,255,0.7)', '&:hover': { color: 'white' } }}
                              >
                                <Edit fontSize="small" />
                              </IconButton>
                              <Button
                                size="small"
                                variant={isVerified ? 'contained' : 'outlined'}
                                startIcon={isVerified ? <CheckCircle /> : <CheckCircleOutline />}
                                onClick={() => handleExampleVerify(originalIndex, isVerified)}
                                color={isVerified ? 'success' : 'inherit'}
                                sx={!isVerified ? {
                                  color: 'rgba(255,255,255,0.7)',
                                  borderColor: 'rgba(255,255,255,0.3)',
                                  '&:hover': { borderColor: 'rgba(255,255,255,0.5)' }
                                } : {}}
                              >
                                {isVerified ? 'Verified' : 'Verify'}
                              </Button>
                            </Box>
                          </Box>
                        </Box>
                      );
                    }
                    // Fallback for simple string examples - still show verify button
                    return (
                      <Box key={originalIndex} sx={{ mb: 1.5, p: 2, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <Typography sx={{ color: 'white', flex: 1 }}>{String(ex)}</Typography>
                          <Box sx={{ display: 'flex', gap: 1, ml: 1, flexShrink: 0 }}>
                            <IconButton
                              size="small"
                              onClick={() => handleOpenEditModal('example', originalIndex, { source_text: String(ex), english: '', analysis: '', human_verified: false })}
                              sx={{ color: 'rgba(255,255,255,0.7)', '&:hover': { color: 'white' } }}
                            >
                              <Edit fontSize="small" />
                            </IconButton>
                            <Button
                              size="small"
                              variant="outlined"
                              startIcon={<CheckCircleOutline />}
                              onClick={() => handleExampleVerify(originalIndex, false)}
                              sx={{
                                color: 'rgba(255,255,255,0.7)',
                                borderColor: 'rgba(255,255,255,0.3)',
                                '&:hover': { borderColor: 'rgba(255,255,255,0.5)' }
                              }}
                            >
                              Verify
                            </Button>
                          </Box>
                        </Box>
                      </Box>
                    );
                  })}
                </Box>
              ) : (
                // Simple format: render as cards with edit and verify (human-entered)
                <Box sx={{ mb: 3 }}>
                  {filteredContent.examples.map(({ item: ex, originalIndex }) => (
                    <Box key={originalIndex} sx={{ mb: 1.5, p: 2, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <Typography sx={{ color: 'white', flex: 1 }}>{String(ex)}</Typography>
                        <Box sx={{ display: 'flex', gap: 1, ml: 1, flexShrink: 0 }}>
                          <IconButton
                            size="small"
                            onClick={() => handleOpenEditModal('example', originalIndex, { source_text: String(ex), english: '', analysis: '', human_verified: false })}
                            sx={{ color: 'rgba(255,255,255,0.7)', '&:hover': { color: 'white' } }}
                          >
                            <Edit fontSize="small" />
                          </IconButton>
                          <Button
                            size="small"
                            variant="outlined"
                            startIcon={<CheckCircleOutline />}
                            onClick={() => handleExampleVerify(originalIndex, false)}
                            sx={{
                              color: 'rgba(255,255,255,0.7)',
                              borderColor: 'rgba(255,255,255,0.3)',
                              '&:hover': { borderColor: 'rgba(255,255,255,0.5)' }
                            }}
                          >
                            Verify
                          </Button>
                        </Box>
                      </Box>
                    </Box>
                  ))}
                </Box>
              )
            ) : (
              <Typography sx={{ color: 'rgba(255,255,255,0.5)', fontStyle: 'italic', mb: 3 }}>
                {searchQuery.trim() ? `No examples matching "${searchQuery}"` : 'No examples yet'}
              </Typography>
            )}

            {searchQuery.trim() && !filteredContent.hasResults && (
              <Typography sx={{ color: 'rgba(255,255,255,0.5)', fontStyle: 'italic', textAlign: 'center', py: 4 }}>
                No content matching &ldquo;{searchQuery}&rdquo;
              </Typography>
            )}
          </Box>
        ) : null}
      </Box>
    );
  };

  return (
    <Box
      sx={{
        height: embeddedMode ? '100%' : '100vh',
        overflow: 'hidden',
        background: 'linear-gradient(135deg, #1A1A1A, #2D2D2D)',
        pt: embeddedMode ? 0 : `${TOPBAR_HEIGHT + 8}px`,
        pb: 4,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Container maxWidth="lg" sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        {/* Header — hidden in embedded mode (parent owns AppBar) */}
        {!embeddedMode && (
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 3, flexShrink: 0 }}>
            <IconButton onClick={handleBack} sx={{ mr: 2, color: 'white' }}>
              <ArrowBack />
            </IconButton>
            <Typography variant="h4" component="h1" sx={{ color: 'white', flexGrow: 1 }}>
              {view === 'detail' && selectedCategory
                ? `Grammar - ${formatCategoryName(selectedCategory.name)}`
                : 'Grammar System'}
            </Typography>
            <Chip
              label={languageName}
              sx={{ bgcolor: 'rgba(255,255,255,0.1)', color: 'white' }}
            />
          </Box>
        )}

        {/* Content */}
        {loading ? (
          <Box display="flex" justifyContent="center" py={8}>
            <CircularProgress color="primary" />
          </Box>
        ) : error ? (
          <Paper sx={{ p: 4, bgcolor: 'rgba(255,255,255,0.05)' }}>
            <Typography color="error" align="center">{error}</Typography>
            <Box display="flex" justifyContent="center" mt={2}>
              <Button variant="outlined" onClick={loadCategories}>
                Retry
              </Button>
            </Box>
          </Paper>
        ) : (
          <Paper elevation={3} sx={{ p: 3, bgcolor: 'rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflowY: 'auto', overflowX: 'hidden' }}>
            {view === 'categories' && renderCategoryGrid()}
            {view === 'detail' && renderDetail()}
          </Paper>
        )}
      </Container>

      {/* Edit Item Modal */}
      <Dialog
        open={!!editModal}
        onClose={handleCloseEditModal}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            bgcolor: '#2D2D2D',
            color: 'white'
          }
        }}
      >
        <DialogTitle>
          {editModal?.type === 'subcategory' && 'Edit Subcategory'}
          {editModal?.type === 'note' && 'Edit Note'}
          {editModal?.type === 'example' && 'Edit Example'}
        </DialogTitle>
        <DialogContent>
          {editModal?.type === 'note' && (
            <TextField
              fullWidth
              multiline
              rows={4}
              value={(editModal.value as NoteData).text || ''}
              onChange={(e) => setEditModal(prev => prev ? {
                ...prev,
                value: { ...(prev.value as NoteData), text: e.target.value }
              } : null)}
              placeholder="Enter note..."
              sx={{ mt: 1 }}
              InputProps={{ sx: { color: 'white', bgcolor: 'rgba(255,255,255,0.05)' } }}
            />
          )}
          {editModal?.type === 'subcategory' && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
              <TextField
                label="Name"
                fullWidth
                value={(editModal.value as SubcategoryData).name || ''}
                onChange={(e) => setEditModal(prev => prev ? {
                  ...prev,
                  value: { ...(prev.value as SubcategoryData), name: e.target.value }
                } : null)}
                InputProps={{ sx: { color: 'white' } }}
                InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.5)' } }}
              />
              <TextField
                label="Content"
                fullWidth
                multiline
                rows={4}
                value={(editModal.value as SubcategoryData).content || ''}
                onChange={(e) => setEditModal(prev => prev ? {
                  ...prev,
                  value: { ...(prev.value as SubcategoryData), content: e.target.value }
                } : null)}
                InputProps={{ sx: { color: 'white' } }}
                InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.5)' } }}
              />
              <TextField
                label="Examples (one per line)"
                fullWidth
                multiline
                rows={3}
                value={((editModal.value as SubcategoryData).examples || []).join('\n')}
                onChange={(e) => setEditModal(prev => prev ? {
                  ...prev,
                  value: { ...(prev.value as SubcategoryData), examples: e.target.value.split('\n').filter(s => s.trim()) }
                } : null)}
                InputProps={{ sx: { color: 'white' } }}
                InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.5)' } }}
              />
            </Box>
          )}
          {editModal?.type === 'example' && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
              <TextField
                label={languageName}
                fullWidth
                multiline
                rows={2}
                value={(editModal.value as ExampleData).source_text || ''}
                onChange={(e) => setEditModal(prev => prev ? {
                  ...prev,
                  value: { ...(prev.value as ExampleData), source_text: e.target.value }
                } : null)}
                InputProps={{ sx: { color: 'white' } }}
                InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.5)' } }}
              />
              <TextField
                label="English"
                fullWidth
                multiline
                rows={2}
                value={(editModal.value as ExampleData).english || ''}
                onChange={(e) => setEditModal(prev => prev ? {
                  ...prev,
                  value: { ...(prev.value as ExampleData), english: e.target.value }
                } : null)}
                InputProps={{ sx: { color: 'white' } }}
                InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.5)' } }}
              />
              <TextField
                label="Analysis"
                fullWidth
                multiline
                rows={2}
                value={(editModal.value as ExampleData).analysis || ''}
                onChange={(e) => setEditModal(prev => prev ? {
                  ...prev,
                  value: { ...(prev.value as ExampleData), analysis: e.target.value }
                } : null)}
                InputProps={{ sx: { color: 'white' } }}
                InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.5)' } }}
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button
            onClick={handleCloseEditModal}
            sx={{ color: 'rgba(255,255,255,0.7)' }}
            disabled={modalSaving}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveEditModal}
            disabled={modalSaving}
            startIcon={modalSaving ? <CircularProgress size={16} /> : <Save />}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
