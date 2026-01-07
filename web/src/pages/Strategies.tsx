import React, { useState } from 'react';
import { Plus } from 'lucide-react';
import { StrategyManager } from '../components/StrategyManager';
import { StrategyForm } from '../components/StrategyForm';

const Strategies: React.FC = () => {
  const [showForm, setShowForm] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleFormClose = () => {
    setShowForm(false);
  };

  const handleFormSuccess = () => {
    setRefreshKey(prev => prev + 1);
    setShowForm(false);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950">
      {/* Header */}
      <div className="bg-slate-900 border-b border-slate-700 px-8 py-6 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-white">Strategies</h1>
          <p className="text-sm text-slate-400 mt-1">Manage and execute trading strategies</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          <Plus size={20} />
          <span>New Strategy</span>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <StrategyManager key={refreshKey} />
      </div>

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-700 rounded-lg shadow-xl max-w-2xl w-full mx-4">
            <StrategyForm
              onClose={handleFormClose}
              onSuccess={handleFormSuccess}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default Strategies;
