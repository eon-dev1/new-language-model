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

import React, { useState, useEffect } from 'react';
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
  Card,
  CardContent,
  CardActionArea
} from '@mui/material';
import {
  ArrowBack,
  Edit,
  Save,
  Cancel,
  CheckCircle,
  CheckCircleOutline,
  Person,
  SmartToy,
  RecordVoiceOver,
  Extension,
  AccountTree,
  Psychology,
  Forum
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import {
  fetchGrammarCategories,
  saveGrammarCategory,
  verifyGrammarCategory,
  MergedGrammarCategory,
  GrammarCategoryVersion,
  SubcategoryItem,
  SubcategoryData,
  ExampleItem,
  ExampleData
} from '../renderer/api';

interface GrammarViewerProps {
  languageCode: string;
  languageName: string;
  onBack: () => void;
}

type ViewState = 'categories' | 'detail';
type TabValue = 'human' | 'ai';

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

// --- Type Guards and Helpers for Rich Data ---

/** Check if a subcategory is a rich object (AI-generated) vs simple string (human). */
function isSubcategoryData(item: SubcategoryItem): item is SubcategoryData {
  return typeof item === 'object' && item !== null && 'name' in item;
}

/** Check if an example is a rich object (AI-generated) vs simple string (human). */
function isExampleData(item: ExampleItem): item is ExampleData {
  return typeof item === 'object' && item !== null && 'bughotu' in item;
}

/** Check if a category version contains rich (non-editable) data. */
function hasRichData(version: GrammarCategoryVersion | undefined): boolean {
  if (!version) return false;
  const hasRichSubcats = version.subcategories?.some(isSubcategoryData) ?? false;
  const hasRichExamples = version.examples?.some(isExampleData) ?? false;
  return hasRichSubcats || hasRichExamples;
}

/** Get display label for a subcategory (handles both formats). */
function getSubcategoryLabel(item: SubcategoryItem): string {
  if (isSubcategoryData(item)) {
    return item.name.replace(/_/g, ' ');
  }
  return String(item).replace(/_/g, ' ');
}

export function GrammarViewer({ languageCode, languageName, onBack }: GrammarViewerProps) {
  // Navigation state
  const [view, setView] = useState<ViewState>('categories');
  const [selectedCategory, setSelectedCategory] = useState<MergedGrammarCategory | null>(null);
  const [activeTab, setActiveTab] = useState<TabValue>('human');

  // Data state
  const [categories, setCategories] = useState<MergedGrammarCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState({
    notes: '',
    examples: ''
  });
  const [saving, setSaving] = useState(false);

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
    // Default to human tab if exists, otherwise ai
    setActiveTab(category.human ? 'human' : 'ai');
    setView('detail');
    setIsEditing(false);
  };

  const handleBack = () => {
    if (view === 'detail') {
      setView('categories');
      setSelectedCategory(null);
      setIsEditing(false);
    } else {
      onBack();
    }
  };

  const handleTabChange = (_: React.SyntheticEvent, newValue: TabValue) => {
    setActiveTab(newValue);
    setIsEditing(false);
  };

  const handleStartEdit = () => {
    const currentVersion = activeTab === 'human' ? selectedCategory?.human : selectedCategory?.ai;
    setEditForm({
      notes: currentVersion?.notes?.join('\n') || '',
      examples: currentVersion?.examples?.join('\n') || ''
    });
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
  };

  const handleSave = async () => {
    if (!selectedCategory) return;

    setSaving(true);
    try {
      await saveGrammarCategory(languageCode, selectedCategory.name, {
        notes: editForm.notes.split('\n').filter(n => n.trim()),
        examples: editForm.examples.split('\n').filter(e => e.trim())
      });

      // Reload categories to get updated data
      await loadCategories();

      // Find the updated category and select it
      const updatedCategories = await fetchGrammarCategories(languageCode);
      const updated = updatedCategories.categories.find(c => c.name === selectedCategory.name);
      if (updated) {
        setSelectedCategory(updated);
        setActiveTab('human'); // Saved content is always human
      }

      setIsEditing(false);
    } catch (err) {
      console.error('Failed to save category:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleVerify = async () => {
    if (!selectedCategory) return;

    const currentVersion = activeTab === 'human' ? selectedCategory.human : selectedCategory.ai;
    if (!currentVersion) return;

    const newVerified = !currentVersion.human_verified;

    try {
      await verifyGrammarCategory(languageCode, selectedCategory.name, activeTab, newVerified);

      // Update local state
      setCategories(prev => prev.map(c => {
        if (c.name === selectedCategory.name) {
          const updated = { ...c };
          if (activeTab === 'human' && updated.human) {
            updated.human = { ...updated.human, human_verified: newVerified };
          } else if (activeTab === 'ai' && updated.ai) {
            updated.ai = { ...updated.ai, human_verified: newVerified };
          }
          return updated;
        }
        return c;
      }));

      // Update selected category
      setSelectedCategory(prev => {
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
      console.error('Failed to verify category:', err);
    }
  };

  // Get current version based on active tab
  const getCurrentVersion = (): GrammarCategoryVersion | undefined => {
    if (!selectedCategory) return undefined;
    return activeTab === 'human' ? selectedCategory.human : selectedCategory.ai;
  };

  // Format category name for display
  const formatCategoryName = (name: string): string => {
    return name.charAt(0).toUpperCase() + name.slice(1);
  };

  // Render category grid
  const renderCategoryGrid = () => (
    <Grid container spacing={2}>
      {categories.map((category) => {
        const config = CATEGORY_CONFIG[category.name] || {
          icon: <Psychology />,
          color: '#9E9E9E',
          description: category.name
        };
        const hasContent = category.human || category.ai;
        const isVerified = category.human?.human_verified || category.ai?.human_verified;

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
                      {isVerified && (
                        <CheckCircle sx={{ color: '#4CAF50', fontSize: 20 }} />
                      )}
                    </Box>
                    <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.6)', mb: 1 }}>
                      {config.description}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                      {category.human && (
                        <Chip
                          size="small"
                          icon={<Person sx={{ fontSize: 14 }} />}
                          label="Human"
                          sx={{ bgcolor: 'rgba(33,150,243,0.3)', color: 'white', fontSize: '0.7rem' }}
                        />
                      )}
                      {category.ai && (
                        <Chip
                          size="small"
                          icon={<SmartToy sx={{ fontSize: 14 }} />}
                          label="AI"
                          sx={{ bgcolor: 'rgba(255,152,0,0.3)', color: 'white', fontSize: '0.7rem' }}
                        />
                      )}
                      {!hasContent && (
                        <Chip
                          size="small"
                          label="Empty"
                          sx={{ bgcolor: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)', fontSize: '0.7rem' }}
                        />
                      )}
                    </Box>
                  </CardContent>
                </CardActionArea>
              </Card>
            </motion.div>
          </Grid>
        );
      })}
    </Grid>
  );

  // Render detail view
  const renderDetail = () => {
    const currentVersion = getCurrentVersion();
    const hasBothVersions = selectedCategory?.human && selectedCategory?.ai;
    const config = selectedCategory ? CATEGORY_CONFIG[selectedCategory.name] : null;

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
                  {selectedCategory?.human?.human_verified && (
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
                  {selectedCategory?.ai?.human_verified && (
                    <CheckCircle sx={{ fontSize: 16, color: '#4CAF50' }} />
                  )}
                </Box>
              }
              sx={{ color: 'white', '&.Mui-selected': { color: '#FF9800' } }}
            />
          </Tabs>
        )}

        {/* Source badge if only one version */}
        {!hasBothVersions && currentVersion && (
          <Chip
            icon={activeTab === 'human' ? <Person /> : <SmartToy />}
            label={activeTab === 'human' ? 'Human Content' : 'AI Content'}
            sx={{
              mb: 2,
              bgcolor: activeTab === 'human' ? 'rgba(33,150,243,0.3)' : 'rgba(255,152,0,0.3)',
              color: 'white'
            }}
          />
        )}

        {/* Empty state - no human or AI content */}
        {!hasBothVersions && !currentVersion && !isEditing && (
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
          // Edit form
          <Box>
            {/* Show "New Content" badge when creating from empty state */}
            {!currentVersion && (
              <Chip
                icon={<Edit />}
                label="New Content"
                sx={{ mb: 2, bgcolor: 'rgba(33,150,243,0.3)', color: 'white' }}
              />
            )}
            <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1 }}>
              Notes (one per line)
            </Typography>
            <TextField
              fullWidth
              value={editForm.notes}
              onChange={(e) => setEditForm(prev => ({ ...prev, notes: e.target.value }))}
              multiline
              rows={6}
              placeholder="Enter grammar notes..."
              sx={{ mb: 3 }}
              InputProps={{ sx: { color: 'white', bgcolor: 'rgba(255,255,255,0.05)' } }}
            />

            <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1 }}>
              Examples (one per line)
            </Typography>
            <TextField
              fullWidth
              value={editForm.examples}
              onChange={(e) => setEditForm(prev => ({ ...prev, examples: e.target.value }))}
              multiline
              rows={4}
              placeholder="Enter examples..."
              sx={{ mb: 3 }}
              InputProps={{ sx: { color: 'white', bgcolor: 'rgba(255,255,255,0.05)' } }}
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
            {currentVersion?.subcategories && currentVersion.subcategories.length > 0 && (
              <>
                <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1 }}>
                  Subcategories
                </Typography>
                {/* Check if subcategories are rich objects (AI) or simple strings (human) */}
                {currentVersion.subcategories.some(isSubcategoryData) ? (
                  // Rich format: render as expandable sections
                  <Box sx={{ mb: 3 }}>
                    {currentVersion.subcategories.map((sub, i) => {
                      if (isSubcategoryData(sub)) {
                        return (
                          <Box key={i} sx={{ mb: 2, p: 2, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1 }}>
                            <Typography variant="subtitle1" sx={{ color: 'white', fontWeight: 'bold', mb: 1 }}>
                              {sub.name.replace(/_/g, ' ')}
                            </Typography>
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
                          key={i}
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
                    {currentVersion.subcategories.map((sub, i) => (
                      <Chip
                        key={i}
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
            {currentVersion?.notes && currentVersion.notes.length > 0 ? (
              <Box component="ul" sx={{ color: 'white', pl: 2, mb: 3 }}>
                {currentVersion.notes.map((note, i) => (
                  <li key={i} style={{ marginBottom: '0.5rem' }}>{note}</li>
                ))}
              </Box>
            ) : (
              <Typography sx={{ color: 'rgba(255,255,255,0.5)', fontStyle: 'italic', mb: 3 }}>
                No notes yet
              </Typography>
            )}

            {/* Examples */}
            <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1 }}>
              Examples
            </Typography>
            {currentVersion?.examples && currentVersion.examples.length > 0 ? (
              currentVersion.examples.some(isExampleData) ? (
                // Rich format: render structured examples (AI-generated)
                <Box sx={{ mb: 3 }}>
                  {currentVersion.examples.map((ex, i) => {
                    if (isExampleData(ex)) {
                      return (
                        <Box key={i} sx={{ mb: 2, p: 2, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1 }}>
                          <Typography sx={{ color: 'white', fontWeight: 'bold' }}>
                            {ex.bughotu}
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
                      );
                    }
                    // Fallback for mixed arrays
                    return (
                      <li key={i} style={{ marginBottom: '0.5rem', color: 'white' }}>{String(ex)}</li>
                    );
                  })}
                </Box>
              ) : (
                // Simple format: render as list items (human-entered)
                <Box component="ul" sx={{ color: 'white', pl: 2, mb: 3 }}>
                  {currentVersion.examples.map((ex, i) => (
                    <li key={i} style={{ marginBottom: '0.5rem' }}>{String(ex)}</li>
                  ))}
                </Box>
              )
            ) : (
              <Typography sx={{ color: 'rgba(255,255,255,0.5)', fontStyle: 'italic', mb: 3 }}>
                No examples yet
              </Typography>
            )}

            <Divider sx={{ my: 3, bgcolor: 'rgba(255,255,255,0.2)' }} />

            {/* Action buttons */}
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
              <Button
                variant="outlined"
                startIcon={<Edit />}
                onClick={handleStartEdit}
                disabled={hasRichData(currentVersion)}
                sx={{
                  color: hasRichData(currentVersion) ? 'rgba(255,255,255,0.3)' : 'white',
                  borderColor: 'rgba(255,255,255,0.3)'
                }}
              >
                Edit
              </Button>
              {hasRichData(currentVersion) && (
                <Typography sx={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.85rem', fontStyle: 'italic' }}>
                  Rich AI content is read-only
                </Typography>
              )}
              <Button
                variant={currentVersion?.human_verified ? 'contained' : 'outlined'}
                startIcon={currentVersion?.human_verified ? <CheckCircle /> : <CheckCircleOutline />}
                onClick={handleVerify}
                color={currentVersion?.human_verified ? 'success' : 'inherit'}
                sx={!currentVersion?.human_verified ? { color: 'white', borderColor: 'rgba(255,255,255,0.3)' } : {}}
                disabled={!currentVersion}
              >
                {currentVersion?.human_verified ? 'Verified' : 'Verify'}
              </Button>
            </Box>
          </Box>
        ) : null}
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
            {view === 'detail' && selectedCategory
              ? `Grammar - ${formatCategoryName(selectedCategory.name)}`
              : 'Grammar System'}
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
              <Button variant="outlined" onClick={loadCategories}>
                Retry
              </Button>
            </Box>
          </Paper>
        ) : (
          <Paper elevation={3} sx={{ p: 3, bgcolor: 'rgba(255,255,255,0.05)' }}>
            {view === 'categories' && renderCategoryGrid()}
            {view === 'detail' && renderDetail()}
          </Paper>
        )}
      </Container>
    </Box>
  );
}
