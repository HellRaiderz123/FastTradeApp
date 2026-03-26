import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StatusBar, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import { analyticsAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, PnLBadge, ScreenHeader, Tag } from '../components/ui';

type SortKey = 'total_pnl' | 'win_rate' | 'total_trades' | 'profit_factor';

export default function StrategyPnLScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [rows, setRows] = useState<any[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>('total_pnl');
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await analyticsAPI.getStrategyPnL();
      const data = res.data;
      const list = Array.isArray(data) ? data : data?.strategies || data?.rows || [];
      setRows(list);
    } catch {
      setRows([]);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    load();
  };

  const sorted = [...rows].sort((a, b) => {
    if (sortKey === 'win_rate') return (b.win_rate ?? 0) - (a.win_rate ?? 0);
    if (sortKey === 'total_trades') return (b.total_trades ?? 0) - (a.total_trades ?? 0);
    if (sortKey === 'profit_factor') return (b.profit_factor ?? 0) - (a.profit_factor ?? 0);
    return (b.total_pnl ?? 0) - (a.total_pnl ?? 0);
  });

  // Aggregate totals
  const totalPnL = rows.reduce((s, r) => s + (r.total_pnl ?? 0), 0);
  const totalTrades = rows.reduce((s, r) => s + (r.total_trades ?? 0), 0);
  const overallWinRate = rows.length
    ? rows.reduce((s, r) => s + (r.win_rate ?? 0), 0) / rows.length
    : 0;

  const SORTS: { key: SortKey; label: string }[] = [
    { key: 'total_pnl', label: 'P&L' },
    { key: 'win_rate', label: 'Win %' },
    { key: 'profit_factor', label: 'PF' },
    { key: 'total_trades', label: 'Trades' },
  ];

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScreenHeader
          title="Strategy P&L"
          subtitle="Lifetime performance breakdown by strategy"
          badge={<Tag label={`${rows.length} STRATEGIES`} color={Colors.accent} bg={Colors.accentSoft} />}
        />

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          {/* Aggregate summary */}
          <View style={styles.statsRow}>
            <GlassCard style={styles.statCard}>
              <Text style={styles.statLabel}>Total P&L</Text>
              <Text style={[styles.statValue, { color: totalPnL >= 0 ? Colors.green : Colors.red }]}>
                {totalPnL >= 0 ? '+' : ''}₹{Math.abs(totalPnL).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </Text>
            </GlassCard>
            <GlassCard style={styles.statCard}>
              <Text style={styles.statLabel}>Trades</Text>
              <Text style={styles.statValue}>{totalTrades}</Text>
            </GlassCard>
            <GlassCard style={styles.statCard}>
              <Text style={styles.statLabel}>Avg Win %</Text>
              <Text style={[styles.statValue, { color: overallWinRate >= 50 ? Colors.green : Colors.red }]}>
                {overallWinRate.toFixed(1)}%
              </Text>
            </GlassCard>
          </View>

          {/* Sort bar */}
          <View style={styles.sortRow}>
            <Text style={styles.sortLabel}>Sort by:</Text>
            {SORTS.map((s) => (
              <TouchableOpacity
                key={s.key}
                style={[styles.sortPill, sortKey === s.key && styles.sortPillActive]}
                onPress={() => { setSortKey(s.key); Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); }}
                activeOpacity={0.8}
              >
                <Text style={[styles.sortPillText, sortKey === s.key && styles.sortPillTextActive]}>{s.label}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {sorted.length === 0 ? (
            <EmptyState icon="📊" title="No Strategy Data" subtitle="Close some trades to see per-strategy analytics." />
          ) : (
            sorted.map((row, idx) => {
              const name = row.strategy || row.name || row.strategy_name || `Strategy #${idx + 1}`;
              const pnl = row.total_pnl ?? 0;
              const winRate = row.win_rate ?? 0;
              const trades = row.total_trades ?? 0;
              const pf = row.profit_factor ?? 0;
              const maxDd = row.max_drawdown_pct ?? row.max_drawdown ?? 0;
              const avgWin = row.avg_win ?? 0;
              const avgLoss = row.avg_loss ?? 0;
              const isExpanded = expanded === name;

              return (
                <TouchableOpacity
                  key={name}
                  activeOpacity={0.9}
                  onPress={() => {
                    setExpanded(isExpanded ? null : name);
                    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                  }}
                >
                  <GlassCard style={styles.rowCard}>
                    <View style={styles.rowHeader}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.rowName} numberOfLines={1}>{name}</Text>
                        <Text style={styles.rowTrades}>{trades} trade{trades !== 1 ? 's' : ''}</Text>
                      </View>
                      <View style={{ alignItems: 'flex-end' }}>
                        <PnLBadge value={pnl} />
                        <Text style={[styles.rowWinRate, { color: winRate >= 50 ? Colors.green : Colors.red }]}>
                          {winRate.toFixed(1)}% win
                        </Text>
                      </View>
                    </View>

                    {isExpanded && (
                      <View style={styles.expandedGrid}>
                        {[
                          ['Profit Factor', pf.toFixed(2)],
                          ['Win Rate', `${winRate.toFixed(1)}%`],
                          ['Max Drawdown', `${maxDd.toFixed(2)}%`],
                          ['Avg Win', `₹${avgWin.toFixed(0)}`],
                          ['Avg Loss', `₹${avgLoss.toFixed(0)}`],
                          ['Total Trades', String(trades)],
                        ].map(([label, val]) => (
                          <View key={label} style={styles.expandedCell}>
                            <Text style={styles.expandedLabel}>{label}</Text>
                            <Text style={styles.expandedVal}>{val}</Text>
                          </View>
                        ))}
                      </View>
                    )}
                  </GlassCard>
                </TouchableOpacity>
              );
            })
          )}

          <View style={{ height: 96 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safe: { flex: 1 },
  scroll: { padding: Spacing.lg },
  statsRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  statCard: { flex: 1, alignItems: 'center', paddingVertical: 12 },
  statLabel: { fontSize: 11, color: Colors.textMuted, marginBottom: 4 },
  statValue: { fontSize: 15, fontWeight: '700', color: Colors.textPrimary },
  sortRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 12, flexWrap: 'wrap' },
  sortLabel: { fontSize: 12, color: Colors.textMuted, marginRight: 2 },
  sortPill: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: Radius.sm,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.bgGlass,
  },
  sortPillActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  sortPillText: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary },
  sortPillTextActive: { color: Colors.accentLight },
  rowCard: { marginBottom: 8 },
  rowHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rowName: { fontSize: 14, fontWeight: '700', color: Colors.textPrimary, maxWidth: 220 },
  rowTrades: { fontSize: 11, color: Colors.textMuted, marginTop: 2 },
  rowWinRate: { fontSize: 11, fontWeight: '600', marginTop: 3 },
  expandedGrid: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 12, borderTopWidth: 1, borderTopColor: Colors.border, paddingTop: 10, gap: 0 },
  expandedCell: { width: '50%', paddingVertical: 5, paddingRight: 8 },
  expandedLabel: { fontSize: 11, color: Colors.textMuted, marginBottom: 2 },
  expandedVal: { fontSize: 14, fontWeight: '600', color: Colors.textPrimary },
});
