import React, { useCallback, useEffect, useState } from 'react';
import { Alert, RefreshControl, ScrollView, StatusBar, StyleSheet, Switch, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { authAPI, getApiBaseUrl, getDefaultApiBaseUrl, persistApiBaseUrl, syncApiBaseUrlFromStorage, systemAPI } from '../lib/api';
import { Colors, Radius, Spacing, Gradients } from '../lib/theme';
import { GlassCard, LoadingSpinner, PrimaryButton, Tag } from '../components/ui';

type ToggleState = {
  faceId: boolean;
  pushAlerts: boolean;
  tradeHaptics: boolean;
  compactCharts: boolean;
};

export default function SettingsScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [systemEnabled, setSystemEnabled] = useState(false);
  const [profileName, setProfileName] = useState('FastTrade Operator');
  const [toggles, setToggles] = useState<ToggleState>({
    faceId: true,
    pushAlerts: true,
    tradeHaptics: true,
    compactCharts: false,
  });
  const [apiBaseInput, setApiBaseInput] = useState('');
  const [savingApiBase, setSavingApiBase] = useState(false);

  const load = useCallback(async () => {
    try {
      const resolvedApiBase = await syncApiBaseUrlFromStorage();
      setApiBaseInput(resolvedApiBase);

      const [systemRes, profileRes] = await Promise.allSettled([
        systemAPI.status(),
        authAPI.me(),
      ]);

      if (systemRes.status === 'fulfilled') {
        setSystemEnabled(Boolean(systemRes.value.data?.trading_enabled));
      }
      if (profileRes.status === 'fulfilled') {
        const data = profileRes.value.data;
        setProfileName(data?.username || data?.email || 'FastTrade Operator');
      }
    } catch {}

    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const setToggle = (key: keyof ToggleState) => {
    setToggles((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleTradingToggle = async () => {
    try {
      if (systemEnabled) {
        await systemAPI.disable();
        setSystemEnabled(false);
      } else {
        await systemAPI.enable();
        setSystemEnabled(true);
      }
    } catch {}
  };

  const handleSaveApiBase = async () => {
    const nextUrl = apiBaseInput.trim();
    const isValid = /^https?:\/\/.+/i.test(nextUrl);
    if (!isValid) {
      Alert.alert('Invalid URL', 'Use a full URL like http://192.168.1.5:8000 or https://api.example.com');
      return;
    }

    setSavingApiBase(true);
    try {
      await persistApiBaseUrl(nextUrl);
      setApiBaseInput(getApiBaseUrl());
      Alert.alert('Saved', 'Backend URL updated for future requests.');
    } catch {
      Alert.alert('Failed', 'Could not save backend URL. Please try again.');
    }
    setSavingApiBase(false);
  };

  const handleResetApiBase = () => {
    const fallbackUrl = getDefaultApiBaseUrl();
    setApiBaseInput(fallbackUrl);
  };

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safeArea}>
        <LinearGradient colors={Gradients.header} style={styles.header}>
          <Text style={styles.headerTitle}>Settings</Text>
          <Text style={styles.headerSub}>Personalize your app and backend connection</Text>
        </LinearGradient>

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          <GlassCard style={styles.profileCard}>
            <View style={styles.profileTop}>
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>{profileName.slice(0, 2).toUpperCase()}</Text>
              </View>
              <View style={styles.profileMeta}>
                <Text style={styles.profileName}>{profileName}</Text>
                <Text style={styles.profileSub}>Metallic iPhone command center</Text>
              </View>
            </View>
            <View style={styles.statusRow}>
              <Text style={styles.rowLabel}>Trading Engine</Text>
              <View style={styles.rowRight}>
                <Tag
                  label={systemEnabled ? 'ENABLED' : 'DISABLED'}
                  color={systemEnabled ? Colors.green : Colors.red}
                  bg={systemEnabled ? Colors.greenBg : Colors.redBg}
                />
                <Switch
                  value={systemEnabled}
                  onValueChange={handleTradingToggle}
                  trackColor={{ false: Colors.bgGlassStrong, true: Colors.greenGlow }}
                  thumbColor={systemEnabled ? Colors.green : '#D1D5DB'}
                />
              </View>
            </View>
          </GlassCard>

          <GlassCard style={styles.sectionCard}>
            <Text style={styles.sectionTitle}>Experience</Text>
            <SettingRow title="Face ID unlock" subtitle="Keep app access instant and private" value={toggles.faceId} onToggle={() => setToggle('faceId')} />
            <SettingRow title="Push alerts" subtitle="Trade events, scanner hits, and AI summaries" value={toggles.pushAlerts} onToggle={() => setToggle('pushAlerts')} />
            <SettingRow title="Trade haptics" subtitle="Subtle feedback on action taps and confirmations" value={toggles.tradeHaptics} onToggle={() => setToggle('tradeHaptics')} />
            <SettingRow title="Compact charts" subtitle="Denser summaries for smaller market cards" value={toggles.compactCharts} onToggle={() => setToggle('compactCharts')} />
          </GlassCard>

          <GlassCard style={styles.sectionCard}>
            <Text style={styles.sectionTitle}>Connection</Text>
            <Text style={styles.inputLabel}>Backend Base URL</Text>
            <TextInput
              value={apiBaseInput}
              onChangeText={setApiBaseInput}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="http://localhost:8000"
              placeholderTextColor={Colors.textFaint}
              style={styles.urlInput}
            />
            <View style={styles.connectionActions}>
              <PrimaryButton title="Save URL" onPress={handleSaveApiBase} loading={savingApiBase} style={styles.connectionButton} />
              <PrimaryButton title="Reset" onPress={handleResetApiBase} variant="ghost" style={styles.connectionButton} />
            </View>
            <Text style={styles.connectionHint}>Tip: use `10.0.2.2` for Android emulator and `localhost` for iOS simulator.</Text>
            <InfoRow label="Active URL" value={getApiBaseUrl()} />
            <InfoRow label="Theme" value="Metallic Night" />
            <InfoRow label="Layout" value="Expo Router tabs" />
          </GlassCard>

          <GlassCard style={styles.sectionCard}>
            <Text style={styles.sectionTitle}>Planned Next</Text>
            <Text style={styles.noteText}>1. Native login flow</Text>
            <Text style={styles.noteText}>2. Push notification registration</Text>
            <Text style={styles.noteText}>3. Live broker and scanner settings sync</Text>
          </GlassCard>

          <TouchableOpacity style={styles.syncButton} activeOpacity={0.85} onPress={() => load()}>
            <LinearGradient colors={Gradients.primaryAction} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.syncGradient}>
              <Text style={styles.syncText}>Refresh Status</Text>
            </LinearGradient>
          </TouchableOpacity>
          <View style={{ height: 100 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

function SettingRow({ title, subtitle, value, onToggle }: { title: string; subtitle: string; value: boolean; onToggle: () => void }) {
  return (
    <View style={styles.settingRow}>
      <View style={styles.settingLeft}>
        <Text style={styles.rowTitle}>{title}</Text>
        <Text style={styles.rowSubtitle}>{subtitle}</Text>
      </View>
      <Switch
        value={value}
        onValueChange={onToggle}
        trackColor={{ false: Colors.bgGlassStrong, true: Colors.accentGlow }}
        thumbColor={value ? Colors.accent : '#D1D5DB'}
      />
    </View>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safeArea: { flex: 1 },
  header: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.lg },
  headerTitle: { fontSize: 28, fontWeight: '700', color: Colors.textPrimary, letterSpacing: -0.5 },
  headerSub: { fontSize: 13, color: Colors.textMuted, marginTop: 2 },
  scroll: { padding: Spacing.lg, flexGrow: 1 },
  profileCard: { marginBottom: 12 },
  profileTop: { flexDirection: 'row', alignItems: 'center', marginBottom: 18 },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: Colors.accentGlow,
    borderWidth: 1,
    borderColor: Colors.borderAccent,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarText: { color: Colors.textPrimary, fontSize: 18, fontWeight: '700' },
  profileMeta: { marginLeft: 14, flex: 1 },
  profileName: { fontSize: 18, fontWeight: '700', color: Colors.textPrimary },
  profileSub: { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  statusRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  rowLabel: { fontSize: 15, fontWeight: '600', color: Colors.textPrimary },
  rowRight: { flexDirection: 'row', alignItems: 'center' },
  sectionCard: { marginBottom: 12 },
  sectionTitle: { fontSize: 17, fontWeight: '700', color: Colors.textPrimary, marginBottom: 8 },
  settingRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 10 },
  settingLeft: { flex: 1, paddingRight: 12 },
  rowTitle: { fontSize: 15, fontWeight: '600', color: Colors.textPrimary },
  rowSubtitle: { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8 },
  infoLabel: { fontSize: 12, color: Colors.textMuted, width: 90 },
  infoValue: { fontSize: 12, color: Colors.textPrimary, fontWeight: '600', flex: 1, textAlign: 'right' },
  inputLabel: { fontSize: 12, color: Colors.textMuted, marginBottom: 6 },
  urlInput: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass,
    color: Colors.textPrimary,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13,
  },
  connectionActions: { flexDirection: 'row', marginTop: 10, marginBottom: 8, gap: 10 },
  connectionButton: { flex: 1 },
  connectionHint: { fontSize: 11, color: Colors.textMuted, marginBottom: 8 },
  noteText: { fontSize: 13, color: Colors.textSecondary, marginBottom: 8 },
  syncButton: { marginTop: 4, borderRadius: Radius.md, overflow: 'hidden' },
  syncGradient: { paddingVertical: 14, alignItems: 'center' },
  syncText: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
