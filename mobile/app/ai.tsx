import React, { useMemo, useState } from 'react';
import { KeyboardAvoidingView, Platform, RefreshControl, ScrollView, StatusBar, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';
import { aiAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { GlassCard, ScreenHeader, Tag } from '../components/ui';

const STARTERS = [
  'Show my open positions',
  'What scanner signals fired this week?',
  'How much brokerage did I pay?',
  'Summarize my trading performance',
];

export default function AIScreen() {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [history, setHistory] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([
    {
      role: 'assistant',
      content: 'FastTrade AI is ready. This screen is UI-first today and can already connect to the same backend chat endpoint when available.',
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
      const reply = res.data?.response || res.data?.message || 'Connected, but no response body was returned from the backend.';
      setHistory((prev) => [...prev, { role: 'assistant', content: reply }]);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.response?.data?.error || error?.message;
      setHistory((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: detail
            ? `AI assistant error: ${String(detail)}`
            : 'The backend assistant is not reachable right now. Check AI URL and main backend URL in Settings.',
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
        content: 'Fresh chat started. Ask anything about positions, scanner signals, P&L, or settings.',
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
          subtitle="Natural-language trading, scanner, and finance queries"
          badge={<Tag label="SMART ASSIST" color={Colors.accent} bg={Colors.accentSoft} />}
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
                  <GlassCard style={[styles.bubble, assistant ? styles.assistantBubble : styles.userBubble]}>
                    <View style={styles.bubbleTop}>
                      <Tag label={assistant ? 'AI' : 'YOU'} color={assistant ? Colors.accent : Colors.green} bg={assistant ? Colors.accentGlow : Colors.greenBg} />
                    </View>
                    <Text style={styles.bubbleText}>{item.content}</Text>
                  </GlassCard>
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
                placeholder="Ask about positions, scanner signals, P&L, or budgets"
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
  bubble: { maxWidth: '86%' },
  assistantBubble: { backgroundColor: Colors.bgGlassStrong },
  userBubble: { backgroundColor: Colors.accentGlow, borderColor: Colors.borderAccent },
  bubbleTop: { marginBottom: 8 },
  bubbleText: { color: Colors.textPrimary, fontSize: 14, lineHeight: 20 },
  loadingText: { color: Colors.textSecondary, fontSize: 14, fontStyle: 'italic' },
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