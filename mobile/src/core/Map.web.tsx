import React from "react";
import { StyleSheet, Text, View, ScrollView } from "react-native";

import { Sale } from "../types";

// Web stub for the native Map component. Renders a simple list of sales
// instead of an actual map — react-native-maps doesn't support web.
// On native (iOS/Android), Map.tsx is used instead.

export interface MapProps {
  region?: { latitude: number; longitude: number; latitudeDelta: number; longitudeDelta: number };
  sales: Sale[];
  onPinPress?: (sale: Sale) => void;
}

export function Map({ region, sales }: MapProps) {
  return (
    <View style={styles.container}>
      <View style={styles.banner}>
        <Text style={styles.bannerText}>
          Map view is mobile-only. Showing list view on web.
        </Text>
        {region ? (
          <Text style={styles.coords}>
            Centered at {region.latitude.toFixed(4)}, {region.longitude.toFixed(4)}
          </Text>
        ) : null}
      </View>
      <ScrollView style={styles.list}>
        {sales.length === 0 ? (
          <Text style={styles.empty}>No sales loaded yet. Ask Jain to find some.</Text>
        ) : (
          sales.map((sale) => (
            <View key={sale.id} style={styles.item}>
              <Text style={styles.title}>{sale.title}</Text>
              <Text style={styles.address}>{sale.address}</Text>
              {sale.description ? <Text style={styles.desc}>{sale.description}</Text> : null}
            </View>
          ))
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  banner: {
    backgroundColor: "#fef3c7",
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#fde68a",
  },
  bannerText: { fontSize: 14, fontWeight: "600", color: "#92400e" },
  coords: { fontSize: 12, color: "#92400e", marginTop: 4 },
  list: { flex: 1, padding: 12 },
  empty: { color: "#64748b", textAlign: "center", marginTop: 40 },
  item: {
    backgroundColor: "#fff",
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    marginBottom: 8,
  },
  title: { fontSize: 16, fontWeight: "600" },
  address: { fontSize: 13, color: "#64748b", marginTop: 2 },
  desc: { fontSize: 14, color: "#374151", marginTop: 6 },
});
