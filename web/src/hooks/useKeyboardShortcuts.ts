import { useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

const NAV_SHORTCUTS: Record<string, string> = {
  't': '/',
  'd': '/dashboard',
  's': '/screener',
  'j': '/journal',
  'p': '/positions',
  'a': '/auto-trader',
  'm': '/ml',
  'b': '/backtest',
  'f': '/finance',
};

interface Options {
  onOpenPalette: () => void;
}

export function useKeyboardShortcuts({ onOpenPalette }: Options) {
  const navigate = useNavigate();

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      // Don't fire when typing in inputs/textareas
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return;

      // Ctrl+K or Cmd+K → command palette
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        onOpenPalette();
        return;
      }

      // Single-key nav (no modifier)
      if (!e.ctrlKey && !e.metaKey && !e.altKey && e.key.length === 1) {
        const path = NAV_SHORTCUTS[e.key.toLowerCase()];
        if (path) {
          navigate(path);
        }
      }
    },
    [navigate, onOpenPalette]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

export const SHORTCUT_LIST = [
  { key: 'Ctrl+K', label: 'Open Command Palette' },
  { key: 'T', label: 'Terminal' },
  { key: 'D', label: 'Dashboard' },
  { key: 'S', label: 'Screener' },
  { key: 'J', label: 'Journal' },
  { key: 'P', label: 'Positions' },
  { key: 'A', label: 'Auto Trader' },
  { key: 'M', label: 'ML Center' },
  { key: 'B', label: 'Backtest' },
  { key: 'F', label: 'Finance' },
];
