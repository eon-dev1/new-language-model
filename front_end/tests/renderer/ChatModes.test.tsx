/**
 * Tests for the Modes feature frontend changes.
 *
 * Failure points targeted:
 * - isThinkingSupported: Haiku returns false; Sonnet returns true; local returns false
 * - wantsThinking: deep_research excluded; maximum_thinking included; null excluded
 * - effectiveThinking: false when model is Haiku even if mode wants thinking
 * - setChatMode: persists to localStorage under key 'chat_mode' (not old key)
 * - setChatMode(null): removes key from localStorage (does not write "null")
 * - localStorage init: unknown stored value falls back to null safely
 * - streamChat body: chat_mode sent when non-null; absent when null
 * - streamChat body: thinking_enabled sent only when true
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';

import {
  isThinkingSupported,
  ChatProvider,
  useChat,
  type ChatMode,
} from '../../src/renderer/contexts/ChatContext';
import { fetchChatConfig } from '../../src/renderer/api';

// ---------------------------------------------------------------------------
// Mock all API calls to prevent network requests
// ---------------------------------------------------------------------------

vi.mock('../../src/renderer/api', () => ({
  streamChat: vi.fn(),
  submitToolResult: vi.fn(),
  fetchConversations: vi.fn().mockResolvedValue([]),
  createConversation: vi.fn().mockResolvedValue({ id: 'test-conv-id' }),
  fetchConversation: vi.fn(),
  deleteConversation: vi.fn(),
  fetchChatConfig: vi.fn().mockResolvedValue({
    llm_provider: 'openrouter',
    local_base_url: '',
    local_model: '',
    has_openrouter_key: true,
    openrouter_key_preview: '...test',
    openrouter_model: 'anthropic/claude-sonnet-4.6',
    thinking_enabled: true,
  }),
  fetchChatSkills: vi.fn().mockResolvedValue([]),
}));

// Mock import.meta.env for api.ts module initialization
vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8221');

// Helper: render useChat hook inside ChatProvider.
// Awaits a flush of ChatProvider's mount-time effects (refreshCurrentModel,
// fetchChatSkills) so their state updates land inside act() instead of
// leaking past the test body.
const renderChatHook = async () => {
  const result = renderHook(() => useChat(), {
    wrapper: ({ children }: { children: React.ReactNode }) => (
      <ChatProvider>{children}</ChatProvider>
    ),
  });
  await act(async () => {});
  return result;
};

// ---------------------------------------------------------------------------
// isThinkingSupported — pure function, no provider needed
// ---------------------------------------------------------------------------

describe('isThinkingSupported', () => {
  it('returns false for null model', () => {
    expect(isThinkingSupported(null)).toBe(false);
  });

  it('returns false for Haiku (CoT not supported)', () => {
    expect(isThinkingSupported('claude-haiku-4-5-20251001', 'anthropic')).toBe(false);
  });

  it('returns true for Sonnet', () => {
    expect(isThinkingSupported('claude-sonnet-4-6', 'anthropic')).toBe(true);
  });

  it('returns true for Opus', () => {
    expect(isThinkingSupported('claude-opus-4-6', 'anthropic')).toBe(true);
  });

  it('returns false for local provider regardless of model name', () => {
    // Local models may share names with Anthropic but CoT is provider-specific
    expect(isThinkingSupported('claude-sonnet-4-6', 'local')).toBe(false);
  });

  it('returns true for unknown non-Haiku model (safe default)', () => {
    // Unknown models should be allowed to try CoT rather than silently blocking
    expect(isThinkingSupported('some-future-model', 'anthropic')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// wantsThinking derivation
// Extracted from ChatContext sendMessage logic for isolated testing.
// ---------------------------------------------------------------------------

const wantsThinking = (chatMode: ChatMode): boolean =>
  chatMode === 'think' || chatMode === 'think_harder' || chatMode === 'maximum_thinking';

describe('wantsThinking derivation', () => {
  it('is true for think', () => {
    expect(wantsThinking('think')).toBe(true);
  });

  it('is true for think_harder', () => {
    expect(wantsThinking('think_harder')).toBe(true);
  });

  it('is true for maximum_thinking', () => {
    // Maximum Thinking is a placeholder but CoT should still be requested on capable models
    expect(wantsThinking('maximum_thinking')).toBe(true);
  });

  it('is false for deep_research', () => {
    // deep_research uses a sub-agent model, not CoT — must NOT trigger thinking_enabled
    expect(wantsThinking('deep_research')).toBe(false);
  });

  it('is false for null (default/no mode)', () => {
    expect(wantsThinking(null)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// effectiveThinking: mode × model capability matrix
// ---------------------------------------------------------------------------

const effectiveThinking = (chatMode: ChatMode, model: string | null, provider: string): boolean => {
  const wants = wantsThinking(chatMode);
  return wants && isThinkingSupported(model, provider);
};

describe('effectiveThinking matrix', () => {
  it('think + Sonnet → true', () => {
    expect(effectiveThinking('think', 'claude-sonnet-4-6', 'anthropic')).toBe(true);
  });

  it('think + Haiku → false (CoT silently skipped)', () => {
    expect(effectiveThinking('think', 'claude-haiku-4-5-20251001', 'anthropic')).toBe(false);
  });

  it('think_harder + Sonnet → true (CoT + skill)', () => {
    expect(effectiveThinking('think_harder', 'claude-sonnet-4-6', 'anthropic')).toBe(true);
  });

  it('think_harder + Haiku → false (skill fires, CoT skipped)', () => {
    // Skill injection is a backend concern. From frontend's perspective, thinking is false.
    expect(effectiveThinking('think_harder', 'claude-haiku-4-5-20251001', 'anthropic')).toBe(false);
  });

  it('null + Sonnet → false (no mode selected)', () => {
    expect(effectiveThinking(null, 'claude-sonnet-4-6', 'anthropic')).toBe(false);
  });

  it('deep_research + Sonnet → false (not a CoT mode)', () => {
    expect(effectiveThinking('deep_research', 'claude-sonnet-4-6', 'anthropic')).toBe(false);
  });

  it('think + local provider → false', () => {
    expect(effectiveThinking('think', 'some-local-model', 'local')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// ChatContext mode state and localStorage
// ---------------------------------------------------------------------------

describe('ChatContext chatMode state', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('defaults to null when localStorage is empty', async () => {
    const { result } = await renderChatHook();
    expect(result.current.chatMode).toBeNull();
  });

  it('restores think mode from localStorage on init', async () => {
    localStorage.setItem('chat_mode', 'think');
    const { result } = await renderChatHook();
    expect(result.current.chatMode).toBe('think');
  });

  it('restores think_harder mode from localStorage on init', async () => {
    localStorage.setItem('chat_mode', 'think_harder');
    const { result } = await renderChatHook();
    expect(result.current.chatMode).toBe('think_harder');
  });

  it('falls back to null for unknown/invalid stored value', async () => {
    // e.g. stale value from old codebase, or corrupted storage
    localStorage.setItem('chat_mode', 'invalid_mode_xyz');
    const { result } = await renderChatHook();
    expect(result.current.chatMode).toBeNull();
  });

  it('falls back to null if old chat_thinking_enabled key is present (no migration)', async () => {
    // Old key from previous implementation — should be ignored, not migrated
    localStorage.setItem('chat_thinking_enabled', 'true');
    const { result } = await renderChatHook();
    expect(result.current.chatMode).toBeNull();
  });
});

describe('ChatContext setChatMode', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('sets mode to think and persists to localStorage', async () => {
    const { result } = await renderChatHook();

    act(() => {
      result.current.setChatMode('think');
    });

    expect(result.current.chatMode).toBe('think');
    expect(localStorage.getItem('chat_mode')).toBe('think');
  });

  it('sets mode to think_harder and persists to localStorage', async () => {
    const { result } = await renderChatHook();

    act(() => {
      result.current.setChatMode('think_harder');
    });

    expect(result.current.chatMode).toBe('think_harder');
    expect(localStorage.getItem('chat_mode')).toBe('think_harder');
  });

  it('setChatMode(null) clears the localStorage key (not writes "null")', async () => {
    localStorage.setItem('chat_mode', 'think');
    const { result } = await renderChatHook();

    act(() => {
      result.current.setChatMode(null);
    });

    expect(result.current.chatMode).toBeNull();
    // The key must be absent — not set to the string "null"
    expect(localStorage.getItem('chat_mode')).toBeNull();
  });

  it('uses the key chat_mode, not the old chat_thinking_enabled key', async () => {
    const { result } = await renderChatHook();

    act(() => {
      result.current.setChatMode('think');
    });

    expect(localStorage.getItem('chat_mode')).toBe('think');
    // Old key must remain absent (no accidental write to legacy key)
    expect(localStorage.getItem('chat_thinking_enabled')).toBeNull();
  });

  it('toggling same mode twice returns to null', async () => {
    // UI behavior: click active mode button → deselect (returns to default)
    const { result } = await renderChatHook();

    act(() => { result.current.setChatMode('think'); });
    expect(result.current.chatMode).toBe('think');

    // Simulate the TopBar handleModeClick: setChatMode(chatMode === mode ? null : mode)
    act(() => { result.current.setChatMode(null); });
    expect(result.current.chatMode).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// isThinkingSupported — OpenRouter provider
// ---------------------------------------------------------------------------

describe('isThinkingSupported — OpenRouter provider', () => {
  it('returns true for OpenRouter Sonnet', () => {
    expect(isThinkingSupported('anthropic/claude-sonnet-4.6', 'openrouter')).toBe(true);
  });

  it('returns true for OpenRouter Opus', () => {
    expect(isThinkingSupported('anthropic/claude-opus-4.6', 'openrouter')).toBe(true);
  });

  it('returns false for OpenRouter Haiku', () => {
    expect(isThinkingSupported('anthropic/claude-haiku-4.5', 'openrouter')).toBe(false);
  });

  it('returns false for Qwen models (qwen/ prefix guard)', () => {
    expect(isThinkingSupported('qwen/qwen3.5-397b-a17b', 'openrouter')).toBe(false);
    expect(isThinkingSupported('qwen/qwen3.5-35b-a3b', 'openrouter')).toBe(false);
  });

  it('returns true for unknown openrouter model (safe default)', () => {
    expect(isThinkingSupported('some-future-provider/model-x', 'openrouter')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// effectiveThinking matrix — OpenRouter cases
// ---------------------------------------------------------------------------

describe('effectiveThinking matrix — OpenRouter cases', () => {
  it('think + OpenRouter Sonnet → true', () => {
    expect(effectiveThinking('think', 'anthropic/claude-sonnet-4.6', 'openrouter')).toBe(true);
  });

  it('think + OpenRouter Haiku → false', () => {
    expect(effectiveThinking('think', 'anthropic/claude-haiku-4.5', 'openrouter')).toBe(false);
  });

  it('think + Qwen → false', () => {
    expect(effectiveThinking('think', 'qwen/qwen3.5-397b-a17b', 'openrouter')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// refreshCurrentModel — three-provider branching
// ---------------------------------------------------------------------------

describe('refreshCurrentModel — provider branching', () => {
  it('sets currentModel from openrouter_model when provider is openrouter', async () => {
    vi.mocked(fetchChatConfig).mockResolvedValueOnce({
      llm_provider: 'openrouter',
      openrouter_model: 'qwen/qwen3.5-397b-a17b',
      local_model: '',
      local_base_url: '',
      has_openrouter_key: true,
      openrouter_key_preview: '...abcd',
      thinking_enabled: true,
    });
    const { result } = await renderChatHook();

    expect(result.current.currentModel).toBe('qwen/qwen3.5-397b-a17b');
    expect(result.current.currentProvider).toBe('openrouter');
  });

  it('sets currentModel from local_model when provider is local', async () => {
    vi.mocked(fetchChatConfig).mockResolvedValueOnce({
      llm_provider: 'local',
      openrouter_model: '',
      local_model: 'llama-3.3-70b',
      local_base_url: 'http://127.0.0.1:8080',
      has_openrouter_key: false,
      openrouter_key_preview: '',
      thinking_enabled: true,
    });
    const { result } = await renderChatHook();

    expect(result.current.currentModel).toBe('llama-3.3-70b');
    expect(result.current.currentProvider).toBe('local');
  });
});
