import React, { useState, useEffect } from 'react';
import { ShoppingBag, Zap, Filter, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react';
import { marketplaceAPI } from '../lib/api';

interface Template {
  id: string;
  name: string;
  category: string;
  description: string;
  underlying: string;
  strategy_type: string;
  risk_level: string;
  ideal_market: string;
  max_profit: string;
  max_loss: string;
  parameters: Record<string, any>;
  tags: string[];
}

const RISK_COLORS: Record<string, string> = {
  Low: 'text-green-400 bg-green-900/30 border-green-700',
  Medium: 'text-yellow-400 bg-yellow-900/30 border-yellow-700',
  High: 'text-red-400 bg-red-900/30 border-red-700',
};

const CATEGORY_COLORS: Record<string, string> = {
  Bullish: 'text-green-300',
  Bearish: 'text-red-300',
  Neutral: 'text-blue-300',
  Adaptive: 'text-purple-300',
};

const StrategyMarketplace: React.FC = () => {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [riskFilter, setRiskFilter] = useState<string>('');
  const [deploying, setDeploying] = useState<string | null>(null);
  const [deployResult, setDeployResult] = useState<{ id: string; success: boolean; message: string } | null>(null);
  const [customLots, setCustomLots] = useState<Record<string, number>>({});

  useEffect(() => {
    fetchTemplates();
  }, [categoryFilter, riskFilter]);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const res = await marketplaceAPI.getTemplates(categoryFilter || undefined, riskFilter || undefined);
      setTemplates(res.data.templates);
    } catch (err) {
      console.error('Failed to load templates:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeploy = async (template: Template) => {
    setDeploying(template.id);
    setDeployResult(null);
    try {
      const lots = customLots[template.id] || template.parameters.lots;
      const res = await marketplaceAPI.deploy(template.id, undefined, lots);
      setDeployResult({ id: template.id, success: true, message: res.data.message });
    } catch (err: any) {
      setDeployResult({
        id: template.id,
        success: false,
        message: err.response?.data?.detail || 'Deploy failed',
      });
    } finally {
      setDeploying(null);
    }
  };

  const categories = ['', 'Bullish', 'Bearish', 'Neutral', 'Adaptive'];
  const riskLevels = ['', 'Low', 'Medium', 'High'];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <ShoppingBag size={28} className="text-purple-400" />
          <h1 className="text-3xl font-bold text-white">Strategy Marketplace</h1>
        </div>
        <p className="text-slate-400">Pre-built strategy templates — one-click deploy with sensible defaults</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-slate-400" />
          <span className="text-slate-400 text-sm">Filter:</span>
        </div>
        <div className="flex gap-2">
          {categories.map((cat) => (
            <button
              key={cat || 'all'}
              onClick={() => setCategoryFilter(cat)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                categoryFilter === cat
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              {cat || 'All Categories'}
            </button>
          ))}
        </div>
        <div className="flex gap-2 ml-4">
          {riskLevels.map((risk) => (
            <button
              key={risk || 'all'}
              onClick={() => setRiskFilter(risk)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                riskFilter === risk
                  ? 'bg-purple-600 text-white'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              {risk || 'All Risk'}
            </button>
          ))}
        </div>
        <button
          onClick={fetchTemplates}
          className="ml-auto p-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-colors"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Templates Grid */}
      {loading ? (
        <div className="text-center py-16 text-slate-400">Loading templates...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {templates.map((template) => {
            const isDeploying = deploying === template.id;
            const result = deployResult?.id === template.id ? deployResult : null;

            return (
              <div
                key={template.id}
                className="bg-slate-800/60 backdrop-blur-sm border border-slate-700 rounded-xl p-5 flex flex-col gap-3 hover:border-slate-500 transition-colors"
              >
                {/* Header */}
                <div>
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <h3 className="font-semibold text-white text-sm leading-tight">{template.name}</h3>
                    <span className={`text-xs px-2 py-0.5 rounded border font-medium flex-shrink-0 ${RISK_COLORS[template.risk_level] || ''}`}>
                      {template.risk_level}
                    </span>
                  </div>
                  <span className={`text-xs font-medium ${CATEGORY_COLORS[template.category] || 'text-slate-400'}`}>
                    {template.category} · {template.underlying}
                  </span>
                </div>

                {/* Description */}
                <p className="text-xs text-slate-400 leading-relaxed">{template.description}</p>

                {/* Stats */}
                <div className="bg-slate-900/50 rounded-lg p-3 space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Ideal Market</span>
                    <span className="text-slate-300 text-right">{template.ideal_market}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Max Profit</span>
                    <span className="text-green-400">{template.max_profit}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Max Loss</span>
                    <span className="text-red-400">{template.max_loss}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Min Confidence</span>
                    <span className="text-slate-300">{template.parameters.min_confidence}%</span>
                  </div>
                </div>

                {/* Tags */}
                <div className="flex flex-wrap gap-1">
                  {template.tags.map((tag) => (
                    <span key={tag} className="text-xs px-2 py-0.5 bg-slate-700 text-slate-400 rounded-full">
                      {tag}
                    </span>
                  ))}
                </div>

                {/* Lots customization */}
                <div className="flex items-center gap-2">
                  <label className="text-xs text-slate-400 flex-shrink-0">Lots:</label>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={customLots[template.id] ?? template.parameters.lots}
                    onChange={(e) =>
                      setCustomLots((prev) => ({ ...prev, [template.id]: Number(e.target.value) }))
                    }
                    className="w-16 px-2 py-1 bg-slate-900 border border-slate-600 rounded text-white text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                  />
                  {template.parameters.use_ml && (
                    <span className="text-xs text-purple-400 ml-auto">🤖 ML</span>
                  )}
                </div>

                {/* Deploy Result */}
                {result && (
                  <div className={`flex items-start gap-2 text-xs p-2 rounded-lg ${
                    result.success ? 'bg-green-900/30 text-green-300' : 'bg-red-900/30 text-red-300'
                  }`}>
                    {result.success ? <CheckCircle size={14} className="flex-shrink-0 mt-0.5" /> : <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />}
                    <span>{result.message}</span>
                  </div>
                )}

                {/* Deploy Button */}
                <button
                  onClick={() => handleDeploy(template)}
                  disabled={isDeploying}
                  className="mt-auto flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 rounded-lg text-white text-sm font-medium transition-colors"
                >
                  {isDeploying ? (
                    <><RefreshCw size={14} className="animate-spin" /> Deploying...</>
                  ) : (
                    <><Zap size={14} /> Deploy Strategy</>
                  )}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {!loading && templates.length === 0 && (
        <div className="text-center py-16 text-slate-400">
          No templates match the selected filters.
        </div>
      )}

      <p className="mt-8 text-xs text-slate-600 text-center">
        Deployed strategies are created as disabled. Enable them from the Strategies page after reviewing parameters.
      </p>
    </div>
  );
};

export default StrategyMarketplace;
