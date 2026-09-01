/**
 * T4: ChatDrawer modes bar conditional rendering — thinking flag.
 *
 * Failure points targeted:
 * - No-language branch (~line 424): modes bar hidden when thinkingEnabled=false
 * - Normal branch (~line 499): modes bar hidden when thinkingEnabled=false
 * - Both branches: modes bar visible when thinkingEnabled=true
 *
 * Two-branch risk: ChatDrawer renders the modes bar independently in the
 * no-language path (appContext.languageCode=null) and the normal path
 * (languageCode≠null). If only one Box is wrapped in {thinkingEnabled && ...},
 * one branch leaks through. This test covers both by rendering each in turn.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';

import { ChatProvider, useChat } from '../../src/renderer/contexts/ChatContext';
import { SettingsProvider } from '../../src/renderer/contexts/SettingsContext';
import { ChatDrawer } from '../../src/components/ChatDrawer';
import { fetchChatConfig } from '../../src/renderer/api';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../src/renderer/api', () => ({
  streamChat: vi.fn(),
  submitToolResult: vi.fn(),
  fetchConversations: vi.fn().mockResolvedValue([]),
  createConversation: vi.fn().mockResolvedValue({ id: 'test-conv' }),
  fetchConversation: vi.fn(),
  deleteConversation: vi.fn(),
  fetchChatSkills: vi.fn().mockResolvedValue([]),
  fetchChatConfig: vi.fn(),
  appendCorrectionLog: vi.fn().mockResolvedValue({}),
}));

vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8221');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const baseConfig = {
  llm_provider: 'openrouter',
  local_base_url: '',
  local_model: '',
  has_openrouter_key: true,
  openrouter_key_preview: '...test',
  openrouter_model: 'anthropic/claude-sonnet-4.6',
};

/** Wraps ChatDrawer in the required provider stack. */
const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <SettingsProvider>
    <ChatProvider>{children}</ChatProvider>
  </SettingsProvider>
);

/**
 * Sibling component that sets a language on the ChatContext after mount,
 * forcing ChatDrawer to render its normal (language-selected) branch.
 * Mirrors how BibleReader calls setAppContext in production.
 */
const SetLanguage: React.FC = () => {
  const { setAppContext } = useChat();
  React.useEffect(() => {
    setAppContext({ languageCode: 'fra', bookCode: 'GEN', chapter: 1, view: 'bible' });
  }, [setAppContext]);
  return null;
};

// ---------------------------------------------------------------------------
// Branch A: no-language path (languageCode = null, the default)
// ---------------------------------------------------------------------------

describe('ChatDrawer modes bar — no-language branch', () => {
  it('hides Think and Think Harder when thinking_enabled is false', async () => {
    /**
     * Regression: If Branch A's modes bar Box is not wrapped in
     * {thinkingEnabled && ...}, Think/Think Harder appear here even when
     * the global flag is off.
     */
    vi.mocked(fetchChatConfig).mockResolvedValue({ ...baseConfig, thinking_enabled: false });
    render(<ChatDrawer />, { wrapper: Wrapper });

    await waitFor(() => expect(fetchChatConfig).toHaveBeenCalled());
    expect(screen.queryByText('Think')).not.toBeInTheDocument();
    expect(screen.queryByText('Think Harder')).not.toBeInTheDocument();
  });

  it('shows Think and Think Harder when thinking_enabled is true', async () => {
    vi.mocked(fetchChatConfig).mockResolvedValue({ ...baseConfig, thinking_enabled: true });
    render(<ChatDrawer />, { wrapper: Wrapper });

    await waitFor(() => expect(screen.getByText('Think')).toBeInTheDocument());
    expect(screen.getByText('Think Harder')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Branch B: normal path (languageCode set → language-selected branch)
// ---------------------------------------------------------------------------

describe('ChatDrawer modes bar — normal branch (language selected)', () => {
  it('hides Think and Think Harder when thinking_enabled is false', async () => {
    /**
     * Regression: If Branch B's modes bar Box is not wrapped in
     * {thinkingEnabled && ...}, Think/Think Harder remain visible after
     * a language is selected — the common user path.
     */
    vi.mocked(fetchChatConfig).mockResolvedValue({ ...baseConfig, thinking_enabled: false });
    render(
      <SettingsProvider>
        <ChatProvider>
          <SetLanguage />
          <ChatDrawer />
        </ChatProvider>
      </SettingsProvider>
    );

    await waitFor(() => expect(fetchChatConfig).toHaveBeenCalled());
    expect(screen.queryByText('Think')).not.toBeInTheDocument();
    expect(screen.queryByText('Think Harder')).not.toBeInTheDocument();
  });

  it('shows Think and Think Harder when thinking_enabled is true', async () => {
    vi.mocked(fetchChatConfig).mockResolvedValue({ ...baseConfig, thinking_enabled: true });
    render(
      <SettingsProvider>
        <ChatProvider>
          <SetLanguage />
          <ChatDrawer />
        </ChatProvider>
      </SettingsProvider>
    );

    await waitFor(() => expect(screen.getByText('Think')).toBeInTheDocument());
    expect(screen.getByText('Think Harder')).toBeInTheDocument();
  });
});
