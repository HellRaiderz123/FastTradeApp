import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Modal,
  Platform,
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Line, Path, Rect } from 'react-native-svg';
import { useRouter, useFocusEffect } from 'expo-router';
import { financeAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, PrimaryButton, ProgressBar, ScreenHeader, StatCard, Tag } from '../components/ui';

type Transaction = {
  id?: number;
  tran_date?: string;
  description?: string;
  debit?: number;
  credit?: number;
  balance?: number;
  category?: string;
};

type Budget = {
  id?: number;
  category?: string;
  monthly_limit?: number;
  alert_threshold?: number;
  month?: string;
};

type BudgetStatus = {
  budget: Budget;
  spent: number;
  remaining: number;
  percent_used: number;
};

type Goal = {
  id?: number;
  name?: string;
  target_amount?: number;
  current_amount?: number;
  progress_percent?: number;
  days_remaining?: number;
};

type Bill = {
  id?: number;
  name?: string;
  category?: string;
  amount?: number;
  due_date?: string;
  is_paid?: boolean;
  is_overdue?: boolean;
  days_until_due?: number;
};

type TrendMonthPoint = {
  month: string;
  total: number;
};

type TrendSeries = {
  category: string;
  months: TrendMonthPoint[];
  pct_change_last_month: number | null;
  trend: string;
};

type TrendPayload = {
  months: string[];
  trends: TrendSeries[];
};

type Forecast = {
  category: string;
  predicted_amount: number;
  confidence: number;
  forecast_month?: string;
};

type TransactionFormState = {
  date: string;
  description: string;
  amount: string;
  type: 'DEBIT' | 'CREDIT';
  category: string;
};

type BudgetFormState = {
  category: string;
  monthly_limit: string;
  alert_threshold: string;
};

const CATEGORY_OPTIONS = [
  'Food',
  'Shopping',
  'Mobile / Internet',
  'UPI Transfer',
  'Bills',
  'Investment',
  'Travel',
  'Entertainment',
  'Health',
  'Education',
  'Kid',
  'Grocery',
  'Utilities',
  'Transportation',
  'Other',
  'Uncategorized',
];

const CHART_COLORS = ['#60A5FA', '#34D399', '#F59E0B', '#F472B6', '#A78BFA'];

const money = (value: number) => `₹${Math.abs(value || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
const monthKey = (dateString?: string) => (dateString || '').slice(0, 7);
const formatMonthLabel = (key: string) => {
  try {
    const [year, month] = key.split('-').map(Number);
    return new Date(year, month - 1, 1).toLocaleString('en-IN', { month: 'short', year: 'numeric' });
  } catch {
    return key;
  }
};
const todayIso = () => new Date().toISOString().slice(0, 10);

export default function FinanceScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [savingTransaction, setSavingTransaction] = useState(false);
  const [savingBudget, setSavingBudget] = useState(false);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [budgetStatuses, setBudgetStatuses] = useState<BudgetStatus[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [bills, setBills] = useState<Bill[]>([]);
  const [trendData, setTrendData] = useState<TrendPayload>({ months: [], trends: [] });
  const [forecasts, setForecasts] = useState<Forecast[]>([]);
  const [selectedMonth, setSelectedMonth] = useState('');
  const [transactionModalVisible, setTransactionModalVisible] = useState(false);
  const [budgetModalVisible, setBudgetModalVisible] = useState(false);
  const [monthModalVisible, setMonthModalVisible] = useState(false);
  const [transactionForm, setTransactionForm] = useState<TransactionFormState>({
    date: todayIso(),
    description: '',
    amount: '',
    type: 'DEBIT',
    category: 'Food',
  });
  const [budgetForm, setBudgetForm] = useState<BudgetFormState>({
    category: 'Food',
    monthly_limit: '',
    alert_threshold: '80',
  });
  const [categoryModalTx, setCategoryModalTx] = useState<Transaction | null>(null);
  const [savingCategory, setSavingCategory] = useState(false);

  const load = useCallback(async (monthOverride?: string) => {
    const month = monthOverride ?? selectedMonth ?? '';
    try {
      const [txRes, goalRes, billRes, trendRes, budgetRes, forecastRes] = await Promise.allSettled([
        financeAPI.getTransactions(),
        financeAPI.getSavingsGoals(),
        financeAPI.getBillReminders(),
        financeAPI.getTrends(6, 5),
        financeAPI.getBudgets(),
        financeAPI.getExpenseForecasts(month || undefined),
      ]);

      let nextTransactions: Transaction[] = [];
      if (txRes.status === 'fulfilled' && Array.isArray(txRes.value.data)) {
        nextTransactions = txRes.value.data;
        setTransactions(nextTransactions);
      }
      if (goalRes.status === 'fulfilled') setGoals(Array.isArray(goalRes.value.data) ? goalRes.value.data : []);
      if (billRes.status === 'fulfilled') setBills(Array.isArray(billRes.value.data) ? billRes.value.data : []);
      if (forecastRes.status === 'fulfilled') setForecasts(Array.isArray(forecastRes.value.data) ? forecastRes.value.data : []);
      if (trendRes.status === 'fulfilled') {
        const data = trendRes.value.data;
        setTrendData({
          months: Array.isArray(data?.months) ? data.months : [],
          trends: Array.isArray(data?.trends) ? data.trends : [],
        });
      }

      if (budgetRes.status === 'fulfilled' && Array.isArray(budgetRes.value.data)) {
        const budgets = budgetRes.value.data as Budget[];
        const statusResults = await Promise.allSettled(
          budgets.map((budget) => financeAPI.getBudgetStatus(String(budget.category || ''), month || undefined))
        );
        const statuses = statusResults
          .filter((result): result is PromiseFulfilledResult<any> => result.status === 'fulfilled')
          .map((result) => result.value.data)
          .filter(Boolean);
        setBudgetStatuses(statuses);
      } else {
        setBudgetStatuses([]);
      }

      if (nextTransactions.length > 0) {
        const months = Array.from(new Set(nextTransactions.map((tx) => monthKey(tx.tran_date)).filter(Boolean))).sort().reverse();
        // Only auto-set month on first load (when no month is selected yet)
        setSelectedMonth((prev) => prev || months[0] || '');
      }
    } catch {
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedMonth]);

  useEffect(() => {
    load();
  }, []);

  useFocusEffect(
    useCallback(() => {
      load(selectedMonth || undefined);
    }, [selectedMonth])
  );

  const availableMonths = useMemo(() => {
    const txMonths = transactions.map((tx) => monthKey(tx.tran_date)).filter(Boolean);
    const trendMonths = trendData.months || [];
    const fallbackMonth = todayIso().slice(0, 7);
    return Array.from(new Set([...txMonths, ...trendMonths, fallbackMonth])).sort().reverse();
  }, [transactions, trendData]);

  const filteredTransactions = useMemo(() => {
    if (!selectedMonth) return transactions;
    return transactions.filter((tx) => monthKey(tx.tran_date) === selectedMonth);
  }, [transactions, selectedMonth]);

  const monthlySpend = useMemo(() => filteredTransactions.reduce((sum, tx) => sum + Number(tx.debit || 0), 0), [filteredTransactions]);
  const monthlyIncome = useMemo(() => filteredTransactions.reduce((sum, tx) => sum + Number(tx.credit || 0), 0), [filteredTransactions]);
  const netFlow = monthlyIncome - monthlySpend;
  const unpaidBills = bills.filter((bill) => !bill.is_paid);
  const selectedMonthTrendTotals = useMemo(() => (
    trendData.trends.map((trend) => ({
      category: trend.category,
      total: Number(trend.months.find((point) => point.month === selectedMonth)?.total || 0),
      pctChange: trend.pct_change_last_month,
      trend: trend.trend,
      history: trend.months,
    })).filter((item) => item.total > 0)
  ), [trendData, selectedMonth]);

  const submitTransaction = async () => {
    const amount = Number(transactionForm.amount);
    if (!transactionForm.date || !transactionForm.description.trim() || !amount) {
      Alert.alert('Missing fields', 'Date, description, and amount are required.');
      return;
    }

    setSavingTransaction(true);
    try {
      await financeAPI.bulkCreateTransactions([
        {
          tran_date: transactionForm.date,
          description: transactionForm.description.trim(),
          debit: transactionForm.type === 'DEBIT' ? amount : 0,
          credit: transactionForm.type === 'CREDIT' ? amount : 0,
          balance: 0,
          category: transactionForm.category,
          source: 'MANUAL',
        },
      ]);
      setTransactionModalVisible(false);
      setTransactionForm({ date: todayIso(), description: '', amount: '', type: 'DEBIT', category: 'Food' });
      await load(selectedMonth);
    } catch {
      Alert.alert('Failed', 'Could not add transaction.');
    }
    setSavingTransaction(false);
  };

  const submitBudget = async () => {
    const monthlyLimit = Number(budgetForm.monthly_limit);
    const alertThreshold = Number(budgetForm.alert_threshold || '80');
    if (!budgetForm.category || !monthlyLimit) {
      Alert.alert('Missing fields', 'Category and monthly limit are required.');
      return;
    }

    setSavingBudget(true);
    try {
      await financeAPI.createBudget({
        category: budgetForm.category,
        monthly_limit: monthlyLimit,
        alert_threshold: alertThreshold,
      });
      setBudgetModalVisible(false);
      setBudgetForm({ category: 'Food', monthly_limit: '', alert_threshold: '80' });
      await load(selectedMonth);
    } catch {
      Alert.alert('Failed', 'Could not create budget.');
    }
    setSavingBudget(false);
  };

  const deleteTransaction = (transaction: Transaction) => {
    if (!transaction.id) return;
    Alert.alert('Delete Transaction', 'This will permanently remove the transaction.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await financeAPI.deleteTransaction(transaction.id as number);
            await load(selectedMonth);
          } catch {
            Alert.alert('Failed', 'Could not delete transaction.');
          }
        },
      },
    ]);
  };

  const updateCategory = async (tx: Transaction, category: string) => {
    if (!tx.id) return;
    setSavingCategory(true);
    try {
      await financeAPI.updateTransactionCategory(tx.id, category);
      setTransactions((prev) => prev.map((t) => t.id === tx.id ? { ...t, category } : t));
      setCategoryModalTx(null);
    } catch {
      Alert.alert('Failed', 'Could not update category.');
    }
    setSavingCategory(false);
  };

  const deleteBudget = (budgetId?: number) => {
    if (!budgetId) return;
    Alert.alert('Delete Budget', 'Remove this monthly budget?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await financeAPI.deleteBudget(budgetId);
            await load(selectedMonth);
          } catch {
            Alert.alert('Failed', 'Could not delete budget.');
          }
        },
      },
    ]);
  };

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safeArea}>
        <ScreenHeader
          title="Finance"
          subtitle="Month filters, trends, budgets, and transaction management"
          badge={<Tag label="EXPANDED" color={Colors.green} bg={Colors.greenBg} />}
          onBack={() => router.back()}
        >
          <View style={styles.headerActions}>
            <PrimaryButton title="Add Tx" onPress={() => setTransactionModalVisible(true)} small style={styles.headerButton} />
            <PrimaryButton title="Add Budget" onPress={() => setBudgetModalVisible(true)} variant="ghost" small style={styles.headerButton} />
            {Platform.OS === 'android' && (
              <PrimaryButton
                title="📱 Scan SMS"
                onPress={() => router.push('/smsScanner')}
                variant="success"
                small
                style={styles.headerButton}
              />
            )}
          </View>
        </ScreenHeader>

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(selectedMonth); }} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          <GlassCard style={styles.filterCard}>
            <Text style={styles.filterLabel}>Month</Text>
            <TouchableOpacity style={styles.selectButton} activeOpacity={0.85} onPress={() => setMonthModalVisible(true)}>
              <Text style={styles.selectButtonText}>{selectedMonth ? formatMonthLabel(selectedMonth) : 'Select month'}</Text>
              <Ionicons name="chevron-down-outline" size={18} color={Colors.textPrimary} />
            </TouchableOpacity>
          </GlassCard>

          <View style={styles.statsRow}>
            <StatCard label="Spend" value={money(monthlySpend)} style={{ marginRight: 8 }} />
            <StatCard label="Income" value={money(monthlyIncome)} color={Colors.green} />
          </View>
          <View style={styles.statsRow}>
            <StatCard label="Net Flow" value={`${netFlow >= 0 ? '+' : '-'}${money(netFlow)}`} color={netFlow >= 0 ? Colors.green : Colors.red} style={{ marginRight: 8 }} />
            <StatCard label="Transactions" value={`${filteredTransactions.length}`} />
          </View>

          <GlassCard style={styles.sectionCard}>
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle}>Monthly Graph</Text>
              <Tag label={selectedMonth ? formatMonthLabel(selectedMonth) : 'No Month'} />
            </View>
            <SpendBarChart income={monthlyIncome} spend={monthlySpend} />
          </GlassCard>

          <GlassCard style={styles.sectionCard}>
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle}>Trend Graphs</Text>
              <Tag label={`${trendData.trends.length} categories`} />
            </View>
            {trendData.trends.length === 0 ? (
              <Text style={styles.emptyHint}>No trend data yet</Text>
            ) : (
              <>
                <TrendLineChart months={trendData.months} trends={trendData.trends} />
                <View style={{ marginTop: 12 }}>
                  {selectedMonthTrendTotals.slice(0, 5).map((item, idx) => (
                    <View key={item.category} style={styles.trendCard}>
                      <View style={styles.itemHeader}>
                        <View style={styles.trendTitleWrap}>
                          <View style={[styles.trendDot, { backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] }]} />
                          <Text style={styles.itemTitle}>{item.category}</Text>
                        </View>
                        <Text style={styles.itemValue}>{money(item.total)}</Text>
                      </View>
                      <Text style={styles.itemSub}>
                        {item.pctChange == null ? 'No prior month comparison' : `${item.pctChange >= 0 ? '+' : ''}${item.pctChange.toFixed(1)}% vs last month`}  ·  {item.trend}
                      </Text>
                      <MiniTrendSparkline data={item.history} color={CHART_COLORS[idx % CHART_COLORS.length]} />
                    </View>
                  ))}
                </View>
              </>
            )}
          </GlassCard>

          <GlassCard style={styles.sectionCard}>
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle}>Expense Forecast</Text>
              <Tag label={`${forecasts.length} categories`} />
            </View>
            {forecasts.length === 0 ? (
              <Text style={styles.emptyHint}>No forecast data yet. Add more transactions to generate forecasts.</Text>
            ) : (
              forecasts.map((fc, idx) => {
                const confidence = Math.round((fc.confidence || 0) * 100);
                return (
                  <View key={`${fc.category}-${idx}`} style={styles.itemRow}>
                    <View style={styles.itemHeader}>
                      <Text style={styles.itemTitle}>{fc.category}</Text>
                      <Text style={[styles.itemValue, { color: Colors.amber }]}>{money(fc.predicted_amount)}</Text>
                    </View>
                    <Text style={styles.itemSub}>Predicted next month  ·  {confidence}% confidence</Text>
                    <ProgressBar value={confidence} color={confidence >= 70 ? Colors.green : confidence >= 40 ? Colors.amber : Colors.red} style={{ marginTop: 6 }} />
                  </View>
                );
              })
            )}
          </GlassCard>

          <GlassCard style={styles.sectionCard}>
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle}>Monthly Budgets</Text>
              <Tag label={`${budgetStatuses.length}`} />
            </View>
            {budgetStatuses.length === 0 ? (
              <Text style={styles.emptyHint}>No budgets for {selectedMonth ? formatMonthLabel(selectedMonth) : 'this month'}</Text>
            ) : (
              budgetStatuses.map((status, idx) => {
                const threshold = Number(status.budget.alert_threshold || 80);
                const over = status.percent_used > 100;
                const warning = status.percent_used >= threshold;
                return (
                  <View key={`${status.budget.id || status.budget.category}-${idx}`} style={styles.itemRow}>
                    <View style={styles.itemHeader}>
                      <Text style={styles.itemTitle}>{status.budget.category || 'Uncategorized'}</Text>
                      <TouchableOpacity onPress={() => deleteBudget(status.budget.id)}>
                        <Ionicons name="trash-outline" size={16} color={Colors.red} />
                      </TouchableOpacity>
                    </View>
                    <Text style={styles.itemSub}>{money(status.spent)} spent  ·  {money(status.remaining)} remaining</Text>
                    <ProgressBar value={status.percent_used} color={over ? Colors.red : warning ? Colors.amber : Colors.green} style={{ marginTop: 8 }} />
                    <View style={styles.budgetFooter}>
                      <Text style={[styles.budgetPct, { color: over ? Colors.red : warning ? Colors.amber : Colors.textSecondary }]}>{status.percent_used.toFixed(0)}%</Text>
                      <Text style={styles.budgetLimit}>Limit {money(Number(status.budget.monthly_limit || 0))}</Text>
                    </View>
                  </View>
                );
              })
            )}
          </GlassCard>

          <GlassCard style={styles.sectionCard}>
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle}>Savings Goals</Text>
              <Tag label={`${goals.length}`} />
            </View>
            {goals.length === 0 ? (
              <Text style={styles.emptyHint}>No goals yet</Text>
            ) : (
              goals.slice(0, 5).map((goal, idx) => {
                const progress = Number(goal.progress_percent ?? 0);
                return (
                  <View key={`${goal.id || goal.name}-${idx}`} style={styles.itemRow}>
                    <View style={styles.itemHeader}>
                      <Text style={styles.itemTitle}>{goal.name || 'Goal'}</Text>
                      <Text style={styles.itemValue}>{Math.round(progress)}%</Text>
                    </View>
                    <Text style={styles.itemSub}>{money(Number(goal.current_amount || 0))} / {money(Number(goal.target_amount || 0))}{typeof goal.days_remaining === 'number' ? `  ·  ${goal.days_remaining}d left` : ''}</Text>
                    <ProgressBar value={progress} color={Colors.green} style={{ marginTop: 6 }} />
                  </View>
                );
              })
            )}
          </GlassCard>

          <GlassCard style={styles.sectionCard}>
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle}>Bill Reminders</Text>
              <Tag label={`${unpaidBills.length} due`} color={unpaidBills.length ? Colors.amber : Colors.textSecondary} bg={unpaidBills.length ? Colors.amberBg : Colors.bgGlassStrong} />
            </View>
            {unpaidBills.length === 0 ? (
              <Text style={styles.emptyHint}>No unpaid bills</Text>
            ) : (
              unpaidBills.slice(0, 6).map((bill, idx) => (
                <View key={`${bill.id || bill.name}-${idx}`} style={styles.billRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.itemTitle}>{bill.name || 'Bill'}</Text>
                    <Text style={styles.itemSub}>{bill.category || 'General'}  ·  Due {bill.due_date || '-'}</Text>
                  </View>
                  <View style={styles.billRight}>
                    <Text style={[styles.itemValue, { color: bill.is_overdue ? Colors.red : Colors.textSecondary }]}>{money(Number(bill.amount || 0))}</Text>
                    {typeof bill.days_until_due === 'number' ? <Text style={[styles.billMeta, { color: bill.days_until_due < 0 ? Colors.red : Colors.textMuted }]}>{bill.days_until_due < 0 ? `${Math.abs(bill.days_until_due)}d overdue` : `${bill.days_until_due}d left`}</Text> : null}
                  </View>
                </View>
              ))
            )}
          </GlassCard>

          <GlassCard style={styles.sectionCard}>
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle}>Transactions</Text>
              <Tag label={`${filteredTransactions.length}`} />
            </View>
            {filteredTransactions.length === 0 ? (
              <EmptyState icon="🧾" title="No transactions for this month" subtitle="Add one manually or switch the month filter." />
            ) : (
              filteredTransactions.map((tx, idx) => {
                const debit = Number(tx.debit || 0);
                const credit = Number(tx.credit || 0);
                const amount = credit > 0 ? credit : debit;
                const isCredit = credit > 0;
                return (
                  <View key={`${tx.id || tx.tran_date}-${idx}`} style={styles.txRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.itemTitle}>{tx.description || 'Transaction'}</Text>
                      <Text style={styles.itemSub}>{tx.tran_date || '-'}</Text>
                      <TouchableOpacity onPress={() => setCategoryModalTx(tx)} style={styles.categoryChip}>
                        <Text style={styles.categoryChipText}>{tx.category || 'Uncategorized'}</Text>
                        <Ionicons name="pencil-outline" size={11} color={Colors.accent} style={{ marginLeft: 4 }} />
                      </TouchableOpacity>
                    </View>
                    <View style={styles.txRight}>
                      <Text style={[styles.itemValue, { color: isCredit ? Colors.green : Colors.textPrimary }]}>{isCredit ? '+' : '-'}{money(amount)}</Text>
                      <TouchableOpacity onPress={() => deleteTransaction(tx)} style={styles.deleteButton}>
                        <Ionicons name="trash-outline" size={16} color={Colors.red} />
                      </TouchableOpacity>
                    </View>
                  </View>
                );
              })
            )}
          </GlassCard>

          <View style={{ height: 100 }} />
        </ScrollView>
      </SafeAreaView>

      {/* Category picker modal */}
      <Modal visible={!!categoryModalTx} transparent animationType="fade" onRequestClose={() => setCategoryModalTx(null)}>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Change Category</Text>
              <TouchableOpacity onPress={() => setCategoryModalTx(null)}>
                <Ionicons name="close-outline" size={22} color={Colors.textPrimary} />
              </TouchableOpacity>
            </View>
            {categoryModalTx && (
              <Text style={[styles.itemSub, { marginBottom: 12 }]} numberOfLines={1}>
                {categoryModalTx.description}
              </Text>
            )}
            <ScrollView style={{ maxHeight: 340 }}>
              {CATEGORY_OPTIONS.map((cat) => {
                const active = cat === categoryModalTx?.category;
                return (
                  <TouchableOpacity
                    key={cat}
                    disabled={savingCategory}
                    style={[styles.optionRow, active && styles.optionRowActive]}
                    onPress={() => categoryModalTx && updateCategory(categoryModalTx, cat)}
                  >
                    <Text style={[styles.optionRowText, active && styles.optionRowTextActive]}>{cat}</Text>
                    {active ? <Ionicons name="checkmark-outline" size={18} color={Colors.accentLight} /> : null}
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </View>
        </View>
      </Modal>

      <OptionListModal
        visible={monthModalVisible}
        title="Select Month"
        options={availableMonths.map((month) => ({ label: formatMonthLabel(month), value: month }))}
        selectedValue={selectedMonth}
        onClose={() => setMonthModalVisible(false)}
        onSelect={(value) => {
          setSelectedMonth(value);
          setMonthModalVisible(false);
        }}
      />

      <FormModal visible={transactionModalVisible} title="Add Transaction" onClose={() => setTransactionModalVisible(false)}>
        <FormField label="Date">
          <TextInput value={transactionForm.date} onChangeText={(value) => setTransactionForm((prev) => ({ ...prev, date: value }))} placeholder="YYYY-MM-DD" placeholderTextColor={Colors.textMuted} style={styles.input} />
        </FormField>
        <FormField label="Description">
          <TextInput value={transactionForm.description} onChangeText={(value) => setTransactionForm((prev) => ({ ...prev, description: value }))} placeholder="Salary, Swiggy, UPI transfer..." placeholderTextColor={Colors.textMuted} style={styles.input} />
        </FormField>
        <View style={styles.rowInputs}>
          <View style={{ flex: 1, marginRight: 8 }}>
            <FormField label="Amount">
              <TextInput value={transactionForm.amount} onChangeText={(value) => setTransactionForm((prev) => ({ ...prev, amount: value }))} placeholder="0" placeholderTextColor={Colors.textMuted} style={styles.input} keyboardType="numeric" />
            </FormField>
          </View>
          <View style={{ flex: 1 }}>
            <FormField label="Type">
              <SegmentedControl
                values={['DEBIT', 'CREDIT']}
                selected={transactionForm.type}
                onChange={(value) => setTransactionForm((prev) => ({ ...prev, type: value as 'DEBIT' | 'CREDIT' }))}
              />
            </FormField>
          </View>
        </View>
        <FormField label="Category">
          <OptionButton label={transactionForm.category} onPress={() => {}} />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
            {CATEGORY_OPTIONS.map((category) => {
              const active = category === transactionForm.category;
              return (
                <TouchableOpacity key={category} onPress={() => setTransactionForm((prev) => ({ ...prev, category }))} style={[styles.choiceChip, active && styles.choiceChipActive]}>
                  <Text style={[styles.choiceChipText, active && styles.choiceChipTextActive]}>{category}</Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </FormField>
        <View style={styles.modalActions}>
          <PrimaryButton title="Cancel" onPress={() => setTransactionModalVisible(false)} variant="ghost" style={styles.modalButton} />
          <PrimaryButton title="Save" onPress={submitTransaction} loading={savingTransaction} style={styles.modalButton} />
        </View>
      </FormModal>

      <FormModal visible={budgetModalVisible} title="Add Budget" onClose={() => setBudgetModalVisible(false)}>
        <FormField label="Category">
          <OptionButton label={budgetForm.category} onPress={() => {}} />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
            {CATEGORY_OPTIONS.map((category) => {
              const active = category === budgetForm.category;
              return (
                <TouchableOpacity key={category} onPress={() => setBudgetForm((prev) => ({ ...prev, category }))} style={[styles.choiceChip, active && styles.choiceChipActive]}>
                  <Text style={[styles.choiceChipText, active && styles.choiceChipTextActive]}>{category}</Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </FormField>
        <View style={styles.rowInputs}>
          <View style={{ flex: 1, marginRight: 8 }}>
            <FormField label="Monthly Limit">
              <TextInput value={budgetForm.monthly_limit} onChangeText={(value) => setBudgetForm((prev) => ({ ...prev, monthly_limit: value }))} placeholder="10000" placeholderTextColor={Colors.textMuted} style={styles.input} keyboardType="numeric" />
            </FormField>
          </View>
          <View style={{ flex: 1 }}>
            <FormField label="Alert %">
              <TextInput value={budgetForm.alert_threshold} onChangeText={(value) => setBudgetForm((prev) => ({ ...prev, alert_threshold: value }))} placeholder="80" placeholderTextColor={Colors.textMuted} style={styles.input} keyboardType="numeric" />
            </FormField>
          </View>
        </View>
        <View style={styles.modalActions}>
          <PrimaryButton title="Cancel" onPress={() => setBudgetModalVisible(false)} variant="ghost" style={styles.modalButton} />
          <PrimaryButton title="Save Budget" onPress={submitBudget} loading={savingBudget} style={styles.modalButton} />
        </View>
      </FormModal>
    </View>
  );
}

function FormModal({ visible, title, onClose, children }: { visible: boolean; title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.modalBackdrop}>
        <View style={styles.modalCard}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>{title}</Text>
            <TouchableOpacity onPress={onClose}>
              <Ionicons name="close-outline" size={22} color={Colors.textPrimary} />
            </TouchableOpacity>
          </View>
          {children}
        </View>
      </View>
    </Modal>
  );
}

function OptionListModal({
  visible,
  title,
  options,
  selectedValue,
  onClose,
  onSelect,
}: {
  visible: boolean;
  title: string;
  options: Array<{ label: string; value: string }>;
  selectedValue: string;
  onClose: () => void;
  onSelect: (value: string) => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.modalBackdrop}>
        <View style={styles.modalCard}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>{title}</Text>
            <TouchableOpacity onPress={onClose}>
              <Ionicons name="close-outline" size={22} color={Colors.textPrimary} />
            </TouchableOpacity>
          </View>
          <ScrollView style={{ maxHeight: 320 }}>
            {options.map((option) => {
              const active = option.value === selectedValue;
              return (
                <TouchableOpacity key={option.value} style={[styles.optionRow, active && styles.optionRowActive]} onPress={() => onSelect(option.value)}>
                  <Text style={[styles.optionRowText, active && styles.optionRowTextActive]}>{option.label}</Text>
                  {active ? <Ionicons name="checkmark-outline" size={18} color={Colors.accentLight} /> : null}
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

function OptionButton({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <TouchableOpacity onPress={onPress} activeOpacity={1} style={styles.selectButtonStatic}>
      <Text style={styles.selectButtonText}>{label}</Text>
    </TouchableOpacity>
  );
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={{ marginBottom: 12 }}>
      <Text style={styles.fieldLabel}>{label}</Text>
      {children}
    </View>
  );
}

function SegmentedControl({ values, selected, onChange }: { values: string[]; selected: string; onChange: (value: string) => void }) {
  return (
    <View style={styles.segmentWrap}>
      {values.map((value) => {
        const active = value === selected;
        return (
          <TouchableOpacity key={value} onPress={() => onChange(value)} style={[styles.segmentButton, active && styles.segmentButtonActive]}>
            <Text style={[styles.segmentText, active && styles.segmentTextActive]}>{value}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

function SpendBarChart({ income, spend }: { income: number; spend: number }) {
  const max = Math.max(income, spend, 1);
  const barWidth = 70;
  const chartHeight = 130;
  const incomeHeight = (income / max) * chartHeight;
  const spendHeight = (spend / max) * chartHeight;
  return (
    <View style={styles.barChartWrap}>
      <Svg width="100%" height={170} viewBox="0 0 220 170">
        <Line x1="20" y1="140" x2="210" y2="140" stroke={Colors.borderStrong} strokeWidth="1" />
        <Rect x="35" y={140 - incomeHeight} width={barWidth} height={incomeHeight} rx="10" fill={Colors.green} />
        <Rect x="125" y={140 - spendHeight} width={barWidth} height={spendHeight} rx="10" fill={Colors.accent} />
      </Svg>
      <View style={styles.barLegendRow}>
        <View style={styles.barLegendItem}><View style={[styles.legendDot, { backgroundColor: Colors.green }]} /><Text style={styles.barLegendText}>Income {money(income)}</Text></View>
        <View style={styles.barLegendItem}><View style={[styles.legendDot, { backgroundColor: Colors.accent }]} /><Text style={styles.barLegendText}>Spend {money(spend)}</Text></View>
      </View>
    </View>
  );
}

function TrendLineChart({ months, trends }: { months: string[]; trends: TrendSeries[] }) {
  const width = 320;
  const height = 180;
  const leftPad = 20;
  const rightPad = 10;
  const topPad = 20;
  const bottomPad = 30;
  const allValues = trends.flatMap((trend) => trend.months.map((point) => point.total));
  const max = Math.max(...allValues, 1);
  const innerWidth = width - leftPad - rightPad;
  const innerHeight = height - topPad - bottomPad;

  const makeSmoothPath = (points: TrendMonthPoint[]) => {
    const mapped = points.map((point, index) => ({
      x: leftPad + (index / Math.max(months.length - 1, 1)) * innerWidth,
      y: topPad + innerHeight - ((point.total || 0) / max) * innerHeight,
    }));
    if (mapped.length <= 1) {
      return mapped.length ? `M ${mapped[0].x} ${mapped[0].y}` : '';
    }
    let path = `M ${mapped[0].x} ${mapped[0].y}`;
    for (let index = 0; index < mapped.length - 1; index += 1) {
      const current = mapped[index];
      const next = mapped[index + 1];
      const controlX = (current.x + next.x) / 2;
      path += ` C ${controlX} ${current.y}, ${controlX} ${next.y}, ${next.x} ${next.y}`;
    }
    return path;
  };

  return (
    <View>
      <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
        <Line x1={leftPad} y1={height - bottomPad} x2={width - rightPad} y2={height - bottomPad} stroke={Colors.borderStrong} strokeWidth="1" />
        <Line x1={leftPad} y1={topPad} x2={leftPad} y2={height - bottomPad} stroke={Colors.borderStrong} strokeWidth="1" />
        {trends.slice(0, 5).map((trend, idx) => (
          <Path key={trend.category} d={makeSmoothPath(trend.months)} stroke={CHART_COLORS[idx % CHART_COLORS.length]} strokeWidth="2.4" fill="none" />
        ))}
      </Svg>
      <View style={styles.chartMonthRow}>
        {months.map((month) => (
          <Text key={month} style={styles.chartMonthLabel}>{month.slice(5)}</Text>
        ))}
      </View>
    </View>
  );
}

function MiniTrendSparkline({ data, color }: { data: TrendMonthPoint[]; color: string }) {
  const width = 220;
  const height = 40;
  const max = Math.max(...data.map((point) => point.total), 1);
  const mapped = data.map((point, index) => ({
    x: (index / Math.max(data.length - 1, 1)) * width,
    y: height - ((point.total || 0) / max) * (height - 4) - 2,
  }));
  let path = mapped.length ? `M ${mapped[0].x} ${mapped[0].y}` : '';
  for (let index = 0; index < mapped.length - 1; index += 1) {
    const current = mapped[index];
    const next = mapped[index + 1];
    const controlX = (current.x + next.x) / 2;
    path += ` C ${controlX} ${current.y}, ${controlX} ${next.y}, ${next.x} ${next.y}`;
  }
  return (
    <Svg width="100%" height={48} viewBox={`0 0 ${width} ${height}`} style={{ marginTop: 8 }}>
      <Path d={path} stroke={color} strokeWidth="2" fill="none" />
    </Svg>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safeArea: { flex: 1 },
  scroll: { padding: Spacing.lg, flexGrow: 1 },
  headerActions: { flexDirection: 'row', marginTop: 12 },
  headerButton: { marginRight: 8 },
  filterCard: { marginBottom: 8 },
  filterLabel: { fontSize: 12, color: Colors.textMuted, marginBottom: 6 },
  pickerWrap: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass,
    overflow: 'hidden',
  },
  selectButton: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: 'rgba(8,12,20,0.92)',
    paddingHorizontal: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  selectButtonStatic: {
    minHeight: 44,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: 'rgba(8,12,20,0.92)',
    paddingHorizontal: 14,
    justifyContent: 'center',
    marginBottom: 10,
  },
  selectButtonText: { color: Colors.textPrimary, fontSize: 14, fontWeight: '600' },
  statsRow: { flexDirection: 'row', marginBottom: 8 },
  sectionCard: { marginTop: 8 },
  sectionHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  sectionTitle: { color: Colors.textPrimary, fontSize: 16, fontWeight: '700' },
  emptyHint: { color: Colors.textMuted, fontSize: 13, paddingVertical: 6 },
  itemRow: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: Colors.border },
  itemHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  itemTitle: { color: Colors.textPrimary, fontSize: 13, fontWeight: '600', flexShrink: 1 },
  itemSub: { color: Colors.textMuted, fontSize: 12, marginTop: 2 },
  itemValue: { color: Colors.textSecondary, fontSize: 12, fontWeight: '700' },
  trendCard: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: Colors.border },
  trendTitleWrap: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  trendDot: { width: 10, height: 10, borderRadius: 5, marginRight: 8 },
  budgetFooter: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 6 },
  budgetPct: { fontSize: 12, fontWeight: '700' },
  budgetLimit: { fontSize: 12, color: Colors.textMuted },
  billRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  billRight: { alignItems: 'flex-end', marginLeft: 10 },
  billMeta: { fontSize: 11, marginTop: 2 },
  txRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    gap: 8,
  },
  txRight: { alignItems: 'flex-end', marginLeft: 10 },
  deleteButton: { marginTop: 6, padding: 4 },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    marginTop: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: Radius.full,
    borderWidth: 1,
    borderColor: Colors.borderAccent,
    backgroundColor: Colors.accentGlow,
  },
  categoryChipText: { fontSize: 11, color: Colors.accent, fontWeight: '600' },
  barChartWrap: { paddingTop: 4 },
  barLegendRow: { flexDirection: 'row', justifyContent: 'space-around', marginTop: -6 },
  barLegendItem: { flexDirection: 'row', alignItems: 'center' },
  barLegendText: { color: Colors.textSecondary, fontSize: 12 },
  legendDot: { width: 8, height: 8, borderRadius: 4, marginRight: 6 },
  chartMonthRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: -8, paddingHorizontal: 8 },
  chartMonthLabel: { color: Colors.textMuted, fontSize: 11, width: 28, textAlign: 'center' },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.82)', justifyContent: 'center', padding: Spacing.lg },
  modalCard: {
    padding: Spacing.lg,
    backgroundColor: '#0B1220',
    borderRadius: Radius.xl,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
    shadowColor: '#000',
    shadowOpacity: 0.35,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 14 },
    elevation: 14,
  },
  optionRow: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    borderRadius: Radius.md,
    backgroundColor: 'rgba(255,255,255,0.02)',
    marginBottom: 8,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.05)',
  },
  optionRowActive: {
    backgroundColor: Colors.accentGlow,
    borderColor: Colors.borderAccent,
  },
  optionRowText: { color: Colors.textPrimary, fontSize: 14, fontWeight: '600' },
  optionRowTextActive: { color: Colors.textPrimary },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  modalTitle: { color: Colors.textPrimary, fontSize: 18, fontWeight: '700' },
  fieldLabel: { color: Colors.textMuted, fontSize: 12, marginBottom: 6 },
  input: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass,
    color: Colors.textPrimary,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  rowInputs: { flexDirection: 'row' },
  modalActions: { flexDirection: 'row', marginTop: 4 },
  modalButton: { flex: 1, marginRight: 8 },
  chipRow: { paddingVertical: 2, paddingRight: 10 },
  choiceChip: {
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: Radius.full,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: 'rgba(255,255,255,0.03)',
    marginRight: 8,
  },
  choiceChipActive: {
    backgroundColor: Colors.accentGlow,
    borderColor: Colors.borderAccent,
  },
  choiceChipText: { color: Colors.textSecondary, fontSize: 12, fontWeight: '600' },
  choiceChipTextActive: { color: Colors.textPrimary },
  segmentWrap: {
    flexDirection: 'row',
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    overflow: 'hidden',
    backgroundColor: Colors.bgGlass,
  },
  segmentButton: { flex: 1, paddingVertical: 11, alignItems: 'center' },
  segmentButtonActive: { backgroundColor: Colors.accentGlow },
  segmentText: { color: Colors.textSecondary, fontSize: 12, fontWeight: '600' },
  segmentTextActive: { color: Colors.textPrimary },
});
