import React from "react";
import { StyleSheet, View, Text } from "react-native";
import MapView, { LongPressEvent, Marker, Region } from "react-native-maps";

import { Sale } from "../types";

export interface MapProps {
  region?: Region;
  sales: Sale[];
  onPinPress?: (sale: Sale) => void;
  onSightingPress?: (sale: Sale) => void;
  onLongPress?: (coord: { lat: number; lng: number }) => void;
}

function pinColor(sale: Sale): string {
  if (sale.source !== "sighting") return "#2563eb"; // blue
  return (sale.confirmations ?? 1) >= 2 ? "#16a34a" : "#f59e0b"; // green / orange
}

export function Map({
  region, sales, onPinPress, onSightingPress, onLongPress,
}: MapProps) {
  if (!region) {
    return (
      <View style={[styles.container, styles.empty]}>
        <Text>Waiting for location...</Text>
      </View>
    );
  }

  const handleLongPress = (e: LongPressEvent) => {
    const { latitude, longitude } = e.nativeEvent.coordinate;
    onLongPress?.({ lat: latitude, lng: longitude });
  };

  return (
    <MapView
      style={styles.container}
      initialRegion={region}
      onLongPress={handleLongPress}
    >
      {sales
        .filter((s): s is Sale & { lat: number; lng: number } => s.lat != null && s.lng != null)
        .map((sale) => (
          <Marker
            key={sale.id}
            coordinate={{ latitude: sale.lat, longitude: sale.lng }}
            title={sale.title}
            description={sale.address}
            pinColor={pinColor(sale)}
            onPress={() =>
              sale.source === "sighting"
                ? onSightingPress?.(sale)
                : onPinPress?.(sale)
            }
          />
        ))}
    </MapView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  empty: { alignItems: "center", justifyContent: "center" },
});
