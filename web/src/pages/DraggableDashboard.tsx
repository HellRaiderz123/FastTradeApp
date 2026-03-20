import React, { useState } from 'react';
import GridLayoutLib from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import { Lock, Unlock, Save } from 'lucide-react';
import { useToast } from '../components/Toast';
import CandleChart from '../components/CandleChart';
import { marketAPI } from '../lib/api';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const GridLayout = GridLayoutLib as any;

const DraggableDashboard: React.FC = () => {
  const { showToast } = useToast();
  const [locked, setLocked] = useState(false);
  
  // Load layout from localStorage or use default
  const loadLayout = () => {
    const saved = localStorage.getItem('dashboard_layout');
    if (saved) {
      return JSON.parse(saved);
    }
    
    // Default layout
    return [
      { i: 'nifty', x: 0, y: 0, w: 6, h: 4 },
      { i: 'banknifty', x: 6, y: 0, w: 6, h: 4 },
      { i: 'finnifty', x: 0, y: 4, w: 4, h: 3 },
      { i: 'stats', x: 4, y: 4, w: 4, h: 3 },
      { i: 'watchlist', x: 8, y: 4, w: 4, h: 3 },
    ];
  };
  
  const [layout, setLayout] = useState(loadLayout());
  
  const saveLayout = () => {
    localStorage.setItem('dashboard_layout', JSON.stringify(layout));
    showToast('success', 'Layout Saved', 'Dashboard layout saved!');
  };
  
  const resetLayout = () => {
    if (!confirm('Reset to default layout?')) return;
    localStorage.removeItem('dashboard_layout');
    setLayout(loadLayout());
  };
  
  const onLayoutChange = (newLayout: any) => {
    setLayout(newLayout);
  };
  
  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="max-w-[1800px] mx-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">Draggable Dashboard</h1>
            <p className="text-gray-400 mt-1">Customize your layout by dragging and resizing widgets</p>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={resetLayout}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors"
            >
              Reset Layout
            </button>
            
            <button
              onClick={saveLayout}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              <Save className="w-4 h-4" />
              Save Layout
            </button>
            
            <button
              onClick={() => setLocked(!locked)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                locked
                  ? 'bg-red-600 hover:bg-red-700 text-white'
                  : 'bg-green-600 hover:bg-green-700 text-white'
              }`}
            >
              {locked ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
              {locked ? 'Locked' : 'Unlocked'}
            </button>
          </div>
        </div>
        
        {/* Grid Layout */}
        <GridLayout
          className="layout"
          layout={layout}
          cols={12}
          rowHeight={80}
          width={1760}
          isDraggable={!locked}
          isResizable={!locked}
          onLayoutChange={onLayoutChange}
          draggableHandle=".drag-handle"
        >
          {/* NIFTY Chart Widget */}
          <div key="nifty" className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden">
            <div className="drag-handle bg-gray-800 px-4 py-2 cursor-move border-b border-gray-700 flex items-center justify-between">
              <span className="text-white font-semibold">NIFTY</span>
              <span className="text-gray-500 text-xs">Drag to move</span>
            </div>
            <div className="p-2">
              <CandleChart symbol="NIFTY" defaultTimeframe="15m" height={250} showTimeframeSelector={false} />
            </div>
          </div>
          
          {/* BANKNIFTY Chart Widget */}
          <div key="banknifty" className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden">
            <div className="drag-handle bg-gray-800 px-4 py-2 cursor-move border-b border-gray-700 flex items-center justify-between">
              <span className="text-white font-semibold">BANKNIFTY</span>
              <span className="text-gray-500 text-xs">Drag to move</span>
            </div>
            <div className="p-2">
              <CandleChart symbol="BANKNIFTY" defaultTimeframe="15m" height={250} showTimeframeSelector={false} />
            </div>
          </div>
          
          {/* FINNIFTY Chart Widget */}
          <div key="finnifty" className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden">
            <div className="drag-handle bg-gray-800 px-4 py-2 cursor-move border-b border-gray-700 flex items-center justify-between">
              <span className="text-white font-semibold">FINNIFTY</span>
              <span className="text-gray-500 text-xs">Drag to move</span>
            </div>
            <div className="p-2">
              <CandleChart symbol="FINNIFTY" defaultTimeframe="5m" height={180} showTimeframeSelector={false} />
            </div>
          </div>
          
          {/* Stats Widget */}
          <div key="stats" className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden">
            <div className="drag-handle bg-gray-800 px-4 py-2 cursor-move border-b border-gray-700 flex items-center justify-between">
              <span className="text-white font-semibold">Market Stats</span>
              <span className="text-gray-500 text-xs">Drag to move</span>
            </div>
            <div className="p-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-gray-800 rounded p-3">
                  <p className="text-gray-400 text-xs">Advances</p>
                  <p className="text-green-400 text-2xl font-bold mt-1">342</p>
                </div>
                <div className="bg-gray-800 rounded p-3">
                  <p className="text-gray-400 text-xs">Declines</p>
                  <p className="text-red-400 text-2xl font-bold mt-1">158</p>
                </div>
                <div className="bg-gray-800 rounded p-3">
                  <p className="text-gray-400 text-xs">Volume</p>
                  <p className="text-blue-400 text-xl font-bold mt-1">2.3B</p>
                </div>
                <div className="bg-gray-800 rounded p-3">
                  <p className="text-gray-400 text-xs">VIX</p>
                  <p className="text-yellow-400 text-xl font-bold mt-1">16.5</p>
                </div>
              </div>
            </div>
          </div>
          
          {/* Watchlist Widget */}
          <div key="watchlist" className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden">
            <div className="drag-handle bg-gray-800 px-4 py-2 cursor-move border-b border-gray-700 flex items-center justify-between">
              <span className="text-white font-semibold">Quick Watchlist</span>
              <span className="text-gray-500 text-xs">Drag to move</span>
            </div>
            <div className="p-4">
              <div className="space-y-2 text-sm">
                {['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK'].map((symbol) => (
                  <div key={symbol} className="flex items-center justify-between py-2 border-b border-gray-800">
                    <span className="text-white">{symbol}</span>
                    <span className="text-green-400">+2.3%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </GridLayout>
        
        {/* Info */}
        <div className="bg-blue-900/20 border border-blue-800 rounded-lg p-4 mt-6">
          <p className="text-blue-400 text-sm">
            💡 <strong>Tip:</strong> Click "{locked ? 'Locked' : 'Unlocked'}" to {locked ? 'unlock' : 'lock'} the layout. 
            Drag widgets by their header and resize from the bottom-right corner. Click "Save Layout" to persist your changes.
          </p>
        </div>
      </div>
    </div>
  );
};

export default DraggableDashboard;
