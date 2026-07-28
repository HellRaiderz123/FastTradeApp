import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
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
import * as Haptics from 'expo-haptics';
import { aiAgentsAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { GlassCard, ScreenHeader, Tag } from '../components/ui';

// ─── Types ──────────────────────────────────────────────────────────────────

type JobStatus = 'IDLE' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';

interface AgentStep {
  key: string;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
}

interface Decision {
  action: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  conviction: string;
  rationale: string;
  key_factors: string[];
  time_horizon: string;
  risk_level: string;
  suggested_stop_loss_pct: number | null;
  suggested_target_pct: number | null;
}

interface HistoryEntry {
  id: number;
  action: string;
  confidence: number;
  conviction: string;
  rationale: string;
  outcome_correct: number | null;
  actual_return_pct: number | null;
  reflection: string | null;
  analysed_at: string;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const PIPELINE_STEPS: AgentStep[] = [
  { key: 'data_collection',  label: 'Collecting Data',        icon: 'cloud-download-outline' },
  { key: 'technical_analyst', label: 'Technical Analyst',      icon: 'bar-chart-outline' },
  { key: 'news_analyst',     label: 'News Analyst',            icon: 'newspaper-outline' },
  { key: 'sentiment_analyst', label: 'Sentiment Analyst',      icon: 'pulse-outline' },
  { key: 'bull_researcher',  label: 'Bull Researcher',         icon: 'trending-up-outline' },
  { key: 'bear_researcher',  label: 'Bear Researcher',         icon: 'trending-down-outline' },
  { key: 'fundamentals_analyst', label: 'Fundamentals Analyst', icon: 'calculator-outline' },
  { key: 'trader_decision',  label: 'Trader Decision',         icon: 'flash-outline' },
];

const POPULAR_SYMBOLS = ['NIFTY', 'BANKNIFTY', 'RELIANCE', 'TCS', 'SBIN', 'INFY', 'HDFC', 'ICICIBANK'];

const POLL_INTERVAL_MS = 3000;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function actionColor(action: string) {
  if (action === 'BUY')  return Colors.green;
  if (action === 'SELL') return Colors.red;
  return Colors.amber;
}

function actionBg(action: string) {
  if (action === 'BUY')  return Colors.greenBg;
  if (action === 'SELL') return Colors.redBg;
  return Colors.amberBg;
}

function confidenceLabel(c: number) {
  if (c >= 0.75) return 'HIGH';
  if (c >= 0.5)  return 'MEDIUM';
  return 'LOW';
}

function stepStatusIcon(key: string, stepsDone: string[], currentStep: string | null) {
  if (stepsDone.includes(key)) return { icon: 'checkmark-circle' as const, color: Colors.green };
  if (currentStep === key)     return { icon: 'radio-button-on' as const, color: Colors.accent };
  return { icon: 'ellipse-outline' as const, color: Colors.textMuted };
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch { return iso; }
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function PipelineProgress({ stepsDone, currentStep, status }: {
  stepsDone: string[];
  currentStep: string | null;
  status: JobStatus;
}) {
  return (
    <GlassCard style={styles.progressCard}>
      <Text style={styles.sectionTitle}>Agent Pipeline</Text>
      {PIPELINE_STEPS.map((step) => {
        const { icon, color } = stepStatusIcon(step.key, stepsDone, currentStep);
        const isActive = currentStep === step.key;
        return (
          <View key={step.key} style={styles.stepRow}>
            <View style={styles.stepIconWrap}>
              <Ionicons name={step.icon} size={16} color={color} />
            </View>
            <Text style={[styles.stepLabel, isActive && { color: Colors.accent, fontWeight: '600' }]}>
              {step.label}
            </Text>
            <Ionicons name={icon} size={16} color={color} />
            {isActive && (
              <ActivityIndicator size="small" color={Colors.accent} style={{ marginLeft: 4 }} />
            )}
          </View>
        );
      })}
      {status === 'FAILED' && (
        <Text style={styles.errorText}>Pipeline failed. Check LLM configuration.</Text>
      )}
    </GlassCard>
  );
}

function DecisionCard({ decision, dataSummary }: { decision: Decision; dataSummary: any }) {
  const color = actionColor(decision.action);
  const bg    = actionBg(decision.action);
  const conf  = Math.round((decision.confidence || 0) * 100);

  return (
    <GlassCard style={styles.decisionCard}>
      {/* Action badge */}
      <View style={[styles.actionBadge, { backgroundColor: bg, borderColor: color + '60' }]}>
        <Text style={[styles.actionText, { color }]}>{decision.action}</Text>
      </View>

      {/* Confidence bar */}
      <View style={styles.confRow}>
        <Text style={styles.confLabel}>Confidence</Text>
        <Text style={[styles.confPct, { color }]}>{conf}%</Text>
      </View>
      <View style={styles.confBarBg}>
        <View style={[styles.confBarFill, { width: `${conf}%` as any, backgroundColor: color }]} />
      </View>

      {/* Tags */}
      <View style={styles.tagRow}>
        <Tag label={decision.conviction ?? '–'} />
        <Tag label={decision.time_horizon ?? '–'} />
        <Tag label={`Risk: ${decision.risk_level ?? '–'}`} />
      </View>

      {/* Levels */}
      {(decision.suggested_stop_loss_pct != null || decision.suggested_target_pct != null) && (
        <View style={styles.levelsRow}>
          {decision.suggested_stop_loss_pct != null && (
            <View style={styles.levelBox}>
              <Text style={styles.levelLabel}>Stop Loss</Text>
              <Text style={[styles.levelValue, { color: Colors.red }]}>
                -{decision.suggested_stop_loss_pct}%
              </Text>
            </View>
          )}
          {decision.suggested_target_pct != null && (
            <View style={styles.levelBox}>
              <Text style={styles.levelLabel}>Target</Text>
              <Text style={[styles.levelValue, { color: Colors.green }]}>
                +{decision.suggested_target_pct}%
              </Text>
            </View>
          )}
        </View>
      )}

      {/* Rationale */}
      <Text style={styles.rationale}>{decision.rationale}</Text>

      {/* Key factors */}
      {decision.key_factors?.length > 0 && (
        <View style={styles.factorsWrap}>
          <Text style={styles.factorsTitle}>Key Factors</Text>
          {decision.key_factors.map((f, i) => (
            <View key={i} style={styles.factorRow}>
              <Ionicons name="chevron-forward" size={12} color={Colors.accent} />
              <Text style={styles.factorText}>{f}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Data summary */}
      {dataSummary && (
        <Text style={styles.dataSummaryText}>
          {dataSummary.candles_used} candles ({dataSummary.candle_timeframe}) ·{' '}
          {dataSummary.news_items_used} news · VIX {dataSummary.vix?.toFixed(1) ?? '–'} ·{' '}
          {dataSummary.history_decisions_used ?? 0} past decisions used
        </Text>
      )}

      <Text style={styles.disclaimer}>
        Research simulation only. Not financial advice.
      </Text>
    </GlassCard>
  );
}

function HistoryCard({ entry }: { entry: HistoryEntry }) {
  const color = actionColor(entry.action);
  const hasOutcome = entry.outcome_correct !== null;
  const outcomeColor = entry.outcome_correct === 1 ? Colors.green : Colors.red;

  return (
    <GlassCard style={styles.historyCard}>
      <View style={styles.historyHeader}>
        <View style={[styles.historyBadge, { backgroundColor: actionBg(entry.action) }]}>
          <Text style={[styles.historyAction, { color }]}>{entry.action}</Text>
        </View>
        <Text style={styles.historyDate}>{formatDate(entry.analysed_at)}</Text>
        {hasOutcome && (
          <View style={[styles.outcomeBadge, { backgroundColor: entry.outcome_correct === 1 ? Colors.greenBg : Colors.redBg }]}>
            <Text style={[styles.outcomeText, { color: outcomeColor }]}>
              {entry.outcome_correct === 1 ? '✓ Correct' : '✗ Wrong'}
            </Text>
            {entry.actual_return_pct != null && (
              <Text style={[styles.returnText, { color: outcomeColor }]}>
                {entry.actual_return_pct > 0 ? '+' : ''}{entry.actual_return_pct.toFixed(1)}%
              </Text>
            )}
          </View>
        )}
      </View>
      <Text style={styles.historyRationale} numberOfLines={2}>{entry.rationale}</Text>
      {entry.reflection && (
        <Text style={styles.reflectionText}>💡 {entry.reflection}</Text>
      )}
    </GlassCard>
  );
}

// ─── Main Screen ─────────────────────────────────────────────────────────────

export default function AIAgentsScreen() {
  const [symbol, setSymbol]         = useState('NIFTY');
  const [exchange]                  = useState('NSE');
  const [jobId, setJobId]           = useState<string | null>(null);
  const [status, setStatus]         = useState<JobStatus>('IDLE');
  const [stepsDone, setStepsDone]   = useState<string[]>([]);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [decision, setDecision]     = useState<Decision | null>(null);
  const [dataSummary, setDataSummary] = useState<any>(null);
  const [history, setHistory]       = useState<HistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [serviceReady, setServiceReady]     = useState<boolean | null>(null);
  const [showReports, setShowReports]       = useState(false);
  const [reports, setReports]               = useState<any>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Check service health on mount ──────────────────────────────────
  useEffect(() => {
    aiAgentsAPI.health()
      .then((r) => setServiceReady(r.data?.ok === true))
      .catch(() => setServiceReady(false));
  }, []);

  // ── Load history when symbol changes ───────────────────────────────
  const loadHistory = useCallback(async (sym: string) => {
    setHistoryLoading(true);
    try {
      const r = await aiAgentsAPI.history(sym, 8);
      setHistory(r.data?.decisions ?? []);
    } catch {
      setHistory([]);
    }
    setHistoryLoading(false);
  }, []);

  useEffect(() => {
    if (symbol.length >= 2) loadHistory(symbol);
  }, [symbol, loadHistory]);

  // ── Polling ────────────────────────────────────────────────────────
  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const pollStatus = useCallback(async (id: string) => {
    try {
      const r = await aiAgentsAPI.status(id);
      const job = r.data;
      setStepsDone(job.steps_done ?? []);
      setCurrentStep(job.current_step ?? null);
      setStatus(job.status as JobStatus);

      if (job.status === 'COMPLETED') {
        stopPolling();
        setDecision(job.result?.decision ?? null);
        setDataSummary(job.result?.data_summary ?? null);
        setReports(job.result?.reports ?? null);
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        loadHistory(symbol);
      } else if (job.status === 'FAILED') {
        stopPolling();
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      }
    } catch (err) {
      // network glitch — keep polling
    }
  }, [symbol, stopPolling, loadHistory]);

  useEffect(() => {
    if (jobId && (status === 'QUEUED' || status === 'RUNNING')) {
      pollRef.current = setInterval(() => pollStatus(jobId), POLL_INTERVAL_MS);
      return stopPolling;
    }
  }, [jobId, status, pollStatus, stopPolling]);

  // ── Start analysis ─────────────────────────────────────────────────
  const handleAnalyze = useCallback(async () => {
    const sym = symbol.trim().toUpperCase();
    if (!sym) { Alert.alert('Enter a symbol', 'e.g. RELIANCE, NIFTY'); return; }

    stopPolling();
    setJobId(null);
    setStatus('QUEUED');
    setStepsDone([]);
    setCurrentStep(null);
    setDecision(null);
    setDataSummary(null);
    setReports(null);
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    try {
      const r = await aiAgentsAPI.analyze(sym, exchange);
      const id = r.data?.job_id;
      if (!id) throw new Error('No job_id returned');
      setJobId(id);
      setStatus('RUNNING');
    } catch (err: any) {
      setStatus('FAILED');
      Alert.alert(
        'Analysis Failed',
        err?.response?.data?.detail ?? err?.message ?? 'Could not start analysis. Check LLM config.',
      );
    }
  }, [symbol, exchange, stopPolling]);

  const isRunning = status === 'QUEUED' || status === 'RUNNING';

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <StatusBar barStyle="light-content" />
      <ScreenHeader title="AI Agents" subtitle="Multi-agent market analysis" />

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {/* Service status banner */}
        {serviceReady === false && (
          <View style={styles.warningBanner}>
            <Ionicons name="warning-outline" size={14} color={Colors.amber} />
            <Text style={styles.warningText}>
              LLM service not configured. Set LLM_API_KEY in backend .env
            </Text>
          </View>
        )}

        {/* Symbol input */}
        <GlassCard style={styles.inputCard}>
          <Text style={styles.inputLabel}>NSE / BSE Symbol</Text>
          <View style={styles.inputRow}>
            <TextInput
              style={styles.symbolInput}
              value={symbol}
              onChangeText={(t) => setSymbol(t.toUpperCase())}
              placeholder="e.g. RELIANCE"
              placeholderTextColor={Colors.textMuted}
              autoCapitalize="characters"
              autoCorrect={false}
              editable={!isRunning}
            />
            <TouchableOpacity
              style={[styles.analyzeBtn, isRunning && styles.analyzeBtnDisabled]}
              onPress={handleAnalyze}
              disabled={isRunning}
            >
              {isRunning
                ? <ActivityIndicator size="small" color="#fff" />
                : <Text style={styles.analyzeBtnText}>Analyse</Text>
              }
            </TouchableOpacity>
          </View>

          {/* Quick-pick chips */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipsRow}>
            {POPULAR_SYMBOLS.map((s) => (
              <TouchableOpacity
                key={s}
                style={[styles.chip, symbol === s && styles.chipActive]}
                onPress={() => { setSymbol(s); }}
                disabled={isRunning}
              >
                <Text style={[styles.chipText, symbol === s && styles.chipTextActive]}>{s}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </GlassCard>

        {/* Pipeline progress */}
        {status !== 'IDLE' && (
          <PipelineProgress
            stepsDone={stepsDone}
            currentStep={currentStep}
            status={status}
          />
        )}

        {/* Decision result */}
        {decision && (
          <DecisionCard decision={decision} dataSummary={dataSummary} />
        )}

        {/* Expandable raw reports */}
        {reports && (
          <GlassCard style={styles.reportsCard}>
            <TouchableOpacity
              style={styles.reportsToggle}
              onPress={() => setShowReports((v) => !v)}
            >
              <Text style={styles.sectionTitle}>Agent Reports</Text>
              <Ionicons
                name={showReports ? 'chevron-up' : 'chevron-down'}
                size={16}
                color={Colors.textSecondary}
              />
            </TouchableOpacity>
            {showReports && (
              <View>
                {Object.entries(reports).map(([key, report]: [string, any]) => (
                  <View key={key} style={styles.reportSection}>
                    <Text style={styles.reportTitle}>
                      {key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    </Text>
                    {report?.summary && (
                      <Text style={styles.reportSummary}>{report.summary}</Text>
                    )}
                    {report?.bull_thesis && (
                      <Text style={styles.reportSummary}>{report.bull_thesis}</Text>
                    )}
                    {report?.bear_thesis && (
                      <Text style={styles.reportSummary}>{report.bear_thesis}</Text>
                    )}
                  </View>
                ))}
              </View>
            )}
          </GlassCard>
        )}

        {/* Evaluate outcomes */}
        {history.length > 0 && (
          <TouchableOpacity
            style={styles.evaluateBtn}
            onPress={async () => {
              try {
                await aiAgentsAPI.evaluateOutcomes(symbol);
                await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
                loadHistory(symbol);
              } catch {
                Alert.alert('Error', 'Could not evaluate outcomes. Try again.');
              }
            }}
          >
            <Ionicons name="checkmark-done-outline" size={14} color={Colors.accent} />
            <Text style={styles.evaluateBtnText}>Evaluate Outcomes</Text>
          </TouchableOpacity>
        )}

        {/* Decision history */}
        <View style={styles.historySectionHeader}>
          <Text style={styles.sectionTitle}>Decision History — {symbol}</Text>
          {historyLoading && <ActivityIndicator size="small" color={Colors.accent} />}
        </View>

        {history.length === 0 && !historyLoading && (
          <Text style={styles.emptyHistory}>No past decisions for {symbol}</Text>
        )}
        {history.map((entry) => (
          <HistoryCard key={entry.id} entry={entry} />
        ))}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  scroll: { flex: 1 },
  scrollContent: { padding: Spacing.md, gap: Spacing.sm },

  warningBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: Colors.amberBg, borderRadius: Radius.sm,
    padding: Spacing.sm, marginBottom: 4,
  },
  warningText: { color: Colors.amber, fontSize: 12, flex: 1 },

  // Input card
  inputCard: { gap: Spacing.sm },
  inputLabel: { color: Colors.textSecondary, fontSize: 12, fontWeight: '600', letterSpacing: 0.5 },
  inputRow: { flexDirection: 'row', gap: Spacing.sm, alignItems: 'center' },
  symbolInput: {
    flex: 1, height: 44,
    backgroundColor: Colors.bgElevated,
    borderRadius: Radius.sm,
    borderWidth: 1, borderColor: Colors.border,
    color: Colors.textPrimary,
    paddingHorizontal: Spacing.sm,
    fontSize: 16, fontWeight: '700', letterSpacing: 1,
  },
  analyzeBtn: {
    height: 44, paddingHorizontal: Spacing.md,
    backgroundColor: Colors.accent,
    borderRadius: Radius.sm,
    alignItems: 'center', justifyContent: 'center',
  },
  analyzeBtnDisabled: { opacity: 0.5 },
  analyzeBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  chipsRow: { marginTop: 4 },
  chip: {
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 20, marginRight: 8,
    backgroundColor: Colors.bgElevated,
    borderWidth: 1, borderColor: Colors.border,
  },
  chipActive: { backgroundColor: Colors.accentSoft, borderColor: Colors.accent },
  chipText: { color: Colors.textSecondary, fontSize: 12, fontWeight: '600' },
  chipTextActive: { color: Colors.accent },

  // Progress
  progressCard: { gap: 10 },
  sectionTitle: { color: Colors.textPrimary, fontSize: 14, fontWeight: '700', marginBottom: 4 },
  stepRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 2 },
  stepIconWrap: { width: 22, alignItems: 'center' },
  stepLabel: { flex: 1, color: Colors.textSecondary, fontSize: 13 },
  errorText: { color: Colors.red, fontSize: 12, marginTop: 4 },

  // Decision card
  decisionCard: { gap: Spacing.sm },
  actionBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 20, paddingVertical: 8,
    borderRadius: Radius.sm, borderWidth: 1,
    marginBottom: 4,
  },
  actionText: { fontSize: 22, fontWeight: '800', letterSpacing: 2 },
  confRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  confLabel: { color: Colors.textSecondary, fontSize: 12 },
  confPct: { fontSize: 14, fontWeight: '700' },
  confBarBg: {
    height: 6, backgroundColor: Colors.bgElevated,
    borderRadius: 3, overflow: 'hidden',
  },
  confBarFill: { height: 6, borderRadius: 3 },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 },
  levelsRow: { flexDirection: 'row', gap: Spacing.sm },
  levelBox: {
    flex: 1, backgroundColor: Colors.bgElevated,
    borderRadius: Radius.sm, padding: Spacing.sm, alignItems: 'center',
  },
  levelLabel: { color: Colors.textMuted, fontSize: 11 },
  levelValue: { fontSize: 15, fontWeight: '700', marginTop: 2 },
  rationale: { color: Colors.textSecondary, fontSize: 13, lineHeight: 19, marginTop: 4 },
  factorsWrap: { marginTop: 6, gap: 4 },
  factorsTitle: { color: Colors.textPrimary, fontSize: 12, fontWeight: '700', marginBottom: 2 },
  factorRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 4 },
  factorText: { flex: 1, color: Colors.textSecondary, fontSize: 12, lineHeight: 17 },
  dataSummaryText: { color: Colors.textMuted, fontSize: 11, marginTop: 6 },
  disclaimer: { color: Colors.textFaint, fontSize: 10, marginTop: 4, fontStyle: 'italic' },

  // Reports
  reportsCard: { gap: 0 },
  reportsToggle: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  reportSection: { marginTop: Spacing.sm, paddingTop: Spacing.sm, borderTopWidth: 1, borderTopColor: Colors.border },
  reportTitle: { color: Colors.textPrimary, fontSize: 12, fontWeight: '700', marginBottom: 3 },
  reportSummary: { color: Colors.textSecondary, fontSize: 12, lineHeight: 17 },

  evaluateBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    alignSelf: 'flex-end',
    paddingHorizontal: 12, paddingVertical: 7,
    borderRadius: Radius.sm,
    borderWidth: 1, borderColor: Colors.accentSoft,
    backgroundColor: Colors.bgElevated,
    marginBottom: 8,
  },
  evaluateBtnText: { color: Colors.accent, fontSize: 12, fontWeight: '600' },
  // History
  historySectionHeader: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginTop: Spacing.sm,
  },
  emptyHistory: { color: Colors.textMuted, fontSize: 13, textAlign: 'center', marginVertical: 12 },
  historyCard: { gap: 6 },
  historyHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  historyBadge: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: 6 },
  historyAction: { fontSize: 12, fontWeight: '800', letterSpacing: 1 },
  historyDate: { flex: 1, color: Colors.textMuted, fontSize: 11 },
  outcomeBadge: { flexDirection: 'row', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  outcomeText: { fontSize: 11, fontWeight: '700' },
  returnText: { fontSize: 11, fontWeight: '600' },
  historyRationale: { color: Colors.textSecondary, fontSize: 12, lineHeight: 17 },
  reflectionText: { color: Colors.textAccent, fontSize: 11, fontStyle: 'italic', lineHeight: 16 },
});
