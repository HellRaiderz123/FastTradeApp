import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
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
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { useRouter } from 'expo-router';
import { screenerAPI, watchlistAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, PrimaryButton, ScreenHeader, Tag } from '../components/ui';

type ScreenerResult = {
  symbol: string;
  ltp: number;
  change_percent: number;
  volume: number;
  rsi: number;
  sector?: string;
  market_cap?: number;
};

const DEFAULT_FILTERS = {
  sort_by: 'change_percent',
  sort_order: 'desc',
};

export default function ScreenerScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [results, setResults] = useState<ScreenerResult[]>([]);
  const [presets, setPresets] = useState<any[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string>('');

  const addToWatchlist = useCallback(async (symbol: string) => {
    try {
      const res = await watchlistAPI.list();
      const lists: any[] = res.data?.watchlists || res.data || [];
      if (lists.length === 0) {
        Alert.alert('No Watchlists', 'Create a watchlist first from the Watchlists screen.');
        return;
      }
      Alert.alert(
        `Add ${symbol}`,
        'Choose a watchlist:',
        [
          ...lists.map((wl: any) => ({
            text: wl.name,
            onPress: async () => {
              try {
                await watchlistAPI.addSymbol(wl.id, symbol);
                Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
              } catch (err: any) {
                Alert.alert('Error', err?.response?.data?.detail || 'Add failed');
              }
            },
          })),
          { text: 'Cancel', style: 'cancel' },
        ]
      );
    } catch {
      Alert.alert('Error', 'Could not load watchlists.');
    }
  }, []);

  const [minPrice, setMinPrice] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [minChange, setMinChange] = useState('');
  const [maxChange, setMaxChange] = useState('');
  const [minVolume, setMinVolume] = useState('');
  const [rsiMin, setRsiMin] = useState('');
  const [rsiMax, setRsiMax] = useState('');

  const loadPresets = useCallback(async () => {
    try {
      const response = await screenerAPI.getPresets();
      setPresets(response.data?.presets || []);
    } catch {
      setPresets([]);
    }
  }, []);

  const runScreener = useCallback(async (overrideFilters?: any) => {
    setRunning(true);
    try {
      const parsedFilters = {
        ...DEFAULT_FILTERS,
        ...(minPrice ? { min_price: Number(minPrice) } : {}),
        ...(maxPrice ? { max_price: Number(maxPrice) } : {}),
        ...(minChange ? { min_change_percent: Number(minChange) } : {}),
        ...(maxChange ? { max_change_percent: Number(maxChange) } : {}),
        ...(minVolume ? { min_volume: Number(minVolume) } : {}),
        ...(rsiMin ? { rsi_min: Number(rsiMin) } : {}),
        ...(rsiMax ? { rsi_max: Number(rsiMax) } : {}),
        ...(overrideFilters || {}),
      };

      const response = await screenerAPI.filterStocks(parsedFilters);
      setResults(response.data?.results || []);
    } catch {
      setResults([]);
    }
    setRunning(false);
    setLoading(false);
    setRefreshing(false);
  }, [maxChange, maxPrice, minChange, minPrice, minVolume, rsiMax, rsiMin]);

  useEffect(() => {
    loadPresets();
    runScreener();
  }, [loadPresets, runScreener]);

  const onRefresh = () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    runScreener();
  };

  const applyPreset = (preset: any) => {
    setSelectedPreset(preset.id || preset.name || '');
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    runScreener(preset.filters || {});
  };

  const resetFilters = () => {
    setMinPrice('');
    setMaxPrice('');
    setMinChange('');
    setMaxChange('');
    setMinVolume('');
    setRsiMin('');
    setRsiMax('');
    setSelectedPreset('');
    runScreener(DEFAULT_FILTERS);
  };

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScreenHeader
          title="Stock Screener"
          subtitle="Filter NIFTY stocks with quick technical criteria"
          badge={<Tag label={`${results.length} MATCHES`} color={Colors.accent} bg={Colors.accentSoft} />}
          onBack={() => router.back()}
        />

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          <GlassCard style={styles.card}>
            <Text style={styles.cardTitle}>Quick Filters</Text>
            <View style={styles.row}>
              <TextInput style={styles.input} value={minPrice} onChangeText={setMinPrice} placeholder="Min Price" placeholderTextColor={Colors.textFaint} keyboardType="numeric" />
              <TextInput style={styles.input} value={maxPrice} onChangeText={setMaxPrice} placeholder="Max Price" placeholderTextColor={Colors.textFaint} keyboardType="numeric" />
            </View>
            <View style={styles.row}>
              <TextInput style={styles.input} value={minChange} onChangeText={setMinChange} placeholder="Min %" placeholderTextColor={Colors.textFaint} keyboardType="numeric" />
              <TextInput style={styles.input} value={maxChange} onChangeText={setMaxChange} placeholder="Max %" placeholderTextColor={Colors.textFaint} keyboardType="numeric" />
            </View>
            <View style={styles.row}>
              <TextInput style={styles.input} value={minVolume} onChangeText={setMinVolume} placeholder="Min Volume" placeholderTextColor={Colors.textFaint} keyboardType="numeric" />
              <TextInput style={styles.input} value={rsiMin} onChangeText={setRsiMin} placeholder="RSI Min" placeholderTextColor={Colors.textFaint} keyboardType="numeric" />
            </View>
            <View style={styles.row}>
              <TextInput style={styles.input} value={rsiMax} onChangeText={setRsiMax} placeholder="RSI Max" placeholderTextColor={Colors.textFaint} keyboardType="numeric" />
            </View>

            <View style={{ flexDirection: 'row', marginTop: Spacing.sm }}>
              <PrimaryButton title="Run Screener" onPress={() => runScreener()} loading={running} style={{ flex: 1, marginRight: 8 }} />
              <PrimaryButton title="Reset" onPress={resetFilters} variant="ghost" style={{ flex: 0.6 }} />
            </View>
          </GlassCard>

          {presets.length > 0 && (
            <GlassCard style={styles.card}>
              <Text style={styles.cardTitle}>Presets</Text>
              <View style={styles.presetWrap}>
                {presets.map((preset: any) => {
                  const isActive = selectedPreset === (preset.id || preset.name);
                  return (
                    <TouchableOpacity
                      key={preset.id || preset.name}
                      style={[styles.preset, isActive && styles.presetActive]}
                      onPress={() => applyPreset(preset)}
                      activeOpacity={0.8}
                    >
                      <Text style={[styles.presetText, isActive && styles.presetTextActive]}>{preset.name}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </GlassCard>
          )}

          {results.length === 0 ? (
            <EmptyState icon="📉" title="No Matches" subtitle="Try broadening filters or use a preset." />
          ) : (
            results.map((item) => {
              const isPositive = (item.change_percent || 0) >= 0;
              return (
                <GlassCard key={item.symbol} style={styles.stockCard}>
                  <View style={styles.stockTop}>
                    <View>
                      <Text style={styles.symbol}>{item.symbol}</Text>
                      <Text style={styles.sector}>{item.sector || 'Unknown Sector'}</Text>
                    </View>
                    <Text style={styles.price}>₹{Number(item.ltp || 0).toLocaleString('en-IN')}</Text>
                  </View>
                  <View style={styles.stockBottom}>
                    <Tag
                      label={`${isPositive ? '+' : ''}${Number(item.change_percent || 0).toFixed(2)}%`}
                      color={isPositive ? Colors.green : Colors.red}
                      bg={isPositive ? Colors.greenBg : Colors.redBg}
                    />
                    <Text style={styles.meta}>Vol: {Number(item.volume || 0).toLocaleString('en-IN')}</Text>
                    <Text style={styles.meta}>RSI: {Number(item.rsi || 0).toFixed(1)}</Text>
                    <TouchableOpacity onPress={() => addToWatchlist(item.symbol)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                      <Ionicons name="bookmark-outline" size={16} color={Colors.accent} />
                    </TouchableOpacity>
                  </View>
                </GlassCard>
              );
            })
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
  card: { marginBottom: Spacing.md },
  cardTitle: { fontSize: 15, fontWeight: '700', color: Colors.textPrimary, marginBottom: Spacing.sm },
  row: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  input: {
    flex: 1,
    backgroundColor: Colors.bgGlassStrong,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    color: Colors.textPrimary,
    paddingHorizontal: 10,
    paddingVertical: 10,
    fontSize: 13,
  },
  presetWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  preset: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.full,
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: Colors.bgGlass,
  },
  presetActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  presetText: { color: Colors.textSecondary, fontSize: 12, fontWeight: '600' },
  presetTextActive: { color: Colors.accentLight },
  stockCard: { marginBottom: 10 },
  stockTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  symbol: { color: Colors.textPrimary, fontSize: 16, fontWeight: '700' },
  sector: { color: Colors.textMuted, fontSize: 12, marginTop: 2 },
  price: { color: Colors.textPrimary, fontSize: 15, fontWeight: '700' },
  stockBottom: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 12 },
  meta: { color: Colors.textSecondary, fontSize: 12 },
});
