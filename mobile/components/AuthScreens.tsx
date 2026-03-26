import React, { useMemo, useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, StatusBar, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Gradients, Radius, Spacing } from '../lib/theme';
import { GlassCard, PrimaryButton, Tag } from './ui';
import { useAuthStore } from '../lib/auth';

export function LoginScreen() {
  const signIn = useAuthStore((state) => state.signIn);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const canSubmit = useMemo(() => username.trim().length > 0 && password.length > 0 && !loading, [username, password, loading]);

  const handleSignIn = async () => {
    if (!canSubmit) return;
    setLoading(true);
    setError('');
    try {
      await signIn(username.trim(), password);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Login failed. Please try again.';
      setError(String(detail));
    }
    setLoading(false);
  };

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <LinearGradient colors={Gradients.header} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={styles.safeArea}>
        <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <View style={styles.loginWrap}>
            <GlassCard style={styles.loginCard}>
              <View style={styles.brandWrap}>
                <View style={styles.logoBadge}>
                  <Ionicons name="pulse-outline" size={24} color={Colors.accentLight} />
                </View>
                <Text style={styles.title}>FastTrade Mobile</Text>
                <Text style={styles.subtitle}>Sign in to access your trading workspace</Text>
                <Tag label="SECURE LOGIN" color={Colors.green} bg={Colors.greenBg} />
              </View>

              {error ? (
                <View style={styles.errorBox}>
                  <Text style={styles.errorText}>{error}</Text>
                </View>
              ) : null}

              <View style={styles.fieldWrap}>
                <Text style={styles.label}>Username</Text>
                <TextInput
                  value={username}
                  onChangeText={setUsername}
                  autoCapitalize="none"
                  autoCorrect={false}
                  placeholder="Enter username"
                  placeholderTextColor={Colors.textMuted}
                  style={styles.input}
                />
              </View>

              <View style={styles.fieldWrap}>
                <Text style={styles.label}>Password</Text>
                <View style={styles.passwordWrap}>
                  <TextInput
                    value={password}
                    onChangeText={setPassword}
                    secureTextEntry={!showPassword}
                    autoCapitalize="none"
                    autoCorrect={false}
                    placeholder="Enter password"
                    placeholderTextColor={Colors.textMuted}
                    style={styles.passwordInput}
                  />
                  <TouchableOpacity onPress={() => setShowPassword((prev) => !prev)} style={styles.eyeButton}>
                    <Ionicons name={showPassword ? 'eye-off-outline' : 'eye-outline'} size={18} color={Colors.textSecondary} />
                  </TouchableOpacity>
                </View>
              </View>

              <PrimaryButton title="Sign In" onPress={handleSignIn} disabled={!canSubmit} loading={loading} />
            </GlassCard>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}

export function BiometricLockScreen() {
  const unlockWithBiometrics = useAuthStore((state) => state.unlockWithBiometrics);
  const signOut = useAuthStore((state) => state.signOut);
  const user = useAuthStore((state) => state.user);
  const [loading, setLoading] = useState(false);

  const handleUnlock = async () => {
    setLoading(true);
    const success = await unlockWithBiometrics();
    if (!success) {
      Alert.alert('Unlock failed', 'Biometric authentication was cancelled or unsuccessful.');
    }
    setLoading(false);
  };

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <LinearGradient colors={Gradients.header} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.lockWrap}>
          <GlassCard style={styles.lockCard}>
            <View style={styles.lockIconWrap}>
              <Ionicons name="shield-checkmark-outline" size={36} color={Colors.accentLight} />
            </View>
            <Text style={styles.title}>Unlock FastTrade</Text>
            <Text style={styles.subtitle}>{user?.username ? `Signed in as ${user.username}` : 'Authenticate to continue'}</Text>
            <PrimaryButton title="Unlock" onPress={handleUnlock} loading={loading} style={{ marginTop: 10 }} />
            <TouchableOpacity onPress={() => signOut()} style={styles.secondaryAction}>
              <Text style={styles.secondaryActionText}>Sign out instead</Text>
            </TouchableOpacity>
          </GlassCard>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safeArea: { flex: 1 },
  flex: { flex: 1 },
  loginWrap: { flex: 1, justifyContent: 'center', padding: Spacing.lg },
  loginCard: { padding: Spacing.lg },
  brandWrap: { alignItems: 'center', marginBottom: 18 },
  logoBadge: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: Colors.accentGlow,
    borderWidth: 1,
    borderColor: Colors.borderAccent,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  title: { color: Colors.textPrimary, fontSize: 24, fontWeight: '700', marginBottom: 6, textAlign: 'center' },
  subtitle: { color: Colors.textSecondary, fontSize: 13, textAlign: 'center', marginBottom: 10 },
  errorBox: {
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.35)',
    backgroundColor: Colors.redBg,
    borderRadius: Radius.md,
    padding: 12,
    marginBottom: 14,
  },
  errorText: { color: Colors.redLight, fontSize: 13, fontWeight: '600' },
  fieldWrap: { marginBottom: 14 },
  label: { color: Colors.textMuted, fontSize: 12, marginBottom: 6 },
  input: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass,
    color: Colors.textPrimary,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 14,
  },
  passwordWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass,
  },
  passwordInput: { flex: 1, color: Colors.textPrimary, paddingHorizontal: 12, paddingVertical: 12, fontSize: 14 },
  eyeButton: { paddingHorizontal: 12, paddingVertical: 12 },
  lockWrap: { flex: 1, justifyContent: 'center', padding: Spacing.lg },
  lockCard: { padding: Spacing.xl, alignItems: 'center' },
  lockIconWrap: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: Colors.accentGlow,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
    borderWidth: 1,
    borderColor: Colors.borderAccent,
  },
  secondaryAction: { marginTop: 16, padding: 8 },
  secondaryActionText: { color: Colors.textSecondary, fontSize: 13, fontWeight: '600' },
});
