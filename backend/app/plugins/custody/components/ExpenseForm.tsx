import React, { useState } from "react";
import {
  ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View,
} from "react-native";

import type { WithBridge } from "./bridge";

const CATEGORIES = ["food", "activity", "clothing", "school", "medical", "other"] as const;
type Category = typeof CATEGORIES[number];

interface ExpenseFormProps extends WithBridge {
  childId: string;
}

export function ExpenseForm({ bridge, childId }: ExpenseFormProps) {
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<Category>("activity");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    const parsed = parseFloat(amount);
    if (Number.isNaN(parsed) || parsed <= 0) {
      setError("Enter a dollar amount.");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await bridge.callPluginApi("/api/plugins/custody/events", "POST", {
        child_id: childId, type: "expense",
        occurred_at: new Date().toISOString(),
        amount_cents: Math.round(parsed * 100),
        category,
        notes: description.trim() || null,
      });
      bridge.showToast(`$${parsed.toFixed(2)} logged`);
      bridge.closeComponent();
    } catch (e) {
      setError((e as Error).message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Log expense</Text>
      <Text style={styles.label}>Amount (USD)</Text>
      <TextInput
        style={styles.input} keyboardType="decimal-pad"
        placeholder="42.50" value={amount} onChangeText={setAmount}
      />
      <Text style={styles.label}>Description</Text>
      <TextInput
        style={styles.input} placeholder="bowling"
        value={description} onChangeText={setDescription}
      />
      <Text style={styles.label}>Category</Text>
      <View style={styles.chipsRow}>
        {CATEGORIES.map((c) => (
          <Pressable
            key={c}
            style={[styles.chip, category === c && styles.chipActive]}
            onPress={() => setCategory(c)}
          >
            <Text style={category === c ? styles.chipTextActive : styles.chipText}>{c}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={styles.hint}>
        Tip: Save now, then tap the saved expense in the timeline to attach a receipt photo.
      </Text>
      {error && <Text style={styles.error}>{error}</Text>}
      <View style={styles.btnRow}>
        <Pressable style={styles.cancelBtn} onPress={bridge.closeComponent}>
          <Text style={styles.cancelBtnText}>Cancel</Text>
        </Pressable>
        <Pressable style={styles.saveBtn} onPress={save} disabled={saving}>
          {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveBtnText}>Save</Text>}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
  label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 16 },
  chipsRow: { flexDirection: "row", flexWrap: "wrap", marginTop: 4 },
  chip: { paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: "#ddd", borderRadius: 14, marginRight: 6, marginBottom: 6 },
  chipActive: { backgroundColor: "#2a7", borderColor: "#2a7" },
  chipText: { color: "#444", fontSize: 12 },
  chipTextActive: { color: "#fff", fontSize: 12, fontWeight: "600" },
  hint: { marginTop: 10, color: "#888", fontSize: 12 },
  error: { color: "#c22", marginTop: 8 },
  btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
  cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
  cancelBtnText: { fontWeight: "600", color: "#444" },
  saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
  saveBtnText: { color: "#fff", fontWeight: "600" },
});
