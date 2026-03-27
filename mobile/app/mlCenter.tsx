import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { mlAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, PrimaryButton, ProgressBar, ScreenHeader, Tag } from '../components/ui';

export default function MLCenterScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [training, setTraining] = useState(false);
  const [backfilling, setBackfilling] = useState(false);

  const [metrics, setMetrics] = useState<any | null>(null);
  const [dataSummary, setDataSummary] = useState<any | null>(null);
  const [backfillStatus, setBackfillStatus] = useState<any | null>(null);

  const [predictSymbol, setPredictSymbol] = useState('NIFTY');
  const [prediction, setPrediction] = useState<any | null>(null);
  const [predicting, setPredicting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const [metricsRes, dataSummaryRes, backfillRes] = await Promise.allSettled([
        mlAPI.getMetrics(),
        mlAPI.getDataSummary(),
        mlAPI.getBackfillStatus(),
      ]);
      if (metricsRes.status === 'fulfilled') setMetrics(metricsRes.value.data || null);
      if (dataSummaryRes.status === 'fulfilled') setDataSummary(dataSummaryRes.value.data || null);
      if (backfillRes.status === 'fulfilled') setBackfillStatus(backfillRes.value.data || null);
    } catch {
      setMetrics(null);
      setDataSummary(null);
      setBackfillStatus(null);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (backfillStatus?.running) {
      pollRef.current = setInterval(load, 2000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [backfillStatus?.running, load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  const runTraining = async () => {
    setTraining(true);
    try {
      await mlAPI.train();
      await load();
    } catch {
      // no-op
    }
    setTraining(false);
  };

  const runBackfill = async () => {
    setBackfilling(true);
    try {
      await mlAPI.backfill();
      await load();
    } catch {
      // no-op
    }
    setBackfilling(false);
  };

  const runPrediction = async () => {
    const symbol = predictSymbol.trim().toUpperCase();
    if (!symbol) return;
    setPredicting(true);
    try {
      const response = await mlAPI.predict(symbol);
      setPrediction(response.data || null);
    } catch {
      setPrediction(null);
    }
    setPredicting(false);
  };

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  const accuracy = Number(metrics?.accuracy || 0) * 100;
  const backfillProgress = backfillStatus?.total ? (Number(backfillStatus.progress || 0) / Number(backfillStatus.total || 1)) * 100 : 0;

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScreenHeader
          title="ML Center"
          subtitle="Train, backfill, and monitor model health"
          badge={<Tag label={String(metrics?.model_status || 'unknown').toUpperCase()} color={Colors.accentLight} bg={Colors.accentSoft} />}
          onBack={() => router.back()}
        />

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.statsRow}>
            <GlassCard style={styles.statCard}><Text style={styles.statLabel}>Accuracy</Text><Text style={styles.statValue}>{accuracy.toFixed(1)}%</Text></GlassCard>
            <GlassCard style={styles.statCard}><Text style={styles.statLabel}>Samples</Text><Text style={styles.statValue}>{Number(metrics?.total_samples || 0).toLocaleString('en-IN')}</Text></GlassCard>
          </View>

          <GlassCard style={styles.card}>
            <Text style={styles.title}>Model Actions</Text>
            <View style={styles.buttonRow}>
              <PrimaryButton title="Train Model" onPress={runTraining} loading={training} style={{ flex: 1, marginRight: 8 }} />
              <PrimaryButton title="Backfill Data" onPress={runBackfill} loading={backfilling} variant="ghost" style={{ flex: 1 }} />
            </View>
            {backfillStatus?.running && (
              <View style={{ marginTop: 12 }}>
                <Text style={styles.meta}>Backfill: {Number(backfillStatus.progress || 0)} / {Number(backfillStatus.total || 0)}</Text>
                <ProgressBar value={backfillProgress} />
                <Text style={[styles.meta, { marginTop: 6 }]}>{backfillStatus.message || 'Running...'}</Text>
              </View>
            )}
          </GlassCard>

          <GlassCard style={styles.card}>
            <Text style={styles.title}>Data Summary</Text>
            {dataSummary ? (
              <>
                <Row label="Total Symbols" value={Number(dataSummary.total_symbols || 0).toString()} />
                <Row label="Total Candles" value={Number(dataSummary.total_candles || 0).toLocaleString('en-IN')} />
                <Row label="500+ Days Symbols" value={Number(dataSummary.symbols_with_500plus_days || 0).toString()} />
              </>
            ) : (
              <EmptyState icon="📊" title="No Data Summary" subtitle="ML data summary is unavailable." />
            )}
          </GlassCard>

          <GlassCard style={styles.card}>
            <Text style={styles.title}>Quick Prediction</Text>
            <TextInput
              style={styles.input}
              value={predictSymbol}
              onChangeText={setPredictSymbol}
              placeholder="Enter symbol (e.g. RELIANCE)"
              placeholderTextColor={Colors.textFaint}
              autoCapitalize="characters"
            />
            <PrimaryButton title="Predict" onPress={runPrediction} loading={predicting} />
            {prediction && (
              <View style={styles.predictionBox}>
                <Text style={styles.predictionSymbol}>{prediction.symbol || '-'}</Text>
                <Text style={styles.predictionMeta}>Signal: {prediction.signal || '-'}</Text>
                <Text style={styles.predictionMeta}>Confidence: {Number(prediction.confidence || 0).toFixed(2)}</Text>
                <Text style={styles.predictionMeta}>Bias: {prediction.bias || '-'}</Text>
              </View>
            )}
          </GlassCard>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.meta}>{label}</Text>
      <Text style={styles.value}>{value}</Text>
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
  card: { marginBottom: Spacing.md },
  title: { color: Colors.textPrimary, fontSize: 16, fontWeight: '700', marginBottom: 10 },
  buttonRow: { flexDirection: 'row' },
  row: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  meta: { color: Colors.textSecondary, fontSize: 13 },
  value: { color: Colors.textPrimary, fontSize: 13, fontWeight: '600' },
  input: {
    backgroundColor: Colors.bgGlassStrong,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    color: Colors.textPrimary,
    paddingHorizontal: 10,
    paddingVertical: 10,
    marginBottom: 10,
  },
  predictionBox: {
    marginTop: 10,
    padding: 10,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.bgGlass,
  },
  predictionSymbol: { color: Colors.textPrimary, fontWeight: '700', fontSize: 15, marginBottom: 4 },
  predictionMeta: { color: Colors.textSecondary, fontSize: 12, marginTop: 2 },
});
