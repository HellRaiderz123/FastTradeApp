import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StatusBar, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { accountAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, ScreenHeader, Tag } from '../components/ui';

export default function AccountScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [profile, setProfile] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);

  const load = useCallback(async () => {
    try {
      const [profileRes, historyRes] = await Promise.allSettled([
        accountAPI.getProfile(),
        accountAPI.getDailyCapitalHistory(30),
      ]);
      if (profileRes.status === 'fulfilled') setProfile(profileRes.value.data || null);
      if (historyRes.status === 'fulfilled') {
        const h = historyRes.value.data;
        setHistory(Array.isArray(h) ? h.slice().reverse() : []);
      }
    } catch {}
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <View style={styles.root}><LoadingSpinner /></View>;

  const capital = Number(profile?.capital || profile?.live_balance || 0);
  const equity = Number(profile?.equity || profile?.net_worth || 0);
  const cash = Number(profile?.cash || 0);
  const collateral = Number(profile?.collateral || 0);
  const isDemo = profile?.user_id === 'DEMO_USER';

  const totalPnL = history.reduce((s, r) => s + (r.daily_pnl || 0), 0);
  const bestDay = history.reduce((best, r) => (r.daily_pnl || 0) > (best?.daily_pnl || 0) ? r : best, null);
  const worstDay = history.reduce((worst, r) => (r.daily_pnl || 0) < (worst?.daily_pnl || 0) ? r : worst, null);

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScreenHeader
          title="Account & Funds"
          subtitle="Broker capital, margins, and daily history"
          badge={<Tag label={isDemo ? 'DEMO' : 'LIVE'} color={isDemo ? Colors.amber : Colors.green} bg={isDemo ? Colors.amberBg : Colors.greenBg} />}
          onBack={() => router.back()}
        />

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          {/* Capital overview */}
          <View style={styles.statsRow}>
            <GlassCard style={styles.statCard}>
              <Text style={styles.statLabel}>Available</Text>
              <Text style={[styles.statValue, { color: Colors.green }]}>₹{capital.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</Text>
            </GlassCard>
            <GlassCard style={styles.statCard}>
              <Text style={styles.statLabel}>Net Equity</Text>
              <Text style={styles.statValue}>₹{equity.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</Text>
            </GlassCard>
          </View>

          {/* Profile card */}
          {profile && (
            <GlassCard style={styles.card}>
              <Text style={styles.sectionTitle}>Broker Profile</Text>
              <Row label="User ID" value={profile.user_id || '—'} />
              <Row label="Email" value={profile.email || '—'} />
              <Row label="Cash" value={`₹${cash.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`} />
              <Row label="Collateral" value={`₹${collateral.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`} />
              <Row label="Margins Available" value={`₹${capital.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`} />
            </GlassCard>
          )}

          {/* 30-day summary */}
          {history.length > 0 && (
            <GlassCard style={styles.card}>
              <Text style={styles.sectionTitle}>30-Day Summary</Text>
              <View style={styles.summaryRow}>
                <View style={styles.summaryItem}>
                  <Text style={styles.summaryLabel}>Total P&L</Text>
                  <Text style={[styles.summaryValue, { color: totalPnL >= 0 ? Colors.green : Colors.red }]}>
                    {totalPnL >= 0 ? '+' : ''}₹{Math.abs(totalPnL).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </Text>
                </View>
                {bestDay && (
                  <View style={styles.summaryItem}>
                    <Text style={styles.summaryLabel}>Best Day</Text>
                    <Text style={[styles.summaryValue, { color: Colors.green }]}>+₹{Number(bestDay.daily_pnl || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</Text>
                    <Text style={styles.summaryDate}>{bestDay.date}</Text>
                  </View>
                )}
                {worstDay && (
                  <View style={styles.summaryItem}>
                    <Text style={styles.summaryLabel}>Worst Day</Text>
                    <Text style={[styles.summaryValue, { color: Colors.red }]}>₹{Number(worstDay.daily_pnl || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</Text>
                    <Text style={styles.summaryDate}>{worstDay.date}</Text>
                  </View>
                )}
              </View>
            </GlassCard>
          )}

          {/* Daily history */}
          <GlassCard style={styles.card}>
            <Text style={styles.sectionTitle}>Daily Capital History</Text>
            {history.length === 0 ? (
              <EmptyState icon="📈" title="No History" subtitle="Capital history will appear after trading days." />
            ) : (
              <>
                <View style={styles.histHeader}>
                  <Text style={[styles.histCell, { flex: 2 }]}>Date</Text>
                  <Text style={[styles.histCell, { textAlign: 'right' }]}>Closing</Text>
                  <Text style={[styles.histCell, { textAlign: 'right' }]}>P&L</Text>
                  <Text style={[styles.histCell, { textAlign: 'right' }]}>Ret%</Text>
                </View>
                {history.slice(0, 30).map((r: any, i: number) => {
                  const pnl = Number(r.daily_pnl || 0);
                  const ret = Number(r.daily_return_pct || 0);
                  const color = pnl >= 0 ? Colors.green : Colors.red;
                  return (
                    <View key={i} style={styles.histRow}>
                      <Text style={[styles.histVal, { flex: 2, color: Colors.textSecondary }]}>{r.date}</Text>
                      <Text style={[styles.histVal, { textAlign: 'right' }]}>₹{Number(r.closing_capital || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</Text>
                      <Text style={[styles.histVal, { textAlign: 'right', color }]}>{pnl >= 0 ? '+' : ''}₹{Math.abs(pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</Text>
                      <Text style={[styles.histVal, { textAlign: 'right', color }]}>{ret >= 0 ? '+' : ''}{ret.toFixed(2)}%</Text>
                    </View>
                  );
                })}
              </>
            )}
          </GlassCard>

          <View style={{ height: 96 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safe: { flex: 1 },
  scroll: { padding: Spacing.lg },
  statsRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  statCard: { flex: 1, alignItems: 'center', paddingVertical: 14 },
  statLabel: { fontSize: 11, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.5 },
  statValue: { fontSize: 20, fontWeight: '700', color: Colors.textPrimary, marginTop: 4 },
  card: { marginBottom: 12 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: Colors.textPrimary, marginBottom: 10 },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 7, borderBottomWidth: 1, borderBottomColor: Colors.border },
  rowLabel: { fontSize: 13, color: Colors.textSecondary },
  rowValue: { fontSize: 13, fontWeight: '600', color: Colors.textPrimary },
  summaryRow: { flexDirection: 'row', gap: 8 },
  summaryItem: { flex: 1, alignItems: 'center', paddingVertical: 8, backgroundColor: Colors.bgGlass, borderRadius: Radius.sm },
  summaryLabel: { fontSize: 10, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.5 },
  summaryValue: { fontSize: 15, fontWeight: '700', marginTop: 4 },
  summaryDate: { fontSize: 10, color: Colors.textFaint, marginTop: 2 },
  histHeader: { flexDirection: 'row', paddingBottom: 6, borderBottomWidth: 1, borderBottomColor: Colors.border, marginBottom: 2 },
  histCell: { flex: 1, fontSize: 10, color: Colors.textMuted, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.3 },
  histRow: { flexDirection: 'row', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: Colors.border },
  histVal: { flex: 1, fontSize: 12, color: Colors.textPrimary, fontWeight: '500' },
});
