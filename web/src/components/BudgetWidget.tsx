import React, { useState, useEffect } from 'react';
import { TrendingDown, Plus, Trash2, AlertCircle } from 'lucide-react';
import { financeAPI } from '../lib/api';

interface BudgetStatus {
  budget: { id: number; category: string; monthly_limit: number; alert_threshold: number };
  spent: number;
  remaining: number;
  percent_used: number;
}

export default function BudgetWidget() {
  const [budgets, setBudgets] = useState<BudgetStatus[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    category: 'Food',
    monthly_limit: 0,
    alert_threshold: 80,
  });

  useEffect(() => {
    loadBudgets();
  }, []);

  const loadBudgets = async () => {
    try {
      const res = await financeAPI.getBudgets();
      const statusPromises = res.data.map((b: any) =>
        financeAPI.getBudgetStatus(b.category)
      );
      const statuses = await Promise.all(statusPromises);
      setBudgets(statuses.map(s => s.data));
    } catch (error) {
      console.error('Failed to load budgets:', error);
    }
  };

  const handleAddBudget = async () => {
    if (formData.monthly_limit <= 0) return;

    try {
      await financeAPI.createBudget({
        category: formData.category,
        monthly_limit: formData.monthly_limit,
        alert_threshold: formData.alert_threshold,
      });

      setFormData({ category: 'Food', monthly_limit: 0, alert_threshold: 80 });
      setShowForm(false);
      await loadBudgets();
    } catch (error) {
      console.error('Failed to add budget:', error);
    }
  };

  const handleDeleteBudget = async (budgetId: number) => {
    try {
      await financeAPI.deleteBudget(budgetId);
      await loadBudgets();
    } catch (error) {
      console.error('Failed to delete budget:', error);
    }
  };

  const getProgressColor = (percent: number, threshold: number) => {
    if (percent > 100) return 'bg-red-500';
    if (percent >= threshold) return 'bg-orange-500';
    return 'bg-green-500';
  };

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2 text-white">
          <TrendingDown size={20} />
          Monthly Budgets
        </h3>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm text-white flex items-center gap-1"
        >
          <Plus size={16} /> Add
        </button>
      </div>

      {showForm && (
        <div className="bg-slate-700/50 rounded-lg p-4 mb-4 space-y-3">
          <select
            value={formData.category}
            onChange={(e) => setFormData({ ...formData, category: e.target.value })}
            className="w-full bg-slate-600 text-white px-3 py-2 rounded text-sm"
          >
            <option>Food</option>
            <option>Shopping</option>
            <option>Utilities</option>
            <option>Entertainment</option>
            <option>Transportation</option>
            <option>Other</option>
          </select>
          <div className="grid grid-cols-2 gap-3">
            <input
              type="number"
              placeholder="Monthly Limit (₹)"
              value={formData.monthly_limit}
              onChange={(e) => setFormData({ ...formData, monthly_limit: parseFloat(e.target.value) })}
              className="bg-slate-600 text-white px-3 py-2 rounded text-sm"
            />
            <input
              type="number"
              placeholder="Alert (%)"
              value={formData.alert_threshold}
              onChange={(e) => setFormData({ ...formData, alert_threshold: parseFloat(e.target.value) })}
              className="bg-slate-600 text-white px-3 py-2 rounded text-sm"
              min="0"
              max="100"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleAddBudget}
              className="flex-1 bg-green-600 hover:bg-green-700 text-white py-2 rounded text-sm"
            >
              Save
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="flex-1 bg-slate-600 hover:bg-slate-700 text-white py-2 rounded text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="space-y-3 max-h-64 overflow-y-auto">
        {budgets.length === 0 ? (
          <p className="text-slate-400 text-sm text-center py-4">No budgets set</p>
        ) : (
          budgets.map((status) => (
            <div key={status.budget.id} className="bg-slate-700/30 p-3 rounded">
              <div className="flex items-center justify-between mb-2">
                <span className="text-white font-medium text-sm">{status.budget.category}</span>
                <button
                  onClick={() => handleDeleteBudget(status.budget.id)}
                  className="text-red-400 hover:text-red-300"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <div className="flex items-center gap-2 mb-2">
                <div className="flex-1 bg-slate-600 rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-full transition-all ${getProgressColor(status.percent_used, status.budget.alert_threshold)}`}
                    style={{ width: `${Math.min(status.percent_used, 100)}%` }}
                  />
                </div>
                <span className="text-slate-300 text-xs font-mono">
                  {status.percent_used.toFixed(0)}%
                </span>
              </div>
              <div className="flex justify-between text-xs text-slate-400">
                <span>Spent: ₹{status.spent.toLocaleString()}</span>
                <span>Remaining: ₹{status.remaining.toLocaleString()}</span>
              </div>
              {status.percent_used >= status.budget.alert_threshold && (
                <div className="mt-2 flex items-center gap-1 text-xs text-orange-400">
                  <AlertCircle size={12} />
                  Budget alert threshold reached
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
