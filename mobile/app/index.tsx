import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Alert, View, Text, ScrollView, StyleSheet, RefreshControl,
  TouchableOpacity, StatusBar, Animated,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { journalAPI, systemAPI, autoTraderAPI, marketAPI, getApiBaseUrl, authTokenStore } from '../lib/api';
import { Colors, Spacing, Radius, Gradients } from '../lib/theme';
import { GlassCard, MetalCard, PnLBadge, StatCard, LoadingSpinner, Tag } from '../components/ui';
import { sendLocalNotification } from '../lib/notifications';

export default function Dashboard() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [positions, setPositions] = useState<any[]>([]);
  const [systemEnabled, setSystemEnabled] = useState(false);
  const [autoTrader, setAutoTrader] = useState<any>(null);
  const [niftyLtp, setNiftyLtp] = useState<number | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const ltpPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const posPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const wsReconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);
  const prevPnLRef = useRef<number>(0);
  const [wsLive, setWsLive] = useState(false);
  const [atActionLoading, setAtActionLoading] = useState(false);
  const atActionRef = useRef(false);

  // Pulsing LIVE dot
  useEffect(() => {
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 0.2, duration: 900, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 900, useNativeDriver: true }),
      ])
    );
    pulse.start();
    return () => pulse.stop();
  }, [pulseAnim]);

  // Live LTP polling — every 5 seconds
  useEffect(() => {
    ltpPollRef.current = setInterval(async () => {
      try {
        const res = await marketAPI.getLTP('NIFTY');
        if (res.data?.ltp) setNiftyLtp(res.data.ltp);
        setLastUpdated(new Date());
      } catch {}
    }, 5000);
    return () => { if (ltpPollRef.current) clearInterval(ltpPollRef.current); };
  }, []);

  // ── Real-time positions via WebSocket (/ws/positions) ────────────────────
  const handlePositionPayload = useCallback((intents: any[]) => {
    const open = intents.filter((p: any) =>
      p.status === 'EXECUTED' && !p.closed_at &&
      !['ZERODHA_HOLDING', 'ZERODHA_ACTUAL', 'DIRECT_ZERODHA'].includes(p.strategy)
    );
    setPositions(open);
    const newPnL = open.reduce((s: number, p: any) => s + (p.unrealized_pnl || 0), 0);
    const prev = prevPnLRef.current;
    if (prev !== 0 && newPnL - prev < -5000) {
      sendLocalNotification(
        '⚠️ P&L Alert',
        `Portfolio P&L dropped ₹${Math.abs(newPnL - prev).toFixed(0)} to ₹${newPnL.toFixed(0)}`
      );
    }
    prevPnLRef.current = newPnL;
  }, []);

  const connectDashboardWS = useCallback(() => {
    const doConnect = async () => {
      if (unmountedRef.current) return;
      const base = getApiBaseUrl().replace(/\/+$/, '');
      const wsBase = base.startsWith('https://') ? `wss://${base.slice(8)}` : `ws://${base.slice(7)}`;
      const token = await authTokenStore.get();
      const url = token ? `${wsBase}/ws/positions?token=${encodeURIComponent(token)}` : `${wsBase}/ws/positions`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => { if (!unmountedRef.current) setWsLive(true); };
      ws.onmessage = (e) => {
        if (unmountedRef.current) return;
        try {
          const msg = JSON.parse(e.data);
          if (msg?.type === 'positions_update' && Array.isArray(msg.intents)) handlePositionPayload(msg.intents);
        } catch {}
      };
      ws.onclose = () => {
        if (unmountedRef.current) return;
        setWsLive(false);
        // Retry after 8 s — dashboard WS is lower priority than positions screen
        if (wsReconnectRef.current) clearTimeout(wsReconnectRef.current);
        wsReconnectRef.current = setTimeout(() => connectDashboardWS(), 8000);
      };
      ws.onerror = () => { if (!unmountedRef.current) setWsLive(false); };
    };
    doConnect().catch(() => {});
  }, [handlePositionPayload]);

  useEffect(() => {
    unmountedRef.current = false;
    connectDashboardWS();
    return () => {
      unmountedRef.current = true;
      if (wsReconnectRef.current) clearTimeout(wsReconnectRef.current);
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    };
  }, [connectDashboardWS]);

  // HTTP fallback poll — every 30 s when WS is not yet live
  useEffect(() => {
    if (wsLive) return;
    posPollRef.current = setInterval(async () => {
      try {
        const res = await journalAPI.getExecutionIntents(50);
        handlePositionPayload(res.data || []);
      } catch {}
    }, 30000);
    return () => { if (posPollRef.current) clearInterval(posPollRef.current); };
  }, [wsLive, handlePositionPayload]);

  const load = useCallback(async () => {
    try {
      const [posRes, sysRes, atRes, ltpRes] = await Promise.allSettled([
        journalAPI.getExecutionIntents(50),
        systemAPI.status(),
        autoTraderAPI.getStatus(),
        marketAPI.getLTP('NIFTY'),
      ]);
      if (posRes.status === 'fulfilled') handlePositionPayload(posRes.value.data || []);
      if (sysRes.status === 'fulfilled') setSystemEnabled(sysRes.value.data?.trading_enabled);
      if (atRes.status === 'fulfilled') setAutoTrader(atRes.value.data);
      if (ltpRes.status === 'fulfilled') setNiftyLtp(ltpRes.value.data?.ltp);
      setLastUpdated(new Date());
    } catch {}
    setLoading(false);
    setRefreshing(false);
  }, [handlePositionPayload]);

  useEffect(() => { load(); }, []);

  const runAtAction = async (action: 'start' | 'stop' | 'pause') => {
    if (atActionRef.current) return;
    atActionRef.current = true;
    setAtActionLoading(true);
    try {
      if (action === 'start') await autoTraderAPI.start();
      else if (action === 'stop') await autoTraderAPI.stop();
      else await autoTraderAPI.pause();
      const r = await autoTraderAPI.getStatus();
      setAutoTrader((prev: any) => ({ ...prev, ...r.data }));
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.detail || `${action} failed`);
    }
    setAtActionLoading(false);
    atActionRef.current = false;
  };

  const totalPnL = positions.reduce((s, p) => s + (p.unrealized_pnl || 0), 0);
  const winners = positions.filter(p => (p.unrealized_pnl || 0) > 0).length;
  const winRate = positions.length > 0 ? Math.round(winners / positions.length * 100) : 0;
  const rawAutoTraderStatus = String(autoTrader?.status || 'STOPPED').toUpperCase();
  const effectiveAutoTraderStatus = !systemEnabled
    ? 'ENGINE OFF'
    : !autoTrader?.enabled
      ? 'DISABLED'
      : rawAutoTraderStatus;
  const autoTraderRunning = effectiveAutoTraderStatus === 'RUNNING';
  const autoTraderPaused = effectiveAutoTraderStatus === 'PAUSED';
  const openSlots = autoTrader?.max_positions != null
    ? Math.max(Number(autoTrader.max_positions || 0) - Number(autoTrader.open_positions || 0), 0)
    : 0;
  const trackedSymbols = Array.isArray(autoTrader?.underlyings) && autoTrader.underlyings.length > 0
    ? autoTrader.underlyings.join(', ')
    : 'NIFTY';
  const lastScanLabel = autoTrader?.last_scan_at
    ? new Date(autoTrader.last_scan_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
    : 'Not scanned';

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
                <Animated.View style={[styles.liveDot, { opacity: pulseAnim, backgroundColor: wsLive ? Colors.green : Colors.amber }]} />
                <Text style={styles.statusText}>{wsLive ? 'LIVE' : 'POLL'}</Text>
              </View>
            </View>

            {/* Big P&L */}
            <View style={styles.heroPnL}>
              <Text style={styles.heroPnLLabel}>Unrealized P&L</Text>
              <Text style={[styles.heroPnLValue, { color: totalPnL >= 0 ? Colors.green : Colors.red }]}>
                {totalPnL >= 0 ? '+' : ''}₹{Math.abs(totalPnL).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </Text>
              {niftyLtp && (
                <Text style={styles.niftyLtp}>NIFTY ₹{niftyLtp.toLocaleString('en-IN')}{lastUpdated ? `  ·  ${lastUpdated.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}` : ''}</Text>
              )}
            </View>

            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              style={styles.quickActionsRow}
              contentContainerStyle={{ gap: 8, paddingRight: Spacing.lg }}
            >
              <QuickAction label="Scanner" value="Signals" icon="scan-outline" onPress={() => router.push('/scanner')} />
              <QuickAction label="Positions" value="Manage" icon="briefcase-outline" onPress={() => router.push('/positions')} />
              <QuickAction label="AI Desk" value="Ask" icon="sparkles-outline" onPress={() => router.push('/ai')} />
              <QuickAction label="Option Chain" value="View" icon="layers-outline" onPress={() => router.push('/optionChain')} />
              <QuickAction label="Auto Trader" value="Control" icon="flash-outline" onPress={() => router.push('/autoTrader')} />
              <QuickAction label="Watchlists" value="Quotes" icon="star-outline" onPress={() => router.push('/watchlists')} />
              <QuickAction label="Alerts" value="Notify" icon="notifications-outline" onPress={() => router.push('/alerts')} />
              <QuickAction label="Analytics" value="P&L" icon="bar-chart-outline" onPress={() => router.push('/strategyPnl')} />
              <QuickAction label="Finance" value="Cashflow" icon="wallet-outline" onPress={() => router.push('/finance')} />
              <QuickAction label="Screener" value="Filter" icon="funnel-outline" onPress={() => router.push('/screener')} />
              <QuickAction label="Heatmap" value="Market" icon="grid-outline" onPress={() => router.push('/heatmap')} />
              <QuickAction label="Trade Costs" value="Charges" icon="calculator-outline" onPress={() => router.push('/tradeCostTracker')} />
              <QuickAction label="Reconcile" value="Sync" icon="sync-outline" onPress={() => router.push('/brokerReconciliation')} />
              <QuickAction label="ML Center" value="Models" icon="analytics-outline" onPress={() => router.push('/mlCenter')} />
              <QuickAction label="Calendar" value="Events" icon="calendar-outline" onPress={() => router.push('/calendar')} />
            </ScrollView>
          </SafeAreaView>
        </LinearGradient>

        <View style={styles.body}>
          {/* Stats Row */}
          <View style={styles.statsRow}>
            <StatCard label="Positions" value={positions.length.toString()} style={{ marginRight: 8 }} />
            <StatCard label="Win Rate" value={`${winRate}%`} color={winRate >= 50 ? Colors.green : Colors.amber} style={{ marginRight: 8 }} />
            <StatCard label="Winners" value={winners.toString()} color={Colors.green} />
          </View>

          <View style={styles.statsRow}>
            <StatCard label="Engine" value={systemEnabled ? 'ON' : 'OFF'} color={systemEnabled ? Colors.green : Colors.red} style={{ marginRight: 8 }} />
            <StatCard label="Trades Today" value={String(autoTrader?.daily_trades || 0)} color={Colors.accent} style={{ marginRight: 8 }} />
            <StatCard label="Open Slots" value={String(openSlots)} color={openSlots > 0 ? Colors.green : Colors.amber} />
          </View>

          {/* P&L Analytics Card */}
          <GlassCard style={styles.card}>
            <View style={styles.sectionHeadCompact}>
              <Text style={styles.sectionTitle}>Trading Analytics</Text>
              <Tag label="THIS SESSION" color={Colors.accent} bg={Colors.accentSoft} />
            </View>
            <View style={styles.analyticsGrid}>
              <View style={styles.analyticsItem}>
                <Text style={styles.analyticsLabel}>Total P&L</Text>
                <Text style={[styles.analyticsValue, { color: totalPnL >= 0 ? Colors.green : Colors.red }]}>
                  {totalPnL >= 0 ? '+' : ''}₹{Math.abs(totalPnL).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                </Text>
              </View>
              <View style={styles.analyticsItem}>
                <Text style={styles.analyticsLabel}>Win Rate</Text>
                <Text style={[styles.analyticsValue, { color: winRate >= 50 ? Colors.green : Colors.amber }]}>
                  {winRate}%
                </Text>
              </View>
              <View style={styles.analyticsItem}>
                <Text style={styles.analyticsLabel}>Daily P&L</Text>
                <Text style={[styles.analyticsValue, { color: (autoTrader?.daily_pnl || 0) >= 0 ? Colors.green : Colors.red }]}>
                  {(autoTrader?.daily_pnl || 0) >= 0 ? '+' : ''}₹{Math.abs(autoTrader?.daily_pnl || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                </Text>
              </View>
              <View style={styles.analyticsItem}>
                <Text style={styles.analyticsLabel}>Total Trades</Text>
                <Text style={styles.analyticsValue}>
                  {(autoTrader?.daily_trades || 0) + positions.length}
                </Text>
              </View>
            </View>
            <View style={styles.analyticsBar}>
              <View style={styles.analyticsBarLabel}>
                <Text style={styles.analyticsBarText}>Winners</Text>
                <Text style={[styles.analyticsBarValue, { color: Colors.green }]}>{winners}</Text>
              </View>
              <View style={styles.analyticsBarLabel}>
                <Text style={styles.analyticsBarText}>Losers</Text>
                <Text style={[styles.analyticsBarValue, { color: Colors.red }]}>{positions.length - winners}</Text>
              </View>
            </View>
          </GlassCard>

          {/* Auto Trader Status */}
          {autoTrader && (
            <MetalCard style={styles.card} colors={
              autoTraderRunning
                ? ['#064E3B', '#0D1421']
                : autoTraderPaused
                  ? ['#3A2A05', '#0D1421']
                : ['#111827', '#0D1421']
            }>
              <View style={styles.row}>
                <View>
                  <Text style={styles.cardTitle}>Auto Trader</Text>
                  <Text style={styles.cardSub}>Mode: {autoTrader.mode || 'PAPER'}  ·  Engine {systemEnabled ? 'ON' : 'OFF'}</Text>
                </View>
                <Tag
                  label={effectiveAutoTraderStatus}
                  color={autoTraderRunning ? Colors.green : autoTraderPaused ? Colors.amber : Colors.red}
                />
              </View>
              <View style={[styles.row, { marginTop: 12 }] }>
                <Text style={styles.metricLabel}>Daily P&L</Text>
                <Text style={[styles.metricValue, { color: (autoTrader.daily_pnl || 0) >= 0 ? Colors.green : Colors.red }] }>
                  ₹{(autoTrader.daily_pnl || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                </Text>
                <Text style={styles.metricLabel}>Trades Today</Text>
                <Text style={styles.metricValue}>{autoTrader.daily_trades || 0}</Text>
              </View>
              <View style={[styles.row, { marginTop: 10 }] }>
                <Text style={styles.metricLabel}>Open Positions</Text>
                <Text style={styles.metricValue}>{autoTrader.open_positions || 0}/{autoTrader.max_positions || 0}</Text>
                <Text style={styles.metricLabel}>Last Scan</Text>
                <Text style={styles.metricValue}>{lastScanLabel}</Text>
              </View>
              <Text style={styles.inlineMeta}>Underlyings: {trackedSymbols}</Text>
              {autoTrader.error_message ? <Text style={styles.errorText}>{autoTrader.error_message}</Text> : null}
              {/* Quick controls */}
              <View style={styles.atControlRow}>
                <TouchableOpacity
                  style={[styles.atBtn, styles.atBtnStart, (autoTraderRunning || atActionLoading) && styles.atBtnDisabled]}
                  disabled={autoTraderRunning || atActionLoading}
                  onPress={() => runAtAction('start')}
                  activeOpacity={0.8}
                >
                  <Text style={styles.atBtnText}>Start</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.atBtn, styles.atBtnPause, (!autoTraderRunning && !autoTraderPaused || atActionLoading) && styles.atBtnDisabled]}
                  disabled={!autoTraderRunning && !autoTraderPaused || atActionLoading}
                  onPress={() => runAtAction(autoTraderPaused ? 'start' : 'pause')}
                  activeOpacity={0.8}
                >
                  <Text style={styles.atBtnText}>{autoTraderPaused ? 'Resume' : 'Pause'}</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.atBtn, styles.atBtnStop, (!autoTraderRunning && !autoTraderPaused || atActionLoading) && styles.atBtnDisabled]}
                  disabled={!autoTraderRunning && !autoTraderPaused || atActionLoading}
                  onPress={() =>
                    Alert.alert('Stop Auto Trader', 'This will halt all automated trading. Continue?', [
                      { text: 'Cancel', style: 'cancel' },
                      { text: 'Stop', style: 'destructive', onPress: () => runAtAction('stop') },
                    ])
                  }
                  activeOpacity={0.8}
                >
                  <Text style={styles.atBtnText}>Stop</Text>
                </TouchableOpacity>
              </View>
            </MetalCard>
          )}

          {autoTrader && (
            <GlassCard style={styles.card}>
              <View style={styles.sectionHeadCompact}>
                <Text style={styles.sectionTitle}>System Snapshot</Text>
                <Tag label={niftyLtp ? 'MARKET LINKED' : 'WAITING'} color={niftyLtp ? Colors.green : Colors.amber} bg={niftyLtp ? Colors.greenBg : Colors.amberBg} />
              </View>
              <View style={styles.snapshotGrid}>
                <View style={styles.snapshotItem}>
                  <Text style={styles.snapshotLabel}>Scan Interval</Text>
                  <Text style={styles.snapshotValue}>{autoTrader.scan_interval_sec || 0}s</Text>
                </View>
                <View style={styles.snapshotItem}>
                  <Text style={styles.snapshotLabel}>Capital</Text>
                  <Text style={styles.snapshotValue}>₹{Number(autoTrader.capital || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</Text>
                </View>
                <View style={styles.snapshotItem}>
                  <Text style={styles.snapshotLabel}>Tracked</Text>
                  <Text style={styles.snapshotValue}>{Array.isArray(autoTrader.underlyings) ? autoTrader.underlyings.length : 1}</Text>
                </View>
                <View style={styles.snapshotItem}>
                  <Text style={styles.snapshotLabel}>Mode</Text>
                  <Text style={styles.snapshotValue}>{autoTrader.mode || 'PAPER'}</Text>
                </View>
              </View>
            </GlassCard>
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

function QuickAction({
  label,
  value,
  icon,
  onPress,
}: {
  label: string;
  value: string;
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.9} style={styles.quickActionBtn}>
      <View style={styles.quickActionIconWrap}>
        <Ionicons name={icon} size={14} color={Colors.accentLight} />
      </View>
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
  liveDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: Colors.green },
  statusText: { fontSize: 13, color: Colors.green, fontWeight: '600' },
  heroPnL: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.xl },
  heroPnLLabel: { fontSize: 13, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 1 },
  heroPnLValue: { fontSize: 42, fontWeight: '700', letterSpacing: -1, marginTop: 4 },
  niftyLtp: { fontSize: 13, color: Colors.textMuted, marginTop: 6 },
  quickActionsRow: {
    marginTop: Spacing.md,
    paddingLeft: Spacing.lg,
  },
  quickActionBtn: {
    width: 96,
    backgroundColor: Colors.bgGlassStrong,
    borderWidth: 1,
    borderColor: Colors.borderStrong,
    borderRadius: Radius.md,
    paddingVertical: 10,
    paddingHorizontal: 8,
  },
  quickActionIconWrap: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: Colors.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
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
  inlineMeta: { fontSize: 12, color: Colors.textSecondary, marginTop: 10 },
  errorText: { fontSize: 12, color: Colors.red, marginTop: 8 },
  sectionHead: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', marginBottom: Spacing.sm, marginTop: Spacing.sm,
  },
  sectionHeadCompact: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: Spacing.md,
  },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: Colors.textPrimary },
  sectionCount: {
    fontSize: 13, color: Colors.accent, fontWeight: '600',
    backgroundColor: Colors.accentGlow, paddingHorizontal: 8,
    paddingVertical: 2, borderRadius: Radius.full,
  },
  snapshotGrid: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -4 },
  snapshotItem: {
    width: '50%',
    paddingHorizontal: 4,
    marginBottom: 10,
  },
  snapshotLabel: { fontSize: 11, color: Colors.textMuted, marginBottom: 4, textTransform: 'uppercase' },
  snapshotValue: { fontSize: 16, fontWeight: '700', color: Colors.textPrimary },
  posCard: { marginBottom: 8, padding: Spacing.md },
  posLeft: { flex: 1 },
  posSymbol: { fontSize: 16, fontWeight: '600', color: Colors.textPrimary },
  posStrategy: { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  emptyCard: { padding: Spacing.xl, alignItems: 'center' },
  emptyText: { fontSize: 16, color: Colors.textSecondary, fontWeight: '500' },
  emptySubText: { fontSize: 13, color: Colors.textMuted, marginTop: 6 },
  moreText: { fontSize: 13, color: Colors.accent, textAlign: 'center', marginTop: 8 },
  analyticsGrid: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -4, marginBottom: 12 },
  analyticsItem: { width: '50%', paddingHorizontal: 4, marginBottom: 12 },
  analyticsLabel: { fontSize: 11, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.6 },
  analyticsValue: { fontSize: 18, fontWeight: '700', marginTop: 4, color: Colors.textPrimary },
  analyticsBar: { flexDirection: 'row', gap: 8 },
  analyticsBarLabel: { flex: 1, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderTopWidth: 1, borderTopColor: Colors.border, paddingTop: 8 },
  analyticsBarText: { fontSize: 12, color: Colors.textMuted },
  analyticsBarValue: { fontSize: 16, fontWeight: '700' },
  atControlRow: { flexDirection: 'row', gap: 8, marginTop: 14 },
  atBtn: { flex: 1, paddingVertical: 8, borderRadius: Radius.sm, alignItems: 'center' },
  atBtnStart: { backgroundColor: Colors.green },
  atBtnPause: { backgroundColor: Colors.accent },
  atBtnStop: { backgroundColor: Colors.red },
  atBtnDisabled: { opacity: 0.35 },
  atBtnText: { fontSize: 13, fontWeight: '700', color: '#fff' },
});
