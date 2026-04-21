import "react-native-gesture-handler";
import React, { useEffect, useCallback } from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { AppState, AppStateStatus } from "react-native";

import { fetchCurrentUser } from "./src/api/auth";
import { listPlugins } from "./src/api/plugins";
import { clearToken, getToken } from "./src/auth/tokenStorage";
import { PluginOverlay } from "./src/plugins/PluginOverlay";
import { useAppStore } from "./src/store/useAppStore";
import { ChatScreen } from "./src/screens/ChatScreen";
import { HelpScreen } from "./src/screens/HelpScreen";
import { MapScreen } from "./src/screens/MapScreen";
import { SettingsScreen } from "./src/screens/SettingsScreen";
import { SkillsScreen } from "./src/screens/SkillsScreen";

const Tab = createBottomTabNavigator();

function useHydrateSession() {
  const setSession = useAppStore((s) => s.setSession);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      if (!token) return;

      try {
        const user = await fetchCurrentUser();
        setSession({ user, token });
      } catch (e) {
        // Treat any error as "token is invalid" — clear it and show signed-out UI.
        // Note: this is slightly pessimistic for network errors; Phase 3 may want
        // to distinguish 401 from network failures.
        await clearToken();
        setSession(null);
      }
    })();
  }, [setSession]);
}

function useHydratePlugins() {
  const setPlugins = useAppStore((s) => s.setPlugins);

  const refresh = useCallback(async () => {
    try {
      const plugins = await listPlugins();
      setPlugins(plugins);
      console.log("[App] loaded plugins:", plugins.map((p) => p.name));
    } catch (e) {
      console.log("[App] failed to load plugins:", (e as Error).message);
    }
  }, [setPlugins]);

  // Initial load on mount
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Refresh when app returns to foreground
  useEffect(() => {
    const sub = AppState.addEventListener("change", (state: AppStateStatus) => {
      if (state === "active") refresh();
    });
    return () => sub.remove();
  }, [refresh]);
}

export default function App() {
  useHydrateSession();
  useHydratePlugins();

  const plugins = useAppStore((s) => s.plugins);
  const pluginsLoaded = useAppStore((s) => s.pluginsLoaded);
  const hasMapPlugin = pluginsLoaded && plugins.some((p) => p.map?.component);

  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <Tab.Navigator
          screenOptions={{
            headerStyle: { backgroundColor: "#2563eb" },
            headerTintColor: "#fff",
            tabBarActiveTintColor: "#2563eb",
          }}
        >
          <Tab.Screen name="Jain" component={ChatScreen} />
          <Tab.Screen
            name="Map"
            component={MapScreen}
            options={hasMapPlugin ? undefined : { tabBarButton: () => null }}
          />
          <Tab.Screen name="Skills" component={SkillsScreen} />
          <Tab.Screen name="Help" component={HelpScreen} />
          <Tab.Screen name="Settings" component={SettingsScreen} />
        </Tab.Navigator>
        <PluginOverlay />
      </NavigationContainer>
      <StatusBar style="light" />
    </SafeAreaProvider>
  );
}
