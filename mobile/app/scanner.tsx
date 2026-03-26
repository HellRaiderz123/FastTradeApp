import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshControl, ScrollView, StatusBar, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';
import { scannerAPI } from '../lib/api';
import { Colors, Gradients, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, PrimaryButton, Tag } from '../components/ui';

const FALLBACK_STRATEGIES = [
  { id: 1, name: 'Momentum Breakout Lab', timeframe: 'Day', universe: 'NIFTY50', direction: 'BUY', is_active: true, last_signal_count: 4 },
  { id: 2, name: 'Hourly Mean Reversion', timeframe: '1 Hour', universe: 'NIFTY50', direction: 'BUY', is_active: true, last_signal_count: 2 },
  { id: 3, name: 'Volume Shock Filter', timeframe: '15 Min', universe: 'BANKNIFTY', direction: 'SELL', is_active: false, last_signal_count: 0 },
];

export default function ScannerScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanStatus, setScanStatus] = useState('');
  const [strategies, setStrategies] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await scannerAPI.listStrategies();
      const data = Array.isArray(res.data) ? res.data : res.data?.items || [];
      setStrategies(data.length ? data : FALLBACK_STRATEGIES);
    } catch {
      setStrategies(FALLBACK_STRATEGIES);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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
    setScanning(true);
    setScanStatus('');
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    try {
      const res = await scannerAPI.scanStrategy(selected.id);
      const count = Array.isArray(res.data?.matches)
        ? res.data.matches.length
        : Array.isArray(res.data?.results)
          ? res.data.results.length
          : Number(res.data?.signal_count || 0);
      setScanStatus(`Scan complete: ${count} signal${count === 1 ? '' : 's'} found`);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch {
      setScanStatus('Scan failed. Please try again.');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }
    setScanning(false);
  };

  const selected = useMemo(() => {
    return strategies.find((strategy) => strategy.id === selectedId) || strategies[0] || null;
  }, [selectedId, strategies]);

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safeArea}>
        <LinearGradient colors={Gradients.header} style={styles.header}>
          <Text style={styles.headerTitle}>Scanner</Text>
          <Text style={styles.headerSub}>Condition strategies and signals in a phone-first layout</Text>
        </LinearGradient>

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
                      <Text style={styles.signalCount}>{strategy.last_signal_count || 0} signals</Text>
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

              <PrimaryButton
                title={scanning ? 'Scanning...' : 'Run Scan'}
                onPress={scanSelected}
                loading={scanning}
                style={{ marginTop: 6 }}
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
  signalCount: { fontSize: 12, color: Colors.textSecondary, fontWeight: '600' },
  detailCard: { marginTop: 10 },
  detailTitle: { fontSize: 14, fontWeight: '600', color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.8 },
  detailName: { fontSize: 20, fontWeight: '700', color: Colors.textPrimary, marginTop: 8, marginBottom: 14 },
  detailRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10 },
  detailLabel: { fontSize: 12, color: Colors.textMuted },
  detailValue: { fontSize: 13, color: Colors.textPrimary, fontWeight: '600' },
  scanStatus: { marginTop: 10, fontSize: 12, color: Colors.textSecondary },
});