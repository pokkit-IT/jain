import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";

interface Sale {
  id: string;
  title: string;
  address: string;
  start_date?: string;
  end_date?: string | null;
  start_time?: string;
  end_time?: string;
  source?: "host" | "sighting";
}

export interface YardsailingHomeProps {
  bridge: {
    callPluginApi: (path: string, method: string, body: unknown) => Promise<unknown>;
    closeComponent: () => void;
    showToast: (msg: string) => void;
    openComponent?: (name: string, props?: Record<string, unknown>) => void;
  };
}

export function YardsailingHome({ bridge }: YardsailingHomeProps) {
  const [sales, setSales] = useState<Sale[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    try {
      const res = await bridge.callPluginApi(
        "/api/plugins/yardsailing/sales", "GET", null,
      );
      setSales(Array.isArray(res) ? (res as Sale[]) : []);
    } catch (e) {
      setError((e as Error).message || "Failed to load your sales.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

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
              await bridge.callPluginApi(
                `/api/plugins/yardsailing/sales/${sale.id}`,
                "DELETE", null,
              );
              setSales((prev) => prev.filter((s) => s.id !== sale.id));
              bridge.showToast("Sale deleted.");
            } catch (e) {
              Alert.alert("Delete failed", (e as Error).message);
            }
          },
        },
      ],
    );
  };

  const openCreate = () => {
    if (bridge.openComponent) {
      bridge.openComponent("SaleForm");
    } else {
      bridge.showToast("Ask Jain to create a yard sale from the Chat tab.");
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.intro}>
        <Text style={styles.heading}>Yardsailing</Text>
        <Text style={styles.blurb}>
          Find yard sales on the Map, drop a pin on one you've spotted, or
          post your own.
        </Text>
        <Pressable style={styles.createBtn} onPress={openCreate}>
          <Text style={styles.createBtnText}>+ Create yard sale</Text>
        </Pressable>
      </View>

      <Text style={styles.sectionTitle}>My sales</Text>
      {loading ? (
        <View style={styles.empty}>
          <ActivityIndicator />
        </View>
      ) : (
        <FlatList
          data={sales}
          keyExtractor={(s) => s.id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          contentContainerStyle={sales.length === 0 ? styles.empty : styles.list}
          ListEmptyComponent={
            <Text style={styles.emptyText}>
              {error ?? "No sales yet. Tap Create above."}
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
              <Pressable
                style={styles.deleteBtn}
                onPress={() => confirmDelete(item)}
              >
                <Text style={styles.deleteText}>Delete</Text>
              </Pressable>
            </View>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  intro: {
    padding: 16,
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  heading: { fontSize: 22, fontWeight: "700", marginBottom: 4 },
  blurb: { fontSize: 14, color: "#475569", marginBottom: 12 },
  createBtn: {
    backgroundColor: "#2563eb",
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
  },
  createBtnText: { color: "#fff", fontSize: 15, fontWeight: "700" },
  sectionTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#64748b",
    textTransform: "uppercase",
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 6,
  },
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
