import React, { useState, useEffect } from 'react';
import { Repeat2, Plus, Trash2 } from 'lucide-react';
import { financeAPI } from '../lib/api';

interface RecurringTransaction {
  id: number;
  description: string;
  amount: number;
  category: string;
  frequency: string;
  is_active: boolean;
}

export default function RecurringTransactionsWidget() {
  const [recurring, setRecurring] = useState<RecurringTransaction[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    description: '',
    amount: 0,
    category: 'Utilities',
    frequency: 'monthly',
    startDate: new Date().toISOString().split('T')[0],
  });

  useEffect(() => {
    loadRecurring();
  }, []);

  const loadRecurring = async () => {
    try {
      const res = await financeAPI.getRecurringTransactions();
      setRecurring(res.data);
    } catch (error) {
      console.error('Failed to load recurring transactions:', error);
    }
  };

  const handleAddRecurring = async () => {
    if (!formData.description || formData.amount <= 0) return;

    try {
      await financeAPI.createRecurringTransaction({
        description: formData.description,
        amount: formData.amount,
        category: formData.category,
        frequency: formData.frequency,
        start_date: formData.startDate,
        end_date: null,
      });

      setFormData({
        description: '',
        amount: 0,
        category: 'Utilities',
        frequency: 'monthly',
        startDate: new Date().toISOString().split('T')[0],
      });
      setShowForm(false);
      await loadRecurring();
    } catch (error) {
      console.error('Failed to add recurring transaction:', error);
    }
  };

  const handleDeleteRecurring = async (id: number) => {
    try {
      await financeAPI.deleteRecurringTransaction(id);
      await loadRecurring();
    } catch (error) {
      console.error('Failed to delete recurring transaction:', error);
    }
  };

  const getFrequencyLabel = (freq: string) => {
    const labels: Record<string, string> = {
      daily: '📅 Daily',
      weekly: '📆 Weekly',
      monthly: '📊 Monthly',
      yearly: '📈 Yearly',
    };
    return labels[freq] || freq;
  };

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2 text-white">
          <Repeat2 size={20} />
          Recurring Transactions
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
            placeholder="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            className="w-full bg-slate-600 text-white px-3 py-2 rounded text-sm"
          />
          <div className="grid grid-cols-2 gap-3">
            <input
              type="number"
              placeholder="Amount"
              value={formData.amount}
              onChange={(e) => setFormData({ ...formData, amount: parseFloat(e.target.value) })}
              className="bg-slate-600 text-white px-3 py-2 rounded text-sm"
            />
            <select
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value })}
              className="bg-slate-600 text-white px-3 py-2 rounded text-sm"
            >
              <option>Utilities</option>
              <option>Subscriptions</option>
              <option>Insurance</option>
              <option>Rent</option>
              <option>Other</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <select
              value={formData.frequency}
              onChange={(e) => setFormData({ ...formData, frequency: e.target.value })}
              className="bg-slate-600 text-white px-3 py-2 rounded text-sm"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="yearly">Yearly</option>
            </select>
            <input
              type="date"
              value={formData.startDate}
              onChange={(e) => setFormData({ ...formData, startDate: e.target.value })}
              className="bg-slate-600 text-white px-3 py-2 rounded text-sm"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleAddRecurring}
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

      <div className="space-y-2 max-h-64 overflow-y-auto">
        {recurring.length === 0 ? (
          <p className="text-slate-400 text-sm text-center py-4">No recurring transactions</p>
        ) : (
          recurring.map((r) => (
            <div key={r.id} className="flex items-center justify-between bg-slate-700/30 p-3 rounded">
              <div>
                <p className="text-white font-medium text-sm">{r.description}</p>
                <p className="text-slate-400 text-xs">₹{r.amount.toLocaleString()} • {getFrequencyLabel(r.frequency)}</p>
              </div>
              <button
                onClick={() => handleDeleteRecurring(r.id)}
                className="text-red-400 hover:text-red-300"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
