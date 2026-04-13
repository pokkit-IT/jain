import React from "react";
import { StyleSheet, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import { fetchRecentSales } from "../api/yardsailing";
import { Map } from "../core/Map";
import { useLocation } from "../hooks/useLocation";
import { useAppStore } from "../store/useAppStore";

export function MapScreen() {
  const location = useLocation();
  const sales = useAppStore((s) => s.sales);
  const setSales = useAppStore((s) => s.setSales);

  useFocusEffect(
    React.useCallback(() => {
      let cancelled = false;
      fetchRecentSales()
        .then((fresh) => {
          if (!cancelled) setSales(fresh);
        })
        .catch((e) => {
          // eslint-disable-next-line no-console
          console.log("[MapScreen] fetchRecentSales failed:", e);
        });
      return () => {
        cancelled = true;
      };
    }, [setSales]),
  );

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
