import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, RefreshControl, ScrollView, StatusBar, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import { useRouter } from 'expo-router';
import { scannerAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, PrimaryButton, ScreenHeader, Tag } from '../components/ui';

const FALLBACK_STRATEGIES = [
  { id: 1, name: 'Momentum Breakout Lab', timeframe: 'Day', universe: 'NIFTY50', direction: 'BUY', is_active: true, last_signal_count: 4, auto_scan_enabled: false, auto_amount: 10000, exit_config: { sl_pct: 5, tp_pct: 10, tsl_pct: 0, exit_mode: 'percentage' }, strategy_type: 'Equity Swing' },
  { id: 2, name: 'Hourly Mean Reversion', timeframe: '1 Hour', universe: 'NIFTY50', direction: 'BUY', is_active: true, last_signal_count: 2, auto_scan_enabled: true, auto_amount: 15000, exit_config: { sl_pct: 3, tp_pct: 8, tsl_pct: 1.5, exit_mode: 'percentage' }, strategy_type: 'Equity Swing' },
  { id: 3, name: 'Volume Shock Filter', timeframe: '15 Min', universe: 'BANKNIFTY', direction: 'SELL', is_active: false, last_signal_count: 0, auto_scan_enabled: false, auto_amount: 10000, exit_config: { sl_pct: 1.5, tp_pct: 3, tsl_pct: 0.5, exit_mode: 'percentage' }, strategy_type: 'Intraday' },
];

export default function ScannerScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanStatus, setScanStatus] = useState('');
  const [strategies, setStrategies] = useState<any[]>([]);
  const [usingFallbackData, setUsingFallbackData] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [autoAmountInput, setAutoAmountInput] = useState('10000');
  const [savingAutoAmount, setSavingAutoAmount] = useState(false);
  const [togglingAutoExecute, setTogglingAutoExecute] = useState(false);
  const [deletingStrategyId, setDeletingStrategyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await scannerAPI.listStrategies();
      const data = Array.isArray(res.data)
        ? res.data
        : Array.isArray(res.data?.strategies)
          ? res.data.strategies
          : res.data?.items || [];
      const useFallback = !data.length;
      setUsingFallbackData(useFallback);
      setStrategies(useFallback ? FALLBACK_STRATEGIES : data);
    } catch {
      setUsingFallbackData(true);
      setStrategies(FALLBACK_STRATEGIES);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  const selected = useMemo(() => {
    return strategies.find((strategy) => strategy.id === selectedId) || strategies[0] || null;
  }, [selectedId, strategies]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (selected?.auto_amount != null) {
      setAutoAmountInput(String(Math.round(Number(selected.auto_amount || 10000))));
    }
  }, [selected?.id, selected?.auto_amount]);

  const onRefresh = async () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setScanStatus('');
    await load();
  };

  const scanSelected = async () => {
    if (!selected?.id) {
      return;
    }
    if (usingFallbackData) {
      setScanStatus('Scanner is showing demo strategies. Check backend/API URL and refresh.');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      return;
    }

    setScanning(true);
    setScanStatus('');
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    try {
      const res = await scannerAPI.scanStrategy(selected.id);
      const count = Number(
        res.data?.matches_found
        ?? (Array.isArray(res.data?.signals) ? res.data.signals.length : undefined)
        ?? (Array.isArray(res.data?.signal_history) ? res.data.signal_history.length : undefined)
        ?? res.data?.signal_count
        ?? 0
      );
      setScanStatus(`Scan complete: ${count} signal${count === 1 ? '' : 's'} found`);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.response?.data?.error || 'Scan failed. Please try again.';
      setScanStatus(String(detail));
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }
    setScanning(false);
  };

  const openBacktestForm = () => {
    if (!selected?.id) return;
    if (usingFallbackData) {
      setScanStatus('Scanner is showing demo strategies. Connect backend first, then open Backtest.');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      return;
    }

    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    const exitConfig = selected.exit_config || {};
    router.push({
      pathname: '/backtest',
      params: {
        strategyId: String(selected.id),
        strategyName: selected.name || `Strategy #${selected.id}`,
        universe: selected.universe || 'NIFTY50',
        timeframe: selected.timeframe || 'Day',
        backtestType: 'scanner',
        slPct: String(exitConfig.sl_pct ?? 5),
        tpPct: String(exitConfig.tp_pct ?? 10),
        tslPct: String(exitConfig.tsl_pct ?? 0),
        exitMode: String(exitConfig.exit_mode || 'percentage'),
        positionSizePct: '10',
        maxOpenTrades: '5',
        initialCapital: '100000',
      },
    });
  };

  const updateStrategy = useCallback((strategyId: number, patch: Record<string, any>) => {
    setStrategies((prev) => prev.map((strategy) => strategy.id === strategyId ? { ...strategy, ...patch } : strategy));
  }, []);

  const handleToggleAutoExecute = async () => {
    if (!selected?.id) return;
    if (usingFallbackData) {
      setScanStatus('Demo strategies cannot change auto-execute. Connect backend first.');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      return;
    }

    setTogglingAutoExecute(true);
    try {
      const nextEnabled = !Boolean(selected.auto_scan_enabled);
      const res = nextEnabled
        ? await scannerAPI.startAutoScan(selected.id)
        : await scannerAPI.stopAutoScan(selected.id);
      updateStrategy(selected.id, { auto_scan_enabled: nextEnabled });
      setScanStatus(res.data?.message || (nextEnabled ? 'Auto-execute enabled' : 'Auto-execute disabled'));
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to update auto-execute setting.';
      setScanStatus(String(detail));
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }
    setTogglingAutoExecute(false);
  };

  const handleSaveAutoAmount = async () => {
    if (!selected?.id) return;
    const amount = Number(autoAmountInput);
    if (!Number.isFinite(amount) || amount < 100) {
      setScanStatus('Auto amount must be at least 100.');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      return;
    }
    if (usingFallbackData) {
      setScanStatus('Demo strategies cannot save auto amount. Connect backend first.');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      return;
    }

    setSavingAutoAmount(true);
    try {
      const res = await scannerAPI.setAutoAmount(selected.id, amount);
      updateStrategy(selected.id, { auto_amount: amount });
      setScanStatus(res.data?.message || `Auto amount updated to ₹${amount.toLocaleString('en-IN')}`);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to update auto amount.';
      setScanStatus(String(detail));
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }
    setSavingAutoAmount(false);
  };

  const handleDeleteStrategy = () => {
    if (!selected?.id) return;
    if (usingFallbackData) {
      setScanStatus('Demo strategies cannot be deleted. Connect backend first.');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      return;
    }

    Alert.alert('Delete Strategy', `Delete "${selected.name}"?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          setDeletingStrategyId(selected.id);
          try {
            await scannerAPI.deleteStrategy(selected.id);
            await load();
            setSelectedId((current) => current === selected.id ? null : current);
            setScanStatus(`Deleted strategy: ${selected.name}`);
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          } catch (error: any) {
            const detail = error?.response?.data?.detail || 'Failed to delete strategy.';
            setScanStatus(String(detail));
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
          }
          setDeletingStrategyId(null);
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
          title="Scanner"
          subtitle="Condition strategies and signals in a phone-first layout"
          badge={<Tag label="LIVE SCAN" color={Colors.green} bg={Colors.greenBg} />}
        />

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.metricGrid}>
            <GlassCard style={styles.metricCard}>
              <Text style={styles.metricLabel}>Strategies</Text>
              <Text style={styles.metricValue}>{strategies.length}</Text>
            </GlassCard>
            <GlassCard style={styles.metricCard}>
              <Text style={styles.metricLabel}>Active</Text>
              <Text style={[styles.metricValue, { color: Colors.green }]}>{strategies.filter((item) => item.is_active).length}</Text>
            </GlassCard>
            <GlassCard style={styles.metricCard}>
              <Text style={styles.metricLabel}>Signals</Text>
              <Text style={[styles.metricValue, { color: Colors.accent }]}>{strategies.reduce((sum, item) => sum + (item.last_signal_count || 0), 0)}</Text>
            </GlassCard>
          </View>

          <Text style={styles.sectionTitle}>Strategy Lab</Text>
          {strategies.length === 0 ? (
            <EmptyState icon="🔍" title="No Scanner Strategies" subtitle="Saved scanner strategies will appear here." />
          ) : (
            strategies.map((strategy) => {
              const active = selected?.id === strategy.id;
              return (
                <TouchableOpacity
                  key={strategy.id}
                  activeOpacity={0.9}
                  onPress={() => {
                    setSelectedId(strategy.id);
                    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                  }}
                >
                  <GlassCard style={[styles.strategyCard, active && styles.strategyCardActive]}>
                    <View style={styles.strategyTop}>
                      <View style={styles.strategyMeta}>
                        <Text style={styles.strategyName}>{strategy.name}</Text>
                        <Text style={styles.strategySub}>{strategy.timeframe} · {strategy.universe}</Text>
                      </View>
                      <Tag
                        label={strategy.is_active ? 'ACTIVE' : 'PAUSED'}
                        color={strategy.is_active ? Colors.green : Colors.textSecondary}
                        bg={strategy.is_active ? Colors.greenBg : Colors.bgGlassStrong}
                      />
                    </View>
                    <View style={styles.strategyBottom}>
                      <Tag label={strategy.direction || 'BUY'} color={Colors.accent} bg={Colors.accentGlow} />
                      <View style={styles.strategyBottomRight}>
                        {strategy.auto_scan_enabled ? <Tag label="AUTO" color={Colors.amber} bg={Colors.amberBg} /> : null}
                        <Text style={styles.signalCount}>{strategy.last_signal_count || 0} signals</Text>
                      </View>
                    </View>
                  </GlassCard>
                </TouchableOpacity>
              );
            })
          )}

          {selected && (
            <GlassCard style={styles.detailCard}>
              <Text style={styles.detailTitle}>Selected Strategy</Text>
              <Text style={styles.detailName}>{selected.name}</Text>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Timeframe</Text>
                <Text style={styles.detailValue}>{selected.timeframe}</Text>
              </View>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Universe</Text>
                <Text style={styles.detailValue}>{selected.universe}</Text>
              </View>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Direction</Text>
                <Text style={styles.detailValue}>{selected.direction}</Text>
              </View>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Last Signal Count</Text>
                <Text style={styles.detailValue}>{selected.last_signal_count || 0}</Text>
              </View>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Exit Config</Text>
                <Text style={styles.detailValue}>SL {selected.exit_config?.sl_pct ?? 5}% · TP {selected.exit_config?.tp_pct ?? 10}% · TSL {selected.exit_config?.tsl_pct ?? 0}%</Text>
              </View>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Auto Execute</Text>
                <Tag
                  label={selected.auto_scan_enabled ? 'ENABLED' : 'DISABLED'}
                  color={selected.auto_scan_enabled ? Colors.green : Colors.textSecondary}
                  bg={selected.auto_scan_enabled ? Colors.greenBg : Colors.bgGlassStrong}
                />
              </View>
              <View style={styles.detailRowTop}>
                <View style={styles.autoAmountWrap}>
                  <Text style={styles.detailLabel}>Auto Amount (₹)</Text>
                  <TextInput
                    style={styles.input}
                    value={autoAmountInput}
                    onChangeText={setAutoAmountInput}
                    keyboardType="numeric"
                    placeholder="10000"
                    placeholderTextColor={Colors.textFaint}
                  />
                </View>
                <View style={styles.autoAmountAction}>
                  <PrimaryButton
                    title="Save"
                    onPress={handleSaveAutoAmount}
                    loading={savingAutoAmount}
                    disabled={usingFallbackData}
                    small
                    variant="success"
                  />
                </View>
              </View>

                {usingFallbackData ? (
                  <Text style={styles.warningText}>Demo strategies loaded. Connect backend to run real scan/backtest.</Text>
                ) : null}

              <PrimaryButton
                title={selected.auto_scan_enabled ? 'Disable Auto Execute' : 'Enable Auto Execute'}
                onPress={handleToggleAutoExecute}
                loading={togglingAutoExecute}
                disabled={usingFallbackData}
                variant={selected.auto_scan_enabled ? 'ghost' : 'success'}
                style={{ marginTop: 6 }}
              />

              <PrimaryButton
                title={scanning ? 'Scanning...' : 'Run Scan'}
                onPress={scanSelected}
                loading={scanning}
                  disabled={usingFallbackData}
                style={{ marginTop: 6 }}
              />
              <PrimaryButton
                  title="Open Backtest Form"
                  onPress={openBacktestForm}
                  disabled={usingFallbackData}
                variant="ghost"
                style={{ marginTop: 8 }}
              />
              <PrimaryButton
                title={deletingStrategyId === selected.id ? 'Deleting...' : 'Delete Strategy'}
                onPress={handleDeleteStrategy}
                loading={deletingStrategyId === selected.id}
                disabled={usingFallbackData || deletingStrategyId === selected.id}
                variant="danger"
                style={{ marginTop: 8 }}
              />

              {scanStatus ? (
                <Text style={styles.scanStatus}>{scanStatus}</Text>
              ) : null}
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
  safeArea: { flex: 1 },
  header: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.lg },
  headerTitle: { fontSize: 28, fontWeight: '700', color: Colors.textPrimary, letterSpacing: -0.5 },
  headerSub: { fontSize: 13, color: Colors.textMuted, marginTop: 2 },
  scroll: { padding: Spacing.lg, flexGrow: 1 },
  metricGrid: { flexDirection: 'row', marginBottom: Spacing.lg },
  metricCard: { flex: 1, marginRight: 8 },
  metricLabel: { fontSize: 11, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.8 },
  metricValue: { fontSize: 22, fontWeight: '700', color: Colors.textPrimary, marginTop: 6 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: Colors.textPrimary, marginBottom: 10 },
  strategyCard: { marginBottom: 10 },
  strategyCardActive: { borderColor: Colors.accent },
  strategyTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  strategyMeta: { flex: 1, paddingRight: 12 },
  strategyName: { fontSize: 16, fontWeight: '700', color: Colors.textPrimary },
  strategySub: { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  strategyBottom: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 },
  strategyBottomRight: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  signalCount: { fontSize: 12, color: Colors.textSecondary, fontWeight: '600' },
  detailCard: { marginTop: 10 },
  detailTitle: { fontSize: 14, fontWeight: '600', color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.8 },
  detailName: { fontSize: 20, fontWeight: '700', color: Colors.textPrimary, marginTop: 8, marginBottom: 14 },
  detailRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10 },
  detailRowTop: { flexDirection: 'row', alignItems: 'flex-end', marginBottom: 8 },
  detailLabel: { fontSize: 12, color: Colors.textMuted },
  detailValue: { fontSize: 13, color: Colors.textPrimary, fontWeight: '600', flex: 1, textAlign: 'right', marginLeft: 12 },
  autoAmountWrap: { flex: 1, marginRight: 10 },
  autoAmountAction: { width: 88 },
  input: {
    marginTop: 6,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass,
    color: Colors.textPrimary,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13,
  },
  warningText: { marginTop: 2, marginBottom: 6, fontSize: 11, color: Colors.amber },
  scanStatus: { marginTop: 10, fontSize: 12, color: Colors.textSecondary },
});