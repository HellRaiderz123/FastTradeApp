import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
  TouchableOpacity, Alert, StatusBar, Modal, TextInput, KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';
import { journalAPI, exitAPI, intentAPI, getApiBaseUrl, authTokenStore } from '../lib/api';
import { Colors, Spacing, Radius } from '../lib/theme';
import { GlassCard, MetalCard, PnLBadge, EmptyState, LoadingSpinner, ScreenHeader, Tag, ProgressBar } from '../components/ui';

const EXCLUDED = ['ZERODHA_HOLDING', 'ZERODHA_ACTUAL', 'DIRECT_ZERODHA'];
type PositionFilter = 'all' | 'live' | 'paper';

export default function Positions() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [positions, setPositions] = useState<any[]>([]);
  const [closing, setClosing] = useState<string | null>(null);
  const [filter, setFilter] = useState<PositionFilter>('all');
  const [wsConnected, setWsConnected] = useState(false);
  const [wsAuthFailed, setWsAuthFailed] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const statusMessageTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const unmountedRef = useRef(false);

  const applyOpenPositions = useCallback((all: any[]) => {
    setPositions(
      (all || []).filter(
        (p: any) => p.status === 'EXECUTED' && !p.closed_at && !EXCLUDED.includes(p.strategy)
      )
    );
  }, []);

  const load = useCallback(async () => {
    try {
      const res = await journalAPI.getExecutionIntents(100);
      applyOpenPositions(res.data || []);
    } catch {
      setStatusMessage('Could not refresh positions. Check connection and retry.');
    }
    setLoading(false);
    setRefreshing(false);
  }, [applyOpenPositions, wsConnected]);

  const wsUrlFromHttpBase = useCallback((httpBase: string) => {
    const trimmed = String(httpBase || '').replace(/\/+$/, '');
    if (trimmed.startsWith('https://')) return `wss://${trimmed.slice(8)}/ws/positions`;
    if (trimmed.startsWith('http://')) return `ws://${trimmed.slice(7)}/ws/positions`;
    return `ws://${trimmed}/ws/positions`;
  }, []);

  const connectWebSocket = useCallback(() => {
    const doConnect = async () => {
    if (unmountedRef.current) return;

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const baseUrl = wsUrlFromHttpBase(getApiBaseUrl());
    const token = await authTokenStore.get();
    const wsUrl = token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmountedRef.current) return;
      // Cancel any pending "disconnected" banner
      if (statusMessageTimerRef.current) {
        clearTimeout(statusMessageTimerRef.current);
        statusMessageTimerRef.current = null;
      }
      reconnectAttemptRef.current = 0;
      setWsConnected(true);
      setWsAuthFailed(false);
      setStatusMessage(null);
    };

    ws.onmessage = (event) => {
      if (unmountedRef.current) return;
      try {
        const payload = JSON.parse(event.data);
        if (payload?.type === 'positions_update' && Array.isArray(payload.intents)) {
          applyOpenPositions(payload.intents);
          setLoading(false);
          setRefreshing(false);
        }
      } catch {}
    };

    ws.onerror = () => {
      if (unmountedRef.current) return;
      setWsConnected(false);
    };

    ws.onclose = (event) => {
      if (unmountedRef.current) return;
      setWsConnected(false);

      // Policy violation (1008) is used by backend for auth rejection.
      // Do not reconnect indefinitely in that case.
      if (event.code === 1008) {
        setWsAuthFailed(true);
        setStatusMessage('Session expired for live feed. Please sign in again.');
        return;
      }

      // Delay showing the disconnect banner by 5 s — brief drops stay invisible.
      if (statusMessageTimerRef.current) clearTimeout(statusMessageTimerRef.current);
      statusMessageTimerRef.current = setTimeout(() => {
        if (!unmountedRef.current) setStatusMessage('Live feed disconnected. Reconnecting...');
      }, 5000);

      // Exponential backoff: 3 s → 6 s → 12 s … capped at 30 s
      reconnectAttemptRef.current += 1;
      const delay = Math.min(3000 * Math.pow(2, reconnectAttemptRef.current - 1), 30000);
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = setTimeout(() => connectWebSocket(), delay);
    };
    };

    doConnect().catch(() => {
      if (unmountedRef.current) return;
      setWsConnected(false);
    });
  }, [applyOpenPositions, wsUrlFromHttpBase]);

  useEffect(() => {
    unmountedRef.current = false;
    load();
    connectWebSocket();

    return () => {
      unmountedRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (statusMessageTimerRef.current) clearTimeout(statusMessageTimerRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connectWebSocket, load]);

  // HTTP polling fallback — runs every 10 s when WebSocket is not connected
  useEffect(() => {
    if (wsConnected) return;
    const pollId = setInterval(() => {
      if (!unmountedRef.current) load();
    }, 10000);
    return () => clearInterval(pollId);
  }, [wsConnected, load]);

  // ── Set Target Modal ──────────────────────────────────────────────
  const [targetModal, setTargetModal] = useState<{ visible: boolean; position: any | null }>({ visible: false, position: null });
  const [tpInput, setTpInput] = useState('');
  const [slInput, setSlInput] = useState('');
  const [trailingInput, setTrailingInput] = useState('');
  const [tpMode, setTpMode] = useState<'abs' | 'pct'>('abs');
  const [slMode, setSlMode] = useState<'abs' | 'pct'>('abs');
  const [saving, setSaving] = useState(false);

  const openTargetModal = (position: any) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setTpInput(position.tp ? String(position.tp) : '');
    setSlInput(position.sl ? String(Math.abs(position.sl)) : '');
    setTrailingInput(position.trailing_sl_pct ? String(position.trailing_sl_pct) : '');
    setTpMode('abs');
    setSlMode('abs');
    setTargetModal({ visible: true, position });
  };

  const saveTarget = async () => {
    const pos = targetModal.position;
    if (!pos) return;
    setSaving(true);
    try {
      const payload: any = {};
      if (tpInput) {
        if (tpMode === 'pct') payload.tp_pct = parseFloat(tpInput);
        else payload.tp = parseFloat(tpInput);
      }
      if (slInput) {
        if (slMode === 'pct') payload.sl_pct = parseFloat(slInput);
        else payload.sl = -Math.abs(parseFloat(slInput));
      }
      if (trailingInput) payload.trailing_sl = parseFloat(trailingInput);
      await intentAPI.updateTpSl(pos.intent_id, payload);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setTargetModal({ visible: false, position: null });
      load();
    } catch {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      Alert.alert('Error', 'Failed to update targets');
    }
    setSaving(false);
  };

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

  const isLivePosition = (position: any) => {
    const mode = position.execution_result?.mode || '';
    return String(mode).includes('ZERODHA_LIVE');
  };

  const filteredPositions = positions.filter((position) => {
    if (filter === 'live') return isLivePosition(position);
    if (filter === 'paper') return !isLivePosition(position);
    return true;
  });

  const liveCount = positions.filter(isLivePosition).length;
  const paperCount = positions.length - liveCount;

  const onRefresh = async () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    await load();
  };

  if (loading) return <View style={styles.root}><LoadingSpinner /></View>;

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safeArea}>
        <ScreenHeader
          title="Positions"
          subtitle={`${positions.length} open · ${liveCount} live`}
          badge={
            <Tag
              label={wsConnected ? 'LIVE FEED' : wsAuthFailed ? 'AUTH' : 'POLLING'}
              color={wsConnected ? Colors.green : wsAuthFailed ? Colors.red : '#F59E0B'}
              bg={wsConnected ? Colors.greenBg : wsAuthFailed ? Colors.redBg : 'rgba(245,158,11,0.12)'}
            />
          }
        >
          {statusMessage ? <Text style={styles.statusNotice}>{statusMessage}</Text> : null}
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
        </ScreenHeader>
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.filterRow}>
            {([
              { key: 'all', label: `ALL (${positions.length})` },
              { key: 'live', label: `LIVE (${liveCount})` },
              { key: 'paper', label: `PAPER (${paperCount})` },
            ] as Array<{ key: PositionFilter; label: string }>).map((item) => {
              const active = filter === item.key;
              return (
                <TouchableOpacity
                  key={item.key}
                  style={[styles.filterChip, active && styles.filterChipActive]}
                  onPress={() => {
                    Haptics.selectionAsync();
                    setFilter(item.key);
                  }}
                >
                  <Text style={[styles.filterText, active && styles.filterTextActive]}>{item.label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {filteredPositions.length === 0 ? (
            <EmptyState icon="📭" title="No Open Positions" subtitle="Execute a strategy to open a position" />
          ) : (
            filteredPositions.map((p) => {
              const pnl = p.unrealized_pnl || 0;
              const entry = p.entry_credit || 0;
              const pct = entry > 0 ? (pnl / entry) * 100 : 0;
              const isPos = pnl >= 0;
              const isLive = isLivePosition(p);
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
                        <Text style={[styles.posMetricValue, { color: Colors.red }]}>₹{Math.abs(p.sl)}</Text>
                      </View>
                    )}
                    {p.trailing_sl_pct ? (
                      <View style={styles.posMetric}>
                        <Text style={styles.posMetricLabel}>Trail</Text>
                        <Text style={[styles.posMetricValue, { color: Colors.amber }]}>{p.trailing_sl_pct}%</Text>
                      </View>
                    ) : null}
                    <View style={styles.posMetric}>
                      <Text style={styles.posMetricLabel}>Legs</Text>
                      <Text style={styles.posMetricValue}>{legs.length}</Text>
                    </View>
                  </View>

                  {/* Opened + Actions */}
                  <View style={styles.posFooter}>
                    <Text style={styles.posDate}>
                      {p.created_at ? new Date(p.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : ''}
                    </Text>
                    <View style={{ flexDirection: 'row', gap: 8 }}>
                      <TouchableOpacity onPress={() => openTargetModal(p)} style={styles.targetBtn}>
                        <Text style={styles.targetBtnText}>🎯 Target</Text>
                      </TouchableOpacity>
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
                  </View>
                </MetalCard>
              );
            })
          )}

          {/* Set Target Modal */}
          <Modal visible={targetModal.visible} transparent animationType="slide">
            <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.modalOverlay}>
              <View style={styles.modalContent}>
                <Text style={styles.modalTitle}>Set Profit / Loss Target</Text>
                <Text style={styles.modalSubtitle}>{targetModal.position?.underlying}</Text>

                {/* TP */}
                <View style={styles.modalRow}>
                  <Text style={styles.modalLabel}>Take Profit</Text>
                  <View style={styles.modeToggle}>
                    <TouchableOpacity onPress={() => setTpMode('abs')} style={[styles.modeBtn, tpMode === 'abs' && styles.modeBtnActive]}>
                      <Text style={[styles.modeBtnText, tpMode === 'abs' && styles.modeBtnTextActive]}>₹</Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => setTpMode('pct')} style={[styles.modeBtn, tpMode === 'pct' && styles.modeBtnActive]}>
                      <Text style={[styles.modeBtnText, tpMode === 'pct' && styles.modeBtnTextActive]}>%</Text>
                    </TouchableOpacity>
                  </View>
                </View>
                <TextInput
                  style={styles.modalInput}
                  value={tpInput}
                  onChangeText={setTpInput}
                  placeholder={tpMode === 'pct' ? 'e.g. 5 (exit at 5% profit)' : 'e.g. 6000'}
                  placeholderTextColor={Colors.textMuted}
                  keyboardType="numeric"
                />

                {/* SL */}
                <View style={styles.modalRow}>
                  <Text style={styles.modalLabel}>Stop Loss</Text>
                  <View style={styles.modeToggle}>
                    <TouchableOpacity onPress={() => setSlMode('abs')} style={[styles.modeBtn, slMode === 'abs' && styles.modeBtnActive]}>
                      <Text style={[styles.modeBtnText, slMode === 'abs' && styles.modeBtnTextActive]}>₹</Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => setSlMode('pct')} style={[styles.modeBtn, slMode === 'pct' && styles.modeBtnActive]}>
                      <Text style={[styles.modeBtnText, slMode === 'pct' && styles.modeBtnTextActive]}>%</Text>
                    </TouchableOpacity>
                  </View>
                </View>
                <TextInput
                  style={styles.modalInput}
                  value={slInput}
                  onChangeText={setSlInput}
                  placeholder={slMode === 'pct' ? 'e.g. 3 (exit at 3% loss)' : 'e.g. 2000'}
                  placeholderTextColor={Colors.textMuted}
                  keyboardType="numeric"
                />

                {/* Trailing SL */}
                <Text style={[styles.modalLabel, { marginTop: 12 }]}>Trailing SL (%)</Text>
                <TextInput
                  style={styles.modalInput}
                  value={trailingInput}
                  onChangeText={setTrailingInput}
                  placeholder="e.g. 50 (exit if profit drops 50% from peak)"
                  placeholderTextColor={Colors.textMuted}
                  keyboardType="numeric"
                />

                <View style={styles.modalActions}>
                  <TouchableOpacity onPress={() => setTargetModal({ visible: false, position: null })} style={styles.modalCancelBtn}>
                    <Text style={styles.modalCancelText}>Cancel</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={saveTarget} disabled={saving} style={styles.modalSaveBtn}>
                    <LinearGradient colors={['#1D4ED8', '#3B82F6']} style={styles.modalSaveBtnGrad}>
                      <Text style={styles.modalSaveText}>{saving ? 'Saving...' : 'Save'}</Text>
                    </LinearGradient>
                  </TouchableOpacity>
                </View>
              </View>
            </KeyboardAvoidingView>
          </Modal>
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
  statusNotice: {
    marginTop: 10,
    fontSize: 12,
    color: Colors.amber,
    fontWeight: '600',
  },
  scroll: { padding: Spacing.lg, flexGrow: 1 },
  filterRow: { flexDirection: 'row', marginBottom: Spacing.md, gap: 8 },
  filterChip: {
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.bgGlass,
    borderRadius: Radius.full,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  filterChipActive: { borderColor: Colors.accent, backgroundColor: Colors.accentGlow },
  filterText: { fontSize: 12, color: Colors.textSecondary, fontWeight: '600' },
  filterTextActive: { color: Colors.textPrimary },
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
  targetBtn: {
    borderRadius: Radius.sm, borderWidth: 1, borderColor: Colors.accent,
    paddingHorizontal: 12, paddingVertical: 6, backgroundColor: Colors.accentSoft,
  },
  targetBtnText: { fontSize: 12, fontWeight: '600', color: Colors.accentLight },
  // Modal
  modalOverlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.6)' },
  modalContent: {
    backgroundColor: Colors.bgElevated, borderTopLeftRadius: Radius.xl, borderTopRightRadius: Radius.xl,
    padding: Spacing.lg, paddingBottom: 40,
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: Colors.textPrimary },
  modalSubtitle: { fontSize: 13, color: Colors.textSecondary, marginBottom: 16 },
  modalRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 },
  modalLabel: { fontSize: 13, fontWeight: '600', color: Colors.textSecondary },
  modeToggle: { flexDirection: 'row', gap: 4 },
  modeBtn: { paddingHorizontal: 12, paddingVertical: 4, borderRadius: Radius.full, borderWidth: 1, borderColor: Colors.border },
  modeBtnActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  modeBtnText: { fontSize: 13, color: Colors.textMuted, fontWeight: '600' },
  modeBtnTextActive: { color: Colors.accentLight },
  modalInput: {
    marginTop: 6, borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.sm,
    padding: 12, fontSize: 15, color: Colors.textPrimary, backgroundColor: Colors.bgGlass,
  },
  modalActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 12, marginTop: 20 },
  modalCancelBtn: { paddingHorizontal: 16, paddingVertical: 10 },
  modalCancelText: { fontSize: 14, color: Colors.textSecondary, fontWeight: '600' },
  modalSaveBtn: { borderRadius: Radius.sm, overflow: 'hidden' },
  modalSaveBtnGrad: { paddingHorizontal: 24, paddingVertical: 10 },
  modalSaveText: { fontSize: 14, fontWeight: '700', color: '#fff' },
});
