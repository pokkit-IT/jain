import React, { useEffect, useState } from "react";
import {
  Alert,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { apiClient } from "../api/client";
import { listPlugins } from "../api/plugins";
import { signInWithGoogle } from "../api/auth";
import { useGoogleSignIn } from "../auth/googleAuth";
import { clearToken, setToken } from "../auth/tokenStorage";
import { useAppStore } from "../store/useAppStore";

interface Settings {
  mode: string;
  radius_miles: number;
  llm_provider: string;
  llm_model: string;
}

export function SettingsScreen() {
  const plugins = useAppStore((s) => s.plugins);
  const setPlugins = useAppStore((s) => s.setPlugins);
  const session = useAppStore((s) => s.session);
  const setSession = useAppStore((s) => s.setSession);

  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [signingIn, setSigningIn] = useState(false);

  const { signIn: googleSignIn, ready: googleReady } = useGoogleSignIn();

  useEffect(() => {
    (async () => {
      try {
        const [s, p] = await Promise.all([
          apiClient.get<Settings>("/api/settings"),
          listPlugins(),
        ]);
        setSettings(s.data);
        setPlugins(p);
      } catch (e) {
        setError((e as Error).message);
      }
    })();
  }, [setPlugins]);

  const handleSignIn = async () => {
    if (signingIn) return;
    setSigningIn(true);
    try {
      const idToken = await googleSignIn();
      if (!idToken) {
        // User cancelled or something went wrong with Google flow
        return;
      }
      const newSession = await signInWithGoogle(idToken);
      await setToken(newSession.token);
      setSession(newSession);
    } catch (e) {
      Alert.alert("Sign-in failed", (e as Error).message || "Try again later.");
    } finally {
      setSigningIn(false);
    }
  };

  const handleSignOut = async () => {
    await clearToken();
    setSession(null);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.header}>Settings</Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Account</Text>
        {session ? (
          <View>
            <View style={styles.profileRow}>
              {session.user.picture_url ? (
                <Image
                  source={{ uri: session.user.picture_url }}
                  style={styles.avatar}
                />
              ) : (
                <View style={[styles.avatar, styles.avatarFallback]}>
                  <Text style={styles.avatarInitial}>
                    {(session.user.name || "?").charAt(0).toUpperCase()}
                  </Text>
                </View>
              )}
              <View style={styles.profileText}>
                <Text style={styles.profileName}>{session.user.name}</Text>
                <Text style={styles.profileEmail}>{session.user.email}</Text>
              </View>
            </View>
            <TouchableOpacity style={styles.signOutButton} onPress={handleSignOut}>
              <Text style={styles.signOutText}>Sign out</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View>
            <Text style={styles.row}>Not signed in</Text>
            <TouchableOpacity
              style={[styles.signInButton, (!googleReady || signingIn) && styles.signInDisabled]}
              onPress={handleSignIn}
              disabled={!googleReady || signingIn}
            >
              <Text style={styles.signInText}>
                {signingIn ? "Signing in..." : "Sign in with Google"}
              </Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>LLM</Text>
        {settings ? (
          <>
            <Text style={styles.row}>Provider: {settings.llm_provider}</Text>
            <Text style={styles.row}>Model: {settings.llm_model}</Text>
            <Text style={styles.row}>Mode: {settings.mode}</Text>
          </>
        ) : (
          <Text style={styles.row}>Loading...</Text>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Installed Plugins</Text>
        {plugins.map((p) => (
          <View key={p.name} style={styles.plugin}>
            <Text style={styles.pluginName}>
              {p.name} v{p.version}
            </Text>
            <Text style={styles.pluginDesc}>{p.description}</Text>
            <Text style={styles.pluginSkills}>
              Skills: {p.skills.map((s) => s.name).join(", ")}
            </Text>
          </View>
        ))}
        {plugins.length === 0 ? <Text style={styles.row}>No plugins installed</Text> : null}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  content: { padding: 16 },
  header: { fontSize: 28, fontWeight: "700", marginBottom: 16 },
  error: { color: "#b91c1c", marginBottom: 12 },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 18, fontWeight: "600", marginBottom: 8 },
  row: { fontSize: 14, color: "#374151", paddingVertical: 2 },

  profileRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    marginRight: 12,
  },
  avatarFallback: {
    backgroundColor: "#2563eb",
    alignItems: "center",
    justifyContent: "center",
  },
  avatarInitial: { color: "#fff", fontSize: 20, fontWeight: "600" },
  profileText: { flex: 1 },
  profileName: { fontSize: 16, fontWeight: "600", color: "#1f2937" },
  profileEmail: { fontSize: 13, color: "#64748b", marginTop: 2 },
  signOutButton: {
    marginTop: 12,
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    alignItems: "center",
  },
  signOutText: { color: "#b91c1c", fontWeight: "600" },

  signInButton: {
    marginTop: 8,
    padding: 14,
    borderRadius: 10,
    backgroundColor: "#2563eb",
    alignItems: "center",
  },
  signInDisabled: { backgroundColor: "#94a3b8" },
  signInText: { color: "#fff", fontSize: 16, fontWeight: "600" },

  plugin: {
    backgroundColor: "#fff",
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    marginBottom: 8,
  },
  pluginName: { fontSize: 16, fontWeight: "600" },
  pluginDesc: { fontSize: 14, color: "#64748b", marginTop: 2 },
  pluginSkills: { fontSize: 12, color: "#94a3b8", marginTop: 4 },
});
