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
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [autoAmountInput, setAutoAmountInput] = useState('10000');
  const [savingAutoAmount, setSavingAutoAmount] = useState(false);
  const [togglingAutoExecute, setTogglingAutoExecute] = useState(false);
  const [deletingStrategyId, setDeletingStrategyId] = useState<number | null>(null);
  const [signalHistory, setSignalHistory] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [scanProgress, setScanProgress] = useState<{ current: number; total: number } | null>(null);
  const [backtestStats, setBacktestStats] = useState<Record<number, any>>({});
  const [tradeSignal, setTradeSignal] = useState<any | null>(null);
  const [tradingSignalId, setTradingSignalId] = useState<number | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
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
    } catch (error: any) {
      const errMsg = error?.response?.data?.detail || error?.message || 'Failed to load strategies';
      setLoadError(errMsg);
      setUsingFallbackData(true);
      setStrategies(FALLBACK_STRATEGIES);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  const selected = useMemo(() => {
    return strategies.find((strategy) => strategy.id === selectedId) || strategies[0] || null;
  }, [selectedId, strategies]);

  const handleExplain = useCallback(async () => {
    if (!selected?.id || usingFallbackData) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setExplaining(true);
    setExplanation(null);
    try {
      const res = await scannerAPI.explainStrategy(selected.id);
      setExplanation(res.data.explanation || null);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'LLM not configured';
      setExplanation(`⚠️ ${msg}`);
    } finally {
      setExplaining(false);
    }
  }, [selected?.id, usingFallbackData]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (selected?.auto_amount != null) {
      setAutoAmountInput(String(Math.round(Number(selected.auto_amount || 10000))));
    }
  }, [selected?.id, selected?.auto_amount]);

  // Fetch signal history when strategy changes
  useEffect(() => {
    if (!selected?.id || usingFallbackData) {
      setSignalHistory([]);
      setBacktestStats({});
      return;
    }
    setLoadingHistory(true);
    
    // Fetch signal history
    scannerAPI
      .getHistory({ strategy_id: selected.id, limit: 10, days: 7 }, 30000)
      .then((res) => {
        const data = Array.isArray(res.data?.history)
          ? res.data.history
          : Array.isArray(res.data?.signals)
            ? res.data.signals
            : Array.isArray(res.data)
              ? res.data
              : [];
        setSignalHistory(data);
      })
      .catch((error) => {
        console.warn('Failed to load signal history:', error?.message);
        setSignalHistory([]);
      })
      .finally(() => setLoadingHistory(false));
      
    // Read backtest stats already embedded in the strategy response by _strategy_with_backtest().
    // Never call backtestAPI (generic /backtest/run) here — its StrategyConfig table is unrelated.
    const cached = selected.last_backtest_result;
    if (cached) {
      const summary = cached.summary || cached;
      setBacktestStats(prev => ({
        ...prev,
        [selected.id]: {
          total_return_pct: summary.total_return_pct,
          sharpe_ratio: summary.sharpe_ratio,
          total_trades: summary.total_trades,
          win_rate_pct: summary.win_rate ?? summary.win_rate_pct,
        },
      }));
    }
  }, [selected?.id, usingFallbackData]);

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
    setScanProgress({ current: 0, total: 100 });
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
      
      // Show completion with count
      setScanStatus(`✅ Scan complete: ${count} signal${count === 1 ? '' : 's'} found`);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);

      // Render fresh scan hits immediately; don't wait for history round-trip.
      const latestHistory = Array.isArray(res.data?.signal_history)
        ? res.data.signal_history
        : [];
      if (latestHistory.length > 0) {
        setSignalHistory(latestHistory);
      }
      
      // Show alert for significant findings
      if (count > 0) {
        Alert.alert(
          '🎯 Signals Found!',
          `${count} new signal${count === 1 ? '' : 's'} detected in ${selected.name}`,
          [
            { text: 'Dismiss', style: 'default' },
            { text: 'View Signals', style: 'default', onPress: () => {} }, // Already visible in timeline
          ]
        );
      }
      
      // Reload signal history
      await scannerAPI
        .getHistory({ strategy_id: selected.id, limit: 10, days: 7 }, 30000)
        .then((histRes) => {
          const data = Array.isArray(histRes.data?.history)
            ? histRes.data.history
            : Array.isArray(histRes.data?.signals)
              ? histRes.data.signals
              : Array.isArray(histRes.data)
                ? histRes.data
                : [];
          setSignalHistory(data);
        })
        .catch((histErr) => {
          console.warn('Failed to reload signal history after scan:', histErr?.message);
        });
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.response?.data?.error || 'Scan failed. Please try again.';
      setScanStatus(`❌ ${String(detail)}`);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    } finally {
      setScanProgress(null);
      setScanning(false);
    }
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
      setScanStatus(res.data?.message || (nextEnabled ? 'Auto scan and execution enabled' : 'Auto scan and execution disabled'));
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
          {/* Error Banner */}
          {loadError && (
            <GlassCard style={[styles.errorBanner]}>
              <Text style={styles.errorText}>⚠️ {loadError}</Text>
              <Text style={styles.errorSubtext}>Showing demo strategies. Tap refresh to retry.</Text>
            </GlassCard>
          )}

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
                    setExplanation(null);
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
                    
                    {/* Backtest Quick Stats */}
                    {backtestStats[strategy.id] && (
                      <View style={styles.backtestStatsRow}>
                        <Text style={styles.backtestStatsText}>
                          📊 {backtestStats[strategy.id].total_return_pct?.toFixed(1)}% | Sharpe {backtestStats[strategy.id].sharpe_ratio?.toFixed(1)} | {backtestStats[strategy.id].total_trades || 0} trades | Win {backtestStats[strategy.id].win_rate_pct?.toFixed(0)}%
                        </Text>
                      </View>
                    )}
                    
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
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
                <Text style={styles.detailTitle}>Selected Strategy</Text>
                {!usingFallbackData && (
                  <TouchableOpacity
                    onPress={handleExplain}
                    disabled={explaining}
                    style={{
                      flexDirection: 'row', alignItems: 'center', gap: 4,
                      paddingHorizontal: 10, paddingVertical: 5,
                      borderRadius: 8,
                      backgroundColor: 'rgba(139,92,246,0.15)',
                      borderWidth: 1, borderColor: 'rgba(139,92,246,0.35)',
                    }}
                  >
                    <Text style={{ fontSize: 12 }}>{explaining ? '⏳' : '✨'}</Text>
                    <Text style={{ color: '#a78bfa', fontSize: 12, fontWeight: '600' }}>
                      {explaining ? 'Thinking…' : 'Explain'}
                    </Text>
                  </TouchableOpacity>
                )}
              </View>
              <Text style={styles.detailName}>{selected.name}</Text>
              {explanation ? (
                <View style={{
                  marginBottom: 10, padding: 10,
                  borderRadius: 8,
                  backgroundColor: 'rgba(139,92,246,0.1)',
                  borderWidth: 1, borderColor: 'rgba(139,92,246,0.3)',
                }}>
                  <Text style={{ color: '#c4b5fd', fontSize: 12, lineHeight: 18 }}>{explanation}</Text>
                </View>
              ) : null}
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
                <Text style={styles.detailLabel}>Auto Scan & Execute</Text>
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

              <Text style={styles.helperText}>
                When enabled, the backend scheduler scans during market hours and places trades automatically. Run Scan only finds signals for review.
              </Text>

                {usingFallbackData ? (
                  <Text style={styles.warningText}>Demo strategies loaded. Connect backend to run real scan/backtest.</Text>
                ) : null}

              <PrimaryButton
                title={selected.auto_scan_enabled ? 'Disable Auto Scan & Execute' : 'Enable Auto Scan & Execute'}
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
              
              {/* Scan Progress Indicator */}
              {scanning && scanProgress && (
                <View style={styles.progressContainer}>
                  <View style={styles.progressRing}>
                    <Text style={styles.progressText}>
                      {scanProgress.current}/{scanProgress.total}
                    </Text>
                  </View>
                  <Text style={styles.progressLabel}>Scanning symbols...</Text>
                </View>
              )}
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

              {/* Signal History Timeline */}
              {!usingFallbackData && (
                <View style={{ marginTop: 14, paddingTop: 12, borderTopWidth: 1, borderTopColor: Colors.border }}>
                  <Text style={[styles.detailTitle, { marginBottom: 8 }]}>Recent Signals</Text>
                  {loadingHistory ? (
                    <Text style={styles.scanStatus}>Loading signal history...</Text>
                  ) : signalHistory.length === 0 ? (
                    <Text style={styles.scanStatus}>No signals yet</Text>
                  ) : (
                    <View style={{ gap: 8 }}>
                      {signalHistory.slice(0, 10).map((signal, idx) => (
                        <View key={idx}>
                          <TouchableOpacity
                            activeOpacity={0.8}
                            onPress={() => {
                              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                            }}
                            style={[styles.signalRow, signal.outcome === 'won' && styles.signalRowWon, signal.outcome === 'lost' && styles.signalRowLost]}
                          >
                            <View style={styles.signalLeft}>
                              <View style={styles.signalIcon}>
                                {signal.outcome === 'won' ? (
                                  <Text style={styles.signalIconText}>🟢</Text>
                                ) : signal.outcome === 'lost' ? (
                                  <Text style={styles.signalIconText}>🔴</Text>
                                ) : (
                                  <Text style={styles.signalIconText}>⏱️</Text>
                                )}
                              </View>
                              <View style={styles.signalDetail}>
                                <Text style={styles.signalSymbol}>{signal.symbol}</Text>
                                <Text style={styles.signalMeta}>
                                  Entry: ₹{Number(signal.entry_price || 0).toFixed(2)} · {signal.timestamp ? new Date(signal.timestamp).toLocaleDateString() : 'N/A'}
                                </Text>
                              </View>
                            </View>
                            {signal.pnl != null && (
                              <Text style={[styles.signalPnl, Number(signal.pnl || 0) >= 0 ? { color: Colors.green } : { color: Colors.red }]}>
                                {Number(signal.pnl || 0) >= 0 ? '+' : ''}{Number(signal.pnl || 0).toFixed(0)}
                              </Text>
                            )}
                          </TouchableOpacity>
                          
                          {/* One-Tap Trade Button - Show for open/fresh signals */}
                          {!signal.outcome && (
                            <TouchableOpacity
                              activeOpacity={0.8}
                              onPress={() => {
                                setTradeSignal(signal);
                                setTradingSignalId(idx);
                                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                              }}
                              style={styles.tradeSignalBtn}
                            >
                              <Text style={styles.tradeSignalBtnText}>⚡ Trade Now</Text>
                            </TouchableOpacity>
                          )}
                        </View>
                      ))}
                    </View>
                  )}
                </View>
              )}

              {/* Trade Signal Modal */}
              {tradeSignal && (
                <View style={{ marginTop: 14, paddingTop: 12, borderTopWidth: 1, borderTopColor: Colors.border }}>
                  <View style={styles.tradeModalHeader}>
                    <Text style={styles.tradeModalTitle}>Execute Trade</Text>
                    <TouchableOpacity
                      onPress={() => {
                        setTradeSignal(null);
                        setTradingSignalId(null);
                      }}
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                    >
                      <Text style={styles.tradeModalClose}>✕</Text>
                    </TouchableOpacity>
                  </View>

                  <View style={styles.tradeModalBody}>
                    <View style={styles.tradeRow}>
                      <Text style={styles.tradeLabel}>Symbol</Text>
                      <Text style={styles.tradeValue}>{tradeSignal.symbol}</Text>
                    </View>
                    <View style={styles.tradeRow}>
                      <Text style={styles.tradeLabel}>Entry Price (Signal)</Text>
                      <Text style={styles.tradeValue}>₹{Number(tradeSignal.entry_price || 0).toFixed(2)}</Text>
                    </View>
                    <View style={styles.tradeRow}>
                      <Text style={styles.tradeLabel}>Direction</Text>
                      <Text style={[styles.tradeValue, { color: selected?.direction === 'SELL' ? Colors.red : Colors.green }]}>
                        {selected?.direction || 'BUY'}
                      </Text>
                    </View>
                    <View style={styles.tradeRow}>
                      <Text style={styles.tradeLabel}>SL / TP</Text>
                      <Text style={styles.tradeValue}>
                        {selected?.exit_config?.sl_pct || 5}% / {selected?.exit_config?.tp_pct || 10}%
                      </Text>
                    </View>

                    <View style={styles.tradeButtonGroup}>
                      <TouchableOpacity
                        style={[styles.tradeExecBtn, styles.tradeCancelBtn]}
                        onPress={() => {
                          setTradeSignal(null);
                          setTradingSignalId(null);
                          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                        }}
                      >
                        <Text style={[styles.tradeExecBtnText, { color: Colors.textSecondary }]}>Cancel</Text>
                      </TouchableOpacity>

                      <TouchableOpacity
                        style={[styles.tradeExecBtn, styles.tradeConfirmBtn]}
                        onPress={async () => {
                          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                          try {
                            await scannerAPI.executeSignal({
                              signal_id: tradeSignal.id,
                              strategy_id: selected?.id,
                              symbol: tradeSignal.symbol,
                              entry_price: Number(tradeSignal.entry_price),
                              signal_type: selected?.direction,
                              sl_pct: selected?.exit_config?.sl_pct ?? 5,
                              tp_pct: selected?.exit_config?.tp_pct ?? 10,
                            });
                            Alert.alert('✅ Trade Executed', `${selected?.direction || 'BUY'} order submitted for ${tradeSignal.symbol} @ ₹${Number(tradeSignal.entry_price).toFixed(2)}`, [
                              { text: 'OK', onPress: () => {
                                setTradeSignal(null);
                                setTradingSignalId(null);
                              }},
                            ]);
                            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
                          } catch (err: any) {
                            Alert.alert('❌ Trade Failed', err?.response?.data?.detail || 'Could not execute trade');
                            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
                          }
                        }}
                      >
                        <Text style={[styles.tradeExecBtnText, { color: '#fff' }]}>Execute ({selected?.direction || 'BUY'})</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
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
  helperText: { marginTop: 2, marginBottom: 8, fontSize: 11, color: Colors.textSecondary, lineHeight: 16 },
  warningText: { marginTop: 2, marginBottom: 6, fontSize: 11, color: Colors.amber },
  scanStatus: { marginTop: 10, fontSize: 12, color: Colors.textSecondary },
  signalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlassStrong,
    paddingHorizontal: 10,
    paddingVertical: 10,
  },
  signalRowWon: { borderColor: Colors.green, backgroundColor: 'rgba(16,185,129,0.08)' },
  signalRowLost: { borderColor: Colors.red, backgroundColor: 'rgba(239,68,68,0.08)' },
  signalLeft: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  signalIcon: { marginRight: 10 },
  signalIconText: { fontSize: 16 },
  signalDetail: { flex: 1 },
  signalSymbol: { fontSize: 13, fontWeight: '700', color: Colors.textPrimary },
  signalMeta: { fontSize: 11, color: Colors.textMuted, marginTop: 2 },
  signalPnl: { fontSize: 12, fontWeight: '700', minWidth: 50, textAlign: 'right' },
  progressContainer: { marginTop: 12, alignItems: 'center' },
  progressRing: {
    width: 60,
    height: 60,
    borderRadius: 30,
    borderWidth: 4,
    borderColor: Colors.accent,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.accentSoft,
  },
  progressText: { fontSize: 14, fontWeight: '700', color: Colors.accent },
  progressLabel: { fontSize: 11, color: Colors.textMuted, marginTop: 8, textTransform: 'uppercase', letterSpacing: 0.6 },
  errorBanner: { marginBottom: 12, borderWidth: 1, borderColor: Colors.red, backgroundColor: 'rgba(239,68,68,0.08)' },
  errorText: { fontSize: 13, fontWeight: '600', color: Colors.red },
  errorSubtext: { fontSize: 11, color: Colors.textMuted, marginTop: 4 },
  backtestStatsRow: { marginTop: 8, paddingTop: 8, borderTopWidth: 1, borderTopColor: Colors.border },
  backtestStatsText: { fontSize: 10, color: Colors.textMuted, fontWeight: '500' },
  tradeSignalBtn: { marginTop: 6, marginBottom: 8, backgroundColor: Colors.accentSoft, borderWidth: 1, borderColor: Colors.accent, borderRadius: Radius.md, paddingVertical: 8, alignItems: 'center' },
  tradeSignalBtnText: { fontSize: 12, fontWeight: '700', color: Colors.accent },
  tradeModalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  tradeModalTitle: { fontSize: 14, fontWeight: '700', color: Colors.textPrimary, textTransform: 'uppercase', letterSpacing: 0.8 },
  tradeModalClose: { fontSize: 18, color: Colors.textMuted },
  tradeModalBody: { gap: 10 },
  tradeRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: Colors.border },
  tradeLabel: { fontSize: 12, color: Colors.textMuted },
  tradeValue: { fontSize: 13, fontWeight: '700', color: Colors.textPrimary, textAlign: 'right' },
  tradeButtonGroup: { flexDirection: 'row', gap: 8, marginTop: 12 },
  tradeExecBtn: { flex: 1, paddingVertical: 10, borderRadius: Radius.md, alignItems: 'center' },
  tradeCancelBtn: { backgroundColor: Colors.bgGlass, borderWidth: 1, borderColor: Colors.border },
  tradeConfirmBtn: { backgroundColor: Colors.green },
  tradeExecBtnText: { fontSize: 12, fontWeight: '700' },
});