import React, { useCallback, useEffect, useState } from 'react';
import {
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { tradeCostAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, PrimaryButton, ScreenHeader, Tag } from '../components/ui';

type Tab = 'calculator' | 'summary' | 'history';

export default function TradeCostTrackerScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('calculator');

  const [symbol, setSymbol] = useState('NIFTY24FEB48000CE');
  const [tradeType, setTradeType] = useState<'BUY' | 'SELL'>('BUY');
  const [segment, setSegment] = useState<'FNO' | 'EQUITY'>('FNO');
  const [productType, setProductType] = useState<'OPTIONS' | 'FUTURES' | 'INTRADAY' | 'DELIVERY'>('OPTIONS');
  const [quantity, setQuantity] = useState('50');
  const [price, setPrice] = useState('100');
  const [calculating, setCalculating] = useState(false);
  const [costBreakdown, setCostBreakdown] = useState<any | null>(null);

  const [summary, setSummary] = useState<any | null>(null);
  const [history, setHistory] = useState<any[]>([]);

  const loadSummary = useCallback(async () => {
    try {
      const response = await tradeCostAPI.getSummary();
      setSummary(response.data || null);
    } catch {
      setSummary(null);
    }
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      const response = await tradeCostAPI.getHistory({ limit: 50 });
      setHistory(response.data?.costs || []);
    } catch {
      setHistory([]);
    }
  }, []);

  const bootstrap = useCallback(async () => {
    await Promise.all([loadSummary(), loadHistory()]);
    setLoading(false);
    setRefreshing(false);
  }, [loadHistory, loadSummary]);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const onRefresh = () => {
    setRefreshing(true);
    bootstrap();
  };

  const calculate = async () => {
    setCalculating(true);
    try {
      const response = await tradeCostAPI.calculate({
        symbol: symbol.trim().toUpperCase(),
        trade_type: tradeType,
        segment,
        product_type: productType,
        quantity: Number(quantity) || 0,
        price: Number(price) || 0,
      });
      setCostBreakdown(response.data || null);
      loadSummary();
      loadHistory();
    } catch {
      setCostBreakdown(null);
    }
    setCalculating(false);
  };

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScreenHeader
          title="Trade Costs"
          subtitle="Calculator, summary, and historical charge tracking"
          badge={<Tag label={`${history.length} RECORDS`} color={Colors.accent} bg={Colors.accentSoft} />}
          onBack={() => router.back()}
        />

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.tabRow}>
            {(['calculator', 'summary', 'history'] as Tab[]).map((tab) => (
              <TouchableOpacity key={tab} style={[styles.tabBtn, activeTab === tab && styles.tabBtnActive]} onPress={() => setActiveTab(tab)}>
                <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>{tab.toUpperCase()}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {activeTab === 'calculator' && (
            <GlassCard style={styles.card}>
              <Text style={styles.cardTitle}>Trade Details</Text>
              <TextInput style={styles.input} value={symbol} onChangeText={setSymbol} placeholder="Symbol" placeholderTextColor={Colors.textFaint} />

              <View style={styles.toggleRow}>
                {(['BUY', 'SELL'] as const).map((value) => (
                  <TouchableOpacity key={value} style={[styles.toggleBtn, tradeType === value && styles.toggleBtnActive]} onPress={() => setTradeType(value)}>
                    <Text style={[styles.toggleText, tradeType === value && styles.toggleTextActive]}>{value}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <View style={styles.toggleRow}>
                {(['FNO', 'EQUITY'] as const).map((value) => (
                  <TouchableOpacity key={value} style={[styles.toggleBtn, segment === value && styles.toggleBtnActive]} onPress={() => setSegment(value)}>
                    <Text style={[styles.toggleText, segment === value && styles.toggleTextActive]}>{value}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <View style={styles.toggleRowWrap}>
                {(['OPTIONS', 'FUTURES', 'INTRADAY', 'DELIVERY'] as const).map((value) => (
                  <TouchableOpacity key={value} style={[styles.toggleBtn, productType === value && styles.toggleBtnActive]} onPress={() => setProductType(value)}>
                    <Text style={[styles.toggleText, productType === value && styles.toggleTextActive]}>{value}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <View style={styles.row}>
                <TextInput style={styles.input} value={quantity} onChangeText={setQuantity} placeholder="Qty" keyboardType="numeric" placeholderTextColor={Colors.textFaint} />
                <TextInput style={styles.input} value={price} onChangeText={setPrice} placeholder="Price" keyboardType="numeric" placeholderTextColor={Colors.textFaint} />
              </View>

              <PrimaryButton title="Calculate Costs" onPress={calculate} loading={calculating} />

              {costBreakdown && (
                <View style={styles.breakdown}>
                  <Row label="Trade Value" value={costBreakdown.trade_value} />
                  <Row label="Brokerage" value={costBreakdown.brokerage} />
                  <Row label="STT/CTT" value={costBreakdown.stt_ctt} />
                  <Row label="Exchange Charge" value={costBreakdown.exchange_txn_charge} />
                  <Row label="GST" value={costBreakdown.gst} />
                  <Row label="Total Cost" value={costBreakdown.total_cost} highlight />
                </View>
              )}
            </GlassCard>
          )}

          {activeTab === 'summary' && (
            <GlassCard style={styles.card}>
              <Text style={styles.cardTitle}>Cost Summary</Text>
              {summary ? (
                <>
                  <Row label="Total Trades" value={summary.total_trades} plain />
                  <Row label="Total Costs" value={summary.total_costs} highlight />
                  <Row label="Brokerage" value={summary.total_brokerage} />
                  <Row label="STT" value={summary.total_stt} />
                  <Row label="GST" value={summary.total_gst} />
                  <Row label="Avg Cost / Trade" value={summary.avg_cost_per_trade} />
                </>
              ) : (
                <EmptyState icon="🧾" title="No Summary" subtitle="Trade costs summary is not available." />
              )}
            </GlassCard>
          )}

          {activeTab === 'history' && (
            <>
              {history.length === 0 ? (
                <EmptyState icon="📚" title="No History" subtitle="Calculated trades will appear here." />
              ) : (
                history.map((row: any, index: number) => (
                  <GlassCard key={`${row.id || row.intent_id || index}`} style={styles.historyCard}>
                    <View style={styles.historyTop}>
                      <Text style={styles.symbol}>{row.symbol || '-'}</Text>
                      <Text style={styles.tradeType}>{row.trade_type || '-'}</Text>
                    </View>
                    <View style={styles.historyBottom}>
                      <Text style={styles.meta}>Qty: {row.quantity || 0}</Text>
                      <Text style={styles.meta}>Price: ₹{Number(row.price || 0).toFixed(2)}</Text>
                      <Text style={styles.cost}>Cost: ₹{Number(row.total_cost || 0).toFixed(2)}</Text>
                    </View>
                  </GlassCard>
                ))
              )}
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

function Row({ label, value, highlight, plain }: { label: string; value: any; highlight?: boolean; plain?: boolean }) {
  return (
    <View style={styles.breakRow}>
      <Text style={styles.breakLabel}>{label}</Text>
      <Text style={[styles.breakValue, highlight && { color: Colors.accentLight, fontWeight: '700' }]}>
        {plain ? String(value ?? '-') : `₹${Number(value || 0).toFixed(2)}`}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safe: { flex: 1 },
  scroll: { padding: Spacing.lg, paddingBottom: 120 },
  tabRow: { flexDirection: 'row', marginBottom: Spacing.md, gap: 8 },
  tabBtn: { flex: 1, paddingVertical: 10, borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.bgGlass, alignItems: 'center' },
  tabBtnActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  tabText: { color: Colors.textSecondary, fontSize: 12, fontWeight: '700' },
  tabTextActive: { color: Colors.accentLight },
  card: { marginBottom: Spacing.md },
  cardTitle: { color: Colors.textPrimary, fontSize: 16, fontWeight: '700', marginBottom: Spacing.sm },
  input: {
    flex: 1,
    backgroundColor: Colors.bgGlassStrong,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    color: Colors.textPrimary,
    paddingHorizontal: 10,
    paddingVertical: 10,
    marginBottom: 8,
  },
  row: { flexDirection: 'row', gap: 8 },
  toggleRow: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  toggleRowWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 8 },
  toggleBtn: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: Radius.full, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.bgGlass },
  toggleBtnActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  toggleText: { color: Colors.textSecondary, fontSize: 12, fontWeight: '600' },
  toggleTextActive: { color: Colors.accentLight },
  breakdown: { marginTop: Spacing.md, borderTopWidth: 1, borderTopColor: Colors.border, paddingTop: Spacing.sm },
  breakRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  breakLabel: { color: Colors.textSecondary, fontSize: 13 },
  breakValue: { color: Colors.textPrimary, fontSize: 13 },
  historyCard: { marginBottom: 10 },
  historyTop: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  symbol: { color: Colors.textPrimary, fontSize: 15, fontWeight: '700' },
  tradeType: { color: Colors.accentLight, fontSize: 12, fontWeight: '700' },
  historyBottom: { flexDirection: 'row', justifyContent: 'space-between' },
  meta: { color: Colors.textSecondary, fontSize: 12 },
  cost: { color: Colors.amber, fontSize: 12, fontWeight: '700' },
});
