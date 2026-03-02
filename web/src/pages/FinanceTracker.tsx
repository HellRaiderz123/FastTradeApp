import { useEffect, useState } from "react";
import Papa from "papaparse"

import FinanceDashboard from "../components/FinanceDashboard";
import TransactionsTable from "../components/TransactionsTable";
import { financeAPI } from "../lib/api";
import AddTransactionModal from "../components/AddTransactionModal";
import RecurringTransactionsWidget from "../components/RecurringTransactionsWidget";
import BudgetWidget from "../components/BudgetWidget";
import SavingsGoalsWidget from "../components/SavingsGoalsWidget";
import BillRemindersWidget from "../components/BillRemindersWidget";
import ExpenseForecastWidget from "../components/ExpenseForecastWidget";
import TrendWidget from "../components/TrendWidget";

// ---------------- Types ----------------
export interface Transaction {
  id?: number;
  date: string;
  particulars: string;
  debit: number;
  credit: number;
  balance: number;
  category: string;
}

interface FinanceTransactionDTO {
  tran_date: string;
  description: string;
  debit: number;
  credit: number;
  balance: number;
  category: string;
  source?: string;
}

// ---------------- Month Helpers (MUST BE ABOVE USAGE) ----------------
const getMonthKey = (date: string) => {
  // YYYY-MM-DD → YYYY-MM
  return date.slice(0, 7);
};

const formatMonthLabel = (key: string) => {
  const [y, m] = key.split("-");
  return new Date(Number(y), Number(m) - 1).toLocaleString(
    "default",
    { month: "short", year: "numeric" }
  );
};

// ---------------- Other Helpers ----------------
const parseAmount = (v: any): number => {
  if (v === null || v === undefined) return 0;
  const s = v.toString().replace(/,/g, "").trim();
  return s === "" ? 0 : Number(s);
};

const suggestCategory = (text: string) => {
  const t = text.toUpperCase();
  if (t.includes("AIRTEL")) return "Mobile / Internet";
  if (t.includes("ZOMATO") || t.includes("SWIGGY")) return "Food";
  if (t.includes("AMAZON") || t.includes("FLIPKART")) return "Shopping";
  return "Uncategorized";
};

const normalizeDate = (raw: string): string => {
  if (!raw) return "";
  const d = raw.trim();

  if (/^\d{2}-\d{2}-\d{4}$/.test(d)) {
    const [day, month, year] = d.split("-");
    return `${year}-${month}-${day}`;
  }

  if (/^\d{2}\/\d{2}\/\d{4}$/.test(d)) {
    const [day, month, year] = d.split("/");
    return `${year}-${month}-${day}`;
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(d)) {
    return d;
  }

  return "";
};
// ------------------------------------------------

export default function FinanceTracker() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedMonth, setSelectedMonth] = useState<string>("ALL");
  const [open, setOpen] = useState(false);

  // 🔹 Load on mount
  useEffect(() => {
    loadTransactions();
  }, []);

  const loadTransactions = async () => {
    const res = await financeAPI.getTransactions();
    const data: Transaction[] = res.data.map((t: any) => ({
      id: t.id,
      date: t.tran_date,
      particulars: t.description,
      debit: t.debit,
      credit: t.credit,
      balance: t.balance,
      category: t.category,
    }));
    setTransactions(data);
  };

  // 🔹 Month options
  const availableMonths = Array.from(
    new Set(transactions.map(t => getMonthKey(t.date)))
  )
    .sort()
    .reverse();

  // 🔹 Filtered data
  const filteredTransactions =
    selectedMonth === "ALL"
      ? transactions
      : transactions.filter(
          t => getMonthKey(t.date) === selectedMonth
        );

  // 🔹 Delete
  const deleteTransaction = async (index: number) => {
    const tx = filteredTransactions[index];
    if (!tx?.id) return;

    await financeAPI.deleteTransaction(tx.id);

    setTransactions(prev =>
      prev.filter(t => t.id !== tx.id)
    );
  };

  // 🔹 CSV Upload
  const handleCSVUpload = (file: File) => {
    setLoading(true);

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: async (results: any) => {
        const parsed: FinanceTransactionDTO[] = results.data
          .map((row: any) => ({
            tran_date: normalizeDate(row["Tran Date"]),
            description: row["PARTICULARS"],
            debit: parseAmount(row["DR"]),
            credit: parseAmount(row["CR"]),
            balance: parseAmount(row["BAL"]),
            category: suggestCategory(row["PARTICULARS"] || ""),
            source: "AXIS",
          }))
          .filter(
            (t: FinanceTransactionDTO) =>
              t.tran_date &&
              /^\d{4}-\d{2}-\d{2}$/.test(t.tran_date) &&
              t.description &&
              t.description.trim() !== ""
          );

        if (parsed.length > 0) {
          await financeAPI.bulkCreateTransactions(parsed);
          await loadTransactions();
        }

        setLoading(false);
      },
      error: () => setLoading(false),
    });
  };

  // 🔹 Update category
  const updateCategory = async (index: number, category: string) => {
    const tx = filteredTransactions[index];
    if (!tx?.id) return;

    await financeAPI.updateTransactionCategory(tx.id, category);

    setTransactions(prev =>
      prev.map(t =>
        t.id === tx.id ? { ...t, category } : t
      )
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between bg-slate-900 border border-slate-800 rounded-xl px-5 py-4">
        <h1 className="text-xl font-semibold flex items-center gap-2">
          💰 <span>Finance Tracker</span>
        </h1>

        <button
          onClick={() => setOpen(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded"
        >
          + Add Transaction
        </button>

        <div className="flex items-center gap-3">
          {/* Month Filter */}
          <select
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-sm"
          >
            <option value="ALL">All Months</option>
            {availableMonths.map(m => (
              <option key={m} value={m}>
                {formatMonthLabel(m)}
              </option>
            ))}
          </select>

          {/* Import */}
          <label className="cursor-pointer bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded-md text-sm">
            {loading ? "Importing..." : "Import CSV"}
            <input
              type="file"
              accept=".csv"
              hidden
              onChange={(e) =>
                e.target.files &&
                handleCSVUpload(e.target.files[0])
              }
            />
          </label>
        </div>
      </div>

      {/* Dashboard */}
      <FinanceDashboard transactions={filteredTransactions} />

      {/* Enhanced Features Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recurring Transactions */}
        <RecurringTransactionsWidget />

        {/* Budgets */}
        <BudgetWidget />

        {/* Savings Goals */}
        <SavingsGoalsWidget />

        {/* Bill Reminders */}
        <BillRemindersWidget />
      </div>

      {/* Expense Forecast & Trends */}
      <div className="lg:col-span-2 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ExpenseForecastWidget />
        <TrendWidget />
      </div>

      {/* Transactions */}
      <TransactionsTable
        transactions={filteredTransactions}
        onCategoryChange={updateCategory}
        onDelete={deleteTransaction}
      />

      {/* Add Transaction Modal */}
      {open && (
        <AddTransactionModal
          onClose={() => setOpen(false)}
          onSaved={loadTransactions}
        />
      )}
    </div>
  );
}
