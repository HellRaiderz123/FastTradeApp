import React, { useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator, SafeAreaView, TextInput } from 'react-native';
import { backtestAPI } from '../lib/api';

const BacktestScreen = () => {
  const [underlying, setUnderlying] = useState('NIFTY');
  const [startDate, setStartDate] = useState('2023-01-01');
  const [endDate, setEndDate] = useState('2023-12-31');
  const [capital, setCapital] = useState('100000');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleRunBacktest = async () => {
    setLoading(true);
    setResult(null);
    try {
      const payload = {
        underlying,
        start_date: startDate,
        end_date: endDate,
        initial_capital: parseInt(capital),
      };
      const response = await backtestAPI.runBacktest(payload);
      setResult(response.data);
    } catch (error) {
      setResult({ error: 'Failed to run backtest' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Text style={styles.title}>Backtest</Text>
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Underlying</Text>
          <TextInput style={styles.input} value={underlying} onChangeText={setUnderlying} />
        </View>
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Start Date (YYYY-MM-DD)</Text>
          <TextInput style={styles.input} value={startDate} onChangeText={setStartDate} />
        </View>
        <View style={styles.inputGroup}>
          <Text style={styles.label}>End Date (YYYY-MM-DD)</Text>
          <TextInput style={styles.input} value={endDate} onChangeText={setEndDate} />
        </View>
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Initial Capital</Text>
          <TextInput style={styles.input} value={capital} onChangeText={setCapital} keyboardType="numeric" />
        </View>
        <TouchableOpacity style={styles.button} onPress={handleRunBacktest} disabled={loading}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Run Backtest</Text>}
        </TouchableOpacity>
        {result && (
          <View style={styles.resultBox}>
            {result.error ? (
              <Text style={styles.error}>{result.error}</Text>
            ) : (
              <>
                <Text style={styles.resultTitle}>Results</Text>
                <Text>Total Return: {result.total_return_pct}%</Text>
                <Text>Annual Return: {result.annual_return_pct}%</Text>
                <Text>Sharpe Ratio: {result.sharpe_ratio}</Text>
                <Text>Max Drawdown: {result.max_drawdown_pct}%</Text>
                <Text>Win Rate: {result.win_rate_pct}%</Text>
                <Text>Total Trades: {result.total_trades}</Text>
              </>
            )}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  scrollContent: { padding: 16 },
  title: { fontSize: 24, fontWeight: 'bold', marginBottom: 16, color: '#0f172a' },
  inputGroup: { marginBottom: 16 },
  label: { fontSize: 14, fontWeight: '600', marginBottom: 8, color: '#333' },
  input: { borderWidth: 1, borderColor: '#ddd', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#333', backgroundColor: '#f9f9f9' },
  button: { backgroundColor: '#10B981', padding: 14, borderRadius: 8, alignItems: 'center', marginTop: 8 },
  buttonText: { color: '#fff', fontWeight: 'bold', fontSize: 16 },
  resultBox: { backgroundColor: '#f1f5f9', borderRadius: 10, padding: 16, marginTop: 20 },
  resultTitle: { fontSize: 18, fontWeight: 'bold', marginBottom: 10, color: '#1e293b' },
  error: { color: '#EF4444', fontWeight: 'bold' },
});

export default BacktestScreen;
