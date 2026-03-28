/**
 * ChatDrawer - Right-side resizable drawer for chat interface.
 *
 * Contains: conversation list/switcher, message history, quick action chips,
 * text input with send/cancel, and settings panel.
 *
 * Features: drag-to-resize via left edge handle, maximize/minimize toggle,
 * overlay mode when expanded beyond default width.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box, Typography, TextField, IconButton, Chip, Divider,
  List, ListItemButton, ListItemText, ListItemSecondaryAction,
  Menu, MenuItem, Tooltip, CircularProgress,
} from '@mui/material';
import {
  Send, Stop, Add, Settings, ChatBubbleOutline,
  Delete, ArrowBack, Close, OpenInFull, CloseFullscreen,
} from '@mui/icons-material';
import { useChat } from '../renderer/contexts/ChatContext';
import { appendCorrectionLog, type AppendCorrectionLogRequest, type PerEntryCorrection } from '../renderer/api';
import type { ChatMode } from '../renderer/contexts/ChatContext';
import { useSettings } from '../renderer/contexts/SettingsContext';
import { ToolDataPreview } from './ToolDataPreview';
import { TOPBAR_HEIGHT } from '../renderer/constants';
import { ChatMessage } from './ChatMessage';
import { ChatSettings } from './ChatSettings';
import { ToolApprovalCard } from './ToolApprovalCard';

interface ModeButtonProps {
  label: string;
  active: boolean;
  onClick: () => void;
  disabled?: boolean;
}

const ModeButton: React.FC<ModeButtonProps> = ({ label, active, onClick, disabled }) => (
  <Box
    component="button"
    onClick={!disabled ? onClick : undefined}
    disabled={disabled}
    sx={{
      background: 'none',
      border: active ? '1px solid' : '1px solid transparent',
      borderColor: active ? 'primary.main' : 'transparent',
      borderRadius: '10px',
      px: 0.75,
      py: 0.25,
      mr: 0.5,
      cursor: disabled ? 'default' : 'pointer',
      opacity: disabled ? 0.25 : active ? 1 : 0.6,
      color: active ? 'primary.main' : 'text.secondary',
      fontSize: '0.75rem',
      fontFamily: 'inherit',
      lineHeight: 1.4,
      whiteSpace: 'nowrap',
      transition: 'border-color 0.15s, color 0.15s, opacity 0.15s',
      '&:hover:not(:disabled)': { opacity: active ? 1 : 0.85 },
    }}
  >
    {label}
  </Box>
);

export const DEFAULT_WIDTH = 400;
const MIN_WIDTH = 300;
const MAX_WIDTH_RATIO = 0.8;
const MAXIMIZED_RATIO = 2 / 3;

export const ChatDrawer: React.FC = () => {
  const {
    isOpen, closeChat,
    messages, clearMessages,
    isStreaming, sendMessage, cancelStream,
    quickActions,
    appContext, injectContextNote,
    pendingApproval, approveToolCall, rejectToolCall,
    conversations, activeConversationId,
    loadConversations, startNewConversation, openConversation, deleteConversation,
    drawerWidth, isMaximized, setDrawerWidth, toggleMaximize,
    chatMode, setChatMode,
    currentModel, currentProvider, refreshCurrentModel,
    toolResultBuffer,
  } = useChat();
  const { settings } = useSettings();

  const [input, setInput] = useState('');
  const [view, setView] = useState<'chat' | 'history' | 'settings'>('chat');
  const [deleteMenuAnchor, setDeleteMenuAnchor] = useState<null | HTMLElement>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Drag state
  const [isDragging, setIsDragging] = useState(false);
  const [windowWidth, setWindowWidth] = useState(window.innerWidth);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(0);

  // Auto-maximize guard: track which approval we already auto-maximized for
  const lastAutoMaxApprovalRef = useRef<string | null>(null);

  // Effective width calculation
  const effectiveWidth = isMaximized
    ? Math.round(windowWidth * MAXIMIZED_RATIO)
    : drawerWidth;

  // Load conversations when drawer opens
  useEffect(() => {
    if (isOpen) {
      loadConversations();
    }
  }, [isOpen, loadConversations]);

  // Refresh model config when returning to chat view (catches changes made in Settings)
  useEffect(() => {
    if (view === 'chat') {
      refreshCurrentModel();
    }
  }, [view, refreshCurrentModel]);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Window resize handler (rAF-throttled)
  useEffect(() => {
    let rafId = 0;
    const handleResize = () => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        setWindowWidth(window.innerWidth);
        const maxPx = window.innerWidth * MAX_WIDTH_RATIO;
        if (drawerWidth > maxPx) setDrawerWidth(Math.round(maxPx));
      });
    };
    window.addEventListener('resize', handleResize);
    return () => { window.removeEventListener('resize', handleResize); cancelAnimationFrame(rafId); };
  }, [drawerWidth, setDrawerWidth]);

  // Drag logic
  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    dragStartX.current = e.clientX;
    dragStartWidth.current = isMaximized ? Math.round(window.innerWidth * MAXIMIZED_RATIO) : drawerWidth;
    if (isMaximized) {
      setDrawerWidth(Math.round(window.innerWidth * MAXIMIZED_RATIO));
      toggleMaximize();
    }
  }, [drawerWidth, isMaximized, setDrawerWidth, toggleMaximize]);

  const handleDoubleClick = useCallback(() => {
    if (isMaximized) toggleMaximize();
    setDrawerWidth(DEFAULT_WIDTH);
  }, [isMaximized, toggleMaximize, setDrawerWidth]);

  const handleModeClick = useCallback((mode: ChatMode) => {
    setChatMode(chatMode === mode ? null : mode);
  }, [chatMode, setChatMode]);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const delta = dragStartX.current - e.clientX;
      const newWidth = Math.min(
        Math.max(dragStartWidth.current + delta, MIN_WIDTH),
        window.innerWidth * MAX_WIDTH_RATIO
      );
      setDrawerWidth(Math.round(newWidth));
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      // Snap to default if close
      const currentWidth = dragStartWidth.current + (dragStartX.current - dragStartX.current);
      // Read latest from DOM-synced state via a microtask isn't possible here,
      // so we just check in the next render cycle. The snap is handled below.
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };
  }, [isDragging, setDrawerWidth]);

  // Snap to default when drag ends and width is close
  useEffect(() => {
    if (!isDragging && Math.abs(drawerWidth - DEFAULT_WIDTH) < 20 && drawerWidth !== DEFAULT_WIDTH) {
      setDrawerWidth(DEFAULT_WIDTH);
    }
  }, [isDragging, drawerWidth, setDrawerWidth]);

  // Auto-maximize when agent presents proposed edits (tool approval)
  useEffect(() => {
    if (
      pendingApproval &&
      !isMaximized &&
      pendingApproval.callId !== lastAutoMaxApprovalRef.current
    ) {
      lastAutoMaxApprovalRef.current = pendingApproval.callId;
      toggleMaximize();
    }
  }, [pendingApproval, isMaximized, toggleMaximize]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput('');
    sendMessage(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleQuickAction = (prompt: string) => {
    if (isStreaming) return;
    sendMessage(prompt);
  };

  const handleDeleteClick = (e: React.MouseEvent<HTMLElement>, id: string) => {
    e.stopPropagation();
    setDeleteTargetId(id);
    setDeleteMenuAnchor(e.currentTarget);
  };

  const handleDeleteConfirm = () => {
    if (deleteTargetId) {
      deleteConversation(deleteTargetId);
    }
    setDeleteMenuAnchor(null);
    setDeleteTargetId(null);
  };

  // ---------------------------------------------------------------------------
  // Tool approval with correction capture
  // ---------------------------------------------------------------------------

  const handleToolApproval = useCallback((
    callId: string,
    modifiedInput?: Record<string, unknown>,
    correctionComment?: string,
  ) => {
    if (modifiedInput && pendingApproval && appContext.languageCode) {
      const toolName = pendingApproval.toolName;
      const originalInput = pendingApproval.input;
      let note: string | null = null;
      let logEntry: AppendCorrectionLogRequest | null = null;

      if (toolName === 'update_grammar_category') {
        const category = String(originalInput.category || 'unknown');
        const origContent = originalInput.content as Record<string, unknown> | undefined;
        const modContent = modifiedInput.content as Record<string, unknown> | undefined;
        const origText = String(origContent?.description || category);
        const corrText = String(modContent?.description || category);
        note = correctionComment?.trim()
          ? `[Correction note] Grammar/${category}: ${correctionComment}\nCorrected text: "${corrText}"`
          : `[Correction note] Grammar/${category} corrected. Corrected text: "${corrText}"`;
        if (correctionComment?.trim()) {
          logEntry = {
            content_type: 'grammar_category',
            content_reference: { category },
            original_text: origText,
            what_was_wrong: correctionComment.trim(),
            correction: corrText,
          };
        }
      } else {
        console.warn(`[ToolApproval] Edited tool "${toolName}" has no correction log handler`);
      }

      if (note) injectContextNote(note);
      if (logEntry) {
        appendCorrectionLog(appContext.languageCode, logEntry)
          .catch(err => console.error('Correction log save failed:', err));
      }
    }

    approveToolCall(callId, modifiedInput);
  }, [approveToolCall, pendingApproval, appContext.languageCode, injectContextNote]);

  const handleDictionarySubmit = useCallback((
    callId: string,
    modifiedInput: Record<string, unknown>,
    corrections: PerEntryCorrection[],
  ) => {
    if (corrections.length > 0 && appContext.languageCode) {
      const lines = corrections.map(c =>
        `  ${c.word}: ${c.comment} (was: "${c.originalText}" → "${c.correctedText}")`
      );
      const note = `[Correction note] Dictionary corrections:\n${lines.join('\n')}`;
      injectContextNote(note);

      for (const c of corrections) {
        appendCorrectionLog(appContext.languageCode, {
          content_type: 'dictionary_entry',
          content_reference: { word: c.word },
          original_text: c.originalText,
          what_was_wrong: c.comment,
          correction: c.correctedText,
        }).catch(err => console.error('Correction log save failed:', err));
      }
    }
    // else: corrections is empty — pure approve/reject with no edits, no note needed

    approveToolCall(callId, modifiedInput);
  }, [approveToolCall, appContext.languageCode, injectContextNote, appendCorrectionLog]);

  // ---------------------------------------------------------------------------
  // Maximize/minimize button (shared between headers)
  // ---------------------------------------------------------------------------

  const maximizeButton = (
    <Tooltip title={isMaximized ? "Default size" : "Expand"}>
      <IconButton size="small" onClick={toggleMaximize}>
        {isMaximized ? <CloseFullscreen fontSize="small" /> : <OpenInFull fontSize="small" />}
      </IconButton>
    </Tooltip>
  );

  // ---------------------------------------------------------------------------
  // Sub-views
  // ---------------------------------------------------------------------------

  const renderHistory = () => (
    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1.5, pb: 1 }}>
        <IconButton size="small" onClick={() => setView('chat')}>
          <ArrowBack fontSize="small" />
        </IconButton>
        <Typography variant="subtitle2" sx={{ flex: 1 }}>Conversations</Typography>
        <Tooltip title="New conversation">
          <IconButton size="small" onClick={() => { startNewConversation(); setView('chat'); }}>
            <Add fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
      <Divider />
      <List sx={{ flex: 1, overflowY: 'auto', py: 0 }}>
        {conversations.length === 0 ? (
          <Box sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="body2" sx={{ opacity: 0.5 }}>No conversations yet</Typography>
          </Box>
        ) : (
          conversations.map(conv => (
            <ListItemButton
              key={conv.id}
              selected={conv.id === activeConversationId}
              onClick={() => { openConversation(conv.id); setView('chat'); }}
              sx={{ pr: 6 }}
            >
              <ListItemText
                primary={conv.title}
                secondary={`${conv.message_count} messages`}
                primaryTypographyProps={{ variant: 'body2', noWrap: true }}
                secondaryTypographyProps={{ variant: 'caption' }}
              />
              <ListItemSecondaryAction>
                <IconButton
                  edge="end"
                  size="small"
                  onClick={(e) => handleDeleteClick(e, conv.id)}
                >
                  <Delete fontSize="small" sx={{ opacity: 0.4 }} />
                </IconButton>
              </ListItemSecondaryAction>
            </ListItemButton>
          ))
        )}
      </List>
      <Menu
        anchorEl={deleteMenuAnchor}
        open={Boolean(deleteMenuAnchor)}
        onClose={() => setDeleteMenuAnchor(null)}
      >
        <MenuItem onClick={handleDeleteConfirm} sx={{ color: 'error.main' }}>
          Delete conversation
        </MenuItem>
      </Menu>
    </Box>
  );

  const renderChat = () => {
    // Check if language selected
    if (!appContext.languageCode) {
      return (
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {/* Header */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1.5, pb: 1 }}>
            <ChatBubbleOutline sx={{ fontSize: 18, opacity: 0.5 }} />
            <Typography variant="subtitle2" sx={{ flex: 1 }}>Chat</Typography>
            <Tooltip title="History">
              <IconButton size="small" onClick={() => setView('history')}>
                <Typography variant="caption" sx={{ opacity: 0.6 }}>
                  {conversations.length || ''}
                </Typography>
              </IconButton>
            </Tooltip>
            <Tooltip title="Settings">
              <IconButton size="small" onClick={() => setView('settings')}>
                <Settings fontSize="small" />
              </IconButton>
            </Tooltip>
            {maximizeButton}
            <IconButton size="small" onClick={closeChat}>
              <Close fontSize="small" />
            </IconButton>
          </Box>
          <Divider />

          {/* Modes bar */}
          <Box sx={{ display: 'flex', alignItems: 'center', px: 1.5, py: 0.5, gap: 0.25, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
            <Typography variant="caption" sx={{ opacity: 0.4, mr: 1, fontSize: '0.65rem', letterSpacing: '0.08em', textTransform: 'uppercase', userSelect: 'none' }}>
              Modes
            </Typography>
            <ModeButton label="Think"            active={chatMode === 'think'}        onClick={() => handleModeClick('think')} />
            <ModeButton label="Think Harder"     active={chatMode === 'think_harder'} onClick={() => handleModeClick('think_harder')} />
            <ModeButton label="Maximum Thinking" active={false}                        onClick={() => {}} disabled />
            <ModeButton label="Deep Research"    active={false}                        onClick={() => {}} disabled />
          </Box>

          {/* Placeholder for no language */}
          <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: 3 }}>
            <Box sx={{ textAlign: 'center', maxWidth: 300 }}>
              <ChatBubbleOutline sx={{ fontSize: 60, opacity: 0.1, mb: 2 }} />
              <Typography variant="body1" sx={{ opacity: 0.6, mb: 1 }}>
                Select a language to enable chat features
              </Typography>
              <Typography variant="body2" sx={{ opacity: 0.4 }}>
                Chat tools and context require an active language project
              </Typography>
            </Box>
          </Box>

          {/* Input disabled */}
          <Divider />
          <Box sx={{ p: 1.5, display: 'flex', gap: 1, alignItems: 'flex-end' }}>
            <TextField
              fullWidth
              multiline
              maxRows={4}
              size="small"
              placeholder="Select a language first..."
              disabled
              sx={{ '& .MuiOutlinedInput-root': { fontSize: '0.875rem' } }}
            />
            <IconButton disabled size="small">
              <Send />
            </IconButton>
          </Box>
        </Box>
      );
    }

    // Normal chat UI when language is selected
    return (
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1.5, pb: 1 }}>
          <ChatBubbleOutline sx={{ fontSize: 18, opacity: 0.5 }} />
          <Typography variant="subtitle2" sx={{ flex: 1 }}>Chat</Typography>
          <Tooltip title="History">
            <IconButton size="small" onClick={() => setView('history')}>
              <Typography variant="caption" sx={{ opacity: 0.6 }}>
                {conversations.length || ''}
              </Typography>
            </IconButton>
          </Tooltip>
          <Tooltip title="New conversation">
            <IconButton size="small" onClick={startNewConversation}>
              <Add fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Settings">
            <IconButton size="small" onClick={() => setView('settings')}>
              <Settings fontSize="small" />
            </IconButton>
          </Tooltip>
          {maximizeButton}
          <IconButton size="small" onClick={closeChat}>
            <Close fontSize="small" />
          </IconButton>
        </Box>
        <Divider />

        {/* Modes bar */}
        <Box sx={{ display: 'flex', alignItems: 'center', px: 1.5, py: 0.5, gap: 0.25, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <Typography variant="caption" sx={{ opacity: 0.4, mr: 1, fontSize: '0.65rem', letterSpacing: '0.08em', textTransform: 'uppercase', userSelect: 'none' }}>
            Modes
          </Typography>
          <ModeButton label="Think"            active={chatMode === 'think'}        onClick={() => handleModeClick('think')} />
          <ModeButton label="Think Harder"     active={chatMode === 'think_harder'} onClick={() => handleModeClick('think_harder')} />
          <ModeButton label="Maximum Thinking" active={false}                        onClick={() => {}} disabled />
          <ModeButton label="Deep Research"    active={false}                        onClick={() => {}} disabled />
        </Box>

      {/* Messages */}
      <Box sx={{ flex: 1, overflowY: 'auto', p: 1.5, minHeight: 0 }}>
        {messages.length === 0 ? (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <ChatBubbleOutline sx={{ fontSize: 40, opacity: 0.15, mb: 1 }} />
            <Typography variant="body2" sx={{ opacity: 0.4, mb: 2 }}>
              Ask a question or use a quick action
            </Typography>
            {/* Quick actions when empty */}
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, justifyContent: 'center' }}>
              {quickActions.map(action => (
                <Chip
                  key={action.label}
                  label={action.label}
                  size="small"
                  variant="outlined"
                  onClick={() => handleQuickAction(action.prompt)}
                  sx={{ cursor: 'pointer' }}
                />
              ))}
            </Box>
          </Box>
        ) : (
          <>
            {messages.map(msg => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            {pendingApproval && (
              <ToolApprovalCard
                approval={pendingApproval}
                onApprove={handleToolApproval}
                onReject={rejectToolCall}
                onSubmitDictionary={handleDictionarySubmit}
              />
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </Box>


      {/* Input */}
      <Divider />
      <Box sx={{ p: 1.5, display: 'flex', gap: 1, alignItems: 'flex-end' }}>
        <TextField
          fullWidth
          multiline
          maxRows={4}
          size="small"
          placeholder={isStreaming ? 'Waiting for response...' : 'Type a message...'}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          sx={{
            '& .MuiOutlinedInput-root': {
              fontSize: '0.875rem',
            },
          }}
        />
        {isStreaming ? (
          <IconButton onClick={cancelStream} color="error" size="small">
            <Stop />
          </IconButton>
        ) : (
          <IconButton
            onClick={handleSend}
            disabled={!input.trim()}
            color="primary"
            size="small"
          >
            <Send />
          </IconButton>
        )}
      </Box>
    </Box>
    );
  };

  return (
    <Box
      sx={{
        position: 'fixed',
        top: TOPBAR_HEIGHT,
        right: 0,
        height: `calc(100% - ${TOPBAR_HEIGHT}px)`,
        width: effectiveWidth,
        transform: isOpen ? 'translateX(0)' : `translateX(100%)`,
        transition: isDragging
          ? 'none'
          : 'transform 225ms cubic-bezier(0, 0, 0.2, 1), width 225ms cubic-bezier(0, 0, 0.2, 1)',
        zIndex: 1200,
        background: 'linear-gradient(135deg, #222222, #333333)',
        boxShadow: '0 0 15px rgba(255, 255, 255, 0.05)',
        borderLeft: '1px solid rgba(255,255,255,0.1)',
        boxSizing: 'border-box',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Drag handle */}
      <Box
        onMouseDown={handleDragStart}
        onDoubleClick={handleDoubleClick}
        sx={{
          position: 'absolute',
          left: 0,
          top: 0,
          bottom: 0,
          width: 6,
          cursor: 'col-resize',
          zIndex: 10,
          '&:hover': {
            bgcolor: 'rgba(100, 150, 255, 0.15)',
          },
          '&::after': {
            content: '""',
            position: 'absolute',
            left: 2,
            top: '50%',
            transform: 'translateY(-50%)',
            width: 2,
            height: 40,
            borderRadius: 1,
            bgcolor: 'rgba(255,255,255,0.2)',
          },
        }}
      />

      <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        {view === 'history' && renderHistory()}
        {view === 'settings' && (
          <ChatSettings onBack={() => setView('chat')} />
        )}
        {view === 'chat' && renderChat()}
      </Box>

      {settings.toolPreviewEnabled && (
        <ToolDataPreview
          buffer={toolResultBuffer}
          isStreaming={isStreaming}
          drawerWidth={effectiveWidth}
          isDrawerOpen={isOpen}
        />
      )}
    </Box>
  );
};
