/**
 * useBatchTranslation — manages all AI generation, batch session, verse selection,
 * and proposal feedback state extracted from BibleReader.
 *
 * Does NOT call useChat() internally — all chat dependencies enter as params.
 */

import { useState, useCallback, useEffect, useMemo, type Dispatch, type SetStateAction } from 'react';
import {
  streamVerseTranslation,
  streamBatchTranslation,
  streamBatchResume,
  appendCorrectionLog,
  type BatchVerseItem,
  type BibleBookInfo,
  type VerseData,
  type ChatStreamEvent,
} from '../renderer/api';
import type { ChatContextType } from '../renderer/contexts/ChatContext';

// ---------------------------------------------------------------------------
// Exported types (also used by BibleReader JSX)
// ---------------------------------------------------------------------------

export interface VerseGenState {
  status: 'queued' | 'proposal_ready' | 'error';
  proposal: { translated_text: string; confidence: number; rationale: string } | null;
  errorMessage?: string;
}

export interface ProposalFeedback {
  verseNum: number;
  mode: 'reject' | 'edit';
  feedbackText: string;
  editText: string;
}

// ---------------------------------------------------------------------------
// Internal types
// ---------------------------------------------------------------------------

interface BatchSession {
  systemPrompt: string;
  systemPromptSig: string;
  messages: unknown[];
  pendingCallId: string;
  pendingVerseNumber: number;
  remainingVerses: BatchVerseItem[];
  abortController: AbortController;
}

// ---------------------------------------------------------------------------
// Return-object interfaces (exported for VerseTranslationCell in Step 4)
// ---------------------------------------------------------------------------

export interface BatchGenerationActions {
  verseGenStates: Map<number, VerseGenState>;
  generatingBatch: boolean;
  handleGenerateVerse: (verse: VerseData) => Promise<void>;
  handleGenerateBatch: () => Promise<void>;
  handleAbortBatch: () => void;
  clearAllGenStates: () => void;
}

export interface BatchSelectionActions {
  selectedVerses: Set<number>;
  handleVerseSelection: (verseNum: number, checked: boolean) => void;
  handleSelectAll: () => void;
  handleSelectAllUnverified: () => void;
  handleClearSelection: () => void;
}

export interface ProposalActions {
  proposalFeedback: ProposalFeedback | null;
  setProposalFeedback: Dispatch<SetStateAction<ProposalFeedback | null>>;
  handleAcceptProposal: (verseNum: number) => Promise<void>;
  handleEditAndSaveProposal: (verseNum: number, text: string, feedbackText: string) => Promise<void>;
  handleRejectProposal: (verseNum: number, feedback?: string) => Promise<void>;
  handleRetry: (verse: VerseData) => void;
}

// ---------------------------------------------------------------------------
// Params interface
// ---------------------------------------------------------------------------

interface UseBatchTranslationParams {
  languageCode: string;
  languageName: string;
  selectedBook: BibleBookInfo | null;
  selectedChapter: number;
  filteredVerses: VerseData[];
  isStreaming: boolean;
  isVersesView: boolean;
  pipeToChat: ChatContextType['pipeToChat'];
  openChat: () => void;
  registerProposalHandler: (fn: (event: ChatStreamEvent) => void) => void;
  unregisterProposalHandler: () => void;
  approveToolCall: (callId: string, input?: Record<string, unknown>) => void;
  rejectToolCall: (callId: string) => void;
  /** Saves a verse to the backend and updates local verse list state in BibleReader. */
  onSaveVerse: (verseNum: number, text: string) => Promise<void>;
  /** Clears the manual edit UI in BibleReader for a given verse number. */
  onClearVerseEdit: (verseNum: number) => void;
  /** Called after handleEditAndSaveProposal succeeds, to inject a correction note into chat. */
  onEditedProposal?: (
    ref: { book_code: string; chapter: number; verse: number },
    originalText: string,
    correctedText: string,
    feedbackText: string
  ) => void;
}

interface UseBatchTranslationReturn {
  generation: BatchGenerationActions;
  selection: BatchSelectionActions;
  proposal: ProposalActions;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useBatchTranslation({
  languageCode,
  languageName,
  selectedBook,
  selectedChapter,
  filteredVerses,
  isStreaming,
  isVersesView,
  pipeToChat,
  openChat,
  registerProposalHandler,
  unregisterProposalHandler,
  approveToolCall,
  rejectToolCall,
  onSaveVerse,
  onClearVerseEdit,
  onEditedProposal,
}: UseBatchTranslationParams): UseBatchTranslationReturn {

  const [verseGenStates, setVerseGenStates] = useState<Map<number, VerseGenState>>(new Map());
  const [selectedVerses, setSelectedVerses] = useState<Set<number>>(new Set());
  const [generatingBatch, setGeneratingBatch] = useState(false);
  const [batchSession, setBatchSession] = useState<BatchSession | null>(null);
  const [proposalFeedback, setProposalFeedback] = useState<ProposalFeedback | null>(null);
  const [chatProposalCallId, setChatProposalCallId] = useState<string | null>(null);

  // ---- Helper: clear only queued entries (used in non-success terminal paths) ----
  const clearQueuedStates = useCallback(() =>
    setVerseGenStates(prev => {
      const next = new Map(prev);
      for (const [k, v] of next) if (v.status === 'queued') next.delete(k);
      return next;
    }), []);

  // ---- clearAllGenStates: abort + full reset ----
  // Abort is done via setBatchSession functional updater to avoid needing batchSession in deps.
  // chatProposalCallId MUST be in deps (plan constraint) — reads current value at call time.
  const clearAllGenStates = useCallback(() => {
    setVerseGenStates(new Map());
    setSelectedVerses(new Set());
    setGeneratingBatch(false);
    setBatchSession(prev => {
      prev?.abortController.abort();
      return null;
    });
    if (chatProposalCallId) rejectToolCall(chatProposalCallId);
    setChatProposalCallId(null);
    setProposalFeedback(null);
  }, [chatProposalCallId, rejectToolCall]);

  // ---- Chat-initiated proposal handler ----
  useEffect(() => {
    if (!isVersesView) {
      unregisterProposalHandler();
      return;
    }
    registerProposalHandler((event) => {
      const input = event.input as {
        verse_number?: number;
        translated_text?: string;
        confidence?: number;
        rationale?: string;
      };
      const verseNum = input?.verse_number;
      if (!input?.translated_text || !verseNum) {
        console.warn('[useBatchTranslation] Chat proposal missing translated_text or verse_number — dropped');
        return;
      }
      setChatProposalCallId(event.call_id ?? null);
      setVerseGenStates(prev => new Map(prev).set(verseNum, {
        status: 'proposal_ready',
        proposal: {
          translated_text: input.translated_text!,
          confidence: input.confidence ?? 0,
          rationale: input.rationale ?? '',
        },
      }));
    });
    return () => unregisterProposalHandler();
  }, [isVersesView, registerProposalHandler, unregisterProposalHandler]);

  // ============================================================================
  // Verse selection handlers
  // ============================================================================

  const handleVerseSelection = useCallback((verseNum: number, checked: boolean) => {
    setSelectedVerses(prev => {
      const next = new Set(prev);
      if (checked) next.add(verseNum);
      else next.delete(verseNum);
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    setSelectedVerses(new Set(filteredVerses.map(v => v.verse)));
  }, [filteredVerses]);

  const handleSelectAllUnverified = useCallback(() => {
    setSelectedVerses(new Set(filteredVerses.filter(v => !v.human_verified).map(v => v.verse)));
  }, [filteredVerses]);

  const handleClearSelection = useCallback(() => {
    setSelectedVerses(new Set());
  }, []);

  const handleAbortBatch = useCallback(() => {
    setBatchSession(prev => {
      prev?.abortController.abort();
      return null;
    });
    setGeneratingBatch(false);
    setVerseGenStates(new Map());
  }, []);

  // ============================================================================
  // AI generation handlers
  // ============================================================================

  const handleGenerateVerse = useCallback(async (verse: VerseData) => {
    if (!selectedBook || !verse.english_text) return;
    if (isStreaming) return;  // guard: pipeToChat would silently no-op, causing false error state

    // Clear any open edit/proposal UI for this verse before starting
    onClearVerseEdit(verse.verse);
    setProposalFeedback(prev => prev?.verseNum === verse.verse ? null : prev);

    openChat();

    const controller = new AbortController();
    let proposalArrived = false;

    await pipeToChat(
      `Translating ${selectedBook.book_name} ${selectedChapter}:${verse.verse}`,
      streamVerseTranslation(
        languageCode, selectedBook.book_code, selectedChapter,
        verse.verse, verse.english_text, languageName, selectedBook.book_name,
        controller.signal,
      ),
      {
        abortController: controller,
        onProposalEvent: (event) => {
          const input = event.input as { translated_text?: string; confidence?: number; rationale?: string };
          if (!input?.translated_text) {
            console.warn('[useBatchTranslation] Single-verse proposal missing translated_text — dropped');
            return;
          }
          proposalArrived = true;
          setVerseGenStates(prev => new Map(prev).set(verse.verse, {
            status: 'proposal_ready',
            proposal: {
              translated_text: input.translated_text!,
              confidence: input.confidence ?? 0,
              rationale: input.rationale ?? '',
            },
          }));
        },
      }
    );

    if (!proposalArrived && !controller.signal.aborted) {
      setVerseGenStates(prev => new Map(prev).set(verse.verse, {
        status: 'error', proposal: null, errorMessage: 'LLM stopped without proposing — retry',
      }));
    }
  }, [selectedBook, selectedChapter, languageCode, languageName, isStreaming,
      pipeToChat, openChat, onClearVerseEdit]);

  const handleBatchResume = useCallback(async (
    verseNum: number,
    decision: 'approve' | 'reject',
    feedback?: string,
  ) => {
    if (!batchSession || !selectedBook) return;
    if (isStreaming) return;
    const { systemPrompt, systemPromptSig, messages, pendingCallId, remainingVerses } = batchSession;

    if (remainingVerses.length === 0) {
      setBatchSession(null);
      setGeneratingBatch(false);
      setSelectedVerses(new Set());
      return;
    }

    const resumeController = new AbortController();
    setBatchSession(prev => prev ? { ...prev, abortController: resumeController } : null);

    let nextProposalReceived = false;

    await pipeToChat(
      null,   // no user message — just a new assistant bubble
      streamBatchResume(
        languageCode, selectedBook.book_code, selectedChapter,
        messages, pendingCallId, verseNum, decision,
        systemPrompt, systemPromptSig, feedback,
        resumeController.signal,
      ),
      {
        abortController: resumeController,
        onProposalEvent: (event) => {
          const input = event.input as { verse_number?: number; translated_text?: string; confidence?: number; rationale?: string };
          const nextVerseNum = input?.verse_number;
          if (!input?.translated_text || !nextVerseNum) {
            console.warn('[useBatchTranslation] Resume proposal missing translated_text or verse_number — dropped');
            return;
          }
          nextProposalReceived = true;
          if (!event.messages_snapshot) console.warn('[useBatchTranslation] Resume proposal missing messages_snapshot — reusing prior messages');
          const nextMessages = event.messages_snapshot ?? messages;
          const nextRemaining = remainingVerses.filter(v => v.verse_number !== nextVerseNum);

          setBatchSession(prev => prev ? {
            ...prev,
            messages: nextMessages,
            pendingCallId: event.call_id!,
            pendingVerseNumber: nextVerseNum,
            remainingVerses: nextRemaining,
          } : null);

          setVerseGenStates(prev => new Map(prev).set(nextVerseNum, {
            status: 'proposal_ready',
            proposal: {
              translated_text: input.translated_text!,
              confidence: input.confidence ?? 0,
              rationale: input.rationale ?? '',
            },
          }));
        },
      }
    );

    if (resumeController.signal.aborted) {
      setBatchSession(null);
      setGeneratingBatch(false);
      clearQueuedStates();
    } else if (!nextProposalReceived) {
      const errorVerseNum = remainingVerses[0]?.verse_number;
      if (errorVerseNum) {
        setVerseGenStates(prev => new Map(prev).set(errorVerseNum, {
          status: 'error', proposal: null, errorMessage: 'LLM stopped — retry',
        }));
      }
      clearQueuedStates();
      setBatchSession(null);
      setGeneratingBatch(false);
    }
  }, [batchSession, selectedBook, selectedChapter, languageCode, isStreaming, pipeToChat, clearQueuedStates]);

  const handleGenerateBatch = useCallback(async () => {
    if (!selectedBook) return;
    if (isStreaming) return;

    const toGenerate = filteredVerses
      .filter(v => selectedVerses.has(v.verse))
      .map(v => ({ verse_number: v.verse, english_text: v.english_text || '' }))
      .filter(v => v.english_text);

    if (toGenerate.length === 0) return;

    if (toGenerate.length === 1) {
      const verse = filteredVerses.find(v => v.verse === toGenerate[0].verse_number);
      if (verse) await handleGenerateVerse(verse);
      return;
    }

    // Mark all selected verses as queued so cards show feedback immediately
    setVerseGenStates(prev => {
      const next = new Map(prev);
      for (const v of toGenerate) {
        next.set(v.verse_number, { status: 'queued', proposal: null });
      }
      return next;
    });

    openChat();
    const controller = new AbortController();
    setGeneratingBatch(true);

    let systemPrompt = '';
    let systemPromptSig = '';
    let proposalReceived = false;

    // Wrap the generator to capture batch_system_prompt before passing to pipeToChat
    async function* wrapBatchStream() {
      for await (const event of streamBatchTranslation(
        languageCode, selectedBook!.book_code, selectedChapter,
        toGenerate, languageName, selectedBook!.book_name, controller.signal,
      )) {
        if (event.type === 'batch_system_prompt') {
          systemPrompt = (event as any).system;
          systemPromptSig = (event as any).system_prompt_sig ?? '';
          // Don't yield — stripped from stream, captured locally
        } else {
          yield event;
        }
      }
    }

    await pipeToChat(
      `Translating ${toGenerate.length} verses from ${selectedBook.book_name} ${selectedChapter}`,
      wrapBatchStream(),
      {
        abortController: controller,
        onProposalEvent: (event) => {
          const input = event.input as { verse_number?: number; translated_text?: string; confidence?: number; rationale?: string };
          const verseNum = input?.verse_number;
          if (!input?.translated_text || !verseNum) {
            console.warn('[useBatchTranslation] Batch proposal missing translated_text or verse_number — dropped');
            return;
          }
          proposalReceived = true;
          if (!event.messages_snapshot) console.warn('[useBatchTranslation] Batch proposal missing messages_snapshot — batch resume will use empty messages');
          const messagesSnapshot = event.messages_snapshot ?? [];
          const remaining = toGenerate.filter(v => v.verse_number !== verseNum);

          setBatchSession({
            systemPrompt,
            systemPromptSig,
            messages: messagesSnapshot,
            pendingCallId: event.call_id!,
            pendingVerseNumber: verseNum,
            remainingVerses: remaining,
            abortController: controller,
          });

          setVerseGenStates(prev => new Map(prev).set(verseNum, {
            status: 'proposal_ready',
            proposal: {
              translated_text: input.translated_text!,
              confidence: input.confidence ?? 0,
              rationale: input.rationale ?? '',
            },
          }));
        },
      }
    );

    if (controller.signal.aborted) {
      // Stop button was clicked — clean up batch state
      setBatchSession(null);
      setGeneratingBatch(false);
      clearQueuedStates();
    } else if (!proposalReceived) {
      // LLM ended stream without proposing any verse — mark all selected as error
      setVerseGenStates(prev => {
        const next = new Map(prev);
        for (const v of toGenerate) {
          if (!next.has(v.verse_number) || next.get(v.verse_number)?.status === 'queued') {
            next.set(v.verse_number, { status: 'error', proposal: null, errorMessage: 'LLM stopped without proposing — retry' });
          }
        }
        return next;
      });
      setGeneratingBatch(false);
    }
    // else: proposalReceived && not aborted — generatingBatch stays true, cleared in handleBatchResume after last verse
  }, [selectedBook, selectedChapter, languageCode, languageName, isStreaming,
      filteredVerses, selectedVerses, pipeToChat, openChat, handleGenerateVerse, clearQueuedStates]);

  // ---- Proposal decision handlers ----

  const handleAcceptProposal = useCallback(async (verseNum: number) => {
    const state = verseGenStates.get(verseNum);
    if (!state?.proposal || !selectedBook) return;
    await onSaveVerse(verseNum, state.proposal.translated_text);
    setVerseGenStates(prev => { const m = new Map(prev); m.delete(verseNum); return m; });
    setProposalFeedback(null);
    if (batchSession?.pendingVerseNumber === verseNum) {
      await handleBatchResume(verseNum, 'approve');
    } else if (chatProposalCallId) {
      approveToolCall(chatProposalCallId);
      setChatProposalCallId(null);
    }
  }, [verseGenStates, selectedBook, onSaveVerse, batchSession, chatProposalCallId, handleBatchResume, approveToolCall]);

  const handleEditAndSaveProposal = useCallback(async (verseNum: number, correctedText: string, feedbackText: string) => {
    if (!selectedBook) return;
    const originalText = verseGenStates.get(verseNum)?.proposal?.translated_text ?? '';
    await onSaveVerse(verseNum, correctedText);
    setVerseGenStates(prev => { const m = new Map(prev); m.delete(verseNum); return m; });
    setProposalFeedback(null);
    if (batchSession?.pendingVerseNumber === verseNum) {
      await handleBatchResume(verseNum, 'reject', `Translator corrected verse ${verseNum} to: "${correctedText}"`);
    } else if (chatProposalCallId) {
      approveToolCall(chatProposalCallId, { decision: 'edited', corrected_text: correctedText });
      setChatProposalCallId(null);
    }
    if (feedbackText.trim()) {
      appendCorrectionLog(languageCode, {
        content_type: 'bible_verse',
        content_reference: { book_code: selectedBook.book_code, chapter: selectedChapter, verse: verseNum },
        original_text: originalText,
        what_was_wrong: feedbackText,
        correction: correctedText,
      }).catch(err => console.error('Correction log save failed:', err));
    }
    onEditedProposal?.(
      { book_code: selectedBook.book_code, chapter: selectedChapter, verse: verseNum },
      originalText,
      correctedText,
      feedbackText
    );
  }, [selectedBook, selectedChapter, languageCode, verseGenStates, onSaveVerse, batchSession, chatProposalCallId,
      handleBatchResume, approveToolCall, onEditedProposal]);

  const handleRejectProposal = useCallback(async (verseNum: number, feedback?: string) => {
    setVerseGenStates(prev => { const m = new Map(prev); m.delete(verseNum); return m; });
    setProposalFeedback(null);
    if (batchSession?.pendingVerseNumber === verseNum) {
      await handleBatchResume(verseNum, 'reject', feedback || undefined);
    } else if (chatProposalCallId) {
      rejectToolCall(chatProposalCallId);
      setChatProposalCallId(null);
    }
  }, [batchSession, chatProposalCallId, handleBatchResume, rejectToolCall]);

  const handleRetry = useCallback((verse: VerseData) => {
    setVerseGenStates(prev => { const m = new Map(prev); m.delete(verse.verse); return m; });
    handleGenerateVerse(verse);
  }, [handleGenerateVerse]);

  // ============================================================================
  // Grouped return objects — useMemo required for React.memo on VerseTranslationCell (Step 4)
  // ============================================================================

  const generation = useMemo<BatchGenerationActions>(() => ({
    verseGenStates,
    generatingBatch,
    handleGenerateVerse,
    handleGenerateBatch,
    handleAbortBatch,
    clearAllGenStates,
  }), [verseGenStates, generatingBatch, handleGenerateVerse, handleGenerateBatch, handleAbortBatch, clearAllGenStates]);

  const selection = useMemo<BatchSelectionActions>(() => ({
    selectedVerses,
    handleVerseSelection,
    handleSelectAll,
    handleSelectAllUnverified,
    handleClearSelection,
  }), [selectedVerses, handleVerseSelection, handleSelectAll, handleSelectAllUnverified, handleClearSelection]);

  const proposal = useMemo<ProposalActions>(() => ({
    proposalFeedback,
    setProposalFeedback,
    handleAcceptProposal,
    handleEditAndSaveProposal,
    handleRejectProposal,
    handleRetry,
  }), [proposalFeedback, setProposalFeedback, handleAcceptProposal, handleEditAndSaveProposal, handleRejectProposal, handleRetry]);

  return { generation, selection, proposal };
}
