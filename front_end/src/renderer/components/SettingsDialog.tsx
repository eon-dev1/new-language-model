/**
 * SettingsDialog - Modal dialog for app font settings.
 *
 * Features:
 * - Font family selection (System Default, Times New Roman)
 * - Font size slider (12-24px)
 * - Preview text
 * - Reset to defaults
 */

import React from 'react';
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
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useSettings, type AppSettings } from '../contexts/SettingsContext';

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

  const handleFontFamilyChange = (event: { target: { value: string } }) => {
    updateSettings({ fontFamily: event.target.value as AppSettings['fontFamily'] });
  };

  const handleFontSizeChange = (_event: Event, value: number | number[]) => {
    updateSettings({ fontSize: value as number });
  };

  const handleReset = () => {
    resetSettings();
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
      </DialogContent>

      <DialogActions>
        <Button onClick={handleReset} color="secondary">
          Reset to Defaults
        </Button>
      </DialogActions>
    </Dialog>
  );
};
