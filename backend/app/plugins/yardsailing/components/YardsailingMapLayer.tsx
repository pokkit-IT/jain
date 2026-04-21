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

import { SaleDetailsModal } from "./SaleDetailsModal";
import { SightingPopup } from "./SightingPopup";

// ─── Local types (no core imports allowed in plugin bundles) ─────────────────

interface MapMarker {
  id: string;
  lat: number;
  lng: number;
  color?: string;
  title?: string;
  description?: string;
  data?: unknown;
}

interface DayHours {
  day_date: string;
  start_time: string;
  end_time: string;
}

interface SalePhoto {
  id: string;
  url: string;
  position: number;
}

interface SaleGroup {
  id: string;
  name: string;
  slug: string;
}

interface Sale {
  id: string;
  owner_id?: string;
  title: string;
  address: string;
  lat?: number | null;
  lng?: number | null;
  description?: string | null;
  start_date?: string;
  end_date?: string | null;
  start_time?: string;
  end_time?: string;
  tags?: string[];
  days?: DayHours[];
  photos?: SalePhoto[];
  source?: "host" | "sighting";
  confirmations?: number;
  groups?: SaleGroup[];
}

interface SaleGroupSummary {
  id: string;
  name: string;
  slug: string;
}

interface MapLayerBridge {
  callPluginApi: (path: string, method: string, body?: unknown) => Promise<unknown>;
  showToast: (msg: string) => void;
  absUrl: (path: string) => string;
  getCurrentUserId: () => string | null;
  setMarkers: (markers: MapMarker[]) => void;
  onLongPress: (cb: (coord: { lat: number; lng: number }) => void) => void;
  offLongPress: (cb: (coord: { lat: number; lng: number }) => void) => void;
  onMarkerPress: (cb: (marker: MapMarker) => void) => void;
  offMarkerPress: (cb: (marker: MapMarker) => void) => void;
  getLocation: () => { lat: number; lng: number } | null;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

// NOTE: Uses device local time. Assumes the user is in the same timezone
// as yard sales in their area. For cross-timezone accuracy, use a server-side cutoff.
function nowHHMM(): string {
  const d = new Date();
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function toMapMarker(sale: Sale): MapMarker {
  let color = "#2563eb";
  if (sale.source === "sighting") {
    color = (sale.confirmations ?? 1) >= 2 ? "#16a34a" : "#f59e0b";
  }
  return {
    id: sale.id,
    lat: sale.lat ?? 0,
    lng: sale.lng ?? 0,
    color,
    title: sale.title,
    description: sale.address,
    data: sale,
  };
}

// ─── Chip sub-component ───────────────────────────────────────────────────────

function Chip({
  label,
  active,
  onPress,
  accent,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
  accent?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[
        styles.chip,
        active && (accent ? styles.chipActiveAccent : styles.chipActive),
      ]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>
        {label}
      </Text>
    </Pressable>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export interface YardsailingMapLayerProps {
  /** bridge must be referentially stable (wrap in useMemo or pass a module-level constant) */
  bridge: MapLayerBridge;
}

export function YardsailingMapLayer({ bridge }: YardsailingMapLayerProps) {
  const [activeTags, setActiveTags] = React.useState<string[]>([]);
  const [happeningNow, setHappeningNow] = React.useState(false);
  const [activeGroup, setActiveGroup] = React.useState<SaleGroupSummary | null>(null);
  const [availableTags, setAvailableTags] = React.useState<string[]>([]);
  const [availableGroups, setAvailableGroups] = React.useState<SaleGroupSummary[]>([]);
  const [groupSheetOpen, setGroupSheetOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [pendingDrop, setPendingDrop] = React.useState<{ lat: number; lng: number } | null>(null);
  const [dropping, setDropping] = React.useState(false);
  const [selectedSale, setSelectedSale] = React.useState<Sale | null>(null);
  const [selectedSighting, setSelectedSighting] = React.useState<Sale | null>(null);

  // ── Load curated tags and groups once ──────────────────────────────────────
  React.useEffect(() => {
    bridge
      .callPluginApi("/api/plugins/yardsailing/tags", "GET", null)
      .then((res: unknown) => {
        if (res && typeof res === "object" && "tags" in res) {
          setAvailableTags((res as { tags: string[] }).tags);
        }
      })
      .catch(() => {});

    bridge
      .callPluginApi("/api/plugins/yardsailing/groups", "GET", null)
      .then((res: unknown) => {
        setAvailableGroups(Array.isArray(res) ? (res as SaleGroupSummary[]) : []);
      })
      .catch(() => {});
  }, [bridge]);

  // ── Fetch sales and push markers whenever filters change ───────────────────
  const loadSales = React.useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      activeTags.forEach((t) => params.append("tag", t));
      if (happeningNow) params.set("happening_now", "1");
      if (activeGroup) params.set("group_id", activeGroup.id);
      const qs = params.toString();
      const path = `/api/plugins/yardsailing/sales/recent${qs ? `?${qs}` : ""}`;
      const res = await bridge.callPluginApi(path, "GET", null);
      const sales = Array.isArray(res) ? (res as Sale[]) : [];
      bridge.setMarkers(
        sales
          .filter((s) => s.lat != null && s.lng != null)
          .map(toMapMarker),
      );
    } catch {
      bridge.setMarkers([]); // clear stale markers on fetch error
    } finally {
      setLoading(false);
    }
  }, [bridge, activeTags, happeningNow, activeGroup]);

  React.useEffect(() => {
    loadSales();
  }, [loadSales]);

  // ── Subscribe to map events ─────────────────────────────────────────────────
  React.useEffect(() => {
    const handleLongPress = (coord: { lat: number; lng: number }) => {
      const hh = parseInt(nowHHMM().slice(0, 2), 10);
      if (hh >= 17) return;
      setPendingDrop(coord);
    };

    const handleMarkerPress = (marker: MapMarker) => {
      const data = marker.data;
      if (!data || typeof data !== "object" || !("id" in data)) return;
      const sale = data as Sale;
      if (sale.source === "sighting") {
        setSelectedSighting(sale);
      } else {
        setSelectedSale(sale);
      }
    };

    bridge.onLongPress(handleLongPress);
    bridge.onMarkerPress(handleMarkerPress);

    return () => {
      bridge.offLongPress(handleLongPress);
      bridge.offMarkerPress(handleMarkerPress);
      bridge.setMarkers([]);
    };
  }, [bridge]);

  // ── Drop-pin handlers ───────────────────────────────────────────────────────
  const confirmDrop = async () => {
    if (!pendingDrop) return;
    setDropping(true);
    try {
      await bridge.callPluginApi("/api/plugins/yardsailing/sightings", "POST", {
        lat: pendingDrop.lat,
        lng: pendingDrop.lng,
        now_hhmm: nowHHMM(),
      });
      setPendingDrop(null);
      await loadSales();
    } catch {
      bridge.showToast("Failed to drop pin. Try again.");
    } finally {
      setDropping(false);
    }
  };

  const handleDropPinFab = () => {
    const hh = parseInt(nowHHMM().slice(0, 2), 10);
    if (hh >= 17) {
      bridge.showToast("Sale drop closed after 5 PM.");
      return;
    }
    const loc = bridge.getLocation();
    if (!loc) {
      bridge.showToast("Location unavailable.");
      return;
    }
    setPendingDrop(loc);
  };

  // ─────────────────────────────────────────────────────────────────────────────

  return (
    <View style={styles.overlay} pointerEvents="box-none">

      {/* ── Filter bar ──────────────────────────────────────────────────────── */}
      <View style={styles.filterBar} pointerEvents="auto">
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
              onPress={() =>
                setActiveTags((prev) =>
                  prev.includes(tag)
                    ? prev.filter((t) => t !== tag)
                    : [...prev, tag],
                )
              }
            />
          ))}
        </ScrollView>
        {activeTags.length > 0 || happeningNow || activeGroup ? (
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

      {/* ── Drop-Pin FAB (above Refresh) ─────────────────────────────────── */}
      <Pressable
        style={[styles.fab, styles.fabDrop]}
        onPress={handleDropPinFab}
        pointerEvents="auto"
        accessibilityLabel="Drop a pin"
      >
        <Text style={styles.fabText}>📍</Text>
      </Pressable>

      {/* ── Refresh FAB ──────────────────────────────────────────────────── */}
      <Pressable
        style={styles.fab}
        onPress={loadSales}
        disabled={loading}
        pointerEvents="auto"
        accessibilityLabel="Refresh sales"
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.fabText}>↻</Text>
        )}
      </Pressable>

      {/* ── Modals ───────────────────────────────────────────────────────── */}
      <SaleDetailsModal
        sale={selectedSale}
        onClose={() => setSelectedSale(null)}
        bridge={bridge}
      />
      <SightingPopup
        sale={selectedSighting}
        onClose={() => setSelectedSighting(null)}
      />

      {/* ── Sighting drop confirmation ────────────────────────────────────── */}
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
              onPress={confirmDrop}
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

      {/* ── Groups picker ─────────────────────────────────────────────────── */}
      <Modal
        transparent
        animationType="slide"
        visible={groupSheetOpen}
        onRequestClose={() => setGroupSheetOpen(false)}
      >
        <View style={styles.groupBackdrop}>
          <Pressable
            style={StyleSheet.absoluteFill}
            onPress={() => setGroupSheetOpen(false)}
          />
          <View style={styles.groupSheet}>
            <Text style={styles.groupTitle}>Filter by Group</Text>
            <Pressable
              style={styles.groupRow}
              onPress={() => {
                setActiveGroup(null);
                setGroupSheetOpen(false);
              }}
            >
              <Text
                style={[
                  styles.groupName,
                  !activeGroup && styles.groupNameActive,
                ]}
              >
                All groups
              </Text>
            </Pressable>
            {availableGroups.map((g) => (
              <Pressable
                key={g.id}
                style={styles.groupRow}
                onPress={() => {
                  setActiveGroup(g);
                  setGroupSheetOpen(false);
                }}
              >
                <Text
                  style={[
                    styles.groupName,
                    activeGroup?.id === g.id && styles.groupNameActive,
                  ]}
                >
                  {g.name}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>
      </Modal>
    </View>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  overlay: { ...StyleSheet.absoluteFillObject },
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
  chipActive: { backgroundColor: "#2563eb", borderColor: "#2563eb" },
  chipActiveAccent: { backgroundColor: "#16a34a", borderColor: "#16a34a" },
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
  fabDrop: { bottom: 88 },
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
  groupBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "flex-end",
  },
  groupSheet: {
    backgroundColor: "#fff",
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    padding: 20,
    paddingBottom: 36,
  },
  groupTitle: {
    fontSize: 17,
    fontWeight: "700",
    marginBottom: 14,
    color: "#0f172a",
  },
  groupRow: { paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#f1f5f9" },
  groupName: { fontSize: 15, color: "#334155" },
  groupNameActive: { color: "#2563eb", fontWeight: "700" },
});
