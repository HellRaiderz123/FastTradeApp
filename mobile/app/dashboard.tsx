import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, SafeAreaView } from 'react-native';
import { LineChart } from 'react-native-chart-kit';
import { useTradeStore } from '../lib/store';
import { systemAPI } from '../lib/api';

const DashboardScreen = () => {
  const { capital, dailyPnL, trades, setSystemEnabled } = useTradeStore();
  const [systemEnabled, setSystemEnabledLocal] = useState(true);

  useEffect(() => {
    checkSystemStatus();
  }, []);

  const checkSystemStatus = async () => {
    try {
      const response = await systemAPI.status();
      setSystemEnabled(response.data.trading_enabled);
      setSystemEnabledLocal(response.data.trading_enabled);
    } catch (error) {
      console.error('Failed to check system status:', error);
    }
  };

  const pnlPercent = ((dailyPnL / capital) * 100).toFixed(2);
  const winCount = trades.filter((t) => t.pnl > 0).length;
  const winRate = trades.length > 0 ? ((winCount / trades.length) * 100).toFixed(1) : '0';

  const chartData = {
    labels: ['09:15', '10:15', '11:15', '12:15', '13:15', '14:15'],
    datasets: [
      {
        data: [100000, 101200, 101800, 100900, 102500, 103200],
        color: (opacity = 1) => `rgba(16, 185, 129, ${opacity})`,
      },
    ],
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>FastTrade Pro</Text>
            <Text style={styles.subtitle}>Paper Trading</Text>
          </View>
          <TouchableOpacity
            style={[
              styles.systemButton,
              { backgroundColor: systemEnabled ? '#10B981' : '#EF4444' },
            ]}
          >
            <Text style={styles.systemButtonText}>
              {systemEnabled ? '🟢 LIVE' : '🔴 OFF'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Key Metrics */}
        <View style={styles.metricsContainer}>
          <MetricCard label="Capital" value={`₹${capital.toLocaleString()}`} color="#3B82F6" />
          <MetricCard
            label="Today's P&L"
            value={`₹${dailyPnL.toLocaleString()}`}
            subtext={`${pnlPercent}%`}
            color={dailyPnL >= 0 ? '#10B981' : '#EF4444'}
          />
          <MetricCard label="Trades" value={trades.length.toString()} color="#8B5CF6" />
          <MetricCard label="Win Rate" value={`${winRate}%`} color="#F59E0B" />
        </View>

        {/* Chart */}
        <View style={styles.chartContainer}>
          <Text style={styles.chartTitle}>Portfolio Growth</Text>
          <LineChart
            data={chartData}
            width={350}
            height={220}
            chartConfig={{
              backgroundColor: '#1f2937',
              backgroundGradientFrom: '#1f2937',
              backgroundGradientTo: '#111827',
              color: (opacity = 1) => `rgba(148, 163, 184, ${opacity})`,
              labelColor: (opacity = 1) => `rgba(148, 163, 184, ${opacity})`,
              style: { borderRadius: 16 },
              propsForDots: {
                r: '6',
                strokeWidth: '2',
                stroke: '#10B981',
              },
            }}
            bezier
            style={styles.chart}
          />
        </View>

        {/* Recent Trades */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Recent Trades</Text>
          {trades.length === 0 ? (
            <Text style={styles.emptyText}>No trades yet</Text>
          ) : (
            trades.slice(0, 5).map((trade, idx) => (
              <TradeRow key={idx} trade={trade} />
            ))
          )}
        </View>

        {/* Coming Soon */}
        <ComingSoonSection />
      </ScrollView>
    </SafeAreaView>
  );
};

const MetricCard = ({ label, value, subtext, color }) => (
  <View style={[styles.metricCard, { borderLeftColor: color }]}>
    <Text style={styles.metricLabel}>{label}</Text>
    <Text style={[styles.metricValue, { color }]}>{value}</Text>
    {subtext && <Text style={styles.metricSubtext}>{subtext}</Text>}
  </View>
);

const TradeRow = ({ trade }) => (
  <View style={styles.tradeRow}>
    <View>
      <Text style={styles.tradeStrategy}>{trade.strategy}</Text>
      <Text style={styles.tradeUnderlying}>{trade.underlying}</Text>
    </View>
    <View style={styles.tradeRight}>
      <Text style={[styles.tradePnL, { color: trade.pnl >= 0 ? '#10B981' : '#EF4444' }]}>
        ₹{Math.abs(trade.pnl).toLocaleString()}
      </Text>
      <Text style={[styles.tradePnLPercent, { color: trade.pnl >= 0 ? '#10B981' : '#EF4444' }]}>
        {trade.pnl >= 0 ? '+' : ''}{trade.pnl_percent.toFixed(2)}%
      </Text>
    </View>
  </View>
);

const ComingSoonSection = () => (
  <View style={styles.comingSoonContainer}>
    <Text style={styles.comingSoonTitle}>More Features Coming</Text>
    <View style={styles.comingSoonGrid}>
      {['Alerts', 'Watchlist', 'Analytics', 'Community'].map((feature) => (
        <View key={feature} style={styles.comingSoonCard}>
          <Text style={styles.comingSoonText}>{feature}</Text>
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
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
  },
  subtitle: {
    fontSize: 12,
    color: '#94a3b8',
    marginTop: 4,
  },
  systemButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
  },
  systemButtonText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 12,
  },
  metricsContainer: {
    marginBottom: 24,
  },
  metricCard: {
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
  },
  metricLabel: {
    fontSize: 12,
    color: '#94a3b8',
    marginBottom: 4,
  },
  metricValue: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  metricSubtext: {
    fontSize: 11,
    color: '#64748b',
    marginTop: 4,
  },
  chartContainer: {
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  chartTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 12,
  },
  chart: {
    borderRadius: 12,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 12,
  },
  tradeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  tradeStrategy: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },
  tradeUnderlying: {
    fontSize: 12,
    color: '#94a3b8',
    marginTop: 2,
  },
  tradeRight: {
    alignItems: 'flex-end',
  },
  tradePnL: {
    fontSize: 14,
    fontWeight: 'bold',
  },
  tradePnLPercent: {
    fontSize: 12,
    marginTop: 2,
  },
  emptyText: {
    color: '#94a3b8',
    textAlign: 'center',
    paddingVertical: 20,
  },
  comingSoonContainer: {
    marginBottom: 24,
  },
  comingSoonTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#cbd5e1',
    marginBottom: 12,
  },
  comingSoonGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  comingSoonCard: {
    width: '48%',
    backgroundColor: '#1e293b',
    borderRadius: 8,
    padding: 16,
    marginBottom: 8,
    justifyContent: 'center',
    alignItems: 'center',
    height: 80,
    opacity: 0.5,
  },
  comingSoonText: {
    color: '#94a3b8',
    fontSize: 14,
    fontWeight: '500',
  },
});

export default DashboardScreen;
