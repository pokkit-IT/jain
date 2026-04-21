import React from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import type { MapMarker } from "../types";

export interface MapProps {
  region?: { latitude: number; longitude: number; latitudeDelta: number; longitudeDelta: number };
  markers: MapMarker[];
  onMarkerPress?: (marker: MapMarker) => void;
  onLongPress?: (coord: { lat: number; lng: number }) => void;
}

export function Map({ region, markers, onMarkerPress }: MapProps) {
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
        {markers.length === 0 ? (
          <Text style={styles.empty}>No sales loaded yet. Ask Jain to find some.</Text>
        ) : (
          markers.map((marker) => (
            <Pressable
              key={marker.id}
              style={styles.item}
              onPress={() => onMarkerPress?.(marker)}
            >
              <Text style={styles.title}>{marker.title}</Text>
              <Text style={styles.address}>{marker.description}</Text>
            </Pressable>
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
});
