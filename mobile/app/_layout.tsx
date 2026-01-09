import { Tabs } from "expo-router";
import { Text } from "react-native";

const TabIcon = ({ focused, name }: { focused: boolean; name: string }) => {
  const icons: Record<string, string> = {
    index: focused ? "📊" : "📉",
    strategies: focused ? "⚡" : "🔧",
    positions: focused ? "💼" : "📁",
    journal: focused ? "📖" : "📝",
    settings: focused ? "⚙️" : "🔨",
  };

  return <Text style={{ fontSize: 20 }}>{icons[name]}</Text>;
};

export default function Layout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: "#0f172a",
          borderTopColor: "#1e293b",
        },
        tabBarActiveTintColor: "#10B981",
        tabBarInactiveTintColor: "#64748b",
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Dashboard",
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} name="index" />
          ),
        }}
      />
      <Tabs.Screen
        name="strategies"
        options={{
          title: "Strategies",
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} name="strategies" />
          ),
        }}
      />
      <Tabs.Screen
        name="positions"
        options={{
          title: "Positions",
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} name="positions" />
          ),
        }}
      />
      <Tabs.Screen
        name="journal"
        options={{
          title: "Journal",
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} name="journal" />
          ),
        }}
      />
      <Tabs.Screen
        name="backtest"
        options={{
          title: "Backtest",
          tabBarIcon: ({ focused }) => (
            <Text style={{ fontSize: 20 }}>{focused ? "🧪" : "🔬"}</Text>
          ),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: "Settings",
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} name="settings" />
          ),
        }}
      />
    </Tabs>
  );
}
