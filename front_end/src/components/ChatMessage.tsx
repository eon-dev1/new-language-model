/**
 * ChatMessage - Renders a single chat message (user or assistant).
 *
 * Assistant messages show tool call indicators and error styling.
 * User messages are simple text bubbles.
 */

import React from 'react';
import { Box, Typography, Chip, Fade, Menu, MenuItem } from '@mui/material';
import { Person, AutoAwesome, Build, ErrorOutline, Lightbulb, Notes } from '@mui/icons-material';
import type { ChatMessage as ChatMessageType } from '../renderer/contexts/ChatContext';
import { CopyIconButton } from './CopyIconButton';

interface Props {
  message: ChatMessageType;
}

const ThinkingBlock: React.FC<{ content: string }> = ({ content }) => {
  const [isOpen, setIsOpen] = React.useState(true);
  return (
    <Box
      component="details"
      open={isOpen}
      onToggle={(e: React.SyntheticEvent) =>
        setIsOpen((e.currentTarget as HTMLDetailsElement).open)
      }
      sx={{
        mb: 0.5,
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 1,
        overflow: 'hidden',
      }}
    >
      <Box
        component="summary"
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          px: 1,
          py: 0.5,
          cursor: 'pointer',
          fontSize: '0.75rem',
          opacity: 0.6,
          userSelect: 'none',
          listStyle: 'none',
          '&::-webkit-details-marker': { display: 'none' },
          '&:hover': { opacity: 0.85 },
        }}
      >
        <Lightbulb sx={{ fontSize: 14 }} />
        Thinking
      </Box>
      <Box
        sx={{
          px: 1.5,
          py: 1,
          fontSize: '0.75rem',
          fontFamily: 'monospace',
          opacity: 0.6,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          borderTop: '1px solid rgba(255,255,255,0.08)',
          maxHeight: '12em',
          overflowY: 'auto',
        }}
      >
        {content}
      </Box>
    </Box>
  );
};

export const ChatMessage: React.FC<Props> = ({ message }) => {
  const isUser = message.role === 'user';
  const isEmpty = !message.content && !message.thinkingContent && !message.isError;
  const [menuAnchor, setMenuAnchor] = React.useState<{ x: number; y: number } | null>(null);

  if (message.isContextNote) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', mb: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.25, px: 0.5 }}>
          <Notes sx={{ fontSize: 14, opacity: 0.4 }} />
          <Typography variant="caption" sx={{ opacity: 0.4 }}>Context note</Typography>
        </Box>
        <Box
          sx={{
            maxWidth: '85%',
            px: 1.5,
            py: 1,
            borderRadius: 2,
            bgcolor: 'rgba(255,255,255,0.03)',
            border: '1px dashed rgba(255,255,255,0.12)',
          }}
        >
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', opacity: 0.6 }}>
            {message.content}
          </Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        mb: 1.5,
      }}
    >
      {/* Role indicator */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.25, px: 0.5 }}>
        {isUser ? (
          <Person sx={{ fontSize: 14, opacity: 0.5 }} />
        ) : (
          <AutoAwesome sx={{ fontSize: 14, opacity: 0.5 }} />
        )}
        <Typography variant="caption" sx={{ opacity: 0.5 }}>
          {isUser ? 'You' : 'Scribe'}
        </Typography>
      </Box>

      {/* Thinking block (renders above message bubble) */}
      {message.thinkingContent && (
        <ThinkingBlock content={message.thinkingContent} />
      )}

      {/* Message bubble — only renders when there is text or an error */}
      {(message.content || message.isError) && (
      <Box
        onContextMenu={(e) => { e.preventDefault(); setMenuAnchor({ x: e.clientX, y: e.clientY }); }}
        sx={{
          maxWidth: '85%',
          px: 1.5,
          py: 1,
          borderRadius: 2,
          bgcolor: isUser
            ? 'rgba(255,255,255,0.08)'
            : message.isError
              ? 'rgba(244,67,54,0.1)'
              : 'rgba(255,255,255,0.03)',
          border: '1px solid',
          borderColor: isUser
            ? 'rgba(255,255,255,0.12)'
            : message.isError
              ? 'rgba(244,67,54,0.3)'
              : 'rgba(255,255,255,0.06)',
        }}
      >
        {message.isError && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
            <ErrorOutline sx={{ fontSize: 14, color: 'error.main' }} />
            <Typography variant="caption" color="error">Error</Typography>
          </Box>
        )}

        {message.content ? (
          <Typography
            variant="body2"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontStyle: 'normal',
              '& p': { m: 0 },
            }}
          >
            {message.content}
          </Typography>
        ) : isEmpty ? (
          <Typography variant="body2" sx={{ opacity: 0.3, fontStyle: 'italic' }}>
            Thinking...
          </Typography>
        ) : null}
      </Box>
      )}

      <Menu
        open={Boolean(menuAnchor)}
        onClose={() => setMenuAnchor(null)}
        anchorReference="anchorPosition"
        anchorPosition={menuAnchor ? { top: menuAnchor.y, left: menuAnchor.x } : undefined}
      >
        <MenuItem onClick={() => { navigator.clipboard.writeText(message.content); setMenuAnchor(null); }}>
          Copy message
        </MenuItem>
        {window.getSelection()?.toString() && (
          <MenuItem onClick={() => { navigator.clipboard.writeText(window.getSelection()?.toString() ?? ''); setMenuAnchor(null); }}>
            Copy selected text
          </MenuItem>
        )}
      </Menu>

      {!isUser && message.content && <CopyIconButton text={message.content} />}

      {/* Current tool indicator (streaming only) */}
      {message.currentTool && (
        <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, px: 0.5 }}>
          <Fade in={true} timeout={300} key={message.currentTool}>
            <Chip
              icon={<Build sx={{ fontSize: '14px !important' }} />}
              label={message.currentTool.replace(/_/g, ' ')}
              size="small"
              variant="outlined"
              sx={{
                height: 20,
                fontSize: '0.7rem',
                opacity: 0.6,
                '& .MuiChip-label': { px: 0.75 },
                '& .MuiChip-icon': { ml: 0.5 },
              }}
            />
          </Fade>
        </Box>
      )}
    </Box>
  );
};
