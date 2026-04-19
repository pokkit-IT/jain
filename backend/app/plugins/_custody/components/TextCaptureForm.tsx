import React, { useState } from "react";
import {
  ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View,
} from "react-native";

import type { WithBridge } from "./bridge";

interface TextCaptureFormProps extends WithBridge {
  childId: string;
}

export function TextCaptureForm({ bridge, childId }: TextCaptureFormProps) {
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await bridge.callPluginApi("/api/plugins/custody/events", "POST", {
        child_id: childId, type: "text_screenshot",
        occurred_at: new Date().toISOString(),
        notes: note.trim() || null,
      });
      bridge.showToast("Text event logged — attach screenshots from timeline");
      bridge.closeComponent();
    } catch (e) {
      setError((e as Error).message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Log text from other parent</Text>
      <Text style={styles.hint}>
        Save this event, then tap it in the timeline to attach a screenshot.
      </Text>
      <Text style={styles.label}>Note (optional)</Text>
      <TextInput
        style={[styles.input, { height: 80 }]} multiline
        placeholder="e.g. refused my Sunday pickup window"
        value={note} onChangeText={setNote}
      />
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
  title: { fontSize: 18, fontWeight: "700", marginBottom: 4 },
  hint: { color: "#888", fontSize: 12, marginBottom: 14 },
  label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 16, textAlignVertical: "top" },
  error: { color: "#c22", marginTop: 8 },
  btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
  cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
  cancelBtnText: { fontWeight: "600", color: "#444" },
  saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
  saveBtnText: { color: "#fff", fontWeight: "600" },
});
