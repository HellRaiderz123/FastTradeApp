import React, { useState, useEffect } from 'react';
import { TrendingUp, RefreshCw } from 'lucide-react';
import { financeAPI } from '../lib/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';

interface Forecast {
  id: number;
  category: string;
  forecast_month: string;
  predicted_amount: number;
  confidence: number;
  actual_amount?: number;
}

export default function ExpenseForecastWidget() {
  const [forecasts, setForecasts] = useState<Forecast[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [chartData, setChartData] = useState<any[]>([]);

  useEffect(() => {
    loadForecasts();
  }, []);

  useEffect(() => {
    generateChartData();
  }, [forecasts, selectedCategories]);

  const loadForecasts = async () => {
    try {
      const res = await financeAPI.getExpenseForecasts();
      setForecasts(res.data);
      // Pre-select first 3 categories
      const categories = [...new Set(res.data.map((f: Forecast) => f.category))].slice(0, 3);
      setSelectedCategories(categories);
    } catch (error) {
      console.error('Failed to load forecasts:', error);
    }
  };

  const handleGenerateForecast = async (category: string) => {
    setLoading(true);
    try {
      await financeAPI.generateForecast(category);
      await loadForecasts();
    } catch (error) {
      console.error('Failed to generate forecast:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateChartData = () => {
    const categories = selectedCategories.length > 0 
      ? selectedCategories 
      : [...new Set(forecasts.map(f => f.category))];

    const data = categories.map((cat) => {
      const forecast = forecasts.find(f => f.category === cat);
      return {
        category: cat,
        predicted: forecast?.predicted_amount || 0,
        actual: forecast?.actual_amount || 0,
        confidence: forecast?.confidence || 0,
      };
    });

    setChartData(data);
  };

  const getTotalPredicted = () => {
    return chartData.reduce((sum, item) => sum + item.predicted, 0);
  };

  const getAverageConfidence = () => {
    if (chartData.length === 0) return 0;
    return chartData.reduce((sum, item) => sum + item.confidence, 0) / chartData.length;
  };

  const categories = [...new Set(forecasts.map(f => f.category))];

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2 text-white">
          <TrendingUp size={20} />
          Expense Forecast & Trends
        </h3>
        <button
          onClick={loadForecasts}
          disabled={loading}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm text-white flex items-center gap-1 disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-slate-700/30 p-3 rounded">
          <p className="text-slate-400 text-xs">Total Predicted</p>
          <p className="text-white text-lg font-bold">₹{getTotalPredicted().toLocaleString()}</p>
        </div>
        <div className="bg-slate-700/30 p-3 rounded">
          <p className="text-slate-400 text-xs">Avg. Confidence</p>
          <p className="text-white text-lg font-bold">{(getAverageConfidence() * 100).toFixed(0)}%</p>
        </div>
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <div className="bg-slate-700/20 rounded-lg p-3 mb-4 h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 15 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
              <XAxis 
                dataKey="category" 
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                angle={-45}
                textAnchor="end"
                height={60}
              />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }}
                labelStyle={{ color: '#e2e8f0' }}
                formatter={(value: number) => `₹${value.toLocaleString()}`}
              />
              <Bar dataKey="predicted" fill="#3b82f6" name="Predicted" />
              {forecasts.some(f => f.actual_amount) && (
                <Bar dataKey="actual" fill="#10b981" name="Actual" />
              )}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Category Selection */}
      <div className="mb-4">
        <p className="text-sm text-slate-300 mb-2">Categories:</p>
        <div className="flex flex-wrap gap-2">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => {
                if (selectedCategories.includes(cat)) {
                  setSelectedCategories(selectedCategories.filter(c => c !== cat));
                } else {
                  setSelectedCategories([...selectedCategories, cat]);
                }
              }}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                selectedCategories.includes(cat)
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Generate Forecast Buttons */}
      <div className="space-y-2 max-h-40 overflow-y-auto">
        {categories.length === 0 ? (
          <p className="text-slate-400 text-sm text-center py-4">No forecast data available</p>
        ) : (
          categories.map((cat) => {
            const forecast = forecasts.find(f => f.category === cat);
            return (
              <div key={cat} className="flex items-center justify-between bg-slate-700/20 p-2 rounded text-sm">
                <div className="flex-1">
                  <p className="text-white font-medium">{cat}</p>
                  {forecast && (
                    <p className="text-slate-400 text-xs">
                      ₹{forecast.predicted_amount.toLocaleString()} • {Math.round(forecast.confidence * 100)}% confidence
                    </p>
                  )}
                </div>
                <button
                  onClick={() => handleGenerateForecast(cat)}
                  disabled={loading}
                  className="px-2 py-1 bg-green-600 hover:bg-green-700 text-white text-xs rounded disabled:opacity-50"
                >
                  {loading ? 'Generating...' : 'Refresh'}
                </button>
              </div>
            );
          })
        )}
      </div>

      <p className="text-xs text-slate-500 mt-3 text-center">
        Forecasts based on last 3 months of spending
      </p>
    </div>
  );
}
