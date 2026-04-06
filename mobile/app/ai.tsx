import React, { useEffect, useMemo, useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, RefreshControl, ScrollView, StatusBar, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';
import * as Speech from 'expo-speech';
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
  place_trade: '🛒 Trade Placed',
  trade_confirmation_required: '🛡️ Confirmation Required',
};

function ActionBadge({ action }: { action: ActionResult }) {
  const ok = action.result.success;
  const label = ACTION_LABELS[action.tool] ?? action.tool.replace(/_/g, ' ');
  const detail = ok
    ? Object.entries(action.result)
        .filter(([k]) => !['success', 'action', 'id', 'requires_confirmation', 'order_preview', 'message'].includes(k))
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

const getSpeechRecognitionCtor = () => {
  const g = globalThis as any;
  return g?.SpeechRecognition || g?.webkitSpeechRecognition || null;
};

const speakAssistantText = async (text: string) => {
  const cleaned = String(text || '').trim();
  if (!cleaned) return;

  if (Platform.OS === 'web') {
    const synth = (globalThis as any)?.speechSynthesis;
    const Utterance = (globalThis as any)?.SpeechSynthesisUtterance;
    if (!synth || !Utterance) return;
    synth.cancel();
    const utterance = new Utterance(cleaned);
    utterance.lang = 'en-IN';
    utterance.rate = 1.02;
    utterance.pitch = 0.95;
    synth.speak(utterance);
    return;
  }

  try {
    Speech.stop();
    Speech.speak(cleaned, { language: 'en-IN', rate: 0.98, pitch: 0.95 });
  } catch {
    // no-op
  }
};

const stopAssistantVoice = () => {
  if (Platform.OS === 'web') {
    const synth = (globalThis as any)?.speechSynthesis;
    synth?.cancel?.();
    return;
  }
  try {
    Speech.stop();
  } catch {
    // no-op
  }
};

const buildTradeConfirmationPrompt = (action: ActionResult) => {
  const preview = (action.result.order_preview as Record<string, unknown> | undefined) ?? {};
  const parts = [
    preview.trade_action,
    preview.quantity,
    preview.symbol,
    preview.order_type,
    preview.product,
  ].filter(Boolean);
  return `Confirm place trade now: ${parts.join(' ')}.`;
};

function TradeConfirmCard({
  action,
  onConfirm,
  onCancel,
  busy,
}: {
  action: ActionResult;
  onConfirm: (action: ActionResult) => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const requiresConfirmation = Boolean(action.result?.requires_confirmation);
  const preview = (action.result.order_preview as Record<string, unknown> | undefined) ?? {};
  if (!requiresConfirmation) return null;

  const summary = [preview.trade_action, preview.quantity, preview.symbol, preview.order_type, preview.product]
    .filter(Boolean)
    .join(' · ');

  return (
    <GlassCard style={styles.confirmCard}>
      <Text style={styles.confirmTitle}>Live trade confirmation required</Text>
      <Text style={styles.confirmText}>{summary || 'Review the order preview and confirm before execution.'}</Text>
      <View style={styles.confirmActions}>
        <TouchableOpacity style={[styles.confirmBtn, styles.confirmBtnPrimary, busy && styles.starterChipDisabled]} onPress={() => onConfirm(action)} disabled={busy}>
          <Text style={styles.confirmBtnText}>Confirm</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.confirmBtn, styles.confirmBtnSecondary, busy && styles.starterChipDisabled]} onPress={onCancel} disabled={busy}>
          <Text style={styles.confirmBtnText}>Cancel</Text>
        </TouchableOpacity>
      </View>
    </GlassCard>
  );
}

const STARTERS = [
  'Show my open positions',
  'Build my pre-market game plan',
  'Buy 1 share of TCS at market price as a dry run',
  'What scanner signals fired this week?',
  'Summarize my trading performance',
];

export default function AIScreen() {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [jarvisMode, setJarvisMode] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [history, setHistory] = useState<Array<{ role: 'user' | 'assistant'; content: string; actions?: ActionResult[] }>>([
    {
      role: 'assistant',
      content: 'Jarvis mode is ready. I can speak responses, manage FastTrade actions, and keep live trade control behind confirmation. Try: "Build my pre-market game plan" or "Buy 1 share of TCS as a dry run".',
    },
  ]);

  const canSend = useMemo(() => message.trim().length > 0 && !loading, [message, loading]);

  useEffect(() => {
    const last = history[history.length - 1];
    if (!voiceEnabled || !last || last.role !== 'assistant') return;
    void speakAssistantText(last.content);
  }, [history, voiceEnabled]);

  const handleVoiceInput = async () => {
    const SpeechRecognitionCtor = getSpeechRecognitionCtor();
    if (!SpeechRecognitionCtor) {
      Alert.alert(
        'Voice input tip',
        Platform.OS === 'web'
          ? 'Speech recognition is not supported in this browser right now.'
          : 'On native mobile, use your device keyboard mic for dictation. Web voice recognition is supported directly in the browser UI.',
      );
      return;
    }

    try {
      const recognition = new SpeechRecognitionCtor();
      recognition.lang = 'en-IN';
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onstart = () => setIsListening(true);
      recognition.onerror = () => {
        setIsListening(false);
        Alert.alert('Voice input', 'I could not hear that clearly. Please try again.');
      };
      recognition.onend = () => setIsListening(false);
      recognition.onresult = (event: any) => {
        const transcript = Array.from(event?.results || [])
          .map((result: any) => result?.[0]?.transcript || '')
          .join(' ')
          .trim();
        if (transcript) {
          setMessage(transcript);
          void send(transcript);
        }
      };
      recognition.start();
    } catch {
      setIsListening(false);
      Alert.alert('Voice input', 'Voice recognition could not be started on this device.');
    }
  };

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
      const res = await aiAPI.query(outgoing, nextHistory, {
        voice_mode: voiceEnabled || jarvisMode,
        assistant_style: jarvisMode ? 'jarvis' : undefined,
      });
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
    stopAssistantVoice();
    setHistory([
      {
        role: 'assistant',
        content: 'Fresh Jarvis session started. Ask anything or give a trading command.',
      },
    ]);
    setMessage('');
    setRefreshing(false);
  };

  const confirmTrade = async (action: ActionResult) => {
    await send(buildTradeConfirmationPrompt(action));
  };

  const cancelTrade = async () => {
    await send('Cancel that pending trade. Do not place the live order.');
  };

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safeArea}>
        <ScreenHeader
          title="AI Desk"
          subtitle="Jarvis-style voice copilot with confirmation-gated trade control"
          badge={<Tag label="JARVIS" color={Colors.accent} bg={Colors.accentSoft} />}
        />

        <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView
            contentContainerStyle={styles.scroll}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={resetConversation} tintColor={Colors.accent} />}
          >
            <View style={styles.modeRow}>
              <TouchableOpacity
                style={[styles.modeChip, jarvisMode && styles.modeChipActive]}
                onPress={() => setJarvisMode((prev) => !prev)}
              >
                <Text style={[styles.modeText, jarvisMode && styles.modeTextActive]}>{jarvisMode ? '🤖 Jarvis ON' : '🤖 Jarvis OFF'}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modeChip, voiceEnabled && styles.modeChipActive]}
                onPress={() => {
                  if (voiceEnabled) stopAssistantVoice();
                  setVoiceEnabled((prev) => !prev);
                }}
              >
                <Text style={[styles.modeText, voiceEnabled && styles.modeTextActive]}>{voiceEnabled ? '🔊 Voice ON' : '🔇 Voice OFF'}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.modeChip, isListening && styles.modeChipActive]} onPress={handleVoiceInput}>
                <Text style={[styles.modeText, isListening && styles.modeTextActive]}>{isListening ? '🎙️ Listening…' : '🎤 Speak'}</Text>
              </TouchableOpacity>
            </View>

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
                        {item.actions.map((a, ai) => (
                          <View key={ai}>
                            <ActionBadge action={a} />
                            <TradeConfirmCard action={a} onConfirm={confirmTrade} onCancel={cancelTrade} busy={loading} />
                          </View>
                        ))}
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
              <View style={styles.composerActions}>
                <TouchableOpacity style={styles.voiceButton} onPress={handleVoiceInput}>
                  <Text style={styles.voiceButtonText}>{isListening ? 'Listening…' : 'Speak'}</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.sendButton, !canSend && styles.sendButtonDisabled]} disabled={!canSend} onPress={() => send()}>
                  <LinearGradient colors={canSend ? ['#1D4ED8', '#3B82F6'] : ['#334155', '#334155']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.sendGradient}>
                    <Text style={styles.sendText}>Send</Text>
                  </LinearGradient>
                </TouchableOpacity>
              </View>
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
  modeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 as any, marginBottom: Spacing.md },
  modeChip: {
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.bgGlass,
    borderRadius: Radius.full,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginRight: 8,
    marginBottom: 8,
  },
  modeChipActive: { borderColor: Colors.borderAccent, backgroundColor: Colors.accentGlow },
  modeText: { color: Colors.textSecondary, fontSize: 12, fontWeight: '700' },
  modeTextActive: { color: Colors.textPrimary },
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
  confirmCard: { marginTop: 6, borderColor: '#a16207', backgroundColor: '#1c1917' },
  confirmTitle: { color: '#fbbf24', fontSize: 12, fontWeight: '700', marginBottom: 4 },
  confirmText: { color: Colors.textPrimary, fontSize: 12, lineHeight: 18 },
  confirmActions: { flexDirection: 'row', marginTop: 10 },
  confirmBtn: { borderRadius: Radius.md, paddingHorizontal: 12, paddingVertical: 8, marginRight: 8 },
  confirmBtnPrimary: { backgroundColor: '#1d4ed8' },
  confirmBtnSecondary: { backgroundColor: '#334155' },
  confirmBtnText: { color: '#fff', fontWeight: '700', fontSize: 12 },
  composerWrap: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.lg, paddingTop: 8 },
  composer: {
    backgroundColor: Colors.bgGlass,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.xl,
    padding: 10,
  },
  input: { color: Colors.textPrimary, minHeight: 44, maxHeight: 120, paddingHorizontal: 4, paddingTop: 8 },
  composerActions: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 },
  voiceButton: { paddingHorizontal: 12, paddingVertical: 10, borderRadius: Radius.md, backgroundColor: Colors.bgGlassStrong, borderWidth: 1, borderColor: Colors.border },
  voiceButtonText: { color: Colors.textPrimary, fontWeight: '700', fontSize: 12 },
  sendButton: { borderRadius: Radius.md, overflow: 'hidden', alignSelf: 'flex-end' },
  sendButtonDisabled: { opacity: 0.55 },
  sendGradient: { paddingHorizontal: 16, paddingVertical: 10 },
  sendText: { color: '#fff', fontWeight: '700' },
});