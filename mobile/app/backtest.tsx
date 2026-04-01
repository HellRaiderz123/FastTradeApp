import React, { useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, StatusBar, TextInput, Dimensions, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Polyline, Polygon, Line, Text as SvgText } from 'react-native-svg';
import { backtestAPI, scannerAPI } from '../lib/api';
import { Colors, Gradients, Radius, Spacing } from '../lib/theme';
import { GlassCard, PrimaryButton, Tag } from '../components/ui';

const SCREEN_W = Dimensions.get('window').width;

const BacktestScreen = () => {
  const router = useRouter();
  const params = useLocalSearchParams<{
    strategyId?: string;
    strategyName?: string;
    universe?: string;
    timeframe?: string;
    backtestType?: string;
    slPct?: string;
    tpPct?: string;
    tslPct?: string;
    exitMode?: string;
    positionSizePct?: string;
    maxOpenTrades?: string;
    initialCapital?: string;
  }>();
  const prefilledStrategyId = params.strategyId ? Number(params.strategyId) : null;
  const initialUnderlying = params.universe ? String(params.universe) : 'NIFTY';
  const initialType: 'generic' | 'scanner' = params.backtestType === 'scanner' ? 'scanner' : 'generic';

  const [underlying, setUnderlying] = useState(initialUnderlying);
  const [timeframe, setTimeframe] = useState(params.timeframe ? String(params.timeframe) : 'Day');
  const [backtestType, setBacktestType] = useState<'generic' | 'scanner'>(initialType);
  const [strategyId, setStrategyId] = useState(prefilledStrategyId ? String(prefilledStrategyId) : '');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [capital, setCapital] = useState(params.initialCapital ? String(params.initialCapital) : '100000');
  const [slPct, setSlPct] = useState(params.slPct ? String(params.slPct) : '');
  const [tpPct, setTpPct] = useState(params.tpPct ? String(params.tpPct) : '');
  const [tslPct, setTslPct] = useState(params.tslPct ? String(params.tslPct) : '0');
  const [positionSizePct, setPositionSizePct] = useState(params.positionSizePct ? String(params.positionSizePct) : '10');
  const [maxOpenTrades, setMaxOpenTrades] = useState(params.maxOpenTrades ? String(params.maxOpenTrades) : '5');
  const [loading, setLoading] = useState(false);
  const [dateRangeLoading, setDateRangeLoading] = useState(initialType === 'scanner');
  const [dateRangeInfo, setDateRangeInfo] = useState<string | null>(null);
  const [result, setResult] = useState(null);
  const isRunningRef = useRef(false);

  // Auto-populate date range from actual candle data when in scanner mode
  useEffect(() => {
    if (backtestType !== 'scanner') {
      setDateRangeLoading(false);
      return;
    }
    setDateRangeLoading(true);
    setDateRangeInfo(null);
    scannerAPI.getCandleRange(timeframe, underlying || 'NIFTY50')
      .then((res) => {
        const min = res.data?.min_date;
        const max = res.data?.max_date;
        const rows = res.data?.total_rows;
        const syms = res.data?.symbols_with_data;
        if (min) setStartDate(min);
        if (max) setEndDate(max);
        if (min && max) {
          setDateRangeInfo(`${rows?.toLocaleString() || '?'} candles for ${syms || '?'} symbols (${min} – ${max})`);
        } else {
          setDateRangeInfo('No candle data found for this timeframe. Change timeframe or load data first.');
        }
      })
      .catch(() => {
        setDateRangeInfo('Could not fetch date range. Enter dates manually.');
      })
      .finally(() => setDateRangeLoading(false));
  }, [backtestType, timeframe, underlying]);

  const handleRunBacktest = async () => {
    if (isRunningRef.current) return; // guard against rapid double-tap
    if (dateRangeLoading) return;     // wait for date range to resolve
    const strategyIdNum = Number(strategyId || prefilledStrategyId || 0);
    if (!strategyIdNum || Number.isNaN(strategyIdNum)) {
      setResult({ error: 'Please enter a valid Strategy ID (numeric). If opened from Scanner, go back and re-open Backtest from a selected strategy.' });
      return;
    }
    if (!startDate || !endDate) {
      setResult({ error: 'Start and end dates are required. Wait for date range to load or enter manually.' });
      return;
    }

    isRunningRef.current = true;
    setLoading(true);
    setResult(null);
    try {
      if (backtestType === 'scanner') {
        let payload: any = {
          initial_capital: Number(capital) || 100000,
          position_size_pct: Number(positionSizePct) || 10,
          max_open_trades: Number(maxOpenTrades) || 5,
          start_date: startDate,
          end_date: endDate,
          ...(slPct.trim() ? { sl_pct: Number(slPct) } : {}),
          ...(tpPct.trim() ? { tp_pct: Number(tpPct) } : {}),
          ...(tslPct.trim() ? { tsl_pct: Number(tslPct) } : {}),
        };

        const response = await scannerAPI.runBacktest(strategyIdNum, payload);
        const data = response.data || {};
        // Surface backend error (e.g. no candle data) to the user
        if (data.error) {
          setResult({ error: data.error } as any);
        } else {
          const summary = data.summary || {};
          const normalizedEquity = Array.isArray(data.equity_curve)
            ? data.equity_curve.map((point: any) => Number(point?.equity)).filter((value: number) => !Number.isNaN(value))
            : [];

          setResult({
            total_return_pct: summary.total_return_pct,
            annual_return_pct: summary.annual_return_pct,
            sharpe_ratio: summary.sharpe_ratio,
            max_drawdown_pct: summary.max_drawdown_pct,
            win_rate_pct: summary.win_rate,
            total_trades: summary.total_trades,
            equity_curve: normalizedEquity,
            raw: data,
          } as any);
        }
      } else {
        const payload = {
          strategy_config_id: strategyIdNum,
          start_date: startDate,
          end_date: endDate,
          initial_capital: Number(capital) || 100000,
          mode: 'auto',
          ...(slPct.trim() ? { sl_pct: Number(slPct) } : {}),
          ...(tpPct.trim() ? { tp_pct: Number(tpPct) } : {}),
          ...(tslPct.trim() ? { tsl_pct: Number(tslPct) } : {}),
        };
        const response = await backtestAPI.runBacktest(payload);
        setResult(response.data || {});
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.response?.data?.error || 'Failed to run backtest';
      setResult({ error: String(detail) } as any);
    } finally {
      isRunningRef.current = false;
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
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}>
            <Ionicons name="chevron-back" size={22} color={Colors.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.title}>Backtest Lab</Text>
          <Text style={styles.subtitle}>Run historical strategy checks with fast mobile inputs</Text>
        </LinearGradient>

        <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          <GlassCard style={styles.formCard}>
            <View style={styles.formHead}>
              <Text style={styles.sectionTitle}>Configuration</Text>
              <Tag label="HISTORICAL" color={Colors.accent} bg={Colors.accentSoft} />
            </View>

            {/* Mode switch — hidden when pre-filled from scanner (type is already locked) */}
            {!prefilledStrategyId && (
            <View style={styles.modeSwitchRow}>
              <TouchableOpacity
                activeOpacity={0.8}
                onPress={() => setBacktestType('generic')}
                style={[styles.modeSwitchBtn, backtestType === 'generic' && styles.modeSwitchBtnActive]}
              >
                <Text style={[styles.modeSwitchText, backtestType === 'generic' && styles.modeSwitchTextActive]}>Generic</Text>
              </TouchableOpacity>
              <TouchableOpacity
                activeOpacity={0.8}
                onPress={() => setBacktestType('scanner')}
                style={[styles.modeSwitchBtn, backtestType === 'scanner' && styles.modeSwitchBtnActive]}
              >
                <Text style={[styles.modeSwitchText, backtestType === 'scanner' && styles.modeSwitchTextActive]}>Scanner</Text>
              </TouchableOpacity>
            </View>
            )}

            {prefilledStrategyId ? (
              <View style={styles.strategyInfoRow}>
                <Text style={styles.strategyInfoLabel}>Strategy</Text>
                <Text style={styles.strategyInfoValue}>
                  {params.strategyName || `Strategy #${prefilledStrategyId}`}
                </Text>
              </View>
            ) : null}

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Strategy ID</Text>
              <TextInput
                style={styles.input}
                value={strategyId}
                onChangeText={setStrategyId}
                keyboardType="number-pad"
                placeholder="e.g. 1"
                placeholderTextColor={Colors.textFaint}
                editable={!prefilledStrategyId}
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>{backtestType === 'scanner' ? 'Universe' : 'Underlying'}</Text>
              <TextInput style={styles.input} value={underlying} onChangeText={setUnderlying} autoCapitalize="characters" placeholder={backtestType === 'scanner' ? 'NIFTY50' : 'NIFTY'} placeholderTextColor={Colors.textFaint} />
            </View>

            {backtestType === 'scanner' ? (
              <View style={styles.inputGroup}>
                <Text style={styles.label}>Timeframe</Text>
                <TextInput style={styles.input} value={timeframe} onChangeText={setTimeframe} placeholder="Day / 15 Min / 1 Hour" placeholderTextColor={Colors.textFaint} />
              </View>
            ) : null}

            {backtestType === 'scanner' && dateRangeLoading && (
              <Text style={styles.helperText}>⏳ Fetching available date range…</Text>
            )}
            {backtestType === 'scanner' && !dateRangeLoading && dateRangeInfo && (
              <Text style={[styles.helperText, { color: dateRangeInfo.startsWith('No') || dateRangeInfo.startsWith('Could') ? Colors.red : Colors.green }]}>
                📊 {dateRangeInfo}
              </Text>
            )}

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

            {backtestType === 'scanner' ? (
              <View style={styles.rowInputs}>
                <View style={[styles.inputGroup, styles.halfInput]}>
                  <Text style={styles.label}>Position Size %</Text>
                  <TextInput
                    style={styles.input}
                    value={positionSizePct}
                    onChangeText={setPositionSizePct}
                    keyboardType="decimal-pad"
                    placeholder="10"
                    placeholderTextColor={Colors.textFaint}
                  />
                </View>
                <View style={[styles.inputGroup, styles.halfInput]}>
                  <Text style={styles.label}>Max Open Trades</Text>
                  <TextInput
                    style={styles.input}
                    value={maxOpenTrades}
                    onChangeText={setMaxOpenTrades}
                    keyboardType="number-pad"
                    placeholder="5"
                    placeholderTextColor={Colors.textFaint}
                  />
                </View>
              </View>
            ) : null}

            <View style={styles.rowInputs}>
              <View style={[styles.inputGroup, styles.halfInput]}>
                <Text style={styles.label}>SL % (optional)</Text>
                <TextInput
                  style={styles.input}
                  value={slPct}
                  onChangeText={setSlPct}
                  keyboardType="decimal-pad"
                  placeholder="e.g. 2.0"
                  placeholderTextColor={Colors.textFaint}
                />
              </View>
              <View style={[styles.inputGroup, styles.halfInput]}>
                <Text style={styles.label}>TP % (optional)</Text>
                <TextInput
                  style={styles.input}
                  value={tpPct}
                  onChangeText={setTpPct}
                  keyboardType="decimal-pad"
                  placeholder="e.g. 8.0"
                  placeholderTextColor={Colors.textFaint}
                />
              </View>
            </View>
            <View style={styles.inputGroup}>
              <Text style={styles.label}>TSL % (optional, 0 = disabled)</Text>
              <TextInput
                style={styles.input}
                value={tslPct}
                onChangeText={setTslPct}
                keyboardType="decimal-pad"
                placeholder="e.g. 1.5"
                placeholderTextColor={Colors.textFaint}
              />
            </View>

            {backtestType === 'scanner' ? (
              <View style={styles.strategyInfoRow}>
                <Text style={styles.strategyInfoLabel}>Scanner Exit Setup</Text>
                <Text style={styles.strategyInfoValue}>SL {slPct || '5'}% · TP {tpPct || '10'}% · TSL {tslPct || '0'}% · {params.exitMode || 'percentage'}</Text>
              </View>
            ) : null}

            {backtestType === 'scanner' ? (
              <Text style={styles.helperText}>
                Scanner mode uses the strategy's saved exit config shown above. Position size and max open trades can still be adjusted here.
              </Text>
            ) : (
              <Text style={styles.helperText}>
                Generic mode: use Strategy Config ID from /strategies endpoint (option spreads).
              </Text>
            )}

            <PrimaryButton title="Run Backtest" onPress={handleRunBacktest} loading={loading} disabled={loading || dateRangeLoading} variant="success" />
          </GlassCard>

          {result && (
            <GlassCard style={styles.resultCard}>
              {'error' in (result as any) ? (
                <Text style={styles.error}>{(result as any).error}</Text>
              ) : (
                <>
                  <Text style={styles.sectionTitle}>Results</Text>
                  {/* Equity Curve Chart */}
                  {(result as any).equity_curve?.length > 1 && (
                    <>
                      <EquityChart
                        data={(result as any).equity_curve}
                        initial={parseInt(capital) || 100000}
                      />
                      {/* Drawdown Chart */}
                      <DrawdownChart
                        data={(result as any).equity_curve}
                        initial={parseInt(capital) || 100000}
                      />
                    </>
                  )}
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
  backButton: { alignSelf: 'flex-start', marginBottom: 10 },
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
  modeSwitchRow: { flexDirection: 'row', marginBottom: 12, gap: 8 },
  modeSwitchBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass,
    paddingVertical: 9,
    alignItems: 'center',
  },
  modeSwitchBtnActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  modeSwitchText: { fontSize: 12, color: Colors.textSecondary, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.6 },
  modeSwitchTextActive: { color: Colors.accentLight },
  strategyInfoRow: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 12,
  },
  strategyInfoLabel: { fontSize: 11, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.7 },
  strategyInfoValue: { fontSize: 14, color: Colors.textPrimary, fontWeight: '600', marginTop: 4 },
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
  helperText: { marginTop: -4, marginBottom: 10, fontSize: 11, color: Colors.textMuted },
  error: { color: Colors.red, fontWeight: '700', fontSize: 14 },
});

function EquityChart({ data, initial }: { data: number[]; initial: number }) {
  const W = SCREEN_W - Spacing.lg * 2 - Spacing.md * 2; // card padding
  const H = 130;
  const padT = 12, padB = 24, padL = 8, padR = 8;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;

  if (!data || data.length < 2) return null;

  const minV = Math.min(...data);
  const maxV = Math.max(...data);
  const range = maxV - minV || 1;
  const toX = (i: number) => padL + (i / (data.length - 1)) * chartW;
  const toY = (v: number) => padT + (1 - (v - minV) / range) * chartH;

  const linePoints = data.map((v, i) => `${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(' ');
  const fillPoints =
    `${(padL).toFixed(1)},${(padT + chartH).toFixed(1)} ` +
    linePoints +
    ` ${toX(data.length - 1).toFixed(1)},${(padT + chartH).toFixed(1)}`;

  const isPositive = data[data.length - 1] >= initial;
  const lineColor = isPositive ? Colors.green : Colors.red;
  const fillColor = isPositive ? 'rgba(16,185,129,0.18)' : 'rgba(239,68,68,0.12)';

  const startLabel = `₹${(data[0] / 1000).toFixed(0)}k`;
  const endLabel = `₹${(data[data.length - 1] / 1000).toFixed(0)}k`;

  return (
    <View style={{ marginTop: 12, marginBottom: 8 }}>
      <Text style={{ fontSize: 11, color: Colors.textMuted, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.8 }}>Equity Curve</Text>
      <Svg width={W} height={H}>
        {/* Baseline */}
        <Line
          x1={padL} y1={padT + chartH}
          x2={padL + chartW} y2={padT + chartH}
          stroke={Colors.border} strokeWidth={1}
        />
        {/* Mid grid */}
        <Line
          x1={padL} y1={padT + chartH / 2}
          x2={padL + chartW} y2={padT + chartH / 2}
          stroke={Colors.border} strokeWidth={0.5} strokeDasharray="4,4"
        />
        {/* Fill area */}
        <Polygon points={fillPoints} fill={fillColor} />
        {/* Line */}
        <Polyline points={linePoints} fill="none" stroke={lineColor} strokeWidth={2} strokeLinejoin="round" />
        {/* Labels */}
        <SvgText x={padL} y={H - 4} fontSize={10} fill={Colors.textMuted}>{startLabel}</SvgText>
        <SvgText x={padL + chartW} y={H - 4} fontSize={10} fill={lineColor} textAnchor="end">{endLabel}</SvgText>
      </Svg>
    </View>
  );
}

function DrawdownChart({ data, initial }: { data: number[]; initial: number }) {
  const W = SCREEN_W - Spacing.lg * 2 - Spacing.md * 2; // card padding
  const H = 100;
  const padT = 12, padB = 24, padL = 8, padR = 8;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;

  if (!data || data.length < 2) return null;

  // Calculate running max and drawdown from peak
  let runningMax = data[0];
  const drawdownData = data.map((equity) => {
    if (equity > runningMax) runningMax = equity;
    return ((equity - runningMax) / runningMax) * 100; // DD as %
  });

  const minDD = Math.min(...drawdownData);
  const maxDD = Math.max(...drawdownData);
  const range = maxDD - minDD || 1;

  const toX = (i: number) => padL + (i / (drawdownData.length - 1)) * chartW;
  const toY = (dd: number) => padT + (1 - (dd - minDD) / range) * chartH;

  const linePoints = drawdownData.map((dd, i) => `${toX(i).toFixed(1)},${toY(dd).toFixed(1)}`).join(' ');
  const fillPoints =
    `${(padL).toFixed(1)},${(padT + chartH).toFixed(1)} ` +
    linePoints +
    ` ${toX(drawdownData.length - 1).toFixed(1)},${(padT + chartH).toFixed(1)}`;

  const worstDD = drawdownData[drawdownData.length - 1];
  const minLabel = `${minDD.toFixed(1)}%`;
  const endLabel = `${worstDD.toFixed(1)}%`;

  return (
    <View style={{ marginTop: 8, marginBottom: 12 }}>
      <Text style={{ fontSize: 11, color: Colors.textMuted, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.8 }}>Drawdown Chart</Text>
      <Svg width={W} height={H}>
        {/* Baseline */}
        <Line
          x1={padL} y1={padT + chartH}
          x2={padL + chartW} y2={padT + chartH}
          stroke={Colors.border} strokeWidth={1}
        />
        {/* Mid grid */}
        <Line
          x1={padL} y1={padT + chartH / 2}
          x2={padL + chartW} y2={padT + chartH / 2}
          stroke={Colors.border} strokeWidth={0.5} strokeDasharray="4,4"
        />
        {/* Fill area (always red/orange since drawdown is negative) */}
        <Polygon points={fillPoints} fill="rgba(239,68,68,0.15)" />
        {/* Line */}
        <Polyline points={linePoints} fill="none" stroke={Colors.red} strokeWidth={2} strokeLinejoin="round" />
        {/* Labels */}
        <SvgText x={padL} y={H - 4} fontSize={10} fill={Colors.textMuted}>{minLabel}</SvgText>
        <SvgText x={padL + chartW} y={H - 4} fontSize={10} fill={Colors.red} textAnchor="end">{endLabel}</SvgText>
      </Svg>
    </View>
  );
}

export default BacktestScreen;
