// MemoriesViewer.tsx
// Top-level Memories viewer. Owns AppBar ("Memories" title + back button).
// Three MUI Tabs: Grammar / Notes / Correction Log.

import React, { useState } from 'react';
import {
  Box,
  Typography,
  IconButton,
  Chip,
  Tabs,
  Tab,
  Container
} from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { GrammarViewer } from './GrammarViewer';
import { NotesTab } from './NotesTab';
import { CorrectionLogTab } from './CorrectionLogTab';
import { TOPBAR_HEIGHT } from '../renderer/constants';

interface MemoriesViewerProps {
  languageCode: string;
  languageName: string;
  onBack: () => void;
}

type MemoriesTab = 'grammar' | 'notes' | 'correction_log';

export function MemoriesViewer({ languageCode, languageName, onBack }: MemoriesViewerProps) {
  const [activeTab, setActiveTab] = useState<MemoriesTab>('grammar');

  return (
    <Box
      sx={{
        height: '100vh',
        overflow: 'hidden',
        background: 'linear-gradient(135deg, #1A1A1A, #2D2D2D)',
        pt: `${TOPBAR_HEIGHT + 8}px`,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Header + Tabs — constrained to lg width */}
      <Box sx={{ flexShrink: 0 }}>
        <Container maxWidth="lg">
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2, pt: 1 }}>
            <IconButton onClick={onBack} sx={{ mr: 2, color: 'white' }}>
              <ArrowBack />
            </IconButton>
            <Typography variant="h4" component="h1" sx={{ color: 'white', flexGrow: 1 }}>
              Memories
            </Typography>
            <Chip
              label={languageName}
              sx={{ bgcolor: 'rgba(255,255,255,0.1)', color: 'white' }}
            />
          </Box>
          <Tabs
            value={activeTab}
            onChange={(_, v: MemoriesTab) => setActiveTab(v)}
            sx={{ borderBottom: 1, borderColor: 'rgba(255,255,255,0.2)' }}
          >
            <Tab
              value="grammar"
              label="Grammar"
              sx={{ color: 'rgba(255,255,255,0.7)', '&.Mui-selected': { color: '#9C27B0' } }}
            />
            <Tab
              value="notes"
              label="Notes"
              sx={{ color: 'rgba(255,255,255,0.7)', '&.Mui-selected': { color: '#2196F3' } }}
            />
            <Tab
              value="correction_log"
              label="Correction Log"
              sx={{ color: 'rgba(255,255,255,0.7)', '&.Mui-selected': { color: '#FF9800' } }}
            />
          </Tabs>
        </Container>
      </Box>

      {/* Tab content — fills remaining height */}
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {activeTab === 'grammar' && (
          <GrammarViewer
            languageCode={languageCode}
            languageName={languageName}
            onBack={() => {}}
            embeddedMode={true}
          />
        )}
        {activeTab === 'notes' && (
          <NotesTab languageCode={languageCode} />
        )}
        {activeTab === 'correction_log' && (
          <CorrectionLogTab languageCode={languageCode} />
        )}
      </Box>
    </Box>
  );
}
