import React from "react";
import {
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import Ionicons from "@expo/vector-icons/Ionicons";
import { useNavigation } from "@react-navigation/native";

import { PluginHost } from "../plugins/PluginHost";
import { useAppStore } from "../store/useAppStore";
import type { PluginSummary } from "../types";

interface SelectedSkill {
  pluginName: string;
  componentName: string;
  label: string;
}

export function SkillsScreen() {
  const plugins = useAppStore((s) => s.plugins);
  const [selected, setSelected] = React.useState<SelectedSkill | null>(null);
  const navigation = useNavigation<any>();

  const withHome = plugins.filter(
    (p): p is PluginSummary & { home: NonNullable<PluginSummary["home"]> } =>
      !!p.home,
  );

  if (selected) {
    return (
      <View style={styles.container}>
        <View style={styles.topBar}>
          <Pressable onPress={() => setSelected(null)} hitSlop={8}>
            <Text style={styles.back}>‹ Skills</Text>
          </Pressable>
          <Text style={styles.topLabel}>{selected.label}</Text>
          <View style={{ width: 60 }} />
        </View>
        <PluginHost
          pluginName={selected.pluginName}
          componentName={selected.componentName}
          navigate={(tab) => navigation.navigate(tab as never)}
        />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={withHome}
        keyExtractor={(p) => p.name}
        contentContainerStyle={
          withHome.length === 0 ? styles.empty : styles.list
        }
        ListEmptyComponent={
          <Text style={styles.emptyText}>
            No skills available yet.
          </Text>
        }
        renderItem={({ item }) => (
          <Pressable
            style={styles.row}
            onPress={() =>
              setSelected({
                pluginName: item.name,
                componentName: item.home.component,
                label: item.home.label,
              })
            }
          >
            <Ionicons
              // Cast is safe: Ionicons accepts any glyph name and warns in dev if
              // unknown. PluginHome.icon is a free-form string from plugin.json.
              name={(item.home.icon ?? "apps-outline") as React.ComponentProps<typeof Ionicons>["name"]}
              size={28}
              color="#475569"
              style={styles.icon}
            />
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{item.home.label}</Text>
              <Text style={styles.rowDesc} numberOfLines={2}>
                {item.home.description ?? item.description}
              </Text>
            </View>
            <Text style={styles.chev}>›</Text>
          </Pressable>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  back: { color: "#2563eb", fontSize: 15, fontWeight: "600" },
  topLabel: { fontSize: 15, fontWeight: "700", color: "#0f172a" },
  list: { padding: 12 },
  empty: {
    flexGrow: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  emptyText: { color: "#64748b", fontSize: 15, textAlign: "center" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    padding: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    marginBottom: 10,
  },
  rowTitle: { fontSize: 16, fontWeight: "700", marginBottom: 2 },
  rowDesc: { fontSize: 13, color: "#64748b" },
  icon: { marginRight: 12 },
  chev: { fontSize: 24, color: "#94a3b8", marginLeft: 8 },
});
