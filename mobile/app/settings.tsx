import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  SafeAreaView,
  TextInput,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  Switch,
} from 'react-native';
import { settingsAPI } from '../../lib/api';

export default function SettingsScreen() {
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [executionMode, setExecutionMode] = useState('ZERODHA_DRY_RUN');
  const [loading, setLoading] = useState(false);
  const [savedStatus, setSavedStatus] = useState({
    api_key: false,
    access_token: false,
  });
  const [showApiSecret, setShowApiSecret] = useState(false);
  const [showAccessToken, setShowAccessToken] = useState(false);

  // Load current settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const response = await settingsAPI.getZerodhaSettings();
      setSavedStatus(response);
      setExecutionMode(response.execution_mode || 'ZERODHA_DRY_RUN');
    } catch (error) {
      console.error('Error loading settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveCredentials = async () => {
    if (!apiKey.trim() || !apiSecret.trim()) {
      Alert.alert('Error', 'Please enter both API Key and API Secret');
      return;
    }

    try {
      setLoading(true);
      await settingsAPI.saveZerodhaCredentials({
        api_key: apiKey,
        api_secret: apiSecret,
      });
      Alert.alert('Success', 'Zerodha credentials saved successfully');
      setSavedStatus((prev) => ({ ...prev, api_key: true }));
    } catch (error) {
      Alert.alert('Error', error.message || 'Failed to save credentials');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveToken = async () => {
    if (!accessToken.trim()) {
      Alert.alert('Error', 'Please enter an access token');
      return;
    }

    try {
      setLoading(true);
      await settingsAPI.saveZerodhaToken({
        access_token: accessToken,
      });
      Alert.alert('Success', 'Access token saved successfully');
      setSavedStatus((prev) => ({ ...prev, access_token: true }));
    } catch (error) {
      Alert.alert('Error', error.message || 'Failed to save token');
    } finally {
      setLoading(false);
    }
  };

  const handleExecutionModeChange = async (mode: string) => {
    try {
      setLoading(true);
      await settingsAPI.setExecutionMode(mode);
      setExecutionMode(mode);
      Alert.alert('Success', `Execution mode changed to ${mode}`);
    } catch (error) {
      Alert.alert('Error', error.message || 'Failed to change execution mode');
    } finally {
      setLoading(false);
    }
  };

  const modes = ['ZERODHA_LIVE', 'ZERODHA_DRY_RUN', 'PAPER_TRADING'];

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Text style={styles.title}>Settings ⚙️</Text>

        {/* Status Section */}
        <View style={styles.statusSection}>
          <Text style={styles.sectionTitle}>Connection Status</Text>
          <View style={styles.statusRow}>
            <Text style={styles.statusLabel}>API Key:</Text>
            <View
              style={[
                styles.statusBadge,
                savedStatus.api_key ? styles.statusGood : styles.statusBad,
              ]}
            >
              <Text style={styles.statusText}>
                {savedStatus.api_key ? '✓ Configured' : '✗ Not Set'}
              </Text>
            </View>
          </View>
          <View style={styles.statusRow}>
            <Text style={styles.statusLabel}>Access Token:</Text>
            <View
              style={[
                styles.statusBadge,
                savedStatus.access_token ? styles.statusGood : styles.statusBad,
              ]}
            >
              <Text style={styles.statusText}>
                {savedStatus.access_token ? '✓ Configured' : '✗ Not Set'}
              </Text>
            </View>
          </View>
        </View>

        {/* API Credentials Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Zerodha API Credentials</Text>
          <Text style={styles.sectionDescription}>
            Enter your Zerodha API credentials. Get them from your Zerodha developer
            console.
          </Text>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>API Key</Text>
            <TextInput
              style={styles.input}
              placeholder="el4pv3dwria188j9"
              value={apiKey}
              onChangeText={setApiKey}
              editable={!loading}
              placeholderTextColor="#999"
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>API Secret</Text>
            <View style={styles.passwordContainer}>
              <TextInput
                style={styles.inputPassword}
                placeholder="your-api-secret"
                value={apiSecret}
                onChangeText={setApiSecret}
                secureTextEntry={!showApiSecret}
                editable={!loading}
                placeholderTextColor="#999"
              />
              <TouchableOpacity
                onPress={() => setShowApiSecret(!showApiSecret)}
                style={styles.eyeIcon}
              >
                <Text>{showApiSecret ? '👁️' : '👁️‍🗨️'}</Text>
              </TouchableOpacity>
            </View>
          </View>

          <TouchableOpacity
            style={[styles.button, styles.primaryButton, loading && styles.buttonDisabled]}
            onPress={handleSaveCredentials}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Save Credentials</Text>
            )}
          </TouchableOpacity>
        </View>

        {/* Access Token Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Access Token</Text>
          <Text style={styles.sectionDescription}>
            Generate or paste your Zerodha access token. This is typically obtained
            through Zerodha's web interface or generated via the Zerodha Connect API.
          </Text>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Access Token</Text>
            <View style={styles.passwordContainer}>
              <TextInput
                style={styles.inputPassword}
                placeholder="Nz7epyXMdgkPN68MVo2jUbnx4jS3hCMy"
                value={accessToken}
                onChangeText={setAccessToken}
                secureTextEntry={!showAccessToken}
                editable={!loading}
                placeholderTextColor="#999"
              />
              <TouchableOpacity
                onPress={() => setShowAccessToken(!showAccessToken)}
                style={styles.eyeIcon}
              >
                <Text>{showAccessToken ? '👁️' : '👁️‍🗨️'}</Text>
              </TouchableOpacity>
            </View>
          </View>

          <TouchableOpacity
            style={[styles.button, styles.secondaryButton, loading && styles.buttonDisabled]}
            onPress={handleSaveToken}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#2196F3" />
            ) : (
              <Text style={styles.buttonTextSecondary}>Save Token</Text>
            )}
          </TouchableOpacity>
        </View>

        {/* Execution Mode Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Execution Mode</Text>
          <Text style={styles.sectionDescription}>
            Choose how your trades will be executed. Live mode executes real trades.
          </Text>

          {modes.map((mode) => (
            <TouchableOpacity
              key={mode}
              style={[
                styles.modeButton,
                executionMode === mode && styles.modeButtonActive,
              ]}
              onPress={() => handleExecutionModeChange(mode)}
              disabled={loading}
            >
              <View style={styles.modeRadio}>
                {executionMode === mode && <View style={styles.modeRadioInner} />}
              </View>
              <View style={styles.modeContent}>
                <Text
                  style={[
                    styles.modeText,
                    executionMode === mode && styles.modeTextActive,
                  ]}
                >
                  {mode}
                </Text>
                <Text style={styles.modeDescription}>
                  {mode === 'ZERODHA_LIVE'
                    ? 'Execute real trades on Zerodha'
                    : mode === 'ZERODHA_DRY_RUN'
                    ? 'Simulate trades without real execution'
                    : 'Paper trading mode for backtesting'}
                </Text>
              </View>
            </TouchableOpacity>
          ))}
        </View>

        {/* Info Section */}
        <View style={styles.infoSection}>
          <Text style={styles.infoTitle}>ℹ️ Setup Instructions</Text>
          <Text style={styles.infoText}>
            1. Go to your Zerodha account settings
          </Text>
          <Text style={styles.infoText}>
            2. Navigate to "Settings → API Consultants"
          </Text>
          <Text style={styles.infoText}>
            3. Create or retrieve your API Key and Secret
          </Text>
          <Text style={styles.infoText}>
            4. Copy them here and save
          </Text>
          <Text style={styles.infoText}>
            5. Log in to Zerodha to get an access token
          </Text>
          <Text style={styles.infoText}>
            6. Paste the access token and save
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  scrollContent: {
    padding: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    marginBottom: 24,
    color: '#1a1a1a',
  },
  section: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 3,
    elevation: 2,
  },
  statusSection: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 3,
    elevation: 2,
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  statusLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#666',
  },
  statusBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
  },
  statusGood: {
    backgroundColor: '#d4edda',
  },
  statusBad: {
    backgroundColor: '#f8d7da',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 8,
    color: '#1a1a1a',
  },
  sectionDescription: {
    fontSize: 13,
    color: '#666',
    marginBottom: 16,
    lineHeight: 20,
  },
  inputGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 8,
    color: '#333',
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: '#333',
    backgroundColor: '#f9f9f9',
  },
  passwordContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    backgroundColor: '#f9f9f9',
    paddingRight: 10,
  },
  inputPassword: {
    flex: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: '#333',
  },
  eyeIcon: {
    padding: 8,
  },
  button: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryButton: {
    backgroundColor: '#4CAF50',
  },
  secondaryButton: {
    backgroundColor: '#e3f2fd',
    borderWidth: 1,
    borderColor: '#2196F3',
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  buttonTextSecondary: {
    color: '#2196F3',
    fontSize: 14,
    fontWeight: '600',
  },
  modeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    marginBottom: 10,
    backgroundColor: '#f9f9f9',
  },
  modeButtonActive: {
    borderColor: '#4CAF50',
    backgroundColor: '#f1f8f4',
  },
  modeRadio: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#ddd',
    marginRight: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modeRadioInner: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#4CAF50',
  },
  modeContent: {
    flex: 1,
  },
  modeText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#666',
  },
  modeTextActive: {
    color: '#4CAF50',
  },
  modeDescription: {
    fontSize: 12,
    color: '#999',
    marginTop: 4,
  },
  infoSection: {
    backgroundColor: '#e3f2fd',
    borderRadius: 8,
    padding: 12,
    marginBottom: 24,
    borderLeftWidth: 4,
    borderLeftColor: '#2196F3',
  },
  infoTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1976D2',
    marginBottom: 10,
  },
  infoText: {
    fontSize: 13,
    color: '#0d47a1',
    marginBottom: 6,
    lineHeight: 18,
  },
});
