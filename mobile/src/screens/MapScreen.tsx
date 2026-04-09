import React from "react";
import { StyleSheet, View } from "react-native";

import { Map } from "../core/Map";
import { useLocation } from "../hooks/useLocation";
import { useAppStore } from "../store/useAppStore";

export function MapScreen() {
  const location = useLocation();
  const sales = useAppStore((s) => s.sales);

  const region = location
    ? {
        latitude: location.lat,
        longitude: location.lng,
        latitudeDelta: 0.1,
        longitudeDelta: 0.1,
      }
    : undefined;

  return (
    <View style={styles.container}>
      <Map region={region} sales={sales} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
});
