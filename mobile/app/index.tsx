import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
  TouchableOpacity, StatusBar,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { journalAPI, systemAPI, autoTraderAPI, marketAPI } from '../lib/api';
import { Colors, Spacing, Radius, Gradients } from '../lib/theme';
import { GlassCard, MetalCard, PnLBadge, StatCard, LoadingSpinner, Tag } from '../components/ui';

export default function Dashboard() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [positions, setPositions] = useState<any[]>([]);
  const [systemEnabled, setSystemEnabled] = useState(false);
  const [autoTrader, setAutoTrader] = useState<any>(null);
  const [niftyLtp, setNiftyLtp] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [posRes, sysRes, atRes, ltpRes] = await Promise.allSettled([
        journalAPI.getExecutionIntents(50),
        systemAPI.status(),
        autoTraderAPI.getStatus(),
        marketAPI.getLTP('NIFTY'),
      ]);
      if (posRes.status === 'fulfilled') {
        const all = posRes.value.data || [];
        setPositions(all.filter((p: any) =>
          p.status === 'EXECUTED' && !p.closed_at &&
          !['ZERODHA_HOLDING', 'ZERODHA_ACTUAL', 'DIRECT_ZERODHA'].includes(p.strategy)
        ));
      }
      if (sysRes.status === 'fulfilled') setSystemEnabled(sysRes.value.data?.trading_enabled);
      if (atRes.status === 'fulfilled') setAutoTrader(atRes.value.data);
      if (ltpRes.status === 'fulfilled') setNiftyLtp(ltpRes.value.data?.ltp);
    } catch {}
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => { load(); }, []);

  const totalPnL = positions.reduce((s, p) => s + (p.unrealized_pnl || 0), 0);
  const winners = positions.filter(p => (p.unrealized_pnl || 0) > 0).length;
  const winRate = positions.length > 0 ? Math.round(winners / positions.length * 100) : 0;

  if (loading) return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <LoadingSpinner />
    </View>
  );

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={Colors.accent} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Hero Header */}
        <LinearGradient
          colors={Gradients.header}
          style={styles.hero}
        >
          <SafeAreaView edges={['top']}>
            <View style={styles.heroContent}>
              <View>
                <Text style={styles.heroGreeting}>FastTrade</Text>
                <Text style={styles.heroDate}>{new Date().toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })}</Text>
              </View>
              <View style={styles.heroRight}>
                <View style={[styles.statusDot, { backgroundColor: systemEnabled ? Colors.green : Colors.red }]} />
                <Text style={styles.statusText}>{systemEnabled ? 'Trading ON' : 'Trading OFF'}</Text>
              </View>
            </View>

            {/* Big P&L */}
            <View style={styles.heroPnL}>
              <Text style={styles.heroPnLLabel}>Unrealized P&L</Text>
              <Text style={[styles.heroPnLValue, { color: totalPnL >= 0 ? Colors.green : Colors.red }]}>
                {totalPnL >= 0 ? '+' : ''}₹{Math.abs(totalPnL).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </Text>
              {niftyLtp && (
                <Text style={styles.niftyLtp}>NIFTY ₹{niftyLtp.toLocaleString('en-IN')}</Text>
              )}
            </View>

            <View style={styles.quickActionsRow}>
              <QuickAction label="Scanner" value="Signals" onPress={() => router.push('/scanner')} />
              <QuickAction label="Positions" value="Manage" onPress={() => router.push('/positions')} />
              <QuickAction label="AI Desk" value="Ask" onPress={() => router.push('/ai')} />
            </View>
          </SafeAreaView>
        </LinearGradient>

        <View style={styles.body}>
          {/* Stats Row */}
          <View style={styles.statsRow}>
            <StatCard label="Positions" value={positions.length.toString()} style={{ marginRight: 8 }} />
            <StatCard label="Win Rate" value={`${winRate}%`} color={winRate >= 50 ? Colors.green : Colors.amber} style={{ marginRight: 8 }} />
            <StatCard label="Winners" value={winners.toString()} color={Colors.green} />
          </View>

          {/* Auto Trader Status */}
          {autoTrader && (
            <MetalCard style={styles.card} colors={
              autoTrader.status === 'RUNNING'
                ? ['#064E3B', '#0D1421']
                : ['#111827', '#0D1421']
            }>
              <View style={styles.row}>
                <View>
                  <Text style={styles.cardTitle}>Auto Trader</Text>
                  <Text style={styles.cardSub}>Mode: {autoTrader.mode || 'PAPER'}</Text>
                </View>
                <Tag
                  label={autoTrader.status || 'STOPPED'}
                  color={autoTrader.status === 'RUNNING' ? Colors.green : autoTrader.status === 'PAUSED' ? Colors.amber : Colors.textMuted}
                />
              </View>
              {autoTrader.status === 'RUNNING' && (
                <View style={[styles.row, { marginTop: 12 }]}>
                  <Text style={styles.metricLabel}>Daily P&L</Text>
                  <Text style={[styles.metricValue, { color: (autoTrader.daily_pnl || 0) >= 0 ? Colors.green : Colors.red }]}>
                    ₹{(autoTrader.daily_pnl || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </Text>
                  <Text style={styles.metricLabel}>Trades Today</Text>
                  <Text style={styles.metricValue}>{autoTrader.daily_trades || 0}</Text>
                </View>
              )}
            </MetalCard>
          )}

          {/* Open Positions Preview */}
          <View style={styles.sectionHead}>
            <Text style={styles.sectionTitle}>Open Positions</Text>
            <Text style={styles.sectionCount}>{positions.length}</Text>
          </View>

          {positions.length === 0 ? (
            <GlassCard style={styles.emptyCard}>
              <Text style={styles.emptyText}>📭  No open positions</Text>
              <Text style={styles.emptySubText}>Execute a strategy to open a position</Text>
            </GlassCard>
          ) : (
            positions.slice(0, 5).map((p) => (
              <GlassCard key={p.intent_id} style={styles.posCard}>
                <View style={styles.row}>
                  <View style={styles.posLeft}>
                    <Text style={styles.posSymbol}>{p.underlying}</Text>
                    <Text style={styles.posStrategy}>{p.strategy}</Text>
                  </View>
                  <PnLBadge value={p.unrealized_pnl || 0} />
                </View>
              </GlassCard>
            ))
          )}

          {positions.length > 5 && (
            <Text style={styles.moreText}>+{positions.length - 5} more positions</Text>
          )}

          <View style={{ height: 100 }} />
        </View>
      </ScrollView>
    </View>
  );
}

function QuickAction({ label, value, onPress }: { label: string; value: string; onPress: () => void }) {
  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.85} style={styles.quickActionBtn}>
      <Text style={styles.quickActionValue}>{value}</Text>
      <Text style={styles.quickActionLabel}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  scroll: { flexGrow: 1 },
  hero: { paddingBottom: 32 },
  heroContent: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg, paddingTop: Spacing.md,
  },
  heroGreeting: { fontSize: 28, fontWeight: '700', color: Colors.textPrimary, letterSpacing: -0.5 },
  heroDate: { fontSize: 13, color: Colors.textMuted, marginTop: 2 },
  heroRight: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { fontSize: 13, color: Colors.textSecondary, fontWeight: '500' },
  heroPnL: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.xl },
  heroPnLLabel: { fontSize: 13, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 1 },
  heroPnLValue: { fontSize: 42, fontWeight: '700', letterSpacing: -1, marginTop: 4 },
  niftyLtp: { fontSize: 13, color: Colors.textMuted, marginTop: 6 },
  quickActionsRow: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.lg,
    marginTop: Spacing.md,
    gap: 8,
  },
  quickActionBtn: {
    flex: 1,
    backgroundColor: Colors.bgGlass,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    paddingVertical: 10,
    paddingHorizontal: 8,
  },
  quickActionValue: { color: Colors.textPrimary, fontSize: 14, fontWeight: '700' },
  quickActionLabel: { color: Colors.textSecondary, fontSize: 11, marginTop: 2 },
  body: { padding: Spacing.lg },
  statsRow: { flexDirection: 'row', marginBottom: Spacing.md },
  card: { marginBottom: Spacing.md },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  cardTitle: { fontSize: 16, fontWeight: '600', color: Colors.textPrimary },
  cardSub: { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  metricLabel: { fontSize: 11, color: Colors.textMuted },
  metricValue: { fontSize: 15, fontWeight: '600', color: Colors.textPrimary, marginLeft: 4, marginRight: 12 },
  sectionHead: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', marginBottom: Spacing.sm, marginTop: Spacing.sm,
  },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: Colors.textPrimary },
  sectionCount: {
    fontSize: 13, color: Colors.accent, fontWeight: '600',
    backgroundColor: Colors.accentGlow, paddingHorizontal: 8,
    paddingVertical: 2, borderRadius: Radius.full,
  },
  posCard: { marginBottom: 8, padding: Spacing.md },
  posLeft: { flex: 1 },
  posSymbol: { fontSize: 16, fontWeight: '600', color: Colors.textPrimary },
  posStrategy: { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  emptyCard: { padding: Spacing.xl, alignItems: 'center' },
  emptyText: { fontSize: 16, color: Colors.textSecondary, fontWeight: '500' },
  emptySubText: { fontSize: 13, color: Colors.textMuted, marginTop: 6 },
  moreText: { fontSize: 13, color: Colors.accent, textAlign: 'center', marginTop: 8 },
});
