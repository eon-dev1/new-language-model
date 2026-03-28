/**
 * Tests for createDynamicTheme - Pure function that generates MUI theme from settings.
 *
 * TDD: These tests are written FIRST (RED), then implementation follows (GREEN).
 */

import { describe, it, expect } from 'vitest';
import { createDynamicTheme, type AppSettings } from '../../src/renderer/theme/createDynamicTheme';

describe('createDynamicTheme', () => {
  describe('font family', () => {
    it('uses system-ui font stack when fontFamily is "system-ui"', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      expect(theme.typography.fontFamily).toContain('system-ui');
      expect(theme.typography.fontFamily).toContain('-apple-system');
    });

    it('uses Times New Roman font stack when fontFamily is "Times New Roman"', () => {
      const settings: AppSettings = { fontFamily: 'Times New Roman', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      expect(theme.typography.fontFamily).toContain('Times New Roman');
      expect(theme.typography.fontFamily).toContain('serif');
    });
  });

  describe('scale factor', () => {
    it('fontSize 12 produces scale 0.75 (body1 = 0.75rem)', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 12 };
      const theme = createDynamicTheme(settings);

      expect(theme.typography.body1?.fontSize).toBe('0.75rem');
    });

    it('fontSize 16 produces scale 1.0 (body1 = 1rem)', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      expect(theme.typography.body1?.fontSize).toBe('1rem');
    });

    it('fontSize 24 produces scale 1.5 (body1 = 1.5rem)', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 24 };
      const theme = createDynamicTheme(settings);

      expect(theme.typography.body1?.fontSize).toBe('1.5rem');
    });

    it('scales h1 proportionally (3rem at scale 1.0)', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      expect(theme.typography.h1?.fontSize).toBe('3rem');
    });

    it('scales h1 at fontSize 24 (scale 1.5 → 4.5rem)', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 24 };
      const theme = createDynamicTheme(settings);

      expect(theme.typography.h1?.fontSize).toBe('4.5rem');
    });
  });

  describe('typography variants fontFamily override', () => {
    const variants = [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'body1', 'body2',
      'subtitle1', 'subtitle2',
      'caption', 'button',
    ] as const;

    it('overrides fontFamily on ALL typography variants with system-ui', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      variants.forEach((variant) => {
        const variantStyle = theme.typography[variant];
        expect(variantStyle?.fontFamily, `${variant} should have fontFamily`).toContain('system-ui');
      });
    });

    it('overrides fontFamily on ALL typography variants with Times New Roman', () => {
      const settings: AppSettings = { fontFamily: 'Times New Roman', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      variants.forEach((variant) => {
        const variantStyle = theme.typography[variant];
        expect(variantStyle?.fontFamily, `${variant} should have fontFamily`).toContain('Times New Roman');
      });
    });

    it('does NOT contain Orbitron in any variant', () => {
      const settings: AppSettings = { fontFamily: 'Times New Roman', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      variants.forEach((variant) => {
        const variantStyle = theme.typography[variant];
        const fontFamily = variantStyle?.fontFamily ?? '';
        expect(fontFamily, `${variant} should not contain Orbitron`).not.toContain('Orbitron');
      });
    });
  });

  describe('theme preservation (non-typography elements)', () => {
    it('preserves dark mode palette', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      expect(theme.palette.mode).toBe('dark');
    });

    it('preserves background colors', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      expect(theme.palette.background.default).toBe('#000000');
      expect(theme.palette.background.paper).toBe('#222222');
    });

    it('preserves primary color palette', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      expect(theme.palette.primary.main).toBe('#C0C0C0');
    });

    it('preserves text colors', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      expect(theme.palette.text.primary).toBe('#FFFFFF');
      expect(theme.palette.text.secondary).toBe('#CCCCCC');
    });

    it('preserves MuiButton component overrides', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      expect(theme.components?.MuiButton?.styleOverrides?.root).toBeDefined();
    });

    it('preserves MuiPaper component overrides', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      expect(theme.components?.MuiPaper?.styleOverrides?.root).toBeDefined();
    });

    it('preserves h1 textShadow from original theme', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      expect(theme.typography.h1?.textShadow).toBe('0 0 5px rgba(255, 255, 255, 0.5)');
    });

    it('preserves h1 fontWeight from original theme', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      expect(theme.typography.h1?.fontWeight).toBe(700);
    });

    it('preserves h2 fontWeight from original theme', () => {
      const settings: AppSettings = { fontFamily: 'system-ui', fontSize: 16 };
      const theme = createDynamicTheme(settings);

      expect(theme.typography.h2?.fontWeight).toBe(600);
    });
  });
});
