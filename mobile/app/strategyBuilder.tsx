
import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, SafeAreaView } from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { strategyAPI, greeksAPI, marketAPI } from '../lib/api';

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
  const [legs, setLegs] = useState([]);
  const [atm, setAtm] = useState(20000);
  const [spot, setSpot] = useState(20000);
  const [expiryDates, setExpiryDates] = useState([]);
  const [selectedExpiry, setSelectedExpiry] = useState('');
  const [loading, setLoading] = useState(false);
  const [template, setTemplate] = useState('CUSTOM');
  const [error, setError] = useState(null);
  const [greeks, setGreeks] = useState(null);

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

  const removeLeg = (id) => setLegs(legs.filter(l => l.id !== id));

  const updateLeg = async (id, field, value) => {
    setLegs(legs.map(l => {
      if (l.id !== id) return l;
      const updated = { ...l, [field]: value };
      if (['strike', 'option_type'].includes(field)) {
        fetchPremium(updated.strike, updated.option_type).then(premium => {
          setLegs(legs => legs.map(x => x.id === id ? { ...x, premium } : x));
        });
      }
      return updated;
    }));
  };

  const fetchPremium = async (strike, optionType) => {
    try {
      if (!selectedExpiry) return 0;
      const resp = await marketAPI.getOptionPremium('NIFTY', strike, optionType, selectedExpiry);
      return resp?.data?.premium || 0;
    } catch {
      return 0;
    }
  };

  const buildTemplate = async (tpl) => {
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
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Text style={styles.title}>Strategy Builder</Text>
        <Text style={styles.label}>Template</Text>
        <Picker
          selectedValue={template}
          onValueChange={buildTemplate}
          style={styles.input}
        >
          {STRATEGY_TEMPLATES.map(t => (
            <Picker.Item key={t.value} label={t.label} value={t.value} />
          ))}
        </Picker>
        <Text style={styles.label}>Expiry</Text>
        <Picker
          selectedValue={selectedExpiry}
          onValueChange={setSelectedExpiry}
          style={styles.input}
        >
          {expiryDates.map(e => (
            <Picker.Item key={e} label={e} value={e} />
          ))}
        </Picker>
        <Text style={styles.label}>Option Legs</Text>
        {legs.map((leg, idx) => (
          <View key={leg.id} style={styles.legBox}>
            <Text>Leg {idx + 1}</Text>
            <Picker
              selectedValue={leg.type}
              onValueChange={v => updateLeg(leg.id, 'type', v)}
              style={styles.input}
            >
              <Picker.Item label="BUY" value="BUY" />
              <Picker.Item label="SELL" value="SELL" />
            </Picker>
            <Picker
              selectedValue={leg.option_type}
              onValueChange={v => updateLeg(leg.id, 'option_type', v)}
              style={styles.input}
            >
              <Picker.Item label="CE" value="CE" />
              <Picker.Item label="PE" value="PE" />
            </Picker>
            <TextInput
              style={styles.input}
              value={String(leg.strike)}
              onChangeText={v => updateLeg(leg.id, 'strike', Number(v))}
              keyboardType="numeric"
              placeholder="Strike"
            />
            <TextInput
              style={styles.input}
              value={String(leg.quantity)}
              onChangeText={v => updateLeg(leg.id, 'quantity', Number(v))}
              keyboardType="numeric"
              placeholder="Lots"
            />
            <Text>Premium: ₹{leg.premium}</Text>
            <TouchableOpacity onPress={() => removeLeg(leg.id)} style={styles.removeBtn}>
              <Text style={{ color: '#fff' }}>Remove</Text>
            </TouchableOpacity>
          </View>
        ))}
        <TouchableOpacity onPress={addLeg} style={styles.addBtn}>
          <Text style={{ color: '#fff' }}>Add Leg</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={calculateGreeks} style={styles.calcBtn}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={{ color: '#fff' }}>Calculate Greeks</Text>}
        </TouchableOpacity>
        {greeks && (
          <View style={styles.resultBox}>
            <Text style={styles.resultTitle}>Greeks</Text>
            <Text>Delta: {greeks.delta}</Text>
            <Text>Gamma: {greeks.gamma}</Text>
            <Text>Theta: {greeks.theta}</Text>
            <Text>Vega: {greeks.vega}</Text>
            <Text>Rho: {greeks.rho}</Text>
          </View>
        )}
        {error && <Text style={styles.error}>{error}</Text>}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  scrollContent: { padding: 16 },
  title: { fontSize: 24, fontWeight: 'bold', marginBottom: 16, color: '#0f172a' },
  label: { fontSize: 14, fontWeight: '600', marginBottom: 8, color: '#333' },
  input: { borderWidth: 1, borderColor: '#ddd', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#333', backgroundColor: '#f9f9f9', marginBottom: 8 },
  legBox: { backgroundColor: '#f1f5f9', borderRadius: 10, padding: 12, marginBottom: 12 },
  addBtn: { backgroundColor: '#10B981', padding: 14, borderRadius: 8, alignItems: 'center', marginBottom: 12 },
  removeBtn: { backgroundColor: '#EF4444', padding: 8, borderRadius: 8, alignItems: 'center', marginTop: 8 },
  calcBtn: { backgroundColor: '#3B82F6', padding: 14, borderRadius: 8, alignItems: 'center', marginBottom: 12 },
  resultBox: { backgroundColor: '#f1f5f9', borderRadius: 10, padding: 16, marginTop: 20 },
  resultTitle: { fontSize: 18, fontWeight: 'bold', marginBottom: 10, color: '#1e293b' },
  error: { color: '#EF4444', fontWeight: 'bold', marginTop: 10 },
});

export default StrategyBuilderScreen;
