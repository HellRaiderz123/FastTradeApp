import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, TextInput, StatusBar, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Picker } from '@react-native-picker/picker';
import { greeksAPI, marketAPI } from '../lib/api';
import { Colors, Gradients, Radius, Spacing } from '../lib/theme';
import { GlassCard, PrimaryButton, Tag } from '../components/ui';

const NIFTY_LOT_SIZE = 50;
const STRIKE_STEP = 50;
const STRATEGY_TEMPLATES = [
  { label: 'Custom', value: 'CUSTOM' },
  { label: 'Bull Put', value: 'BULL_PUT' },
  { label: 'Bear Call', value: 'BEAR_CALL' },
  { label: 'Iron Condor', value: 'IRON_CONDOR' },
  { label: 'Bull Call', value: 'BULL_CALL' },
  { label: 'Bear Put', value: 'BEAR_PUT' },
  { label: 'Short Strangle', value: 'SHORT_STRANGLE' },
  { label: 'Long Straddle', value: 'LONG_STRADDLE' },
];

const defaultLeg = (atm) => ({
  id: Date.now().toString(),
  type: 'BUY',
  option_type: 'CE',
  strike: atm,
  quantity: 1,
  strike_type: 'ABSOLUTE',
  strike_offset: 0,
  premium: 0,
});

const StrategyBuilderScreen = () => {
  const router = useRouter();
  const [legs, setLegs] = useState([]);
  const [atm, setAtm] = useState(20000);
  const [spot, setSpot] = useState(20000);
  const [expiryDates, setExpiryDates] = useState([]);
  const [selectedExpiry, setSelectedExpiry] = useState('');
  const [loading, setLoading] = useState(false);
  const [template, setTemplate] = useState('CUSTOM');
  const [error, setError] = useState<string | null>(null);
  const [greeks, setGreeks] = useState<any>(null);

  useEffect(() => {
    fetchMarketData();
  }, []);

  const fetchMarketData = async () => {
    setLoading(true);
    try {
      const spotResp = await marketAPI.getLTP('NIFTY');
      const spotVal = spotResp?.data?.ltp || 20000;
      setSpot(spotVal);
      setAtm(Math.round(spotVal / STRIKE_STEP) * STRIKE_STEP);
      const expiryResp = await marketAPI.getAvailableExpiries('NIFTY');
      const expiries = expiryResp?.data?.expiries || [];
      setExpiryDates(expiries);
      setSelectedExpiry(expiries[0] || '');
    } catch {
      setError('Failed to fetch market data');
    } finally {
      setLoading(false);
    }
  };

  const addLeg = async () => {
    const newLeg = defaultLeg(atm);
    newLeg.premium = await fetchPremium(newLeg.strike, newLeg.option_type);
    setLegs([...legs, newLeg]);
  };

  const removeLeg = (id: string) => setLegs(legs.filter((l: any) => l.id !== id));

  const updateLeg = async (id: string, field: string, value: any) => {
    setLegs(legs.map((l: any) => {
      if (l.id !== id) return l;
      const updated = { ...l, [field]: value };
      if (['strike', 'option_type'].includes(field)) {
        fetchPremium(updated.strike, updated.option_type).then((premium) => {
          setLegs((prev: any[]) => prev.map((x) => x.id === id ? { ...x, premium } : x));
        });
      }
      return updated;
    }));
  };

  const fetchPremium = async (strike: number, optionType: string) => {
    try {
      if (!selectedExpiry) return 0;
      const resp = await marketAPI.getOptionPremium('NIFTY', strike, optionType, selectedExpiry);
      return resp?.data?.premium || 0;
    } catch {
      return 0;
    }
  };

  const buildTemplate = async (tpl: string) => {
    setTemplate(tpl);
    // ...template logic (see web for details, can be expanded in next steps)...
    // For now, just clear legs for custom
    if (tpl === 'CUSTOM') setLegs([]);
  };

  const calculateGreeks = async () => {
    setLoading(true);
    try {
      const legsData = legs.map(l => ({
        type: l.type,
        option_type: l.option_type,
        strike: l.strike,
        spot,
        expiry_days: 7, // TODO: calculate from expiry
        volatility: 20,
        quantity: l.quantity * NIFTY_LOT_SIZE,
      }));
      const resp = await greeksAPI.calculate({ legs: legsData, spot, rate: 5.0 });
      setGreeks(resp?.data || resp);
    } catch {
      setError('Failed to calculate Greeks');
    } finally {
      setLoading(false);
    }
  };

  // UI rendering
  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safeArea}>
        <LinearGradient colors={Gradients.header} style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}>
            <Ionicons name="chevron-back" size={22} color={Colors.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.title}>Strategy Builder</Text>
          <Text style={styles.subtitle}>Build option legs and calculate Greeks from your phone</Text>
        </LinearGradient>

        <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          <GlassCard style={styles.summaryCard}>
            <View style={styles.summaryTop}>
              <Text style={styles.sectionTitle}>Market Snapshot</Text>
              <Tag label="LIVE DATA" color={Colors.green} bg={Colors.greenBg} />
            </View>
            <View style={styles.metricRow}>
              <Text style={styles.metricLabel}>Spot</Text>
              <Text style={styles.metricValue}>₹{Number(spot).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</Text>
            </View>
            <View style={styles.metricRow}>
              <Text style={styles.metricLabel}>ATM</Text>
              <Text style={styles.metricValue}>{atm}</Text>
            </View>
          </GlassCard>

          <GlassCard style={styles.configCard}>
            <Text style={styles.sectionTitle}>Setup</Text>

            <Text style={styles.label}>Template</Text>
            <View style={styles.pickerWrap}>
              <Picker
                selectedValue={template}
                onValueChange={buildTemplate}
                style={styles.picker}
                dropdownIconColor={Colors.textSecondary}
              >
                {STRATEGY_TEMPLATES.map((t) => (
                  <Picker.Item key={t.value} label={t.label} value={t.value} />
                ))}
              </Picker>
            </View>

            <Text style={styles.label}>Expiry</Text>
            <View style={styles.pickerWrap}>
              <Picker
                selectedValue={selectedExpiry}
                onValueChange={setSelectedExpiry}
                style={styles.picker}
                dropdownIconColor={Colors.textSecondary}
              >
                {expiryDates.map((e: string) => (
                  <Picker.Item key={e} label={e} value={e} />
                ))}
              </Picker>
            </View>

            <PrimaryButton title="Add Leg" onPress={addLeg} variant="success" />
          </GlassCard>

          <Text style={styles.sectionTitle}>Option Legs</Text>
          {legs.length === 0 ? (
            <GlassCard style={styles.emptyLegsCard}>
              <Text style={styles.emptyLegsText}>No legs yet. Tap Add Leg to start building.</Text>
            </GlassCard>
          ) : (
            legs.map((leg: any, idx: number) => (
              <GlassCard key={leg.id} style={styles.legBox}>
                <View style={styles.legHead}>
                  <Text style={styles.legTitle}>Leg {idx + 1}</Text>
                  <PrimaryButton title="Remove" onPress={() => removeLeg(leg.id)} variant="danger" small />
                </View>

                <Text style={styles.label}>Action</Text>
                <View style={styles.pickerWrap}>
                  <Picker selectedValue={leg.type} onValueChange={(v) => updateLeg(leg.id, 'type', v)} style={styles.picker} dropdownIconColor={Colors.textSecondary}>
                    <Picker.Item label="BUY" value="BUY" />
                    <Picker.Item label="SELL" value="SELL" />
                  </Picker>
                </View>

                <Text style={styles.label}>Option Type</Text>
                <View style={styles.pickerWrap}>
                  <Picker selectedValue={leg.option_type} onValueChange={(v) => updateLeg(leg.id, 'option_type', v)} style={styles.picker} dropdownIconColor={Colors.textSecondary}>
                    <Picker.Item label="CE" value="CE" />
                    <Picker.Item label="PE" value="PE" />
                  </Picker>
                </View>

                <View style={styles.rowInputs}>
                  <View style={[styles.inputBlock, styles.halfInput]}>
                    <Text style={styles.label}>Strike</Text>
                    <TextInput
                      style={styles.input}
                      value={String(leg.strike)}
                      onChangeText={(v) => updateLeg(leg.id, 'strike', Number(v) || 0)}
                      keyboardType="numeric"
                      placeholder="Strike"
                      placeholderTextColor={Colors.textFaint}
                    />
                  </View>
                  <View style={[styles.inputBlock, styles.halfInput]}>
                    <Text style={styles.label}>Lots</Text>
                    <TextInput
                      style={styles.input}
                      value={String(leg.quantity)}
                      onChangeText={(v) => updateLeg(leg.id, 'quantity', Number(v) || 0)}
                      keyboardType="numeric"
                      placeholder="Lots"
                      placeholderTextColor={Colors.textFaint}
                    />
                  </View>
                </View>

                <View style={styles.metricRow}>
                  <Text style={styles.metricLabel}>Premium</Text>
                  <Text style={[styles.metricValue, { color: Colors.accent }]}>₹{Number(leg.premium || 0).toFixed(2)}</Text>
                </View>
              </GlassCard>
            ))
          )}

          <PrimaryButton title="Calculate Greeks" onPress={calculateGreeks} loading={loading} />

          {greeks && (
            <GlassCard style={styles.resultBox}>
              <Text style={styles.sectionTitle}>Greeks</Text>
              <MetricRow label="Delta" value={greeks.delta} />
              <MetricRow label="Gamma" value={greeks.gamma} />
              <MetricRow label="Theta" value={greeks.theta} />
              <MetricRow label="Vega" value={greeks.vega} />
              <MetricRow label="Rho" value={greeks.rho} />
            </GlassCard>
          )}

          {error && <Text style={styles.error}>{error}</Text>}
          <View style={{ height: 96 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
};

function MetricRow({ label, value }: { label: string; value: number | string }) {
  return (
    <View style={styles.metricRow}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{Number(value || 0).toFixed(4)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safeArea: { flex: 1 },
  header: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.lg },
  backButton: { alignSelf: 'flex-start', marginBottom: 10 },
  title: { fontSize: 28, fontWeight: '700', color: Colors.textPrimary, letterSpacing: -0.5 },
  subtitle: { marginTop: 4, fontSize: 13, color: Colors.textMuted },
  scrollContent: { padding: Spacing.lg },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: Colors.textPrimary, marginBottom: 8 },
  summaryCard: { marginBottom: 12 },
  summaryTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  configCard: { marginBottom: 12 },
  label: { fontSize: 12, fontWeight: '600', color: Colors.textMuted, marginBottom: 6, marginTop: 4 },
  pickerWrap: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass,
    overflow: 'hidden',
    marginBottom: 10,
  },
  picker: { color: Colors.textPrimary },
  legBox: { marginBottom: 12 },
  legHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  legTitle: { color: Colors.textPrimary, fontSize: 15, fontWeight: '700' },
  rowInputs: { flexDirection: 'row', gap: 10 },
  inputBlock: { marginBottom: 8 },
  halfInput: { flex: 1 },
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
  emptyLegsCard: { marginBottom: 12 },
  emptyLegsText: { color: Colors.textSecondary, fontSize: 13 },
  resultBox: { marginTop: 12 },
  metricRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  metricLabel: { fontSize: 13, color: Colors.textSecondary },
  metricValue: { fontSize: 14, fontWeight: '700', color: Colors.textPrimary },
  error: { color: Colors.red, fontWeight: '700', marginTop: 12 },
});

export default StrategyBuilderScreen;
