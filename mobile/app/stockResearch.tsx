import React, { useCallback, useEffect, useState } from 'react';
import {
  RefreshControl, ScrollView, StatusBar, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import { useRouter } from 'expo-router';
import { fundamentalsAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, PrimaryButton, ProgressBar, ScreenHeader, Tag } from '../components/ui';

const QUICK_SYMBOLS = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'WIPRO', 'NIFTY'];

type Tab = 'profile' | 'financials' | 'peers';

function MetricRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={s.metricRow}>
      <Text style={s.metricLabel}>{label}</Text>
      <Text style={[s.metricValue, color ? { color } : {}]}>{value}</Text>
    </View>
  );
}

export default function StockResearchScreen() {
  const router = useRouter();
  const [symbol, setSymbol] = useState('RELIANCE');
  const [inputSymbol, setInputSymbol] = useState('RELIANCE');
  const [tab, setTab] = useState<Tab>('profile');
  const [profile, setProfile] = useState<any>(null);
  const [financials, setFinancials] = useState<any>(null);
  const [peers, setPeers] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (sym: string) => {
    setLoading(true);
    setError(null);
    try {
      const [profRes, finRes, peerRes] = await Promise.allSettled([
        fundamentalsAPI.getProfile(sym),
        fundamentalsAPI.getFinancials(sym),
        fundamentalsAPI.getPeers(sym),
      ]);
      if (profRes.status === 'fulfilled') setProfile(profRes.value.data);
      else setProfile(null);
      if (finRes.status === 'fulfilled') setFinancials(finRes.value.data);
      else setFinancials(null);
      if (peerRes.status === 'fulfilled') {
        const d = peerRes.value.data;
        setPeers(Array.isArray(d) ? d : d?.peers || []);
      } else {
        setPeers([]);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load research data');
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => { load(symbol); }, [symbol]);

  const search = () => {
    const sym = inputSymbol.trim().toUpperCase();
    if (!sym) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setSymbol(sym);
  };

  const onRefresh = () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    load(symbol);
  };

  const TABS: { id: Tab; label: string }[] = [
    { id: 'profile', label: 'Profile' },
    { id: 'financials', label: 'Financials' },
    { id: 'peers', label: 'Peers' },
  ];

  const changeColor = (v: number | null | undefined) =>
    v == null ? Colors.textPrimary : v >= 0 ? Colors.green : Colors.red;

  return (
    <View style={s.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={s.flex}>
        <ScreenHeader
          title="Stock Research"
          subtitle="Fundamentals, financials & peer comparison"
          badge={<Tag label={symbol} color={Colors.accent} bg={Colors.accentSoft} />}
          onBack={() => router.back()}
        />

        {/* Search bar */}
        <View style={s.searchRow}>
          <TextInput
            style={s.searchInput}
            value={inputSymbol}
            onChangeText={setInputSymbol}
            placeholder="Enter symbol (e.g. RELIANCE)"
            placeholderTextColor={Colors.textMuted}
            autoCapitalize="characters"
            returnKeyType="search"
            onSubmitEditing={search}
          />
          <TouchableOpacity style={s.searchBtn} onPress={search} activeOpacity={0.8}>
            <Text style={s.searchBtnText}>Search</Text>
          </TouchableOpacity>
        </View>

        {/* Quick symbols */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.quickRow} contentContainerStyle={{ gap: 6, paddingHorizontal: Spacing.md }}>
          {QUICK_SYMBOLS.map((sym) => (
            <TouchableOpacity
              key={sym}
              style={[s.quickChip, symbol === sym && s.quickChipActive]}
              onPress={() => { setInputSymbol(sym); setSymbol(sym); Haptics.selectionAsync(); }}
              activeOpacity={0.8}
            >
              <Text style={[s.quickChipText, symbol === sym && s.quickChipTextActive]}>{sym}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Tab bar */}
        <View style={s.tabRow}>
          {TABS.map(({ id, label }) => (
            <TouchableOpacity
              key={id}
              style={[s.tabBtn, tab === id && s.tabBtnActive]}
              onPress={() => { setTab(id); Haptics.selectionAsync(); }}
              activeOpacity={0.8}
            >
              <Text style={[s.tabText, tab === id && s.tabTextActive]}>{label}</Text>
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
          ) : error ? (
            <GlassCard style={s.errorCard}>
              <Text style={s.errorText}>⚠️ {error}</Text>
              <PrimaryButton title="Retry" onPress={() => load(symbol)} variant="ghost" style={{ marginTop: 12 }} />
            </GlassCard>
          ) : (
            <>
              {/* ── Profile Tab ── */}
              {tab === 'profile' && (
                <>
                  {!profile ? (
                    <EmptyState icon="🔍" title="No Profile Data" subtitle="Fundamentals data unavailable for this symbol." />
                  ) : (
                    <>
                      <GlassCard style={s.card}>
                        <View style={s.profileHeader}>
                          <View style={{ flex: 1 }}>
                            <Text style={s.companyName}>{profile.company_name || symbol}</Text>
                            <Text style={s.sector}>{profile.sector || ''}{profile.industry ? ` · ${profile.industry}` : ''}</Text>
                          </View>
                          {profile.change_pct != null && (
                            <Tag
                              label={`${profile.change_pct >= 0 ? '+' : ''}${Number(profile.change_pct).toFixed(2)}%`}
                              color={changeColor(profile.change_pct)}
                              bg={profile.change_pct >= 0 ? Colors.greenBg : Colors.redBg}
                            />
                          )}
                        </View>
                        {profile.ltp != null && (
                          <Text style={[s.ltp, { color: changeColor(profile.change_pct) }]}>
                            ₹{Number(profile.ltp).toLocaleString('en-IN')}
                          </Text>
                        )}
                      </GlassCard>

                      <GlassCard style={s.card}>
                        <Text style={s.cardTitle}>Key Metrics</Text>
                        {[
                          ['Market Cap', profile.market_cap ? `₹${(Number(profile.market_cap) / 1e7).toFixed(0)} Cr` : '—'],
                          ['P/E Ratio', profile.pe_ratio ? Number(profile.pe_ratio).toFixed(1) : '—'],
                          ['P/B Ratio', profile.pb_ratio ? Number(profile.pb_ratio).toFixed(2) : '—'],
                          ['EPS', profile.eps ? `₹${Number(profile.eps).toFixed(2)}` : '—'],
                          ['Dividend Yield', profile.dividend_yield ? `${Number(profile.dividend_yield).toFixed(2)}%` : '—'],
                          ['52W High', profile.high_52w ? `₹${Number(profile.high_52w).toLocaleString('en-IN')}` : '—'],
                          ['52W Low', profile.low_52w ? `₹${Number(profile.low_52w).toLocaleString('en-IN')}` : '—'],
                          ['Beta', profile.beta ? Number(profile.beta).toFixed(2) : '—'],
                          ['Book Value', profile.book_value ? `₹${Number(profile.book_value).toFixed(2)}` : '—'],
                          ['ROE', profile.roe ? `${Number(profile.roe).toFixed(1)}%` : '—'],
                          ['ROCE', profile.roce ? `${Number(profile.roce).toFixed(1)}%` : '—'],
                          ['Debt/Equity', profile.debt_equity ? Number(profile.debt_equity).toFixed(2) : '—'],
                        ].map(([label, value]) => (
                          <MetricRow key={label} label={label} value={value} />
                        ))}
                      </GlassCard>

                      {profile.description && (
                        <GlassCard style={s.card}>
                          <Text style={s.cardTitle}>About</Text>
                          <Text style={s.description}>{profile.description}</Text>
                        </GlassCard>
                      )}
                    </>
                  )}
                </>
              )}

              {/* ── Financials Tab ── */}
              {tab === 'financials' && (
                <>
                  {!financials ? (
                    <EmptyState icon="📈" title="No Financials" subtitle="Financial data unavailable for this symbol." />
                  ) : (
                    <>
                      {financials.quarterly && financials.quarterly.length > 0 && (
                        <GlassCard style={s.card}>
                          <Text style={s.cardTitle}>Quarterly Results</Text>
                          {financials.quarterly.slice(0, 6).map((q: any, i: number) => (
                            <View key={i} style={s.quarterRow}>
                              <Text style={[s.metricLabel, { width: 80 }]}>{q.period || q.quarter || `Q${i + 1}`}</Text>
                              <View style={{ flex: 1 }}>
                                {q.revenue != null && (
                                  <Text style={s.metricValue}>Rev: ₹{(Number(q.revenue) / 1e7).toFixed(0)} Cr</Text>
                                )}
                                {q.net_profit != null && (
                                  <Text style={[s.metricValue, { color: changeColor(q.net_profit) }]}>
                                    PAT: ₹{(Number(q.net_profit) / 1e7).toFixed(0)} Cr
                                  </Text>
                                )}
                              </View>
                              {q.yoy_growth != null && (
                                <Text style={[s.metricValue, { color: changeColor(q.yoy_growth) }]}>
                                  {q.yoy_growth >= 0 ? '+' : ''}{Number(q.yoy_growth).toFixed(1)}%
                                </Text>
                              )}
                            </View>
                          ))}
                        </GlassCard>
                      )}

                      {financials.annual && financials.annual.length > 0 && (
                        <GlassCard style={s.card}>
                          <Text style={s.cardTitle}>Annual Financials</Text>
                          {financials.annual.slice(0, 5).map((a: any, i: number) => (
                            <View key={i} style={s.quarterRow}>
                              <Text style={[s.metricLabel, { width: 60 }]}>{a.year || `FY${i + 1}`}</Text>
                              <View style={{ flex: 1 }}>
                                {a.revenue != null && <Text style={s.metricValue}>Rev: ₹{(Number(a.revenue) / 1e7).toFixed(0)} Cr</Text>}
                                {a.net_profit != null && (
                                  <Text style={[s.metricValue, { color: changeColor(a.net_profit) }]}>
                                    PAT: ₹{(Number(a.net_profit) / 1e7).toFixed(0)} Cr
                                  </Text>
                                )}
                              </View>
                              {a.eps != null && <Text style={s.metricValue}>EPS: ₹{Number(a.eps).toFixed(2)}</Text>}
                            </View>
                          ))}
                        </GlassCard>
                      )}

                      {!financials.quarterly?.length && !financials.annual?.length && (
                        <EmptyState icon="📊" title="No Financial Data" subtitle="Detailed financials not available." />
                      )}
                    </>
                  )}
                </>
              )}

              {/* ── Peers Tab ── */}
              {tab === 'peers' && (
                <GlassCard style={s.card}>
                  <Text style={s.cardTitle}>Peer Comparison</Text>
                  {peers.length === 0 ? (
                    <EmptyState icon="👥" title="No Peers" subtitle="Peer comparison data unavailable." />
                  ) : (
                    <>
                      <View style={s.peerHeader}>
                        <Text style={[s.metricLabel, { flex: 1 }]}>Symbol</Text>
                        <Text style={[s.metricLabel, { width: 70, textAlign: 'right' }]}>LTP</Text>
                        <Text style={[s.metricLabel, { width: 50, textAlign: 'right' }]}>P/E</Text>
                        <Text style={[s.metricLabel, { width: 60, textAlign: 'right' }]}>Chg%</Text>
                      </View>
                      {peers.map((p: any, i: number) => (
                        <View key={i} style={s.peerRow}>
                          <Text style={[s.metricValue, { flex: 1, color: Colors.textPrimary }]}>{p.symbol}</Text>
                          <Text style={[s.metricValue, { width: 70, textAlign: 'right' }]}>
                            {p.ltp ? `₹${Number(p.ltp).toLocaleString('en-IN')}` : '—'}
                          </Text>
                          <Text style={[s.metricValue, { width: 50, textAlign: 'right' }]}>
                            {p.pe_ratio ? Number(p.pe_ratio).toFixed(1) : '—'}
                          </Text>
                          <Text style={[s.metricValue, { width: 60, textAlign: 'right', color: changeColor(p.change_pct) }]}>
                            {p.change_pct != null ? `${p.change_pct >= 0 ? '+' : ''}${Number(p.change_pct).toFixed(2)}%` : '—'}
                          </Text>
                        </View>
                      ))}
                    </>
                  )}
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
  searchRow: { flexDirection: 'row', paddingHorizontal: Spacing.md, paddingVertical: 8, gap: 8 },
  searchInput: {
    flex: 1, borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass, color: Colors.textPrimary,
    paddingHorizontal: 12, paddingVertical: 10, fontSize: 14,
  },
  searchBtn: { backgroundColor: Colors.accent, borderRadius: Radius.md, paddingHorizontal: 16, justifyContent: 'center' },
  searchBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  quickRow: { paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: Colors.border },
  quickChip: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: Radius.full, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.bgGlass },
  quickChipActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  quickChipText: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary },
  quickChipTextActive: { color: Colors.accentLight },
  tabRow: { flexDirection: 'row', marginHorizontal: Spacing.md, marginVertical: 8, borderRadius: Radius.md, backgroundColor: Colors.bgGlass, borderWidth: 1, borderColor: Colors.border, overflow: 'hidden' },
  tabBtn: { flex: 1, paddingVertical: 9, alignItems: 'center' },
  tabBtnActive: { backgroundColor: Colors.accentSoft },
  tabText: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5 },
  tabTextActive: { color: Colors.accentLight },
  card: { marginBottom: 12 },
  cardTitle: { fontSize: 14, fontWeight: '700', color: Colors.textPrimary, marginBottom: 10 },
  profileHeader: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8 },
  companyName: { fontSize: 18, fontWeight: '700', color: Colors.textPrimary },
  sector: { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  ltp: { fontSize: 28, fontWeight: '700', marginTop: 4 },
  metricRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: Colors.border },
  metricLabel: { fontSize: 12, color: Colors.textSecondary },
  metricValue: { fontSize: 12, fontWeight: '600', color: Colors.textPrimary },
  description: { fontSize: 13, color: Colors.textSecondary, lineHeight: 20 },
  quarterRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: Colors.border },
  peerHeader: { flexDirection: 'row', paddingBottom: 6, borderBottomWidth: 1, borderBottomColor: Colors.border, marginBottom: 4 },
  peerRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: Colors.border },
  errorCard: { borderColor: Colors.red, backgroundColor: Colors.redBg },
  errorText: { fontSize: 13, color: Colors.red, fontWeight: '600' },
});
