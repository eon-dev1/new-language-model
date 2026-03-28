// NotesTab.tsx
// Notes CRUD UI. Inline add/edit/delete matching existing viewer patterns.
// No verify toggle — all notes are trusted on write.

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  IconButton,
  TextField,
  CircularProgress,
  Container
} from '@mui/material';
import { Add, Edit, Delete, Save, Cancel } from '@mui/icons-material';
import {
  fetchNotes,
  addNote,
  updateNote,
  deleteNote,
  LanguageNote
} from '../renderer/api';

interface NotesTabProps {
  languageCode: string;
}

export function NotesTab({ languageCode }: NotesTabProps) {
  const [notes, setNotes] = useState<LanguageNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add form state
  const [addingNew, setAddingNew] = useState(false);
  const [newText, setNewText] = useState('');
  const [addSaving, setAddSaving] = useState(false);

  // Inline edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [editSaving, setEditSaving] = useState(false);

  useEffect(() => {
    load();
  }, [languageCode]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchNotes(languageCode);
      setNotes(data.notes);
    } catch (err) {
      setError('Failed to load notes. Please check if the backend is running.');
      console.error('Failed to load notes:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async () => {
    if (!newText.trim()) return;
    setAddSaving(true);
    try {
      const result = await addNote(languageCode, newText.trim());
      const now = new Date().toISOString();
      const newNote: LanguageNote = {
        id: result.note_id,
        text: newText.trim(),
        created_at: now,
        updated_at: now,
      };
      setNotes(prev => [...prev, newNote]);
      setNewText('');
      setAddingNew(false);
    } catch (err) {
      console.error('Failed to add note:', err);
    } finally {
      setAddSaving(false);
    }
  };

  const handleStartEdit = (note: LanguageNote) => {
    setEditingId(note.id);
    setEditText(note.text);
  };

  const handleSaveEdit = async (noteId: string) => {
    if (!editText.trim()) return;
    setEditSaving(true);
    try {
      await updateNote(languageCode, noteId, editText.trim());
      setNotes(prev =>
        prev.map(n =>
          n.id === noteId
            ? { ...n, text: editText.trim(), updated_at: new Date().toISOString() }
            : n
        )
      );
      setEditingId(null);
    } catch (err) {
      console.error('Failed to update note:', err);
    } finally {
      setEditSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditText('');
  };

  const handleDelete = async (noteId: string) => {
    try {
      await deleteNote(languageCode, noteId);
      setNotes(prev => prev.filter(n => n.id !== noteId));
    } catch (err) {
      console.error('Failed to delete note:', err);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" py={8}>
        <CircularProgress color="primary" />
      </Box>
    );
  }

  if (error) {
    return (
      <Box py={4} textAlign="center">
        <Typography color="error">{error}</Typography>
        <Button variant="outlined" onClick={load} sx={{ mt: 2, color: 'white', borderColor: 'rgba(255,255,255,0.3)' }}>
          Retry
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%', overflowY: 'auto' }}>
      <Container maxWidth="lg">
        <Box sx={{ py: 2 }}>
          {notes.length === 0 && !addingNew && (
            <Paper sx={{ p: 4, bgcolor: 'rgba(255,255,255,0.05)', textAlign: 'center', mb: 2 }}>
              <Typography sx={{ color: 'rgba(255,255,255,0.5)', mb: 2 }}>
                No notes yet. Add your first note to capture language insights.
              </Typography>
            </Paper>
          )}

          {notes.map(note => (
            <Paper key={note.id} sx={{ p: 2, mb: 2, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 2 }}>
              {editingId === note.id ? (
                <Box>
                  <TextField
                    fullWidth
                    multiline
                    rows={3}
                    value={editText}
                    onChange={e => setEditText(e.target.value)}
                    sx={{ mb: 1 }}
                    InputProps={{ sx: { color: 'white' } }}
                    InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.7)' } }}
                    autoFocus
                  />
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button
                      size="small"
                      variant="contained"
                      startIcon={editSaving ? <CircularProgress size={14} /> : <Save />}
                      onClick={() => handleSaveEdit(note.id)}
                      disabled={editSaving || !editText.trim()}
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
                  <Typography sx={{ color: 'white', mb: 1.5, whiteSpace: 'pre-wrap' }}>
                    {note.text}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.4)', display: 'block', mb: 1.5 }}>
                    {new Date(note.updated_at).toLocaleDateString()}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<Edit />}
                      onClick={() => handleStartEdit(note)}
                      sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.3)' }}
                    >
                      Edit
                    </Button>
                    <IconButton
                      size="small"
                      onClick={() => handleDelete(note.id)}
                      sx={{ color: '#f44336' }}
                    >
                      <Delete />
                    </IconButton>
                  </Box>
                </Box>
              )}
            </Paper>
          ))}

          {/* Add note form */}
          {addingNew ? (
            <Paper sx={{ p: 2, mb: 2, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 2 }}>
              <TextField
                fullWidth
                multiline
                rows={3}
                label="Note"
                placeholder="Enter your note..."
                value={newText}
                onChange={e => setNewText(e.target.value)}
                sx={{ mb: 1 }}
                InputProps={{ sx: { color: 'white' } }}
                InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.7)' } }}
                autoFocus
              />
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  size="small"
                  variant="contained"
                  startIcon={addSaving ? <CircularProgress size={14} /> : <Save />}
                  onClick={handleAdd}
                  disabled={addSaving || !newText.trim()}
                >
                  Save
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<Cancel />}
                  onClick={() => { setAddingNew(false); setNewText(''); }}
                  disabled={addSaving}
                  sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.3)' }}
                >
                  Cancel
                </Button>
              </Box>
            </Paper>
          ) : (
            <Button
              variant="outlined"
              startIcon={<Add />}
              onClick={() => setAddingNew(true)}
              sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.3)' }}
            >
              Add Note
            </Button>
          )}
        </Box>
      </Container>
    </Box>
  );
}
