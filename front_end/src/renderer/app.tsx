// src/renderer/app.tsx
import React from 'react';
import { Box } from '@mui/material';
import { Homepage } from './Homepage';
import { TopBar } from './TopBar';
import { ChatDrawer, DEFAULT_WIDTH } from '../components/ChatDrawer';
import { useChat } from './contexts/ChatContext';

export function App() {
  const { isOpen, drawerWidth, isMaximized } = useChat();

  const pushWidth = Math.min(drawerWidth, DEFAULT_WIDTH);
  const contentWidth = isOpen && !isMaximized
    ? `calc(100% - ${pushWidth}px)`
    : '100%';

  return (
    <>
      <Box
        sx={{
          width: contentWidth,
          transition: 'width 225ms cubic-bezier(0, 0, 0.2, 1)',
          overflow: 'hidden',
        }}
      >
        <TopBar />
        <Homepage />
      </Box>
      <ChatDrawer />
    </>
  );
}
