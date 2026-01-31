import { Transaction } from "../pages/FinanceTracker";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

const COLORS = ["#4ade80", "#60a5fa", "#fbbf24", "#f87171", "#a78bfa"];

interface Props {
  transactions: Transaction[];
}

interface StatCardProps {
  label: string;
  value: number;
  color: string;
  small?: boolean;
}

const StatCard = ({ label, value, color, small }: StatCardProps) => (
  <div
    className={`bg-slate-900 border border-slate-800 rounded-xl p-4 ${
      small ? "opacity-80" : ""
    }`}
  >
    <p className="text-xs text-slate-400">{label}</p>
    <p
      className={`font-bold ${
        small ? "text-lg" : "text-2xl"
      } ${color}`}
    >
      ₹{value.toLocaleString("en-IN")}
    </p>
  </div>
);

export default function FinanceDashboard({ transactions }: Props) {
  const totalDebit = transactions.reduce((sum, t) => sum + (t.debit || 0), 0);
  const totalCredit = transactions.reduce((sum, t) => sum + (t.credit || 0), 0);
  const netBalance = totalCredit - totalDebit;

  const days =
    new Set(transactions.map(t => t.date)).size || 1;

  const avgDailySpend = Math.round(totalDebit / days);

  // ---- Category Aggregation ----
  const categoryMap: Record<string, number> = {};
  transactions.forEach(t => {
    if (t.debit > 0) {
      categoryMap[t.category] =
        (categoryMap[t.category] || 0) + t.debit;
    }
  });

  const pieData = Object.entries(categoryMap).map(
    ([name, value]) => ({
      name,
      value,
    })
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      {/* KPI CARDS */}
      <div className="lg:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Spend"
          value={totalDebit}
          color="text-red-400"
        />
        <StatCard
          label="Total Income"
          value={totalCredit}
          color="text-green-400"
        />
        <StatCard
          label="Net Balance"
          value={netBalance}
          color={netBalance >= 0 ? "text-green-300" : "text-red-300"}
        />
        <StatCard
          label="Avg Daily Spend"
          value={avgDailySpend}
          color="text-yellow-400"
          small
        />
      </div>

      {/* DONUT CHART */}
      <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">
          Spending by Category
        </h3>

        {pieData.length === 0 ? (
          <p className="text-slate-500 text-sm text-center py-12">
            No spending data available
          </p>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={85}
                  outerRadius={105}
                  paddingAngle={2}
                >
                  {pieData.map((_, index) => (
                    <Cell
                      key={index}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: number) =>
                    `₹${v.toLocaleString("en-IN")}`
                  }
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
