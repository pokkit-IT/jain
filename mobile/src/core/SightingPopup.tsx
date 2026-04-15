import React from "react";
import {
  Linking,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import type { Sale } from "../types";

export interface SightingPopupProps {
  sale: Sale | null;
  onClose: () => void;
}

function directionsUrl(sale: Sale): string {
  if (sale.lat != null && sale.lng != null) {
    const coords = `${sale.lat},${sale.lng}`;
    return Platform.OS === "ios"
      ? `https://maps.apple.com/?daddr=${coords}`
      : `https://www.google.com/maps/dir/?api=1&destination=${coords}`;
  }
  return "";
}

export function SightingPopup({ sale, onClose }: SightingPopupProps) {
  if (!sale) return null;
  const confirmed = (sale.confirmations ?? 1) >= 2;
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.card} onPress={() => { /* swallow */ }}>
          <View
            style={[
              styles.badge,
              confirmed ? styles.badgeConfirmed : styles.badgeUnconfirmed,
            ]}
          >
            <Text style={styles.badgeText}>
              {confirmed ? "Confirmed" : "Unconfirmed"}
            </Text>
          </View>
          <Text style={styles.coords}>{sale.address}</Text>
          {sale.start_time && sale.end_time ? (
            <Text style={styles.hours}>
              {sale.start_time} – {sale.end_time}
            </Text>
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
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  card: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 20,
  },
  badge: {
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 10,
    marginBottom: 10,
  },
  badgeUnconfirmed: { backgroundColor: "#fef3c7" },
  badgeConfirmed: { backgroundColor: "#dcfce7" },
  badgeText: { fontSize: 12, fontWeight: "700", color: "#0f172a" },
  coords: { fontSize: 15, color: "#0f172a", marginBottom: 4 },
  hours: { fontSize: 13, color: "#475569", marginBottom: 12 },
  button: {
    backgroundColor: "#2563eb",
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 15 },
  closeBtn: { paddingVertical: 12, alignItems: "center", marginTop: 4 },
  closeText: { color: "#64748b", fontSize: 14 },
});
