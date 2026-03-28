import React from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  CircularProgress,
  Tooltip,
  IconButton,
  Chip,
} from '@mui/material';
import { Save, Cancel, Edit, AutoFixHigh } from '@mui/icons-material';
import type { VerseData } from '../renderer/api';
import type { BatchGenerationActions, ProposalActions } from './useBatchTranslation';
import { CopyIconButton } from './CopyIconButton';

interface VerseTranslationCellProps {
  verse: VerseData;
  generation: BatchGenerationActions;
  proposal: ProposalActions;
  editingVerse: number | null;
  editText: string;
  savingVerse: boolean;
  onStartEdit: (verse: VerseData) => void;
  onCancelEdit: () => void;
  onSaveEdit: (verseNum: number) => void;
  onEditTextChange: (text: string) => void;
}

export const VerseTranslationCell = React.memo(function VerseTranslationCell({
  verse,
  generation,
  proposal,
  editingVerse,
  editText,
  savingVerse,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onEditTextChange,
}: VerseTranslationCellProps) {
  const genState = generation.verseGenStates.get(verse.verse);

  // ---- Queued state ----
  if (genState?.status === 'queued') {
    return (
      <Typography
        variant="caption"
        sx={{ color: 'rgba(255,255,255,0.35)', fontStyle: 'italic' }}
      >
        In queue...
      </Typography>
    );
  }

  // ---- Proposal ready state ----
  if (genState?.status === 'proposal_ready' && genState.proposal) {
    const { translated_text, confidence, rationale } = genState.proposal;
    const isFeedbackOpen = proposal.proposalFeedback?.verseNum === verse.verse;
    const feedbackMode = isFeedbackOpen ? proposal.proposalFeedback!.mode : null;

    return (
      <Box>
        {/* Proposed translation text */}
        <Typography variant="body1" sx={{ color: 'white', lineHeight: 1.7, mb: 0.75 }}>
          {translated_text}
        </Typography>

        {/* Confidence + rationale */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexWrap: 'wrap' }}>
          <Chip
            label={`${Math.round(confidence * 100)}% confidence`}
            size="small"
            sx={{
              bgcolor: confidence >= 0.8
                ? 'rgba(76,175,80,0.3)'
                : confidence >= 0.5
                ? 'rgba(255,193,7,0.3)'
                : 'rgba(244,67,54,0.3)',
              color: 'white',
              fontSize: '0.7rem',
            }}
          />
        </Box>
        {rationale && (
          <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.55)', display: 'block', mb: 1 }}>
            {rationale}
          </Typography>
        )}

        {/* Edit mode: editable text + feedback */}
        {feedbackMode === 'edit' && (
          <Box sx={{ mt: 1 }}>
            <TextField
              fullWidth
              multiline
              value={proposal.proposalFeedback?.editText ?? ''}
              onChange={(e) => proposal.setProposalFeedback(prev => prev ? { ...prev, editText: e.target.value } : prev)}
              label="Edit translation"
              size="small"
              autoFocus
              sx={{
                mb: 1,
                '& .MuiOutlinedInput-root': { bgcolor: 'rgba(255,255,255,0.05)' },
                '& .MuiInputBase-input': { color: 'white' },
                '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.6)' },
              }}
            />
            <TextField
              fullWidth
              multiline
              rows={2}
              value={proposal.proposalFeedback?.feedbackText ?? ''}
              onChange={(e) => proposal.setProposalFeedback(prev => prev ? { ...prev, feedbackText: e.target.value } : prev)}
              placeholder="Optional: describe the correction. This informs remaining verses."
              size="small"
              sx={{
                mb: 1,
                '& .MuiOutlinedInput-root': { bgcolor: 'rgba(255,255,255,0.05)' },
                '& .MuiInputBase-input': { color: 'rgba(255,255,255,0.8)', fontSize: '0.82rem' },
                '& .MuiInputBase-input::placeholder': { color: 'rgba(255,255,255,0.35)' },
              }}
            />
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                size="small"
                variant="contained"
                color="primary"
                onClick={() => proposal.handleEditAndSaveProposal(verse.verse, proposal.proposalFeedback?.editText ?? '', proposal.proposalFeedback?.feedbackText ?? '')}
                disabled={!proposal.proposalFeedback?.editText?.trim()}
              >
                Save Edit
              </Button>
              <Button
                size="small"
                variant="outlined"
                onClick={() => { proposal.setProposalFeedback(null); }}
                sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.3)' }}
              >
                Back
              </Button>
            </Box>
          </Box>
        )}

        {/* Reject mode: feedback textarea */}
        {feedbackMode === 'reject' && (
          <Box sx={{ mt: 1 }}>
            <TextField
              fullWidth
              multiline
              rows={2}
              value={proposal.proposalFeedback?.feedbackText ?? ''}
              onChange={(e) => proposal.setProposalFeedback(prev => prev ? { ...prev, feedbackText: e.target.value } : prev)}
              placeholder="Optional: explain why. This feedback informs remaining verses."
              size="small"
              autoFocus
              sx={{
                mb: 1,
                '& .MuiOutlinedInput-root': { bgcolor: 'rgba(255,255,255,0.05)' },
                '& .MuiInputBase-input': { color: 'rgba(255,255,255,0.8)', fontSize: '0.82rem' },
                '& .MuiInputBase-input::placeholder': { color: 'rgba(255,255,255,0.35)' },
              }}
            />
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                size="small"
                variant="outlined"
                color="error"
                onClick={() => proposal.handleRejectProposal(verse.verse, proposal.proposalFeedback?.feedbackText || undefined)}
              >
                Confirm Reject
              </Button>
              <Button
                size="small"
                variant="outlined"
                onClick={() => { proposal.setProposalFeedback(null); }}
                sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.3)' }}
              >
                Back
              </Button>
            </Box>
          </Box>
        )}

        {/* Main action buttons (Accept / Edit / Reject) — shown when feedback not open */}
        {!isFeedbackOpen && (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Button
              size="small"
              variant="contained"
              color="success"
              onClick={() => proposal.handleAcceptProposal(verse.verse)}
            >
              Accept
            </Button>
            <Button
              size="small"
              variant="outlined"
              onClick={() => {
                proposal.setProposalFeedback({ verseNum: verse.verse, mode: 'edit', editText: translated_text, feedbackText: '' });
              }}
              sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.4)' }}
            >
              Edit
            </Button>
            <Button
              size="small"
              variant="outlined"
              color="error"
              onClick={() => {
                proposal.setProposalFeedback({ verseNum: verse.verse, mode: 'reject', editText: '', feedbackText: '' });
              }}
            >
              Reject
            </Button>
          </Box>
        )}
      </Box>
    );
  }

  // ---- Error state ----
  if (genState?.status === 'error') {
    return (
      <Box>
        <Typography variant="caption" sx={{ color: 'rgba(255,80,80,0.9)', display: 'block', mb: 0.5 }}>
          {genState.errorMessage ?? 'Error'}
        </Typography>
        <Button
          size="small"
          variant="outlined"
          color="error"
          onClick={() => proposal.handleRetry(verse)}
        >
          Retry
        </Button>
      </Box>
    );
  }

  // ---- Normal display (with Edit + Generate buttons) ----
  if (editingVerse === verse.verse) {
    return (
      <Box>
        <TextField
          fullWidth
          multiline
          value={editText}
          onChange={(e) => onEditTextChange(e.target.value)}
          autoFocus
          sx={{ bgcolor: 'rgba(255,255,255,0.1)' }}
          InputProps={{ sx: { color: 'white' } }}
        />
        <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
          <Button
            size="small"
            variant="contained"
            startIcon={savingVerse ? <CircularProgress size={14} /> : <Save />}
            onClick={() => onSaveEdit(verse.verse)}
            disabled={savingVerse}
          >
            Save
          </Button>
          <Button
            size="small"
            variant="outlined"
            startIcon={<Cancel />}
            onClick={onCancelEdit}
            disabled={savingVerse}
            sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.3)' }}
          >
            Cancel
          </Button>
        </Box>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
      <Typography
        onClick={() => onStartEdit(verse)}
        variant="body1"
        sx={{
          color: 'white',
          lineHeight: 1.7,
          cursor: 'pointer',
          flexGrow: 1,
          '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' }
        }}
      >
        {verse.translated_text || <em style={{ opacity: 0.5 }}>(Click to add translation)</em>}
      </Typography>
      <Tooltip title="Edit translation">
        <IconButton
          size="small"
          onClick={() => onStartEdit(verse)}
          aria-label="Edit verse"
          sx={{ color: 'rgba(255,255,255,0.5)' }}
        >
          <Edit fontSize="small" />
        </IconButton>
      </Tooltip>
      {verse.english_text && (
        <Tooltip title="AI generate translation">
          <IconButton
            size="small"
            onClick={() => generation.handleGenerateVerse(verse)}
            aria-label="Generate translation"
            sx={{ color: 'rgba(180,140,255,0.7)', '&:hover': { color: 'rgba(180,140,255,1)' } }}
          >
            <AutoFixHigh fontSize="small" />
          </IconButton>
        </Tooltip>
      )}
      {verse.translated_text && <CopyIconButton text={verse.translated_text} />}
    </Box>
  );
});
