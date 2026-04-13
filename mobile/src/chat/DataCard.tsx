import React from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { SaleDetailsModal } from "../core/SaleDetailsModal";
import { Sale } from "../types";

export interface DataCardProps {
  displayHint: string;
  data: unknown;
}

type SaleWithDistance = Sale & { distance_miles?: number };

export function DataCard({ displayHint, data }: DataCardProps) {
  const [selected, setSelected] = React.useState<Sale | null>(null);

  if (displayHint === "map" && data && typeof data === "object" && "sales" in data) {
    const sales = ((data as { sales: SaleWithDistance[] }).sales ?? []);
    if (sales.length === 0) {
      return (
        <View style={styles.header}>
          <Text style={styles.headerText}>No yard sales found nearby.</Text>
        </View>
      );
    }
    return (
      <View style={styles.wrapper}>
        <Text style={styles.headerText}>
          {sales.length} yard sale{sales.length === 1 ? "" : "s"}
        </Text>
        <ScrollView
          horizontal={false}
          style={styles.list}
          contentContainerStyle={styles.listContent}
        >
          {sales.map((sale) => (
            <Pressable
              key={sale.id}
              style={styles.card}
              onPress={() => setSelected(sale)}
            >
              <View style={styles.cardRow}>
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
              <Text style={styles.chev}>›</Text>
            </Pressable>
          ))}
        </ScrollView>
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
    marginBottom: 8,
    paddingHorizontal: 4,
  },
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
  cardRow: {
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
});
