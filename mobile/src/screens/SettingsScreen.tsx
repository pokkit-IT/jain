import React, { useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { apiClient } from "../api/client";
import { listPlugins } from "../api/plugins";
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
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.header}>Settings</Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}

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
