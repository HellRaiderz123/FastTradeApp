import { Transaction } from "../pages/FinanceTracker";

const categories = [
  "Food",
  "Shopping",
  "Mobile / Internet",
  "UPI Transfer",
  "Bills",
  "Investment",
  "Travel",
  "Entertainment",
  "Health",
  "Education",
  "Kid",
  "Grocery",
  "Uncategorized",
];

interface Props {
  transactions: Transaction[];
  onCategoryChange: (index: number, category: string) => void;
  onDelete: (index: number) => void; // ✅ ADD THIS
}

const normalizeCategory = (c?: string) =>
  (c || "").trim().toLowerCase();

export default function TransactionsTable({
  transactions,
  onCategoryChange,
  onDelete,
}: Props) {
  const validTransactions = transactions.filter(
    (t) =>
      t.date &&
      t.particulars &&
      t.date.toString().trim() !== "" &&
      t.particulars.toString().trim() !== ""
  );

  const showCategoryColumn = validTransactions.some(
    (t) => normalizeCategory(t.category) !== "uncategorized"
  );

  return (
    <div className="overflow-auto rounded-xl border border-slate-800 bg-slate-900">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-slate-800 text-slate-200 text-xs uppercase tracking-wide">
          <tr>
            <th className="p-3 text-left">Date</th>
            <th className="text-left">Description</th>
            <th className="text-right">Debit</th>
            <th className="text-right">Credit</th>
            {showCategoryColumn && (
              <th className="text-center">Category</th>
            )}
            <th className="text-center">Actions</th> {/* ✅ */}
          </tr>
        </thead>

        <tbody>
          {validTransactions.length === 0 ? (
            <tr>
              <td
                colSpan={showCategoryColumn ? 6 : 5}
                className="p-6 text-center text-slate-500"
              >
                No transactions
              </td>
            </tr>
          ) : (
            validTransactions.map((t, i) => (
              <tr
                key={i}
                className="border-t border-slate-800 odd:bg-slate-900 even:bg-slate-950 hover:bg-slate-800 transition"
              >
                <td className="p-3 whitespace-nowrap">
                  {t.date}
                </td>

                <td className="max-w-xl truncate">
                  {t.particulars}
                </td>

                <td className="p-3 text-right text-red-400">
                  {t.debit > 0
                    ? `₹${t.debit.toLocaleString("en-IN")}`
                    : "–"}
                </td>

                <td className="p-3 text-right text-green-400">
                  {t.credit > 0
                    ? `₹${t.credit.toLocaleString("en-IN")}`
                    : "–"}
                </td>

                {showCategoryColumn && (
                  <td className="p-3 text-center">
                    {normalizeCategory(t.category) ===
                    "uncategorized" ? (
                      <button
                        onClick={() =>
                          onCategoryChange(i, "Food")
                        }
                        className="text-xs text-slate-400 hover:text-white underline underline-offset-4"
                      >
                        Set category
                      </button>
                    ) : (
                      <select
                        value={t.category}
                        onChange={(e) =>
                          onCategoryChange(i, e.target.value)
                        }
                        className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs"
                      >
                        {categories.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    )}
                  </td>
                )}

                {/* ✅ DELETE BUTTON */}
                <td className="p-3 text-center">
                  <button
                    onClick={() => onDelete(i)}
                    className="text-red-400 hover:text-red-300 text-xs"
                    title="Delete transaction"
                  >
                    🗑️
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}