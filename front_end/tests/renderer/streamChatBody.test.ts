/**
 * Tests for streamChat request body construction.
 *
 * IMPORTANT: This file must NOT have a top-level vi.mock for '../api'.
 * Vitest hoists vi.mock to module scope — any import('...api') inside
 * test bodies would return the mock, making fetchSpy never fire.
 * Keep these tests in a separate file from ChatContext tests.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { streamChat } from '../../src/renderer/api';

// ---------------------------------------------------------------------------
// streamChat body construction
// Tests the api.ts body-building logic without making real fetch calls.
// ---------------------------------------------------------------------------

describe('streamChat request body construction', () => {
  // We test the body-building logic by inspecting what fetch receives.
  // This isolates the api.ts concern from ChatContext.

  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: {"type":"done"}\n\n'));
            controller.close();
          },
        }),
        { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
      )
    );
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('sends chat_mode in body when mode is think', async () => {
    const gen = streamChat(
      [{ role: 'user', content: 'hi' }],
      undefined,
      undefined,
      undefined,
      false,
      'think',
    );
    // Drain the generator
    for await (const _ of gen) { /* consume */ }

    const callArgs = fetchSpy.mock.calls[0];
    const body = JSON.parse(callArgs[1]?.body as string);
    expect(body.chat_mode).toBe('think');
  });

  it('sends chat_mode in body when mode is think_harder', async () => {
    const gen = streamChat(
      [{ role: 'user', content: 'hi' }],
      undefined,
      undefined,
      undefined,
      false,
      'think_harder',
    );
    for await (const _ of gen) { /* consume */ }

    const callArgs = fetchSpy.mock.calls[0];
    const body = JSON.parse(callArgs[1]?.body as string);
    expect(body.chat_mode).toBe('think_harder');
  });

  it('omits chat_mode from body when mode is null', async () => {
    const gen = streamChat(
      [{ role: 'user', content: 'hi' }],
      undefined,
      undefined,
      undefined,
      false,
      null,
    );
    for await (const _ of gen) { /* consume */ }

    const callArgs = fetchSpy.mock.calls[0];
    const body = JSON.parse(callArgs[1]?.body as string);
    // chat_mode must be absent — not sent as null or "null"
    expect('chat_mode' in body).toBe(false);
  });

  it('omits thinking_enabled from body when false', async () => {
    const gen = streamChat([{ role: 'user', content: 'hi' }]);
    for await (const _ of gen) { /* consume */ }

    const callArgs = fetchSpy.mock.calls[0];
    const body = JSON.parse(callArgs[1]?.body as string);
    expect('thinking_enabled' in body).toBe(false);
  });

  it('sends thinking_enabled: true when enabled', async () => {
    const gen = streamChat(
      [{ role: 'user', content: 'hi' }],
      undefined,
      undefined,
      undefined,
      true,
    );
    for await (const _ of gen) { /* consume */ }

    const callArgs = fetchSpy.mock.calls[0];
    const body = JSON.parse(callArgs[1]?.body as string);
    expect(body.thinking_enabled).toBe(true);
  });
});
