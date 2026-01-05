import React, { useState } from 'react';
import { Settings as SettingsIcon, Save, Bell, Lock, Eye } from 'lucide-react';
import { useTradeStore } from '../lib/store';

const Settings: React.FC = () => {
  const { capital, setCapital } = useTradeStore();
  const [settings, setSettings] = useState({
    capital,
    riskPerTrade: 2,
    maxDailyLoss: 2,
    maxTrades: 3,
    autoExit: true,
    notifications: true,
    darkMode: true,
  });
  const [saved, setSaved] = useState(false);

  const handleChange = (key: string, value: any) => {
    setSettings({ ...settings, [key]: value });
  };

  const handleSave = () => {
    setCapital(settings.capital);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
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
        <SettingItem label="Capital (₹)" type="number" value={settings.capital} onChange={(val) => handleChange('capital', val)} />
        <SettingItem label="Risk Per Trade (%)" type="number" value={settings.riskPerTrade} onChange={(val) => handleChange('riskPerTrade', val)} min="0.5" max="5" step="0.5" />
        <SettingItem label="Max Daily Loss (%)" type="number" value={settings.maxDailyLoss} onChange={(val) => handleChange('maxDailyLoss', val)} min="1" max="10" step="0.5" />
        <SettingItem label="Max Daily Trades" type="number" value={settings.maxTrades} onChange={(val) => handleChange('maxTrades', val)} min="1" max="10" />
      </SettingsCard>

      {/* Execution Settings */}
      <SettingsCard title="Execution">
        <ToggleSetting label="Auto Exit on TP/SL" value={settings.autoExit} onChange={(val) => handleChange('autoExit', val)} />
      </SettingsCard>

      {/* Notifications */}
      <SettingsCard title="Notifications">
        <ToggleSetting label="Trade Notifications" value={settings.notifications} onChange={(val) => handleChange('notifications', val)} />
        <ToggleSetting label="Email Alerts" value={true} onChange={() => {}} disabled />
      </SettingsCard>

      {/* Appearance */}
      <SettingsCard title="Appearance">
        <ToggleSetting label="Dark Mode (Always On)" value={settings.darkMode} onChange={() => {}} disabled />
      </SettingsCard>

      {/* API Keys */}
      <SettingsCard title="Integrations">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Zerodha API Key</label>
            <input
              type="password"
              defaultValue="●●●●●●●●●●●●"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
              disabled
            />
            <p className="text-xs text-slate-400 mt-1">Change in environment variables</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Execution Mode</label>
            <select className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500">
              <option>PAPER (Recommended)</option>
              <option>ZERODHA_DRY_RUN</option>
            </select>
            <p className="text-xs text-slate-400 mt-1">Paper mode is safe for testing</p>
          </div>
        </div>
      </SettingsCard>

      {/* Account */}
      <SettingsCard title="Account">
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-slate-300">Account Type</span>
            <span className="font-medium text-white">Paper Trading</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-300">Status</span>
            <span className="font-medium text-green-400">Active</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-300">Joined</span>
            <span className="font-medium text-white">January 5, 2026</span>
          </div>
        </div>
      </SettingsCard>

      {/* Save Button */}
      <div className="flex gap-4">
        <button onClick={handleSave} className="btn-primary flex items-center gap-2">
          <Save className="w-4 h-4" />
          Save Settings
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
