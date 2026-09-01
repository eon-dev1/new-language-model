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

const TITLE_MAX = 200;

export function NotesTab({ languageCode }: NotesTabProps) {
  const [notes, setNotes] = useState<LanguageNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add form state
  const [addingNew, setAddingNew] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newText, setNewText] = useState('');
  const [addSaving, setAddSaving] = useState(false);

  // Inline edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
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
    if (!newTitle.trim() || !newText.trim()) return;
    setAddSaving(true);
    try {
      const trimmedTitle = newTitle.trim();
      const trimmedText = newText.trim();
      const result = await addNote(languageCode, trimmedTitle, trimmedText);
      const now = new Date().toISOString();
      const newNote: LanguageNote = {
        id: result.note_id,
        title: trimmedTitle,
        text: trimmedText,
        created_at: now,
        updated_at: now,
      };
      setNotes(prev => [...prev, newNote]);
      setNewTitle('');
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
    setEditTitle(note.title);
    setEditText(note.text);
  };

  const handleSaveEdit = async (noteId: string) => {
    if (!editTitle.trim() || !editText.trim()) return;
    setEditSaving(true);
    try {
      const trimmedTitle = editTitle.trim();
      const trimmedText = editText.trim();
      await updateNote(languageCode, noteId, trimmedTitle, trimmedText);
      setNotes(prev =>
        prev.map(n =>
          n.id === noteId
            ? { ...n, title: trimmedTitle, text: trimmedText, updated_at: new Date().toISOString() }
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
    setEditTitle('');
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
                    label="Title"
                    value={editTitle}
                    onChange={e => setEditTitle(e.target.value)}
                    inputProps={{ maxLength: TITLE_MAX }}
                    sx={{ mb: 1 }}
                    InputProps={{ sx: { color: 'white' } }}
                    InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.7)' } }}
                    autoFocus
                  />
                  <TextField
                    fullWidth
                    multiline
                    rows={3}
                    label="Body"
                    value={editText}
                    onChange={e => setEditText(e.target.value)}
                    sx={{ mb: 1 }}
                    InputProps={{ sx: { color: 'white' } }}
                    InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.7)' } }}
                  />
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button
                      size="small"
                      variant="contained"
                      startIcon={editSaving ? <CircularProgress size={14} /> : <Save />}
                      onClick={() => handleSaveEdit(note.id)}
                      disabled={editSaving || !editTitle.trim() || !editText.trim()}
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
                  <Typography
                    variant="subtitle1"
                    sx={{ color: 'white', fontWeight: 600, mb: 0.5, whiteSpace: 'pre-wrap' }}
                  >
                    {note.title}
                  </Typography>
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
                label="Title"
                placeholder="Short heading…"
                value={newTitle}
                onChange={e => setNewTitle(e.target.value)}
                inputProps={{ maxLength: TITLE_MAX }}
                sx={{ mb: 1 }}
                InputProps={{ sx: { color: 'white' } }}
                InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.7)' } }}
                autoFocus
              />
              <TextField
                fullWidth
                multiline
                rows={3}
                label="Body"
                placeholder="Enter your note..."
                value={newText}
                onChange={e => setNewText(e.target.value)}
                sx={{ mb: 1 }}
                InputProps={{ sx: { color: 'white' } }}
                InputLabelProps={{ sx: { color: 'rgba(255,255,255,0.7)' } }}
              />
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  size="small"
                  variant="contained"
                  startIcon={addSaving ? <CircularProgress size={14} /> : <Save />}
                  onClick={handleAdd}
                  disabled={addSaving || !newTitle.trim() || !newText.trim()}
                >
                  Save
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<Cancel />}
                  onClick={() => { setAddingNew(false); setNewTitle(''); setNewText(''); }}
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
