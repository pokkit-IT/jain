import React, { useEffect, useState } from "react";
import {
  ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View,
} from "react-native";

import type { WithBridge } from "./bridge";

interface Schedule {
  id: string; child_id: string; name: string; active: boolean;
  start_date: string; interval_weeks: number; weekdays: string;
  pickup_time: string; dropoff_time: string;
}

export function ScheduleListScreen({ bridge }: WithBridge) {
  const [rows, setRows] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const data = (await bridge.callPluginApi(
      "/api/plugins/custody/schedules", "GET", null,
    )) as Schedule[];
    setRows(data);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  if (loading) return <ActivityIndicator style={{ marginTop: 40 }} />;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Schedules</Text>
      <FlatList
        data={rows} keyExtractor={(r) => r.id}
        renderItem={({ item }) => (
          <Pressable
            style={styles.row}
            onPress={() => bridge.openComponent?.("ScheduleForm", { scheduleId: item.id })}
          >
            <Text style={styles.name}>{item.name}</Text>
            <Text style={styles.sub}>
              Every {item.interval_weeks}w · days {item.weekdays} ·
              {" "}{item.pickup_time}→{item.dropoff_time}
            </Text>
          </Pressable>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No schedules yet.</Text>}
      />
      <Pressable
        style={styles.primary}
        onPress={() => bridge.openComponent?.("ScheduleForm")}
      >
        <Text style={styles.primaryText}>+ Add schedule</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
  row: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#f0f0f0" },
  name: { fontSize: 15, fontWeight: "600" },
  sub: { fontSize: 12, color: "#666" },
  empty: { color: "#888", padding: 20, textAlign: "center" },
  primary: { backgroundColor: "#2a7", padding: 12, borderRadius: 6, alignItems: "center", marginTop: 12 },
  primaryText: { color: "#fff", fontWeight: "600" },
});
