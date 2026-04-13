import React from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import { fetchRecentSales } from "../api/yardsailing";
import { Map } from "../core/Map";
import { SaleDetailsModal } from "../core/SaleDetailsModal";
import { useLocation } from "../hooks/useLocation";
import { useAppStore } from "../store/useAppStore";
import type { Sale } from "../types";

export function MapScreen() {
  const location = useLocation();
  const sales = useAppStore((s) => s.sales);
  const setSales = useAppStore((s) => s.setSales);
  const [selected, setSelected] = React.useState<Sale | null>(null);
  const [loading, setLoading] = React.useState(false);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    try {
      const fresh = await fetchRecentSales();
      setSales(fresh);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.log("[MapScreen] fetchRecentSales failed:", e);
    } finally {
      setLoading(false);
    }
  }, [setSales]);

  useFocusEffect(
    React.useCallback(() => {
      refresh();
    }, [refresh]),
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
      <Map region={region} sales={sales} onPinPress={setSelected} />
      <Pressable
        accessibilityLabel="Refresh sales"
        style={styles.fab}
        onPress={refresh}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.fabText}>↻</Text>
        )}
      </Pressable>
      <SaleDetailsModal sale={selected} onClose={() => setSelected(null)} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  fab: {
    position: "absolute",
    right: 16,
    bottom: 24,
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: "#2563eb",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOpacity: 0.2,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 4,
  },
  fabText: { color: "#fff", fontSize: 24, lineHeight: 26, fontWeight: "700" },
});
