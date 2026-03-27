import React from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet,
  ViewStyle, ActivityIndicator, StyleProp,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Gradients, Radius, Spacing, Typography } from '../lib/theme';

export function GlassCard({ children, style, padding = Spacing.md }: {
  children: React.ReactNode; style?: StyleProp<ViewStyle>; padding?: number;
}) {
  return (
    <View style={[styles.glassCard, { padding }, style]}>
      {children}
    </View>
  );
}

export function MetalCard({ children, style, padding = Spacing.md, colors }: {
  children: React.ReactNode; style?: StyleProp<ViewStyle>; padding?: number; colors?: string[];
}) {
  return (
    <LinearGradient
      colors={(colors || ['#111827', '#0D1421']) as any}
      start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
      style={[styles.metalCard, { padding }, style]}
    >
      {children}
    </LinearGradient>
  );
}

export function StatCard({ label, value, subtext, color = Colors.textPrimary, style }: {
  label: string; value: string; subtext?: string; color?: string; style?: StyleProp<ViewStyle>;
}) {
  return (
    <GlassCard style={[styles.statCard, style]}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      {subtext ? <Text style={styles.statSubtext}>{subtext}</Text> : null}
    </GlassCard>
  );
}

export function PnLBadge({ value, size = 'md', style }: {
  value: number; size?: 'sm' | 'md' | 'lg'; style?: StyleProp<ViewStyle>;
}) {
  const isPos = value >= 0;
  const color = isPos ? Colors.green : Colors.red;
  const bg = isPos ? Colors.greenBg : Colors.redBg;
  const sizes = { sm: 12, md: 14, lg: 18 };
  return (
    <View style={[styles.pnlBadge, { backgroundColor: bg, borderColor: color + '40' }, style]}>
      <Text style={{ color, fontSize: sizes[size], fontWeight: '600' }}>
        {isPos ? '+' : ''}₹{Math.abs(value).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
      </Text>
    </View>
  );
}

export function PrimaryButton({ title, onPress, loading, disabled, variant = 'primary', style, small }: {
  title: string; onPress: () => void; loading?: boolean; disabled?: boolean;
  variant?: 'primary' | 'danger' | 'ghost' | 'success'; style?: StyleProp<ViewStyle>; small?: boolean;
}) {
  const gradients: any = {
    primary: ['#1D4ED8', '#3B82F6'],
    danger: ['#991B1B', '#EF4444'],
    ghost: ['rgba(255,255,255,0.06)', 'rgba(255,255,255,0.04)'],
    success: ['#065F46', '#10B981'],
  };
  return (
    <TouchableOpacity onPress={onPress} disabled={disabled || loading}
      activeOpacity={0.75} style={[{ opacity: disabled ? 0.5 : 1 }, style]}>
      <LinearGradient colors={gradients[variant]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
        style={[styles.button, small && styles.buttonSmall]}>
        {loading
          ? <ActivityIndicator color="#fff" size="small" />
          : <Text style={[styles.buttonText, small && { fontSize: 13 }]}>{title}</Text>}
      </LinearGradient>
    </TouchableOpacity>
  );
}

export function SectionHeader({ title, subtitle, right }: {
  title: string; subtitle?: string; right?: React.ReactNode;
}) {
  return (
    <View style={styles.sectionHeader}>
      <View>
        <Text style={styles.sectionTitle}>{title}</Text>
        {subtitle ? <Text style={styles.sectionSubtitle}>{subtitle}</Text> : null}
      </View>
      {right}
    </View>
  );
}

export function Divider({ style }: { style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.divider, style]} />;
}

export function Tag({ label, color = Colors.textSecondary, bg = Colors.bgGlass }: {
  label: string; color?: string; bg?: string;
}) {
  return (
    <View style={[styles.tag, { backgroundColor: bg, borderColor: color + '40' }]}>
      <Text style={[styles.tagText, { color }]}>{label}</Text>
    </View>
  );
}

export function EmptyState({ icon, title, subtitle }: {
  icon: string; title: string; subtitle?: string;
}) {
  return (
    <View style={styles.emptyState}>
      <Text style={styles.emptyIcon}>{icon}</Text>
      <Text style={styles.emptyTitle}>{title}</Text>
      {subtitle ? <Text style={styles.emptySubtitle}>{subtitle}</Text> : null}
    </View>
  );
}

export function LoadingSpinner({ color = Colors.accent }: { color?: string }) {
  return (
    <View style={styles.loadingContainer}>
      <ActivityIndicator color={color} size="large" />
    </View>
  );
}

export function ProgressBar({ value, color = Colors.accent, height = 4, style }: {
  value: number; color?: string; height?: number; style?: StyleProp<ViewStyle>;
}) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <View style={[styles.progressTrack, { height }, style]}>
      <LinearGradient
        colors={[color + 'AA', color] as any}
        start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
        style={[styles.progressFill, { width: `${pct}%` as any, height }]}
      />
    </View>
  );
}

export function ScreenHeader({
  title,
  subtitle,
  badge,
  children,
  onBack,
}: {
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  children?: React.ReactNode;
  onBack?: () => void;
}) {
  return (
    <LinearGradient colors={Gradients.header} style={styles.screenHeader}>
      <View style={styles.headerGlowOne} />
      <View style={styles.headerGlowTwo} />
      <View style={styles.screenHeaderRow}>
        {onBack ? (
          <TouchableOpacity onPress={onBack} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={22} color={Colors.textPrimary} />
          </TouchableOpacity>
        ) : null}
        <View style={{ flex: 1 }}>
          <Text style={styles.screenHeaderTitle}>{title}</Text>
          {subtitle ? <Text style={styles.screenHeaderSubtitle}>{subtitle}</Text> : null}
        </View>
        {badge ? <View>{badge}</View> : null}
      </View>
      {children ? <View style={styles.screenHeaderChildren}>{children}</View> : null}
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  glassCard: {
    backgroundColor: Colors.bgGlass,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  metalCard: {
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    overflow: 'hidden',
  },
  statCard: { flex: 1 },
  statLabel: {
    fontSize: 11, fontWeight: '500', color: Colors.textMuted,
    textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 4,
  },
  statValue: { fontSize: 22, fontWeight: '700', color: Colors.textPrimary },
  statSubtext: { fontSize: 11, color: Colors.textMuted, marginTop: 2 },
  pnlBadge: {
    paddingHorizontal: 10, paddingVertical: 4,
    borderRadius: Radius.full, borderWidth: 1, alignSelf: 'flex-start',
  },
  button: {
    paddingVertical: 14, paddingHorizontal: 24,
    borderRadius: Radius.md, alignItems: 'center', justifyContent: 'center',
  },
  buttonSmall: { paddingVertical: 8, paddingHorizontal: 14, borderRadius: Radius.sm },
  buttonText: { fontSize: 15, color: '#fff', fontWeight: '600' },
  sectionHeader: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', marginBottom: Spacing.md,
  },
  sectionTitle: { fontSize: 20, fontWeight: '600', color: Colors.textPrimary },
  sectionSubtitle: { fontSize: 13, color: Colors.textMuted, marginTop: 2 },
  divider: { height: 1, backgroundColor: Colors.border, marginVertical: Spacing.md },
  tag: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: Radius.full, borderWidth: 1 },
  tagText: { fontSize: 11, fontWeight: '600' },
  emptyState: { alignItems: 'center', paddingVertical: 48 },
  emptyIcon: { fontSize: 40, marginBottom: 16 },
  emptyTitle: { fontSize: 17, fontWeight: '600', color: Colors.textSecondary, marginBottom: 4 },
  emptySubtitle: { fontSize: 13, color: Colors.textMuted, textAlign: 'center' },
  loadingContainer: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 48 },
  progressTrack: { backgroundColor: Colors.bgGlassStrong, borderRadius: Radius.full, overflow: 'hidden' },
  progressFill: { borderRadius: Radius.full },
  screenHeader: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.lg,
    overflow: 'hidden',
  },
  screenHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    zIndex: 2,
  },
  backBtn: {
    marginRight: 8,
    padding: 2,
  },
  screenHeaderTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: Colors.textPrimary,
    letterSpacing: -0.5,
  },
  screenHeaderSubtitle: {
    fontSize: 13,
    color: Colors.textMuted,
    marginTop: 3,
  },
  screenHeaderChildren: {
    marginTop: Spacing.md,
    zIndex: 2,
  },
  headerGlowOne: {
    position: 'absolute',
    width: 220,
    height: 220,
    borderRadius: 999,
    backgroundColor: Colors.accentSoft,
    top: -130,
    right: -80,
  },
  headerGlowTwo: {
    position: 'absolute',
    width: 130,
    height: 130,
    borderRadius: 999,
    backgroundColor: Colors.greenBg,
    top: -50,
    left: -40,
  },
});
