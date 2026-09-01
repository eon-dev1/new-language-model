/**
 * Chat Context - Manages chat state, messages, streaming, and conversation persistence.
 *
 * Conversations are global (not scoped to language) and persisted in MongoDB.
 * App context (current view, language, book, chapter) is sent per-message.
 */

import React, { createContext, useContext, useState, useCallback, useRef, useEffect, type ReactNode } from 'react';
import {
  streamChat,
  submitToolResult,
  fetchConversations,
  createConversation,
  fetchConversation,
  deleteConversation as apiDeleteConversation,
  fetchChatConfig,
  fetchChatSkills,
  type ChatStreamEvent,
  type ConversationSummary,
  type QuickActionSkill,
} from '../api';

// ---------------------------------------------------------------------------
// Thinking support
// ---------------------------------------------------------------------------

const NO_THINKING_MODELS = new Set([
  'claude-haiku-4-5-20251001',
  'anthropic/claude-haiku-4.5',
]);

export type ChatMode = 'think' | 'think_harder' | 'maximum_thinking' | 'deep_research' | null;

export const isThinkingSupported = (model: string | null, provider?: string): boolean => {
  if (!model) return false;
  if (provider === 'local') return false;
  if (NO_THINKING_MODELS.has(model)) return false;
  if (model.startsWith('qwen/')) return false;
  return true;
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: string[];
  currentTool?: string | null;  // Ephemeral display state (streaming only)
  isError?: boolean;
  thinkingContent?: string;
  isContextNote?: boolean;
}

export interface AppContext {
  languageCode: string | null;
  bookCode: string | null;
  chapter: number | null;
  view: string | null;
}

export interface ToolResultEntry {
  id: string;        // unique key for AnimatePresence
  toolName: string;
  preview: string;   // raw JSON string, max 500 chars
  timestamp: number;
}

export interface PendingToolApproval {
  callId: string;
  toolName: string;
  input: Record<string, unknown>;
}

export interface ChatContextType {
  // Drawer
  isOpen: boolean;
  toggleChat: () => void;
  openChat: () => void;
  closeChat: () => void;

  // Drawer sizing
  drawerWidth: number;
  isMaximized: boolean;
  setDrawerWidth: (w: number) => void;
  toggleMaximize: () => void;

  // Messages
  messages: ChatMessage[];
  clearMessages: () => void;
  injectContextNote: (text: string) => void;

  // Streaming
  isStreaming: boolean;
  sendMessage: (text: string) => void;
  cancelStream: () => void;
  pipeToChat: (
    userLabel: string | null,
    gen: AsyncGenerator<ChatStreamEvent>,
    opts?: {
      abortController?: AbortController;
      onProposalEvent?: (event: ChatStreamEvent) => void;
    }
  ) => Promise<void>;

  // App context (set by viewers)
  appContext: AppContext;
  setAppContext: (ctx: Partial<AppContext>) => void;

  // Quick actions
  quickActions: QuickActionSkill[];

  // Tool approval
  pendingApproval: PendingToolApproval | null;
  approveToolCall: (callId: string, modifiedInput?: Record<string, unknown>) => void;
  rejectToolCall: (callId: string) => void;

  // Chat-initiated proposal handler (registered by BibleReader)
  registerProposalHandler: (fn: (event: ChatStreamEvent) => void) => void;
  unregisterProposalHandler: () => void;

  // Conversations
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  loadConversations: () => Promise<void>;
  startNewConversation: () => Promise<void>;
  openConversation: (id: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;

  // Mode
  chatMode: ChatMode;
  setChatMode: (mode: ChatMode) => void;
  currentModel: string | null;
  currentProvider: string;
  refreshCurrentModel: () => Promise<void>;
  thinkingEnabled: boolean;

  // Tool result preview
  toolResultBuffer: ToolResultEntry[];
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const ChatContext = createContext<ChatContextType | undefined>(undefined);

const DEFAULT_APP_CONTEXT: AppContext = {
  languageCode: null,
  bookCode: null,
  chapter: null,
  view: null,
};

let msgCounter = 0;
const nextId = () => `msg-${++msgCounter}`;

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export const ChatProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isOpen, setIsOpen] = useState(true);
  const [drawerWidth, setDrawerWidth] = useState(400);
  const [isMaximized, setIsMaximized] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [appContext, setAppContextState] = useState<AppContext>(DEFAULT_APP_CONTEXT);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const toolPreviewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [pendingApproval, setPendingApproval] = useState<PendingToolApproval | null>(null);
  const [chatMode, setChatModeState] = useState<ChatMode>(() => {
    const stored = localStorage.getItem('chat_mode');
    if (stored === 'think' || stored === 'think_harder') return stored;
    return null;
  });
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const [currentProvider, setCurrentProvider] = useState<string>('openrouter');
  const [thinkingEnabled, setThinkingEnabled] = useState<boolean>(true);
  const [availableSkills, setAvailableSkills] = useState<QuickActionSkill[]>([]);
  const [toolResultBuffer, setToolResultBuffer] = useState<ToolResultEntry[]>([]);

  useEffect(() => {
    fetchChatSkills()
      .then(setAvailableSkills)
      .catch(() => {});
  }, []);

  // External proposal handler (registered by BibleReader for chat-initiated verse translations)
  const proposalHandlerRef = useRef<((event: ChatStreamEvent) => void) | null>(null);
  const registerProposalHandler = useCallback((fn: (event: ChatStreamEvent) => void) => {
    proposalHandlerRef.current = fn;
  }, []);
  const unregisterProposalHandler = useCallback(() => {
    proposalHandlerRef.current = null;
  }, []);

  const toggleChat = useCallback(() => setIsOpen(prev => !prev), []);
  const openChat = useCallback(() => setIsOpen(true), []);
  const closeChat = useCallback(() => setIsOpen(false), []);
  const toggleMaximize = useCallback(() => setIsMaximized(prev => !prev), []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setActiveConversationId(null);
  }, []);

  const injectContextNote = useCallback((text: string) => {
    setMessages(prev => [
      ...prev,
      { id: nextId(), role: 'user', content: text, isContextNote: true },
    ]);
  }, []);

  const setAppContext = useCallback((ctx: Partial<AppContext>) => {
    setAppContextState(prev => ({ ...prev, ...ctx }));
  }, []);

  const clearToolPreviewTimer = useCallback(() => {
    if (toolPreviewTimerRef.current) {
      clearTimeout(toolPreviewTimerRef.current);
      toolPreviewTimerRef.current = null;
    }
  }, []);

  const resetToolPreviewTimer = useCallback(() => {
    if (toolPreviewTimerRef.current) clearTimeout(toolPreviewTimerRef.current);
    toolPreviewTimerRef.current = setTimeout(() => {
      setToolResultBuffer([]);
      toolPreviewTimerRef.current = null;
    }, 5000);
  }, []);

  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    clearToolPreviewTimer();
    setIsStreaming(false);
    setToolResultBuffer([]);
  }, [clearToolPreviewTimer]);

  const refreshCurrentModel = useCallback(async () => {
    try {
      const cfg = await fetchChatConfig();
      const model = cfg.llm_provider === 'local' ? cfg.local_model
        : cfg.openrouter_model;
      setCurrentModel(model);
      setCurrentProvider(cfg.llm_provider);
      setThinkingEnabled(cfg.thinking_enabled ?? true);
    } catch {
      // silent — model stays null, toggle stays disabled
    }
  }, []);

  // Fetch model config when drawer opens (separate from ChatDrawer's loadConversations effect)
  useEffect(() => {
    if (isOpen) {
      refreshCurrentModel();
    }
  }, [isOpen, refreshCurrentModel]);

  const setChatMode = useCallback((mode: ChatMode) => {
    setChatModeState(mode);
    if (mode === null) {
      localStorage.removeItem('chat_mode');
    } else {
      localStorage.setItem('chat_mode', mode);
    }
  }, []);

  // Conversation management
  const loadConversations = useCallback(async () => {
    try {
      const list = await fetchConversations();
      setConversations(list);
    } catch (err) {
      console.error('[Chat] Failed to load conversations:', err);
    }
  }, []);

  const startNewConversation = useCallback(async () => {
    try {
      const { id } = await createConversation();
      setActiveConversationId(id);
      setMessages([]);
      await loadConversations();
    } catch (err) {
      console.error('[Chat] Failed to create conversation:', err);
    }
  }, [loadConversations]);

  const openConversation = useCallback(async (id: string) => {
    try {
      const detail = await fetchConversation(id);
      setActiveConversationId(id);
      setMessages(detail.messages.map(m => ({
        id: nextId(),
        role: m.role,
        content: m.content,
        toolCalls: m.tool_calls,
        thinkingContent: m.thinking_content || undefined,
      })));
    } catch (err) {
      console.error('[Chat] Failed to open conversation:', err);
    }
  }, []);

  const deleteConversationHandler = useCallback(async (id: string) => {
    try {
      await apiDeleteConversation(id);
      if (activeConversationId === id) {
        setActiveConversationId(null);
        setMessages([]);
      }
      await loadConversations();
    } catch (err) {
      console.error('[Chat] Failed to delete conversation:', err);
    }
  }, [activeConversationId, loadConversations]);

  // Shared event-loop body for sendMessage / approveToolCall / rejectToolCall.
  // pipeToChat is intentionally excluded (different error prefix, no loadConversations).
  const processStreamEvents = useCallback(async (
    gen: AsyncIterable<ChatStreamEvent>,
    assistantId: string,
    signal: AbortSignal,
  ): Promise<void> => {
    for await (const event of gen) {
      if (signal.aborted) break;

      if (event.type === 'text') {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: m.content + event.content } : m
        ));
      } else if (event.type === 'thinking_delta') {
        setMessages(prev => prev.map(m =>
          m.id === assistantId
            ? { ...m, thinkingContent: (m.thinkingContent || '') + event.content! }
            : m
        ));
      } else if (event.type === 'tool_call') {
        setMessages(prev => prev.map(m =>
          m.id === assistantId
            ? {
                ...m,
                toolCalls: [...(m.toolCalls || []), event.name!],
                currentTool: event.name!
              }
            : m
        ));
      } else if (event.type === 'tool_approval') {
        if (event.tool_name === 'propose_verse_translation' && proposalHandlerRef.current) {
          proposalHandlerRef.current(event);
        } else {
          setPendingApproval({ callId: event.call_id!, toolName: event.tool_name!, input: event.input! });
        }
      } else if (event.type === 'tool_result') {
        setToolResultBuffer(prev => {
          const entry: ToolResultEntry = {
            id: `tr-${Date.now()}-${Math.random().toString(36).slice(2)}`,
            toolName: event.name!,
            preview: event.preview!,
            timestamp: Date.now(),
          };
          const next = [...prev, entry];
          return next.length > 5 ? next.slice(next.length - 5) : next;
        });
        resetToolPreviewTimer();
      } else if (event.type === 'error') {
        setMessages(prev => prev.map(m =>
          m.id === assistantId
            ? { ...m, content: m.content || event.content!, isError: true }
            : m
        ));
      } else if (event.type === 'done') {
        setMessages(prev => prev.map(m =>
          m.id === assistantId
            ? { ...m, currentTool: null }
            : m
        ));
      }
    }
  }, [setMessages, setPendingApproval, setToolResultBuffer, resetToolPreviewTimer]);

  const approveToolCall = useCallback((callId: string, modifiedInput?: Record<string, unknown>) => {
    if (!activeConversationId || isStreaming) return;
    setPendingApproval(null);
    setIsStreaming(true);

    const resumeAssistantId = nextId();
    setMessages(prev => [...prev, { id: resumeAssistantId, role: 'assistant', content: '', toolCalls: [] }]);

    const abort = new AbortController();
    abortRef.current = abort;

    (async () => {
      try {
        await processStreamEvents(
          submitToolResult(activeConversationId, callId, 'approve', modifiedInput, abort.signal),
          resumeAssistantId,
          abort.signal,
        );
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          setMessages(prev => prev.map(m =>
            m.id === resumeAssistantId
              ? { ...m, content: `Connection error: ${err.message}`, isError: true }
              : m
          ));
        }
      } finally {
        clearToolPreviewTimer();
        setToolResultBuffer([]);
        setIsStreaming(false);
        abortRef.current = null;
        loadConversations().catch(() => {});
      }
    })();
  }, [activeConversationId, isStreaming, loadConversations, clearToolPreviewTimer, processStreamEvents]);

  const rejectToolCall = useCallback((callId: string) => {
    if (!activeConversationId || isStreaming) return;
    setPendingApproval(null);
    setIsStreaming(true);

    const resumeAssistantId = nextId();
    setMessages(prev => [...prev, { id: resumeAssistantId, role: 'assistant', content: '', toolCalls: [] }]);

    const abort = new AbortController();
    abortRef.current = abort;

    (async () => {
      try {
        await processStreamEvents(
          submitToolResult(activeConversationId, callId, 'reject', undefined, abort.signal),
          resumeAssistantId,
          abort.signal,
        );
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          setMessages(prev => prev.map(m =>
            m.id === resumeAssistantId
              ? { ...m, content: `Connection error: ${err.message}`, isError: true }
              : m
          ));
        }
      } finally {
        clearToolPreviewTimer();
        setToolResultBuffer([]);
        setIsStreaming(false);
        abortRef.current = null;
        loadConversations().catch(() => {});
      }
    })();
  }, [activeConversationId, isStreaming, loadConversations, clearToolPreviewTimer, processStreamEvents]);

  const pipeToChat = useCallback(async (
    userLabel: string | null,
    gen: AsyncGenerator<ChatStreamEvent>,
    opts?: {
      abortController?: AbortController;
      onProposalEvent?: (event: ChatStreamEvent) => void;
    }
  ) => {
    if (isStreaming) return;  // guard against concurrent calls

    // Register caller's AbortController so chat Stop button works
    if (opts?.abortController) {
      abortRef.current = opts.abortController;
    }

    // Build messages
    const toAdd: ChatMessage[] = [];
    if (userLabel !== null) {
      toAdd.push({ id: nextId(), role: 'user', content: userLabel });
    }
    const assistantId = nextId();
    toAdd.push({ id: assistantId, role: 'assistant', content: '', toolCalls: [] });
    setMessages(prev => [...prev, ...toAdd]);
    setIsStreaming(true);
    setToolResultBuffer([]);

    try {
      for await (const event of gen) {
        if (opts?.abortController?.signal.aborted) break;

        if (event.type === 'text') {
          setMessages(prev => prev.map(m =>
            m.id === assistantId ? { ...m, content: m.content + event.content } : m
          ));
        } else if (event.type === 'tool_call') {
          setMessages(prev => prev.map(m =>
            m.id === assistantId
              ? { ...m, toolCalls: [...(m.toolCalls || []), event.name!], currentTool: event.name! }
              : m
          ));
        } else if (event.type === 'tool_result') {
          setToolResultBuffer(prev => {
            const entry: ToolResultEntry = {
              id: `tr-${Date.now()}-${Math.random().toString(36).slice(2)}`,
              toolName: event.name!,
              preview: event.preview!,
              timestamp: Date.now(),
            };
            const next = [...prev, entry];
            return next.length > 5 ? next.slice(next.length - 5) : next;
          });
          resetToolPreviewTimer();
        } else if (event.type === 'tool_approval') {
          if (event.tool_name === 'propose_verse_translation') {
            opts?.onProposalEvent?.(event);
          } else {
            // safety fallback for any other write tool
            setPendingApproval({ callId: event.call_id!, toolName: event.tool_name!, input: event.input! });
          }
        } else if (event.type === 'error') {
          setMessages(prev => prev.map(m =>
            m.id === assistantId
              ? { ...m, content: m.content || event.content!, isError: true }
              : m
          ));
        } else if (event.type === 'done') {
          setMessages(prev => prev.map(m =>
            m.id === assistantId ? { ...m, currentTool: null } : m
          ));
        }
        // context_usage, batch_system_prompt → ignored
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setMessages(prev => prev.map(m =>
          m.id === assistantId
            ? { ...m, content: `Translation error: ${err.message}`, isError: true }
            : m
        ));
      }
    } finally {
      clearToolPreviewTimer();
      setToolResultBuffer([]);
      setIsStreaming(false);
      abortRef.current = null;
      // NOTE: no loadConversations — translation is ephemeral
    }
  }, [isStreaming, clearToolPreviewTimer, resetToolPreviewTimer]);

  const sendMessage = useCallback((text: string) => {
    if (isStreaming) return;

    const userMsg: ChatMessage = { id: nextId(), role: 'user', content: text };
    const assistantId = nextId();
    const assistantMsg: ChatMessage = { id: assistantId, role: 'assistant', content: '', toolCalls: [] };

    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    // Build API message history (exclude empty assistant placeholder)
    const apiMessages = [...messages, userMsg].map(m => ({
      role: m.role,
      content: m.content,
    }));

    const abort = new AbortController();
    abortRef.current = abort;

    const context = {
      language_code: appContext.languageCode || undefined,
      book_code: appContext.bookCode || undefined,
      chapter: appContext.chapter || undefined,
      view: appContext.view || undefined,
    };

    // Double-guard: check model support at send time to avoid stale state issues
    const wantsThinking = chatMode === 'think' || chatMode === 'think_harder' || chatMode === 'maximum_thinking';
    const effectiveThinking = wantsThinking && thinkingEnabled && isThinkingSupported(currentModel, currentProvider);

    (async () => {
      setToolResultBuffer([]);
      // Auto-create conversation if none active
      let convId = activeConversationId;
      if (!convId) {
        try {
          const snippet = text.length > 40 ? text.slice(0, 40) + '...' : text;
          const { id } = await createConversation(snippet);
          convId = id;
          setActiveConversationId(id);
        } catch {
          // Continue without persistence
        }
      }

      try {
        await processStreamEvents(
          streamChat(apiMessages, context, abort.signal, convId || undefined, effectiveThinking, chatMode),
          assistantId,
          abort.signal,
        );
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          setMessages(prev => prev.map(m =>
            m.id === assistantId
              ? { ...m, content: `Connection error: ${err.message}`, isError: true }
              : m
          ));
        }
      } finally {
        clearToolPreviewTimer();
        setToolResultBuffer([]);
        setIsStreaming(false);
        abortRef.current = null;
        // Refresh conversation list to update timestamps
        loadConversations().catch(() => {});
      }
    })();
  }, [isStreaming, messages, appContext, activeConversationId, loadConversations,
      chatMode, currentModel, currentProvider, thinkingEnabled, clearToolPreviewTimer, processStreamEvents]);

  const quickActions = messages.length === 0
    ? availableSkills.filter(s =>
        s.views.length === 0 || s.views.includes(appContext.view ?? '')
      )
    : [];

  const value: ChatContextType = {
    isOpen, toggleChat, openChat, closeChat,
    drawerWidth, isMaximized, setDrawerWidth, toggleMaximize,
    messages, clearMessages, injectContextNote,
    isStreaming, sendMessage, cancelStream, pipeToChat,
    appContext, setAppContext,
    quickActions,
    pendingApproval, approveToolCall, rejectToolCall,
    registerProposalHandler, unregisterProposalHandler,
    conversations, activeConversationId,
    loadConversations, startNewConversation,
    openConversation, deleteConversation: deleteConversationHandler,
    chatMode, setChatMode,
    currentModel, currentProvider, refreshCurrentModel,
    thinkingEnabled,
    toolResultBuffer,
  };

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export const useChat = (): ChatContextType => {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};
