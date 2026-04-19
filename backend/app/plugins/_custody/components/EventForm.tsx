import React, { useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, StyleSheet, Switch, Text, TextInput, View,
} from "react-native";

import type { WithBridge } from "./bridge";

type EventType = "activity" | "note" | "medical" | "school" | "phone_call" | "missed_visit" | "pickup" | "dropoff";

// Props are received via PluginOverlay's { initialData: ... } wrapping,
// matching the convention used by SaleForm and other overlay-opened forms.
interface EventFormInitialData {
  childId?: string;
  type?: EventType;
  eventId?: string;
  mode?: "create" | "edit";
}

interface EventFormProps extends WithBridge {
  initialData?: EventFormInitialData;
}

interface EventRow {
  id: string; child_id: string; type: EventType;
  occurred_at: string;
  notes?: string | null; location?: string | null;
  overnight?: boolean; call_connected?: boolean | null;
}

export function EventForm({ bridge, initialData }: EventFormProps) {
  const { childId, type = "note", eventId, mode = "create" } = initialData ?? {};
  const [effectiveType, setEffectiveType] = useState<EventType>(type);
  const [occurredAt, setOccurredAt] = useState<string>(() => new Date().toISOString());
  const [notes, setNotes] = useState("");
  const [location, setLocation] = useState("");
  const [overnight, setOvernight] = useState(false);
  const [callConnected, setCallConnected] = useState<boolean>(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(mode === "create");

  useEffect(() => {
    if (mode !== "edit" || !eventId) return;
    bridge
      .callPluginApi(`/api/plugins/custody/events/${eventId}`, "GET", null)
      .catch(async () => {
        const list = (await bridge.callPluginApi(
          `/api/plugins/custody/events?limit=500`, "GET", null,
        )) as EventRow[];
        return list.find((x) => x.id === eventId);
      })
      .then((evt) => {
        if (!evt) return;
        const e = evt as EventRow;
        setEffectiveType(e.type);
        setOccurredAt(e.occurred_at);
        setNotes(e.notes || "");
        setLocation(e.location || "");
        setOvernight(!!e.overnight);
        setCallConnected(e.call_connected ?? true);
      })
      .finally(() => setLoaded(true));
  }, [bridge, eventId, mode]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      if (mode === "edit" && eventId) {
        await bridge.callPluginApi(`/api/plugins/custody/events/${eventId}`, "PATCH", {
          notes: notes || null,
          location: location || null,
          ...(effectiveType === "pickup" ? { overnight } : {}),
          ...(effectiveType === "phone_call" ? { call_connected: callConnected } : {}),
          occurred_at: occurredAt,
        });
      } else {
        if (!childId) { setError("Missing child id."); setSaving(false); return; }
        await bridge.callPluginApi("/api/plugins/custody/events", "POST", {
          child_id: childId, type: effectiveType,
          occurred_at: occurredAt,
          notes: notes || null,
          location: location || null,
          overnight: effectiveType === "pickup" ? overnight : false,
          call_connected: effectiveType === "phone_call" ? callConnected : null,
        });
      }
      bridge.showToast("Saved");
      bridge.closeComponent();
    } catch (e) {
      setError((e as Error).message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!eventId) return;
    setDeleting(true);
    try {
      await bridge.callPluginApi(`/api/plugins/custody/events/${eventId}`, "DELETE", null);
      bridge.showToast("Deleted");
      bridge.closeComponent();
    } catch (e) {
      setError((e as Error).message || "Failed to delete");
    } finally {
      setDeleting(false);
    }
  };

  if (!loaded) return <ActivityIndicator style={{ marginTop: 40 }} />;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>
        {mode === "edit" ? "Edit event" : `Log ${effectiveType.replace("_", " ")}`}
      </Text>
      <Text style={styles.label}>When (ISO)</Text>
      <TextInput style={styles.input} value={occurredAt} onChangeText={setOccurredAt} />

      <Text style={styles.label}>Notes</Text>
      <TextInput
        style={[styles.input, { height: 70 }]} multiline
        value={notes} onChangeText={setNotes}
      />

      <Text style={styles.label}>Location</Text>
      <TextInput style={styles.input} value={location} onChangeText={setLocation} />

      {effectiveType === "pickup" && (
        <View style={styles.switchRow}>
          <Text style={styles.label}>Overnight visit</Text>
          <Switch value={overnight} onValueChange={setOvernight} />
        </View>
      )}
      {effectiveType === "phone_call" && (
        <View style={styles.switchRow}>
          <Text style={styles.label}>Call connected</Text>
          <Switch value={callConnected} onValueChange={setCallConnected} />
        </View>
      )}

      {error && <Text style={styles.error}>{error}</Text>}

      <View style={styles.btnRow}>
        <Pressable style={styles.cancelBtn} onPress={bridge.closeComponent}>
          <Text style={styles.cancelBtnText}>Cancel</Text>
        </Pressable>
        <Pressable style={styles.saveBtn} onPress={save} disabled={saving}>
          {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveBtnText}>Save</Text>}
        </Pressable>
      </View>

      {mode === "edit" && (
        <Pressable style={styles.deleteBtn} onPress={remove} disabled={deleting}>
          <Text style={styles.deleteBtnText}>{deleting ? "Deleting..." : "Delete event"}</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
  label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 14 },
  switchRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 10 },
  error: { color: "#c22", marginTop: 10 },
  btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
  cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
  cancelBtnText: { fontWeight: "600", color: "#444" },
  saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
  saveBtnText: { color: "#fff", fontWeight: "600" },
  deleteBtn: { marginTop: 20, padding: 10, alignItems: "center" },
  deleteBtnText: { color: "#c22", fontWeight: "600" },
});
