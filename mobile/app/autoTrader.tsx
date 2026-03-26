import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import { Ionicons } from '@expo/vector-icons';
import { autoTraderAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { GlassCard, LoadingSpinner, PrimaryButton, ScreenHeader, Tag } from '../components/ui';

const MODES = ['PAPER', 'DRY_RUN', 'LIVE'] as const;
const RISK_MODES = ['CONSERVATIVE', 'BALANCED', 'AGGRESSIVE'] as const;

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string; bg: string }> = {
    running: { label: 'RUNNING', color: Colors.green, bg: Colors.greenBg },
    paused: { label: 'PAUSED', color: '#F59E0B', bg: 'rgba(245,158,11,0.12)' },
    stopped: { label: 'STOPPED', color: Colors.red, bg: 'rgba(239,68,68,0.12)' },
    idle: { label: 'IDLE', color: Colors.textMuted, bg: Colors.bgGlass },
  };
  const s = map[status?.toLowerCase()] || map.idle;
  return <Tag label={s.label} color={s.color} bg={s.bg} />;
}

export default function AutoTraderScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [status, setStatus] = useState<any>(null);
  const [config, setConfig] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [tab, setTab] = useState<'overview' | 'config' | 'logs'>('overview');
  const [saving, setSaving] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Local editable config state
  const [editCapital, setEditCapital] = useState('');
  const [editLots, setEditLots] = useState('');
  const [editMode, setEditMode] = useState('PAPER');
  const [editRiskMode, setEditRiskMode] = useState('BALANCED');
  const [editMinConf, setEditMinConf] = useState('');
  const [editMaxPos, setEditMaxPos] = useState('');
  const [editMaxLoss, setEditMaxLoss] = useState('');
  const [editScanInterval, setEditScanInterval] = useState('');
  const [editAutoExit, setEditAutoExit] = useState(false);
  const [editMarketHours, setEditMarketHours] = useState(true);
  const actionRef = useRef(false);

  const load = useCallback(async (showLoader = false) => {
    if (showLoader) setLoading(true);
    try {
      const [statusRes, configRes, logsRes] = await Promise.all([
        autoTraderAPI.getStatus(),
        autoTraderAPI.getConfig(),
        autoTraderAPI.getLogs({ limit: 50 }),
      ]);
      setStatus(statusRes.data);
      const cfg = configRes.data;
      setConfig(cfg);
      // Populate editable fields
      setEditCapital(String(cfg.capital || ''));
      setEditLots(String(cfg.lots || ''));
      setEditMode(cfg.mode || 'PAPER');
      setEditRiskMode(cfg.risk_mode || 'BALANCED');
      setEditMinConf(String(cfg.min_confidence ?? ''));
      setEditMaxPos(String(cfg.max_open_positions || ''));
      setEditMaxLoss(String(cfg.max_daily_loss || ''));
      setEditScanInterval(String(cfg.scan_interval_sec || ''));
      setEditAutoExit(!!cfg.auto_exit_on_reversal);
      setEditMarketHours(cfg.market_hours_only !== false);
      const logData = logsRes.data;
      setLogs(Array.isArray(logData) ? logData : logData?.logs || []);
    } catch {
      // silently fail — show whatever we have
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    load(true);
    // poll status every 10s when on overview tab
    const interval = setInterval(() => {
      if (tab === 'overview') {
        autoTraderAPI.getStatus().then((r) => setStatus(r.data)).catch(() => {});
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [load, tab]);

  const onRefresh = () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    load();
  };

  const runAction = async (action: 'start' | 'stop' | 'pause', label: string) => {
    if (actionRef.current) return;
    actionRef.current = true;
    setActionLoading(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    try {
      if (action === 'start') await autoTraderAPI.start();
      else if (action === 'stop') await autoTraderAPI.stop();
      else await autoTraderAPI.pause();
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      await load();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || `${label} failed`;
      Alert.alert('Error', String(detail));
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }
    setActionLoading(false);
    actionRef.current = false;
  };

  const saveConfig = async () => {
    setSaving(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    try {
      await autoTraderAPI.updateConfig({
        capital: Number(editCapital) || undefined,
        lots: Number(editLots) || undefined,
        mode: editMode,
        risk_mode: editRiskMode,
        min_confidence: editMinConf ? Number(editMinConf) : undefined,
        max_open_positions: editMaxPos ? Number(editMaxPos) : undefined,
        max_daily_loss: editMaxLoss ? Number(editMaxLoss) : undefined,
        scan_interval_sec: editScanInterval ? Number(editScanInterval) : undefined,
        auto_exit_on_reversal: editAutoExit,
        market_hours_only: editMarketHours,
      });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      await load();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Save failed';
      Alert.alert('Error', String(detail));
    }
    setSaving(false);
  };

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  const engineStatus = status?.status || 'idle';
  const isRunning = engineStatus === 'running';
  const isPaused = engineStatus === 'paused';
  const dailyPnL = status?.daily_pnl ?? config?.daily_pnl ?? 0;
  const dailyTrades = status?.daily_trades ?? config?.daily_trades ?? 0;

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScreenHeader
          title="Auto Trader"
          subtitle="Autonomous trading engine control"
          badge={<StatusBadge status={engineStatus} />}
        />

        {/* Tab bar */}
        <View style={styles.tabRow}>
          {(['overview', 'config', 'logs'] as const).map((t) => (
            <TouchableOpacity
              key={t}
              style={[styles.tabBtn, tab === t && styles.tabBtnActive]}
              onPress={() => setTab(t)}
              activeOpacity={0.8}
            >
              <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          {tab === 'overview' && (
            <>
              {/* Stats */}
              <View style={styles.statsRow}>
                <GlassCard style={styles.statCard}>
                  <Text style={styles.statLabel}>Daily P&L</Text>
                  <Text style={[styles.statValue, { color: dailyPnL >= 0 ? Colors.green : Colors.red }]}>
                    {dailyPnL >= 0 ? '+' : ''}₹{Math.abs(dailyPnL).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </Text>
                </GlassCard>
                <GlassCard style={styles.statCard}>
                  <Text style={styles.statLabel}>Trades Today</Text>
                  <Text style={styles.statValue}>{dailyTrades}</Text>
                </GlassCard>
                <GlassCard style={styles.statCard}>
                  <Text style={styles.statLabel}>Mode</Text>
                  <Text style={[styles.statValue, { fontSize: 13 }]}>{config?.mode || '—'}</Text>
                </GlassCard>
              </View>

              {/* Control buttons */}
              <GlassCard style={styles.card}>
                <Text style={styles.sectionTitle}>Engine Control</Text>
                <View style={styles.controlRow}>
                  <PrimaryButton
                    title="Start"
                    variant="success"
                    small
                    style={[styles.ctrlBtn, (isRunning || actionLoading) && { opacity: 0.4 }]}
                    disabled={isRunning || actionLoading}
                    onPress={() => runAction('start', 'Start')}
                  />
                  <PrimaryButton
                    title={isPaused ? 'Resume' : 'Pause'}
                    variant="primary"
                    small
                    style={[styles.ctrlBtn, (!isRunning && !isPaused) && { opacity: 0.4 }]}
                    disabled={!isRunning && !isPaused || actionLoading}
                    onPress={() => runAction('pause', 'Pause')}
                  />
                  <PrimaryButton
                    title="Stop"
                    variant="danger"
                    small
                    style={[styles.ctrlBtn, (!isRunning && !isPaused) && { opacity: 0.4 }]}
                    disabled={!isRunning && !isPaused || actionLoading}
                    onPress={() => {
                      Alert.alert('Stop Auto Trader', 'This will halt all automated trading. Continue?', [
                        { text: 'Cancel', style: 'cancel' },
                        { text: 'Stop', style: 'destructive', onPress: () => runAction('stop', 'Stop') },
                      ]);
                    }}
                  />
                </View>
              </GlassCard>

              {/* Info */}
              <GlassCard style={styles.card}>
                <Text style={styles.sectionTitle}>Configuration Summary</Text>
                {[
                  ['Capital', `₹${Number(config?.capital || 0).toLocaleString('en-IN')}`],
                  ['Lots', String(config?.lots || 0)],
                  ['Risk Mode', config?.risk_mode || '—'],
                  ['Min Confidence', `${config?.min_confidence ?? '—'}`],
                  ['Max Positions', String(config?.max_open_positions || '—')],
                  ['Max Daily Loss', config?.max_daily_loss ? `₹${config.max_daily_loss}` : '—'],
                  ['Scan Interval', config?.scan_interval_sec ? `${config.scan_interval_sec}s` : '—'],
                  ['Market Hours Only', config?.market_hours_only ? 'Yes' : 'No'],
                ].map(([label, val]) => (
                  <View key={label} style={styles.infoRow}>
                    <Text style={styles.infoLabel}>{label}</Text>
                    <Text style={styles.infoValue}>{val}</Text>
                  </View>
                ))}
              </GlassCard>
            </>
          )}

          {tab === 'config' && (
            <GlassCard style={styles.card}>
              <Text style={styles.sectionTitle}>Edit Configuration</Text>

              <Text style={styles.label}>Mode</Text>
              <View style={styles.pillRow}>
                {MODES.map((m) => (
                  <TouchableOpacity
                    key={m}
                    style={[styles.pill, editMode === m && styles.pillActive]}
                    onPress={() => setEditMode(m)}
                    activeOpacity={0.8}
                  >
                    <Text style={[styles.pillText, editMode === m && styles.pillTextActive]}>{m}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              {editMode === 'LIVE' && (
                <Text style={styles.warnText}>⚠️ LIVE mode uses real broker orders. Use with caution.</Text>
              )}

              <Text style={styles.label}>Risk Mode</Text>
              <View style={styles.pillRow}>
                {RISK_MODES.map((m) => (
                  <TouchableOpacity
                    key={m}
                    style={[styles.pill, editRiskMode === m && styles.pillActive]}
                    onPress={() => setEditRiskMode(m)}
                    activeOpacity={0.8}
                  >
                    <Text style={[styles.pillText, editRiskMode === m && styles.pillTextActive]}>{m.slice(0, 4)}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <ConfigInput label="Capital (₹)" value={editCapital} onChange={setEditCapital} keyboardType="numeric" />
              <ConfigInput label="Lots" value={editLots} onChange={setEditLots} keyboardType="number-pad" />
              <ConfigInput label="Min Confidence (0–1)" value={editMinConf} onChange={setEditMinConf} keyboardType="decimal-pad" />
              <ConfigInput label="Max Open Positions" value={editMaxPos} onChange={setEditMaxPos} keyboardType="number-pad" />
              <ConfigInput label="Max Daily Loss (₹)" value={editMaxLoss} onChange={setEditMaxLoss} keyboardType="numeric" />
              <ConfigInput label="Scan Interval (sec)" value={editScanInterval} onChange={setEditScanInterval} keyboardType="number-pad" />

              <View style={styles.switchRow}>
                <Text style={styles.switchLabel}>Auto-exit on Reversal</Text>
                <Switch
                  value={editAutoExit}
                  onValueChange={setEditAutoExit}
                  trackColor={{ true: Colors.green, false: Colors.border }}
                  thumbColor="#fff"
                />
              </View>
              <View style={styles.switchRow}>
                <Text style={styles.switchLabel}>Market Hours Only</Text>
                <Switch
                  value={editMarketHours}
                  onValueChange={setEditMarketHours}
                  trackColor={{ true: Colors.accent, false: Colors.border }}
                  thumbColor="#fff"
                />
              </View>

              <PrimaryButton title="Save Configuration" onPress={saveConfig} loading={saving} variant="primary" style={{ marginTop: 12 }} />
            </GlassCard>
          )}

          {tab === 'logs' && (
            <GlassCard style={styles.card}>
              <Text style={styles.sectionTitle}>Engine Logs</Text>
              {logs.length === 0 ? (
                <Text style={styles.emptyText}>No logs available</Text>
              ) : (
                logs.slice(0, 80).map((log: any, i) => {
                  const level = (log.level || log.log_level || '').toUpperCase();
                  const color = level === 'ERROR' ? Colors.red : level === 'WARNING' ? '#F59E0B' : Colors.textSecondary;
                  const msg = log.message || log.msg || JSON.stringify(log);
                  const ts = log.timestamp || log.created_at || '';
                  const timeStr = ts ? new Date(ts).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';
                  return (
                    <View key={i} style={styles.logRow}>
                      <Text style={[styles.logLevel, { color }]}>{level || 'INFO'}</Text>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.logMsg} numberOfLines={2}>{msg}</Text>
                        {timeStr ? <Text style={styles.logTime}>{timeStr}</Text> : null}
                      </View>
                    </View>
                  );
                })
              )}
            </GlassCard>
          )}

          <View style={{ height: 96 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

function ConfigInput({
  label,
  value,
  onChange,
  keyboardType = 'default',
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  keyboardType?: any;
}) {
  return (
    <View style={styles.configInputGroup}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        style={styles.input}
        value={value}
        onChangeText={onChange}
        keyboardType={keyboardType}
        placeholderTextColor={Colors.textFaint}
        placeholder="—"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safe: { flex: 1 },
  scroll: { padding: Spacing.lg },
  tabRow: {
    flexDirection: 'row',
    marginHorizontal: Spacing.lg,
    marginBottom: 12,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass,
    borderWidth: 1,
    borderColor: Colors.border,
    overflow: 'hidden',
  },
  tabBtn: { flex: 1, paddingVertical: 9, alignItems: 'center' },
  tabBtnActive: { backgroundColor: Colors.accentSoft },
  tabText: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5 },
  tabTextActive: { color: Colors.accentLight },
  statsRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  statCard: { flex: 1, alignItems: 'center', paddingVertical: 12 },
  statLabel: { fontSize: 11, color: Colors.textMuted, marginBottom: 4 },
  statValue: { fontSize: 16, fontWeight: '700', color: Colors.textPrimary },
  card: { marginBottom: 12 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: Colors.textPrimary, marginBottom: 12 },
  controlRow: { flexDirection: 'row', gap: 8 },
  ctrlBtn: { flex: 1 },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: Colors.border },
  infoLabel: { fontSize: 13, color: Colors.textSecondary },
  infoValue: { fontSize: 13, fontWeight: '600', color: Colors.textPrimary },
  label: { fontSize: 12, fontWeight: '600', color: Colors.textMuted, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 },
  pillRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  pill: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: Radius.sm,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.bgGlass,
  },
  pillActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  pillText: { fontSize: 11, fontWeight: '700', color: Colors.textSecondary, letterSpacing: 0.4 },
  pillTextActive: { color: Colors.accentLight },
  warnText: { fontSize: 12, color: '#F59E0B', marginTop: -6, marginBottom: 10 },
  configInputGroup: { marginBottom: 10 },
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
  switchRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 8 },
  switchLabel: { fontSize: 14, color: Colors.textSecondary },
  logRow: { flexDirection: 'row', gap: 8, paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: Colors.border },
  logLevel: { fontSize: 10, fontWeight: '700', width: 40, paddingTop: 2, letterSpacing: 0.3 },
  logMsg: { fontSize: 12, color: Colors.textSecondary, lineHeight: 17 },
  logTime: { fontSize: 10, color: Colors.textFaint, marginTop: 2 },
  emptyText: { color: Colors.textMuted, textAlign: 'center', paddingVertical: 24 },
});
