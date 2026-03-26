import { Tabs } from 'expo-router';
import { View, StyleSheet, Platform } from 'react-native';
import { BlurView } from 'expo-blur';
import { Colors } from '../lib/theme';
import { Ionicons } from '@expo/vector-icons';

function TabIcon({ name, focused }: { name: keyof typeof Ionicons.glyphMap; focused: boolean }) {
  return (
    <View style={[styles.iconWrap, focused && styles.iconWrapActive]}>
      <Ionicons
        name={name}
        size={20}
        color={focused ? Colors.tabActive : Colors.tabInactive}
      />
      {focused && <View style={styles.dot} />}
    </View>
  );
}

export default function Layout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: styles.tabBar,
        tabBarActiveTintColor: Colors.accent,
        tabBarInactiveTintColor: Colors.tabInactive,
        tabBarLabelStyle: styles.tabLabel,
        tabBarBackground: () => (
          <BlurView intensity={80} tint="dark" style={StyleSheet.absoluteFill} />
        ),
      }}
    >
      <Tabs.Screen name="index" options={{
        title: 'Dashboard',
        tabBarIcon: ({ focused }) => <TabIcon name="grid-outline" focused={focused} />,
      }} />
      <Tabs.Screen name="positions" options={{
        title: 'Positions',
        tabBarIcon: ({ focused }) => <TabIcon name="briefcase-outline" focused={focused} />,
      }} />
      <Tabs.Screen name="scanner" options={{
        title: 'Scanner',
        tabBarIcon: ({ focused }) => <TabIcon name="search-outline" focused={focused} />,
      }} />
      <Tabs.Screen name="journal" options={{
        title: 'Journal',
        tabBarIcon: ({ focused }) => <TabIcon name="book-outline" focused={focused} />,
      }} />
      <Tabs.Screen name="ai" options={{
        title: 'AI',
        tabBarIcon: ({ focused }) => <TabIcon name="sparkles-outline" focused={focused} />,
      }} />
      <Tabs.Screen name="settings" options={{
        title: 'Settings',
        tabBarIcon: ({ focused }) => <TabIcon name="settings-outline" focused={focused} />,
      }} />
      <Tabs.Screen name="dashboard" options={{ href: null }} />
      <Tabs.Screen name="backtest" options={{ href: null }} />
      <Tabs.Screen name="strategies" options={{ href: null }} />
      <Tabs.Screen name="strategyBuilder" options={{ href: null }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.08)',
    backgroundColor: Colors.tabBg,
    elevation: 0,
    height: Platform.OS === 'ios' ? 88 : 68,
    paddingBottom: Platform.OS === 'ios' ? 20 : 8,
    paddingTop: 6,
  },
  tabLabel: {
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
  iconWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 4,
  },
  iconWrapActive: {},
  dot: {
    width: 4, height: 4,
    borderRadius: 2,
    backgroundColor: Colors.accent,
    marginTop: 3,
  },
});
