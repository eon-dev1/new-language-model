/**
 * Tests for ToolApprovalCard — dictionary per-entry approval flow.
 *
 * Failure modes targeted (from dictionary-entries.md Tests section):
 * - Test 1: pencil click on rejected entry must not override rejection status
 * - Test 2: edit-then-revert must hide comment field and produce empty corrections
 * - Test 4: all-rejected submission must call onReject, not onSubmitDictionary
 * - Test 5: grammar tool must render Edit/Reject/Approve header, not Cancel/Submit
 * - Test 6: mixed approval must preserve language_code in modifiedInput
 * - Test 7: rejected+edited+commented entry must not appear in corrections
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';

import { ToolApprovalCard } from '../../src/components/ToolApprovalCard';
import type { PendingToolApproval } from '../../src/renderer/contexts/ChatContext';

// ToolApprovalCard uses only `import type` from api and ChatContext — no runtime mock needed.

// ---------------------------------------------------------------------------
// Shared mock data
// ---------------------------------------------------------------------------

const mockDictApproval: PendingToolApproval = {
  callId: 'test-call-id',
  toolName: 'upsert_dictionary_entries',
  input: {
    language_code: 'tpi',
    entries: [
      { word: 'ol', definition: 'they, plural marker', part_of_speech: 'pronoun' },
      { word: 'long', definition: 'to, at, in, on', part_of_speech: 'preposition' },
      { word: 'bilong', definition: 'of, belonging to', part_of_speech: 'preposition' },
    ],
  },
};

const mockGrammarApproval: PendingToolApproval = {
  callId: 'grammar-call-id',
  toolName: 'update_grammar_category',
  input: {
    category: 'pronouns',
    content: {
      description: 'Personal pronouns in Tok Pisin',
      subcategories: [],
      notes: [],
      examples: [],
    },
  },
};

// ---------------------------------------------------------------------------
// Test 4 — All-rejected submission calls onReject, not onSubmitDictionary (priority 1)
// ---------------------------------------------------------------------------

describe('Test 4 — All-rejected submission', () => {
  it('calls onReject when all entries are rejected, not onSubmitDictionary or onApprove', () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    const onSubmitDictionary = vi.fn();

    render(
      <ToolApprovalCard
        approval={mockDictApproval}
        onApprove={onApprove}
        onReject={onReject}
        onSubmitDictionary={onSubmitDictionary}
      />
    );

    fireEvent.click(screen.getByTestId('entry-0-reject'));
    fireEvent.click(screen.getByTestId('entry-1-reject'));
    fireEvent.click(screen.getByTestId('entry-2-reject'));

    const submitBtn = screen.getByTestId('dict-submit');
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn);

    expect(onReject).toHaveBeenCalledOnce();
    expect(onReject).toHaveBeenCalledWith('test-call-id');
    expect(onSubmitDictionary).not.toHaveBeenCalled();
    expect(onApprove).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Test 5 — Grammar approval regression (priority 4)
// ---------------------------------------------------------------------------

describe('Test 5 — Grammar approval regression', () => {
  it('renders Edit/Reject/Approve header for grammar tool, not Cancel/Submit', () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    const onSubmitDictionary = vi.fn();

    render(
      <ToolApprovalCard
        approval={mockGrammarApproval}
        onApprove={onApprove}
        onReject={onReject}
        onSubmitDictionary={onSubmitDictionary}
      />
    );

    // Dictionary-specific buttons must be absent
    expect(screen.queryByTestId('dict-submit')).not.toBeInTheDocument();
    expect(screen.queryByTestId('dict-cancel')).not.toBeInTheDocument();

    // Grammar header has exactly 3 icon buttons: Edit, Reject, Approve
    // (GrammarCategoryRenderer has no buttons in non-editing mode with empty arrays)
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBe(3);

    // Last button is Approve (checkmark) — clicking it calls onApprove, not onSubmitDictionary
    fireEvent.click(buttons[2]);

    expect(onApprove).toHaveBeenCalledOnce();
    expect(onSubmitDictionary).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Test 6 — Mixed approval passes language_code in modifiedInput (priority 5)
// ---------------------------------------------------------------------------

describe('Test 6 — Mixed approval preserves language_code', () => {
  it('approved entries include language_code; rejected entry excluded', () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    const onSubmitDictionary = vi.fn();

    render(
      <ToolApprovalCard
        approval={mockDictApproval}
        onApprove={onApprove}
        onReject={onReject}
        onSubmitDictionary={onSubmitDictionary}
      />
    );

    // entry[0] approved, entry[1] rejected, entry[2] approved
    fireEvent.click(screen.getByTestId('entry-0-approve'));
    fireEvent.click(screen.getByTestId('entry-1-reject'));
    fireEvent.click(screen.getByTestId('entry-2-approve'));

    fireEvent.click(screen.getByTestId('dict-submit'));

    expect(onSubmitDictionary).toHaveBeenCalledOnce();
    const [callId, modifiedInput, corrections] = onSubmitDictionary.mock.calls[0] as [
      string,
      Record<string, unknown>,
      unknown[],
    ];

    expect(callId).toBe('test-call-id');
    expect(modifiedInput.language_code).toBe('tpi');

    const entries = modifiedInput.entries as Array<Record<string, string>>;
    expect(entries.length).toBe(2);
    expect(entries[0].word).toBe('ol');
    expect(entries[1].word).toBe('bilong');
    expect(corrections).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Test 7 — Rejected+edited+commented entry: correction NOT logged (priority 6)
// ---------------------------------------------------------------------------

describe('Test 7 — Rejected+edited entry does not appear in corrections', () => {
  it('silently drops edits and comment from rejected entry; corrections is empty', () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    const onSubmitDictionary = vi.fn();

    render(
      <ToolApprovalCard
        approval={mockDictApproval}
        onApprove={onApprove}
        onReject={onReject}
        onSubmitDictionary={onSubmitDictionary}
      />
    );

    // entry[0]: approve without edits
    fireEvent.click(screen.getByTestId('entry-0-approve'));

    // entry[1]: reject first, then open edit mode (should NOT override rejection)
    fireEvent.click(screen.getByTestId('entry-1-reject'));
    fireEvent.click(screen.getByTestId('entry-1-edit'));

    // Modify definition of entry[1]
    const defInput = screen.getByDisplayValue('to, at, in, on');
    fireEvent.change(defInput, { target: { value: 'at, in (location marker)' } });

    // Add a comment to entry[1]'s comment field (visible because entry is modified)
    const commentField = screen.getByPlaceholderText('Optional: describe the correction');
    fireEvent.change(commentField, { target: { value: 'this is wrong' } });

    // entry[2]: reject to enable Submit (all entries decided)
    fireEvent.click(screen.getByTestId('entry-2-reject'));

    const submitBtn = screen.getByTestId('dict-submit');
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn);

    expect(onSubmitDictionary).toHaveBeenCalledOnce();
    const [callId, modifiedInput, corrections] = onSubmitDictionary.mock.calls[0] as [
      string,
      Record<string, unknown>,
      unknown[],
    ];

    expect(callId).toBe('test-call-id');
    const entries = modifiedInput.entries as Array<Record<string, string>>;
    expect(entries.length).toBe(1);
    expect(entries[0].word).toBe('ol');
    // Rejected entry's edit and comment must be silently dropped
    expect(corrections).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Test 1 — Edit a rejected entry: status stays rejected (priority 2)
// ---------------------------------------------------------------------------

describe('Test 1 — Edit rejected entry: status stays rejected', () => {
  it('pencil click on rejected entry does not promote it to approved', () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    const onSubmitDictionary = vi.fn();

    render(
      <ToolApprovalCard
        approval={mockDictApproval}
        onApprove={onApprove}
        onReject={onReject}
        onSubmitDictionary={onSubmitDictionary}
      />
    );

    // entry[0]: approve
    fireEvent.click(screen.getByTestId('entry-0-approve'));

    // entry[1]: reject, then open edit mode
    fireEvent.click(screen.getByTestId('entry-1-reject'));
    fireEvent.click(screen.getByTestId('entry-1-edit'));

    // Change a field in entry[1] — if bug exists, this triggers auto-approve
    const defInput = screen.getByDisplayValue('to, at, in, on');
    fireEvent.change(defInput, { target: { value: 'at, in, on (location marker)' } });

    // entry[2]: reject to enable Submit
    fireEvent.click(screen.getByTestId('entry-2-reject'));

    const submitBtn = screen.getByTestId('dict-submit');
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn);

    // If the rejection guard is missing, entry[1] would be in approvedEntries.
    // Correct behavior: only entry[0] in the submission.
    expect(onSubmitDictionary).toHaveBeenCalledOnce();
    const [callId, modifiedInput] = onSubmitDictionary.mock.calls[0] as [
      string,
      Record<string, unknown>,
    ];

    expect(callId).toBe('test-call-id');
    const entries = modifiedInput.entries as Array<Record<string, string>>;
    expect(entries.length).toBe(1);
    expect(entries[0].word).toBe('ol');
  });
});

// ---------------------------------------------------------------------------
// Test 2 — Edit-then-revert: comment field hidden, no correction logged (priority 3)
// ---------------------------------------------------------------------------

describe('Test 2 — Edit-then-revert: comment field hidden', () => {
  it('hides comment field after revert and sends empty corrections on submit', () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    const onSubmitDictionary = vi.fn();

    render(
      <ToolApprovalCard
        approval={mockDictApproval}
        onApprove={onApprove}
        onReject={onReject}
        onSubmitDictionary={onSubmitDictionary}
      />
    );

    // Open edit mode on entry[0] — auto-approves the pending entry
    fireEvent.click(screen.getByTestId('entry-0-edit'));

    // Change definition — entry[0] is now modified, comment field appears
    const defInput = screen.getByDisplayValue('they, plural marker');
    fireEvent.change(defInput, { target: { value: 'they, those (plural)' } });

    const commentField = screen.getByPlaceholderText('Optional: describe the correction');
    expect(commentField).toBeInTheDocument();

    // Type a comment
    fireEvent.change(commentField, { target: { value: 'added clarity' } });

    // Revert definition back to original
    fireEvent.change(screen.getByDisplayValue('they, those (plural)'), {
      target: { value: 'they, plural marker' },
    });

    // Comment field must disappear — diff returned to equal, isModified = false
    expect(screen.queryByPlaceholderText('Optional: describe the correction')).not.toBeInTheDocument();

    // Reject entries [1] and [2] to enable Submit
    fireEvent.click(screen.getByTestId('entry-1-reject'));
    fireEvent.click(screen.getByTestId('entry-2-reject'));

    const submitBtn = screen.getByTestId('dict-submit');
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn);

    expect(onSubmitDictionary).toHaveBeenCalledOnce();
    const [, , corrections] = onSubmitDictionary.mock.calls[0] as [
      string,
      Record<string, unknown>,
      unknown[],
    ];

    // Comment is preserved in state but edited=false at submission time → no log entry
    expect(corrections).toEqual([]);
  });
});
