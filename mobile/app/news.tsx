import React, { useCallback, useEffect, useState } from 'react';
import {
  Linking,
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { newsAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, ScreenHeader, Tag } from '../components/ui';

const CATEGORIES = ['All', 'Market', 'Stocks', 'Economy', 'RBI', 'IPO', 'Earnings', 'Corporate'];
const SENTIMENTS = ['all', 'bullish', 'bearish', 'neutral'] as const;

function sentimentColor(s: string) {
  if (s === 'bullish') return Colors.green;
  if (s === 'bearish') return Colors.red;
  return Colors.textMuted;
}

function sentimentBg(s: string) {
  if (s === 'bullish') return Colors.greenBg;
  if (s === 'bearish') return Colors.redBg;
  return Colors.bgGlass;
}

function timeAgo(iso: string) {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  } catch { return ''; }
}

export default function NewsScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [news, setNews] = useState<any[]>([]);
  const [trending, setTrending] = useState<any[]>([]);
  const [sentimentSummary, setSentimentSummary] = useState<any>(null);
  const [category, setCategory] = useState('All');
  const [sentiment, setSentiment] = useState<string>('all');

  const load = useCallback(async () => {
    try {
      const [feedRes, trendRes] = await Promise.allSettled([
        newsAPI.getFeed({
          limit: 40,
          ...(category !== 'All' ? { category } : {}),
          ...(sentiment !== 'all' ? { sentiment } : {}),
        }),
        newsAPI.getTrending(),
      ]);
      if (feedRes.status === 'fulfilled') {
        setNews(feedRes.value.data?.news || []);
        setSentimentSummary(feedRes.value.data?.sentiment_summary || null);
      }
      if (trendRes.status === 'fulfilled') {
        setTrending(trendRes.value.data?.topics || []);
      }
    } catch {}
    setLoading(false);
    setRefreshing(false);
  }, [category, sentiment]);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    load();
  };

  if (loading) return <View style={styles.root}><LoadingSpinner /></View>;

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScreenHeader
          title="Market News"
          subtitle="Live headlines from MoneyControl, ET, BS"
          badge={<Tag label={`${news.length} STORIES`} color={Colors.accent} bg={Colors.accentSoft} />}
          onBack={() => router.back()}
        />

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          {/* Sentiment summary */}
          {sentimentSummary && (
            <View style={styles.sentimentRow}>
              <View style={[styles.sentimentBox, { borderColor: Colors.green + '40' }]}>
                <Text style={[styles.sentimentCount, { color: Colors.green }]}>{sentimentSummary.bullish}</Text>
                <Text style={styles.sentimentLabel}>Bullish</Text>
              </View>
              <View style={[styles.sentimentBox, { borderColor: Colors.red + '40' }]}>
                <Text style={[styles.sentimentCount, { color: Colors.red }]}>{sentimentSummary.bearish}</Text>
                <Text style={styles.sentimentLabel}>Bearish</Text>
              </View>
              <View style={[styles.sentimentBox, { borderColor: Colors.border }]}>
                <Text style={[styles.sentimentCount, { color: Colors.textSecondary }]}>{sentimentSummary.neutral}</Text>
                <Text style={styles.sentimentLabel}>Neutral</Text>
              </View>
            </View>
          )}

          {/* Trending topics */}
          {trending.length > 0 && (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.trendingRow} contentContainerStyle={{ gap: 8, paddingRight: 16 }}>
              {trending.slice(0, 8).map((t: any) => (
                <View key={t.keyword} style={[styles.trendChip, { borderColor: t.sentiment > 0 ? Colors.green + '60' : t.sentiment < 0 ? Colors.red + '60' : Colors.border }]}>
                  <Text style={styles.trendKeyword}>{t.keyword}</Text>
                  <Text style={styles.trendCount}>{t.mentions}</Text>
                </View>
              ))}
            </ScrollView>
          )}

          {/* Category filter */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterRow} contentContainerStyle={{ gap: 8, paddingRight: 16 }}>
            {CATEGORIES.map((c) => (
              <TouchableOpacity
                key={c}
                style={[styles.chip, category === c && styles.chipActive]}
                onPress={() => { Haptics.selectionAsync(); setCategory(c); }}
                activeOpacity={0.8}
              >
                <Text style={[styles.chipText, category === c && styles.chipTextActive]}>{c}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          {/* Sentiment filter */}
          <View style={styles.sentimentFilter}>
            {SENTIMENTS.map((s) => (
              <TouchableOpacity
                key={s}
                style={[styles.sentPill, sentiment === s && styles.sentPillActive]}
                onPress={() => { Haptics.selectionAsync(); setSentiment(s); }}
                activeOpacity={0.8}
              >
                <Text style={[styles.sentPillText, sentiment === s && styles.sentPillTextActive]}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* News list */}
          {news.length === 0 ? (
            <EmptyState icon="📰" title="No News" subtitle="Pull to refresh or change filters." />
          ) : (
            news.map((item: any, i: number) => (
              <TouchableOpacity
                key={i}
                activeOpacity={0.85}
                onPress={() => { if (item.link) Linking.openURL(item.link).catch(() => {}); }}
              >
                <GlassCard style={styles.newsCard}>
                  <View style={styles.newsTop}>
                    <View style={styles.newsLeft}>
                      <Text style={styles.newsTitle} numberOfLines={3}>{item.title}</Text>
                      <View style={styles.newsMeta}>
                        <Text style={styles.newsSource}>{item.source || 'RSS'}</Text>
                        {item.published ? <Text style={styles.newsTime}>{timeAgo(item.published)}</Text> : null}
                      </View>
                    </View>
                    <View style={styles.newsRight}>
                      <Tag
                        label={(item.sentiment || 'neutral').toUpperCase()}
                        color={sentimentColor(item.sentiment)}
                        bg={sentimentBg(item.sentiment)}
                      />
                      {item.link ? <Ionicons name="open-outline" size={13} color={Colors.textFaint} style={{ marginTop: 6 }} /> : null}
                    </View>
                  </View>
                  {item.category ? (
                    <Text style={styles.newsCategory}>{item.category}</Text>
                  ) : null}
                </GlassCard>
              </TouchableOpacity>
            ))
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
  sentimentRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  sentimentBox: { flex: 1, alignItems: 'center', paddingVertical: 10, borderRadius: Radius.md, borderWidth: 1, backgroundColor: Colors.bgGlass },
  sentimentCount: { fontSize: 20, fontWeight: '700' },
  sentimentLabel: { fontSize: 10, color: Colors.textMuted, marginTop: 2, textTransform: 'uppercase', letterSpacing: 0.5 },
  trendingRow: { marginBottom: 12 },
  trendChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: Radius.sm, borderWidth: 1, backgroundColor: Colors.bgGlass, flexDirection: 'row', alignItems: 'center', gap: 5 },
  trendKeyword: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary },
  trendCount: { fontSize: 11, color: Colors.textFaint, backgroundColor: Colors.bgGlassStrong, paddingHorizontal: 5, paddingVertical: 1, borderRadius: 8 },
  filterRow: { marginBottom: 10 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.bgGlass },
  chipActive: { backgroundColor: Colors.accentSoft, borderColor: Colors.accent },
  chipText: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary },
  chipTextActive: { color: Colors.accentLight },
  sentimentFilter: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  sentPill: { flex: 1, paddingVertical: 7, alignItems: 'center', borderRadius: Radius.sm, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.bgGlass },
  sentPillActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  sentPillText: { fontSize: 11, fontWeight: '600', color: Colors.textSecondary },
  sentPillTextActive: { color: Colors.accentLight },
  newsCard: { marginBottom: 10 },
  newsTop: { flexDirection: 'row', gap: 10 },
  newsLeft: { flex: 1 },
  newsRight: { alignItems: 'flex-end', minWidth: 70 },
  newsTitle: { fontSize: 14, fontWeight: '600', color: Colors.textPrimary, lineHeight: 20 },
  newsMeta: { flexDirection: 'row', gap: 8, marginTop: 6, alignItems: 'center' },
  newsSource: { fontSize: 11, color: Colors.accent, fontWeight: '600' },
  newsTime: { fontSize: 11, color: Colors.textFaint },
  newsCategory: { fontSize: 10, color: Colors.textMuted, marginTop: 6, textTransform: 'uppercase', letterSpacing: 0.5 },
});
