import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, RefreshControl, ScrollView, StatusBar, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import { Ionicons } from '@expo/vector-icons';
import { journalAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, PnLBadge, ScreenHeader, Tag } from '../components/ui';

type FilterMode = 'all' | 'wins' | 'losses';

const EXCLUDED = ['ZERODHA_HOLDING', 'ZERODHA_ACTUAL', 'DIRECT_ZERODHA'];

export default function JournalScreen() {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterMode>('all');

  const load = useCallback(async () => {
    try {
      const response = await journalAPI.getExecutionIntents(100);
      const all = Array.isArray(response.data) ? response.data : [];
      setEntries(all.filter((entry) => !EXCLUDED.includes(entry.strategy)));
    } catch {
      setEntries([]);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filteredEntries = useMemo(() => {
    if (filter === 'wins') {
      return entries.filter((entry) => (entry.pnl || 0) > 0);
    }
    if (filter === 'losses') {
      return entries.filter((entry) => (entry.pnl || 0) < 0);
    }
    return entries;
  }, [entries, filter]);

  const closedEntries = entries.filter((entry) => entry.closed_at);
  const totalPnL = closedEntries.reduce((sum, entry) => sum + (entry.pnl || 0), 0);
  const wins = closedEntries.filter((entry) => (entry.pnl || 0) > 0).length;
  const losses = closedEntries.filter((entry) => (entry.pnl || 0) < 0).length;
  const winRate = closedEntries.length ? Math.round((wins / closedEntries.length) * 100) : 0;

  const onRefresh = async () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    await load();
  };

  const deleteEntry = (intentId: string) => {
    Alert.alert('Delete Entry', 'Remove this trade from the journal?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await journalAPI.deleteExecutionIntent(intentId);
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
            setExpandedId(null);
            await load();
          } catch (err: any) {
            Alert.alert('Error', err?.response?.data?.detail || 'Delete failed');
          }
        },
      },
    ]);
  };

  const clearClosed = () => {
    Alert.alert('Clear All Closed', 'This removes all closed trade records. Continue?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Clear',
        style: 'destructive',
        onPress: async () => {
          try {
            await journalAPI.clearClosedTrades();
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
            await load();
          } catch (err: any) {
            Alert.alert('Error', err?.response?.data?.detail || 'Clear failed');
          }
        },
      },
    ]);
  };

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safeArea}>
        <ScreenHeader
          title="Journal"
          subtitle="Closed trades, clean and readable"
          badge={<Tag label="TRACKED" color={Colors.accent} bg={Colors.accentSoft} />}
        >
          <View style={styles.summaryStrip}>
            <View style={styles.summaryItem}>
              <Text style={styles.summaryLabel}>Closed</Text>
              <Text style={styles.summaryValue}>{closedEntries.length}</Text>
            </View>
            <View style={styles.summaryDivider} />
            <View style={styles.summaryItem}>
              <Text style={styles.summaryLabel}>Win Rate</Text>
              <Text style={[styles.summaryValue, { color: winRate >= 50 ? Colors.green : Colors.amber }]}>{winRate}%</Text>
            </View>
            <View style={styles.summaryDivider} />
            <View style={styles.summaryItem}>
              <Text style={styles.summaryLabel}>Total P&L</Text>
              <Text style={[styles.summaryValue, { color: totalPnL >= 0 ? Colors.green : Colors.red }]}>₹{Math.abs(totalPnL).toLocaleString('en-IN')}</Text>
            </View>
          </View>
        </ScreenHeader>

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          {/* Clear closed trades button */}
          {closedEntries.length > 0 && (
            <TouchableOpacity style={styles.clearBtn} onPress={clearClosed} activeOpacity={0.8}>
              <Ionicons name="trash-outline" size={14} color={Colors.red} />
              <Text style={styles.clearBtnText}>Clear Closed ({closedEntries.length})</Text>
            </TouchableOpacity>
          )}

          <View style={styles.filterRow}>
            {(['all', 'wins', 'losses'] as FilterMode[]).map((mode) => {
              const active = filter === mode;
              const count = mode === 'all' ? filteredEntries.length : mode === 'wins' ? wins : losses;
              return (
                <TouchableOpacity
                  key={mode}
                  style={[styles.filterChip, active && styles.filterChipActive]}
                  onPress={() => {
                    Haptics.selectionAsync();
                    setFilter(mode);
                  }}
                >
                  <Text style={[styles.filterText, active && styles.filterTextActive]}>{mode.toUpperCase()} ({count})</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {filteredEntries.length === 0 ? (
            <EmptyState
              icon="📚"
              title={filter === 'all' ? 'No Journal Entries' : `No ${filter} yet`}
              subtitle={filter === 'all' ? 'Executed trades will appear here once they close.' : 'Try switching filter or pull to refresh.'}
            />
          ) : (
            filteredEntries.map((entry) => {
              const expanded = expandedId === entry.intent_id;
              const pnl = Number(entry?.pnl ?? 0) || 0;
              const entryPrice = Number(entry?.entry_credit ?? 0) || 0;
              const pct = entryPrice ? (pnl / entryPrice) * 100 : 0;
              const profitable = pnl >= 0;
              return (
                <TouchableOpacity
                  key={entry.intent_id}
                  activeOpacity={0.9}
                  onPress={() => {
                    Haptics.selectionAsync();
                    setExpandedId(expanded ? null : entry.intent_id);
                  }}
                >
                  <GlassCard style={styles.entryCard}>
                    <View style={styles.entryTop}>
                      <View style={styles.entryLeft}>
                        <Text style={styles.entryTitle}>{entry.underlying || 'Unknown'}</Text>
                        <Text style={styles.entrySub}>{entry.strategy || 'Unknown Strategy'}</Text>
                      </View>
                      <View style={styles.entryRight}>
                        <PnLBadge value={pnl} />
                        <Text style={[styles.entryPct, { color: profitable ? Colors.greenLight : Colors.redLight }]}>
                          {profitable ? '+' : ''}{pct.toFixed(2)}%
                        </Text>
                      </View>
                    </View>

                    <View style={styles.metaRow}>
                      <Tag label={entry.status || 'CLOSED'} color={Colors.textSecondary} />
                      <Text style={styles.metaText}>
                        {entry.closed_at
                          ? new Date(entry.closed_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
                          : 'Open'}
                      </Text>
                    </View>

                    {expanded && (
                      <View style={styles.expanded}>
                        <View style={styles.detailRow}>
                          <Text style={styles.detailLabel}>Entry</Text>
                          <Text style={styles.detailValue}>₹{entryPrice.toLocaleString('en-IN')}</Text>
                        </View>
                        <View style={styles.detailRow}>
                          <Text style={styles.detailLabel}>Exit Reason</Text>
                          <Text style={styles.detailValue}>{entry.exit_reason || 'Manual / n.a.'}</Text>
                        </View>
                        <View style={styles.detailRow}>
                          <Text style={styles.detailLabel}>Opened</Text>
                          <Text style={styles.detailValue}>
                            {entry.created_at
                              ? new Date(entry.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
                              : 'n.a.'}
                          </Text>
                        </View>
                        <View style={styles.detailRow}>
                          <Text style={styles.detailLabel}>Closed</Text>
                          <Text style={styles.detailValue}>
                            {entry.closed_at
                              ? new Date(entry.closed_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
                              : 'Still open'}
                          </Text>
                        </View>
                        <TouchableOpacity
                          style={styles.deleteEntryBtn}
                          onPress={() => deleteEntry(entry.intent_id)}
                          activeOpacity={0.8}
                        >
                          <Ionicons name="trash-outline" size={14} color={Colors.red} />
                          <Text style={styles.deleteEntryText}>Delete Entry</Text>
                        </TouchableOpacity>
                      </View>
                    )}
                  </GlassCard>
                </TouchableOpacity>
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
  summaryStrip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.bgGlass,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.lg,
    padding: Spacing.md,
    marginTop: Spacing.lg,
  },
  summaryItem: { flex: 1, alignItems: 'center' },
  summaryLabel: { fontSize: 11, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.8 },
  summaryValue: { fontSize: 16, fontWeight: '700', color: Colors.textPrimary, marginTop: 4 },
  summaryDivider: { width: 1, alignSelf: 'stretch', backgroundColor: Colors.border },
  scroll: { padding: Spacing.lg, flexGrow: 1 },
  filterRow: { flexDirection: 'row', marginBottom: Spacing.md },
  filterChip: {
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.bgGlass,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: Radius.full,
    marginRight: 8,
  },
  filterChipActive: { backgroundColor: Colors.accentGlow, borderColor: Colors.accent },
  filterText: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary },
  filterTextActive: { color: Colors.textPrimary },
  entryCard: { marginBottom: 12 },
  entryTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  entryLeft: { flex: 1, paddingRight: 12 },
  entryRight: { alignItems: 'flex-end' },
  entryTitle: { fontSize: 17, fontWeight: '700', color: Colors.textPrimary },
  entrySub: { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  entryPct: { fontSize: 12, fontWeight: '600', marginTop: 6 },
  metaRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 },
  metaText: { fontSize: 12, color: Colors.textMuted },
  expanded: { marginTop: 14, paddingTop: 14, borderTopWidth: 1, borderTopColor: Colors.border },
  detailRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  detailLabel: { fontSize: 12, color: Colors.textMuted },
  detailValue: { fontSize: 12, color: Colors.textPrimary, fontWeight: '600', maxWidth: '60%', textAlign: 'right' },
  clearBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    alignSelf: 'flex-end',
    marginBottom: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: Radius.sm,
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.3)',
    backgroundColor: 'rgba(239,68,68,0.08)',
  },
  clearBtnText: { fontSize: 12, color: Colors.red, fontWeight: '600' },
  deleteEntryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: 6,
    paddingVertical: 6,
  },
  deleteEntryText: { fontSize: 12, color: Colors.red, fontWeight: '600' },
});
