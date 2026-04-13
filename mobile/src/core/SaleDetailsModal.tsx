import React from "react";
import {
  Linking,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import type { Sale } from "../types";

export interface SaleDetailsModalProps {
  sale: Sale | null;
  onClose: () => void;
}

function directionsUrl(sale: Sale): string {
  // Prefer coords if present (exact pin). Fall back to address string.
  if (sale.lat != null && sale.lng != null) {
    const coords = `${sale.lat},${sale.lng}`;
    return Platform.OS === "ios"
      ? `https://maps.apple.com/?daddr=${coords}`
      : `https://www.google.com/maps/dir/?api=1&destination=${coords}`;
  }
  const q = encodeURIComponent(sale.address);
  return Platform.OS === "ios"
    ? `https://maps.apple.com/?daddr=${q}`
    : `https://www.google.com/maps/dir/?api=1&destination=${q}`;
}

export function SaleDetailsModal({ sale, onClose }: SaleDetailsModalProps) {
  if (!sale) return null;

  const when = sale.start_date
    ? sale.end_date && sale.end_date !== sale.start_date
      ? `${sale.start_date} – ${sale.end_date}`
      : sale.start_date
    : null;
  const hours = sale.start_time && sale.end_time
    ? `${sale.start_time} – ${sale.end_time}`
    : null;

  return (
    <Modal
      visible={sale !== null}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={() => { /* swallow */ }}>
          <ScrollView contentContainerStyle={styles.body}>
            <Text style={styles.title}>{sale.title}</Text>
            <Text style={styles.address}>{sale.address}</Text>
            {when || hours ? (
              <Text style={styles.meta}>
                {[when, hours].filter(Boolean).join(" · ")}
              </Text>
            ) : null}
            {sale.description ? (
              <Text style={styles.desc}>{sale.description}</Text>
            ) : null}
            <Pressable
              style={styles.button}
              onPress={() => Linking.openURL(directionsUrl(sale))}
            >
              <Text style={styles.buttonText}>Get directions</Text>
            </Pressable>
            <Pressable style={styles.closeBtn} onPress={onClose}>
              <Text style={styles.closeText}>Close</Text>
            </Pressable>
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: "#fff",
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    maxHeight: "70%",
  },
  body: { padding: 20 },
  title: { fontSize: 20, fontWeight: "700", marginBottom: 4 },
  address: { fontSize: 15, color: "#475569", marginBottom: 8 },
  meta: { fontSize: 13, color: "#64748b", marginBottom: 12 },
  desc: { fontSize: 15, color: "#1f2937", marginBottom: 16, lineHeight: 22 },
  button: {
    backgroundColor: "#2563eb",
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 8,
  },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
  closeBtn: { paddingVertical: 14, alignItems: "center", marginTop: 8 },
  closeText: { color: "#64748b", fontSize: 15 },
});
