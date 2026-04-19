import React, { useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View,
} from "react-native";

import type { WithBridge } from "./bridge";

interface Child { id: string; name: string }

const DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"];

interface ScheduleFormProps extends WithBridge {
  scheduleId?: string;
}

export function ScheduleForm({ bridge, scheduleId }: ScheduleFormProps) {
  const [children, setChildren] = useState<Child[]>([]);
  const [childId, setChildId] = useState<string>("");
  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState(new Date().toISOString().slice(0, 10));
  const [intervalWeeks, setIntervalWeeks] = useState("1");
  const [weekdaySet, setWeekdaySet] = useState<Set<number>>(new Set([4]));
  const [pickupTime, setPickupTime] = useState("17:00");
  const [dropoffTime, setDropoffTime] = useState("19:00");
  const [pickupLocation, setPickupLocation] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(!scheduleId);

  useEffect(() => {
    bridge.callPluginApi("/api/plugins/custody/children", "GET", null).then((list) => {
      const rows = list as Child[];
      setChildren(rows);
      if (rows[0] && !childId) setChildId(rows[0].id);
    });
  }, [bridge]);

  useEffect(() => {
    if (!scheduleId) return;
    bridge.callPluginApi(
      "/api/plugins/custody/schedules", "GET", null,
    ).then((list) => {
      const found = (list as Array<{
        id: string; child_id: string; name: string; start_date: string;
        interval_weeks: number; weekdays: string;
        pickup_time: string; dropoff_time: string; pickup_location?: string;
      }>).find((s) => s.id === scheduleId);
      if (found) {
        setChildId(found.child_id);
        setName(found.name);
        setStartDate(found.start_date);
        setIntervalWeeks(String(found.interval_weeks));
        setWeekdaySet(new Set(found.weekdays.split(",").map(Number)));
        setPickupTime(found.pickup_time);
        setDropoffTime(found.dropoff_time);
        setPickupLocation(found.pickup_location || "");
      }
    }).finally(() => setLoaded(true));
  }, [bridge, scheduleId]);

  const toggleDay = (i: number) => {
    const next = new Set(weekdaySet);
    next.has(i) ? next.delete(i) : next.add(i);
    setWeekdaySet(next);
  };

  const save = async () => {
    if (!childId) { setError("Pick a child first"); return; }
    if (weekdaySet.size === 0) { setError("Pick at least one weekday"); return; }
    setSaving(true);
    setError(null);
    const payload = {
      child_id: childId, name: name.trim() || "Schedule",
      start_date: startDate,
      interval_weeks: Math.max(1, parseInt(intervalWeeks, 10) || 1),
      weekdays: Array.from(weekdaySet).sort().join(","),
      pickup_time: pickupTime, dropoff_time: dropoffTime,
      pickup_location: pickupLocation.trim() || null,
    };
    try {
      if (scheduleId) {
        await bridge.callPluginApi(
          `/api/plugins/custody/schedules/${scheduleId}`, "PATCH", payload,
        );
      } else {
        await bridge.callPluginApi("/api/plugins/custody/schedules", "POST", payload);
      }
      bridge.showToast("Saved");
      bridge.closeComponent();
    } catch (e) {
      setError((e as Error).message || "Failed");
    } finally {
      setSaving(false);
    }
  };

  if (!loaded) return <ActivityIndicator style={{ marginTop: 40 }} />;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{scheduleId ? "Edit schedule" : "New schedule"}</Text>

      <Text style={styles.label}>Child</Text>
      <View style={styles.row}>
        {children.map((c) => (
          <Pressable
            key={c.id}
            style={[styles.chip, c.id === childId && styles.chipActive]}
            onPress={() => setChildId(c.id)}
          >
            <Text style={c.id === childId ? styles.chipTextActive : styles.chipText}>
              {c.name}
            </Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.label}>Name</Text>
      <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="EOW Fri-Sun" />

      <Text style={styles.label}>Start date (YYYY-MM-DD)</Text>
      <TextInput style={styles.input} value={startDate} onChangeText={setStartDate} />

      <Text style={styles.label}>Interval (weeks)</Text>
      <TextInput
        style={styles.input} keyboardType="numeric"
        value={intervalWeeks} onChangeText={setIntervalWeeks}
      />

      <Text style={styles.label}>Weekdays</Text>
      <View style={styles.row}>
        {DAY_LABELS.map((lbl, i) => (
          <Pressable
            key={i} style={[styles.dayBtn, weekdaySet.has(i) && styles.dayBtnOn]}
            onPress={() => toggleDay(i)}
          >
            <Text style={weekdaySet.has(i) ? styles.dayTextOn : styles.dayText}>{lbl}</Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.label}>Pickup (HH:MM)</Text>
      <TextInput style={styles.input} value={pickupTime} onChangeText={setPickupTime} />

      <Text style={styles.label}>Dropoff (HH:MM)</Text>
      <TextInput style={styles.input} value={dropoffTime} onChangeText={setDropoffTime} />

      <Text style={styles.label}>Pickup location (optional)</Text>
      <TextInput style={styles.input} value={pickupLocation} onChangeText={setPickupLocation} />

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
  row: { flexDirection: "row", flexWrap: "wrap" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 14 },
  chip: { paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: "#ddd", borderRadius: 14, marginRight: 6, marginBottom: 6 },
  chipActive: { backgroundColor: "#2a7", borderColor: "#2a7" },
  chipText: { color: "#444", fontSize: 12 },
  chipTextActive: { color: "#fff", fontSize: 12, fontWeight: "600" },
  dayBtn: { width: 36, height: 36, borderRadius: 18, borderWidth: 1, borderColor: "#ddd", alignItems: "center", justifyContent: "center", marginRight: 6 },
  dayBtnOn: { backgroundColor: "#2a7", borderColor: "#2a7" },
  dayText: { color: "#444" },
  dayTextOn: { color: "#fff", fontWeight: "600" },
  error: { color: "#c22", marginTop: 8 },
  btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
  cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
  cancelBtnText: { fontWeight: "600", color: "#444" },
  saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
  saveBtnText: { color: "#fff", fontWeight: "600" },
});
