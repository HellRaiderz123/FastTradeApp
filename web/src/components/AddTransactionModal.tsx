import { useForm } from "react-hook-form";
import { financeAPI } from "../lib/api";

type FormData = {
  date: string;
  description: string;
  amount: number;
  type: "DEBIT" | "CREDIT";
  category: string;
};

interface FinanceTransactionDTO {
  tran_date: string;
  description: string;
  debit: number;
  credit: number;
  balance: number;
  category: string;
  source?: string;
}

export default function AddTransactionModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const { register, handleSubmit } = useForm<FormData>();

  const onSubmit = async (data: FormData) => {
    const payload : FinanceTransactionDTO[]= [{
      tran_date: data.date,
      description: data.description,
      debit: data.type === "DEBIT" ? data.amount : 0,
      credit: data.type === "CREDIT" ? data.amount : 0,
      balance: 0,
      category: data.category,
      source: "MANUAL",
    }];

    await financeAPI.bulkCreateTransactions(payload);
    onSaved();
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="bg-slate-900 border border-slate-800 rounded-xl p-6 w-96 space-y-4"
      >
        <h2 className="text-lg font-semibold">Add Transaction</h2>

        <input
          type="date"
          {...register("date", { required: true })}
          className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2"
        />

        <input
          placeholder="Description"
          {...register("description", { required: true })}
          className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2"
        />

        <input
          type="number"
          placeholder="Amount"
          {...register("amount", { required: true, min: 1 })}
          className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2"
        />

        <select
          {...register("type")}
          className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2"
        >
          <option value="DEBIT">Expense</option>
          <option value="CREDIT">Income</option>
        </select>

        <select
          {...register("category", { required: true })}
          className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2"
        >
          <option value="">Select Category</option>
          <option value="Food">Food</option>
          <option value="Shopping">Shopping</option>
          <option value="Mobile / Internet">Mobile / Internet</option>
          <option value="UPI Transfer">UPI Transfer</option>
          <option value="Bills">Bills</option>
          <option value="Investment">Investment</option>
          <option value="Travel">Travel</option>
          <option value="Entertainment">Entertainment</option>
          <option value="Health">Health</option>
          <option value="Education">Education</option>
           <option value="Uncategorized">Uncategorized</option>
        </select>

        <div className="flex justify-end gap-3 pt-2">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="bg-blue-600 px-4 py-2 rounded text-white">
            Save
          </button>
        </div>
      </form>
    </div>
  );
}
