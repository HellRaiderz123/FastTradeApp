import React, { useState, useEffect } from 'react';
import { 
  BarChart3, 
  RefreshCw, 
  Play, 
  Clock, 
  CheckCircle2, 
  AlertCircle,
  TrendingUp,
  Activity,
  Gauge,
  Zap,
  Save,
  Database,
  Download,
  Brain,
  Layers,
  Target,
  Newspaper,
  Grid,
  GitBranch,
} from 'lucide-react';
import { settingsAPI, mlAPI } from '../lib/api';
import {
  EnsembleTab,
  ShapTab,
  SignalBacktestTab,
  NewsSentimentTab,
  CorrelationTab,
  WalkForwardTab,
} from './MLIntelligence';

// ========================= TAB DEFINITIONS ==============================
type Tab = 'overview' | 'ensemble' | 'shap' | 'signal-backtest' | 'news-sentiment' | 'correlation' | 'walk-forward';

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'overview', label: 'Overview', icon: Brain },
  { id: 'ensemble', label: 'Ensemble', icon: Layers },
  { id: 'shap', label: 'Feature Importance', icon: BarChart3 },
  { id: 'signal-backtest', label: 'Signal Backtest', icon: Target },
  { id: 'news-sentiment', label: 'News Sentiment', icon: Newspaper },
  { id: 'correlation', label: 'Correlation', icon: Grid },
  { id: 'walk-forward', label: 'Walk-Forward', icon: GitBranch },
];

// ========================= INTERFACES ===================================
interface MLMetrics {
  accuracy: number | null;
  precision: number | null;
  recall: number | null;
  f1_score: number | null;
  training_date: string | null;
  total_samples: number;
  model_status: 'ready' | 'training' | 'not_trained' | 'error';
  last_training_duration: number | null;
}

interface MLSettings {
  enabled: boolean;
  confidence_threshold: number;
  auto_train_enabled: boolean;
  retraining_frequency: string;
}

// ========================= MAIN COMPONENT ================================
const MLCenter: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Brain className="w-8 h-8 text-purple-400" />
            ML Center
          </h1>
          <p className="text-slate-400 mt-1">Train, monitor, and analyze your machine learning models</p>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-slate-900 p-1 rounded-xl overflow-x-auto">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? 'bg-purple-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div>
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'ensemble' && <EnsembleTab />}
        {activeTab === 'shap' && <ShapTab />}
        {activeTab === 'signal-backtest' && <SignalBacktestTab />}
        {activeTab === 'news-sentiment' && <NewsSentimentTab />}
        {activeTab === 'correlation' && <CorrelationTab />}
        {activeTab === 'walk-forward' && <WalkForwardTab />}
      </div>
    </div>
  );
};

// ========================= OVERVIEW TAB ==================================
const OverviewTab: React.FC = () => {
  const [metrics, setMetrics] = useState<MLMetrics>({
    accuracy: null,
    precision: null,
    recall: null,
    f1_score: null,
    training_date: null,
    total_samples: 0,
    model_status: 'not_trained',
    last_training_duration: null,
  });

  const [settings, setSettings] = useState<MLSettings>({
    enabled: true,
    confidence_threshold: 0.65,
    auto_train_enabled: false,
    retraining_frequency: 'weekly',
  });

  const [isTraining, setIsTraining] = useState(false);
  const [trainingLog, setTrainingLog] = useState<string>('');
  const [refreshing, setRefreshing] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  
  // Backfill state
  const [isBackfilling, setIsBackfilling] = useState(false);
  const [backfillStatus, setBackfillStatus] = useState<{
    running: boolean;
    progress: number;
    total: number;
    current_symbol: string;
    completed_count: number;
    failed_count: number;
    message: string;
  } | null>(null);
  const [dataSummary, setDataSummary] = useState<{
    total_symbols: number;
    total_candles: number;
    symbols_with_500plus_days: number;
  } | null>(null);

  useEffect(() => {
    loadMLMetrics();
    loadMLSettings();
    loadDataSummary();
    const interval = setInterval(() => {
      loadMLMetrics();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  // Poll backfill status when running
  useEffect(() => {
    if (!isBackfilling) return;
    const poll = setInterval(async () => {
      try {
        const res = await mlAPI.getBackfillStatus();
        const data = res.data;
        if (data) {
          setBackfillStatus(data);
          if (!data.running) {
            setIsBackfilling(false);
            loadDataSummary();
          }
        }
      } catch (e) {
        console.error('Backfill poll error:', e);
      }
    }, 2000);
    return () => clearInterval(poll);
  }, [isBackfilling]);

  const loadDataSummary = async () => {
    try {
      const res = await mlAPI.getDataSummary();
      const data = res.data;
      if (data) {
        setDataSummary({
          total_symbols: data.total_symbols,
          total_candles: data.total_candles,
          symbols_with_500plus_days: data.symbols_with_500plus_days,
        });
      }
    } catch (e) {
      console.error('Error loading data summary:', e);
    }
  };

  const startBackfill = async () => {
    try {
      setIsBackfilling(true);
      const res = await mlAPI.backfill();
      const data = res.data;
      if (data) {
        setBackfillStatus({
          running: true,
          progress: 0,
          total: data.total_symbols || 0,
          current_symbol: '',
          completed_count: 0,
          failed_count: 0,
          message: data.message || 'Starting backfill...',
        });
      }
    } catch (e) {
      console.error('Backfill error:', e);
      setIsBackfilling(false);
    }
  };

  const loadMLMetrics = async () => {
    try {
      setRefreshing(true);
      const response = await mlAPI.getMetrics();
      const data = response.data;
      if (data) {
        setMetrics({
          accuracy: data.accuracy,
          precision: data.precision,
          recall: data.recall,
          f1_score: data.f1_score,
          training_date: data.training_date,
          total_samples: data.total_samples || 0,
          model_status: data.model_status || 'not_trained',
          last_training_duration: data.last_training_duration,
        });
      }
    } catch (error) {
      console.error('Error loading ML metrics:', error);
      setMetrics(prev => ({ ...prev, model_status: 'error' }));
    } finally {
      setRefreshing(false);
    }
  };

  const loadMLSettings = async () => {
    try {
      const response = await settingsAPI.getMLSettings();
      const data = response.data || response;
      setSettings({
        enabled: data.enabled ?? true,
        confidence_threshold: data.confidence_threshold ?? 0.65,
        auto_train_enabled: data.auto_train_enabled ?? false,
        retraining_frequency: data.retraining_frequency ?? 'weekly',
      });
    } catch (error) {
      console.error('Error loading ML settings:', error);
      const stored = localStorage.getItem('ml_settings');
      if (stored) {
        const parsed = JSON.parse(stored);
        setSettings(parsed);
      }
    }
  };

  const saveMLSettings = async () => {
    try {
      localStorage.setItem('ml_settings', JSON.stringify(settings));
      await settingsAPI.saveMLSettings(settings);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (error) {
      console.error('Error saving ML settings:', error);
    }
  };

  const trainModel = async () => {
    try {
      setIsTraining(true);
      setTrainingLog('Initiating ML model training...\n');

      const response = await mlAPI.train();
      const data = response.data;
      if (data) {
        setTrainingLog(prev => prev + `✓ Training completed\n${JSON.stringify(data, null, 2)}`);
        loadMLMetrics();
      }
    } catch (error: any) {
      console.error('Error training model:', error);
      const detail = error?.response?.data?.detail || error?.message || 'Unknown error';
      setTrainingLog(prev => prev + `✗ Error: ${detail}`);
    } finally {
      setIsTraining(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready': return 'text-green-400';
      case 'training': return 'text-yellow-400';
      case 'error': return 'text-red-400';
      default: return 'text-slate-400';
    }
  };

  const getStatusBg = (status: string) => {
    switch (status) {
      case 'ready': return 'bg-green-500/10 border border-green-500/30';
      case 'training': return 'bg-yellow-500/10 border border-yellow-500/30';
      case 'error': return 'bg-red-500/10 border border-red-500/30';
      default: return 'bg-slate-500/10 border border-slate-500/30';
    }
  };

  return (
    <div className="space-y-6">
      {/* Refresh button */}
      <div className="flex justify-end">
        <button
          onClick={loadMLMetrics}
          disabled={refreshing}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh Metrics
        </button>
      </div>

      {/* Success Message */}
      {saveSuccess && (
        <div className="bg-green-500/20 border border-green-500/50 text-green-200 p-4 rounded-lg flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5" />
          Settings saved successfully
        </div>
      )}

      {/* Warning: Incomplete metrics */}
      {metrics.model_status === 'ready' && (metrics.precision === null || metrics.recall === null) && (
        <div className="bg-blue-500/20 border border-blue-500/50 text-blue-200 p-4 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-5 h-5" />
          This model was trained with an earlier version. Click "Train Now" to update metrics and improve accuracy.
        </div>
      )}

      {/* Status + Metrics cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Model Status */}
        <div className={`card-glass p-6 rounded-xl ${getStatusBg(metrics.model_status)}`}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Model Status</h3>
            {metrics.model_status === 'ready' && <CheckCircle2 className={`w-5 h-5 ${getStatusColor(metrics.model_status)}`} />}
            {metrics.model_status === 'training' && <Activity className={`w-5 h-5 ${getStatusColor(metrics.model_status)} animate-pulse`} />}
            {metrics.model_status === 'error' && <AlertCircle className={`w-5 h-5 ${getStatusColor(metrics.model_status)}`} />}
          </div>
          <p className={`text-2xl font-bold ${getStatusColor(metrics.model_status)} capitalize`}>
            {metrics.model_status}
          </p>
          {metrics.training_date && (
            <p className="text-xs text-slate-400 mt-2 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Last trained: {new Date(metrics.training_date).toLocaleDateString()}
            </p>
          )}
        </div>

        {/* Accuracy */}
        <div className="card-glass p-6 rounded-xl border border-blue-500/30 bg-blue-500/10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Accuracy</h3>
            <TrendingUp className="w-5 h-5 text-blue-400" />
          </div>
          <p className="text-3xl font-bold text-blue-400">
            {metrics.accuracy !== null ? `${(metrics.accuracy * 100).toFixed(2)}%` : '—'}
          </p>
          <p className="text-xs text-slate-400 mt-2">Model prediction correctness</p>
        </div>

        {/* Training Samples */}
        <div className="card-glass p-6 rounded-xl border border-purple-500/30 bg-purple-500/10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Training Samples</h3>
            <Gauge className="w-5 h-5 text-purple-400" />
          </div>
          <p className="text-3xl font-bold text-purple-400">{metrics.total_samples}</p>
          <p className="text-xs text-slate-400 mt-2">Total data points used</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Precision */}
        <div className="card-glass p-6 rounded-xl border border-green-500/30 bg-green-500/10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Precision</h3>
            <BarChart3 className="w-5 h-5 text-green-400" />
          </div>
          <p className="text-3xl font-bold text-green-400">
            {metrics.precision !== null && metrics.precision !== undefined 
              ? `${(metrics.precision * 100).toFixed(2)}%` 
              : '—'}
          </p>
          <p className="text-xs text-slate-400 mt-2">True positive rate</p>
        </div>

        {/* Recall */}
        <div className="card-glass p-6 rounded-xl border border-yellow-500/30 bg-yellow-500/10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Recall</h3>
            <Activity className="w-5 h-5 text-yellow-400" />
          </div>
          <p className="text-3xl font-bold text-yellow-400">
            {metrics.recall !== null && metrics.recall !== undefined 
              ? `${(metrics.recall * 100).toFixed(2)}%` 
              : '—'}
          </p>
          <p className="text-xs text-slate-400 mt-2">Sensitivity to signals</p>
        </div>

        {/* F1 Score */}
        <div className="card-glass p-6 rounded-xl border border-red-500/30 bg-red-500/10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">F1 Score</h3>
            <Zap className="w-5 h-5 text-red-400" />
          </div>
          <p className="text-3xl font-bold text-red-400">
            {metrics.f1_score !== null && metrics.f1_score !== undefined 
              ? `${(metrics.f1_score * 100).toFixed(2)}%` 
              : '—'}
          </p>
          <p className="text-xs text-slate-400 mt-2">Overall model score</p>
        </div>
      </div>

      {/* Data & Backfill Section */}
      <div className="card-glass p-6 rounded-xl border border-slate-700">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-white flex items-center gap-2">
            <Database className="w-5 h-5" />
            Training Data
          </h2>
          <button
            onClick={startBackfill}
            disabled={isBackfilling}
            className="btn-primary flex items-center gap-2"
          >
            {isBackfilling ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Backfilling...
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                Backfill NIFTY100
              </>
            )}
          </button>
        </div>

        {/* Data Stats */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="bg-slate-900/50 rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-cyan-400">{dataSummary?.total_symbols ?? '—'}</p>
            <p className="text-xs text-slate-400">Symbols in DB</p>
          </div>
          <div className="bg-slate-900/50 rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-cyan-400">{dataSummary?.total_candles?.toLocaleString() ?? '—'}</p>
            <p className="text-xs text-slate-400">Total Candles</p>
          </div>
          <div className="bg-slate-900/50 rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-cyan-400">{dataSummary?.symbols_with_500plus_days ?? '—'}</p>
            <p className="text-xs text-slate-400">Symbols 500+ Days</p>
          </div>
        </div>

        {/* Backfill Progress */}
        {backfillStatus && (backfillStatus.running || backfillStatus.completed_count > 0) && (
          <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-slate-300">{backfillStatus.message}</span>
              <span className="text-sm text-slate-400">
                {backfillStatus.progress}/{backfillStatus.total}
              </span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-2">
              <div
                className="bg-cyan-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${backfillStatus.total > 0 ? (backfillStatus.progress / backfillStatus.total) * 100 : 0}%` }}
              />
            </div>
            <div className="flex gap-4 mt-2 text-xs">
              <span className="text-green-400">{backfillStatus.completed_count} completed</span>
              {backfillStatus.failed_count > 0 && (
                <span className="text-red-400">{backfillStatus.failed_count} failed</span>
              )}
            </div>
          </div>
        )}

        <p className="text-sm text-slate-400 mt-4">
          Click "Backfill NIFTY100" to download 900 days of daily candles for ~100 NIFTY stocks. 
          This enables the ML model to train on a much larger dataset.
          {dataSummary && dataSummary.total_symbols < 50 && (
            <span className="text-yellow-400 ml-1">
              Currently only {dataSummary.total_symbols} symbols — backfill recommended.
            </span>
          )}
        </p>
      </div>

      {/* Training Section */}
      <div className="card-glass p-6 rounded-xl border border-slate-700">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-white flex items-center gap-2">
            <Play className="w-5 h-5" />
            Model Training
          </h2>
          <button
            onClick={trainModel}
            disabled={isTraining}
            className="btn-primary flex items-center gap-2"
          >
            {isTraining ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Training...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Train Now
              </>
            )}
          </button>
        </div>

        {trainingLog && (
          <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4 mb-4">
            <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
              {trainingLog}
            </pre>
          </div>
        )}

        <p className="text-sm text-slate-400">
          Click "Train Now" to immediately train the ML model with the latest market data. 
          {metrics.training_date && (
            <> Last training was on {new Date(metrics.training_date).toLocaleDateString()}</>
          )}
        </p>
      </div>

      {/* ML Settings */}
      <div className="card-glass p-6 rounded-xl border border-slate-700">
        <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
          <Zap className="w-5 h-5" />
          ML Settings
        </h2>

        <div className="space-y-6">
          {/* Enable/Disable */}
          <div className="flex items-center justify-between p-4 bg-slate-900/50 rounded-lg">
            <div>
              <h3 className="text-white font-medium">Enable ML Suggestions</h3>
              <p className="text-xs text-slate-400">Use ML model for trade suggestions</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.enabled}
                onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600"></div>
            </label>
          </div>

          {/* Confidence Threshold */}
          <div className="p-4 bg-slate-900/50 rounded-lg">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-white font-medium">Confidence Threshold</h3>
                <p className="text-xs text-slate-400">Minimum confidence for suggestions</p>
              </div>
              <span className="text-lg font-bold text-green-400">{(settings.confidence_threshold * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="0.95"
              step="0.05"
              value={settings.confidence_threshold}
              onChange={(e) => setSettings({ ...settings, confidence_threshold: parseFloat(e.target.value) })}
              className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-green-500"
            />
            <div className="flex justify-between text-xs text-slate-500 mt-2">
              <span>50%</span>
              <span>95%</span>
            </div>
          </div>

          {/* Auto Train */}
          <div className="flex items-center justify-between p-4 bg-slate-900/50 rounded-lg">
            <div>
              <h3 className="text-white font-medium">Auto Train Model</h3>
              <p className="text-xs text-slate-400">Automatically retrain on schedule</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.auto_train_enabled}
                onChange={(e) => setSettings({ ...settings, auto_train_enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>

          {/* Retraining Frequency */}
          <div className="p-4 bg-slate-900/50 rounded-lg">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-white font-medium">Retraining Schedule</h3>
                <p className="text-xs text-slate-400">How often to retrain the model</p>
              </div>
            </div>
            <select
              value={settings.retraining_frequency}
              onChange={(e) => setSettings({ ...settings, retraining_frequency: e.target.value })}
              className="w-full bg-slate-800 text-white p-3 rounded-lg border border-slate-700 focus:border-green-500 focus:outline-none"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly (Sundays 4 AM IST)</option>
              <option value="bi-weekly">Bi-Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>

          {/* Save Button */}
          <button
            onClick={saveMLSettings}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            <Save className="w-4 h-4" />
            Save ML Settings
          </button>
        </div>
      </div>

      {/* Info Section */}
      <div className="card-glass p-6 rounded-xl border border-slate-700 bg-slate-900/30">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-blue-400" />
          How ML Works
        </h3>
        <ul className="space-y-2 text-sm text-slate-300">
          <li className="flex gap-2">
            <span className="text-green-400 font-bold">•</span>
            <span>GradientBoosting model trained on 900+ days of daily data from NIFTY100 stocks</span>
          </li>
          <li className="flex gap-2">
            <span className="text-blue-400 font-bold">•</span>
            <span>24 technical features: RSI, MACD, ADX, Bollinger Bands, ATR, OBV, EMA cross, candle patterns</span>
          </li>
          <li className="flex gap-2">
            <span className="text-yellow-400 font-bold">•</span>
            <span>Step 1: Click "Backfill NIFTY100" to download data for ~100 stocks (~40 seconds)</span>
          </li>
          <li className="flex gap-2">
            <span className="text-purple-400 font-bold">•</span>
            <span>Step 2: Click "Train Now" — GradientBoosting learns non-linear patterns in price action</span>
          </li>
          <li className="flex gap-2">
            <span className="text-orange-400 font-bold">•</span>
            <span>Large dataset (100 symbols × 600+ days = 40K+ samples) ensures robust predictions</span>
          </li>
          <li className="flex gap-2">
            <span className="text-cyan-400 font-bold">•</span>
            <span>Target: Accuracy 60%+, F1 55%+ — realistic for swing trading signal classification</span>
          </li>
          <li className="flex gap-2">
            <span className="text-purple-400 font-bold">•</span>
            <span>Use the Ensemble, SHAP, Walk-Forward tabs above for advanced analysis</span>
          </li>
        </ul>
      </div>
    </div>
  );
};

export default MLCenter;
