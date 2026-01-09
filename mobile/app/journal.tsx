import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator, SafeAreaView } from 'react-native';
import { journalAPI } from '../lib/api';

const JournalScreen = () => {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    fetchJournal();
  }, []);

  const fetchJournal = async () => {
    try {
      setLoading(true);
      const response = await journalAPI.getExecutionIntents(100);
      setEntries(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      // Optionally show error
    } finally {
      setLoading(false);
    }
  };

  const renderEntry = (entry) => {
    const expanded = expandedId === entry.id;
    const entryPrice = Number(entry?.entry_credit ?? 0) || 0;
    const pnl = Number(entry?.pnl ?? 0) || 0;
    const exitPrice = entryPrice ? entryPrice - pnl : null;
    const pnlPercent = entryPrice !== 0 ? (pnl / entryPrice) * 100 : 0;
    const isProfitable = pnl >= 0;
    return (
      <TouchableOpacity
        key={entry.id}
        style={styles.entryContainer}
        onPress={() => setExpandedId(expanded ? null : entry.id)}
      >
        <View style={styles.entryHeader}>
          <Text style={styles.entryTitle}>{entry.strategy || 'Unknown'}</Text>
          <Text style={[styles.pnl, isProfitable ? styles.green : styles.red]}>
            ₹{pnl.toLocaleString()} ({pnlPercent.toFixed(2)}%)
          </Text>
        </View>
        <Text style={styles.entrySub}>{entry.underlying || '-'}</Text>
        {expanded && (
          <View style={styles.entryDetails}>
            <Text>Entry Price: ₹{entryPrice}</Text>
            <Text>Exit Price: {exitPrice !== null ? `₹${exitPrice}` : 'N/A'}</Text>
            <Text>Status: {entry.status}</Text>
          </View>
        )}
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Text style={styles.title}>Trade Journal</Text>
        {loading ? (
          <ActivityIndicator size="large" color="#10B981" />
        ) : entries.length === 0 ? (
          <Text style={styles.empty}>No journal entries found.</Text>
        ) : (
          entries.map(renderEntry)
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  scrollContent: { padding: 16 },
  title: { fontSize: 24, fontWeight: 'bold', marginBottom: 16, color: '#0f172a' },
  entryContainer: { backgroundColor: '#f1f5f9', borderRadius: 10, padding: 16, marginBottom: 12 },
  entryHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  entryTitle: { fontSize: 16, fontWeight: '600', color: '#1e293b' },
  entrySub: { fontSize: 13, color: '#64748b', marginTop: 4 },
  pnl: { fontWeight: 'bold', fontSize: 15 },
  green: { color: '#10B981' },
  red: { color: '#EF4444' },
  entryDetails: { marginTop: 10 },
  empty: { textAlign: 'center', color: '#64748b', marginTop: 40 },
});

export default JournalScreen;
