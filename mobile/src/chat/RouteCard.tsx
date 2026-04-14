import React from "react";
import { Linking, Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import type { Route, RouteStop } from "../api/yardsailing";

interface Props {
  route: Route;
}

export function RouteCard({ route }: Props) {
  const openInMaps = () => {
    if (route.stops.length === 0) return;
    const url =
      Platform.OS === "ios"
        ? buildAppleMapsUrl(route.stops)
        : buildGoogleMapsUrl(route.stops);
    Linking.openURL(url);
  };

  return (
    <View style={styles.wrapper}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          Route · {route.stops.length} stops
        </Text>
        <Text style={styles.headerMeta}>
          {route.total_distance_miles.toFixed(1)} mi · {Math.round(route.total_duration_minutes)} min
        </Text>
      </View>
      <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
        {route.stops.map((stop, idx) => (
          <View key={stop.sale_id} style={styles.stop}>
            <View style={styles.stopNum}>
              <Text style={styles.stopNumText}>{idx + 1}</Text>
            </View>
            <View style={styles.stopBody}>
              <Text style={styles.stopTitle} numberOfLines={1}>{stop.title}</Text>
              <Text style={styles.stopAddr} numberOfLines={1}>{stop.address}</Text>
              <View style={styles.stopMetaRow}>
                <Text style={styles.stopEta}>ETA {Math.round(stop.eta_minutes)} min</Text>
                <View
                  style={[
                    styles.badge,
                    stop.in_window ? styles.badgeOk : styles.badgeLate,
                  ]}
                >
                  <Text
                    style={[
                      styles.badgeText,
                      stop.in_window ? styles.badgeOkText : styles.badgeLateText,
                    ]}
                  >
                    {stop.in_window ? "in window" : "late"}
                  </Text>
                </View>
              </View>
            </View>
          </View>
        ))}
      </ScrollView>
      <Pressable style={styles.button} onPress={openInMaps}>
        <Text style={styles.buttonText}>Open in Maps</Text>
      </Pressable>
    </View>
  );
}

function buildAppleMapsUrl(stops: RouteStop[]): string {
  const params = stops.map((s) => `daddr=${s.lat},${s.lng}`).join("&");
  return `http://maps.apple.com/?${params}`;
}

function buildGoogleMapsUrl(stops: RouteStop[]): string {
  const destination = stops[stops.length - 1];
  const waypoints = stops
    .slice(0, -1)
    .map((s) => `${s.lat},${s.lng}`)
    .join("|");
  const base = "https://www.google.com/maps/dir/?api=1";
  const dest = `&destination=${destination.lat},${destination.lng}`;
  const wp = waypoints ? `&waypoints=${encodeURIComponent(waypoints)}` : "";
  return `${base}${dest}${wp}`;
}

const styles = StyleSheet.create({
  wrapper: {
    marginHorizontal: 12,
    marginVertical: 6,
    backgroundColor: "#fff",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    overflow: "hidden",
  },
  header: {
    padding: 12,
    backgroundColor: "#f8fafc",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  headerTitle: { fontSize: 15, fontWeight: "700", color: "#0f172a" },
  headerMeta: { fontSize: 12, color: "#64748b", marginTop: 2 },
  list: { maxHeight: 320 },
  listContent: { padding: 8 },
  stop: { flexDirection: "row", padding: 8 },
  stopNum: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: "#2563eb",
    alignItems: "center", justifyContent: "center",
    marginRight: 10, marginTop: 2,
  },
  stopNumText: { color: "#fff", fontWeight: "700", fontSize: 13 },
  stopBody: { flex: 1 },
  stopTitle: { fontSize: 14, fontWeight: "700", color: "#0f172a" },
  stopAddr: { fontSize: 12, color: "#475569", marginTop: 1 },
  stopMetaRow: { flexDirection: "row", alignItems: "center", marginTop: 4 },
  stopEta: { fontSize: 12, color: "#334155", marginRight: 8 },
  badge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8 },
  badgeOk: { backgroundColor: "#dcfce7" },
  badgeLate: { backgroundColor: "#fef3c7" },
  badgeText: { fontSize: 11, fontWeight: "600" },
  badgeOkText: { color: "#166534" },
  badgeLateText: { color: "#92400e" },
  button: {
    backgroundColor: "#2563eb",
    padding: 12,
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontWeight: "700", fontSize: 14 },
});
