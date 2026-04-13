import React from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import { fetchCuratedTags, fetchRecentSales } from "../api/yardsailing";
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
  const [availableTags, setAvailableTags] = React.useState<string[]>([]);
  const [activeTags, setActiveTags] = React.useState<string[]>([]);
  const [happeningNow, setHappeningNow] = React.useState(false);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    try {
      const fresh = await fetchRecentSales({
        tags: activeTags,
        happeningNow,
      });
      setSales(fresh);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.log("[MapScreen] fetchRecentSales failed:", e);
    } finally {
      setLoading(false);
    }
  }, [setSales, activeTags, happeningNow]);

  useFocusEffect(
    React.useCallback(() => {
      refresh();
    }, [refresh]),
  );

  React.useEffect(() => {
    fetchCuratedTags().then(setAvailableTags).catch(() => {});
  }, []);

  const toggleTag = (tag: string) => {
    setActiveTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
    );
  };

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
      <View style={styles.filterBar}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipRow}
        >
          <Chip
            label="Now"
            active={happeningNow}
            onPress={() => setHappeningNow((v) => !v)}
            accent
          />
          {availableTags.map((tag) => (
            <Chip
              key={tag}
              label={tag}
              active={activeTags.includes(tag)}
              onPress={() => toggleTag(tag)}
            />
          ))}
        </ScrollView>
        {(activeTags.length > 0 || happeningNow) ? (
          <Pressable
            style={styles.clearBtn}
            onPress={() => {
              setActiveTags([]);
              setHappeningNow(false);
            }}
          >
            <Text style={styles.clearText}>Clear</Text>
          </Pressable>
        ) : null}
      </View>
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

function Chip({
  label, active, onPress, accent,
}: { label: string; active: boolean; onPress: () => void; accent?: boolean }) {
  return (
    <Pressable
      onPress={onPress}
      style={[
        styles.chip,
        active && (accent ? styles.chipActiveAccent : styles.chipActive),
      ]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  filterBar: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  chipRow: { paddingHorizontal: 10, paddingVertical: 8, gap: 6 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#cbd5e1",
    backgroundColor: "#f8fafc",
    marginRight: 6,
  },
  chipActive: {
    backgroundColor: "#2563eb",
    borderColor: "#2563eb",
  },
  chipActiveAccent: {
    backgroundColor: "#16a34a",
    borderColor: "#16a34a",
  },
  chipText: { fontSize: 13, color: "#334155", fontWeight: "600" },
  chipTextActive: { color: "#fff" },
  clearBtn: { paddingHorizontal: 10, paddingVertical: 8 },
  clearText: { color: "#64748b", fontSize: 13, fontWeight: "600" },
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
