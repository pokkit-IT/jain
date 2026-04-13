import React from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  ActivityIndicator,
} from "react-native";
import { useFocusEffect, useNavigation } from "@react-navigation/native";

import { fetchPluginHelp, PluginHelp } from "../api/help";
import { SimpleMarkdown } from "../core/SimpleMarkdown";
import { useAppStore } from "../store/useAppStore";

export function HelpScreen() {
  const navigation = useNavigation<any>();
  const [plugins, setPlugins] = React.useState<PluginHelp[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setError(null);
    try {
      setPlugins(await fetchPluginHelp());
    } catch (e) {
      setError((e as Error).message || "Failed to load help.");
    }
  }, []);

  useFocusEffect(
    React.useCallback(() => {
      load();
    }, [load]),
  );

  const tryExample = (prompt: string) => {
    useAppStore.getState().setPendingPrompt(prompt);
    navigation.navigate("Jain");
  };

  if (plugins === null && !error) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  if (!plugins || plugins.length === 0) {
    return (
      <View style={styles.center}>
        <Text style={styles.muted}>No plugins installed.</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {plugins.map((p) => (
        <View key={p.name} style={styles.section}>
          <Text style={styles.pluginName}>{p.name}</Text>
          <Text style={styles.pluginVersion}>v{p.version}</Text>
          <Text style={styles.pluginDesc}>{p.description}</Text>

          {p.examples.length > 0 ? (
            <View style={styles.examples}>
              <Text style={styles.examplesTitle}>Try an example</Text>
              <View style={styles.chips}>
                {p.examples.map((ex, i) => (
                  <Pressable
                    key={i}
                    style={styles.chip}
                    onPress={() => tryExample(ex.prompt)}
                  >
                    <Text style={styles.chipText}>{ex.prompt}</Text>
                    {ex.description ? (
                      <Text style={styles.chipDesc}>{ex.description}</Text>
                    ) : null}
                  </Pressable>
                ))}
              </View>
            </View>
          ) : null}

          {p.help_markdown ? (
            <View style={styles.md}>
              <SimpleMarkdown source={p.help_markdown} />
            </View>
          ) : (
            <Text style={styles.muted}>No detailed help for this plugin yet.</Text>
          )}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  content: { padding: 16 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  errorText: { color: "#b91c1c" },
  muted: { color: "#64748b", fontSize: 14 },

  section: {
    backgroundColor: "#fff",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    padding: 16,
    marginBottom: 14,
  },
  pluginName: { fontSize: 20, fontWeight: "700", color: "#0f172a" },
  pluginVersion: { fontSize: 12, color: "#94a3b8", marginTop: 2 },
  pluginDesc: { fontSize: 14, color: "#475569", marginTop: 6 },

  examples: { marginTop: 14 },
  examplesTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#64748b",
    textTransform: "uppercase",
    marginBottom: 8,
  },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    backgroundColor: "#eff6ff",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: "#bfdbfe",
    maxWidth: "100%",
  },
  chipText: { fontSize: 14, fontWeight: "600", color: "#1d4ed8" },
  chipDesc: { fontSize: 12, color: "#60a5fa", marginTop: 2 },

  md: {
    marginTop: 14,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: "#f1f5f9",
  },
});
