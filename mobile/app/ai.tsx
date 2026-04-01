import React, { useMemo, useState } from 'react';
import { KeyboardAvoidingView, Platform, RefreshControl, ScrollView, StatusBar, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';
import { aiAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { GlassCard, ScreenHeader, Tag } from '../components/ui';

interface ActionResult {
  tool: string;
  args: Record<string, unknown>;
  result: { success: boolean; action?: string; error?: string; [key: string]: unknown };
}

const ACTION_LABELS: Record<string, string> = {
  create_budget: '💰 Budget Created',
  update_budget: '💰 Budget Updated',
  delete_budget: '🗑️ Budget Deleted',
  create_savings_goal: '🎯 Savings Goal Created',
  update_savings_goal_progress: '🎯 Savings Goal Updated',
  create_bill_reminder: '🔔 Bill Reminder Added',
  mark_bill_paid: '✅ Bill Marked Paid',
  add_transaction: '📝 Transaction Added',
  run_scanner: '🔍 Scanner Ran',
  close_position: '📉 Position Closed',
};

function ActionBadge({ action }: { action: ActionResult }) {
  const ok = action.result.success;
  const label = ACTION_LABELS[action.tool] ?? action.tool.replace(/_/g, ' ');
  const detail = ok
    ? Object.entries(action.result)
        .filter(([k]) => !['success', 'action', 'id'].includes(k))
        .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
        .join(' · ')
    : action.result.error;

  return (
    <View style={[styles.actionCard, ok ? styles.actionCardOk : styles.actionCardErr]}>
      <Text style={[styles.actionLabel, ok ? styles.actionLabelOk : styles.actionLabelErr]}>{label}</Text>
      {!!detail && <Text style={[styles.actionDetail, ok ? styles.actionDetailOk : styles.actionDetailErr]}>{detail}</Text>}
    </View>
  );
}

const STARTERS = [
  'Show my open positions',
  'Add Food budget ₹3000',
  'What scanner signals fired this week?',
  'Summarize my trading performance',
];

export default function AIScreen() {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [history, setHistory] = useState<Array<{ role: 'user' | 'assistant'; content: string; actions?: ActionResult[] }>>([
    {
      role: 'assistant',
      content: 'FastTrade AI is ready.\nI can answer questions AND take actions — add budgets, record expenses, run scanners, close positions, and more.\nTry: "Add a Food budget of ₹3000" or "Run my RSI scanner".',
    },
  ]);

  const canSend = useMemo(() => message.trim().length > 0 && !loading, [message, loading]);

  const send = async (text?: string) => {
    const outgoing = (text ?? message).trim();
    if (!outgoing) {
      return;
    }

    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    const nextHistory = [...history, { role: 'user' as const, content: outgoing }];
    setHistory(nextHistory);
    setMessage('');
    setLoading(true);

    try {
      const res = await aiAPI.query(outgoing, nextHistory);
      const reply = res.data?.answer || res.data?.response || res.data?.message || 'No response from backend.';
      const actions: ActionResult[] = res.data?.actions?.length ? res.data.actions : [];
      setHistory((prev) => [...prev, { role: 'assistant', content: reply, actions }]);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.response?.data?.error || error?.message;
      setHistory((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: detail
            ? `AI assistant error: ${String(detail)}`
            : 'The backend assistant is not reachable right now.',
        },
      ]);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }

    setLoading(false);
  };

  const resetConversation = async () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setHistory([
      {
        role: 'assistant',
        content: 'Fresh chat started. Ask anything or give a command.',
      },
    ]);
    setMessage('');
    setRefreshing(false);
  };

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safeArea}>
        <ScreenHeader
          title="AI Desk"
          subtitle="Natural-language queries and actions"
          badge={<Tag label="AGENTIC" color={Colors.accent} bg={Colors.accentSoft} />}
        />

        <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView
            contentContainerStyle={styles.scroll}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={resetConversation} tintColor={Colors.accent} />}
          >
            <View style={styles.starterRow}>
              {STARTERS.map((starter) => (
                <TouchableOpacity key={starter} style={[styles.starterChip, loading && styles.starterChipDisabled]} onPress={() => send(starter)} disabled={loading}>
                  <Text style={styles.starterText}>{starter}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {history.map((item, index) => {
              const assistant = item.role === 'assistant';
              return (
                <View key={`${item.role}-${index}`} style={[styles.messageRow, assistant ? styles.messageRowLeft : styles.messageRowRight]}>
                  <View style={styles.bubbleWrap}>
                    <GlassCard style={[styles.bubble, assistant ? styles.assistantBubble : styles.userBubble]}>
                      <View style={styles.bubbleTop}>
                        <Tag label={assistant ? 'AI' : 'YOU'} color={assistant ? Colors.accent : Colors.green} bg={assistant ? Colors.accentGlow : Colors.greenBg} />
                      </View>
                      <Text style={styles.bubbleText}>{item.content}</Text>
                    </GlassCard>
                    {item.actions && item.actions.length > 0 && (
                      <View style={styles.actionsWrap}>
                        {item.actions.map((a, ai) => <ActionBadge key={ai} action={a} />)}
                      </View>
                    )}
                  </View>
                </View>
              );
            })}

            {loading && (
              <View style={styles.messageRowLeft}>
                <GlassCard style={[styles.bubble, styles.assistantBubble]}>
                  <Text style={styles.loadingText}>Thinking...</Text>
                </GlassCard>
              </View>
            )}
            <View style={{ height: 24 }} />
          </ScrollView>

          <View style={styles.composerWrap}>
            <View style={styles.composer}>
              <TextInput
                value={message}
                onChangeText={setMessage}
                placeholder="Ask a question or give a command..."
                placeholderTextColor={Colors.textMuted}
                style={styles.input}
                multiline
              />
              <TouchableOpacity style={[styles.sendButton, !canSend && styles.sendButtonDisabled]} disabled={!canSend} onPress={() => send()}>
                <LinearGradient colors={canSend ? ['#1D4ED8', '#3B82F6'] : ['#334155', '#334155']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.sendGradient}>
                  <Text style={styles.sendText}>Send</Text>
                </LinearGradient>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safeArea: { flex: 1 },
  flex: { flex: 1 },
  header: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.lg },
  headerTitle: { fontSize: 28, fontWeight: '700', color: Colors.textPrimary, letterSpacing: -0.5 },
  headerSub: { fontSize: 13, color: Colors.textMuted, marginTop: 2 },
  scroll: { padding: Spacing.lg, flexGrow: 1 },
  starterRow: { flexDirection: 'row', flexWrap: 'wrap', marginBottom: Spacing.md },
  starterChip: {
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.bgGlass,
    borderRadius: Radius.full,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginRight: 8,
    marginBottom: 8,
  },
  starterChipDisabled: { opacity: 0.55 },
  starterText: { color: Colors.textSecondary, fontSize: 12, fontWeight: '600' },
  messageRow: { marginBottom: 12, flexDirection: 'row' },
  messageRowLeft: { justifyContent: 'flex-start' },
  messageRowRight: { justifyContent: 'flex-end' },
  bubbleWrap: { maxWidth: '86%' },
  bubble: {},
  assistantBubble: { backgroundColor: Colors.bgGlassStrong },
  userBubble: { backgroundColor: Colors.accentGlow, borderColor: Colors.borderAccent },
  bubbleTop: { marginBottom: 8 },
  bubbleText: { color: Colors.textPrimary, fontSize: 14, lineHeight: 20 },
  loadingText: { color: Colors.textSecondary, fontSize: 14, fontStyle: 'italic' },
  actionsWrap: { marginTop: 6 },
  actionCard: {
    borderRadius: Radius.md,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 7,
    marginTop: 4,
  },
  actionCardOk: { backgroundColor: '#052e16', borderColor: '#166534' },
  actionCardErr: { backgroundColor: '#450a0a', borderColor: '#991b1b' },
  actionLabel: { fontSize: 12, fontWeight: '700' },
  actionLabelOk: { color: '#86efac' },
  actionLabelErr: { color: '#fca5a5' },
  actionDetail: { fontSize: 11, marginTop: 2 },
  actionDetailOk: { color: '#4ade80' },
  actionDetailErr: { color: '#f87171' },
  composerWrap: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.lg, paddingTop: 8 },
  composer: {
    backgroundColor: Colors.bgGlass,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.xl,
    padding: 10,
  },
  input: { color: Colors.textPrimary, minHeight: 44, maxHeight: 120, paddingHorizontal: 4, paddingTop: 8 },
  sendButton: { marginTop: 10, borderRadius: Radius.md, overflow: 'hidden', alignSelf: 'flex-end' },
  sendButtonDisabled: { opacity: 0.55 },
  sendGradient: { paddingHorizontal: 16, paddingVertical: 10 },
  sendText: { color: '#fff', fontWeight: '700' },
});