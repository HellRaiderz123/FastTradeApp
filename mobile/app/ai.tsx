import React, { useEffect, useMemo, useRef, useState } from 'react';
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

type SpeechRecognitionModuleLike = {
  start: (options: Record<string, unknown>) => void;
  stop: () => void;
  abort: () => void;
  requestPermissionsAsync?: () => Promise<{ granted?: boolean; canAskAgain?: boolean }>;
  isRecognitionAvailable?: () => boolean;
  addListener?: (eventName: string, listener: (event?: any) => void) => { remove?: () => void };
};

let speechRecognitionModuleCache: SpeechRecognitionModuleLike | null | undefined;

const getSpeechRecognitionModule = (): SpeechRecognitionModuleLike | null => {
  if (speechRecognitionModuleCache !== undefined) {
    return speechRecognitionModuleCache;
  }

  try {
    const speechPackage = require('expo-speech-recognition');
    speechRecognitionModuleCache = speechPackage?.ExpoSpeechRecognitionModule ?? null;
  } catch {
    speechRecognitionModuleCache = null;
  }

  return speechRecognitionModuleCache ?? null;
};

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
  const baseLabel = ACTION_LABELS[action.tool] ?? action.tool.replace(/_/g, ' ');
  const label = ok ? baseLabel : `${baseLabel} Failed`;
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

const WAKE_WORD_REGEX = /(?:^|\b)(?:hey\s+)?jarvis\b[\s,.:;-]*/i;
const JARVIS_CONTEXTUAL_STRINGS = ['Jarvis', 'FastTrade', 'Nifty', 'Bank Nifty', 'TCS', 'Infosys', 'Zerodha', 'Kite', 'NSE', 'BSE'];

const normalizeSpeechText = (text: string) => String(text || '').replace(/\s+/g, ' ').trim();

const extractWakeCommand = (text: string) => {
  const cleaned = normalizeSpeechText(text);
  const match = cleaned.match(WAKE_WORD_REGEX);
  if (!match || match.index === undefined) return null;
  return cleaned.slice(match.index + match[0].length).trim();
};

const isSpeechRecognitionAvailable = () => {
  try {
    return Boolean(getSpeechRecognitionModule()?.isRecognitionAvailable?.());
  } catch {
    return false;
  }
};

const getDefaultVoiceStatus = (voiceAvailable: boolean, wakeWordEnabled = true) => {
  if (!voiceAvailable) {
    return 'Spoken replies are enabled. Live voice input needs the FastTrade development build, not Expo Go.';
  }
  return wakeWordEnabled
    ? 'Say "Jarvis" and your command to start.'
    : 'Tap the mic and speak your command.';
};

const speakAssistantText = async (
  text: string,
  callbacks?: { onStart?: () => void; onDone?: () => void; onError?: () => void }
) => {
  const cleaned = normalizeSpeechText(text);
  if (!cleaned) return;

  try {
    await Speech.stop();
    Speech.speak(cleaned, {
      language: 'en-IN',
      rate: 0.98,
      pitch: 0.92,
      onStart: () => callbacks?.onStart?.(),
      onDone: () => callbacks?.onDone?.(),
      onStopped: () => callbacks?.onDone?.(),
      onError: () => callbacks?.onError?.(),
    });
  } catch {
    callbacks?.onError?.();
  }
};

const stopAssistantVoice = () => {
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
  const initialVoiceAvailable = isSpeechRecognitionAvailable();
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [jarvisMode, setJarvisMode] = useState(true);
  const [handsFreeMode, setHandsFreeMode] = useState(true);
  const [wakeWordEnabled, setWakeWordEnabled] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [voiceAvailable, setVoiceAvailable] = useState(initialVoiceAvailable);
  const [voiceSessionArmed, setVoiceSessionArmed] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState(getDefaultVoiceStatus(initialVoiceAvailable, true));
  const [history, setHistory] = useState<Array<{ role: 'user' | 'assistant'; content: string; actions?: ActionResult[] }>>([
    {
      role: 'assistant',
      content: 'Jarvis mode is ready. I can speak responses, listen for commands, manage FastTrade actions, and keep live trade control behind confirmation.',
    },
  ]);

  const canSend = useMemo(() => message.trim().length > 0 && !loading, [message, loading]);
  const speechSubscriptionsRef = useRef<Array<{ remove?: () => void }>>([]);
  const lastSpeechTextRef = useRef('');

  const clearSpeechListeners = () => {
    speechSubscriptionsRef.current.forEach((subscription) => subscription?.remove?.());
    speechSubscriptionsRef.current = [];
  };

  const stopListeningSession = (manual = true) => {
    const speechModule = getSpeechRecognitionModule();
    try {
      if (manual) {
        speechModule?.abort?.();
      } else {
        speechModule?.stop?.();
      }
    } catch {
      // ignore stop errors
    }

    clearSpeechListeners();
    setIsListening(false);
    if (manual) {
      setVoiceStatus(getDefaultVoiceStatus(voiceAvailable, wakeWordEnabled));
    }
  };

  const send = async (text?: string) => {
    const outgoing = (text ?? message).trim();
    if (!outgoing) {
      return;
    }

    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setVoiceStatus(`Processing: ${outgoing}`);

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
      setVoiceStatus('Backend connection issue. Please try again.');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }

    setLoading(false);
  };

  const startVoiceSession = async (auto = false) => {
    const speechModule = getSpeechRecognitionModule();
    if (!speechModule) {
      setVoiceAvailable(false);
      setIsListening(false);
      setVoiceStatus('Voice input needs the FastTrade development build. Expo Go cannot load the native speech module.');
      if (!auto) {
        Alert.alert(
          'Mobile Jarvis voice',
          'The app can speak replies now, but live voice recognition requires the FastTrade development build. Please open the custom app built with `npx expo run:android` or `npx expo run:ios` instead of Expo Go.'
        );
      }
      return;
    }

    const available = isSpeechRecognitionAvailable();
    setVoiceAvailable(available);
    if (!available) {
      setVoiceStatus('Speech recognition is unavailable on this device. Enable Siri/Dictation on iPhone or a Google speech service on Android.');
      if (!auto) {
        Alert.alert(
          'Voice recognition unavailable',
          Platform.OS === 'ios'
            ? 'Please enable Siri & Dictation and reopen the app.'
            : 'Please enable a speech recognition service such as Google Voice Typing on this device.'
        );
      }
      return;
    }

    if (!auto) {
      setVoiceSessionArmed(true);
    }

    if (loading) {
      setVoiceStatus('Hold on — I am still processing the previous request.');
      return;
    }

    try {
      const permission = await speechModule.requestPermissionsAsync?.();
      if (permission && permission.granted === false) {
        setVoiceStatus('Microphone or speech permission was denied.');
        Alert.alert('Permission needed', 'Please allow microphone and speech recognition access to use Jarvis voice mode.');
        return;
      }

      clearSpeechListeners();
      lastSpeechTextRef.current = '';

      const startSubscription = speechModule.addListener?.('start', () => {
        setIsListening(true);
        setVoiceStatus(wakeWordEnabled ? 'Listening… say "Jarvis" and your command.' : 'Listening… speak your command.');
      });

      const resultSubscription = speechModule.addListener?.('result', (event: any) => {
        const transcript = normalizeSpeechText(
          Array.isArray(event?.results)
            ? event.results.map((result: any) => result?.transcript || result?.segment || '').join(' ')
            : String(event?.value || '')
        );

        if (!transcript) return;

        lastSpeechTextRef.current = transcript;
        const wakeCommand = wakeWordEnabled ? extractWakeCommand(transcript) : transcript;
        const candidateCommand = normalizeSpeechText(wakeCommand || transcript);
        setMessage(candidateCommand);

        if (event?.isFinal) {
          if (wakeWordEnabled && !wakeCommand) {
            setVoiceStatus('Wake word missing. Say "Jarvis" followed by your command.');
            return;
          }

          setIsListening(false);
          setVoiceStatus(`Executing: ${candidateCommand}`);
          clearSpeechListeners();
          try {
            speechModule.stop?.();
          } catch {
            // ignore stop errors
          }
          void send(candidateCommand);
          return;
        }

        setVoiceStatus(`Heard: ${candidateCommand}`);
      });

      const errorSubscription = speechModule.addListener?.('error', (event: any) => {
        clearSpeechListeners();
        setIsListening(false);
        const code = String(event?.error || 'unknown');
        if (code === 'not-allowed' || code === 'service-not-allowed') {
          setVoiceStatus('Microphone permission is blocked. Please allow it in settings.');
        } else if (code === 'no-speech') {
          setVoiceStatus('No speech detected. Please try again.');
        } else {
          setVoiceStatus(`Voice recognition error: ${code}`);
        }
      });

      const endSubscription = speechModule.addListener?.('end', () => {
        clearSpeechListeners();
        setIsListening(false);
        if (!lastSpeechTextRef.current) {
          setVoiceStatus(getDefaultVoiceStatus(voiceAvailable, wakeWordEnabled));
        }
      });

      speechSubscriptionsRef.current = [startSubscription, resultSubscription, errorSubscription, endSubscription].filter(Boolean) as Array<{ remove?: () => void }>;

      speechModule.start({
        lang: 'en-IN',
        interimResults: true,
        maxAlternatives: 1,
        continuous: handsFreeMode,
        addsPunctuation: true,
        contextualStrings: JARVIS_CONTEXTUAL_STRINGS,
        androidIntentOptions: { EXTRA_LANGUAGE_MODEL: 'web_search' },
        iosTaskHint: 'dictation',
      });
    } catch (error: any) {
      clearSpeechListeners();
      setIsListening(false);
      setVoiceStatus('Voice recognition could not be started on this build.');
      if (!auto) {
        Alert.alert('Voice input', String(error?.message || 'Voice recognition could not be started on this device.'));
      }
    }
  };

  useEffect(() => {
    setVoiceAvailable(isSpeechRecognitionAvailable());
    return () => {
      clearSpeechListeners();
      stopAssistantVoice();
    };
  }, []);

  useEffect(() => {
    const last = history[history.length - 1];
    if (!voiceEnabled || !last || last.role !== 'assistant') return;

    void speakAssistantText(last.content, {
      onStart: () => setVoiceStatus('Jarvis is speaking…'),
      onDone: () => {
        if (voiceSessionArmed && handsFreeMode && voiceAvailable && !loading) {
          setVoiceStatus(wakeWordEnabled ? 'Standing by — say "Jarvis" and your next command.' : 'Standing by for your next command.');
          setTimeout(() => {
            void startVoiceSession(true);
          }, 350);
        } else {
          setVoiceStatus(getDefaultVoiceStatus(voiceAvailable, wakeWordEnabled));
        }
      },
      onError: () => setVoiceStatus('Voice playback is unavailable right now.'),
    });
  }, [history, voiceEnabled, handsFreeMode, voiceAvailable, wakeWordEnabled, voiceSessionArmed, loading]);

  const handleVoiceInput = async () => {
    if (isListening) {
      stopListeningSession(true);
      return;
    }
    await startVoiceSession(false);
  };

  const resetConversation = async () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    stopListeningSession(true);
    stopAssistantVoice();
    setVoiceSessionArmed(false);
    setHistory([
      {
        role: 'assistant',
        content: 'Fresh Jarvis session started. Say "Jarvis" and your command, or tap a starter prompt below.',
      },
    ]);
    setMessage('');
    setVoiceStatus(getDefaultVoiceStatus(voiceAvailable, wakeWordEnabled));
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
            <GlassCard style={styles.voiceHeroCard}>
              <View style={styles.voiceHeroRow}>
                <TouchableOpacity
                  style={[styles.voiceOrb, isListening && styles.voiceOrbActive]}
                  onPress={handleVoiceInput}
                  activeOpacity={0.85}
                >
                  <Text style={styles.voiceOrbIcon}>{isListening ? '🛑' : '🎙️'}</Text>
                </TouchableOpacity>
                <View style={styles.voiceHeroContent}>
                  <Text style={styles.voiceHeroTitle}>{isListening ? 'Jarvis is listening' : 'Engage Jarvis'}</Text>
                  <Text style={styles.voiceHeroText}>{voiceStatus}</Text>
                  <Text style={styles.voiceHeroHint}>
                    {wakeWordEnabled
                      ? 'Example: "Jarvis buy 1 share of TCS as a dry run"'
                      : 'Example: "Buy 1 share of TCS as a dry run"'}
                  </Text>
                </View>
              </View>
            </GlassCard>

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
              <TouchableOpacity
                style={[styles.modeChip, handsFreeMode && styles.modeChipActive]}
                onPress={() => setHandsFreeMode((prev) => !prev)}
              >
                <Text style={[styles.modeText, handsFreeMode && styles.modeTextActive]}>{handsFreeMode ? '🎧 Hands-Free ON' : '🎧 Hands-Free OFF'}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modeChip, wakeWordEnabled && styles.modeChipActive]}
                onPress={() => setWakeWordEnabled((prev) => !prev)}
              >
                <Text style={[styles.modeText, wakeWordEnabled && styles.modeTextActive]}>{wakeWordEnabled ? '🗣️ Wake Word ON' : '🗣️ Wake Word OFF'}</Text>
              </TouchableOpacity>
            </View>

            {!voiceAvailable && (
              <GlassCard style={styles.warningCard}>
                <Text style={styles.warningTitle}>Voice input needs a custom build</Text>
                <Text style={styles.warningText}>
                  This screen will not crash now, but full microphone recognition requires the FastTrade development build or App Store/TestFlight build — not Expo Go.
                </Text>
              </GlassCard>
            )}

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
                placeholder={wakeWordEnabled ? 'Say "Jarvis" or type a command...' : 'Ask a question or give a command...'}
                placeholderTextColor={Colors.textMuted}
                style={styles.input}
                multiline
              />
              <View style={styles.composerActions}>
                <TouchableOpacity style={[styles.voiceButton, isListening && styles.voiceButtonActive]} onPress={handleVoiceInput}>
                  <Text style={styles.voiceButtonText}>{isListening ? 'Stop Mic' : 'Start Mic'}</Text>
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
  voiceHeroCard: {
    marginBottom: Spacing.md,
    borderColor: Colors.borderAccent,
    backgroundColor: Colors.bgGlassStrong,
  },
  voiceHeroRow: { flexDirection: 'row', alignItems: 'center' },
  voiceOrb: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 1,
    borderColor: Colors.borderAccent,
    backgroundColor: Colors.accentGlow,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  voiceOrbActive: {
    backgroundColor: '#7c2d12',
    borderColor: '#f59e0b',
  },
  voiceOrbIcon: { fontSize: 28 },
  voiceHeroContent: { flex: 1 },
  voiceHeroTitle: { color: Colors.textPrimary, fontSize: 16, fontWeight: '700' },
  voiceHeroText: { color: Colors.textSecondary, fontSize: 13, lineHeight: 19, marginTop: 4 },
  voiceHeroHint: { color: Colors.textMuted, fontSize: 12, marginTop: 6 },
  modeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 as any, marginBottom: Spacing.md },
  warningCard: { marginBottom: Spacing.md, borderColor: '#a16207', backgroundColor: '#1c1917' },
  warningTitle: { color: '#fbbf24', fontSize: 13, fontWeight: '700', marginBottom: 4 },
  warningText: { color: Colors.textSecondary, fontSize: 12, lineHeight: 18 },
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
  voiceButtonActive: { borderColor: '#f59e0b', backgroundColor: '#7c2d12' },
  voiceButtonText: { color: Colors.textPrimary, fontWeight: '700', fontSize: 12 },
  sendButton: { borderRadius: Radius.md, overflow: 'hidden', alignSelf: 'flex-end' },
  sendButtonDisabled: { opacity: 0.55 },
  sendGradient: { paddingHorizontal: 16, paddingVertical: 10 },
  sendText: { color: '#fff', fontWeight: '700' },
});