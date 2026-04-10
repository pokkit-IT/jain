import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { Sale } from "../types";

export interface DataCardProps {
  displayHint: string;
  data: unknown;
}

export function DataCard({ displayHint, data }: DataCardProps) {
  if (displayHint === "map" && data && typeof data === "object" && "sales" in data) {
    const sales = (data as { sales: Sale[] }).sales ?? [];
    return (
      <View style={styles.card}>
        <Text style={styles.title}>
          Found {sales.length} yard sale{sales.length === 1 ? "" : "s"}
        </Text>
        <Text style={styles.subtitle}>Tap the Map tab to see them on a map</Text>
      </View>
    );
  }
  return null;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#fefce8",
    padding: 12,
    marginHorizontal: 12,
    marginVertical: 6,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#fde68a",
  },
  title: { fontSize: 15, fontWeight: "600", color: "#713f12" },
  subtitle: { fontSize: 13, color: "#92400e", marginTop: 2 },
});
