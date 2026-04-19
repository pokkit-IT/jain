import React, { useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View,
} from "react-native";

import type { WithBridge } from "./bridge";

interface Child { id: string; name: string }

export function ExportSheet({ bridge }: WithBridge) {
  const [children, setChildren] = useState<Child[]>([]);
  const [childId, setChildId] = useState<string>("");
  const [fromDate, setFromDate] = useState(() => {
    const d = new Date(); d.setMonth(d.getMonth() - 1);
    return d.toISOString().slice(0, 10);
  });
  const [toDate, setToDate] = useState(new Date().toISOString().slice(0, 10));
  const [format, setFormat] = useState<"pdf" | "csv">("pdf");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    bridge.callPluginApi("/api/plugins/custody/children", "GET", null).then((list) => {
      const rows = list as Child[];
      setChildren(rows);
      if (rows[0]) setChildId(rows[0].id);
    });
  }, [bridge]);

  const doExport = async () => {
    if (!childId) return;
    setBusy(true);
    setStatus(null);
    try {
      const from = `${fromDate}T00:00:00`;
      const to = `${toDate}T23:59:59`;
      await bridge.callPluginApi(
        `/api/plugins/custody/export?child_id=${childId}`
        + `&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`
        + `&format=${format}`,
        "GET", null,
      );
      setStatus(`Export generated. Re-open from the same URL to download.`);
    } catch (e) {
      setStatus((e as Error).message || "Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Export custody log</Text>

      <Text style={styles.label}>Child</Text>
      <View style={styles.row}>
        {children.map((c) => (
          <Pressable
            key={c.id}
            style={[styles.chip, c.id === childId && styles.chipActive]}
            onPress={() => setChildId(c.id)}
          >
            <Text style={c.id === childId ? styles.chipTextActive : styles.chipText}>{c.name}</Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.label}>From (YYYY-MM-DD)</Text>
      <TextInput style={styles.input} value={fromDate} onChangeText={setFromDate} />
      <Text style={styles.label}>To (YYYY-MM-DD)</Text>
      <TextInput style={styles.input} value={toDate} onChangeText={setToDate} />

      <Text style={styles.label}>Format</Text>
      <View style={styles.row}>
        {(["pdf", "csv"] as const).map((f) => (
          <Pressable
            key={f} style={[styles.chip, format === f && styles.chipActive]}
            onPress={() => setFormat(f)}
          >
            <Text style={format === f ? styles.chipTextActive : styles.chipText}>
              {f.toUpperCase()}
            </Text>
          </Pressable>
        ))}
      </View>

      {status && <Text style={styles.status}>{status}</Text>}

      <View style={styles.btnRow}>
        <Pressable style={styles.cancelBtn} onPress={bridge.closeComponent}>
          <Text style={styles.cancelBtnText}>Close</Text>
        </Pressable>
        <Pressable style={styles.saveBtn} onPress={doExport} disabled={busy}>
          {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveBtnText}>Export</Text>}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
  label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
  row: { flexDirection: "row", flexWrap: "wrap" },
  chip: { paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: "#ddd", borderRadius: 14, marginRight: 6, marginBottom: 6 },
  chipActive: { backgroundColor: "#2a7", borderColor: "#2a7" },
  chipText: { color: "#444", fontSize: 12 },
  chipTextActive: { color: "#fff", fontSize: 12, fontWeight: "600" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 14 },
  status: { color: "#444", marginTop: 10 },
  btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
  cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
  cancelBtnText: { fontWeight: "600", color: "#444" },
  saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
  saveBtnText: { color: "#fff", fontWeight: "600" },
});
