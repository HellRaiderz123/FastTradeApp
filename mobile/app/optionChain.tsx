import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, StatusBar, TouchableOpacity,
  ActivityIndicator, RefreshControl, Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import { useRouter } from 'expo-router';
import { marketAPI, optionsAPI } from '../lib/api';
import { Colors, Spacing, Radius, Gradients } from '../lib/theme';
import { ScreenHeader, Tag, GlassCard } from '../components/ui';

const SYMBOLS = ['NIFTY', 'BANKNIFTY', 'FINNIFTY'];

interface OptionLeg {
  ltp: number;
  change: number;
  change_percent: number;
  volume: number;
  oi: number;
  iv: number;
  delta: number;
  theta: number;
  vega: number;
  bid: number;
  ask: number;
}

interface StrikeRow {
  strike: number;
  call: OptionLeg | null;
  put: OptionLeg | null;
}

interface ChainData {
  symbol: string;
  spot: number;
  expiry: string;
  days_to_expiry: number;
  strikes: StrikeRow[];
}

export default function OptionChainScreen() {
  const router = useRouter();
  const [symbol, setSymbol] = useState('NIFTY');
  const [chain, setChain] = useState<ChainData | null>(null);
  const [expiries, setExpiries] = useState<string[]>([]);
  const [selectedExpiry, setSelectedExpiry] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // Pulsing LIVE dot
  useEffect(() => {
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 0.2, duration: 900, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 900, useNativeDriver: true }),
      ])
    );
    pulse.start();
    return () => pulse.stop();
  }, [pulseAnim]);

  const fetchExpiries = useCallback(async (sym: string) => {
    try {
      const res = await marketAPI.getAvailableExpiries(sym);
      const list: string[] = res.data?.expiries || res.data || [];
      setExpiries(list);
      if (list.length > 0 && !selectedExpiry) {
        setSelectedExpiry(list[0]);
      }
    } catch {}
  }, [selectedExpiry]);

  const fetchChain = useCallback(async (sym: string, expiry?: string) => {
    try {
      const res = await optionsAPI.getChain(sym, expiry);
      setChain(res.data);
      setLastUpdated(new Date());
    } catch {
      setChain(null);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchExpiries(symbol);
    fetchChain(symbol, selectedExpiry);
  }, [symbol]);

  useEffect(() => {
    if (selectedExpiry) fetchChain(symbol, selectedExpiry);
  }, [selectedExpiry]);

  // Auto-refresh every 15s
  useEffect(() => {
    pollRef.current = setInterval(() => {
      fetchChain(symbol, selectedExpiry).catch(() => {});
    }, 15000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [symbol, selectedExpiry]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    Haptics.selectionAsync();
    fetchChain(symbol, selectedExpiry);
  }, [symbol, selectedExpiry]);

  const atmStrike = chain ? Math.round(chain.spot / 50) * 50 : null;

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <ScreenHeader
        title="Option Chain"
        subtitle={chain ? `Spot ₹${chain.spot?.toLocaleString('en-IN')}  ·  ${chain.days_to_expiry}d to expiry` : 'Live options data'}
        badge={
          <View style={styles.liveBadge}>
            <Animated.View style={[styles.liveDot, { opacity: pulseAnim }]} />
            <Text style={styles.liveBadgeText}>LIVE</Text>
          </View>
        }
        onBack={() => router.back()}
      />

      <SafeAreaView edges={['bottom']} style={styles.flex}>
        {/* Symbol + Expiry selectors */}
        <View style={styles.controls}>
          {/* Symbol pills */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.pillRow}>
            {SYMBOLS.map((s) => (
              <TouchableOpacity
                key={s}
                style={[styles.pill, symbol === s && styles.pillActive]}
                onPress={() => { Haptics.selectionAsync(); setSymbol(s); setSelectedExpiry(undefined); }}
                activeOpacity={0.8}
              >
                <Text style={[styles.pillText, symbol === s && styles.pillTextActive]}>{s}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          {/* Expiry pills */}
          {expiries.length > 0 && (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.pillRow}>
              {expiries.slice(0, 5).map((exp) => (
                <TouchableOpacity
                  key={exp}
                  style={[styles.pill, styles.pillSm, selectedExpiry === exp && styles.pillActive]}
                  onPress={() => { Haptics.selectionAsync(); setSelectedExpiry(exp); }}
                  activeOpacity={0.8}
                >
                  <Text style={[styles.pillText, { fontSize: 11 }, selectedExpiry === exp && styles.pillTextActive]}>{exp}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          )}
        </View>

        {/* Column headers */}
        <View style={styles.tableHeader}>
          <Text style={[styles.colHead, styles.colLtp]}>CE LTP</Text>
          <Text style={[styles.colHead, styles.colOI]}>CE OI</Text>
          <Text style={[styles.colHead, styles.colStrike]}>STRIKE</Text>
          <Text style={[styles.colHead, styles.colOI]}>PE OI</Text>
          <Text style={[styles.colHead, styles.colLtp, { textAlign: 'right' }]}>PE LTP</Text>
        </View>

        {loading ? (
          <View style={styles.center}><ActivityIndicator color={Colors.accent} size="large" /></View>
        ) : (
          <ScrollView
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
            showsVerticalScrollIndicator={false}
          >
            {chain?.strikes?.map((row) => {
              const isAtm = row.strike === atmStrike;
              return (
                <View key={row.strike} style={[styles.strikeRow, isAtm && styles.strikeRowAtm]}>
                  {/* Call LTP */}
                  <View style={styles.colLtp}>
                    <Text style={[styles.ltpText, { color: row.call?.change_percent >= 0 ? Colors.green : Colors.red }]}>
                      {row.call?.ltp?.toFixed(1) ?? '-'}
                    </Text>
                    {row.call?.iv ? (
                      <Text style={styles.ivText}>IV {row.call.iv.toFixed(1)}%</Text>
                    ) : null}
                  </View>

                  {/* Call OI bar + value */}
                  <View style={styles.colOI}>
                    <Text style={styles.oiText}>{formatOI(row.call?.oi)}</Text>
                    <Text style={styles.deltaText}>Δ{row.call?.delta?.toFixed(2)}</Text>
                  </View>

                  {/* Strike */}
                  <View style={[styles.colStrike, isAtm && styles.atmCol]}>
                    <Text style={[styles.strikeText, isAtm && styles.strikeTextAtm]}>{row.strike}</Text>
                    {isAtm && <Text style={styles.atmLabel}>ATM</Text>}
                  </View>

                  {/* Put OI */}
                  <View style={styles.colOI}>
                    <Text style={styles.oiText}>{formatOI(row.put?.oi)}</Text>
                    <Text style={styles.deltaText}>Δ{row.put?.delta?.toFixed(2)}</Text>
                  </View>

                  {/* Put LTP */}
                  <View style={[styles.colLtp, { alignItems: 'flex-end' }]}>
                    <Text style={[styles.ltpText, { color: row.put?.change_percent >= 0 ? Colors.green : Colors.red }]}>
                      {row.put?.ltp?.toFixed(1) ?? '-'}
                    </Text>
                    {row.put?.iv ? (
                      <Text style={styles.ivText}>IV {row.put.iv.toFixed(1)}%</Text>
                    ) : null}
                  </View>
                </View>
              );
            })}
            <View style={{ height: 100 }} />
          </ScrollView>
        )}

        {lastUpdated && (
          <View style={styles.footer}>
            <Text style={styles.footerText}>
              ⏱ Updated {lastUpdated.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </Text>
          </View>
        )}
      </SafeAreaView>
    </View>
  );
}

function formatOI(oi?: number): string {
  if (!oi) return '-';
  if (oi >= 10_000_000) return `${(oi / 10_000_000).toFixed(1)}Cr`;
  if (oi >= 100_000) return `${(oi / 100_000).toFixed(1)}L`;
  if (oi >= 1_000) return `${(oi / 1_000).toFixed(0)}K`;
  return oi.toString();
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  flex: { flex: 1 },
  controls: { paddingTop: 8, borderBottomWidth: 1, borderBottomColor: Colors.border },
  pillRow: { paddingHorizontal: Spacing.md, paddingVertical: 6 },
  pill: {
    paddingHorizontal: 14, paddingVertical: 6, borderRadius: Radius.full,
    borderWidth: 1, borderColor: Colors.border,
    backgroundColor: Colors.bgGlass, marginRight: 8,
  },
  pillSm: { paddingHorizontal: 10, paddingVertical: 4 },
  pillActive: { backgroundColor: Colors.accentSoft, borderColor: Colors.accent },
  pillText: { fontSize: 13, fontWeight: '600', color: Colors.textSecondary },
  pillTextActive: { color: Colors.accentLight },
  tableHeader: {
    flexDirection: 'row', paddingHorizontal: Spacing.md,
    paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: Colors.border,
    backgroundColor: Colors.bgCard,
  },
  colHead: { fontSize: 10, fontWeight: '700', color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.6 },
  colLtp: { width: 72 },
  colOI: { flex: 1, alignItems: 'center' },
  colStrike: { width: 72, alignItems: 'center' },
  strikeRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: Spacing.md, paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: Colors.border,
  },
  strikeRowAtm: { backgroundColor: 'rgba(245,158,11,0.06)' },
  ltpText: { fontSize: 14, fontWeight: '700' },
  ivText: { fontSize: 10, color: Colors.textMuted, marginTop: 2 },
  oiText: { fontSize: 12, color: Colors.textSecondary, fontWeight: '500' },
  deltaText: { fontSize: 10, color: Colors.textMuted, marginTop: 2 },
  atmCol: {},
  strikeText: { fontSize: 14, fontWeight: '700', color: Colors.textPrimary },
  strikeTextAtm: { color: Colors.amber },
  atmLabel: { fontSize: 8, color: Colors.amber, fontWeight: '700', letterSpacing: 0.5, marginTop: 2 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  footer: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    paddingVertical: 6, borderTopWidth: 1, borderTopColor: Colors.border,
  },
  footerText: { fontSize: 11, color: Colors.textFaint },
  liveBadge: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: Colors.greenBg, borderRadius: Radius.full, paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: Colors.green + '40' },
  liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: Colors.green },
  liveBadgeText: { fontSize: 11, color: Colors.green, fontWeight: '700', letterSpacing: 0.5 },
});
