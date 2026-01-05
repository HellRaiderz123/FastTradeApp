import React from 'react';
import { LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp, DollarSign, Activity, Target } from 'lucide-react';
import { useTradeStore } from '../lib/store';

const Dashboard: React.FC = () => {
  const { capital, dailyPnL, trades } = useTradeStore();

  const pnlPercent = ((dailyPnL / capital) * 100).toFixed(2);
  const winCount = trades.filter((t) => t.pnl > 0).length;
  const winRate = trades.length > 0 ? ((winCount / trades.length) * 100).toFixed(1) : '0';

  // Sample data for charts
  const chartData = [
    { time: '09:15', balance: 100000, pnl: 0 },
    { time: '09:45', balance: 101200, pnl: 1200 },
    { time: '10:15', balance: 101800, pnl: 1800 },
    { time: '10:45', balance: 100900, pnl: 900 },
    { time: '11:15', balance: 102500, pnl: 2500 },
    { time: '11:45', balance: 103200, pnl: 3200 },
    { time: '12:15', balance: 102100, pnl: 2100 },
    { time: '12:45', balance: 103800, pnl: 3800 },
  ];

  const tradeStats = [
    { time: '09:00', trades: 1, wins: 1 },
    { time: '10:00', trades: 2, wins: 2 },
    { time: '11:00', trades: 3, wins: 2 },
    { time: '12:00', trades: 4, wins: 3 },
    { time: '13:00', trades: 5, wins: 4 },
  ];

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          icon={DollarSign}
          label="Capital"
          value={`₹${capital.toLocaleString()}`}
          change="+0%"
          color="blue"
        />
        <MetricCard
          icon={TrendingUp}
          label="Today's P&L"
          value={`₹${dailyPnL.toLocaleString()}`}
          change={`${pnlPercent}%`}
          color={dailyPnL >= 0 ? 'green' : 'red'}
        />
        <MetricCard
          icon={Activity}
          label="Total Trades"
          value={trades.length.toString()}
          change={`${trades.length} today`}
          color="purple"
        />
        <MetricCard
          icon={Target}
          label="Win Rate"
          value={`${winRate}%`}
          change={`${winCount}/${trades.length} wins`}
          color={parseFloat(winRate) >= 50 ? 'green' : 'orange'}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Portfolio Growth */}
        <div className="lg:col-span-2 card-glass p-6">
          <h3 className="text-lg font-semibold mb-4 text-white">Portfolio Growth</h3>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorBalance" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #475569',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: '#f1f5f9' }}
              />
              <Area type="monotone" dataKey="balance" stroke="#10B981" fillOpacity={1} fill="url(#colorBalance)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Quick Stats */}
        <div className="card-glass p-6 space-y-4">
          <h3 className="text-lg font-semibold text-white">Quick Stats</h3>
          <div className="space-y-3">
            <StatItem label="Avg Win" value="₹2,400" />
            <StatItem label="Avg Loss" value="₹1,200" />
            <StatItem label="Profit Factor" value="2.0x" />
            <StatItem label="Max Drawdown" value="-1.2%" />
            <StatItem label="Sharpe Ratio" value="1.85" />
          </div>
        </div>
      </div>

      {/* Trade Activity */}
      <div className="card-glass p-6">
        <h3 className="text-lg font-semibold mb-4 text-white">Trade Activity</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={tradeStats}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="time" stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1e293b',
                border: '1px solid #475569',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#f1f5f9' }}
            />
            <Legend />
            <Bar dataKey="trades" fill="#3B82F6" />
            <Bar dataKey="wins" fill="#10B981" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Recent Trades */}
      <div className="card-glass p-6">
        <h3 className="text-lg font-semibold mb-4 text-white">Recent Trades</h3>
        <div className="space-y-2">
          {trades.slice(0, 5).map((trade, idx) => (
            <TradeRow key={idx} trade={trade} />
          ))}
          {trades.length === 0 && (
            <p className="text-center text-slate-400 py-8">No trades today</p>
          )}
        </div>
      </div>
    </div>
  );
};

interface MetricCardProps {
  icon: React.ElementType;
  label: string;
  value: string;
  change: string;
  color: 'blue' | 'green' | 'red' | 'purple' | 'orange';
}

const MetricCard: React.FC<MetricCardProps> = ({ icon: Icon, label, value, change, color }) => {
  const colorClasses = {
    blue: 'from-blue-500 to-blue-600',
    green: 'from-green-500 to-green-600',
    red: 'from-red-500 to-red-600',
    purple: 'from-purple-500 to-purple-600',
    orange: 'from-orange-500 to-orange-600',
  };

  return (
    <div className="card-glass p-6">
      <div className={`w-12 h-12 bg-gradient-to-br ${colorClasses[color]} rounded-lg flex items-center justify-center mb-4`}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <p className="text-sm text-slate-400 mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-xs text-slate-500 mt-2">{change}</p>
    </div>
  );
};

const StatItem: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex justify-between items-center">
    <span className="text-sm text-slate-400">{label}</span>
    <span className="font-semibold text-white">{value}</span>
  </div>
);

interface TradeRowProps {
  trade: any;
}

const TradeRow: React.FC<TradeRowProps> = ({ trade }) => (
  <div className="flex justify-between items-center p-3 bg-slate-900/50 rounded-lg">
    <div>
      <p className="font-medium text-white">{trade.strategy}</p>
      <p className="text-xs text-slate-400">{trade.underlying}</p>
    </div>
    <div className="text-right">
      <p className={`font-bold ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
        ₹{Math.abs(trade.pnl).toLocaleString()}
      </p>
      <p className={`text-xs ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
        {trade.pnl >= 0 ? '+' : ''}{trade.pnl_percent.toFixed(2)}%
      </p>
    </div>
  </div>
);

export default Dashboard;
