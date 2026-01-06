import React, { useEffect, useState } from 'react';

interface TypewriterTextProps {
  text: string;
  speed?: number; // milliseconds per character
  sx?: object;
  [key: string]: any; // for passing Typography props
}

/**
 * TypewriterText
 * Renders text with a left-to-right "typewriter" animation.
 * @param text - The string to animate.
 * @param speed - Milliseconds per character (default: 50ms).
 * @param sx - Optional style overrides for Typography.
 * @param ...props - Any other Typography props.
 */
export function TypewriterText({ text, speed = 50, sx, ...props }: TypewriterTextProps) {
  const [displayed, setDisplayed] = useState('');

  useEffect(() => {
    setDisplayed('');
    let i = 0;
    let cancelled = false;
    function tick() {
      if (cancelled) return;
      setDisplayed(text.slice(0, i + 1));
      if (i < text.length - 1) {
        i++;
        setTimeout(tick, speed);
      }
    }
    tick();
    return () => { cancelled = true; };
  }, [text, speed]);

  return (
    <span style={sx} {...props}>{displayed}</span>
  );
}