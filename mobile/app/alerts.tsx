import React, { useCallback, useEffect, useRef, useState } from 'react';
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
import * as Haptics from 'expo-haptics';
import { Ionicons } from '@expo/vector-icons';
import { alertsAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, PrimaryButton, ScreenHeader, Tag } from '../components/ui';

const OPERATORS = [
  { key: 'above', label: 'Above' },
  { key: 'below', label: 'Below' },
  { key: 'above_or_equal', label: '≥' },
  { key: 'below_or_equal', label: '≤' },
];

export default function AlertsScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);

  // Create form
  const [ticker, setTicker] = useState('');
  const [price, setPrice] = useState('');
  const [operator, setOperator] = useState('above');
  const [creating, setCreating] = useState(false);
  const createRef = useRef(false);

  const load = useCallback(async () => {
    try {
      const res = await alertsAPI.list();
      const data = res.data?.alerts || [];
      setAlerts(Array.isArray(data) ? data : []);
    } catch {
      setAlerts([]);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    load();
  };

  const createAlert = async () => {
    const sym = ticker.trim().toUpperCase();
    const priceNum = parseFloat(price);
    if (!sym || !priceNum || isNaN(priceNum) || createRef.current) return;
    createRef.current = true;
    setCreating(true);
    try {
      await alertsAPI.create({
        ticker: sym,
        condition: { operator, price: priceNum },
        name: `${sym} ${operator} ₹${priceNum}`,
      });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setTicker('');
      setPrice('');
      setOperator('above');
      setShowCreate(false);
      await load();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Create failed';
      Alert.alert('Error', String(detail));
    }
    setCreating(false);
    createRef.current = false;
  };

  const toggleAlert = async (id: number, isEnabled: boolean) => {
    try {
      if (isEnabled) {
        await alertsAPI.disable(id);
      } else {
        await alertsAPI.enable(id);
      }
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      await load();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.detail || 'Toggle failed');
    }
  };

  const deleteAlert = (id: number, name: string) => {
    Alert.alert('Delete Alert', `Remove "${name}"?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await alertsAPI.remove(id);
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
            await load();
          } catch (err: any) {
            Alert.alert('Error', err?.response?.data?.detail || 'Delete failed');
          }
        },
      },
    ]);
  };

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  const activeCount = alerts.filter((a) => a.is_enabled).length;

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScreenHeader
          title="Price Alerts"
          subtitle="Get notified when symbols hit your target prices"
          badge={<Tag label={`${activeCount} ACTIVE`} color={Colors.green} bg={Colors.greenBg} />}
        />

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          {/* Add alert toggle */}
          <TouchableOpacity
            style={styles.addBtn}
            onPress={() => { setShowCreate(!showCreate); Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); }}
            activeOpacity={0.8}
          >
            <Ionicons name={showCreate ? 'close-outline' : 'notifications-outline'} size={18} color={Colors.accent} />
            <Text style={styles.addBtnText}>{showCreate ? 'Cancel' : 'New Alert'}</Text>
          </TouchableOpacity>

          {showCreate && (
            <GlassCard style={styles.card}>
              <Text style={styles.sectionTitle}>Create Price Alert</Text>

              <Text style={styles.label}>Symbol</Text>
              <TextInput
                style={styles.input}
                value={ticker}
                onChangeText={setTicker}
                placeholder="e.g. NIFTY, RELIANCE"
                placeholderTextColor={Colors.textFaint}
                autoCapitalize="characters"
              />

              <Text style={styles.label}>Condition</Text>
              <View style={styles.pillRow}>
                {OPERATORS.map((op) => (
                  <TouchableOpacity
                    key={op.key}
                    style={[styles.pill, operator === op.key && styles.pillActive]}
                    onPress={() => setOperator(op.key)}
                    activeOpacity={0.8}
                  >
                    <Text style={[styles.pillText, operator === op.key && styles.pillTextActive]}>{op.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={styles.label}>Target Price (₹)</Text>
              <TextInput
                style={styles.input}
                value={price}
                onChangeText={setPrice}
                keyboardType="decimal-pad"
                placeholder="e.g. 22500"
                placeholderTextColor={Colors.textFaint}
              />

              {ticker && price ? (
                <View style={styles.previewBox}>
                  <Ionicons name="information-circle-outline" size={14} color={Colors.accent} />
                  <Text style={styles.previewText}>
                    Notify when <Text style={{ color: Colors.textPrimary, fontWeight: '700' }}>{ticker.toUpperCase()}</Text>
                    {' '}{OPERATORS.find((o) => o.key === operator)?.label.toLowerCase() || operator}{' '}
                    <Text style={{ color: Colors.accent, fontWeight: '700' }}>₹{price}</Text>
                  </Text>
                </View>
              ) : null}

              <PrimaryButton title="Create Alert" onPress={createAlert} loading={creating} variant="primary" style={{ marginTop: 8 }} />
            </GlassCard>
          )}

          {alerts.length === 0 ? (
            <EmptyState icon="🔔" title="No Alerts" subtitle="Create your first price alert to get notified." />
          ) : (
            alerts.map((alert) => {
              const cond = alert.condition || {};
              const opLabel = OPERATORS.find((o) => o.key === cond.operator)?.label || cond.operator || '';
              const triggered = !!alert.triggered_at;
              const enabled = !!alert.is_enabled;

              return (
                <GlassCard key={alert.id} style={styles.alertCard}>
                  <View style={styles.alertHeader}>
                    <View style={{ flex: 1 }}>
                      <View style={styles.alertTitleRow}>
                        <Text style={styles.alertTicker}>{alert.ticker}</Text>
                        {triggered && (
                          <Tag label="TRIGGERED" color={Colors.green} bg={Colors.greenBg} />
                        )}
                        {!enabled && !triggered && (
                          <Tag label="PAUSED" color={Colors.textMuted} bg={Colors.bgGlass} />
                        )}
                      </View>
                      <Text style={styles.alertCondition}>
                        {opLabel} ₹{Number(cond.price || 0).toLocaleString('en-IN')}
                      </Text>
                      {alert.name && alert.name !== `${alert.ticker} ${cond.operator} ₹${cond.price}` && (
                        <Text style={styles.alertName}>{alert.name}</Text>
                      )}
                    </View>

                    <View style={styles.alertActions}>
                      <TouchableOpacity
                        onPress={() => toggleAlert(alert.id, enabled)}
                        style={[styles.iconBtn, enabled && styles.iconBtnActive]}
                        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                      >
                        <Ionicons
                          name={enabled ? 'notifications' : 'notifications-off-outline'}
                          size={18}
                          color={enabled ? Colors.green : Colors.textMuted}
                        />
                      </TouchableOpacity>
                      <TouchableOpacity
                        onPress={() => deleteAlert(alert.id, alert.name || alert.ticker)}
                        style={styles.iconBtn}
                        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                      >
                        <Ionicons name="trash-outline" size={16} color={Colors.red} />
                      </TouchableOpacity>
                    </View>
                  </View>

                  {alert.triggered_at && (
                    <Text style={styles.triggeredText}>
                      Triggered: {new Date(alert.triggered_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                    </Text>
                  )}
                </GlassCard>
              );
            })
          )}

          <View style={{ height: 96 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safe: { flex: 1 },
  scroll: { padding: Spacing.lg },
  addBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.accentSoft,
    backgroundColor: Colors.bgGlass,
    marginBottom: 12,
    alignSelf: 'flex-start',
  },
  addBtnText: { fontSize: 14, fontWeight: '600', color: Colors.accent },
  card: { marginBottom: 12 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: Colors.textPrimary, marginBottom: 12 },
  label: { fontSize: 12, fontWeight: '600', color: Colors.textMuted, marginBottom: 6, textTransform: 'uppercase' },
  input: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass,
    color: Colors.textPrimary,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    marginBottom: 12,
  },
  pillRow: { flexDirection: 'row', gap: 6, marginBottom: 12, flexWrap: 'wrap' },
  pill: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: Radius.sm,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.bgGlass,
  },
  pillActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  pillText: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary },
  pillTextActive: { color: Colors.accentLight },
  previewBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: Colors.accentSoft,
    borderRadius: Radius.sm,
    paddingHorizontal: 10,
    paddingVertical: 7,
    marginBottom: 8,
  },
  previewText: { flex: 1, fontSize: 13, color: Colors.textSecondary },
  alertCard: { marginBottom: 10 },
  alertHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  alertTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 3 },
  alertTicker: { fontSize: 16, fontWeight: '700', color: Colors.textPrimary },
  alertCondition: { fontSize: 14, color: Colors.accent, fontWeight: '600' },
  alertName: { fontSize: 11, color: Colors.textMuted, marginTop: 2 },
  alertActions: { flexDirection: 'row', gap: 6, alignItems: 'center' },
  iconBtn: { padding: 6, borderRadius: Radius.sm },
  iconBtnActive: { backgroundColor: Colors.greenBg },
  triggeredText: { fontSize: 11, color: Colors.green, marginTop: 6, fontWeight: '500' },
});
