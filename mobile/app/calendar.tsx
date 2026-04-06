import React, { useCallback, useEffect, useState } from 'react';
import {
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { calendarAPI } from '../lib/api';
import { Colors, Radius, Spacing } from '../lib/theme';
import { EmptyState, GlassCard, LoadingSpinner, ScreenHeader, Tag } from '../components/ui';

type Tab = 'today' | 'week' | 'events';

export default function CalendarScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<Tab>('today');
  const [todayEvents, setTodayEvents] = useState<any[]>([]);
  const [weekByDay, setWeekByDay] = useState<Record<string, any[]>>({});
  const [events, setEvents] = useState<any[]>([]);

  const load = useCallback(async () => {
    try {
      const [todayRes, weekRes, eventsRes] = await Promise.allSettled([
        calendarAPI.getToday(),
        calendarAPI.getWeek(),
        calendarAPI.getEvents({ days_ahead: 30, event_type: 'all' }),
      ]);

      if (todayRes.status === 'fulfilled') setTodayEvents(todayRes.value.data?.events || []);
      if (weekRes.status === 'fulfilled') setWeekByDay(weekRes.value.data?.events_by_day || {});
      if (eventsRes.status === 'fulfilled') setEvents(eventsRes.value.data?.events || []);
    } catch {
      setTodayEvents([]);
      setWeekByDay({});
      setEvents([]);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  if (loading) {
    return <View style={styles.root}><LoadingSpinner /></View>;
  }

  const weekDays = Object.keys(weekByDay || {});
  const list = tab === 'today' ? todayEvents : tab === 'events' ? events : [];

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScreenHeader
          title="Calendar"
          subtitle="Economic and market events across upcoming sessions"
          badge={<Tag label={`${events.length} EVENTS`} color={Colors.accent} bg={Colors.accentSoft} />}
          onBack={() => router.back()}
        />

        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.tabRow}>
            {(['today', 'week', 'events'] as Tab[]).map((value) => (
              <TouchableOpacity key={value} style={[styles.tabBtn, tab === value && styles.tabBtnActive]} onPress={() => setTab(value)}>
                <Text style={[styles.tabText, tab === value && styles.tabTextActive]}>{value.toUpperCase()}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {tab === 'week' ? (
            weekDays.length === 0 ? (
              <EmptyState icon="📆" title="No Week Events" subtitle="No events found for this week." />
            ) : (
              weekDays.map((day) => (
                <GlassCard key={day} style={styles.card}>
                  <Text style={styles.dayTitle}>{new Date(day).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })}</Text>
                  {(weekByDay[day] || []).map((event: any, index: number) => (
                    <EventRow key={`${event.title || event.name || day}-${index}`} event={event} />
                  ))}
                </GlassCard>
              ))
            )
          ) : list.length === 0 ? (
            <EmptyState icon="🗓️" title="No Events" subtitle="No events available in this view." />
          ) : (
            list.map((event: any, index: number) => (
              <GlassCard key={`${event.title || event.name || index}-${index}`} style={styles.card}>
                <EventRow event={event} />
              </GlassCard>
            ))
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

function EventRow({ event }: { event: any }) {
  const impact = String(event?.impact || 'low').toLowerCase();
  const impactColor = impact === 'high' ? Colors.red : impact === 'medium' ? Colors.amber : Colors.green;
  return (
    <View style={styles.eventRow}>
      <View style={{ flex: 1, paddingRight: 8 }}>
        <Text style={styles.eventTitle}>{event?.title || event?.name || 'Event'}</Text>
        <Text style={styles.eventMeta}>{event?.type || 'economic'} • {event?.source || 'Live'} • {event?.date || '-'}</Text>
        {event?.countdown ? <Text style={styles.eventCountdown}>{event.countdown}</Text> : null}
      </View>
      <Tag label={impact.toUpperCase()} color={impactColor} bg={`${impactColor}22`} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safe: { flex: 1 },
  scroll: { padding: Spacing.lg, paddingBottom: 120 },
  tabRow: { flexDirection: 'row', gap: 8, marginBottom: Spacing.md },
  tabBtn: { flex: 1, paddingVertical: 10, borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.bgGlass, alignItems: 'center' },
  tabBtnActive: { borderColor: Colors.accent, backgroundColor: Colors.accentSoft },
  tabText: { color: Colors.textSecondary, fontSize: 12, fontWeight: '700' },
  tabTextActive: { color: Colors.accentLight },
  card: { marginBottom: 10 },
  dayTitle: { color: Colors.textPrimary, fontSize: 14, fontWeight: '700', marginBottom: 8 },
  eventRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: Colors.border },
  eventTitle: { color: Colors.textPrimary, fontSize: 13, fontWeight: '600' },
  eventMeta: { color: Colors.textSecondary, fontSize: 12, marginTop: 2 },
  eventCountdown: { color: Colors.accentLight, fontSize: 11, marginTop: 3 },
});
