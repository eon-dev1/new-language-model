import React from 'react';
import { Box, Paper, Button, CircularProgress, Typography } from '@mui/material';
import { AutoFixHigh } from '@mui/icons-material';

interface VerseSelectionToolbarProps {
  selectedCount: number;
  generatingBatch: boolean;
  onGenerate: () => void;
  onSelectAll: () => void;
  onSelectUnverified: () => void;
  onClearSelection: () => void;
  onAbort: () => void;
}

export function VerseSelectionToolbar({
  selectedCount,
  generatingBatch,
  onGenerate,
  onSelectAll,
  onSelectUnverified,
  onClearSelection,
  onAbort,
}: VerseSelectionToolbarProps) {
  return (
    <Paper
      elevation={2}
      sx={{
        p: 1.5,
        mb: 1,
        display: 'flex',
        gap: 1,
        alignItems: 'center',
        flexWrap: 'wrap',
      }}
    >
      {!generatingBatch && (
        <>
          {selectedCount > 0 && (
            <Button
              size="small"
              variant="contained"
              startIcon={<AutoFixHigh />}
              onClick={onGenerate}
            >
              Generate Selected ({selectedCount})
            </Button>
          )}
          <Button size="small" variant="outlined" onClick={onSelectAll}
            sx={{ color: 'rgba(255,255,255,0.8)', borderColor: 'rgba(255,255,255,0.3)' }}>
            Select All
          </Button>
          <Button size="small" variant="outlined" onClick={onSelectUnverified}
            sx={{ color: 'rgba(255,255,255,0.8)', borderColor: 'rgba(255,255,255,0.3)' }}>
            Select Unverified
          </Button>
          {selectedCount > 0 && (
            <Button size="small" variant="outlined" onClick={onClearSelection}
              sx={{ color: 'rgba(255,255,255,0.5)', borderColor: 'rgba(255,255,255,0.2)' }}>
              Unselect All
            </Button>
          )}
        </>
      )}
      {generatingBatch && (
        <>
          <CircularProgress size={16} sx={{ color: 'rgba(255,255,255,0.6)' }} />
          <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.7)', flexGrow: 1 }}>
            Batch translation in progress...
          </Typography>
          <Button size="small" variant="outlined" color="warning" onClick={onAbort}>
            Cancel
          </Button>
        </>
      )}
    </Paper>
  );
}
