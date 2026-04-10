import "react-native-gesture-handler";
import React, { useEffect } from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";

import { fetchCurrentUser } from "./src/api/auth";
import { clearToken, getToken } from "./src/auth/tokenStorage";
import { useAppStore } from "./src/store/useAppStore";
import { ChatScreen } from "./src/screens/ChatScreen";
import { MapScreen } from "./src/screens/MapScreen";
import { SettingsScreen } from "./src/screens/SettingsScreen";

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

export default function App() {
  useHydrateSession();

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
          <Tab.Screen name="Map" component={MapScreen} />
          <Tab.Screen name="Settings" component={SettingsScreen} />
        </Tab.Navigator>
      </NavigationContainer>
      <StatusBar style="light" />
    </SafeAreaProvider>
  );
}
