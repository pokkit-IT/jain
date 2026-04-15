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
  fetchRecentSales,
  postSighting,
} from "../api/yardsailing";
import { Map } from "../core/Map";
import { SaleDetailsModal } from "../core/SaleDetailsModal";
import { SightingPopup } from "../core/SightingPopup";
import { useLocation } from "../hooks/useLocation";
import { useAppStore } from "../store/useAppStore";
import type { Sale, SaleGroupSummary } from "../types";

function pad2(n: number) { return n < 10 ? `0${n}` : String(n); }
function nowHHMM(): string {
  const d = new Date();
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

export function MapScreen() {
  const location = useLocation();
  const sales = useAppStore((s) => s.sales);
  const setSales = useAppStore((s) => s.setSales);
  const [selected, setSelected] = React.useState<Sale | null>(null);
  const [selectedSighting, setSelectedSighting] = React.useState<Sale | null>(null);
  const [pendingDrop, setPendingDrop] = React.useState<{ lat: number; lng: number } | null>(null);
  const [dropping, setDropping] = React.useState(false);
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
      <Map
        region={region}
        sales={sales}
        onPinPress={setSelected}
        onSightingPress={setSelectedSighting}
        onLongPress={(c) => {
          const hh = parseInt(nowHHMM().slice(0, 2), 10);
          if (hh >= 17) {
            // past the drop cutoff — no-op with a light hint
            return;
          }
          setPendingDrop(c);
        }}
      />
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
      <SightingPopup
        sale={selectedSighting}
        onClose={() => setSelectedSighting(null)}
      />
      <Modal
        transparent
        animationType="fade"
        visible={pendingDrop !== null}
        onRequestClose={() => setPendingDrop(null)}
      >
        <View style={styles.dropBackdrop}>
          <Pressable
            style={StyleSheet.absoluteFill}
            onPress={() => !dropping && setPendingDrop(null)}
          />
          <View style={styles.dropCard}>
            <Text style={styles.dropTitle}>Drop unconfirmed sale?</Text>
            {pendingDrop ? (
              <Text style={styles.dropCoords}>
                {pendingDrop.lat.toFixed(5)}, {pendingDrop.lng.toFixed(5)}
              </Text>
            ) : null}
            <Text style={styles.dropHint}>
              If someone else drops a pin here too, it'll be marked Confirmed.
            </Text>
            <Pressable
              style={[styles.dropBtn, dropping && { opacity: 0.6 }]}
              disabled={dropping || !pendingDrop}
              onPress={async () => {
                if (!pendingDrop) return;
                setDropping(true);
                try {
                  await postSighting(pendingDrop.lat, pendingDrop.lng, nowHHMM());
                  setPendingDrop(null);
                  await refresh();
                } catch (e) {
                  // eslint-disable-next-line no-console
                  console.log("[MapScreen] drop failed:", e);
                } finally {
                  setDropping(false);
                }
              }}
            >
              <Text style={styles.dropBtnText}>
                {dropping ? "Dropping…" : "Drop pin"}
              </Text>
            </Pressable>
            <Pressable
              style={styles.dropCancel}
              onPress={() => !dropping && setPendingDrop(null)}
            >
              <Text style={styles.dropCancelText}>Cancel</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
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
  dropBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  dropCard: { backgroundColor: "#fff", borderRadius: 14, padding: 20 },
  dropTitle: { fontSize: 18, fontWeight: "700", marginBottom: 8 },
  dropCoords: { fontSize: 14, color: "#475569", marginBottom: 8 },
  dropHint: { fontSize: 13, color: "#64748b", marginBottom: 16 },
  dropBtn: {
    backgroundColor: "#f59e0b",
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
  },
  dropBtnText: { color: "#fff", fontSize: 15, fontWeight: "700" },
  dropCancel: { paddingVertical: 12, alignItems: "center", marginTop: 4 },
  dropCancelText: { color: "#64748b", fontSize: 14 },
});
