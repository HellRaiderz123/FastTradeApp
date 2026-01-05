import React, { useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, SafeAreaView } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { useTradeStore } from './lib/store';
import { systemAPI } from './lib/api';
import DashboardScreen from './app/dashboard';
import StrategiesScreen from './app/strategies';
import PositionsScreen from './app/positions';

const Tab = createBottomTabNavigator();

const JournalScreen = () => (
  <SafeAreaView style={styles.container}>
    <ScrollView contentContainerStyle={styles.scrollContent}>
      <Text style={styles.title}>Trade Journal</Text>
      <ComingSoonPlaceholder />
    </ScrollView>
  </SafeAreaView>
);

const SettingsScreen = () => (
  <SafeAreaView style={styles.container}>
    <ScrollView contentContainerStyle={styles.scrollContent}>
      <Text style={styles.title}>Settings</Text>
      <ComingSoonPlaceholder />
    </ScrollView>
  </SafeAreaView>
);

const ComingSoonPlaceholder = () => (
  <View style={styles.placeholder}>
    <Text style={styles.placeholderText}>Coming Soon 🔜</Text>
    <Text style={styles.placeholderSubtext}>This feature is under development</Text>
  </View>
);

const TabIcon = ({ focused, name }) => {
  const icons = {
    Home: focused ? '📊' : '📉',
    Strategies: focused ? '⚡' : '🔧',
    Positions: focused ? '💼' : '📁',
    Journal: focused ? '📖' : '📝',
    Settings: focused ? '⚙️' : '🔨',
  };
  
  return <Text style={styles.tabIcon}>{icons[name]}</Text>;
};

export default function App() {
  const { setSystemEnabled } = useTradeStore();

  useEffect(() => {
    checkSystemStatus();
    const interval = setInterval(checkSystemStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const checkSystemStatus = async () => {
    try {
      const response = await systemAPI.status();
      setSystemEnabled(response.data.trading_enabled);
    } catch (error) {
      console.error('Failed to check system status:', error);
    }
  };

  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={{
          headerShown: false,
          tabBarStyle: {
            backgroundColor: '#0f172a',
            borderTopColor: '#1e293b',
            borderTopWidth: 1,
            paddingBottom: 8,
            paddingTop: 8,
          },
          tabBarActiveTintColor: '#10B981',
          tabBarInactiveTintColor: '#64748b',
          tabBarLabelStyle: {
            fontSize: 11,
            fontWeight: '500',
            marginTop: 4,
          },
        }}
      >
        <Tab.Screen
          name="Home"
          component={DashboardScreen}
          options={{
            tabBarIcon: ({ focused }) => <TabIcon focused={focused} name="Home" />,
            tabBarLabel: 'Dashboard',
          }}
        />
        <Tab.Screen
          name="Strategies"
          component={StrategiesScreen}
          options={{
            tabBarIcon: ({ focused }) => <TabIcon focused={focused} name="Strategies" />,
            tabBarLabel: 'Strategies',
          }}
        />
        <Tab.Screen
          name="Positions"
          component={PositionsScreen}
          options={{
            tabBarIcon: ({ focused }) => <TabIcon focused={focused} name="Positions" />,
            tabBarLabel: 'Positions',
          }}
        />
        <Tab.Screen
          name="Journal"
          component={JournalScreen}
          options={{
            tabBarIcon: ({ focused }) => <TabIcon focused={focused} name="Journal" />,
            tabBarLabel: 'Journal',
          }}
        />
        <Tab.Screen
          name="Settings"
          component={SettingsScreen}
          options={{
            tabBarIcon: ({ focused }) => <TabIcon focused={focused} name="Settings" />,
            tabBarLabel: 'Settings',
          }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a',
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingVertical: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 24,
  },
  placeholder: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 80,
    backgroundColor: '#1e293b',
    borderRadius: 12,
  },
  placeholderText: {
    fontSize: 24,
    color: '#cbd5e1',
    marginBottom: 8,
  },
  placeholderSubtext: {
    fontSize: 14,
    color: '#64748b',
  },
  tabIcon: {
    fontSize: 20,
  },
});
