import React, { useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, SafeAreaView, TextInput, Alert } from 'react-native';
import { strategyAPI, executionAPI } from '../lib/api';
import { useTradeStore } from '../lib/store';

const StrategiesScreen = () => {
  const [underlying, setUnderlying] = useState('NIFTY');
  const [capital, setCapital] = useState('100000');
  const [lots, setLots] = useState('1');
  const [riskMode, setRiskMode] = useState('BALANCED');
  const [loading, setLoading] = useState(false);
  const [strategyResult, setStrategyResult] = useState(null);
  const { addTrade } = useTradeStore();

  const underlyings = ['NIFTY', 'BANKNIFTY', 'FINNIFTY'];
  const riskModes = ['Conservative', 'Balanced', 'Aggressive'];

  const handleRunStrategy = async () => {
    setLoading(true);
    try {
      const payload = {
        underlying,
        interval: '15minute',
        use_ml: false,
        min_confidence: 75,
        risk_mode: riskMode,
        lots: parseInt(lots),
        capital: parseInt(capital),
      };

      const response = await strategyAPI.runStrategy(payload);
      setStrategyResult(response.data);
    } catch (error) {
      Alert.alert('Error', 'Failed to run strategy');
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!strategyResult || !strategyResult.run_id) return;

    try {
      const intentRes = await executionAPI.createIntent(strategyResult.run_id, riskMode);
      const intent = intentRes.data;

      await executionAPI.confirmIntent(intent.intent_id);

      await executionAPI.executeIntent(intent.intent_id, `exec_${Date.now()}`);

      addTrade({
        id: intent.id,
        strategy: strategyResult.strategy,
        underlying,
        status: 'EXECUTED',
        entry_price: 0,
        current_price: 0,
        pnl: 0,
        pnl_percent: 0,
        entry_time: new Date().toISOString(),
      });

      setStrategyResult(null);
      Alert.alert('Success', 'Trade executed successfully!');
    } catch (error) {
      Alert.alert('Error', 'Failed to execute trade');
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Text style={styles.title}>Strategy Generator</Text>

        {/* Input Fields */}
        <View style={styles.inputGroup}>
          <Label text="Underlying" />
          <Picker
            selectedValue={underlying}
            onValueChange={setUnderlying}
            items={underlyings}
          />

          <Label text="Capital (₹)" />
          <TextInput
            style={styles.input}
            placeholder="100000"
            value={capital}
            onChangeText={setCapital}
            keyboardType="numeric"
            placeholderTextColor="#64748b"
          />

          <Label text="Lots" />
          <TextInput
            style={styles.input}
            placeholder="1"
            value={lots}
            onChangeText={setLots}
            keyboardType="numeric"
            placeholderTextColor="#64748b"
          />

          <Label text="Risk Mode" />
          <Picker
            selectedValue={riskMode}
            onValueChange={setRiskMode}
            items={riskModes}
          />
        </View>

        {/* Action Button */}
        <TouchableOpacity
          style={[styles.button, styles.primaryButton]}
          onPress={handleRunStrategy}
          disabled={loading}
        >
          <Text style={styles.buttonText}>{loading ? 'Analyzing...' : 'Run Strategy'}</Text>
        </TouchableOpacity>

        {/* Strategy Result */}
        {strategyResult && (
          <StrategyResultCard result={strategyResult} onExecute={handleExecute} />
        )}

        {/* Coming Soon */}
        <View style={styles.comingSoon}>
          <Text style={styles.comingSoonTitle}>More Features</Text>
          {['Backtester', 'Strategy Builder', 'Signals', 'Analysis'].map((item) => (
            <View key={item} style={styles.comingSoonItem}>
              <Text style={styles.comingSoonText}>{item} 🔜</Text>
            </View>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const Label = ({ text }) => <Text style={styles.label}>{text}</Text>;

const Picker = ({ selectedValue, onValueChange, items }) => (
  <ScrollView horizontal style={styles.pickerContainer} showsHorizontalScrollIndicator={false}>
    {items.map((item) => (
      <TouchableOpacity
        key={item}
        style={[
          styles.pickerItem,
          selectedValue === item && styles.pickerItemActive,
        ]}
        onPress={() => onValueChange(item)}
      >
        <Text
          style={[
            styles.pickerItemText,
            selectedValue === item && styles.pickerItemTextActive,
          ]}
        >
          {item}
        </Text>
      </TouchableOpacity>
    ))}
  </ScrollView>
);

const StrategyResultCard = ({ result, onExecute }) => (
  <View style={styles.resultCard}>
    <View style={styles.resultHeader}>
      <Text style={styles.resultTitle}>Strategy Result</Text>
      <View
        style={[
          styles.statusBadge,
          result.approved && styles.statusBadgeApproved,
          !result.approved && styles.statusBadgeRejected,
        ]}
      >
        <Text style={styles.statusBadgeText}>
          {result.approved ? '✓ APPROVED' : '✗ REJECTED'}
        </Text>
      </View>
    </View>

    <Text style={styles.resultReason}>{result.reason}</Text>

    <View style={styles.resultDetails}>
      <DetailRow label="Strategy" value={result.strategy} />
      <DetailRow label="Signal" value={result.signal?.signal || 'N/A'} />
      <DetailRow label="Confidence" value={`${result.signal?.confidence || 0}%`} />
    </View>

    {result.approved && (
      <TouchableOpacity style={[styles.button, styles.successButton]} onPress={onExecute}>
        <Text style={styles.buttonText}>Execute Trade</Text>
      </TouchableOpacity>
    )}
  </View>
);

const DetailRow = ({ label, value }) => (
  <View style={styles.detailRow}>
    <Text style={styles.detailLabel}>{label}</Text>
    <Text style={styles.detailValue}>{value}</Text>
  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a',
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingVertical: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 24,
  },
  inputGroup: {
    marginBottom: 24,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#cbd5e1',
    marginBottom: 8,
    marginTop: 12,
  },
  input: {
    backgroundColor: '#1e293b',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 12,
    color: '#fff',
    borderWidth: 1,
    borderColor: '#334155',
  },
  pickerContainer: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  pickerItem: {
    backgroundColor: '#1e293b',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginRight: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  pickerItemActive: {
    backgroundColor: '#3B82F6',
    borderColor: '#3B82F6',
  },
  pickerItemText: {
    color: '#94a3b8',
    fontWeight: '500',
  },
  pickerItemTextActive: {
    color: '#fff',
  },
  button: {
    borderRadius: 8,
    paddingVertical: 12,
    marginBottom: 16,
  },
  primaryButton: {
    backgroundColor: '#3B82F6',
  },
  successButton: {
    backgroundColor: '#10B981',
  },
  buttonText: {
    color: '#fff',
    fontWeight: '600',
    textAlign: 'center',
    fontSize: 14,
  },
  resultCard: {
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  resultHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  resultTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#fff',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: '#EF4444',
  },
  statusBadgeApproved: {
    backgroundColor: '#10B981',
  },
  statusBadgeRejected: {
    backgroundColor: '#EF4444',
  },
  statusBadgeText: {
    color: '#fff',
    fontSize: 11,
    fontWeight: '600',
  },
  resultReason: {
    color: '#cbd5e1',
    fontSize: 14,
    marginBottom: 16,
  },
  resultDetails: {
    borderTopWidth: 1,
    borderTopColor: '#334155',
    paddingTop: 12,
    marginBottom: 16,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  detailLabel: {
    color: '#94a3b8',
    fontSize: 12,
  },
  detailValue: {
    color: '#fff',
    fontWeight: '600',
  },
  comingSoon: {
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 16,
    opacity: 0.6,
  },
  comingSoonTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#cbd5e1',
    marginBottom: 12,
  },
  comingSoonItem: {
    paddingVertical: 8,
  },
  comingSoonText: {
    color: '#94a3b8',
    fontSize: 14,
  },
});

export default StrategiesScreen;
