import React, { useMemo, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, StatusBar, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { backtestAPI } from '../lib/api';
import { Colors, Gradients, Radius, Spacing } from '../lib/theme';
import { GlassCard, PrimaryButton, Tag } from '../components/ui';

const BacktestScreen = () => {
  const [underlying, setUnderlying] = useState('NIFTY');
  const [startDate, setStartDate] = useState('2023-01-01');
  const [endDate, setEndDate] = useState('2023-12-31');
  const [capital, setCapital] = useState('100000');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleRunBacktest = async () => {
    setLoading(true);
    setResult(null);
    try {
      const payload = {
        underlying,
        start_date: startDate,
        end_date: endDate,
        initial_capital: parseInt(capital),
      };
      const response = await backtestAPI.runBacktest(payload);
      setResult(response.data || {});
    } catch {
      setResult({ error: 'Failed to run backtest' });
    } finally {
      setLoading(false);
    }
  };

  const summary = useMemo(() => {
    if (!result || (result as any).error) {
      return [] as Array<{ label: string; value: string; positive?: boolean; negative?: boolean }>;
    }
    const data: any = result;
    return [
      { label: 'Total Return', value: `${Number(data.total_return_pct || 0).toFixed(2)}%`, positive: Number(data.total_return_pct || 0) >= 0, negative: Number(data.total_return_pct || 0) < 0 },
      { label: 'Annual Return', value: `${Number(data.annual_return_pct || 0).toFixed(2)}%`, positive: Number(data.annual_return_pct || 0) >= 0, negative: Number(data.annual_return_pct || 0) < 0 },
      { label: 'Sharpe Ratio', value: `${Number(data.sharpe_ratio || 0).toFixed(2)}` },
      { label: 'Max Drawdown', value: `${Number(data.max_drawdown_pct || 0).toFixed(2)}%`, negative: true },
      { label: 'Win Rate', value: `${Number(data.win_rate_pct || 0).toFixed(2)}%`, positive: Number(data.win_rate_pct || 0) >= 50 },
      { label: 'Total Trades', value: `${data.total_trades || 0}` },
    ];
  }, [result]);

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safeArea}>
        <LinearGradient colors={Gradients.header} style={styles.header}>
          <Text style={styles.title}>Backtest Lab</Text>
          <Text style={styles.subtitle}>Run historical strategy checks with fast mobile inputs</Text>
        </LinearGradient>

        <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          <GlassCard style={styles.formCard}>
            <View style={styles.formHead}>
              <Text style={styles.sectionTitle}>Configuration</Text>
              <Tag label="HISTORICAL" color={Colors.accent} bg={Colors.accentSoft} />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Underlying</Text>
              <TextInput style={styles.input} value={underlying} onChangeText={setUnderlying} autoCapitalize="characters" placeholder="NIFTY" placeholderTextColor={Colors.textFaint} />
            </View>

            <View style={styles.rowInputs}>
              <View style={[styles.inputGroup, styles.halfInput]}>
                <Text style={styles.label}>Start Date</Text>
                <TextInput style={styles.input} value={startDate} onChangeText={setStartDate} placeholder="YYYY-MM-DD" placeholderTextColor={Colors.textFaint} />
              </View>
              <View style={[styles.inputGroup, styles.halfInput]}>
                <Text style={styles.label}>End Date</Text>
                <TextInput style={styles.input} value={endDate} onChangeText={setEndDate} placeholder="YYYY-MM-DD" placeholderTextColor={Colors.textFaint} />
              </View>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Initial Capital</Text>
              <TextInput style={styles.input} value={capital} onChangeText={setCapital} keyboardType="numeric" placeholder="100000" placeholderTextColor={Colors.textFaint} />
            </View>

            <PrimaryButton title="Run Backtest" onPress={handleRunBacktest} loading={loading} variant="success" />
          </GlassCard>

          {result && (
            <GlassCard style={styles.resultCard}>
              {'error' in (result as any) ? (
                <Text style={styles.error}>{(result as any).error}</Text>
              ) : (
                <>
                  <Text style={styles.sectionTitle}>Results</Text>
                  {summary.map((item) => (
                    <View key={item.label} style={styles.metricRow}>
                      <Text style={styles.metricLabel}>{item.label}</Text>
                      <Text style={[
                        styles.metricValue,
                        item.positive && { color: Colors.green },
                        item.negative && { color: Colors.red },
                      ]}>
                        {item.value}
                      </Text>
                    </View>
                  ))}
                </>
              )}
            </GlassCard>
          )}

          <View style={{ height: 96 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
};

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safeArea: { flex: 1 },
  header: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.lg },
  title: { fontSize: 28, fontWeight: '700', color: Colors.textPrimary, letterSpacing: -0.5 },
  subtitle: { marginTop: 4, fontSize: 13, color: Colors.textMuted },
  scrollContent: { padding: Spacing.lg },
  formCard: { marginBottom: Spacing.md },
  formHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: Colors.textPrimary },
  inputGroup: { marginBottom: 12 },
  rowInputs: { flexDirection: 'row', gap: 10 },
  halfInput: { flex: 1 },
  label: { fontSize: 12, fontWeight: '600', color: Colors.textMuted, marginBottom: 6 },
  input: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass,
    color: Colors.textPrimary,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  resultCard: { marginTop: 2 },
  metricRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 10 },
  metricLabel: { fontSize: 13, color: Colors.textSecondary },
  metricValue: { fontSize: 14, fontWeight: '700', color: Colors.textPrimary },
  error: { color: Colors.red, fontWeight: '700', fontSize: 14 },
});

export default BacktestScreen;
