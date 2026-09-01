import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  Typography,
  LinearProgress,
  Alert,
  FormControlLabel,
  Checkbox
} from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import { selectFolder, importBible } from '../renderer/api';

interface NewProjectDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (languageCode: string) => void;
}

interface ImportState {
  status: 'idle' | 'importing' | 'success' | 'error';
  message: string;
}

export const NewProjectDialog: React.FC<NewProjectDialogProps> = ({
  open,
  onClose,
  onSuccess
}) => {
  console.log('[NewProjectDialog] Rendering, open =', open);
  const [languageName, setLanguageName] = useState('');
  const [folderPath, setFolderPath] = useState('');
  const [humanVerified, setHumanVerified] = useState(false);
  const [importState, setImportState] = useState<ImportState>({
    status: 'idle',
    message: ''
  });

  const handleSelectFolder = async () => {
    const path = await selectFolder();
    if (path) {
      setFolderPath(path);
    }
  };

  const handleImport = async () => {
    if (!languageName.trim() || !folderPath) {
      setImportState({
        status: 'error',
        message: 'Please fill in all required fields'
      });
      return;
    }

    setImportState({ status: 'importing', message: 'Importing USFM Bible data...' });

    try {
      const languageCode = languageName.toLowerCase().replace(/\s+/g, '_');

      const result = await importBible({
          language_code: languageCode,
          language_name: languageName,
          usfm_directory: folderPath,
          human_verified: humanVerified,
        });

      setImportState({
        status: 'success',
        message: result.message || `Imported ${result.verses_imported} verses`
      });

      setTimeout(() => {
        onSuccess(result.language_code);
        handleClose();
      }, 1500);

    } catch (error) {
      setImportState({
        status: 'error',
        message: error instanceof Error ? error.message : 'Import failed'
      });
    }
  };

  const handleClose = () => {
    setLanguageName('');
    setFolderPath('');
    setHumanVerified(false);
    setImportState({ status: 'idle', message: '' });
    onClose();
  };

  const isFormValid = languageName.trim() && folderPath;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Create New Language Project</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
          <TextField
            label="Language Name"
            value={languageName}
            onChange={(e) => setLanguageName(e.target.value)}
            placeholder="e.g., Bughotu, Kope, Spanish"
            fullWidth
            required
            disabled={importState.status === 'importing'}
          />

          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <TextField
              label="USFM Directory"
              value={folderPath}
              placeholder="Select folder containing USFM files..."
              fullWidth
              required
              disabled
              InputProps={{ readOnly: true }}
            />
            <Button
              variant="outlined"
              onClick={handleSelectFolder}
              disabled={importState.status === 'importing'}
              startIcon={<FolderOpenIcon />}
            >
              Browse
            </Button>
          </Box>

          <FormControlLabel
            control={
              <Checkbox
                checked={humanVerified}
                onChange={(e) => setHumanVerified(e.target.checked)}
                disabled={importState.status === 'importing'}
              />
            }
            label={
              <Box>
                <Typography variant="body2">Mark as pre-verified</Typography>
                <Typography variant="caption" color="text.secondary">
                  Check this if the translation has already been reviewed externally and does not need re-verification in this workflow.
                </Typography>
              </Box>
            }
          />

          {importState.status === 'importing' && (
            <Box>
              <Typography variant="body2" color="text.secondary">
                {importState.message}
              </Typography>
              <LinearProgress sx={{ mt: 1 }} />
            </Box>
          )}

          {importState.status === 'success' && (
            <Alert severity="success">{importState.message}</Alert>
          )}

          {importState.status === 'error' && (
            <Alert severity="error">{importState.message}</Alert>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={importState.status === 'importing'}>Cancel</Button>
        <Button
          onClick={handleImport}
          variant="contained"
          disabled={!isFormValid || importState.status === 'importing'}
        >
          {importState.status === 'importing' ? 'Importing...' : 'Create Project'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
