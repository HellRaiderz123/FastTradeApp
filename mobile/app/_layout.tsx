import { Tabs } from 'expo-router';
import { View, Text, StyleSheet, Platform } from 'react-native';
import { BlurView } from 'expo-blur';
import { Colors } from '../lib/theme';

function TabIcon({ emoji, focused }: { emoji: string; focused: boolean }) {
  return (
    <View style={[styles.iconWrap, focused && styles.iconWrapActive]}>
      <Text style={[styles.emoji, { opacity: focused ? 1 : 0.5 }]}>{emoji}</Text>
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
        tabBarIcon: ({ focused }) => <TabIcon emoji="📊" focused={focused} />,
      }} />
      <Tabs.Screen name="positions" options={{
        title: 'Positions',
        tabBarIcon: ({ focused }) => <TabIcon emoji="💼" focused={focused} />,
      }} />
      <Tabs.Screen name="scanner" options={{
        title: 'Scanner',
        tabBarIcon: ({ focused }) => <TabIcon emoji="🔍" focused={focused} />,
      }} />
      <Tabs.Screen name="journal" options={{
        title: 'Journal',
        tabBarIcon: ({ focused }) => <TabIcon emoji="📖" focused={focused} />,
      }} />
      <Tabs.Screen name="ai" options={{
        title: 'AI',
        tabBarIcon: ({ focused }) => <TabIcon emoji="🤖" focused={focused} />,
      }} />
      <Tabs.Screen name="settings" options={{
        title: 'Settings',
        tabBarIcon: ({ focused }) => <TabIcon emoji="⚙️" focused={focused} />,
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
    position: 'absolute',
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.08)',
    backgroundColor: 'transparent',
    elevation: 0,
    height: Platform.OS === 'ios' ? 85 : 65,
    paddingBottom: Platform.OS === 'ios' ? 20 : 8,
  },
  tabLabel: {
    fontSize: 10,
    fontWeight: '600',
    letterSpacing: 0.3,
  },
  iconWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 4,
  },
  iconWrapActive: {},
  emoji: { fontSize: 22 },
  dot: {
    width: 4, height: 4,
    borderRadius: 2,
    backgroundColor: Colors.accent,
    marginTop: 3,
  },
});
