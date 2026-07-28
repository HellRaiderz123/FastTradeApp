import { Tabs } from 'expo-router';
import React, { useEffect } from 'react';
import { View, StyleSheet, Platform, AppState } from 'react-native';
import { BlurView } from 'expo-blur';
import { Colors } from '../lib/theme';
import { Ionicons } from '@expo/vector-icons';
import { requestNotificationPermissions } from '../lib/notifications';
import { LoadingSpinner } from '../components/ui';
import { BiometricLockScreen, LoginScreen } from '../components/AuthScreens';
import { useAuthStore } from '../lib/auth';

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
  const bootstrap = useAuthStore((state) => state.bootstrap);
  const bootstrapped = useAuthStore((state) => state.bootstrapped);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isLocked = useAuthStore((state) => state.isLocked);
  const handleAppStateChange = useAuthStore((state) => state.handleAppStateChange);

  useEffect(() => {
    bootstrap();
    requestNotificationPermissions();
    const subscription = AppState.addEventListener('change', handleAppStateChange);
    return () => subscription.remove();
  }, [bootstrap, handleAppStateChange]);

  if (!bootstrapped) {
    return (
      <View style={styles.loadingRoot}>
        <LoadingSpinner />
      </View>
    );
  }

  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  if (isLocked) {
    return <BiometricLockScreen />;
  }

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
      <Tabs.Screen name="optionChain" options={{ href: null }} />
      <Tabs.Screen name="autoTrader" options={{ href: null }} />
      <Tabs.Screen name="watchlists" options={{ href: null }} />
      <Tabs.Screen name="alerts" options={{ href: null }} />
      <Tabs.Screen name="strategyPnl" options={{ href: null }} />
      <Tabs.Screen name="finance" options={{ href: null }} />
      <Tabs.Screen name="screener" options={{ href: null }} />
      <Tabs.Screen name="heatmap" options={{ href: null }} />
      <Tabs.Screen name="tradeCostTracker" options={{ href: null }} />
      <Tabs.Screen name="brokerReconciliation" options={{ href: null }} />
      <Tabs.Screen name="mlCenter" options={{ href: null }} />
      <Tabs.Screen name="calendar" options={{ href: null }} />
      <Tabs.Screen name="aiAgents" options={{ href: null }} />
      <Tabs.Screen name="news" options={{ href: null }} />
      <Tabs.Screen name="account" options={{ href: null }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  loadingRoot: {
    flex: 1,
    backgroundColor: Colors.bg,
  },
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
