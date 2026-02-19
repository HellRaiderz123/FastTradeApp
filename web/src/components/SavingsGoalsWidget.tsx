import React, { useState, useEffect } from 'react';
import { Target, Plus, Trash2, CheckCircle } from 'lucide-react';
import { financeAPI } from '../lib/api';

interface SavingsGoal {
  id: number;
  name: string;
  target_amount: number;
  current_amount: number;
  deadline: string;
  priority: string;
  progress_percent: number;
  days_remaining: number;
}

export default function SavingsGoalsWidget() {
  const [goals, setGoals] = useState<SavingsGoal[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    target_amount: 0,
    deadline: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    priority: 'medium',
  });

  useEffect(() => {
    loadGoals();
  }, []);

  const loadGoals = async () => {
    try {
      const res = await financeAPI.getSavingsGoals();
      setGoals(res.data);
    } catch (error) {
      console.error('Failed to load savings goals:', error);
    }
  };

  const handleAddGoal = async () => {
    if (!formData.name || formData.target_amount <= 0) return;

    try {
      await financeAPI.createSavingsGoal({
        name: formData.name,
        target_amount: formData.target_amount,
        deadline: formData.deadline,
        priority: formData.priority,
      });

      setFormData({
        name: '',
        target_amount: 0,
        deadline: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        priority: 'medium',
      });
      setShowForm(false);
      await loadGoals();
    } catch (error) {
      console.error('Failed to add savings goal:', error);
    }
  };

  const handleDeleteGoal = async (id: number) => {
    try {
      await financeAPI.deleteSavingsGoal(id);
      await loadGoals();
    } catch (error) {
      console.error('Failed to delete savings goal:', error);
    }
  };

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      high: 'text-red-400',
      medium: 'text-yellow-400',
      low: 'text-green-400',
    };
    return colors[priority] || 'text-slate-400';
  };

  const getProgressColor = (percent: number) => {
    if (percent >= 100) return 'bg-green-500';
    if (percent >= 75) return 'bg-blue-500';
    if (percent >= 50) return 'bg-purple-500';
    if (percent >= 25) return 'bg-orange-500';
    return 'bg-red-500';
  };

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2 text-white">
          <Target size={20} />
          Savings Goals
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
          <input
            type="text"
            placeholder="Goal Name (e.g., Vacation)"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className="w-full bg-slate-600 text-white px-3 py-2 rounded text-sm"
          />
          <div className="grid grid-cols-2 gap-3">
            <input
              type="number"
              placeholder="Target Amount (₹)"
              value={formData.target_amount}
              onChange={(e) => setFormData({ ...formData, target_amount: parseFloat(e.target.value) })}
              className="bg-slate-600 text-white px-3 py-2 rounded text-sm"
            />
            <input
              type="date"
              value={formData.deadline}
              onChange={(e) => setFormData({ ...formData, deadline: e.target.value })}
              className="bg-slate-600 text-white px-3 py-2 rounded text-sm"
            />
          </div>
          <select
            value={formData.priority}
            onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
            className="w-full bg-slate-600 text-white px-3 py-2 rounded text-sm"
          >
            <option value="high">🔴 High Priority</option>
            <option value="medium">🟡 Medium Priority</option>
            <option value="low">🟢 Low Priority</option>
          </select>
          <div className="flex gap-2">
            <button
              onClick={handleAddGoal}
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
        {goals.length === 0 ? (
          <p className="text-slate-400 text-sm text-center py-4">No savings goals</p>
        ) : (
          goals.map((goal) => (
            <div key={goal.id} className="bg-slate-700/30 p-3 rounded">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {goal.progress_percent >= 100 && <CheckCircle size={16} className="text-green-400" />}
                  <span className="text-white font-medium text-sm">{goal.name}</span>
                </div>
                <button
                  onClick={() => handleDeleteGoal(goal.id)}
                  className="text-red-400 hover:text-red-300"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <div className="flex items-center gap-2 mb-2">
                <div className="flex-1 bg-slate-600 rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-full transition-all ${getProgressColor(goal.progress_percent)}`}
                    style={{ width: `${Math.min(goal.progress_percent, 100)}%` }}
                  />
                </div>
                <span className="text-slate-300 text-xs font-mono">
                  {goal.progress_percent.toFixed(0)}%
                </span>
              </div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>₹{goal.current_amount.toLocaleString()} / ₹{goal.target_amount.toLocaleString()}</span>
                <span className={`font-medium ${getPriorityColor(goal.priority)}`}>
                  {goal.priority.toUpperCase()}
                </span>
              </div>
              <div className="text-xs text-slate-400">
                {goal.days_remaining > 0
                  ? `${goal.days_remaining} days left`
                  : goal.days_remaining === 0
                  ? 'Due today'
                  : `${Math.abs(goal.days_remaining)} days overdue`}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
