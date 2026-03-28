/**
 * SettingsDialog - Modal dialog for app font settings.
 *
 * Features:
 * - Font family selection (System Default, Times New Roman)
 * - Font size slider (12-24px)
 * - Preview text
 * - Reset to defaults
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Typography,
  Box,
  Divider,
  Alert,
  CircularProgress,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useSettings, type AppSettings } from '../contexts/SettingsContext';
import { fetchLanguages, rebuildWordIndex, selectFolder, exportUsfm, backupDatabase, type Language } from '../api';

export interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
}

const FONT_OPTIONS: Array<{ value: AppSettings['fontFamily']; label: string }> = [
  { value: 'system-ui', label: 'System Default' },
  { value: 'Times New Roman', label: 'Times New Roman' },
];

export const SettingsDialog: React.FC<SettingsDialogProps> = ({ open, onClose }) => {
  const { settings, updateSettings, resetSettings } = useSettings();

  // Word index rebuild state
  const [languages, setLanguages] = useState<Language[]>([]);
  const [selectedLanguage, setSelectedLanguage] = useState('');
  const [rebuilding, setRebuilding] = useState(false);
  const [rebuildResult, setRebuildResult] = useState<{ ok: boolean; message: string } | null>(null);

  // Export USFM state
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<{ ok: boolean; message: string } | null>(null);

  // Database backup state
  const [backingUp, setBackingUp] = useState(false);
  const [backupResult, setBackupResult] = useState<{ ok: boolean; message: string } | null>(null);

  useEffect(() => {
    if (open) {
      fetchLanguages()
        .then((langs) => {
          const nonBase = langs.filter((l) => !l.is_base_language);
          setLanguages(nonBase);
          if (nonBase.length === 1) setSelectedLanguage(nonBase[0].language_code);
        })
        .catch(() => {});
    }
  }, [open]);

  const handleFontFamilyChange = (event: { target: { value: string } }) => {
    updateSettings({ fontFamily: event.target.value as AppSettings['fontFamily'] });
  };

  const handleFontSizeChange = (_event: Event, value: number | number[]) => {
    updateSettings({ fontSize: value as number });
  };

  const handleReset = () => {
    resetSettings();
  };

  const handleExport = async () => {
    const dir = await selectFolder();
    if (!dir) return;

    setExporting(true);
    setExportResult(null);
    try {
      const result = await exportUsfm({ language_code: selectedLanguage, output_dir: dir });
      setExportResult({
        ok: result.success,
        message: result.success
          ? `Exported ${result.files_written} book(s) to ${dir}`
          : result.message,
      });
    } catch (err: any) {
      setExportResult({ ok: false, message: `Export failed: ${err.message}` });
    } finally {
      setExporting(false);
    }
  };

  const handleRebuild = async () => {
    if (!selectedLanguage) return;
    setRebuilding(true);
    setRebuildResult(null);
    try {
      const result = await rebuildWordIndex(selectedLanguage);
      setRebuildResult({
        ok: true,
        message: `Indexed ${result.words_indexed} words from ${result.verses_processed} verses (${(result.duration_ms / 1000).toFixed(1)}s)`,
      });
    } catch (err: any) {
      setRebuildResult({ ok: false, message: err.message });
    } finally {
      setRebuilding(false);
    }
  };

  const handleBackup = async () => {
    const dir = await selectFolder();
    if (!dir) return;

    setBackingUp(true);
    setBackupResult(null);
    try {
      const result = await backupDatabase(dir);
      setBackupResult({
        ok: result.success,
        message: result.success
          ? `Backup completed to ${result.backup_dir} (${(result.duration_ms / 1000).toFixed(1)}s)`
          : result.message,
      });
    } catch (err: any) {
      setBackupResult({ ok: false, message: `Backup failed: ${err.message}` });
    } finally {
      setBackingUp(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        Settings
        <IconButton aria-label="close" onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers>
        {/* Font Family Select */}
        <FormControl fullWidth sx={{ mb: 3 }}>
          <InputLabel id="font-family-label">Font Family</InputLabel>
          <Select
            labelId="font-family-label"
            id="font-family-select"
            value={settings.fontFamily}
            label="Font Family"
            onChange={handleFontFamilyChange}
          >
            {FONT_OPTIONS.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Font Size Slider */}
        <Box sx={{ mb: 3 }}>
          <Typography gutterBottom>
            Font Size: {settings.fontSize} px
          </Typography>
          <Slider
            value={settings.fontSize}
            onChange={handleFontSizeChange}
            min={12}
            max={24}
            step={1}
            valueLabelDisplay="auto"
            aria-label="Font Size"
          />
        </Box>

        {/* Preview */}
        <Box
          sx={{
            p: 2,
            border: 1,
            borderColor: 'divider',
            borderRadius: 1,
            backgroundColor: 'background.paper',
          }}
        >
          <Typography variant="body1">
            The quick brown fox jumps over the lazy dog.
          </Typography>
        </Box>

        {/* Word Index */}
        {languages.length > 0 && (
          <>
            <Divider sx={{ my: 3 }} />
            <Typography variant="subtitle2" gutterBottom>
              Word Index
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
              Rebuild the word index if search results seem stale or after manual data changes.
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              {languages.length > 1 && (
                <FormControl size="small" sx={{ minWidth: 160 }}>
                  <InputLabel>Language</InputLabel>
                  <Select
                    value={selectedLanguage}
                    label="Language"
                    onChange={(e) => setSelectedLanguage(e.target.value)}
                  >
                    {languages.map((l) => (
                      <MenuItem key={l.language_code} value={l.language_code}>
                        {l.language_name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}
              <Button
                variant="outlined"
                size="small"
                onClick={handleRebuild}
                disabled={rebuilding || !selectedLanguage}
              >
                {rebuilding ? <CircularProgress size={18} sx={{ mr: 0.5 }} /> : null}
                {rebuilding ? 'Rebuilding...' : languages.length === 1 ? `Rebuild Index (${languages[0].language_name})` : 'Rebuild Index'}
              </Button>
              <Button
                variant="outlined"
                size="small"
                onClick={handleExport}
                disabled={exporting || !selectedLanguage}
              >
                {exporting ? <CircularProgress size={18} sx={{ mr: 0.5 }} /> : null}
                {exporting ? 'Exporting...' : 'Export USFM'}
              </Button>
            </Box>
            {rebuildResult && (
              <Alert
                severity={rebuildResult.ok ? 'success' : 'error'}
                onClose={() => setRebuildResult(null)}
                sx={{ mt: 1 }}
              >
                {rebuildResult.message}
              </Alert>
            )}
            {exportResult && (
              <Alert
                severity={exportResult.ok ? 'success' : 'error'}
                onClose={() => setExportResult(null)}
                sx={{ mt: 1 }}
              >
                {exportResult.message}
              </Alert>
            )}
          </>
        )}

        {/* Database Backup */}
        <Divider sx={{ my: 3 }} />
        <Button
          variant="outlined"
          size="small"
          onClick={handleBackup}
          disabled={backingUp}
        >
          {backingUp ? <CircularProgress size={18} sx={{ mr: 0.5 }} /> : null}
          {backingUp ? 'Backing up...' : 'Backup Database'}
        </Button>
        {backupResult && (
          <Alert
            severity={backupResult.ok ? 'success' : 'error'}
            onClose={() => setBackupResult(null)}
            sx={{ mt: 1 }}
          >
            {backupResult.message}
          </Alert>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={handleReset} color="secondary">
          Reset to Defaults
        </Button>
      </DialogActions>
    </Dialog>
  );
};
