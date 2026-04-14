import * as Location from "expo-location";
import React from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { planRoute, Route as PlannedRoute } from "../api/yardsailing";
import { SaleDetailsModal } from "../core/SaleDetailsModal";
import { Sale } from "../types";
import { RouteCard } from "./RouteCard";

export interface DataCardProps {
  displayHint: string;
  data: unknown;
}

type SaleWithDistance = Sale & { distance_miles?: number };

async function getCurrentStartLocation(): Promise<{ lat: number; lng: number }> {
  const { status } = await Location.requestForegroundPermissionsAsync();
  if (status !== "granted") {
    throw new Error("Location permission denied");
  }
  const pos = await Location.getCurrentPositionAsync({});
  return { lat: pos.coords.latitude, lng: pos.coords.longitude };
}

export function DataCard({ displayHint, data }: DataCardProps) {
  const [selected, setSelected] = React.useState<Sale | null>(null);
  const [selectMode, setSelectMode] = React.useState(false);
  const [ticked, setTicked] = React.useState<Set<string>>(new Set());
  const [route, setRoute] = React.useState<PlannedRoute | null>(null);
  const [planning, setPlanning] = React.useState(false);
  const [planError, setPlanError] = React.useState<string | null>(null);

  if (displayHint === "route" && data && typeof data === "object" && "route" in data) {
    const route = (data as { route: PlannedRoute }).route;
    return <RouteCard route={route} />;
  }

  if (displayHint === "map" && data && typeof data === "object" && "sales" in data) {
    const sales = ((data as { sales: SaleWithDistance[] }).sales ?? []);

    if (route) {
      return <RouteCard route={route} />;
    }

    if (sales.length === 0) {
      return (
        <View style={styles.header}>
          <Text style={styles.headerText}>No yard sales found nearby.</Text>
        </View>
      );
    }

    const toggleTick = (id: string) => {
      setTicked((prev) => {
        const next = new Set(prev);
        if (next.has(id)) {
          next.delete(id);
        } else {
          if (next.size >= 10) return prev; // cap at 10
          next.add(id);
        }
        return next;
      });
    };

    const handlePlanRoute = async () => {
      setPlanError(null);
      setPlanning(true);
      try {
        const start = await getCurrentStartLocation();
        const result = await planRoute(Array.from(ticked), start);
        setRoute(result.route);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Failed to plan route.";
        setPlanError(msg);
      } finally {
        setPlanning(false);
      }
    };

    return (
      <View style={styles.wrapper}>
        <View style={styles.topRow}>
          <Text style={styles.headerText}>
            {sales.length} yard sale{sales.length === 1 ? "" : "s"}
          </Text>
          <Pressable onPress={() => {
            setSelectMode((m) => !m);
            if (selectMode) {
              setTicked(new Set());
              setPlanError(null);
            }
          }}>
            <Text style={styles.selectToggle}>{selectMode ? "Done" : "Select"}</Text>
          </Pressable>
        </View>
        <ScrollView
          horizontal={false}
          style={styles.list}
          contentContainerStyle={styles.listContent}
        >
          {sales.map((sale) => {
            const isChecked = ticked.has(sale.id);
            return (
              <Pressable
                key={sale.id}
                style={[styles.card, selectMode && isChecked ? styles.cardChecked : null]}
                onPress={() => {
                  if (selectMode) {
                    toggleTick(sale.id);
                  } else {
                    setSelected(sale);
                  }
                }}
              >
                <View style={styles.cardRow}>
                  {selectMode ? (
                    <View style={[styles.checkbox, isChecked ? styles.checkboxChecked : null]}>
                      {isChecked ? <Text style={styles.checkMark}>✓</Text> : null}
                    </View>
                  ) : null}
                  <View style={{ flex: 1 }}>
                    <View style={styles.cardInnerRow}>
                      <Text style={styles.title} numberOfLines={1}>{sale.title}</Text>
                      {sale.distance_miles != null ? (
                        <Text style={styles.distance}>{sale.distance_miles.toFixed(1)} mi</Text>
                      ) : null}
                    </View>
                    <Text style={styles.address} numberOfLines={1}>{sale.address}</Text>
                    {(sale.start_date || sale.start_time) ? (
                      <Text style={styles.meta} numberOfLines={1}>
                        {sale.start_date ?? ""}
                        {sale.start_time ? ` · ${sale.start_time}` : ""}
                        {sale.end_time ? `–${sale.end_time}` : ""}
                      </Text>
                    ) : null}
                    {sale.tags && sale.tags.length > 0 ? (
                      <View style={styles.tagRow}>
                        {sale.tags.slice(0, 4).map((t) => (
                          <View key={t} style={styles.tagChip}>
                            <Text style={styles.tagText}>{t}</Text>
                          </View>
                        ))}
                      </View>
                    ) : null}
                  </View>
                </View>
                {!selectMode ? <Text style={styles.chev}>›</Text> : null}
              </Pressable>
            );
          })}
        </ScrollView>
        {selectMode && ticked.size >= 2 ? (
          <Pressable
            style={[styles.planButton, planning ? { opacity: 0.6 } : null]}
            onPress={handlePlanRoute}
            disabled={planning}
          >
            <Text style={styles.planButtonText}>
              {planning ? "Planning…" : `Plan Route (${ticked.size})`}
            </Text>
          </Pressable>
        ) : null}
        {planError ? <Text style={styles.planError}>{planError}</Text> : null}
        <SaleDetailsModal sale={selected} onClose={() => setSelected(null)} />
      </View>
    );
  }
  return null;
}

const styles = StyleSheet.create({
  wrapper: {
    marginHorizontal: 12,
    marginVertical: 6,
  },
  header: {
    backgroundColor: "#fefce8",
    padding: 12,
    marginHorizontal: 12,
    marginVertical: 6,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#fde68a",
  },
  headerText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#475569",
    paddingHorizontal: 4,
  },
  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 4,
    marginBottom: 8,
  },
  selectToggle: { fontSize: 13, color: "#2563eb", fontWeight: "600" },
  list: { maxHeight: 320 },
  listContent: { paddingBottom: 4 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    padding: 12,
    marginBottom: 8,
    position: "relative",
  },
  cardChecked: { backgroundColor: "#eff6ff", borderColor: "#93c5fd" },
  cardRow: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  cardInnerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: { fontSize: 15, fontWeight: "700", color: "#0f172a", flex: 1, paddingRight: 8 },
  distance: { fontSize: 12, color: "#2563eb", fontWeight: "600" },
  address: { fontSize: 13, color: "#475569", marginTop: 2 },
  meta: { fontSize: 12, color: "#64748b", marginTop: 4 },
  chev: {
    position: "absolute",
    right: 12,
    bottom: 10,
    fontSize: 20,
    color: "#cbd5e1",
    fontWeight: "300",
  },
  tagRow: { flexDirection: "row", flexWrap: "wrap", marginTop: 6 },
  tagChip: {
    backgroundColor: "#eff6ff",
    borderRadius: 10,
    paddingHorizontal: 8,
    paddingVertical: 2,
    marginRight: 4,
    marginBottom: 4,
    borderWidth: 1,
    borderColor: "#bfdbfe",
  },
  tagText: { fontSize: 11, color: "#1d4ed8", fontWeight: "600", textTransform: "capitalize" },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: "#cbd5e1",
    marginRight: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  checkboxChecked: { backgroundColor: "#2563eb", borderColor: "#2563eb" },
  checkMark: { color: "#fff", fontSize: 13, fontWeight: "700" },
  planButton: {
    backgroundColor: "#2563eb",
    padding: 12,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 8,
  },
  planButtonText: { color: "#fff", fontWeight: "700", fontSize: 14 },
  planError: { color: "#b91c1c", textAlign: "center", marginTop: 6, fontSize: 12 },
});
