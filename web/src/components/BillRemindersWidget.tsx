import React, { useState, useEffect } from 'react';
import { Calendar, Plus, Trash2, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { financeAPI } from '../lib/api';

interface BillReminder {
  id: number;
  name: string;
  amount: number;
  due_date: string;
  category: string;
  is_paid: boolean;
  reminder_days: number;
  days_until_due: number;
  is_overdue: boolean;
}

export default function BillRemindersWidget() {
  const [bills, setBills] = useState<BillReminder[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    amount: 0,
    due_date: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    category: 'Utilities',
    reminder_days: 3,
  });

  useEffect(() => {
    loadBills();
  }, []);

  const loadBills = async () => {
    try {
      const res = await financeAPI.getBillReminders();
      // Sort by due date
      const sorted = res.data.sort((a: BillReminder, b: BillReminder) => 
        new Date(a.due_date).getTime() - new Date(b.due_date).getTime()
      );
      setBills(sorted);
    } catch (error) {
      console.error('Failed to load bills:', error);
    }
  };

  const handleAddBill = async () => {
    if (!formData.name || formData.amount <= 0) return;

    try {
      await financeAPI.createBillReminder({
        name: formData.name,
        amount: formData.amount,
        due_date: formData.due_date,
        category: formData.category,
        reminder_days: formData.reminder_days,
      });

      setFormData({
        name: '',
        amount: 0,
        due_date: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        category: 'Utilities',
        reminder_days: 3,
      });
      setShowForm(false);
      await loadBills();
    } catch (error) {
      console.error('Failed to add bill:', error);
    }
  };

  const handleMarkPaid = async (id: number) => {
    try {
      await financeAPI.markBillPaid(id);
      await loadBills();
    } catch (error) {
      console.error('Failed to mark bill as paid:', error);
    }
  };

  const handleDeleteBill = async (id: number) => {
    try {
      await financeAPI.deleteBillReminder(id);
      await loadBills();
    } catch (error) {
      console.error('Failed to delete bill:', error);
    }
  };

  const getStatusColor = (bill: BillReminder) => {
    if (bill.is_overdue) return 'bg-red-900/20 border-red-500';
    if (bill.days_until_due <= bill.reminder_days) return 'bg-orange-900/20 border-orange-500';
    return 'bg-slate-700/30 border-slate-600';
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: '2-digit',
    });
  };

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2 text-white">
          <Calendar size={20} />
          Bill Reminders
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
            placeholder="Bill Name (e.g., Electricity)"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className="w-full bg-slate-600 text-white px-3 py-2 rounded text-sm"
          />
          <div className="grid grid-cols-2 gap-3">
            <input
              type="number"
              placeholder="Amount (₹)"
              value={formData.amount}
              onChange={(e) => setFormData({ ...formData, amount: parseFloat(e.target.value) })}
              className="bg-slate-600 text-white px-3 py-2 rounded text-sm"
            />
            <input
              type="date"
              value={formData.due_date}
              onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
              className="bg-slate-600 text-white px-3 py-2 rounded text-sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <select
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value })}
              className="bg-slate-600 text-white px-3 py-2 rounded text-sm"
            >
              <option>Utilities</option>
              <option>Insurance</option>
              <option>Rent</option>
              <option>Subscription</option>
              <option>Other</option>
            </select>
            <input
              type="number"
              placeholder="Remind (days before)"
              value={formData.reminder_days}
              onChange={(e) => setFormData({ ...formData, reminder_days: parseInt(e.target.value) })}
              className="bg-slate-600 text-white px-3 py-2 rounded text-sm"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleAddBill}
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
        {bills.length === 0 ? (
          <p className="text-slate-400 text-sm text-center py-4">No unpaid bills</p>
        ) : (
          bills.map((bill) => (
            <div
              key={bill.id}
              className={`border rounded-lg p-3 transition-colors ${getStatusColor(bill)}`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {bill.is_overdue && <AlertTriangle size={16} className="text-red-400" />}
                  <span className="text-white font-medium text-sm">{bill.name}</span>
                </div>
                <div className="flex gap-1">
                  {!bill.is_paid && (
                    <button
                      onClick={() => handleMarkPaid(bill.id)}
                      className="p-1 hover:bg-green-500/20 rounded text-green-400"
                      title="Mark as paid"
                    >
                      <CheckCircle2 size={16} />
                    </button>
                  )}
                  <button
                    onClick={() => handleDeleteBill(bill.id)}
                    className="p-1 hover:bg-red-500/20 rounded text-red-400"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-300">₹{bill.amount.toLocaleString()}</span>
                <span className="text-slate-400">{formatDate(bill.due_date)}</span>
              </div>
              <div className="text-xs">
                {bill.is_overdue ? (
                  <span className="text-red-400 font-medium">⚠️ {Math.abs(bill.days_until_due)} days overdue</span>
                ) : bill.days_until_due <= bill.reminder_days ? (
                  <span className="text-orange-400">⏰ Due in {bill.days_until_due} day(s)</span>
                ) : (
                  <span className="text-slate-400">Due in {bill.days_until_due} days</span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
