/**
 * ToolApprovalCard - Renders a write-tool approval request inline in the chat.
 *
 * Shows proposed data with approve/edit/reject actions.
 * Supports tool-specific renderers (dictionary entries table, grammar preview)
 * with a generic JSON fallback.
 */

import React, { useState } from 'react';
import {
  Box,
  Typography,
  IconButton,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Paper,
  Chip,
} from '@mui/material';
import { Check, Close, Edit, SmartToy } from '@mui/icons-material';
import type { PendingToolApproval } from '../renderer/contexts/ChatContext';
import type { PerEntryCorrection } from '../renderer/api';

interface EntryDecision {
  status: 'pending' | 'approved' | 'rejected';
  comment: string;    // per-entry correction comment
}

interface Props {
  approval: PendingToolApproval;
  onApprove: (callId: string, modifiedInput?: Record<string, unknown>, correctionComment?: string) => void;
  onReject: (callId: string) => void;
  onSubmitDictionary: (callId: string, modifiedInput: Record<string, unknown>, corrections: PerEntryCorrection[]) => void;
}

// Tool-friendly display names
const TOOL_LABELS: Record<string, string> = {
  upsert_dictionary_entries: 'Add dictionary entries',
  update_grammar_category: 'Update grammar',
};

export const ToolApprovalCard: React.FC<Props> = ({ approval, onApprove, onReject, onSubmitDictionary }) => {
  const [editing, setEditing] = useState(false);
  const [editedInput, setEditedInput] = useState<Record<string, unknown>>(
    () => JSON.parse(JSON.stringify(approval.input))
  );
  const [correctionComment, setCorrectionComment] = useState('');

  const isDictionary = approval.toolName === 'upsert_dictionary_entries';
  const originalEntries = (approval.input.entries || []) as Array<Record<string, string>>;

  const [entryDecisions, setEntryDecisions] = useState<EntryDecision[] | null>(() =>
    isDictionary
      ? originalEntries.map(() => ({ status: 'pending' as const, comment: '' }))
      : null
  );
  const [editingRows, setEditingRows] = useState<Set<number>>(new Set());

  const label = TOOL_LABELS[approval.toolName] || approval.toolName.replace(/_/g, ' ');
  const hasEdits = JSON.stringify(editedInput) !== JSON.stringify(approval.input);

  const handleApprove = () => {
    onApprove(approval.callId, hasEdits ? editedInput : undefined, hasEdits ? correctionComment : undefined);
  };

  const handleSubmit = () => {
    const entries = (editedInput.entries || []) as Array<Record<string, string>>;
    const approvedEntries: Array<Record<string, string>> = [];
    const corrections: PerEntryCorrection[] = [];

    for (let i = 0; i < entryDecisions!.length; i++) {
      const d = entryDecisions![i];
      if (d.status !== 'approved') continue;

      const entry = entries[i];
      if (!entry) continue;  // defensive — index-sync invariant
      approvedEntries.push({ ...entry, human_verified: true });

      const edited = JSON.stringify(entry) !== JSON.stringify(originalEntries[i]);
      if (edited && d.comment.trim()) {
        corrections.push({
          word: entry.word,
          comment: d.comment,
          originalText: `${originalEntries[i].word}: ${originalEntries[i].definition} (${originalEntries[i].part_of_speech || ''})`,
          correctedText: `${entry.word}: ${entry.definition} (${entry.part_of_speech || ''})`,
        });
      }
    }

    if (approvedEntries.length === 0) {
      onReject(approval.callId);
    } else {
      onSubmitDictionary(approval.callId, { ...editedInput, entries: approvedEntries }, corrections);
    }
  };

  const handleDecisionChange = (i: number, status: 'approved' | 'rejected') => {
    setEntryDecisions(prev => prev!.map((d, idx) =>
      idx === i ? { ...d, status } : d
    ));
  };

  const handleToggleEdit = (i: number) => {
    setEditingRows(prev => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
    // Auto-approve only from pending — never override rejected
    setEntryDecisions(prev => prev!.map((d, idx) =>
      idx === i && d.status === 'pending' ? { ...d, status: 'approved' } : d
    ));
  };

  const handleCommentChange = (i: number, comment: string) => {
    setEntryDecisions(prev => prev!.map((d, idx) =>
      idx === i ? { ...d, comment } : d
    ));
  };

  return (
    <Box
      sx={{
        mb: 1.5,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
      }}
    >
      {/* Role indicator */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.25, px: 0.5 }}>
        <SmartToy sx={{ fontSize: 14, opacity: 0.5 }} />
        <Typography variant="caption" sx={{ opacity: 0.5 }}>
          Approval Required
        </Typography>
      </Box>

      {/* Card */}
      <Paper
        variant="outlined"
        sx={{
          maxWidth: '95%',
          width: '100%',
          borderColor: 'warning.dark',
          bgcolor: 'rgba(255, 167, 38, 0.04)',
        }}
      >
        {/* Header */}
        {isDictionary ? (
          <Box sx={{ px: 1.5, py: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {label}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                size="small"
                variant="outlined"
                color="error"
                data-testid="dict-cancel"
                onClick={() => onReject(approval.callId)}
              >
                Cancel
              </Button>
              <Button
                size="small"
                variant="contained"
                color="success"
                data-testid="dict-submit"
                disabled={entryDecisions?.some(d => d.status === 'pending') ?? false}
                onClick={handleSubmit}
              >
                Submit
              </Button>
            </Box>
          </Box>
        ) : (
          <Box sx={{ px: 1.5, py: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {label}
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              <Tooltip title="Edit before approving">
                <IconButton
                  size="small"
                  onClick={() => { const next = !editing; setEditing(next); if (!next) setCorrectionComment(''); }}
                  sx={{ color: editing ? 'primary.main' : 'text.secondary' }}
                >
                  <Edit fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Reject">
                <IconButton
                  size="small"
                  onClick={() => onReject(approval.callId)}
                  sx={{ color: 'error.main' }}
                >
                  <Close fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title={hasEdits ? 'Approve with edits' : 'Approve'}>
                <IconButton
                  size="small"
                  onClick={handleApprove}
                  sx={{ color: 'success.main' }}
                >
                  <Check fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
        )}

        {/* Body — tool-specific rendering */}
        <Box sx={{ px: 1.5, pb: 1.5 }}>
          {approval.toolName === 'upsert_dictionary_entries' ? (
            <DictionaryEntriesRenderer
              input={editedInput}
              onChange={setEditedInput}
              entryDecisions={entryDecisions!}
              onDecisionChange={handleDecisionChange}
              editingRows={editingRows}
              onToggleEdit={handleToggleEdit}
              originalEntries={originalEntries}
              onCommentChange={handleCommentChange}
            />
          ) : approval.toolName === 'update_grammar_category' ? (
            <GrammarCategoryRenderer
              input={editedInput}
              editing={editing}
              onChange={setEditedInput}
            />
          ) : (
            <GenericRenderer
              input={editedInput}
              editing={editing}
              onChange={setEditedInput}
            />
          )}
          {!isDictionary && editing && hasEdits && (
            <TextField
              fullWidth
              multiline
              rows={2}
              placeholder="Optional: describe the correction"
              value={correctionComment}
              onChange={(e) => setCorrectionComment(e.target.value)}
              size="small"
              sx={{ mt: 1, '& textarea': { fontSize: '0.8rem' } }}
            />
          )}
        </Box>
      </Paper>
    </Box>
  );
};

// ---------------------------------------------------------------------------
// Dictionary entries renderer
// ---------------------------------------------------------------------------

interface DictionaryRendererProps {
  input: Record<string, unknown>;
  onChange: (input: Record<string, unknown>) => void;
  entryDecisions: EntryDecision[];
  onDecisionChange: (i: number, status: 'approved' | 'rejected') => void;
  editingRows: Set<number>;
  onToggleEdit: (i: number) => void;
  originalEntries: Array<Record<string, string>>;
  onCommentChange: (i: number, comment: string) => void;
}

interface RendererProps {
  input: Record<string, unknown>;
  editing: boolean;
  onChange: (input: Record<string, unknown>) => void;
}

const DictionaryEntriesRenderer: React.FC<DictionaryRendererProps> = ({
  input, onChange, entryDecisions, onDecisionChange, editingRows, onToggleEdit, originalEntries, onCommentChange,
}) => {
  const entries = (input.entries || []) as Array<Record<string, string>>;

  const updateEntry = (index: number, field: string, value: string) => {
    const updated = [...entries];
    updated[index] = { ...updated[index], [field]: value };
    onChange({ ...input, entries: updated });
  };

  return (
    <TableContainer sx={{ maxHeight: 400, overflowY: 'auto' }}>
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>
            <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 0.5 }}>Word</TableCell>
            <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 0.5 }}>Definition</TableCell>
            <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 0.5 }}>POS</TableCell>
            <TableCell sx={{ width: 96, py: 0.5 }} />
          </TableRow>
        </TableHead>
        <TableBody>
          {entries.map((entry, i) => {
            const decision = entryDecisions[i];
            const isEditing = editingRows.has(i);
            const isModified = JSON.stringify(entry) !== JSON.stringify(originalEntries[i]);

            const rowBg = decision.status === 'rejected'
              ? 'rgba(244, 67, 54, 0.08)'
              : decision.status === 'approved'
                ? isModified ? 'rgba(255, 167, 38, 0.12)' : 'rgba(76, 175, 80, 0.08)'
                : undefined;

            return (
              <React.Fragment key={i}>
                <TableRow sx={{ bgcolor: rowBg }}>
                  <TableCell sx={{ fontSize: '0.8rem', py: 0.5 }}>
                    {isEditing ? (
                      <TextField
                        size="small"
                        value={entry.word || ''}
                        onChange={e => updateEntry(i, 'word', e.target.value)}
                        variant="standard"
                        sx={{ '& input': { fontSize: '0.8rem' } }}
                      />
                    ) : (
                      <strong>{entry.word}</strong>
                    )}
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', py: 0.5 }}>
                    {isEditing ? (
                      <TextField
                        size="small"
                        value={entry.definition || ''}
                        onChange={e => updateEntry(i, 'definition', e.target.value)}
                        variant="standard"
                        fullWidth
                        sx={{ '& input': { fontSize: '0.8rem' } }}
                      />
                    ) : (
                      entry.definition
                    )}
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', py: 0.5 }}>
                    {isEditing ? (
                      <TextField
                        size="small"
                        value={entry.part_of_speech || ''}
                        onChange={e => updateEntry(i, 'part_of_speech', e.target.value)}
                        variant="standard"
                        sx={{ '& input': { fontSize: '0.8rem', width: 80 } }}
                      />
                    ) : (
                      <Typography variant="caption" sx={{ opacity: 0.7 }}>
                        {entry.part_of_speech}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell sx={{ py: 0.5 }}>
                    <Box sx={{ display: 'flex', gap: 0.25 }}>
                      <Tooltip title="Approve">
                        <IconButton
                          size="small"
                          data-testid={`entry-${i}-approve`}
                          onClick={() => onDecisionChange(i, 'approved')}
                          sx={{ color: decision.status === 'approved' ? 'success.main' : 'text.disabled' }}
                        >
                          <Check sx={{ fontSize: 14 }} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Reject">
                        <IconButton
                          size="small"
                          data-testid={`entry-${i}-reject`}
                          onClick={() => onDecisionChange(i, 'rejected')}
                          sx={{ color: decision.status === 'rejected' ? 'error.main' : 'text.disabled' }}
                        >
                          <Close sx={{ fontSize: 14 }} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Edit">
                        <IconButton
                          size="small"
                          data-testid={`entry-${i}-edit`}
                          onClick={() => onToggleEdit(i)}
                          sx={{ color: isEditing ? 'primary.main' : 'text.secondary' }}
                        >
                          <Edit sx={{ fontSize: 14 }} />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </TableCell>
                </TableRow>
                {isModified && (
                  <TableRow key={`${i}-comment`} sx={{ bgcolor: rowBg }}>
                    <TableCell colSpan={4} sx={{ py: 0.5, pt: 0, borderBottom: 'none' }}>
                      <TextField
                        fullWidth
                        size="small"
                        placeholder="Optional: describe the correction"
                        value={decision.comment}
                        onChange={e => onCommentChange(i, e.target.value)}
                        sx={{ '& input': { fontSize: '0.8rem' } }}
                      />
                    </TableCell>
                  </TableRow>
                )}
              </React.Fragment>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

// ---------------------------------------------------------------------------
// Grammar category renderer
// ---------------------------------------------------------------------------

const GrammarCategoryRenderer: React.FC<RendererProps> = ({ input, editing, onChange }) => {
  const content = (input.content || {}) as Record<string, unknown>;
  const category = String(input.category || '');

  const description = String(content.description || '');
  const subcategories = (content.subcategories || []) as Array<Record<string, string>>;
  const notes = (content.notes || []) as Array<Record<string, string> | string>;
  const examples = (content.examples || []) as Array<Record<string, string>>;

  // Helper: update content sub-field, preserving the rest of input
  const updateContent = (field: string, value: unknown) => {
    onChange({ ...input, content: { ...content, [field]: value } });
  };

  const updateSubcategory = (index: number, field: string, value: string) => {
    const updated = [...subcategories];
    updated[index] = { ...updated[index], [field]: value };
    updateContent('subcategories', updated);
  };

  return (
    <Box sx={{ maxHeight: 400, overflowY: 'auto' }}>
      {/* Header: category chip */}
      <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
        <Chip label={category} size="small" sx={{ textTransform: 'capitalize' }} />
      </Box>

      {/* Description */}
      <Typography variant="caption" sx={{ opacity: 0.6, display: 'block', mb: 0.5 }}>
        Description
      </Typography>
      {editing ? (
        <TextField size="small" fullWidth multiline rows={2}
          value={description}
          onChange={e => updateContent('description', e.target.value)}
          sx={{ mb: 1.5, '& textarea': { fontSize: '0.8rem' } }}
        />
      ) : (
        <Typography variant="body2" sx={{ fontSize: '0.8rem', mb: 1.5 }}>
          {description}
        </Typography>
      )}

      {/* Subcategories — table */}
      {subcategories.length > 0 && (
        <>
          <Typography variant="caption" sx={{ opacity: 0.6, display: 'block', mb: 0.5 }}>
            Subcategories
          </Typography>
          <TableContainer sx={{ mb: 1.5 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 0.5, width: '25%' }}>
                    Name
                  </TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 0.5 }}>
                    Content
                  </TableCell>
                  {editing && <TableCell sx={{ width: 32, py: 0.5 }} />}
                </TableRow>
              </TableHead>
              <TableBody>
                {subcategories.map((sub, i) => (
                  <TableRow key={i}>
                    <TableCell sx={{ fontSize: '0.8rem', py: 0.5, verticalAlign: 'top' }}>
                      {editing ? (
                        <TextField size="small" value={sub.name || ''}
                          onChange={e => updateSubcategory(i, 'name', e.target.value)}
                          variant="standard"
                          sx={{ '& input': { fontSize: '0.8rem' } }}
                        />
                      ) : (
                        <strong>{sub.name}</strong>
                      )}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.8rem', py: 0.5 }}>
                      {editing ? (
                        <TextField size="small" fullWidth multiline rows={2}
                          value={sub.content || ''}
                          onChange={e => updateSubcategory(i, 'content', e.target.value)}
                          variant="standard"
                          sx={{ '& textarea': { fontSize: '0.8rem' } }}
                        />
                      ) : (
                        sub.content
                      )}
                    </TableCell>
                    {editing && (
                      <TableCell sx={{ py: 0.5, verticalAlign: 'top' }}>
                        <IconButton size="small"
                          onClick={() => {
                            const updated = subcategories.filter((_, idx) => idx !== i);
                            updateContent('subcategories', updated);
                          }}
                          sx={{ color: 'error.main' }}>
                          <Close sx={{ fontSize: 14 }} />
                        </IconButton>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      {/* Notes — single multiline */}
      {(notes.length > 0 || editing) && (
        <>
          <Typography variant="caption" sx={{ opacity: 0.6, display: 'block', mb: 0.5 }}>
            Notes
          </Typography>
          {editing ? (
            <TextField size="small" fullWidth multiline rows={3}
              value={notes.map(n => typeof n === 'string' ? n : n.text || n).join('\n')}
              onChange={e => updateContent('notes',
                e.target.value.split('\n').map(text => ({ text, human_verified: false }))
              )}
              sx={{ mb: 1.5, '& textarea': { fontSize: '0.8rem' } }}
            />
          ) : (
            <Box component="ul" sx={{ m: 0, mb: 1.5, pl: 2 }}>
              {notes.map((n, i) => (
                <Typography key={i} component="li" variant="body2"
                  sx={{ fontSize: '0.8rem' }}>
                  {typeof n === 'string' ? n : n.text}
                </Typography>
              ))}
            </Box>
          )}
        </>
      )}

      {/* Examples — table */}
      {(examples.length > 0 || editing) && (
        <>
          <Typography variant="caption" sx={{ opacity: 0.6, display: 'block', mb: 0.5 }}>
            Examples
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 0.5 }}>
                    Source
                  </TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 0.5 }}>
                    English
                  </TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 0.5 }}>
                    Analysis
                  </TableCell>
                  {editing && <TableCell sx={{ width: 32, py: 0.5 }} />}
                </TableRow>
              </TableHead>
              <TableBody>
                {examples.map((ex, i) => (
                  <TableRow key={i}>
                    {['source_text', 'english', 'analysis'].map(field => (
                      <TableCell key={field} sx={{ fontSize: '0.8rem', py: 0.5 }}>
                        {editing ? (
                          <TextField size="small" fullWidth
                            value={ex[field] || ''}
                            onChange={e => {
                              const updated = [...examples];
                              updated[i] = { ...updated[i], [field]: e.target.value };
                              updateContent('examples', updated);
                            }}
                            variant="standard"
                            sx={{ '& input': { fontSize: '0.8rem' } }}
                          />
                        ) : (
                          ex[field]
                        )}
                      </TableCell>
                    ))}
                    {editing && (
                      <TableCell sx={{ py: 0.5 }}>
                        <IconButton size="small"
                          onClick={() => updateContent('examples',
                            examples.filter((_, idx) => idx !== i)
                          )}
                          sx={{ color: 'error.main' }}>
                          <Close sx={{ fontSize: 14 }} />
                        </IconButton>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}
    </Box>
  );
};

// ---------------------------------------------------------------------------
// Generic JSON renderer (fallback)
// ---------------------------------------------------------------------------

const GenericRenderer: React.FC<RendererProps> = ({ input, editing, onChange }) => {
  const [jsonText, setJsonText] = useState(() => JSON.stringify(input, null, 2));

  const handleChange = (value: string) => {
    setJsonText(value);
    try {
      onChange(JSON.parse(value));
    } catch {
      // Invalid JSON — keep the text but don't update
    }
  };

  if (editing) {
    return (
      <TextField
        multiline
        fullWidth
        size="small"
        value={jsonText}
        onChange={e => handleChange(e.target.value)}
        sx={{
          '& textarea': { fontSize: '0.75rem', fontFamily: 'monospace' },
        }}
      />
    );
  }

  return (
    <Typography
      variant="body2"
      component="pre"
      sx={{
        fontSize: '0.75rem',
        fontFamily: 'monospace',
        whiteSpace: 'pre-wrap',
        maxHeight: 200,
        overflowY: 'auto',
        opacity: 0.8,
      }}
    >
      {JSON.stringify(input, null, 2)}
    </Typography>
  );
};
