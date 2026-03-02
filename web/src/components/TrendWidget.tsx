import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { financeAPI } from '../lib/api';

interface MonthPoint {
  month: string;
  total: number;
}

interface Trend {
  category: string;
  months: MonthPoint[];
  pct_change_last_month: number | null;
  slope: number;
  trend: string;
}

export default function TrendWidget({ months = 6, topN = 5 }: { months?: number; topN?: number }) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>({ months: [], trends: [] });

  useEffect(() => {
    loadTrends();
  }, [months, topN]);

  const loadTrends = async () => {
    setLoading(true);
    try {
      const res = await financeAPI.getTrends(months, topN);
      setData(res.data || { months: [], trends: [] });
    } catch (err) {
      console.error('Failed to load trends', err);
    } finally {
      setLoading(false);
    }
  };

  // Transform into series data for recharts: array of objects { month: '2026-02', Food: 1234, Travel: 234 }
  const chartData = React.useMemo(() => {
    const monthsList: string[] = data.months || [];
    const trends: Trend[] = data.trends || [];
    const rows: any[] = monthsList.map((m: string) => ({ month: m }));

    trends.forEach((t) => {
      t.months.forEach((pt) => {
        const row = rows.find(r => r.month === pt.month);
        if (row) row[t.category] = pt.total;
      });
    });

    return rows;
  }, [data]);

  return (
    <div className="card-glass p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold">Spending Trends</h3>
        <div className="text-sm text-slate-400">Top categories — last {months} months</div>
      </div>

      {loading ? (
        <div className="animate-pulse space-y-3">
          <div className="h-[300px] bg-slate-800 rounded"></div>
        </div>
      ) : (
        <>
          <div className="w-full h-[300px]">
            <ResponsiveContainer>
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" tickFormatter={(m) => {
                  try { const [y,mo] = m.split('-'); return new Date(Number(y), Number(mo)-1).toLocaleString('default',{month:'short'}); } catch { return m }
                }} />
                <YAxis />
                <Tooltip formatter={(v: any) => `₹${Number(v).toLocaleString()}`} />
                <Legend />
                {/* Dynamically create a Line per category */}
                { (data.trends || []).map((t: Trend, idx: number) => (
                  <Line key={t.category} type="monotone" dataKey={t.category} stroke={PALETTE[idx % PALETTE.length]} strokeWidth={2} dot={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Small table summary */}
          <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
            {(data.trends || []).map((t: Trend) => (
              <div key={t.category} className="p-3 bg-slate-900/50 rounded">
                <div className="text-sm text-slate-300">{t.category}</div>
                <div className="text-lg font-semibold">₹{(t.months[t.months.length-1]?.total || 0).toLocaleString()}</div>
                <div className="text-xs text-slate-400">Change: {t.pct_change_last_month === null ? 'N/A' : `${t.pct_change_last_month > 0 ? '+' : ''}${t.pct_change_last_month.toFixed(1)}%`}</div>
                <div className="text-xs text-slate-400">Trend: {t.trend}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

const PALETTE = ['#60a5fa', '#34d399', '#f472b6', '#f59e0b', '#a78bfa', '#fb7185'];
