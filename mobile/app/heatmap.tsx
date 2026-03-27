import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { marketDashboardAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, ScreenHeader, Tag } from '../components/ui';

type HeatmapStock = {
  symbol: string;
  ltp: number;
  change_percent: number;
  volume: number;
  market_cap_rank: number;
};

export default function HeatmapScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stocks, setStocks] = useState<HeatmapStock[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await marketDashboardAPI.getHeatmap();
      setStocks(response.data?.stocks || []);
    } catch {
      setStocks([]);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    load();
    pollRef.current = setInterval(load, 30000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  const stats = useMemo(() => {
    const gainers = stocks.filter((s) => s.change_percent > 0).length;
    const losers = stocks.filter((s) => s.change_percent < 0).length;
    const avg = stocks.length ? stocks.reduce((sum, s) => sum + s.change_percent, 0) / stocks.length : 0;
    return { gainers, losers, avg };
  }, [stocks]);

  const getCellStyle = (changePercent: number) => {
    if (changePercent >= 2) return { bg: Colors.green, fg: '#ffffff' };
    if (changePercent >= 0.5) return { bg: 'rgba(16,185,129,0.7)', fg: '#ffffff' };
    if (changePercent > 0) return { bg: Colors.greenBg, fg: Colors.greenLight };
    if (changePercent === 0) return { bg: Colors.bgGlassStrong, fg: Colors.textSecondary };
    if (changePercent > -0.5) return { bg: Colors.redBg, fg: Colors.redLight };
    if (changePercent > -2) return { bg: 'rgba(239,68,68,0.7)', fg: '#ffffff' };
    return { bg: Colors.red, fg: '#ffffff' };
  };

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScreenHeader
          title="Market Heatmap"
          subtitle="NIFTY performance snapshot refreshed every 30s"
          badge={<Tag label={`${stocks.length} STOCKS`} color={Colors.accent} bg={Colors.accentSoft} />}
          onBack={() => router.back()}
        />

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.statsRow}>
            <GlassCard style={styles.statCard}><Text style={styles.statLabel}>Gainers</Text><Text style={[styles.statValue, { color: Colors.green }]}>{stats.gainers}</Text></GlassCard>
            <GlassCard style={styles.statCard}><Text style={styles.statLabel}>Losers</Text><Text style={[styles.statValue, { color: Colors.red }]}>{stats.losers}</Text></GlassCard>
            <GlassCard style={styles.statCard}><Text style={styles.statLabel}>Avg %</Text><Text style={[styles.statValue, { color: stats.avg >= 0 ? Colors.green : Colors.red }]}>{stats.avg.toFixed(2)}%</Text></GlassCard>
          </View>

          {stocks.length === 0 ? (
            <EmptyState icon="🧊" title="No Heatmap Data" subtitle="Unable to fetch market heatmap right now." />
          ) : (
            <View style={styles.grid}>
              {stocks.map((stock) => {
                const tone = getCellStyle(stock.change_percent);
                return (
                  <View key={stock.symbol} style={[styles.tile, { backgroundColor: tone.bg }]}> 
                    <Text style={[styles.tileSymbol, { color: tone.fg }]}>{stock.symbol}</Text>
                    <Text style={[styles.tileChange, { color: tone.fg }]}>{stock.change_percent >= 0 ? '+' : ''}{stock.change_percent.toFixed(2)}%</Text>
                    <Text style={[styles.tileMeta, { color: tone.fg }]}>₹{Number(stock.ltp || 0).toFixed(2)}</Text>
                  </View>
                );
              })}
            </View>
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safe: { flex: 1 },
  scroll: { padding: Spacing.lg, paddingBottom: 120 },
  statsRow: { flexDirection: 'row', gap: 8, marginBottom: Spacing.md },
  statCard: { flex: 1 },
  statLabel: { color: Colors.textMuted, fontSize: 11, textTransform: 'uppercase' },
  statValue: { color: Colors.textPrimary, fontSize: 22, fontWeight: '700', marginTop: 4 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tile: {
    width: '31%',
    minHeight: 84,
    borderRadius: Radius.md,
    padding: 10,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.15)',
    justifyContent: 'space-between',
  },
  tileSymbol: { fontSize: 13, fontWeight: '700' },
  tileChange: { fontSize: 16, fontWeight: '800' },
  tileMeta: { fontSize: 11, opacity: 0.9 },
});
