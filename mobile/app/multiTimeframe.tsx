import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Dimensions, RefreshControl, ScrollView, StatusBar, StyleSheet,
  Text, TouchableOpacity, View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import { useRouter } from 'expo-router';
import { candleAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, ScreenHeader, Tag } from '../components/ui';

const SYMBOLS = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX', 'RELIANCE', 'TCS', 'INFY'];
const TIMEFRAMES = ['1m', '5m', '15m', '1h', 'Day'];
const { width: SCREEN_W } = Dimensions.get('window');
const CHART_W = SCREEN_W - Spacing.lg * 2 - 32; // card padding
const CANDLE_W = 6;
const CANDLE_GAP = 2;
const CHART_H = 180;

interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

function CandleChart({ candles }: { candles: Candle[] }) {
  if (!candles.length) return null;

  const maxVisible = Math.floor(CHART_W / (CANDLE_W + CANDLE_GAP));
  const visible = candles.slice(-maxVisible);

  const highs = visible.map((c) => c.high);
  const lows = visible.map((c) => c.low);
  const maxH = Math.max(...highs);
  const minL = Math.min(...lows);
  const range = maxH - minL || 1;

  const toY = (price: number) => ((maxH - price) / range) * CHART_H;

  return (
    <View style={{ height: CHART_H, width: CHART_W, position: 'relative' }}>
      {/* Price grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((pct) => (
        <View
          key={pct}
          style={{
            position: 'absolute',
            top: pct * CHART_H,
            left: 0,
            right: 0,
            height: StyleSheet.hairlineWidth,
            backgroundColor: Colors.border,
          }}
        />
      ))}

      {/* Candles */}
      {visible.map((c, i) => {
        const isGreen = c.close >= c.open;
        const color = isGreen ? Colors.green : Colors.red;
        const bodyTop = toY(Math.max(c.open, c.close));
        const bodyH = Math.max(1, Math.abs(toY(c.open) - toY(c.close)));
        const wickTop = toY(c.high);
        const wickH = Math.max(1, toY(c.low) - toY(c.high));
        const x = i * (CANDLE_W + CANDLE_GAP);

        return (
          <View key={i} style={{ position: 'absolute', left: x, top: 0, width: CANDLE_W }}>
            {/* Wick */}
            <View
              style={{
                position: 'absolute',
                left: CANDLE_W / 2 - 0.5,
                top: wickTop,
                width: 1,
                height: wickH,
                backgroundColor: color,
              }}
            />
            {/* Body */}
            <View
              style={{
                position: 'absolute',
                left: 0,
                top: bodyTop,
                width: CANDLE_W,
                height: bodyH,
                backgroundColor: color,
                opacity: isGreen ? 0.9 : 0.85,
              }}
            />
          </View>
        );
      })}
    </View>
  );
}

function PriceLabels({ candles }: { candles: Candle[] }) {
  if (!candles.length) return null;
  const last = candles[candles.length - 1];
  const first = candles[0];
  const change = last.close - first.open;
  const changePct = (change / first.open) * 100;
  const isPos = change >= 0;
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 }}>
      <View>
        <Text style={{ fontSize: 11, color: Colors.textMuted }}>O: {first.open.toFixed(2)}</Text>
        <Text style={{ fontSize: 11, color: Colors.textMuted }}>H: {Math.max(...candles.map(c => c.high)).toFixed(2)}</Text>
      </View>
      <View style={{ alignItems: 'center' }}>
        <Text style={{ fontSize: 18, fontWeight: '700', color: isPos ? Colors.green : Colors.red }}>
          {last.close.toFixed(2)}
        </Text>
        <Text style={{ fontSize: 12, color: isPos ? Colors.green : Colors.red }}>
          {isPos ? '+' : ''}{change.toFixed(2)} ({changePct.toFixed(2)}%)
        </Text>
      </View>
      <View style={{ alignItems: 'flex-end' }}>
        <Text style={{ fontSize: 11, color: Colors.textMuted }}>L: {Math.min(...candles.map(c => c.low)).toFixed(2)}</Text>
        <Text style={{ fontSize: 11, color: Colors.textMuted }}>C: {last.close.toFixed(2)}</Text>
      </View>
    </View>
  );
}

export default function MultiTimeframeScreen() {
  const router = useRouter();
  const [symbol, setSymbol] = useState('NIFTY');
  const [timeframe, setTimeframe] = useState('15m');
  const [candles, setCandles] = useState<Candle[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchCandles = useCallback(async (sym: string, tf: string) => {
    try {
      const res = await candleAPI.getCandles(sym, tf, 100);
      const data = res.data;
      const arr: Candle[] = Array.isArray(data)
        ? data
        : Array.isArray(data?.candles)
          ? data.candles
          : Array.isArray(data?.data)
            ? data.data
            : [];
      setCandles(arr);
      setLastUpdated(new Date());
    } catch {
      setCandles([]);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchCandles(symbol, timeframe);
  }, [symbol, timeframe]);

  // Auto-refresh every 30s
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => fetchCandles(symbol, timeframe), 30000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [symbol, timeframe, fetchCandles]);

  const onRefresh = () => {
    setRefreshing(true);
    Haptics.selectionAsync();
    fetchCandles(symbol, timeframe);
  };

  const last = candles.length > 0 ? candles[candles.length - 1] : null;
  const isPos = last ? last.close >= last.open : true;

  return (
    <View style={s.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={s.flex}>
        <ScreenHeader
          title="Multi-Timeframe"
          subtitle={`${symbol} · ${timeframe} candles`}
          badge={
            last ? (
              <Tag
                label={isPos ? '▲' : '▼'}
                color={isPos ? Colors.green : Colors.red}
                bg={isPos ? Colors.greenBg : Colors.redBg}
              />
            ) : undefined
          }
          onBack={() => router.back()}
        />

        {/* Symbol selector */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.pillRow} contentContainerStyle={{ gap: 6, paddingHorizontal: Spacing.md }}>
          {SYMBOLS.map((sym) => (
            <TouchableOpacity
              key={sym}
              style={[s.pill, symbol === sym && s.pillActive]}
              onPress={() => { Haptics.selectionAsync(); setSymbol(sym); }}
              activeOpacity={0.8}
            >
              <Text style={[s.pillText, symbol === sym && s.pillTextActive]}>{sym}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Timeframe selector */}
        <View style={s.tfRow}>
          {TIMEFRAMES.map((tf) => (
            <TouchableOpacity
              key={tf}
              style={[s.tfBtn, timeframe === tf && s.tfBtnActive]}
              onPress={() => { Haptics.selectionAsync(); setTimeframe(tf); }}
              activeOpacity={0.8}
            >
              <Text style={[s.tfText, timeframe === tf && s.tfTextActive]}>{tf}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <ScrollView
          contentContainerStyle={s.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          {loading ? (
            <LoadingSpinner />
          ) : candles.length === 0 ? (
            <EmptyState icon="📊" title="No Candle Data" subtitle={`No ${timeframe} candles available for ${symbol}. Check backend connection.`} />
          ) : (
            <>
              {/* Main chart */}
              <GlassCard style={s.chartCard}>
                <View style={s.chartHeader}>
                  <Text style={s.chartTitle}>{symbol}</Text>
                  <Text style={s.chartSub}>{timeframe} · {candles.length} candles</Text>
                </View>
                <CandleChart candles={candles} />
                <PriceLabels candles={candles} />
                {lastUpdated && (
                  <Text style={s.updateTime}>
                    ⏱ {lastUpdated.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </Text>
                )}
              </GlassCard>

              {/* OHLCV table — last 20 candles */}
              <GlassCard style={s.card}>
                <Text style={s.cardTitle}>Recent Candles</Text>
                <View style={s.tableHeader}>
                  <Text style={[s.th, { flex: 1.5 }]}>Time</Text>
                  <Text style={[s.th, { flex: 1, textAlign: 'right' }]}>Open</Text>
                  <Text style={[s.th, { flex: 1, textAlign: 'right' }]}>High</Text>
                  <Text style={[s.th, { flex: 1, textAlign: 'right' }]}>Low</Text>
                  <Text style={[s.th, { flex: 1, textAlign: 'right' }]}>Close</Text>
                </View>
                {[...candles].reverse().slice(0, 20).map((c, i) => {
                  const green = c.close >= c.open;
                  return (
                    <View key={i} style={[s.tableRow, { backgroundColor: green ? 'rgba(16,185,129,0.04)' : 'rgba(239,68,68,0.04)' }]}>
                      <Text style={[s.td, { flex: 1.5 }]} numberOfLines={1}>
                        {c.timestamp ? new Date(c.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : `${i}`}
                      </Text>
                      <Text style={[s.td, { flex: 1, textAlign: 'right' }]}>{c.open.toFixed(1)}</Text>
                      <Text style={[s.td, { flex: 1, textAlign: 'right', color: Colors.green }]}>{c.high.toFixed(1)}</Text>
                      <Text style={[s.td, { flex: 1, textAlign: 'right', color: Colors.red }]}>{c.low.toFixed(1)}</Text>
                      <Text style={[s.td, { flex: 1, textAlign: 'right', color: green ? Colors.green : Colors.red, fontWeight: '700' }]}>{c.close.toFixed(1)}</Text>
                    </View>
                  );
                })}
              </GlassCard>

              {/* Volume bar chart */}
              {candles.some((c) => c.volume) && (
                <GlassCard style={s.card}>
                  <Text style={s.cardTitle}>Volume</Text>
                  <View style={s.volChart}>
                    {candles.slice(-40).map((c, i) => {
                      const maxVol = Math.max(...candles.slice(-40).map((x) => x.volume || 0));
                      const pct = maxVol > 0 ? ((c.volume || 0) / maxVol) * 60 : 0;
                      const green = c.close >= c.open;
                      return (
                        <View
                          key={i}
                          style={{
                            width: 5,
                            height: Math.max(2, pct),
                            backgroundColor: green ? Colors.green : Colors.red,
                            opacity: 0.7,
                            alignSelf: 'flex-end',
                            marginRight: 1,
                          }}
                        />
                      );
                    })}
                  </View>
                </GlassCard>
              )}
            </>
          )}
          <View style={{ height: 100 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  flex: { flex: 1 },
  scroll: { padding: Spacing.lg, flexGrow: 1 },
  pillRow: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: Colors.border },
  pill: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: Radius.full, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.bgGlass },
  pillActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  pillText: { fontSize: 13, fontWeight: '600', color: Colors.textSecondary },
  pillTextActive: { color: Colors.accentLight },
  tfRow: { flexDirection: 'row', paddingHorizontal: Spacing.md, paddingVertical: 8, gap: 6, borderBottomWidth: 1, borderBottomColor: Colors.border },
  tfBtn: { flex: 1, paddingVertical: 6, alignItems: 'center', borderRadius: Radius.sm, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.bgGlass },
  tfBtnActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  tfText: { fontSize: 12, fontWeight: '700', color: Colors.textSecondary },
  tfTextActive: { color: Colors.accentLight },
  chartCard: { marginBottom: 12, padding: Spacing.md },
  chartHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  chartTitle: { fontSize: 16, fontWeight: '700', color: Colors.textPrimary },
  chartSub: { fontSize: 12, color: Colors.textMuted },
  updateTime: { fontSize: 10, color: Colors.textFaint, marginTop: 8, textAlign: 'right' },
  card: { marginBottom: 12 },
  cardTitle: { fontSize: 14, fontWeight: '700', color: Colors.textPrimary, marginBottom: 8 },
  tableHeader: { flexDirection: 'row', paddingBottom: 6, borderBottomWidth: 1, borderBottomColor: Colors.border, marginBottom: 2 },
  th: { fontSize: 10, fontWeight: '700', color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.5 },
  tableRow: { flexDirection: 'row', paddingVertical: 5, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: Colors.border },
  td: { fontSize: 11, color: Colors.textSecondary },
  volChart: { flexDirection: 'row', alignItems: 'flex-end', height: 64, overflow: 'hidden' },
});
