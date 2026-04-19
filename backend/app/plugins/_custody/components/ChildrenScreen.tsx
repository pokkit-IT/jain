import React, { useEffect, useState } from "react";
import {
  ActivityIndicator, Alert, FlatList, Pressable,
  StyleSheet, Text, TextInput, View,
} from "react-native";

import type { WithBridge } from "./bridge";

interface Child { id: string; name: string; dob?: string | null }

export function ChildrenScreen({ bridge }: WithBridge) {
  const [children, setChildren] = useState<Child[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");

  const load = async () => {
    setLoading(true);
    const rows = (await bridge.callPluginApi(
      "/api/plugins/custody/children", "GET", null,
    )) as Child[];
    setChildren(rows);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!name.trim()) return;
    await bridge.callPluginApi("/api/plugins/custody/children", "POST", {
      name: name.trim(), dob: dob.trim() || null,
    });
    setName(""); setDob("");
    bridge.showToast("Added");
    load();
  };

  const remove = async (c: Child) => {
    Alert.alert("Delete child?", `All events for ${c.name} will be deleted.`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete", style: "destructive",
        onPress: async () => {
          await bridge.callPluginApi(`/api/plugins/custody/children/${c.id}`, "DELETE", null);
          load();
        },
      },
    ]);
  };

  if (loading) return <ActivityIndicator style={{ marginTop: 40 }} />;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Children</Text>
      <FlatList
        data={children} keyExtractor={(c) => c.id}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{item.name}</Text>
              {item.dob && <Text style={styles.dob}>DOB {item.dob}</Text>}
            </View>
            <Pressable onPress={() => remove(item)}>
              <Text style={{ color: "#c22" }}>Delete</Text>
            </Pressable>
          </View>
        )}
      />
      <Text style={styles.label}>Add a child</Text>
      <TextInput style={styles.input} placeholder="Name" value={name} onChangeText={setName} />
      <TextInput style={styles.input} placeholder="DOB (YYYY-MM-DD, optional)" value={dob} onChangeText={setDob} />
      <Pressable style={styles.primary} onPress={add}>
        <Text style={styles.primaryText}>Add</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
  row: { flexDirection: "row", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#f0f0f0" },
  name: { fontSize: 16 },
  dob: { fontSize: 12, color: "#666" },
  label: { fontSize: 12, color: "#666", marginTop: 16, marginBottom: 6, letterSpacing: 0.5, textTransform: "uppercase" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, marginBottom: 8 },
  primary: { backgroundColor: "#2a7", padding: 12, borderRadius: 6, alignItems: "center", marginTop: 4 },
  primaryText: { color: "#fff", fontWeight: "600" },
});
