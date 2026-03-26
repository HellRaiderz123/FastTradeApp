import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
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
import * as Haptics from 'expo-haptics';
import { Ionicons } from '@expo/vector-icons';
import { watchlistAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, PrimaryButton, ScreenHeader, Tag } from '../components/ui';

const PRESET_COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#14B8A6'];

export default function WatchlistsScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [watchlists, setWatchlists] = useState<any[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [quotes, setQuotes] = useState<Record<number, any[]>>({});
  const [quotesLoading, setQuotesLoading] = useState<Record<number, boolean>>({});

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState(PRESET_COLORS[0]);
  const [creating, setCreating] = useState(false);

  // Add symbol form
  const [addingSymbolTo, setAddingSymbolTo] = useState<number | null>(null);
  const [newSymbol, setNewSymbol] = useState('');
  const addRef = useRef(false);

  const load = useCallback(async () => {
    try {
      const res = await watchlistAPI.list();
      const data = res.data?.watchlists || res.data || [];
      setWatchlists(Array.isArray(data) ? data : []);
    } catch {
      setWatchlists([]);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    load();
  };

  const loadQuotes = async (id: number) => {
    setQuotesLoading((prev) => ({ ...prev, [id]: true }));
    try {
      const res = await watchlistAPI.getQuotes(id);
      const q = res.data?.quotes || [];
      setQuotes((prev) => ({ ...prev, [id]: q }));
    } catch {
      setQuotes((prev) => ({ ...prev, [id]: [] }));
    }
    setQuotesLoading((prev) => ({ ...prev, [id]: false }));
  };

  const toggleExpand = (id: number) => {
    const next = expandedId === id ? null : id;
    setExpandedId(next);
    if (next !== null && !quotes[next]) {
      loadQuotes(next);
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  };

  const createWatchlist = async () => {
    if (!newName.trim() || creating) return;
    setCreating(true);
    try {
      await watchlistAPI.create({ name: newName.trim(), color: newColor });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setNewName('');
      setNewColor(PRESET_COLORS[0]);
      setShowCreate(false);
      await load();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Create failed';
      Alert.alert('Error', String(detail));
    }
    setCreating(false);
  };

  const deleteWatchlist = (id: number, name: string) => {
    Alert.alert('Delete Watchlist', `Remove "${name}"?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await watchlistAPI.remove(id);
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
            setExpandedId(null);
            await load();
          } catch (err: any) {
            Alert.alert('Error', err?.response?.data?.detail || 'Delete failed');
          }
        },
      },
    ]);
  };

  const addSymbol = async (watchlistId: number) => {
    const sym = newSymbol.trim().toUpperCase();
    if (!sym || addRef.current) return;
    addRef.current = true;
    try {
      await watchlistAPI.addSymbol(watchlistId, sym);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setNewSymbol('');
      setAddingSymbolTo(null);
      await load();
      // Refresh quotes if expanded
      if (expandedId === watchlistId) loadQuotes(watchlistId);
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.detail || 'Add failed');
    }
    addRef.current = false;
  };

  const removeSymbol = async (watchlistId: number, symbol: string) => {
    try {
      await watchlistAPI.removeSymbol(watchlistId, symbol);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      await load();
      if (expandedId === watchlistId) loadQuotes(watchlistId);
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.detail || 'Remove failed');
    }
  };

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScreenHeader
          title="Watchlists"
          subtitle="Track your favourite symbols in organised lists"
          badge={<Tag label={`${watchlists.length} LISTS`} color={Colors.accent} bg={Colors.accentSoft} />}
        />

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          {/* Create new */}
          <TouchableOpacity
            style={styles.addBtn}
            onPress={() => { setShowCreate(!showCreate); Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); }}
            activeOpacity={0.8}
          >
            <Ionicons name={showCreate ? 'close-outline' : 'add-circle-outline'} size={18} color={Colors.accent} />
            <Text style={styles.addBtnText}>{showCreate ? 'Cancel' : 'New Watchlist'}</Text>
          </TouchableOpacity>

          {showCreate && (
            <GlassCard style={styles.createCard}>
              <Text style={styles.sectionTitle}>Create Watchlist</Text>
              <Text style={styles.label}>Name</Text>
              <TextInput
                style={styles.input}
                value={newName}
                onChangeText={setNewName}
                placeholder="e.g. My F&O Picks"
                placeholderTextColor={Colors.textFaint}
              />
              <Text style={styles.label}>Color</Text>
              <View style={styles.colorRow}>
                {PRESET_COLORS.map((c) => (
                  <TouchableOpacity
                    key={c}
                    style={[styles.colorDot, { backgroundColor: c }, newColor === c && styles.colorDotActive]}
                    onPress={() => setNewColor(c)}
                  />
                ))}
              </View>
              <PrimaryButton title="Create" onPress={createWatchlist} loading={creating} variant="primary" style={{ marginTop: 8 }} />
            </GlassCard>
          )}

          {watchlists.length === 0 ? (
            <EmptyState icon="📋" title="No Watchlists" subtitle="Create your first watchlist to track symbols." />
          ) : (
            watchlists.map((wl) => {
              const isExpanded = expandedId === wl.id;
              const wlQuotes: any[] = quotes[wl.id] || [];
              const symList: string[] = Array.isArray(wl.symbols) ? wl.symbols : [];

              return (
                <GlassCard key={wl.id} style={styles.wlCard}>
                  {/* Header row */}
                  <TouchableOpacity style={styles.wlHeader} onPress={() => toggleExpand(wl.id)} activeOpacity={0.8}>
                    <View style={[styles.colorStripe, { backgroundColor: wl.color || Colors.accent }]} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.wlName}>{wl.name}</Text>
                      <Text style={styles.wlMeta}>{symList.length} symbol{symList.length !== 1 ? 's' : ''}</Text>
                    </View>
                    <TouchableOpacity onPress={() => deleteWatchlist(wl.id, wl.name)} style={{ padding: 4, marginRight: 4 }}>
                      <Ionicons name="trash-outline" size={16} color={Colors.red} />
                    </TouchableOpacity>
                    <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={18} color={Colors.textMuted} />
                  </TouchableOpacity>

                  {isExpanded && (
                    <View style={styles.expandedContent}>
                      {/* Add symbol */}
                      {addingSymbolTo === wl.id ? (
                        <View style={styles.addSymRow}>
                          <TextInput
                            style={[styles.input, { flex: 1, marginBottom: 0 }]}
                            value={newSymbol}
                            onChangeText={setNewSymbol}
                            placeholder="e.g. RELIANCE"
                            placeholderTextColor={Colors.textFaint}
                            autoCapitalize="characters"
                            autoFocus
                          />
                          <TouchableOpacity style={styles.symAddBtn} onPress={() => addSymbol(wl.id)} activeOpacity={0.8}>
                            <Text style={{ color: '#fff', fontWeight: '700', fontSize: 13 }}>Add</Text>
                          </TouchableOpacity>
                          <TouchableOpacity style={{ padding: 8 }} onPress={() => { setAddingSymbolTo(null); setNewSymbol(''); }}>
                            <Ionicons name="close" size={18} color={Colors.textMuted} />
                          </TouchableOpacity>
                        </View>
                      ) : (
                        <TouchableOpacity
                          style={styles.addSymTrigger}
                          onPress={() => { setAddingSymbolTo(wl.id); setNewSymbol(''); }}
                          activeOpacity={0.8}
                        >
                          <Ionicons name="add-circle-outline" size={15} color={Colors.accent} />
                          <Text style={styles.addSymText}>Add Symbol</Text>
                        </TouchableOpacity>
                      )}

                      {/* Quotes table */}
                      {quotesLoading[wl.id] ? (
                        <Text style={styles.loadingText}>Loading quotes…</Text>
                      ) : wlQuotes.length > 0 ? (
                        <>
                          <View style={styles.quoteHeaderRow}>
                            <Text style={[styles.quoteCell, { flex: 2 }]}>Symbol</Text>
                            <Text style={[styles.quoteCell, { textAlign: 'right' }]}>LTP</Text>
                            <Text style={[styles.quoteCell, { textAlign: 'right' }]}>Chg%</Text>
                            <Text style={[styles.quoteCell, { width: 32 }]} />
                          </View>
                          {wlQuotes.map((q: any) => {
                            const chg = q.change_pct ?? q.pct_change ?? 0;
                            const chgColor = chg >= 0 ? Colors.green : Colors.red;
                            return (
                              <View key={q.symbol} style={styles.quoteRow}>
                                <Text style={[styles.quoteSymbol, { flex: 2 }]}>{q.symbol}</Text>
                                <Text style={[styles.quoteVal, { textAlign: 'right' }]}>
                                  ₹{Number(q.ltp ?? q.last_price ?? 0).toFixed(2)}
                                </Text>
                                <Text style={[styles.quoteVal, { color: chgColor, textAlign: 'right' }]}>
                                  {chg >= 0 ? '+' : ''}{Number(chg).toFixed(2)}%
                                </Text>
                                <TouchableOpacity onPress={() => removeSymbol(wl.id, q.symbol)} style={{ width: 32, alignItems: 'center' }}>
                                  <Ionicons name="remove-circle-outline" size={16} color={Colors.red} />
                                </TouchableOpacity>
                              </View>
                            );
                          })}
                        </>
                      ) : symList.length > 0 ? (
                        // No quotes yet — show plain symbol chips
                        <View style={styles.symChipRow}>
                          {symList.map((s) => (
                            <View key={s} style={styles.symChip}>
                              <Text style={styles.symChipText}>{s}</Text>
                              <TouchableOpacity onPress={() => removeSymbol(wl.id, s)} style={{ marginLeft: 4 }}>
                                <Ionicons name="close-circle" size={13} color={Colors.textMuted} />
                              </TouchableOpacity>
                            </View>
                          ))}
                        </View>
                      ) : (
                        <Text style={styles.emptyText}>No symbols yet. Tap "Add Symbol" to get started.</Text>
                      )}

                      {symList.length > 0 && !quotesLoading[wl.id] && (
                        <TouchableOpacity style={styles.refreshQuotesBtn} onPress={() => loadQuotes(wl.id)} activeOpacity={0.8}>
                          <Ionicons name="refresh-outline" size={14} color={Colors.accent} />
                          <Text style={styles.refreshQuotesText}>Refresh Quotes</Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  )}
                </GlassCard>
              );
            })
          )}

          <View style={{ height: 96 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safe: { flex: 1 },
  scroll: { padding: Spacing.lg },
  addBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.accentSoft,
    backgroundColor: Colors.bgGlass,
    marginBottom: 12,
    alignSelf: 'flex-start',
  },
  addBtnText: { fontSize: 14, fontWeight: '600', color: Colors.accent },
  createCard: { marginBottom: 12 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: Colors.textPrimary, marginBottom: 12 },
  label: { fontSize: 12, fontWeight: '600', color: Colors.textMuted, marginBottom: 6, textTransform: 'uppercase' },
  input: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.bgGlass,
    color: Colors.textPrimary,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    marginBottom: 10,
  },
  colorRow: { flexDirection: 'row', gap: 10, marginBottom: 12 },
  colorDot: { width: 28, height: 28, borderRadius: 14, opacity: 0.7 },
  colorDotActive: { opacity: 1, borderWidth: 2, borderColor: '#fff' },
  wlCard: { marginBottom: 10 },
  wlHeader: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  colorStripe: { width: 4, height: 38, borderRadius: 2 },
  wlName: { fontSize: 15, fontWeight: '700', color: Colors.textPrimary },
  wlMeta: { fontSize: 11, color: Colors.textMuted, marginTop: 1 },
  expandedContent: { marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: Colors.border },
  addSymRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  symAddBtn: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: Radius.md,
    backgroundColor: Colors.accent,
  },
  addSymTrigger: { flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 10 },
  addSymText: { fontSize: 13, color: Colors.accent, fontWeight: '600' },
  quoteHeaderRow: { flexDirection: 'row', paddingBottom: 6, borderBottomWidth: 1, borderBottomColor: Colors.border },
  quoteCell: { flex: 1, fontSize: 10, color: Colors.textMuted, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
  quoteRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 7, borderBottomWidth: 1, borderBottomColor: Colors.border },
  quoteSymbol: { fontSize: 13, fontWeight: '700', color: Colors.textPrimary },
  quoteVal: { flex: 1, fontSize: 13, fontWeight: '600', color: Colors.textPrimary },
  loadingText: { color: Colors.textMuted, fontSize: 13, paddingVertical: 10 },
  emptyText: { color: Colors.textMuted, fontSize: 13, paddingVertical: 10 },
  symChipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 },
  symChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.bgGlass,
    borderRadius: Radius.sm,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  symChipText: { fontSize: 12, color: Colors.textSecondary, fontWeight: '600' },
  refreshQuotesBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 8 },
  refreshQuotesText: { fontSize: 12, color: Colors.accent },
});
