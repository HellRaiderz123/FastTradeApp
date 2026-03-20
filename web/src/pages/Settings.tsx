import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Save, Bell, Lock, Eye, EyeOff, CheckCircle, XCircle, Send, Brain, Zap } from 'lucide-react';
import { useTradeStore } from '../lib/store';
import { settingsAPI } from '../lib/api';
import { useToast } from '../components/Toast';

const DEFAULT_IV_LIMITS: Record<string, { min_atm_dist_pct: number; max_risk_pct_capital: number }> = {
  LOW: { min_atm_dist_pct: 0.5, max_risk_pct_capital: 4.0 },
  NORMAL: { min_atm_dist_pct: 0.6, max_risk_pct_capital: 2.0 },
  HIGH: { min_atm_dist_pct: 0.8, max_risk_pct_capital: 5.0 },
};

const Settings: React.FC = () => {
  const { showToast } = useToast();
  const { capital, setCapital } = useTradeStore();
  const [settings, setSettings] = useState({
    riskPerTrade: 2,
    maxDailyLoss: 2,
    maxTrades: 3,
    autoExit: true,
    notifications: true,
    darkMode: true,
  });
  const [riskLimits, setRiskLimits] = useState({
    max_portfolio_loss_pct: 2,
    max_trades_per_day: 3,
    iv_regime_limits: { ...DEFAULT_IV_LIMITS },
  });
  const [saved, setSaved] = useState(false);
  const [riskSaving, setRiskSaving] = useState(false);
  
  // Zerodha settings
  const [zerodhaStatus, setZerodhaStatus] = useState({
    api_key_set: false,
    access_token_set: false,
    execution_mode: 'ZERODHA_DRY_RUN',
  });
  const [zerodhaForm, setZerodhaForm] = useState({
    apiKey: '',
    apiSecret: '',
    requestToken: '',
    accessToken: '',
    executionMode: 'ZERODHA_DRY_RUN',
  });
  const [zerodhaLoading, setZerodhaLoading] = useState(false);
  const [zerodhaMessage, setZerodhaMessage] = useState('');
  const [showSecrets, setShowSecrets] = useState({
    apiSecret: false,
    accessToken: false,
  });
  const [oauthLoading, setOAuthLoading] = useState(false);
  const [sessionStatus, setSessionStatus] = useState<{
    has_active_session: boolean;
    user_id?: string;
    expires_at?: string;
    fallback_to_env?: boolean;
  } | null>(null);

  // Active broker settings
  const [activeBroker, setActiveBroker] = useState('ZERODHA');

  // INDMoney settings
  const [indmoneyStatus, setIndmoneyStatus] = useState({
    access_token_set: false,
    execution_mode: 'ZERODHA_DRY_RUN',
  });
  const [indmoneyForm, setIndmoneyForm] = useState({
    accessToken: '',
    lookupSymbol: '',
  });
  const [indmoneyLoading, setIndmoneyLoading] = useState(false);
  const [indmoneyMessage, setIndmoneyMessage] = useState('');
  const [showIndmoneyToken, setShowIndmoneyToken] = useState(false);
  const [indmoneyLookup, setIndmoneyLookup] = useState<{
    symbol: string;
    normalized_symbol: string;
    security_id: string;
    source: string;
  } | null>(null);

  // Gmail notification settings
  const [notificationStatus, setNotificationStatus] = useState({
    gmail_configured: false,
    gmail_enabled: true,
    gmail_user: '',
    alert_email: '',
  });
  const [gmailForm, setGmailForm] = useState({
    gmail_user: '',
    gmail_app_password: '',
    alert_email: '',
  });
  const [gmailLoading, setGmailLoading] = useState(false);
  const [gmailMessage, setGmailMessage] = useState('');
  const [showGmailPassword, setShowGmailPassword] = useState(false);

  // ML settings
  const [mlSettings, setMlSettings] = useState({
    enabled: false,
    autoTrain: true,
    minConfidence: 60,
  });
  const [mlSaving, setMlSaving] = useState(false);
  const [mlMessage, setMlMessage] = useState('');

  useEffect(() => {
    console.log('Settings component mounted - loading Zerodha settings');
    loadBrokerSettings();
    loadZerodhaSettings();
    loadINDMoneySettings();
    loadNotificationSettings();
    loadTradingSettings();
    loadMlSettings();
    loadSessionStatus();
    // Handle OAuth callback if redirected back
    handleOAuthCallback();
    // Refresh every 5 seconds to sync with backend
    const interval = setInterval(() => {
      //loadZerodhaSettings();
      loadNotificationSettings();
      loadSessionStatus();
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  const loadTradingSettings = async () => {
    try {
      const response = await settingsAPI.getRiskLimits();
      const data = response.data || response;
      const ivLimits = { ...DEFAULT_IV_LIMITS, ...(data.iv_regime_limits || {}) };

      const riskPerTrade = data.max_portfolio_loss_pct ?? data.risk_per_trade ?? 2;
      const maxTrades = data.max_trades_per_day ?? data.max_trades ?? 3;

      setRiskLimits({
        max_portfolio_loss_pct: riskPerTrade,
        max_trades_per_day: maxTrades,
        iv_regime_limits: ivLimits,
      });

      setSettings(prev => ({
        ...prev,
        riskPerTrade,
        maxTrades,
        maxDailyLoss: riskPerTrade,
      }));
    } catch (error) {
      console.error('Error loading trading settings:', error);
    }
  };

  const loadZerodhaSettings = async () => {
    try {
      const response = await settingsAPI.getZerodhaSettings();
      // Handle axios response structure - data is nested in .data
      const data = response.data || response;
      console.log('Zerodha settings loaded:', data);
      setZerodhaStatus({
        api_key_set: data.api_key_set === true,
        access_token_set: data.access_token_set === true,
        execution_mode: data.execution_mode || 'ZERODHA_DRY_RUN',
      });
      setZerodhaForm(prev => ({ 
        ...prev, 
        executionMode: data.execution_mode || 'ZERODHA_DRY_RUN' 
      }));
    } catch (error) {
      console.error('Error loading settings:', error);
    }
  };

  const loadBrokerSettings = async () => {
    try {
      const response = await settingsAPI.getBrokerSettings();
      const data = response.data || response;
      console.log('Broker settings loaded:', data);
      setActiveBroker(data.active_broker || 'ZERODHA');
    } catch (error) {
      console.error('Error loading broker settings:', error);
    }
  };

  const loadINDMoneySettings = async () => {
    try {
      const response = await settingsAPI.getINDMoneySettings();
      const data = response.data || response;
      console.log('INDMoney settings loaded:', data);
      setIndmoneyStatus({
        access_token_set: data.access_token_set === true,
        execution_mode: data.execution_mode || 'ZERODHA_DRY_RUN',
      });
    } catch (error) {
      console.error('Error loading INDMoney settings:', error);
    }
  };

  const loadNotificationSettings = async () => {
    try {
      const response = await settingsAPI.getNotificationSettings();
      const data = response.data || response;
      setNotificationStatus({
        gmail_configured: !!data.gmail_configured,
        gmail_enabled: !!data.gmail_enabled,
        gmail_user: data.gmail_user || '',
        alert_email: data.alert_email || '',
      });
    } catch (error) {
      console.error('Error loading notification settings:', error);
    }
  };

  const loadMlSettings = () => {
    try {
      const stored = localStorage.getItem('ml_settings');
      if (stored) {
        setMlSettings(JSON.parse(stored));
      }
    } catch (error) {
      console.error('Error loading ML settings:', error);
    }
  };

  const saveMlSettings = async () => {
    try {
      setMlSaving(true);
      localStorage.setItem('ml_settings', JSON.stringify(mlSettings));
      setMlMessage('✓ ML settings saved');
      setTimeout(() => setMlMessage(''), 3000);
    } catch (error) {
      console.error('Error saving ML settings:', error);
      setMlMessage('Error saving ML settings');
    } finally {
      setMlSaving(false);
    }
  };

  const handleChange = (key: string, value: any) => {
    setSettings({ ...settings, [key]: value });
  };

  const updateIvLimit = (regime: string, field: 'min_atm_dist_pct' | 'max_risk_pct_capital', value: number) => {
    setRiskLimits(prev => ({
      ...prev,
      iv_regime_limits: {
        ...prev.iv_regime_limits,
        [regime]: {
          ...(prev.iv_regime_limits?.[regime] || DEFAULT_IV_LIMITS[regime] || {}),
          [field]: value,
        },
      },
    }));
  };

  const handleSave = async () => {
    try {
      setRiskSaving(true);
      await settingsAPI.saveRiskLimits({
        max_portfolio_loss_pct: riskLimits.max_portfolio_loss_pct,
        max_trades_per_day: riskLimits.max_trades_per_day,
        iv_regime_limits: riskLimits.iv_regime_limits,
      });

      // Keep legacy trading endpoint in sync for backward compatibility
      await settingsAPI.saveTradingSettings({
        risk_per_trade: riskLimits.max_portfolio_loss_pct,
        max_trades_per_day: riskLimits.max_trades_per_day,
      });

      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (error: any) {
      console.error('Error saving settings:', error);
      showToast('error', 'Save Error', error.response?.data?.detail || 'Error saving settings');
    } finally {
      setRiskSaving(false);
    }
  };

  const handleSaveZerodhaCredentials = async () => {
    if (!zerodhaForm.apiKey.trim() || !zerodhaForm.apiSecret.trim()) {
      setZerodhaMessage('API Key and Secret cannot be empty');
      return;
    }
    
    try {
      setZerodhaLoading(true);
      await settingsAPI.saveZerodhaCredentials({
        api_key: zerodhaForm.apiKey,
        api_secret: zerodhaForm.apiSecret,
      });
      setZerodhaMessage('✓ Credentials saved successfully');
      setZerodhaForm(prev => ({ ...prev, apiKey: '', apiSecret: '' }));
      // Refresh immediately and again after delay
      await loadZerodhaSettings();
      setTimeout(() => loadZerodhaSettings(), 500);
      setTimeout(() => setZerodhaMessage(''), 3000);
    } catch (error: any) {
      console.error('Error:', error);
      setZerodhaMessage(error.response?.data?.detail || 'Error saving credentials');
    } finally {
      setZerodhaLoading(false);
    }
  };

  const handleSaveZerodhaToken = async () => {
    if (!zerodhaForm.accessToken.trim()) {
      setZerodhaMessage('Access token cannot be empty');
      return;
    }
    
    try {
      setZerodhaLoading(true);
      await settingsAPI.saveZerodhaToken({
        access_token: zerodhaForm.accessToken,
      });
      setZerodhaMessage('✓ Access token saved successfully');
      setZerodhaForm(prev => ({ ...prev, accessToken: '' }));
      // Refresh immediately and again after delay
      await loadZerodhaSettings();
      setTimeout(() => loadZerodhaSettings(), 500);
      setTimeout(() => setZerodhaMessage(''), 3000);
    } catch (error: any) {
      console.error('Error:', error);
      setZerodhaMessage(error.response?.data?.detail || 'Error saving token');
    } finally {
      setZerodhaLoading(false);
    }
  };

  const handleGenerateAccessToken = async () => {
    if (!zerodhaForm.requestToken.trim()) {
      setZerodhaMessage('Request token cannot be empty');
      return;
    }
    
    try {
      setZerodhaLoading(true);
      const response = await settingsAPI.generateZerodhaToken({
        request_token: zerodhaForm.requestToken,
      });
      setZerodhaMessage('✓ Access token generated successfully!');
      setZerodhaForm(prev => ({ ...prev, requestToken: '', accessToken: response.data?.access_token }));
      // Refresh immediately and again after delay
      await loadZerodhaSettings();
      setTimeout(() => loadZerodhaSettings(), 500);
      setTimeout(() => setZerodhaMessage(''), 3000);
    } catch (error: any) {
      console.error('Error:', error);
      setZerodhaMessage(error.response?.data?.detail || 'Error generating token');
    } finally {
      setZerodhaLoading(false);
    }
  };

  const handleSetExecutionMode = async (mode: string) => {
    try {
      setZerodhaLoading(true);
      await settingsAPI.setExecutionMode(mode);
      setZerodhaForm(prev => ({ ...prev, executionMode: mode }));
      setZerodhaMessage(`✓ Mode changed to ${mode}`);
      // Refresh immediately and again after delay
      await loadZerodhaSettings();
      setTimeout(() => loadZerodhaSettings(), 500);
      setTimeout(() => setZerodhaMessage(''), 3000);
    } catch (error: any) {
      console.error('Error:', error);
      setZerodhaMessage(error.response?.data?.detail || 'Error changing mode');
    } finally {
      setZerodhaLoading(false);
    }
  };

  const loadSessionStatus = async () => {
    try {
      const response = await settingsAPI.getZerodhaSessionStatus();
      const data = response.data || response;
      setSessionStatus(data);
    } catch (error) {
      console.error('Error loading session status:', error);
    }
  };

  const handleLoginWithZerodha = async () => {
    try {
      setOAuthLoading(true);
      const response = await settingsAPI.getZerodhaLoginUrl('http://localhost:5173/settings');
      const loginUrl = response.data?.login_url;
      if (loginUrl) {
        // Open in new window; user will be redirected back to settings page with request_token
        window.open(loginUrl, '_blank', 'width=600,height=700');
        setZerodhaMessage('Opening Zerodha login... You will be redirected back after login');
        // Poll for session after a delay
        setTimeout(() => loadSessionStatus(), 3000);
      }
    } catch (error: any) {
      console.error('Error:', error);
      setZerodhaMessage(error.response?.data?.detail || 'Error getting login URL');
    } finally {
      setOAuthLoading(false);
    }
  };

  const handleOAuthCallback = async () => {
    // Check if URL has request_token parameter
    const params = new URLSearchParams(window.location.search);
    const requestToken = params.get('request_token');
    
    if (requestToken) {
      console.log('OAuth callback detected, exchanging token...');
      try {
        setOAuthLoading(true);
        const response = await settingsAPI.handleZerodhaCallback(requestToken);
        setZerodhaMessage('✓ ' + (response.data?.message || 'Login successful! Access token saved.'));
        // Clear the URL parameter
        window.history.replaceState({}, document.title, window.location.pathname);
        // Reload settings and session status
        setTimeout(() => {
          loadZerodhaSettings();
          loadSessionStatus();
        }, 500);
        setTimeout(() => setZerodhaMessage(''), 3000);
      } catch (error: any) {
        console.error('Error:', error);
        setZerodhaMessage(error.response?.data?.detail || 'OAuth callback failed');
      } finally {
        setOAuthLoading(false);
      }
    }
  };

  const handleLogoutZerodha = async () => {
    try {
      setOAuthLoading(true);
      await settingsAPI.logoutZerodha();
      setZerodhaMessage('✓ Logged out successfully');
      await loadSessionStatus();
      setTimeout(() => setZerodhaMessage(''), 3000);
    } catch (error: any) {
      console.error('Error:', error);
      setZerodhaMessage(error.response?.data?.detail || 'Error logging out');
    } finally {
      setOAuthLoading(false);
    }
  };

  const handleSaveINDMoneyToken = async () => {
    if (!indmoneyForm.accessToken.trim()) {
      setIndmoneyMessage('Access token cannot be empty');
      return;
    }
    
    try {
      setIndmoneyLoading(true);
      await settingsAPI.saveINDMoneyToken({
        access_token: indmoneyForm.accessToken,
      });
      setIndmoneyMessage('✓ Access token saved successfully');
      setIndmoneyForm(prev => ({ ...prev, accessToken: '' }));
      await loadINDMoneySettings();
      setTimeout(() => setIndmoneyMessage(''), 3000);
    } catch (error: any) {
      console.error('Error:', error);
      setIndmoneyMessage(error.response?.data?.detail || 'Error saving token');
    } finally {
      setIndmoneyLoading(false);
    }
  };

  const handleResolveINDMoneySecurity = async () => {
    if (!indmoneyForm.lookupSymbol.trim()) {
      setIndmoneyMessage('Enter a symbol to resolve security_id');
      return;
    }

    try {
      setIndmoneyLoading(true);
      const response = await settingsAPI.resolveINDMoneySecurity(indmoneyForm.lookupSymbol.trim());
      const data = response.data || response;
      setIndmoneyLookup(data);
      setIndmoneyMessage(`✓ Found security_id ${data.security_id} for ${data.symbol}`);
      setTimeout(() => setIndmoneyMessage(''), 3000);
    } catch (error: any) {
      console.error('Error:', error);
      setIndmoneyLookup(null);
      setIndmoneyMessage(error.response?.data?.detail || 'Could not resolve security_id');
    } finally {
      setIndmoneyLoading(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <SettingsIcon className="w-8 h-8 text-blue-400" />
        <h1 className="text-3xl font-bold text-white">Settings</h1>
      </div>

      {/* Active Broker Status */}
      <SettingsCard title="Active Broker">
        <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-slate-300 font-medium">Currently Active for Orders:</span>
              <p className="text-sm text-slate-400 mt-1">
                {activeBroker === 'ZERODHA' && 'Orders will be placed via Zerodha API'}
                {activeBroker === 'INDMONEY' && 'Orders will be placed via INDMoney/INDstocks API'}
              </p>
            </div>
            <div className={`px-4 py-2 rounded-full font-semibold text-sm ${
              activeBroker === 'ZERODHA'
                ? 'bg-orange-600 text-white'
                : 'bg-purple-600 text-white'
            }`}>
              {activeBroker}
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-3">
            💡 Change broker from the header dropdown. Market data always uses Zerodha.
          </p>
        </div>
      </SettingsCard>

      {/* Trading Settings */}
      <SettingsCard title="Trading Configuration">
        <SettingItem
          label="Risk Per Trade (%)"
          type="number"
          value={riskLimits.max_portfolio_loss_pct}
          onChange={(val) => {
            setRiskLimits(prev => ({ ...prev, max_portfolio_loss_pct: val }));
            handleChange('riskPerTrade', val);
            handleChange('maxDailyLoss', val);
          }}
          min="0.5"
          max="15"
          step="0.1"
        />
        <SettingItem
          label="Max Daily Loss (%)"
          type="number"
          value={riskLimits.max_portfolio_loss_pct}
          onChange={(val) => {
            setRiskLimits(prev => ({ ...prev, max_portfolio_loss_pct: val }));
            handleChange('maxDailyLoss', val);
            handleChange('riskPerTrade', val);
          }}
          min="0.5"
          max="15"
          step="0.1"
        />
        <div className="space-y-2">
          <SettingItem
            label="Max Daily Trades"
            type="number"
            value={riskLimits.max_trades_per_day}
            onChange={(val) => {
              setRiskLimits(prev => ({ ...prev, max_trades_per_day: val }));
              handleChange('maxTrades', val);
            }}
            min="1"
            max="100"
          />
          <div className="mt-2 p-3 bg-blue-900 bg-opacity-30 border border-blue-700 rounded text-sm text-blue-200">
            <strong>💡 Tip:</strong> In {zerodhaStatus.execution_mode === 'ZERODHA_DRY_RUN' ? <span className="text-blue-100">Dry Run mode</span> : <span className="text-orange-100">Live mode</span>}, set this higher to test more strategies.
            {zerodhaStatus.execution_mode === 'ZERODHA_DRY_RUN' && ' Recommended: 10-20 trades for testing.'}
            {zerodhaStatus.execution_mode === 'ZERODHA_LIVE' && ' Recommended: 2-5 trades for live trading.'}
          </div>
        </div>
      </SettingsCard>

      {/* IV Regime Limits */}
      <SettingsCard title="IV Regime Risk Limits">
        <p className="text-sm text-slate-300">Tune how much risk each IV environment is allowed to take before a trade is blocked.</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {['LOW', 'NORMAL', 'HIGH'].map((regime) => (
            <div key={regime} className="p-4 rounded-lg border border-slate-700 bg-slate-800/60 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-white">{regime} IV</span>
                <span className="text-xs text-slate-400">caps</span>
              </div>
              <SettingItem
                label="Min ATM Distance (%)"
                type="number"
                value={riskLimits.iv_regime_limits?.[regime]?.min_atm_dist_pct ?? DEFAULT_IV_LIMITS[regime].min_atm_dist_pct}
                onChange={(val) => updateIvLimit(regime, 'min_atm_dist_pct', val)}
                min="0"
                max="5"
                step="0.1"
              />
              <SettingItem
                label="Max Risk % of Capital"
                type="number"
                value={riskLimits.iv_regime_limits?.[regime]?.max_risk_pct_capital ?? DEFAULT_IV_LIMITS[regime].max_risk_pct_capital}
                onChange={(val) => updateIvLimit(regime, 'max_risk_pct_capital', val)}
                min="0.1"
                max="50"
                step="0.1"
              />
            </div>
          ))}
        </div>
      </SettingsCard>

      {/* Execution Settings */}
      <SettingsCard title="Execution Mode">
        <div className="p-4 bg-slate-800 rounded-lg border border-slate-700 mb-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-slate-300 font-medium">Current Mode:</span>
            <div className={`px-4 py-2 rounded-full font-semibold text-sm ${
              zerodhaStatus.execution_mode === 'ZERODHA_DRY_RUN'
                ? 'bg-green-600 text-white'
                : 'bg-red-600 text-white'
            }`}>
              {zerodhaStatus.execution_mode === 'ZERODHA_DRY_RUN' ? '🟢 Dry Run (Paper)' : '🔴 Live'}
            </div>
          </div>
          <p className="text-sm text-slate-400">
            {zerodhaStatus.execution_mode === 'ZERODHA_DRY_RUN'
              ? 'Testing mode - No real money at risk. Perfect for increasing Max Daily Trades.'
              : 'Live mode - Real trades with actual funds. Use conservative trade limits.'}
          </p>
        </div>
        <ToggleSetting label="Auto Exit on TP/SL" value={settings.autoExit} onChange={(val) => handleChange('autoExit', val)} />
      </SettingsCard>

      {/* Notifications */}
      <SettingsCard title="Notifications">
        <ToggleSetting label="Trade Notifications" value={settings.notifications} onChange={(val) => handleChange('notifications', val)} />
        <ToggleSetting label="Email Alerts" value={true} onChange={() => {}} disabled />
      </SettingsCard>

      {/* Save Button for Trading Settings */}
      <div className="flex gap-3">
        <button
          onClick={handleSave}
          disabled={riskSaving}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold"
        >
          <Save className="w-5 h-5" />
          {riskSaving ? 'Saving...' : 'Save Trading Settings'}
        </button>
        {saved && (
          <div className="flex items-center gap-2 px-4 py-3 bg-green-900 text-green-200 rounded-lg">
            <CheckCircle className="w-5 h-5" />
            Settings saved!
          </div>
        )}
      </div>

      {/* Gmail Notification Settings */}
      <SettingsCard title="Email Notifications (Gmail)">
        {/* Status */}
        <div className="mb-4 p-4 bg-slate-800 rounded-lg border border-slate-700">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Gmail Configured:</span>
              {notificationStatus.gmail_configured ? (
                <span className="flex items-center gap-1 text-green-400"><CheckCircle className="w-4 h-4" /> Yes</span>
              ) : (
                <span className="flex items-center gap-1 text-red-400"><XCircle className="w-4 h-4" /> No</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Enabled:</span>
              <ToggleSetting label="" value={notificationStatus.gmail_enabled} onChange={async (val) => {
                try {
                  setGmailLoading(true);
                  await settingsAPI.setGmailEnabled(val);
                  setNotificationStatus(prev => ({ ...prev, gmail_enabled: val }));
                } catch (e) {
                  console.error('Toggle error', e);
                } finally {
                  setGmailLoading(false);
                }
              }} />
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-2">User: <span className="text-slate-300">{notificationStatus.gmail_user || 'not set'}</span> • Alerts to: <span className="text-slate-300">{notificationStatus.alert_email || 'not set'}</span></p>
        </div>

        {/* Gmail Credentials */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Gmail User</label>
            <input
              type="email"
              placeholder="your.email@gmail.com"
              value={gmailForm.gmail_user}
              onChange={(e) => setGmailForm({ ...gmailForm, gmail_user: e.target.value })}
              disabled={gmailLoading}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">App Password</label>
            <div className="relative">
              <input
                type={showGmailPassword ? 'text' : 'password'}
                placeholder="16-character app password"
                value={gmailForm.gmail_app_password}
                onChange={(e) => setGmailForm({ ...gmailForm, gmail_app_password: e.target.value })}
                disabled={gmailLoading}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50 pr-10"
              />
              <button
                onClick={() => setShowGmailPassword(!showGmailPassword)}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-300"
              >
                {showGmailPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-xs text-slate-500 mt-1">Use a Google App Password (2FA required). Do not use your regular password.</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Alert Email</label>
            <input
              type="email"
              placeholder="recipient email for alerts (defaults to Gmail user)"
              value={gmailForm.alert_email}
              onChange={(e) => setGmailForm({ ...gmailForm, alert_email: e.target.value })}
              disabled={gmailLoading}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
          </div>

          <div className="flex gap-3">
            <button
              onClick={async () => {
                try {
                  setGmailLoading(true);
                  await settingsAPI.saveGmailSettings(gmailForm);
                  setGmailMessage('✓ Gmail settings saved');
                  setGmailForm({ gmail_user: '', gmail_app_password: '', alert_email: '' });
                  await loadNotificationSettings();
                  setTimeout(() => setGmailMessage(''), 3000);
                } catch (error: any) {
                  console.error('Error:', error);
                  setGmailMessage(error.response?.data?.detail || 'Error saving Gmail settings');
                } finally {
                  setGmailLoading(false);
                }
              }}
              disabled={gmailLoading}
              className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-slate-600 text-white font-semibold py-2 rounded-lg transition flex items-center justify-center gap-2"
            >
              <Save className="w-4 h-4" />
              {gmailLoading ? 'Saving...' : 'Save Gmail Settings'}
            </button>

            <button
              onClick={async () => {
                try {
                  setGmailLoading(true);
                  await settingsAPI.sendTestEmail('Test Email', 'This is a test alert from FastTrade');
                  setGmailMessage('✓ Test email sent');
                  setTimeout(() => setGmailMessage(''), 3000);
                } catch (error: any) {
                  console.error('Error:', error);
                  setGmailMessage(error.response?.data?.detail || 'Error sending test email');
                } finally {
                  setGmailLoading(false);
                }
              }}
              disabled={gmailLoading}
              className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white font-semibold py-2 rounded-lg transition flex items-center justify-center gap-2"
            >
              <Send className="w-4 h-4" />
              {gmailLoading ? 'Sending...' : 'Send Test Email'}
            </button>
          </div>

          {gmailMessage && (
            <div className={`mt-4 p-3 rounded-lg text-sm font-semibold ${
              gmailMessage.includes('✓') ? 'bg-green-900 text-green-200' : 'bg-red-900 text-red-200'
            }`}>
              {gmailMessage}
            </div>
          )}
        </div>
      </SettingsCard>

      {/* Appearance */}
      <SettingsCard title="Appearance">
        <ToggleSetting label="Dark Mode (Always On)" value={settings.darkMode} onChange={() => {}} disabled />
      </SettingsCard>

      {/* API Keys */}
      <SettingsCard title="Zerodha Configuration">
        {/* Status */}
        <div className="mb-6 p-4 bg-slate-800 rounded-lg border border-slate-700">
          <div className="flex justify-between items-start mb-4">
            <div className="flex-1">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">API Key Status:</span>
                  <div className="flex items-center gap-1">
                    {zerodhaStatus?.api_key_set ? (
                      <>
                        <CheckCircle className="w-4 h-4 text-green-400" />
                        <span className="text-green-400">Configured</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="w-4 h-4 text-red-400" />
                        <span className="text-red-400">Not Set</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">Access Token Status:</span>
                  <div className="flex items-center gap-1">
                    {sessionStatus?.has_active_session ? (
                      <>
                        <CheckCircle className="w-4 h-4 text-green-400" />
                        <span className="text-green-400">Active (OAuth)</span>
                      </>
                    ) : zerodhaStatus?.access_token_set ? (
                      <>
                        <CheckCircle className="w-4 h-4 text-blue-400" />
                        <span className="text-blue-400">.env Token</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="w-4 h-4 text-red-400" />
                        <span className="text-red-400">Not Set</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
              {sessionStatus?.user_id && (
                <p className="text-xs text-slate-400 mt-3">🔐 Logged in as: <span className="text-slate-200 font-semibold">{sessionStatus.user_id}</span></p>
              )}
              {sessionStatus?.expires_at && (
                <p className="text-xs text-slate-400 mt-1">expires: {new Date(sessionStatus.expires_at).toLocaleDateString()}</p>
              )}
            </div>
            <button
              onClick={() => {
                console.log('Refreshing settings...');
                loadZerodhaSettings();
                loadSessionStatus();
              }}
              className="ml-4 px-3 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs rounded transition"
            >
              🔄 Refresh
            </button>
          </div>
        </div>

        {/* OAuth Login Section */}
        {sessionStatus?.has_active_session ? (
          <div className="space-y-4 mb-6 p-4 bg-green-900/20 rounded-lg border border-green-700/50">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-400" />
              <p className="text-sm font-semibold text-green-300">Zerodha OAuth Session Active</p>
            </div>
            <p className="text-xs text-green-200">✓ Your Zerodha session is active and will be used automatically for trading.</p>
            <button
              onClick={handleLogoutZerodha}
              disabled={oauthLoading}
              className="w-full bg-red-600 hover:bg-red-700 disabled:bg-slate-600 text-white font-semibold py-2 rounded-lg transition flex items-center justify-center gap-2"
            >
              {oauthLoading ? 'Logging out...' : 'Logout from Zerodha'}
            </button>
          </div>
        ) : (
          <div className="space-y-4 mb-6 p-4 bg-blue-900/20 rounded-lg border border-blue-700/50">
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-blue-400" />
              <p className="text-sm font-semibold text-blue-300">Quick OAuth Login</p>
            </div>
            <p className="text-xs text-blue-200">Click below to login with your Zerodha account. No API keys or tokens needed!</p>
            <button
              onClick={handleLoginWithZerodha}
              disabled={oauthLoading || !zerodhaStatus.api_key_set}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white font-semibold py-3 rounded-lg transition flex items-center justify-center gap-2 text-base"
            >
              {oauthLoading ? 'Opening login...' : '🔐 Login with Zerodha'}
            </button>
            {!zerodhaStatus.api_key_set && (
              <p className="text-xs text-yellow-400">⚠️ Please configure API Key first</p>
            )}
          </div>
        )}

        {/* Credentials Form */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Zerodha API Key</label>
            <input
              type="text"
              placeholder="Your API Key from Zerodha"
              value={zerodhaForm.apiKey}
              onChange={(e) => setZerodhaForm({ ...zerodhaForm, apiKey: e.target.value })}
              disabled={zerodhaLoading}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Zerodha API Secret</label>
            <div className="relative">
              <input
                type={showSecrets.apiSecret ? 'text' : 'password'}
                placeholder="Your API Secret from Zerodha"
                value={zerodhaForm.apiSecret}
                onChange={(e) => setZerodhaForm({ ...zerodhaForm, apiSecret: e.target.value })}
                disabled={zerodhaLoading}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50 pr-10"
              />
              <button
                onClick={() => setShowSecrets({ ...showSecrets, apiSecret: !showSecrets.apiSecret })}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-300"
              >
                {showSecrets.apiSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            onClick={handleSaveZerodhaCredentials}
            disabled={zerodhaLoading}
            className="w-full bg-green-600 hover:bg-green-700 disabled:bg-slate-600 text-white font-semibold py-2 rounded-lg transition flex items-center justify-center gap-2"
          >
            <Save className="w-4 h-4" />
            {zerodhaLoading ? 'Saving...' : 'Save Credentials'}
          </button>
        </div>

        {/* Access Token Generation */}
        <div className="space-y-4 mt-6 pt-6 border-t border-slate-700">
          <h3 className="text-sm font-semibold text-slate-300">Generate Access Token</h3>
          <p className="text-xs text-slate-400">
            1. Go to <a href="https://kite.zerodha.com" target="_blank" rel="noopener noreferrer" className="text-blue-400 underline">Zerodha login</a>
            <br />
            2. Check browser console or Network tab for "request_token"
            <br />
            3. Paste the request token below - access token will be generated and saved automatically
          </p>
          
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Request Token (from Zerodha OAuth)</label>
            <div className="relative">
              <input
                type={showSecrets.accessToken ? 'text' : 'password'}
                placeholder="Paste request token here"
                value={zerodhaForm.requestToken}
                onChange={(e) => setZerodhaForm({ ...zerodhaForm, requestToken: e.target.value })}
                disabled={zerodhaLoading}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50 pr-10"
              />
              <button
                onClick={() => setShowSecrets({ ...showSecrets, accessToken: !showSecrets.accessToken })}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-300"
              >
                {showSecrets.accessToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            onClick={handleGenerateAccessToken}
            disabled={zerodhaLoading || !zerodhaStatus.api_key_set}
            className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-slate-600 text-white font-semibold py-2 rounded-lg transition flex items-center justify-center gap-2"
          >
            <Save className="w-4 h-4" />
            {zerodhaLoading ? 'Generating & Saving...' : 'Generate & Save Access Token'}
          </button>
          {!zerodhaStatus.api_key_set && (
            <p className="text-xs text-red-400">⚠️ Save API credentials first</p>
          )}
          <p className="text-xs text-slate-400 bg-slate-800 p-2 rounded">
            ✓ Access token will be automatically saved to .env when generated
          </p>
        </div>

        {/* Manual Access Token (Optional) */}
        <div className="space-y-4 mt-6 pt-6 border-t border-slate-700">
          <h3 className="text-sm font-semibold text-slate-300">Manual Token (Optional)</h3>
          <p className="text-xs text-slate-400">
            Or paste an access token manually if you already have one
          </p>
          
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Access Token</label>
            <div className="relative">
              <input
                type={showSecrets.accessToken ? 'text' : 'password'}
                placeholder="Your access token"
                value={zerodhaForm.accessToken}
                onChange={(e) => setZerodhaForm({ ...zerodhaForm, accessToken: e.target.value })}
                disabled={zerodhaLoading}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50 pr-10"
              />
              <button
                onClick={() => setShowSecrets({ ...showSecrets, accessToken: !showSecrets.accessToken })}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-300"
              >
                {showSecrets.accessToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            onClick={handleSaveZerodhaToken}
            disabled={zerodhaLoading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white font-semibold py-2 rounded-lg transition flex items-center justify-center gap-2"
          >
            <Save className="w-4 h-4" />
            {zerodhaLoading ? 'Saving...' : 'Save Manually'}
          </button>
        </div>

        {/* Execution Mode */}
        <div className="space-y-4 mt-6 pt-6 border-t border-slate-700">
          <label className="block text-sm font-medium text-slate-300">Execution Mode</label>
          <div className="grid grid-cols-3 gap-2">
            {['ZERODHA_DRY_RUN', 'ZERODHA_LIVE', 'PAPER_TRADING'].map((mode) => (
              <button
                key={mode}
                onClick={() => handleSetExecutionMode(mode)}
                disabled={zerodhaLoading}
                className={`py-2 px-3 rounded-lg font-semibold transition text-sm ${
                  zerodhaForm.executionMode === mode
                    ? 'bg-green-600 text-white'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                } disabled:opacity-50`}
              >
                {mode}
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-400">
            {zerodhaForm.executionMode === 'ZERODHA_DRY_RUN' && 'Simulated trading - no real trades'}
            {zerodhaForm.executionMode === 'ZERODHA_LIVE' && '⚠️ Real trading - use with caution'}
            {zerodhaForm.executionMode === 'PAPER_TRADING' && 'Paper trading mode'}
          </p>
        </div>

        {/* Message */}
        {zerodhaMessage && (
          <div className={`mt-4 p-3 rounded-lg text-sm font-semibold ${
            zerodhaMessage.includes('✓') 
              ? 'bg-green-900 text-green-200' 
              : 'bg-red-900 text-red-200'
          }`}>
            {zerodhaMessage}
          </div>
        )}
      </SettingsCard>

      {/* INDMoney Configuration */}
      <SettingsCard title="INDMoney Configuration">
        {/* Status */}
        <div className="mb-6 p-4 bg-slate-800 rounded-lg border border-slate-700">
          <div className="flex justify-between items-start mb-4">
            <div className="flex-1">
              <div className="grid grid-cols-1 gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">Access Token Status:</span>
                  <div className="flex items-center gap-1">
                    {indmoneyStatus?.access_token_set ? (
                      <>
                        <CheckCircle className="w-4 h-4 text-green-400" />
                        <span className="text-green-400">Configured</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="w-4 h-4 text-red-400" />
                        <span className="text-red-400">Not Set</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
            <button
              onClick={() => {
                console.log('Refreshing INDMoney settings...');
                loadINDMoneySettings();
              }}
              className="ml-4 px-3 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs rounded transition"
            >
              🔄 Refresh
            </button>
          </div>
        </div>

        {/* Info Box */}
        <div className="mb-6 p-4 bg-purple-900/20 rounded-lg border border-purple-700/50">
          <div className="flex items-center gap-2 mb-2">
            <Lock className="w-5 h-5 text-purple-400" />
            <p className="text-sm font-semibold text-purple-300">Where to get your INDMoney Access Token</p>
          </div>
          <ol className="text-xs text-purple-200 space-y-1 ml-1">
            <li>1. Visit <a href="https://indstocks.com/app/api-trading" target="_blank" rel="noopener noreferrer" className="text-purple-400 underline">indstocks.com/app/api-trading</a></li>
            <li>2. Login with your INDMoney credentials</li>
            <li>3. Enable API Trading and copy your Access Token</li>
            <li>4. Paste it in the field below and click Save</li>
          </ol>
        </div>

        {/* Access Token Input */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              INDMoney Access Token
              <span className="text-purple-400 ml-2 text-xs">← Paste your token here</span>
            </label>
            <div className="relative">
              <input
                type={showIndmoneyToken ? 'text' : 'password'}
                placeholder="Paste your INDstocks access token here"
                value={indmoneyForm.accessToken}
                onChange={(e) => setIndmoneyForm(prev => ({ ...prev, accessToken: e.target.value }))}
                disabled={indmoneyLoading}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 disabled:opacity-50 pr-10"
              />
              <button
                onClick={() => setShowIndmoneyToken(!showIndmoneyToken)}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-300"
              >
                {showIndmoneyToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              This token is saved to your .env file (INDMONEY_ACCESS_TOKEN)
            </p>
          </div>

          <button
            onClick={handleSaveINDMoneyToken}
            disabled={indmoneyLoading}
            className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-slate-600 text-white font-semibold py-2 rounded-lg transition flex items-center justify-center gap-2"
          >
            <Save className="w-4 h-4" />
            {indmoneyLoading ? 'Saving...' : 'Save Access Token'}
          </button>
        </div>

        {/* Additional Configuration Note */}
        <div className="mt-4 p-3 bg-blue-900/20 border border-blue-700/50 rounded text-sm text-blue-200">
          <strong>💡 Note:</strong> INDMoney is used for order execution only. Market data (charts, options chain, etc.) continues to use Zerodha API.
        </div>

        {/* Symbol to security_id Lookup */}
        <div className="space-y-4 mt-6 pt-6 border-t border-slate-700">
          <h3 className="text-sm font-semibold text-slate-300">Test Symbol Mapping</h3>
          <p className="text-xs text-slate-400">
            Validate whether a symbol can be auto-resolved to INDMoney security_id.
          </p>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Trading Symbol</label>
            <input
              type="text"
              placeholder="Example: NIFTY27MAR2422000CE"
              value={indmoneyForm.lookupSymbol}
              onChange={(e) => setIndmoneyForm({ ...indmoneyForm, lookupSymbol: e.target.value })}
              disabled={indmoneyLoading}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 disabled:opacity-50"
            />
          </div>

          <button
            onClick={handleResolveINDMoneySecurity}
            disabled={indmoneyLoading || !indmoneyStatus.access_token_set}
            className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-600 text-white font-semibold py-2 rounded-lg transition"
          >
            {indmoneyLoading ? 'Resolving...' : 'Resolve security_id'}
          </button>

          {!indmoneyStatus.access_token_set && (
            <p className="text-xs text-yellow-400">Save INDMoney access token first to use lookup.</p>
          )}

          {indmoneyLookup && (
            <div className="p-3 bg-slate-800 border border-slate-700 rounded text-sm text-slate-200 space-y-1">
              <p><strong>Symbol:</strong> {indmoneyLookup.symbol}</p>
              <p><strong>Normalized:</strong> {indmoneyLookup.normalized_symbol}</p>
              <p><strong>security_id:</strong> {indmoneyLookup.security_id}</p>
              <p><strong>Source:</strong> {indmoneyLookup.source}</p>
            </div>
          )}
        </div>

        {/* Message */}
        {indmoneyMessage && (
          <div className={`mt-4 p-3 rounded-lg text-sm font-semibold ${
            indmoneyMessage.includes('✓') 
              ? 'bg-green-900 text-green-200' 
              : 'bg-red-900 text-red-200'
          }`}>
            {indmoneyMessage}
          </div>
        )}
      </SettingsCard>

      {/* Account */}
      <SettingsCard title="Account">
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-slate-300">Account Type</span>
            <span className="font-medium text-white">
              {zerodhaStatus.execution_mode === 'ZERODHA_LIVE' && 'Zerodha Live'}
              {zerodhaStatus.execution_mode === 'ZERODHA_DRY_RUN' && 'Zerodha Dry Run'}
              {zerodhaStatus.execution_mode === 'PAPER_TRADING' && 'Paper Trading'}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-300">Status</span>
            <span className={`font-medium ${
              zerodhaStatus.execution_mode === 'ZERODHA_LIVE' ? 'text-red-400' :
              zerodhaStatus.execution_mode === 'ZERODHA_DRY_RUN' ? 'text-yellow-400' :
              'text-green-400'
            }`}>
              {zerodhaStatus.execution_mode === 'ZERODHA_LIVE' && '⚠️ Live Trading'}
              {zerodhaStatus.execution_mode === 'ZERODHA_DRY_RUN' && 'Simulated'}
              {zerodhaStatus.execution_mode === 'PAPER_TRADING' && 'Active'}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-300">Joined</span>
            <span className="font-medium text-white">January 5, 2026</span>
          </div>
        </div>
      </SettingsCard>

      {/* Save Button */}
      <div className="flex gap-4">
        <button onClick={handleSave} disabled={riskSaving} className="btn-primary flex items-center gap-2 disabled:opacity-60">
          <Save className="w-4 h-4" />
          {riskSaving ? 'Saving...' : 'Save Settings'}
        </button>
        {saved && <p className="text-green-400 flex items-center">✓ Settings saved!</p>}
      </div>

      {/* AI/ML Settings */}
      <SettingsCard title="AI/ML Features">
        <div className="space-y-4">
          <div className="flex items-center gap-3 pb-4 border-b border-slate-700">
            <Brain className="w-6 h-6 text-purple-400" />
            <div className="flex-1">
              <h3 className="font-semibold text-white">Machine Learning Signals</h3>
              <p className="text-sm text-slate-400">Enhance stock suggestions with ML predictions</p>
            </div>
            <button
              onClick={() => setMlSettings(prev => ({ ...prev, enabled: !prev.enabled }))}
              aria-label="ML enabled toggle"
              title="ML enabled toggle"
              className={`relative inline-flex h-7 w-12 items-center rounded-full transition ${
                mlSettings.enabled ? 'bg-purple-500' : 'bg-slate-700'
              }`}
            >
              <span
                className={`inline-block h-5 w-5 transform bg-white rounded-full transition ${
                  mlSettings.enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          <div className="space-y-3">
            <SettingItem
              label="Minimum Confidence (%)"
              type="number"
              value={mlSettings.minConfidence}
              onChange={(val) => setMlSettings(prev => ({ ...prev, minConfidence: val }))}
              min="50"
              max="95"
              step="5"
            />

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-yellow-400" />
                <label className="text-slate-300">Auto-Train Weekly</label>
              </div>
              <button
                onClick={() => setMlSettings(prev => ({ ...prev, autoTrain: !prev.autoTrain }))}
                aria-label="Auto-train toggle"
                title="Auto-train toggle"
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                  mlSettings.autoTrain ? 'bg-green-500' : 'bg-slate-700'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform bg-white rounded-full transition ${
                    mlSettings.autoTrain ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div className="p-3 bg-purple-900 bg-opacity-20 border border-purple-700 rounded text-sm text-purple-200">
              <strong>💡 Info:</strong> ML model trains automatically every Sunday at 4 AM using accumulated daily candles. Requires 200+ candles per symbol.
            </div>
          </div>

          <button
            onClick={saveMlSettings}
            disabled={mlSaving}
            className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-slate-600 text-white font-semibold py-2 rounded-lg transition flex items-center justify-center gap-2"
          >
            <Save className="w-4 h-4" />
            {mlSaving ? 'Saving...' : 'Save ML Settings'}
          </button>

          {mlMessage && (
            <div className={`p-3 rounded-lg text-sm font-semibold ${
              mlMessage.includes('✓') ? 'bg-green-900 text-green-200' : 'bg-red-900 text-red-200'
            }`}>
              {mlMessage}
            </div>
          )}
        </div>
      </SettingsCard>

      {/* Coming Soon */}
      <div className="card-glass p-6 opacity-50">
        <h3 className="font-semibold text-slate-300 mb-4">Advanced Settings (Coming Soon)</h3>
        <div className="space-y-2 text-sm text-slate-400">
          <p>• Custom risk profiles</p>
          <p>• Strategy parameters tuning</p>
          <p>• Advanced alert rules</p>
          <p>• Portfolio rebalancing</p>
          <p>• Multi-account management</p>
        </div>
      </div>
    </div>
  );
};

interface SettingsCardProps {
  title: string;
  children: React.ReactNode;
}

const SettingsCard: React.FC<SettingsCardProps> = ({ title, children }) => (
  <div className="card-glass p-6">
    <h2 className="text-lg font-semibold text-white mb-4">{title}</h2>
    <div className="space-y-4">{children}</div>
  </div>
);

interface SettingItemProps {
  label: string;
  type?: string;
  value: any;
  onChange: (value: any) => void;
  min?: string | number;
  max?: string | number;
  step?: string | number;
}

const SettingItem: React.FC<SettingItemProps> = ({ label, type = 'text', value, onChange, min, max, step }) => (
  <div className="flex items-center justify-between">
    <label className="text-slate-300">{label}</label>
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(type === 'number' ? parseFloat(e.target.value) : e.target.value)}
      min={min}
      max={max}
      step={step}
      title={typeof label === 'string' ? label : 'input'}
      className="w-32 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
    />
  </div>
);

interface ToggleSettingProps {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}

const ToggleSetting: React.FC<ToggleSettingProps> = ({ label, value, onChange, disabled }) => (
  <div className="flex items-center justify-between">
    <label className="text-slate-300">{label}</label>
    <button
      onClick={() => !disabled && onChange(!value)}
      disabled={disabled}
      aria-label={label || 'toggle'}
      title={label || 'toggle'}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
        value ? 'bg-green-500' : 'bg-slate-700'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      <span
        className={`inline-block h-4 w-4 transform bg-white rounded-full transition ${
          value ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  </div>
);

export default Settings;
