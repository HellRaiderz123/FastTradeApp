import React, { useCallback, useEffect, useState } from 'react';
import {
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { reconcileAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, PrimaryButton, ScreenHeader, Tag } from '../components/ui';

export default function BrokerReconciliationScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [status, setStatus] = useState<any | null>(null);
  const [syncResult, setSyncResult] = useState<any | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await reconcileAPI.getStatus();
      setStatus(response.data || null);
    } catch {
      setStatus(null);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  const runSync = async () => {
    setSyncing(true);
    try {
      const response = await reconcileAPI.run();
      setSyncResult(response.data || null);
      await load();
    } catch {
      setSyncResult(null);
    }
    setSyncing(false);
  };

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  const openIntents = status?.open_intents || [];
  const closedLog = status?.broker_closed_log || [];

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScreenHeader
          title="Reconciliation"
          subtitle="Sync broker-closed positions back into FastTrade"
          badge={<Tag label={`${status?.open_count ?? 0} OPEN`} color={Colors.amber} bg={Colors.amberBg} />}
          onBack={() => router.back()}
        />

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          <GlassCard style={styles.card}>
            <Text style={styles.title}>One-Click Sync</Text>
            <Text style={styles.subtitle}>Compares open local intents with broker state and closes stale entries.</Text>
            <PrimaryButton title="Run Sync" onPress={runSync} loading={syncing} style={{ marginTop: 12 }} />
            {syncResult && (
              <View style={styles.banner}>
                <Text style={styles.bannerText}>
                  Synced {Number(syncResult.closed_count || 0)} positions
                </Text>
              </View>
            )}
          </GlassCard>

          <View style={styles.summaryRow}>
            <GlassCard style={styles.summaryCard}><Text style={styles.summaryLabel}>Open Intents</Text><Text style={styles.summaryValue}>{status?.open_count ?? 0}</Text></GlassCard>
            <GlassCard style={styles.summaryCard}><Text style={styles.summaryLabel}>Broker Closed</Text><Text style={[styles.summaryValue, { color: Colors.green }]}>{status?.broker_closed_count ?? 0}</Text></GlassCard>
          </View>

          <GlassCard style={styles.card}>
            <Text style={styles.title}>Open in FastTrade</Text>
            {openIntents.length === 0 ? (
              <EmptyState icon="✅" title="No Open Discrepancies" subtitle="Open intent list is currently empty." />
            ) : (
              openIntents.slice(0, 25).map((row: any) => (
                <View key={row.intent_id} style={styles.row}>
                  <View>
                    <Text style={styles.symbol}>{row.underlying || '-'}</Text>
                    <Text style={styles.meta}>{row.strategy || '-'} • {row.mode || 'PAPER'}</Text>
                  </View>
                  <Text style={[styles.pnl, { color: Number(row.pnl || 0) >= 0 ? Colors.green : Colors.red }]}>₹{Number(row.pnl || 0).toFixed(2)}</Text>
                </View>
              ))
            )}
          </GlassCard>

          <GlassCard style={styles.card}>
            <Text style={styles.title}>Reconciliation Log</Text>
            {closedLog.length === 0 ? (
              <EmptyState icon="🧾" title="No Reconciled Records" subtitle="No broker-closed intents recorded yet." />
            ) : (
              closedLog.slice(0, 25).map((row: any) => (
                <View key={row.intent_id} style={styles.row}>
                  <View>
                    <Text style={styles.symbol}>{row.underlying || '-'}</Text>
                    <Text style={styles.meta}>{row.exit_reason || 'BROKER_CLOSED'}</Text>
                  </View>
                  <Text style={[styles.pnl, { color: Number(row.pnl || 0) >= 0 ? Colors.green : Colors.red }]}>₹{Number(row.pnl || 0).toFixed(2)}</Text>
                </View>
              ))
            )}
          </GlassCard>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safe: { flex: 1 },
  scroll: { padding: Spacing.lg, paddingBottom: 120 },
  card: { marginBottom: Spacing.md },
  title: { color: Colors.textPrimary, fontSize: 16, fontWeight: '700' },
  subtitle: { color: Colors.textSecondary, fontSize: 12, marginTop: 4 },
  banner: { marginTop: 12, borderRadius: Radius.md, backgroundColor: Colors.greenBg, borderWidth: 1, borderColor: Colors.greenGlow, padding: 10 },
  bannerText: { color: Colors.greenLight, fontSize: 13, fontWeight: '600' },
  summaryRow: { flexDirection: 'row', gap: 8, marginBottom: Spacing.md },
  summaryCard: { flex: 1 },
  summaryLabel: { color: Colors.textMuted, fontSize: 11, textTransform: 'uppercase' },
  summaryValue: { color: Colors.textPrimary, fontSize: 24, fontWeight: '700', marginTop: 4 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: Colors.border },
  symbol: { color: Colors.textPrimary, fontSize: 14, fontWeight: '700' },
  meta: { color: Colors.textSecondary, fontSize: 12, marginTop: 2 },
  pnl: { fontSize: 13, fontWeight: '700' },
});
