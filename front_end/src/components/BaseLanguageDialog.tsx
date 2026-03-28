import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  LinearProgress,
  Alert,
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio
} from '@mui/material';
import { ensureBaseLanguage } from '../renderer/api';

const AVAILABLE_BASE_LANGUAGES = [
  {
    code: 'english',
    name: 'English',
    description: 'World English Bible (WEB)',
  },
  // future: { code: 'hebrew', name: 'Hebrew', description: 'Westminster Leningrad Codex' }
  // future: { code: 'greek',  name: 'Greek',  description: 'SBL Greek New Testament' }
];

interface BaseLanguageDialogProps {
  open: boolean;
  onClose: () => void;
}

export const BaseLanguageDialog: React.FC<BaseLanguageDialogProps> = (props) => {
  const [selectedBase, setSelectedBase] = useState('english');
  const [ensureState, setEnsureState] = useState<{
    status: 'idle' | 'loading' | 'success' | 'error';
    message: string;
  }>({ status: 'idle', message: '' });

  const handleClose = () => {
    setSelectedBase('english');
    setEnsureState({ status: 'idle', message: '' });
    props.onClose();
  };

  const handleLoad = async () => {
    setEnsureState({ status: 'loading', message: 'Loading base language...' });
    try {
      const result = await ensureBaseLanguage(selectedBase);
      setEnsureState({ status: 'success', message: result.message });
    } catch (err) {
      setEnsureState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Failed to load base language'
      });
    }
  };

  const loadLabel =
    ensureState.status === 'loading' ? 'Loading...'
    : ensureState.status === 'success' ? 'Loaded ✓'
    : ensureState.status === 'error' ? 'Retry'
    : 'Load';

  return (
    <Dialog open={props.open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Base Languages</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <FormControl>
            <FormLabel>Select Base Language</FormLabel>
            <RadioGroup
              value={selectedBase}
              onChange={(e) => setSelectedBase(e.target.value)}
            >
              {AVAILABLE_BASE_LANGUAGES.map((lang) => (
                <FormControlLabel
                  key={lang.code}
                  value={lang.code}
                  control={<Radio />}
                  label={`${lang.name} — ${lang.description}`}
                  disabled={ensureState.status === 'loading'}
                />
              ))}
            </RadioGroup>
          </FormControl>

          {ensureState.status === 'loading' && (
            <Box>
              <Typography variant="body2" color="text.secondary">
                {ensureState.message}
              </Typography>
              <LinearProgress sx={{ mt: 1 }} />
            </Box>
          )}

          {ensureState.status === 'success' && (
            <Alert severity="success">{ensureState.message}</Alert>
          )}

          {ensureState.status === 'error' && (
            <Alert severity="error">{ensureState.message}</Alert>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={ensureState.status === 'loading'}>
          Close
        </Button>
        <Button
          onClick={handleLoad}
          variant="contained"
          disabled={ensureState.status === 'loading' || ensureState.status === 'success'}
        >
          {loadLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
