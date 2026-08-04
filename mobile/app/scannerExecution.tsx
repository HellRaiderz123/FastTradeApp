import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet,
  StatusBar, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { scannerAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { GlassCard, ScreenHeader, Tag } from '../components/ui';

interface ScanSignal {
  symbol: string;
  ltp: number;
  change_percent: number;
  indicators: Record<string, number>;
  suggested_quantity?: number;
  atr?: number | null;
}

interface ScanResult {
  strategy_id: number;
  strategy_name: string;
  direction: string;
  signals: ScanSignal[];
  total_scanned: number;
  matches_found: number;
  execution_mode: string;
  exit_config: Record<string, any>;
}

interface TimelineEvent {
  label: string;
  sublabel: string;
  status: 'done' | 'active' | 'pending';
  time: string;
}

interface ExecutedSignal {
  symbol: string;
  ltp: number;
  change_percent: number;
  quantity: number;
  direction: string;
  status: 'idle' | 'executing' | 'done' | 'failed';
  order?: { status: string; order_id?: string; fill_price?: number; error?: string };
  events: TimelineEvent[];
}

const MODE_BADGE: Record<string, { label: string; color: string; bg: string }> = {
  ZERODHA_LIVE: { label: '🔴 LIVE', color: Colors.red, bg: Colors.redBg },
  PAPER_TRADING: { label: '🟢 PAPER', color: Colors.green, bg: Colors.greenBg },
  ZERODHA_DRY_RUN: { label: '🟡 DRY RUN', color: Colors.amber, bg: Colors.amberBg },
};

function buildInitialEvents(direction: string): TimelineEvent[] {
  const now = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  return [
    { label: direction === 'BUY' ? 'Sold' : 'Bought', sublabel: 'Order Placed', status: 'pending', time: '' },
    { label: 'Exit Triggered', sublabel: 'Condition has been met', status: 'pending', time: '' },
    { label: direction === 'BUY' ? 'Bought' : 'Sold', sublabel: 'Order Placed', status: 'pending', time: '' },
    { label: `${direction} alert`, sublabel: 'Take action', status: 'active', time: now },
    { label: 'Waiting for entry', sublabel: 'Signal detected', status: 'done', time: now },
  ];
}

function buildExecutedEvents(direction: string, fillPrice: number, orderId: string): TimelineEvent[] {
  const now = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  return [
    { label: direction === 'BUY' ? 'Sold' : 'Bought', sublabel: 'Order Placed', status: 'pending', time: '' },
    { label: 'Exit Triggered', sublabel: 'Condition has been met', status: 'pending', time: '' },
    { label: direction === 'BUY' ? 'Bought' : 'Sold', sublabel: `Order ${orderId}`, status: 'done', time: now },
    { label: `${direction} at ₹${fillPrice}`, sublabel: 'Take action', status: 'active', time: now },
    { label: 'Waiting for entry', sublabel: 'Signal detected', status: 'done', time: now },
  ];
}

export default function ScannerExecutionScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ scanResult: string; autoExecute: string }>();

  const scanResult: ScanResult | null = params.scanResult ? JSON.parse(params.scanResult) : null;
  const autoExecute = params.autoExecute === 'true';

  const [signals, setSignals] = useState<ExecutedSignal[]>(() =>
    (scanResult?.signals || []).map(sig => ({
      symbol: sig.symbol,
      ltp: sig.ltp,
      change_percent: sig.change_percent,
      quantity: sig.suggested_quantity || 1,
      direction: scanResult?.direction || 'BUY',
      status: 'idle',
      events: buildInitialEvents(scanResult?.direction || 'BUY'),
    }))
  );

  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(
    scanResult?.signals?.[0]?.symbol || null
  );
  const [executingAll, setExecutingAll] = useState(false);

  const executeOne = useCallback(async (symbol: string) => {
    if (!scanResult) return;
    const sig = scanResult.signals.find(s => s.symbol === symbol);
    if (!sig) return;

    setSignals(prev => prev.map(s => s.symbol === symbol ? { ...s, status: 'executing' } : s));
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    try {
      const res = await scannerAPI.executeSignal({
        symbol,
        direction: scanResult.direction,
        strategy_id: scanResult.strategy_id,
        strategy_name: scanResult.strategy_name,
        exit_config: scanResult.exit_config,
        quantity: sig.suggested_quantity || 1,
        suggested_quantity: sig.suggested_quantity || 1,
      });

      const order = res.data.order;
      const failed = order.status?.includes('FAILED');

      setSignals(prev => prev.map(s =>
        s.symbol === symbol
          ? {
              ...s,
              status: failed ? 'failed' : 'done',
              order,
              events: failed
                ? s.events
                : buildExecutedEvents(scanResult.direction, order.fill_price || sig.ltp, order.order_id || ''),
            }
          : s
      ));

      Haptics.notificationAsync(
        failed ? Haptics.NotificationFeedbackType.Error : Haptics.NotificationFeedbackType.Success
      );
    } catch (err: any) {
      setSignals(prev => prev.map(s =>
        s.symbol === symbol ? { ...s, status: 'failed' } : s
      ));
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      Alert.alert('Execution Failed', err?.response?.data?.detail || 'Could not execute trade');
    }
  }, [scanResult]);

  useEffect(() => {
    if (!autoExecute || !scanResult?.signals?.length) return;
    const run = async () => {
      setExecutingAll(true);
      for (const sig of scanResult.signals) {
        await executeOne(sig.symbol);
      }
      setExecutingAll(false);
    };
    run();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!scanResult) {
    return (
      <View style={styles.root}>
        <SafeAreaView edges={['top']} style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 }}>
          <Text style={{ fontSize: 40 }}>⚠️</Text>
          <Text style={styles.emptyText}>No scan result. Go back and run a scan first.</Text>
          <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
            <Text style={styles.backBtnText}>← Back to Scanner</Text>
          </TouchableOpacity>
        </SafeAreaView>
      </View>
    );
  }

  const modeBadge = MODE_BADGE[scanResult.execution_mode] || MODE_BADGE['ZERODHA_DRY_RUN'];
  const selectedSig = signals.find(s => s.symbol === selectedSymbol);
  const originalSig = scanResult.signals.find(s => s.symbol === selectedSymbol);
  const doneCount = signals.filter(s => s.status === 'done').length;

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={{ flex: 1 }}>
        <ScreenHeader
          title={scanResult.strategy_name}
          subtitle={`${scanResult.matches_found} signal${scanResult.matches_found !== 1 ? 's' : ''} · ${scanResult.total_scanned} scanned`}
          badge={<Tag label={modeBadge.label} color={modeBadge.color} bg={modeBadge.bg} />}
          onBack={() => router.back()}
        />

        {/* Signal List */}
        <View style={styles.listHeader}>
          <Text style={styles.listHeaderCol}>Instrument</Text>
          <Text style={styles.listHeaderCol}>LTP</Text>
          <Text style={styles.listHeaderCol}>Chg%</Text>
          <Text style={[styles.listHeaderCol, { textAlign: 'right' }]}>Status</Text>
        </View>

        {/* Execute All */}
        <TouchableOpacity
          style={[styles.executeAllBtn, (executingAll || signals.every(s => s.status !== 'idle')) && { opacity: 0.5 }]}
          disabled={executingAll || signals.every(s => s.status !== 'idle')}
          onPress={async () => {
            setExecutingAll(true);
            for (const sig of scanResult.signals) {
              const s = signals.find(x => x.symbol === sig.symbol);
              if (s?.status === 'idle') await executeOne(sig.symbol);
            }
            setExecutingAll(false);
          }}
        >
          {executingAll
            ? <ActivityIndicator color="#fff" size="small" />
            : <Text style={styles.executeAllText}>⚡ Execute All ({signals.length - doneCount} remaining)</Text>
          }
        </TouchableOpacity>

        <ScrollView style={styles.signalList} showsVerticalScrollIndicator={false}>
          {signals.map(sig => {
            const isSelected = sig.symbol === selectedSymbol;
            return (
              <TouchableOpacity
                key={sig.symbol}
                activeOpacity={0.8}
                onPress={() => {
                  setSelectedSymbol(sig.symbol);
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                }}
                style={[styles.signalRow, isSelected && styles.signalRowSelected]}
              >
                <View style={styles.signalSymbolCol}>
                  <Text style={styles.signalSymbol}>{sig.symbol}</Text>
                  <Text style={styles.signalExchange}>NSE{sig.quantity > 1 ? ` · x${sig.quantity}` : ''}</Text>
                </View>
                <Text style={styles.signalLtp}>₹{sig.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</Text>
                <Text style={[styles.signalChg, sig.change_percent >= 0 ? { color: Colors.green } : { color: Colors.red }]}>
                  {sig.change_percent >= 0 ? '+' : ''}{sig.change_percent.toFixed(2)}%
                </Text>
                <View style={styles.signalStatusCol}>
                  {sig.status === 'executing' && <ActivityIndicator size="small" color={Colors.accent} />}
                  {sig.status === 'done' && <Text style={[styles.statusBadge, { color: Colors.green }]}>✓ Done</Text>}
                  {sig.status === 'failed' && <Text style={[styles.statusBadge, { color: Colors.red }]}>✗ Failed</Text>}
                  {sig.status === 'idle' && (
                    <Text style={[styles.statusBadge, { color: Colors.accent }]}>
                      {sig.direction === 'BUY' ? '▲ BUY' : '▼ SELL'}
                    </Text>
                  )}
                </View>
              </TouchableOpacity>
            );
          })}

          {/* Timeline for selected signal */}
          {selectedSig && (
            <GlassCard style={styles.timelineCard}>
              <View style={styles.timelineHeader}>
                <View style={styles.timelineSymbolBadge}>
                  <Text style={styles.timelineSymbolInitials}>{selectedSig.symbol.slice(0, 2)}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.timelineSymbolName}>{selectedSig.symbol}</Text>
                  <Text style={styles.timelineSymbolSub}>
                    Avg: ₹{selectedSig.order?.fill_price?.toFixed(2) || '0.00'} × {selectedSig.quantity}
                  </Text>
                </View>
                <Tag label="C1" color={Colors.accent} bg={Colors.accentSoft} />
              </View>

              {/* Events */}
              <View style={styles.timeline}>
                {selectedSig.events.map((event, idx) => (
                  <View key={idx} style={[styles.timelineItem, event.status === 'active' && styles.timelineItemActive]}>
                    <View style={styles.timelineLeft}>
                      <View style={[
                        styles.timelineDot,
                        event.status === 'done' && styles.timelineDotDone,
                        event.status === 'active' && styles.timelineDotActive,
                      ]}>
                        <Text style={styles.timelineDotIcon}>
                          {event.status === 'done' ? '✓' : event.status === 'active' ? (selectedSig.direction === 'BUY' ? '↑' : '↓') : '○'}
                        </Text>
                      </View>
                      {idx < selectedSig.events.length - 1 && <View style={styles.timelineLine} />}
                    </View>
                    <View style={styles.timelineContent}>
                      <Text style={[
                        styles.timelineLabel,
                        event.status === 'done' && { color: Colors.textMuted },
                        event.status === 'pending' && { color: Colors.textFaint },
                      ]}>{event.label}</Text>
                      <Text style={styles.timelineSublabel}>{event.sublabel}</Text>
                    </View>
                    {event.time ? <Text style={styles.timelineTime}>{event.time}</Text> : null}
                  </View>
                ))}
              </View>

              {/* Execute button */}
              {selectedSig.status === 'idle' && (
                <View style={styles.executeBox}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.executeBoxTitle}>
                      {selectedSig.direction === 'BUY' ? 'Buy' : 'Sell'} {selectedSig.symbol}
                    </Text>
                    <Text style={styles.executeBoxSub}>
                      LTP ₹{selectedSig.ltp.toLocaleString('en-IN')} · Qty {selectedSig.quantity}
                    </Text>
                  </View>
                  <TouchableOpacity
                    style={[styles.executeBtn, { backgroundColor: selectedSig.direction === 'BUY' ? Colors.green : Colors.red }]}
                    onPress={() => executeOne(selectedSig.symbol)}
                  >
                    <Text style={styles.executeBtnText}>{selectedSig.direction === 'BUY' ? 'Buy' : 'Sell'}</Text>
                  </TouchableOpacity>
                </View>
              )}

              {/* Indicators */}
              {selectedSig.status === 'idle' && originalSig && Object.keys(originalSig.indicators).length > 0 && (
                <View style={styles.indicatorsRow}>
                  {Object.entries(originalSig.indicators).map(([k, v]) => (
                    <View key={k} style={styles.indicatorChip}>
                      <Text style={styles.indicatorText}>{k}: {typeof v === 'number' ? v.toFixed(2) : v}</Text>
                    </View>
                  ))}
                  {originalSig.atr != null && (
                    <View style={styles.indicatorChip}>
                      <Text style={styles.indicatorText}>ATR: {Number(originalSig.atr).toFixed(2)}</Text>
                    </View>
                  )}
                </View>
              )}

              {/* Order result */}
              {selectedSig.status === 'done' && selectedSig.order && (
                <View style={styles.orderResult}>
                  <Text style={styles.orderResultTitle}>✓ Order Placed</Text>
                  <View style={styles.orderGrid}>
                    <View style={styles.orderGridItem}>
                      <Text style={styles.orderGridLabel}>Order ID</Text>
                      <Text style={styles.orderGridValue}>{selectedSig.order.order_id || '-'}</Text>
                    </View>
                    <View style={styles.orderGridItem}>
                      <Text style={styles.orderGridLabel}>Fill Price</Text>
                      <Text style={styles.orderGridValue}>₹{selectedSig.order.fill_price?.toLocaleString('en-IN') || '-'}</Text>
                    </View>
                    <View style={styles.orderGridItem}>
                      <Text style={styles.orderGridLabel}>Status</Text>
                      <Text style={[styles.orderGridValue, { color: Colors.green }]}>{selectedSig.order.status}</Text>
                    </View>
                    <View style={styles.orderGridItem}>
                      <Text style={styles.orderGridLabel}>Qty</Text>
                      <Text style={styles.orderGridValue}>{selectedSig.quantity}</Text>
                    </View>
                  </View>
                </View>
              )}

              {/* Failed */}
              {selectedSig.status === 'failed' && (
                <View style={styles.failedBox}>
                  <Text style={styles.failedTitle}>✗ Execution Failed</Text>
                  <Text style={styles.failedMsg}>{selectedSig.order?.error || 'Unknown error'}</Text>
                  <TouchableOpacity
                    onPress={() => {
                      setSignals(prev => prev.map(s =>
                        s.symbol === selectedSig.symbol
                          ? { ...s, status: 'idle', events: buildInitialEvents(s.direction) }
                          : s
                      ));
                    }}
                  >
                    <Text style={styles.retryText}>↺ Retry</Text>
                  </TouchableOpacity>
                </View>
              )}
            </GlassCard>
          )}

          <View style={{ height: 100 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  emptyText: { fontSize: 14, color: Colors.textSecondary, textAlign: 'center', paddingHorizontal: 32 },
  backBtn: { paddingHorizontal: 20, paddingVertical: 10, backgroundColor: Colors.accent, borderRadius: Radius.md },
  backBtnText: { color: '#fff', fontWeight: '600', fontSize: 14 },

  listHeader: {
    flexDirection: 'row', paddingHorizontal: Spacing.lg, paddingVertical: 8,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  listHeaderCol: { flex: 1, fontSize: 10, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.8 },

  executeAllBtn: {
    marginHorizontal: Spacing.lg, marginVertical: 8,
    backgroundColor: Colors.accent, borderRadius: Radius.md,
    paddingVertical: 10, alignItems: 'center',
  },
  executeAllText: { color: '#fff', fontWeight: '700', fontSize: 13 },

  signalList: { flex: 1, paddingHorizontal: Spacing.lg },

  signalRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  signalRowSelected: {
    backgroundColor: Colors.accentSoft,
    borderRadius: Radius.md,
    borderLeftWidth: 3, borderLeftColor: Colors.accent,
    paddingHorizontal: 8, marginHorizontal: -8,
  },
  signalSymbolCol: { flex: 1.2 },
  signalSymbol: { fontSize: 13, fontWeight: '700', color: Colors.textPrimary },
  signalExchange: { fontSize: 10, color: Colors.textMuted, marginTop: 1 },
  signalLtp: { flex: 1, fontSize: 12, color: Colors.textPrimary, fontWeight: '600', textAlign: 'center' },
  signalChg: { flex: 1, fontSize: 12, fontWeight: '600', textAlign: 'center' },
  signalStatusCol: { flex: 1, alignItems: 'flex-end' },
  statusBadge: { fontSize: 11, fontWeight: '700' },

  timelineCard: { marginTop: 16 },
  timelineHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 16 },
  timelineSymbolBadge: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: Colors.accentSoft, borderWidth: 1, borderColor: Colors.accent,
    alignItems: 'center', justifyContent: 'center',
  },
  timelineSymbolInitials: { fontSize: 12, fontWeight: '700', color: Colors.accent },
  timelineSymbolName: { fontSize: 15, fontWeight: '700', color: Colors.textPrimary },
  timelineSymbolSub: { fontSize: 11, color: Colors.textMuted, marginTop: 1 },

  timeline: { gap: 0 },
  timelineItem: { flexDirection: 'row', alignItems: 'flex-start', paddingVertical: 6 },
  timelineItemActive: {
    backgroundColor: Colors.accentSoft, borderRadius: Radius.md,
    borderWidth: 1, borderColor: Colors.borderAccent,
    paddingHorizontal: 8, marginHorizontal: -8,
  },
  timelineLeft: { alignItems: 'center', width: 32, marginRight: 10 },
  timelineDot: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: Colors.bgGlassStrong, borderWidth: 2, borderColor: Colors.border,
    alignItems: 'center', justifyContent: 'center',
  },
  timelineDotDone: { borderColor: Colors.textMuted, backgroundColor: Colors.bgGlass },
  timelineDotActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  timelineDotIcon: { fontSize: 12, color: Colors.textSecondary, fontWeight: '700' },
  timelineLine: { width: 1, flex: 1, minHeight: 12, backgroundColor: Colors.border, marginTop: 2 },
  timelineContent: { flex: 1, paddingTop: 4 },
  timelineLabel: { fontSize: 13, fontWeight: '600', color: Colors.textPrimary },
  timelineSublabel: { fontSize: 11, color: Colors.textMuted, marginTop: 1 },
  timelineTime: { fontSize: 10, color: Colors.textMuted, paddingTop: 4 },

  executeBox: {
    flexDirection: 'row', alignItems: 'center',
    marginTop: 14, padding: 12,
    borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.borderAccent,
    backgroundColor: Colors.accentSoft,
  },
  executeBoxTitle: { fontSize: 14, fontWeight: '700', color: Colors.textPrimary },
  executeBoxSub: { fontSize: 11, color: Colors.textMuted, marginTop: 2 },
  executeBtn: { paddingHorizontal: 20, paddingVertical: 10, borderRadius: Radius.md },
  executeBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },

  indicatorsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 },
  indicatorChip: {
    paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: Radius.sm, backgroundColor: Colors.bgGlassStrong,
    borderWidth: 1, borderColor: Colors.border,
  },
  indicatorText: { fontSize: 10, color: Colors.textSecondary },

  orderResult: {
    marginTop: 14, padding: 12,
    borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.green + '50',
    backgroundColor: Colors.greenBg,
  },
  orderResultTitle: { fontSize: 13, fontWeight: '700', color: Colors.green, marginBottom: 10 },
  orderGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  orderGridItem: { width: '48%' },
  orderGridLabel: { fontSize: 10, color: Colors.textMuted },
  orderGridValue: { fontSize: 12, fontWeight: '600', color: Colors.textPrimary, marginTop: 2 },

  failedBox: {
    marginTop: 14, padding: 12,
    borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.red + '50',
    backgroundColor: Colors.redBg,
  },
  failedTitle: { fontSize: 13, fontWeight: '700', color: Colors.red, marginBottom: 4 },
  failedMsg: { fontSize: 11, color: Colors.textMuted },
  retryText: { fontSize: 12, color: Colors.accent, fontWeight: '600', marginTop: 8 },
});
