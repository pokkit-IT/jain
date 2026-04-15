import React from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import {
  fetchCuratedTags,
  fetchGroups,
  fetchRecentSales,
} from "../api/yardsailing";
import { Map } from "../core/Map";
import { SaleDetailsModal } from "../core/SaleDetailsModal";
import { useLocation } from "../hooks/useLocation";
import { useAppStore } from "../store/useAppStore";
import type { Sale, SaleGroupSummary } from "../types";

export function MapScreen() {
  const location = useLocation();
  const sales = useAppStore((s) => s.sales);
  const setSales = useAppStore((s) => s.setSales);
  const [selected, setSelected] = React.useState<Sale | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [availableTags, setAvailableTags] = React.useState<string[]>([]);
  const [activeTags, setActiveTags] = React.useState<string[]>([]);
  const [happeningNow, setHappeningNow] = React.useState(false);
  const [availableGroups, setAvailableGroups] = React.useState<SaleGroupSummary[]>([]);
  const [activeGroup, setActiveGroup] = React.useState<SaleGroupSummary | null>(null);
  const [groupSheetOpen, setGroupSheetOpen] = React.useState(false);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    try {
      const fresh = await fetchRecentSales({
        tags: activeTags,
        happeningNow,
        groupId: activeGroup?.id,
      });
      setSales(fresh);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.log("[MapScreen] fetchRecentSales failed:", e);
    } finally {
      setLoading(false);
    }
  }, [setSales, activeTags, happeningNow, activeGroup]);

  useFocusEffect(
    React.useCallback(() => {
      refresh();
    }, [refresh]),
  );

  React.useEffect(() => {
    fetchCuratedTags().then(setAvailableTags).catch(() => {});
    fetchGroups().then(setAvailableGroups).catch(() => {});
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
          <Chip
            label={activeGroup ? activeGroup.name : "Groups"}
            active={!!activeGroup}
            onPress={() => setGroupSheetOpen(true)}
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
        {(activeTags.length > 0 || happeningNow || activeGroup) ? (
          <Pressable
            style={styles.clearBtn}
            onPress={() => {
              setActiveTags([]);
              setHappeningNow(false);
              setActiveGroup(null);
            }}
          >
            <Text style={styles.clearText}>Clear</Text>
          </Pressable>
        ) : null}
      </View>
      <Modal
        transparent
        animationType="fade"
        visible={groupSheetOpen}
        onRequestClose={() => setGroupSheetOpen(false)}
      >
        <View style={styles.sheetBackdrop}>
          <Pressable
            style={StyleSheet.absoluteFill}
            onPress={() => setGroupSheetOpen(false)}
          />
          <View style={styles.sheetCard}>
            <Text style={styles.sheetTitle}>Filter by group</Text>
            <ScrollView style={{ maxHeight: 320 }}>
              <Pressable
                style={styles.sheetRow}
                onPress={() => { setActiveGroup(null); setGroupSheetOpen(false); }}
              >
                <Text style={styles.sheetRowText}>All sales</Text>
              </Pressable>
              {availableGroups.map((g) => (
                <Pressable
                  key={g.id}
                  style={styles.sheetRow}
                  onPress={() => { setActiveGroup(g); setGroupSheetOpen(false); }}
                >
                  <Text style={styles.sheetRowText}>{g.name}</Text>
                  {g.start_date && g.end_date ? (
                    <Text style={styles.sheetRowDates}>
                      {g.start_date} – {g.end_date}
                    </Text>
                  ) : null}
                </Pressable>
              ))}
              {availableGroups.length === 0 ? (
                <Text style={styles.sheetEmpty}>No groups yet.</Text>
              ) : null}
            </ScrollView>
          </View>
        </View>
      </Modal>
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
  sheetBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  sheetCard: {
    backgroundColor: "#fff",
    borderTopLeftRadius: 14,
    borderTopRightRadius: 14,
    paddingVertical: 12,
  },
  sheetTitle: { fontSize: 15, fontWeight: "700", paddingHorizontal: 16, paddingBottom: 8 },
  sheetRow: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: "#f1f5f9",
  },
  sheetRowText: { fontSize: 14, color: "#0f172a", fontWeight: "600" },
  sheetRowDates: { fontSize: 12, color: "#64748b", marginTop: 2 },
  sheetEmpty: { padding: 16, color: "#64748b", fontSize: 13 },
});
