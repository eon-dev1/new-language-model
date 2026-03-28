/**
 * ToolDataPreview - Floating overlay panel showing a rolling sample of tool
 * result data during streaming. Positioned fixed, just to the left of the
 * ChatDrawer edge.
 */

import React, { useState, useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import type { ToolResultEntry } from '../renderer/contexts/ChatContext';

interface Props {
  buffer: ToolResultEntry[];
  isStreaming: boolean;
  drawerWidth: number;
  isDrawerOpen: boolean;
}

const TOOL_LABELS: Record<string, string> = {
  get_chapter: 'Chapter',
  get_bible_chunk: 'Bible Chunk',
  get_parallel_verses: 'Parallel Verses',
  list_languages: 'Languages',
  get_language_info: 'Language Info',
  list_dictionary_entries: 'Dictionary',
  get_dictionary_entry: 'Dictionary Entry',
  get_word_index: 'Word Index',
  get_words_not_in_dictionary: 'Missing Words',
  get_word_frequency_list: 'Word Frequency',
  list_grammar_categories: 'Grammar Categories',
  get_grammar_category: 'Grammar Category',
  list_bible_books: 'Bible Books',
  save_bible_batches: 'Bible Batches',
};

function extractExcerpt(toolName: string, preview: string): string {
  try {
    const data = JSON.parse(preview);

    if ((toolName === 'get_chapter' || toolName === 'get_bible_chunk') && data.verses) {
      const first = data.verses[0];
      if (first?.text) return first.text;
      if (first?.translated_text) return first.translated_text;
    }

    if (toolName === 'get_parallel_verses' && data.parallel_verses) {
      const first = data.parallel_verses[0];
      if (first?.translations) {
        const langs = Object.keys(first.translations);
        if (langs.length > 0) {
          const t = first.translations[langs[0]];
          if (t?.text) return `${langs[0]}: ${t.text}`;
        }
      }
    }

    if (toolName === 'list_languages' && Array.isArray(data)) {
      return data.slice(0, 4).map((l: any) => l.language_name || l.language_code).join(', ');
    }

    if (toolName === 'get_language_info' && data.language_name) {
      return `${data.language_name} — ${data.status || ''}`.trim();
    }

    if (toolName === 'list_dictionary_entries' && data.entries) {
      return data.entries.slice(0, 3).map((e: any) => e.word).join(', ');
    }

    if (toolName === 'get_dictionary_entry' && data.word) {
      const def = data.definition || '';
      return `${data.word}: ${def}`.slice(0, 200);
    }

    if (toolName === 'get_word_index' && data.word) {
      return `"${data.word}" — ${data.total_count ?? '?'} occurrences, ${data.book_count ?? '?'} books`;
    }

    if (
      (toolName === 'get_words_not_in_dictionary' || toolName === 'get_word_frequency_list') &&
      Array.isArray(data)
    ) {
      return data.slice(0, 6).map((w: any) => `${w.word}(${w.count ?? w.total_count ?? '?'})`).join(' ');
    }

    if (
      (toolName === 'list_grammar_categories' || toolName === 'get_grammar_category') &&
      data.categories
    ) {
      return data.categories.map((c: any) => c.name || c).join(', ');
    }

    return preview.slice(0, 200);
  } catch {
    return preview.slice(0, 200);
  }
}

export const ToolDataPreview: React.FC<Props> = ({ buffer, isStreaming, drawerWidth, isDrawerOpen }) => {
  const [activeIndex, setActiveIndex] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Reset to last entry when buffer changes
  useEffect(() => {
    if (buffer.length > 0) {
      setActiveIndex(buffer.length - 1);
    }
  }, [buffer.length]);

  // Carousel interval
  useEffect(() => {
    if (isStreaming && buffer.length > 1) {
      intervalRef.current = setInterval(() => {
        setActiveIndex(prev => (prev + 1) % buffer.length);
      }, 2500);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isStreaming, buffer.length]);

  if (buffer.length === 0 || !isDrawerOpen) return null;

  const PANEL_WIDTH = 512;
  const rightOffset = drawerWidth + 8;

  // Hide if panel would overflow off-screen left
  if (rightOffset + PANEL_WIDTH >= window.innerWidth) return null;

  const current = buffer[Math.min(activeIndex, buffer.length - 1)];
  const label = TOOL_LABELS[current.toolName] || current.toolName;
  const excerpt = extractExcerpt(current.toolName, current.preview);
  const position = buffer.length > 1 ? `${activeIndex + 1}/${buffer.length}` : '';

  return (
    <Box
      style={{
        position: 'fixed',
        bottom: 16,
        right: rightOffset,
        width: PANEL_WIDTH,
        opacity: isStreaming ? 1 : 0.6,
        transition: 'opacity 0.4s ease',
        pointerEvents: 'none',
        zIndex: 1300,
        borderRadius: 10,
        background: 'linear-gradient(135deg, rgba(17,17,17,0.96), rgba(34,34,34,0.92))',
        border: '1px solid rgba(192,192,192,0.15)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          height: 128,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 10px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <PulsingDot isStreaming={isStreaming} />
          <span
            style={{
              fontSize: '0.62rem',
              fontFamily: 'system-ui, sans-serif',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'rgba(192,192,192,0.8)',
              userSelect: 'none',
            }}
          >
            {label}
          </span>
        </div>
        {position && (
          <span
            style={{
              fontSize: '0.6rem',
              color: 'rgba(255,255,255,0.3)',
              fontFamily: 'monospace',
              userSelect: 'none',
            }}
          >
            {position}
          </span>
        )}
      </div>

      {/* Content */}
      <div style={{ height: 128, padding: '8px 10px', overflow: 'hidden', position: 'relative' }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={current.id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2 }}
            style={{
              position: 'absolute',
              inset: '8px 10px',
              fontSize: '0.72rem',
              fontFamily: 'monospace',
              color: 'rgba(255,255,255,0.75)',
              lineHeight: 1.5,
              overflow: 'hidden',
              display: '-webkit-box',
              WebkitLineClamp: 4,
              WebkitBoxOrient: 'vertical',
              wordBreak: 'break-word',
            }}
          >
            {excerpt}
          </motion.div>
        </AnimatePresence>
      </div>
    </Box>
  );
};

// Inline pulsing dot — avoids MUI Box dependency, keeps the component self-contained
const PulsingDot: React.FC<{ isStreaming: boolean }> = ({ isStreaming }) => (
  <motion.div
    animate={isStreaming ? { opacity: [1, 0.3, 1] } : { opacity: 0.4 }}
    transition={isStreaming ? { duration: 1.2, repeat: Infinity } : {}}
    style={{
      width: 6,
      height: 6,
      borderRadius: '50%',
      background: 'rgba(192,192,192,1)',
      flexShrink: 0,
    }}
  />
);

// Minimal Box-like div wrapper to avoid importing MUI (panel is non-interactive)
const Box: React.FC<{ style?: React.CSSProperties; children: React.ReactNode }> = ({ style, children }) => (
  <div style={style}>{children}</div>
);
