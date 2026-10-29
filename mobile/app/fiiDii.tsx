import React, { useCallback, useEffect, useState } from 'react';
import {
  RefreshControl, ScrollView, StatusBar, StyleSheet,
  Text, TouchableOpacity, View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import { useRouter } from 'expo-router';
import { fiiDiiAPI, nseAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, ProgressBar, ScreenHeader, Tag } from '../components/ui';

type Tab = 'cash' | 'fno' | 'heatmap' | 'history' | 'participant' | 'short' | '52week';

const cr = (v: number | null | undefined) => {
  if (v == null) return 'N/A';
  const abs = Math.abs(v);
  const s = abs >= 10000 ? `₹${(abs / 1000).toFixed(1)}K Cr` : `₹${abs.toFixed(0)} Cr`;
  return v < 0 ? `-${s}` : `+${s}`;
};

const netColor = (v: number | null | undefined) =>
  v == null ? Colors.textMuted : v >= 0 ? Colors.green : Colors.red;

const heatBg = (v: number | null | undefined, type: 'fii' | 'dii') => {
  if (v == null) return Colors.bgGlass;
  if (type === 'fii') {
    if (v > 5000) return 'rgba(16,185,129,0.8)';
    if (v > 2000) return 'rgba(16,185,129,0.5)';
    if (v > 0) return 'rgba(16,185,129,0.25)';
    if (v > -2000) return 'rgba(239,68,68,0.25)';
    if (v > -5000) return 'rgba(239,68,68,0.5)';
    return 'rgba(239,68,68,0.8)';
  }
  if (v > 5000) return 'rgba(59,130,246,0.8)';
  if (v > 2000) return 'rgba(59,130,246,0.5)';
  if (v > 0) return 'rgba(59,130,246,0.25)';
  if (v > -2000) return 'rgba(245,158,11,0.25)';
  if (v > -5000) return 'rgba(245,158,11,0.5)';
  return 'rgba(245,158,11,0.8)';
};

export default function FiiDiiScreen() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>('cash');
  const [summary, setSummary] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [extraData, setExtraData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [extraLoading, setExtraLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const [sumRes, histRes] = await Promise.allSettled([
        fiiDiiAPI.getSummary(),
        fiiDiiAPI.getHistory(60),
      ]);
      if (sumRes.status === 'fulfilled') setSummary(sumRes.value.data);
      if (histRes.status === 'fulfilled') {
        const records = histRes.value.data?.records || histRes.value.data || [];
        setHistory(Array.isArray(records) ? [...records].reverse() : []);
      }
    } catch {}
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const loadExtra = useCallback(async (t: Tab) => {
    if (extraData[t]) return;
    setExtraLoading(true);
    try {
      let data: any;
      if (t === 'participant') data = (await nseAPI.getParticipantOI()).data;
      else if (t === 'short') data = (await nseAPI.getShortSelling()).data;
      else if (t === '52week') data = (await nseAPI.get52Week()).data;
      if (data) setExtraData(prev => ({ ...prev, [t]: data }));
    } catch {}
    setExtraLoading(false);
  }, [extraData]);

  const switchTab = (t: Tab) => {
    Haptics.selectionAsync();
    setTab(t);
    loadExtra(t);
  };

  const onRefresh = () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    load();
  };

  if (loading) return <View style={s.root}><LoadingSpinner /></View>;

  const fiiUp = summary?.fii_direction === 'BUY';
  const diiUp = summary?.dii_direction === 'BUY';
  const sentScore = summary?.sentiment_score;

  const TABS: { id: Tab; label: string }[] = [
    { id: 'cash', label: 'Cash' },
    { id: 'fno', label: 'F&O' },
    { id: 'heatmap', label: 'Heatmap' },
    { id: 'history', label: 'History' },
    { id: 'participant', label: 'Part. OI' },
    { id: 'short', label: 'Short' },
    { id: '52week', label: '52W' },
  ];

  return (
    <View style={s.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={s.flex}>
        <ScreenHeader
          title="FII / DII"
          subtitle={summary ? `${summary.latest_date} · Institutional flows` : 'Institutional money flows'}
          badge={
            summary ? (
              <Tag
                label={fiiUp ? 'FII BUY' : 'FII SELL'}
                color={fiiUp ? Colors.green : Colors.red}
                bg={fiiUp ? Colors.greenBg : Colors.redBg}
              />
            ) : undefined
          }
          onBack={() => router.back()}
        />

        {/* Tab bar */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.tabScroll} contentContainerStyle={s.tabContent}>
          {TABS.map(({ id, label }) => (
            <TouchableOpacity
              key={id}
              style={[s.tabBtn, tab === id && s.tabBtnActive]}
              onPress={() => switchTab(id)}
              activeOpacity={0.8}
            >
              <Text style={[s.tabText, tab === id && s.tabTextActive]}>{label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        <ScrollView
          contentContainerStyle={s.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          {!summary ? (
            <EmptyState icon="📊" title="No FII/DII Data" subtitle="Pull to refresh or check backend connection." />
          ) : (
            <>
              {/* ── Cash Tab ── */}
              {tab === 'cash' && (
                <>
                  {/* Hero cards */}
                  <GlassCard style={[s.heroCard, { borderColor: fiiUp ? Colors.green + '60' : Colors.red + '60' }]}>
                    <View style={s.heroRow}>
                      <Text style={s.heroLabel}>FII / FPI Net</Text>
                      <Tag label={fiiUp ? 'NET BUYER' : 'NET SELLER'} color={fiiUp ? Colors.green : Colors.red} bg={fiiUp ? Colors.greenBg : Colors.redBg} />
                    </View>
                    <Text style={[s.heroValue, { color: netColor(summary.fii_net) }]}>{cr(summary.fii_net)}</Text>
                    <View style={s.heroMeta}>
                      <Text style={[s.heroMetaText, { color: Colors.green }]}>Buy: {cr(summary.fii_buy)}</Text>
                      <Text style={[s.heroMetaText, { color: Colors.red }]}>Sell: {cr(-summary.fii_sell)}</Text>
                    </View>
                    <Text style={s.streakText}>
                      Streak: {Math.abs(summary.fii_streak_days || 0)}d {fiiUp ? '▲' : '▼'}
                      {'  '}20d avg: {cr(summary.avg_fii_20d)}
                    </Text>
                  </GlassCard>

                  <GlassCard style={[s.heroCard, { borderColor: diiUp ? '#3B82F6' + '60' : Colors.amber + '60' }]}>
                    <View style={s.heroRow}>
                      <Text style={s.heroLabel}>DII Net</Text>
                      <Tag label={diiUp ? 'NET BUYER' : 'NET SELLER'} color={diiUp ? '#60A5FA' : Colors.amber} bg={diiUp ? 'rgba(59,130,246,0.1)' : Colors.amberBg} />
                    </View>
                    <Text style={[s.heroValue, { color: diiUp ? '#60A5FA' : Colors.amber }]}>{cr(summary.dii_net)}</Text>
                    <View style={s.heroMeta}>
                      <Text style={[s.heroMetaText, { color: '#60A5FA' }]}>Buy: {cr(summary.dii_buy)}</Text>
                      <Text style={[s.heroMetaText, { color: Colors.amber }]}>Sell: {cr(-summary.dii_sell)}</Text>
                    </View>
                    <Text style={s.streakText}>
                      Streak: {Math.abs(summary.dii_streak_days || 0)}d {diiUp ? '▲' : '▼'}
                      {'  '}20d avg: {cr(summary.avg_dii_20d)}
                    </Text>
                  </GlassCard>

                  {/* Flow strength */}
                  <GlassCard style={s.card}>
                    <Text style={s.cardTitle}>Flow Strength Meter</Text>
                    <ProgressBar value={summary.flow_strength_fii_pct || 0} color={fiiUp ? Colors.green : Colors.red} height={8} style={{ marginVertical: 8 }} />
                    <View style={s.row}>
                      <Text style={[s.meta, { color: fiiUp ? Colors.green : Colors.red }]}>FII {summary.flow_strength_fii_pct || 0}%</Text>
                      <Text style={[s.meta, { color: diiUp ? '#60A5FA' : Colors.amber }]}>DII {summary.flow_strength_dii_pct || 0}%</Text>
                    </View>
                  </GlassCard>

                  {/* MTD / YTD */}
                  <View style={s.statsRow}>
                    {[
                      { label: 'MTD FII', val: summary.mtd_fii, color: netColor(summary.mtd_fii) },
                      { label: 'MTD DII', val: summary.mtd_dii, color: (summary.mtd_dii || 0) >= 0 ? '#60A5FA' : Colors.amber },
                      { label: 'YTD FII', val: summary.ytd_fii, color: netColor(summary.ytd_fii) },
                      { label: 'YTD DII', val: summary.ytd_dii, color: (summary.ytd_dii || 0) >= 0 ? '#60A5FA' : Colors.amber },
                    ].map(({ label, val, color }) => (
                      <GlassCard key={label} style={s.miniCard}>
                        <Text style={s.miniLabel}>{label}</Text>
                        <Text style={[s.miniValue, { color }]}>{cr(val)}</Text>
                      </GlassCard>
                    ))}
                  </View>

                  {/* Sentiment */}
                  {sentScore != null && (
                    <GlassCard style={s.card}>
                      <View style={s.row}>
                        <Text style={s.cardTitle}>Sentiment Score</Text>
                        <Text style={[s.heroValue, { fontSize: 20, color: sentScore >= 60 ? Colors.green : sentScore >= 40 ? Colors.amber : Colors.red }]}>
                          {sentScore}/100
                        </Text>
                      </View>
                      <ProgressBar
                        value={sentScore}
                        color={sentScore >= 60 ? Colors.green : sentScore >= 40 ? Colors.amber : Colors.red}
                        height={6}
                        style={{ marginTop: 8 }}
                      />
                      {summary.pcr != null && (
                        <Text style={[s.meta, { marginTop: 6 }]}>PCR: <Text style={{ color: Colors.textPrimary }}>{Number(summary.pcr).toFixed(2)}</Text></Text>
                      )}
                    </GlassCard>
                  )}
                </>
              )}

              {/* ── F&O Tab ── */}
              {tab === 'fno' && (
                <>
                  {summary.fno?.sentiment && (
                    <Tag
                      label={`F&O Sentiment: ${summary.fno.sentiment}`}
                      color={summary.fno.sentiment === 'Bullish' ? Colors.green : summary.fno.sentiment === 'Bearish' ? Colors.red : Colors.textMuted}
                      bg={summary.fno.sentiment === 'Bullish' ? Colors.greenBg : summary.fno.sentiment === 'Bearish' ? Colors.redBg : Colors.bgGlass}
                    />
                  )}
                  {[
                    { label: 'FII Index Futures', long: summary.fno?.fii_idx_fut_long, short: summary.fno?.fii_idx_fut_short, net: summary.fno?.fii_idx_fut_net },
                    { label: 'DII Index Futures', long: summary.fno?.dii_idx_fut_long, short: summary.fno?.dii_idx_fut_short, net: summary.fno?.dii_idx_fut_net },
                    { label: 'FII Stock Futures', long: summary.fno?.fii_stk_fut_long, short: summary.fno?.fii_stk_fut_short, net: summary.fno?.fii_stk_fut_net },
                    { label: 'FII Index Calls', long: summary.fno?.fii_idx_call_long, short: summary.fno?.fii_idx_call_short, net: summary.fno?.fii_idx_call_net },
                    { label: 'FII Index Puts', long: summary.fno?.fii_idx_put_long, short: summary.fno?.fii_idx_put_short, net: summary.fno?.fii_idx_put_net },
                  ].map(({ label, long, short, net }) => {
                    const total = (long ?? 0) + (short ?? 0);
                    const longPct = total > 0 ? ((long ?? 0) / total) * 100 : 50;
                    return (
                      <GlassCard key={label} style={s.card}>
                        <View style={s.row}>
                          <Text style={s.cardTitle}>{label}</Text>
                          <Text style={[s.meta, { color: netColor(net), fontWeight: '700' }]}>{net != null ? (net >= 0 ? '+' : '') + net.toLocaleString('en-IN') : 'N/A'}</Text>
                        </View>
                        <View style={s.fnoBar}>
                          <View style={[s.fnoBarFill, { width: `${longPct}%` as any, backgroundColor: Colors.green }]} />
                          <View style={[s.fnoBarFill, { flex: 1, backgroundColor: Colors.red }]} />
                        </View>
                        <View style={s.row}>
                          <Text style={[s.meta, { color: Colors.green }]}>L: {(long ?? 0).toLocaleString('en-IN')}</Text>
                          <Text style={[s.meta, { color: Colors.red }]}>S: {(short ?? 0).toLocaleString('en-IN')}</Text>
                        </View>
                      </GlassCard>
                    );
                  })}
                </>
              )}

              {/* ── Heatmap Tab ── */}
              {tab === 'heatmap' && summary.heatmap && (
                <>
                  {(['fii', 'dii'] as const).map((type) => (
                    <GlassCard key={type} style={s.card}>
                      <Text style={s.cardTitle}>{type.toUpperCase()} 45-Day Heatmap</Text>
                      <View style={s.heatGrid}>
                        {summary.heatmap.map((d: any, i: number) => (
                          <View
                            key={i}
                            style={[s.heatCell, { backgroundColor: heatBg(type === 'fii' ? d.fii_net : d.dii_net, type) }]}
                          />
                        ))}
                      </View>
                      <View style={s.heatLegend}>
                        <View style={[s.heatDot, { backgroundColor: type === 'fii' ? 'rgba(16,185,129,0.8)' : 'rgba(59,130,246,0.8)' }]} />
                        <Text style={s.meta}>Strong Buy</Text>
                        <View style={[s.heatDot, { backgroundColor: type === 'fii' ? 'rgba(239,68,68,0.8)' : 'rgba(245,158,11,0.8)', marginLeft: 12 }]} />
                        <Text style={s.meta}>Strong Sell</Text>
                      </View>
                    </GlassCard>
                  ))}
                </>
              )}

              {/* ── History Tab ── */}
              {tab === 'history' && (
                <GlassCard style={s.card}>
                  <Text style={s.cardTitle}>60-Day History</Text>
                  {history.length === 0 ? (
                    <EmptyState icon="📋" title="No History" subtitle="History data unavailable." />
                  ) : (
                    history.slice(0, 30).map((r: any, i: number) => (
                      <View key={i} style={s.histRow}>
                        <Text style={[s.meta, { width: 72 }]}>{r.date}</Text>
                        <Text style={[s.meta, { color: netColor(r.fii_net), flex: 1, textAlign: 'right' }]}>{cr(r.fii_net)}</Text>
                        <Text style={[s.meta, { color: (r.dii_net || 0) >= 0 ? '#60A5FA' : Colors.amber, flex: 1, textAlign: 'right' }]}>{cr(r.dii_net)}</Text>
                        {r.sentiment_score != null && (
                          <Text style={[s.meta, { color: r.sentiment_score >= 60 ? Colors.green : r.sentiment_score >= 40 ? Colors.amber : Colors.red, width: 32, textAlign: 'right' }]}>
                            {r.sentiment_score}
                          </Text>
                        )}
                      </View>
                    ))
                  )}
                </GlassCard>
              )}

              {/* ── Participant OI Tab ── */}
              {tab === 'participant' && (
                <GlassCard style={s.card}>
                  <Text style={s.cardTitle}>Participant Open Interest</Text>
                  {extraLoading ? (
                    <LoadingSpinner />
                  ) : !extraData.participant ? (
                    <EmptyState icon="📊" title="No Data" subtitle="Participant OI data unavailable." />
                  ) : (
                    (['index_futures', 'stock_futures', 'index_options'] as const).map((key) => {
                      const rows: any[] = extraData.participant[key] || [];
                      if (!rows.length) return null;
                      return (
                        <View key={key} style={{ marginBottom: 16 }}>
                          <Text style={[s.meta, { fontWeight: '700', marginBottom: 8, textTransform: 'capitalize' }]}>{key.replace('_', ' ')}</Text>
                          {rows.map((r: any, i: number) => (
                            <View key={i} style={s.histRow}>
                              <Text style={[s.meta, { flex: 1 }]}>{r.client_type}</Text>
                              <Text style={[s.meta, { color: Colors.green }]}>L: {Number(r.oi_long || 0).toLocaleString('en-IN')}</Text>
                              <Text style={[s.meta, { color: Colors.red, marginLeft: 8 }]}>S: {Number(r.oi_short || 0).toLocaleString('en-IN')}</Text>
                              <Text style={[s.meta, { color: netColor(r.oi_net), marginLeft: 8 }]}>Net: {Number(r.oi_net || 0).toLocaleString('en-IN')}</Text>
                            </View>
                          ))}
                        </View>
                      );
                    })
                  )}
                </GlassCard>
              )}

              {/* ── Short Selling Tab ── */}
              {tab === 'short' && (
                <GlassCard style={s.card}>
                  <Text style={s.cardTitle}>Short Selling</Text>
                  {extraLoading ? (
                    <LoadingSpinner />
                  ) : !extraData.short?.data?.length ? (
                    <EmptyState icon="📉" title="No Short Data" subtitle="No short selling data available today." />
                  ) : (
                    extraData.short.data.map((r: any, i: number) => (
                      <View key={i} style={s.histRow}>
                        <Text style={[s.meta, { fontWeight: '700', color: Colors.textPrimary, width: 80 }]}>{r.symbol}</Text>
                        <Text style={[s.meta, { flex: 1 }]}>{r.company}</Text>
                        <Text style={[s.meta, { color: Colors.red }]}>{Number(r.quantity || 0).toLocaleString('en-IN')}</Text>
                      </View>
                    ))
                  )}
                </GlassCard>
              )}

              {/* ── 52-Week Tab ── */}
              {tab === '52week' && (
                <>
                  {extraLoading ? (
                    <LoadingSpinner />
                  ) : (
                    (['highs', 'lows'] as const).map((bucket) => {
                      const rows: any[] = extraData['52week']?.[bucket] || [];
                      return (
                        <GlassCard key={bucket} style={s.card}>
                          <Text style={[s.cardTitle, { color: bucket === 'highs' ? Colors.green : Colors.red }]}>
                            {bucket === 'highs' ? '🚀 52-Week Highs' : '📉 52-Week Lows'} ({rows.length})
                          </Text>
                          {rows.length === 0 ? (
                            <Text style={s.meta}>No data available</Text>
                          ) : (
                            rows.slice(0, 20).map((r: any, i: number) => (
                              <View key={i} style={s.histRow}>
                                <Text style={[s.meta, { fontWeight: '700', color: Colors.textPrimary, width: 80 }]}>{r.symbol}</Text>
                                <Text style={[s.meta, { flex: 1 }]}>₹{Number(r.ltp || 0).toLocaleString('en-IN')}</Text>
                                <Text style={[s.meta, { color: (r.change_pct || 0) >= 0 ? Colors.green : Colors.red }]}>
                                  {(r.change_pct || 0) >= 0 ? '+' : ''}{Number(r.change_pct || 0).toFixed(2)}%
                                </Text>
                              </View>
                            ))
                          )}
                        </GlassCard>
                      );
                    })
                  )}
                </>
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
  tabScroll: { borderBottomWidth: 1, borderBottomColor: Colors.border },
  tabContent: { paddingHorizontal: Spacing.md, paddingVertical: 8, gap: 6 },
  tabBtn: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: Radius.full, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.bgGlass },
  tabBtnActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  tabText: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary },
  tabTextActive: { color: Colors.accentLight },
  heroCard: { marginBottom: 12, padding: Spacing.md, borderWidth: 1, borderRadius: Radius.lg, backgroundColor: Colors.bgGlass },
  heroRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  heroLabel: { fontSize: 13, fontWeight: '600', color: Colors.textSecondary },
  heroValue: { fontSize: 28, fontWeight: '700', color: Colors.textPrimary },
  heroMeta: { flexDirection: 'row', gap: 16, marginTop: 6 },
  heroMetaText: { fontSize: 12 },
  streakText: { fontSize: 11, color: Colors.textMuted, marginTop: 6 },
  card: { marginBottom: 12 },
  cardTitle: { fontSize: 14, fontWeight: '700', color: Colors.textPrimary, marginBottom: 10 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  meta: { fontSize: 12, color: Colors.textSecondary },
  statsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  miniCard: { width: '47%', padding: Spacing.sm },
  miniLabel: { fontSize: 10, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.5 },
  miniValue: { fontSize: 14, fontWeight: '700', marginTop: 4 },
  fnoBar: { height: 6, borderRadius: Radius.full, overflow: 'hidden', flexDirection: 'row', marginVertical: 8, backgroundColor: Colors.bgGlassStrong },
  fnoBarFill: { height: 6 },
  heatGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 3, marginVertical: 8 },
  heatCell: { width: 20, height: 20, borderRadius: 3 },
  heatLegend: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 },
  heatDot: { width: 10, height: 10, borderRadius: 2 },
  histRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: Colors.border },
});
