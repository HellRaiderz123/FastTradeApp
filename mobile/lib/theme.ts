// Premium Metallic Theme for FastTrade iOS App

export const Colors = {
  // Backgrounds
  bg: '#080C14',
  bgCard: '#0D1421',
  bgElevated: '#111827',
  bgGlass: 'rgba(255,255,255,0.04)',
  bgGlassStrong: 'rgba(255,255,255,0.08)',

  // Borders
  border: 'rgba(255,255,255,0.08)',
  borderStrong: 'rgba(255,255,255,0.14)',
  borderAccent: 'rgba(99,179,237,0.3)',

  // Accent — Electric Blue
  accent: '#3B82F6',
  accentLight: '#60A5FA',
  accentGlow: 'rgba(59,130,246,0.25)',

  // Green (profit)
  green: '#10B981',
  greenLight: '#34D399',
  greenGlow: 'rgba(16,185,129,0.2)',
  greenBg: 'rgba(16,185,129,0.1)',

  // Red (loss)
  red: '#EF4444',
  redLight: '#F87171',
  redGlow: 'rgba(239,68,68,0.2)',
  redBg: 'rgba(239,68,68,0.1)',

  // Amber (warning)
  amber: '#F59E0B',
  amberBg: 'rgba(245,158,11,0.1)',

  // Text
  textPrimary: '#F1F5F9',
  textSecondary: '#94A3B8',
  textMuted: '#475569',
  textAccent: '#60A5FA',

  // Metallic gradients
  metalDark: ['#0D1421', '#111827'],
  metalCard: ['#111827', '#0D1421'],
  metalAccent: ['#1D4ED8', '#3B82F6'],
  metalGreen: ['#065F46', '#10B981'],
  metalRed: ['#7F1D1D', '#EF4444'],

  // Tab bar
  tabBg: 'rgba(8,12,20,0.95)',
  tabActive: '#3B82F6',
  tabInactive: '#475569',
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const Radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 28,
  full: 999,
};

export const Typography = {
  hero: { fontSize: 32, fontWeight: '700' as const, letterSpacing: -0.5 },
  h1: { fontSize: 24, fontWeight: '700' as const, letterSpacing: -0.3 },
  h2: { fontSize: 20, fontWeight: '600' as const, letterSpacing: -0.2 },
  h3: { fontSize: 17, fontWeight: '600' as const },
  body: { fontSize: 15, fontWeight: '400' as const },
  bodyMed: { fontSize: 15, fontWeight: '500' as const },
  small: { fontSize: 13, fontWeight: '400' as const },
  smallMed: { fontSize: 13, fontWeight: '500' as const },
  tiny: { fontSize: 11, fontWeight: '500' as const, letterSpacing: 0.3 },
  mono: { fontSize: 14, fontWeight: '600' as const, fontVariant: ['tabular-nums'] as any },
  monoLg: { fontSize: 22, fontWeight: '700' as const, fontVariant: ['tabular-nums'] as any },
};
