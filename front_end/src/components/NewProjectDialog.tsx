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
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio
} from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import { selectFolder, importBible, importHtmlBible } from '../renderer/api';

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
  const [format, setFormat] = useState<'usfm' | 'html'>('usfm');
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

    setImportState({ status: 'importing', message: `Importing ${format.toUpperCase()} Bible data...` });

    try {
      const languageCode = languageName.toLowerCase().replace(/\s+/g, '_');

      const result = format === 'usfm'
        ? await importBible({
            language_code: languageCode,
            language_name: languageName,
            usfm_directory: folderPath,
            translation_type: 'human'
          })
        : await importHtmlBible({
            language_code: languageCode,
            language_name: languageName,
            html_directory: folderPath,
            translation_type: 'human'
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
    setFormat('usfm');
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

          <FormControl disabled={importState.status === 'importing'}>
            <FormLabel>Bible Format</FormLabel>
            <RadioGroup
              row
              value={format}
              onChange={(e) => setFormat(e.target.value as 'usfm' | 'html')}
            >
              <FormControlLabel value="usfm" control={<Radio />} label="USFM files (.usfm, .SFM)" />
              <FormControlLabel value="html" control={<Radio />} label="HTML files (.htm)" />
            </RadioGroup>
          </FormControl>

          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <TextField
              label="Directory"
              value={folderPath}
              placeholder={format === 'usfm' ? 'Select folder containing USFM files...' : 'Select folder containing HTML files...'}
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
        <Button
          onClick={handleClose}
          disabled={importState.status === 'importing'}
        >
          Cancel
        </Button>
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
