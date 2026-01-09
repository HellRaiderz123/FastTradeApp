import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, SafeAreaView } from 'react-native';
import { useTradeStore } from '../lib/store';
import { paperAPI } from '../lib/api';

const PositionsScreen = () => {
  const { trades, setTrades } = useTradeStore();
  const [loading, setLoading] = useState(false);

  const fetchPositions = useCallback(async () => {
    setLoading(true);
    try {
      const response = await paperAPI.getPositions();
      if (Array.isArray(response.data)) {
        setTrades(response.data);
      }
    } catch (error) {
      // Optionally show error
    } finally {
      setLoading(false);
    }
  }, [setTrades]);

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 30000); // Poll every 30s
    return () => clearInterval(interval);
  }, [fetchPositions]);

  const openPositions = trades.filter((t) => t.status === 'EXECUTED');
  const totalPnL = openPositions.reduce((sum, t) => sum + t.pnl, 0);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={{flexDirection:'row', justifyContent:'space-between', alignItems:'center'}}>
          <Text style={styles.title}>Open Positions</Text>
          <TouchableOpacity onPress={fetchPositions} disabled={loading} style={{padding:8}}>
            <Text style={{color:'#3B82F6', fontWeight:'bold'}}>{loading ? 'Refreshing...' : 'Refresh'}</Text>
          </TouchableOpacity>
        </View>

        {/* Summary Cards */}
        <View style={styles.summaryContainer}>
          <SummaryCard label="Open" value={openPositions.length.toString()} />
          <SummaryCard
            label="P&L"
            value={`₹${totalPnL.toLocaleString()}`}
            color={totalPnL >= 0 ? '#10B981' : '#EF4444'}
          />
        </View>

        {/* Positions List */}
        {openPositions.length === 0 ? (
          <EmptyState />
        ) : (
          <View style={styles.positionsList}>
            {openPositions.map((position) => (
              <PositionCard key={position.id} position={position} />
            ))}
          </View>
        )}

        {/* Risk Metrics */}
        <RiskMetricsSection />

        {/* Coming Soon */}
        <ComingSoonFeatures />
      </ScrollView>
    </SafeAreaView>
  );
};

const SummaryCard = ({ label, value, color = '#fff' }) => (
  <View style={styles.summaryCard}>
    <Text style={styles.summaryLabel}>{label}</Text>
    <Text style={[styles.summaryValue, { color }]}>{value}</Text>
  </View>
);

const PositionCard = ({ position }) => (
  <View style={styles.positionCard}>
    <View style={styles.positionHeader}>
      <View>
        <Text style={styles.positionStrategy}>{position.strategy}</Text>
        <Text style={styles.positionUnderlying}>{position.underlying}</Text>
      </View>
      <Text
        style={[
          styles.positionPnL,
          { color: position.pnl >= 0 ? '#10B981' : '#EF4444' },
        ]}
      >
        {position.pnl >= 0 ? '+' : ''}₹{Math.abs(position.pnl).toLocaleString()}
      </Text>
    </View>

    <View style={styles.positionDetails}>
      <Detail label="Entry" value={`₹${position.entry_price}`} />
      <Detail label="Current" value={`₹${position.current_price}`} />
      <Detail
        label="Return"
        value={`${position.pnl_percent.toFixed(2)}%`}
        color={position.pnl >= 0 ? '#10B981' : '#EF4444'}
      />
    </View>

    <TouchableOpacity style={styles.closeButton}>
      <Text style={styles.closeButtonText}>Close Position</Text>
    </TouchableOpacity>
  </View>
);

const Detail = ({ label, value, color = '#fff' }) => (
  <View>
    <Text style={styles.detailLabel}>{label}</Text>
    <Text style={[styles.detailValue, { color }]}>{value}</Text>
  </View>
);

const EmptyState = () => (
  <View style={styles.emptyState}>
    <Text style={styles.emptyStateText}>No open positions</Text>
    <Text style={styles.emptyStateSubtext}>Execute a strategy to open a position</Text>
  </View>
);

const RiskMetricsSection = () => (
  <View style={styles.metricsSection}>
    <Text style={styles.sectionTitle}>Risk Metrics</Text>
    <View style={styles.metricsGrid}>
      <MetricBox label="Portfolio Heat" value="2.5%" status="good" />
      <MetricBox label="Max Drawdown" value="-1.2%" status="warning" />
    </View>
  </View>
);

const MetricBox = ({ label, value, status }) => {
  const statusColor = {
    good: '#10B981',
    warning: '#F59E0B',
  }[status];

  return (
    <View style={styles.metricBox}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, { color: statusColor }]}>{value}</Text>
    </View>
  );
};

const ComingSoonFeatures = () => (
  <View style={styles.comingSoon}>
    <Text style={styles.comingSoonTitle}>More Features Coming</Text>
    <View style={styles.featureGrid}>
      {['Hedge', 'Adjust', 'Add To', 'Share'].map((feature) => (
        <View key={feature} style={styles.featureCard}>
          <Text style={styles.featureText}>{feature}</Text>
        </View>
      ))}
    </View>
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
    marginBottom: 20,
  },
  summaryContainer: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 24,
  },
  summaryCard: {
    flex: 1,
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 16,
  },
  summaryLabel: {
    fontSize: 12,
    color: '#94a3b8',
    marginBottom: 8,
  },
  summaryValue: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  positionsList: {
    marginBottom: 24,
  },
  positionCard: {
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  positionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  positionStrategy: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },
  positionUnderlying: {
    fontSize: 12,
    color: '#94a3b8',
    marginTop: 4,
  },
  positionPnL: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  positionDetails: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingVertical: 12,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: '#334155',
    marginBottom: 12,
  },
  detailLabel: {
    fontSize: 11,
    color: '#94a3b8',
    marginBottom: 4,
  },
  detailValue: {
    fontSize: 13,
    fontWeight: '600',
  },
  closeButton: {
    backgroundColor: '#EF4444',
    borderRadius: 8,
    paddingVertical: 10,
  },
  closeButtonText: {
    color: '#fff',
    fontWeight: '600',
    textAlign: 'center',
    fontSize: 13,
  },
  emptyState: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyStateText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#cbd5e1',
    marginBottom: 8,
  },
  emptyStateSubtext: {
    fontSize: 13,
    color: '#64748b',
  },
  metricsSection: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 12,
  },
  metricsGrid: {
    flexDirection: 'row',
    gap: 12,
  },
  metricBox: {
    flex: 1,
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 12,
  },
  metricLabel: {
    fontSize: 11,
    color: '#94a3b8',
    marginBottom: 6,
  },
  metricValue: {
    fontSize: 18,
    fontWeight: 'bold',
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
  featureGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  featureCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: '#0f172a',
    borderRadius: 8,
    paddingVertical: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  featureText: {
    color: '#94a3b8',
    fontSize: 12,
    fontWeight: '500',
  },
});

export default PositionsScreen;
