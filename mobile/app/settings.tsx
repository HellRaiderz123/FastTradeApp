import React, { useCallback, useEffect, useState } from 'react';
import { Alert, RefreshControl, ScrollView, StatusBar, StyleSheet, Switch, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import {
  authAPI,
  getAiApiBaseUrl,
  getApiBaseUrl,
  getDefaultAiApiBaseUrl,
  getDefaultApiBaseUrl,
  persistAiApiBaseUrl,
  persistApiBaseUrl,
  syncAiApiBaseUrlFromStorage,
  syncApiBaseUrlFromStorage,
  systemAPI,
} from '../lib/api';
import { useAuthStore } from '../lib/auth';
import { Colors, Radius, Spacing, Gradients } from '../lib/theme';
import { GlassCard, LoadingSpinner, PrimaryButton, ScreenHeader, Tag } from '../components/ui';

type ToggleState = {
  faceId: boolean;
  pushAlerts: boolean;
  tradeHaptics: boolean;
  compactCharts: boolean;
};

export default function SettingsScreen() {
  const biometricEnabled = useAuthStore((state) => state.biometricEnabled);
  const biometricAvailable = useAuthStore((state) => state.biometricAvailable);
  const setBiometricEnabled = useAuthStore((state) => state.setBiometricEnabled);
  const signOut = useAuthStore((state) => state.signOut);
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
  const [aiApiBaseInput, setAiApiBaseInput] = useState('');
  const [savingApiBase, setSavingApiBase] = useState(false);
  const [savingAiApiBase, setSavingAiApiBase] = useState(false);

  const load = useCallback(async () => {
    try {
      const resolvedApiBase = await syncApiBaseUrlFromStorage();
      const resolvedAiApiBase = await syncAiApiBaseUrlFromStorage();
      setApiBaseInput(resolvedApiBase);
      setAiApiBaseInput(resolvedAiApiBase);

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
      setToggles((prev) => ({ ...prev, faceId: biometricEnabled }));
    } catch {}

    setLoading(false);
    setRefreshing(false);
  }, [biometricEnabled]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setToggles((prev) => ({ ...prev, faceId: biometricEnabled }));
  }, [biometricEnabled]);

  const setToggle = async (key: keyof ToggleState) => {
    if (key === 'faceId') {
      const nextValue = !toggles.faceId;
      const result = await setBiometricEnabled(nextValue);
      if (!result.ok) {
        Alert.alert('Face ID unavailable', result.reason || 'Biometric authentication is not available on this device.');
      }
      setToggles((prev) => ({ ...prev, faceId: result.ok ? nextValue : false }));
      return;
    }

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
    } catch {
      Alert.alert('Action failed', 'Could not update trading engine status. Check backend connectivity and try again.');
    }
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

  const handleSaveAiApiBase = async () => {
    const nextUrl = aiApiBaseInput.trim();
    const isValid = /^https?:\/\/.+/i.test(nextUrl);
    if (!isValid) {
      Alert.alert('Invalid URL', 'Use a full URL like http://192.168.1.5:8000 or https://api.example.com');
      return;
    }

    setSavingAiApiBase(true);
    try {
      await persistAiApiBaseUrl(nextUrl);
      setAiApiBaseInput(getAiApiBaseUrl());
      Alert.alert('Saved', 'AI URL updated for future requests.');
    } catch {
      Alert.alert('Failed', 'Could not save AI URL. Please try again.');
    }
    setSavingAiApiBase(false);
  };

  const handleResetApiBase = async () => {
    const fallbackUrl = getDefaultApiBaseUrl();
    setSavingApiBase(true);
    try {
      await persistApiBaseUrl(fallbackUrl);
      setApiBaseInput(getApiBaseUrl());
      Alert.alert('Reset complete', 'Backend URL was reset to the app default.');
    } catch {
      setApiBaseInput(fallbackUrl);
      Alert.alert('Reset failed', 'Could not persist the default backend URL.');
    }
    setSavingApiBase(false);
  };

  const handleResetAiApiBase = async () => {
    const fallbackUrl = getDefaultAiApiBaseUrl();
    setSavingAiApiBase(true);
    try {
      await persistAiApiBaseUrl(fallbackUrl);
      setAiApiBaseInput(getAiApiBaseUrl());
      Alert.alert('Reset complete', 'AI URL was reset to the app default.');
    } catch {
      setAiApiBaseInput(fallbackUrl);
      Alert.alert('Reset failed', 'Could not persist the default AI URL.');
    }
    setSavingAiApiBase(false);
  };

  const handleLogout = () => {
    Alert.alert('Sign Out', 'This will clear your mobile session.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign Out',
        style: 'destructive',
        onPress: async () => {
          await signOut();
        },
      },
    ]);
  };

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safeArea}>
        <ScreenHeader
          title="Settings"
          subtitle="Personalize your app and backend connection"
          badge={<Tag label={systemEnabled ? 'ENGINE ON' : 'ENGINE OFF'} color={systemEnabled ? Colors.green : Colors.red} bg={systemEnabled ? Colors.greenBg : Colors.redBg} />}
        />

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
            <View style={styles.infoBlock}>
              <InfoRow label="API" value={getApiBaseUrl()} />
              <InfoRow label="AI API" value={getAiApiBaseUrl()} />
              <InfoRow label="Biometric" value={toggles.faceId ? 'Enabled' : 'Disabled'} />
            </View>
          </GlassCard>

          <GlassCard style={styles.sectionCard}>
            <Text style={styles.sectionTitle}>Experience</Text>
            <SettingRow title="Face ID unlock" subtitle="Keep app access instant and private" value={toggles.faceId} onToggle={() => setToggle('faceId')} />
            {!biometricAvailable ? <Text style={styles.noteText}>Biometric unlock is not available or not enrolled on this device.</Text> : null}
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
              placeholder="http://10.0.2.2:8000 or http://192.168.1.x:8000"
              placeholderTextColor={Colors.textFaint}
              style={styles.urlInput}
            />
            <View style={styles.connectionActions}>
              <PrimaryButton title="Save URL" onPress={handleSaveApiBase} loading={savingApiBase} style={styles.connectionButton} />
              <PrimaryButton title="Reset" onPress={handleResetApiBase} variant="ghost" style={styles.connectionButton} />
            </View>
            <Text style={styles.connectionHint}>Tip: use `10.0.2.2` for Android emulator, `127.0.0.1`/`localhost` for iOS simulator, and your PC&apos;s LAN IP on a real phone.</Text>
            <InfoRow label="Active URL" value={getApiBaseUrl()} />
            <Text style={[styles.inputLabel, { marginTop: 10 }]}>AI Base URL</Text>
            <TextInput
              value={aiApiBaseInput}
              onChangeText={setAiApiBaseInput}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="http://10.0.2.2:8000 or http://192.168.1.x:8000"
              placeholderTextColor={Colors.textFaint}
              style={styles.urlInput}
            />
            <View style={styles.connectionActions}>
              <PrimaryButton title="Save AI URL" onPress={handleSaveAiApiBase} loading={savingAiApiBase} style={styles.connectionButton} />
              <PrimaryButton title="Reset AI" onPress={handleResetAiApiBase} variant="ghost" style={styles.connectionButton} />
            </View>
            <InfoRow label="Active AI URL" value={getAiApiBaseUrl()} />
            <InfoRow label="Theme" value="Metallic Night" />
            <InfoRow label="Layout" value="Expo Router tabs" />
          </GlassCard>

<PrimaryButton title="Sign Out" onPress={handleLogout} variant="danger" style={{ marginBottom: 12 }} />

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
  infoBlock: { marginTop: 14, borderTopWidth: 1, borderTopColor: Colors.border, paddingTop: 10 },
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
