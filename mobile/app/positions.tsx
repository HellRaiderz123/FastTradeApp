import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
  TouchableOpacity, Alert, StatusBar,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';
import { journalAPI, exitAPI } from '../lib/api';
import { Colors, Spacing, Radius } from '../lib/theme';
import { GlassCard, MetalCard, PnLBadge, SectionHeader, EmptyState, LoadingSpinner, Tag, ProgressBar } from '../components/ui';

const EXCLUDED = ['ZERODHA_HOLDING', 'ZERODHA_ACTUAL', 'DIRECT_ZERODHA'];

export default function Positions() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [positions, setPositions] = useState<any[]>([]);
  const [closing, setClosing] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await journalAPI.getExecutionIntents(100);
      const all = res.data || [];
      setPositions(all.filter((p: any) =>
        p.status === 'EXECUTED' && !p.closed_at && !EXCLUDED.includes(p.strategy)
      ));
    } catch {}
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => { load(); }, []);

  const handleClose = (intentId: string, symbol: string) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    Alert.alert('Close Position', `Close ${symbol}?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Close', style: 'destructive',
        onPress: async () => {
          setClosing(intentId);
          try {
            await exitAPI.manualExit(intentId);
            setPositions(prev => prev.filter(p => p.intent_id !== intentId));
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          } catch {
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
          }
          setClosing(null);
        },
      },
    ]);
  };

  const totalPnL = positions.reduce((s, p) => s + (p.unrealized_pnl || 0), 0);
  const totalEntry = positions.reduce((s, p) => s + (p.entry_credit || 0), 0);
  const pnlPct = totalEntry > 0 ? (totalPnL / totalEntry) * 100 : 0;

  if (loading) return <View style={styles.root}><LoadingSpinner /></View>;

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safeArea}>
        {/* Header */}
        <LinearGradient colors={['#0F172A', '#080C14']} style={styles.header}>
          <Text style={styles.headerTitle}>Positions</Text>
          <Text style={styles.headerSub}>{positions.length} open</Text>

          {/* Summary Bar */}
          {positions.length > 0 && (
            <View style={styles.summaryBar}>
              <View style={styles.summaryItem}>
                <Text style={styles.summaryLabel}>Total P&L</Text>
                <Text style={[styles.summaryValue, { color: totalPnL >= 0 ? Colors.green : Colors.red }]}>
                  {totalPnL >= 0 ? '+' : ''}₹{Math.abs(totalPnL).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                </Text>
              </View>
              <View style={styles.summaryDivider} />
              <View style={styles.summaryItem}>
                <Text style={styles.summaryLabel}>Return</Text>
                <Text style={[styles.summaryValue, { color: pnlPct >= 0 ? Colors.green : Colors.red }]}>
                  {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                </Text>
              </View>
              <View style={styles.summaryDivider} />
              <View style={styles.summaryItem}>
                <Text style={styles.summaryLabel}>Invested</Text>
                <Text style={styles.summaryValue}>₹{totalEntry.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</Text>
              </View>
            </View>
          )}
        </LinearGradient>

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          {positions.length === 0 ? (
            <EmptyState icon="📭" title="No Open Positions" subtitle="Execute a strategy to open a position" />
          ) : (
            positions.map((p) => {
              const pnl = p.unrealized_pnl || 0;
              const entry = p.entry_credit || 0;
              const pct = entry > 0 ? (pnl / entry) * 100 : 0;
              const isPos = pnl >= 0;
              const mode = p.execution_result?.mode || '';
              const isLive = mode.includes('ZERODHA_LIVE');
              const legs = p.ticket?.legs || [];

              return (
                <MetalCard key={p.intent_id} style={styles.posCard}
                  colors={isPos ? ['#0A1F14', '#0D1421'] : ['#1A0A0A', '#0D1421']}>
                  {/* Top Row */}
                  <View style={styles.posTop}>
                    <View style={styles.posLeft}>
                      <View style={styles.posSymbolRow}>
                        <Text style={styles.posSymbol}>{p.underlying}</Text>
                        {isLive && <Tag label="LIVE" color={Colors.red} bg={Colors.redBg} />}
                      </View>
                      <Text style={styles.posStrategy}>{p.strategy}</Text>
                    </View>
                    <View style={styles.posRight}>
                      <Text style={[styles.posPnL, { color: isPos ? Colors.green : Colors.red }]}>
                        {isPos ? '+' : ''}₹{Math.abs(pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                      </Text>
                      <Text style={[styles.posPct, { color: isPos ? Colors.greenLight : Colors.redLight }]}>
                        {isPos ? '+' : ''}{pct.toFixed(2)}%
                      </Text>
                    </View>
                  </View>

                  {/* Progress bar */}
                  <ProgressBar
                    value={Math.abs(pct)}
                    color={isPos ? Colors.green : Colors.red}
                    height={3}
                    style={{ marginVertical: 10 }}
                  />

                  {/* Metrics */}
                  <View style={styles.posMetrics}>
                    <View style={styles.posMetric}>
                      <Text style={styles.posMetricLabel}>Entry</Text>
                      <Text style={styles.posMetricValue}>₹{entry.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</Text>
                    </View>
                    {p.tp && (
                      <View style={styles.posMetric}>
                        <Text style={styles.posMetricLabel}>TP</Text>
                        <Text style={[styles.posMetricValue, { color: Colors.green }]}>₹{p.tp}</Text>
                      </View>
                    )}
                    {p.sl && (
                      <View style={styles.posMetric}>
                        <Text style={styles.posMetricLabel}>SL</Text>
                        <Text style={[styles.posMetricValue, { color: Colors.red }]}>₹{p.sl}</Text>
                      </View>
                    )}
                    <View style={styles.posMetric}>
                      <Text style={styles.posMetricLabel}>Legs</Text>
                      <Text style={styles.posMetricValue}>{legs.length}</Text>
                    </View>
                  </View>

                  {/* Opened */}
                  <View style={styles.posFooter}>
                    <Text style={styles.posDate}>
                      {p.created_at ? new Date(p.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : ''}
                    </Text>
                    <TouchableOpacity
                      onPress={() => handleClose(p.intent_id, p.underlying)}
                      disabled={closing === p.intent_id}
                      style={styles.closeBtn}
                    >
                      <LinearGradient colors={['#7F1D1D', '#EF4444']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.closeBtnGrad}>
                        <Text style={styles.closeBtnText}>{closing === p.intent_id ? 'Closing...' : 'Close'}</Text>
                      </LinearGradient>
                    </TouchableOpacity>
                  </View>
                </MetalCard>
              );
            })
          )}
          <View style={{ height: 100 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safeArea: { flex: 1 },
  header: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.lg },
  headerTitle: { fontSize: 28, fontWeight: '700', color: Colors.textPrimary, letterSpacing: -0.5 },
  headerSub: { fontSize: 13, color: Colors.textMuted, marginTop: 2 },
  summaryBar: {
    flexDirection: 'row', marginTop: Spacing.lg,
    backgroundColor: Colors.bgGlass, borderRadius: Radius.lg,
    borderWidth: 1, borderColor: Colors.border, padding: Spacing.md,
  },
  summaryItem: { flex: 1, alignItems: 'center' },
  summaryLabel: { fontSize: 11, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.5 },
  summaryValue: { fontSize: 16, fontWeight: '700', color: Colors.textPrimary, marginTop: 4 },
  summaryDivider: { width: 1, backgroundColor: Colors.border },
  scroll: { padding: Spacing.lg, flexGrow: 1 },
  posCard: { marginBottom: 12, padding: Spacing.md },
  posTop: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
  posLeft: { flex: 1 },
  posSymbolRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  posSymbol: { fontSize: 18, fontWeight: '700', color: Colors.textPrimary },
  posStrategy: { fontSize: 12, color: Colors.textMuted, marginTop: 3 },
  posRight: { alignItems: 'flex-end' },
  posPnL: { fontSize: 20, fontWeight: '700' },
  posPct: { fontSize: 13, fontWeight: '500', marginTop: 2 },
  posMetrics: { flexDirection: 'row', gap: 16 },
  posMetric: {},
  posMetricLabel: { fontSize: 11, color: Colors.textMuted },
  posMetricValue: { fontSize: 13, fontWeight: '600', color: Colors.textPrimary, marginTop: 2 },
  posFooter: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 12 },
  posDate: { fontSize: 11, color: Colors.textMuted },
  closeBtn: { borderRadius: Radius.sm, overflow: 'hidden' },
  closeBtnGrad: { paddingHorizontal: 16, paddingVertical: 7 },
  closeBtnText: { fontSize: 13, fontWeight: '600', color: '#fff' },
});
