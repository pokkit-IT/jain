import React from "react";
import {
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import { deleteSale, fetchMySales } from "../api/yardsailing";
import { useAppStore } from "../store/useAppStore";
import type { Sale } from "../types";

export function MySalesScreen() {
  const session = useAppStore((s) => s.session);
  const [sales, setSales] = React.useState<Sale[]>([]);
  const [refreshing, setRefreshing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      const mine = await fetchMySales();
      setSales(mine);
    } catch (e) {
      setError((e as Error).message || "Failed to load your sales.");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    React.useCallback(() => {
      if (session) load();
    }, [session, load]),
  );

  const confirmDelete = (sale: Sale) => {
    Alert.alert(
      "Delete sale?",
      `"${sale.title}" will be removed. This can't be undone.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              await deleteSale(sale.id);
              setSales((prev) => prev.filter((s) => s.id !== sale.id));
            } catch (e) {
              Alert.alert("Delete failed", (e as Error).message);
            }
          },
        },
      ],
    );
  };

  if (!session) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>Sign in to manage your sales.</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={sales}
      keyExtractor={(s) => s.id}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={load} />}
      contentContainerStyle={sales.length === 0 ? styles.empty : styles.list}
      ListEmptyComponent={
        <Text style={styles.emptyText}>
          {error ?? "No sales yet. Create one from the Jain tab."}
        </Text>
      }
      renderItem={({ item }) => (
        <View style={styles.card}>
          <Text style={styles.title}>{item.title}</Text>
          <Text style={styles.address}>{item.address}</Text>
          <Text style={styles.meta}>
            {item.start_date ?? ""} {item.start_time ? `· ${item.start_time}` : ""}
            {item.end_time ? `–${item.end_time}` : ""}
          </Text>
          <Pressable style={styles.deleteBtn} onPress={() => confirmDelete(item)}>
            <Text style={styles.deleteText}>Delete</Text>
          </Pressable>
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  list: { padding: 12 },
  empty: {
    flexGrow: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  emptyText: { color: "#64748b", fontSize: 15, textAlign: "center" },
  card: {
    backgroundColor: "#fff",
    padding: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    marginBottom: 10,
  },
  title: { fontSize: 16, fontWeight: "700", marginBottom: 2 },
  address: { fontSize: 13, color: "#475569", marginBottom: 4 },
  meta: { fontSize: 12, color: "#64748b", marginBottom: 10 },
  deleteBtn: {
    alignSelf: "flex-start",
    backgroundColor: "#fee2e2",
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
  },
  deleteText: { color: "#b91c1c", fontWeight: "600" },
});
