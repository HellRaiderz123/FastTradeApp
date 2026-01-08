import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Save, Bell, Lock, Eye, EyeOff, CheckCircle, XCircle, Send } from 'lucide-react';
import { useTradeStore } from '../lib/store';
import { settingsAPI } from '../lib/api';

const DEFAULT_IV_LIMITS: Record<string, { min_atm_dist_pct: number; max_risk_pct_capital: number }> = {
  LOW: { min_atm_dist_pct: 0.5, max_risk_pct_capital: 4.0 },
  NORMAL: { min_atm_dist_pct: 0.6, max_risk_pct_capital: 2.0 },
  HIGH: { min_atm_dist_pct: 0.8, max_risk_pct_capital: 5.0 },
};

const Settings: React.FC = () => {
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

  useEffect(() => {
    console.log('Settings component mounted - loading Zerodha settings');
    loadZerodhaSettings();
    loadNotificationSettings();
    loadTradingSettings();
    // Refresh every 5 seconds to sync with backend
    const interval = setInterval(() => {
      loadZerodhaSettings();
      loadNotificationSettings();
    }, 5000);
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
      alert(error.response?.data?.detail || 'Error saving settings');
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

  return (
    <div className="max-w-2xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <SettingsIcon className="w-8 h-8 text-blue-400" />
        <h1 className="text-3xl font-bold text-white">Settings</h1>
      </div>

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
                    {zerodhaStatus?.access_token_set ? (
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
                console.log('Refreshing settings...');
                loadZerodhaSettings();
              }}
              className="ml-4 px-3 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs rounded transition"
            >
              🔄 Refresh
            </button>
          </div>
        </div>

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
