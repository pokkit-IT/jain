import React from "react";
import {
  Dimensions,
  Image,
  Linking,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

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
  groups?: SaleGroup[];
}

interface Bridge {
  absUrl: (path: string) => string;
  getCurrentUserId: () => string | null;
}

export interface SaleDetailsModalProps {
  sale: Sale | null;
  onClose: () => void;
  bridge: Bridge;
}

function directionsUrl(sale: Sale): string {
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

const SCREEN_WIDTH = Dimensions.get("window").width;

export function SaleDetailsModal({ sale, onClose, bridge }: SaleDetailsModalProps) {
  if (!sale) return null;

  const days = sale.days ?? [];
  const isMultiDay = days.length > 1;
  const when = !isMultiDay
    ? sale.start_date
      ? sale.end_date && sale.end_date !== sale.start_date
        ? `${sale.start_date} – ${sale.end_date}`
        : sale.start_date
      : null
    : null;
  const hours =
    !isMultiDay && sale.start_time && sale.end_time
      ? `${sale.start_time} – ${sale.end_time}`
      : null;
  const photos = sale.photos ?? [];

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
            {photos.length > 0 ? (
              <ScrollView
                horizontal
                pagingEnabled
                showsHorizontalScrollIndicator={false}
                style={styles.carousel}
              >
                {photos.map((p) => (
                  <Image
                    key={p.id}
                    source={{ uri: bridge.absUrl(p.url) }}
                    style={[styles.carouselImage, { width: SCREEN_WIDTH - 24 }]}
                    resizeMode="cover"
                  />
                ))}
              </ScrollView>
            ) : null}
            <Text style={styles.title}>{sale.title}</Text>
            <Text style={styles.address}>{sale.address}</Text>
            {when || hours ? (
              <Text style={styles.meta}>
                {[when, hours].filter(Boolean).join(" · ")}
              </Text>
            ) : null}
            {isMultiDay ? (
              <View style={styles.schedule}>
                {days.map((d) => (
                  <View key={d.day_date} style={styles.scheduleRow}>
                    <Text style={styles.scheduleDate}>{d.day_date}</Text>
                    <Text style={styles.scheduleHours}>
                      {d.start_time} – {d.end_time}
                    </Text>
                  </View>
                ))}
              </View>
            ) : null}
            {sale.tags && sale.tags.length > 0 ? (
              <View style={styles.tagRow}>
                {sale.tags.map((t) => (
                  <View key={t} style={styles.tagChip}>
                    <Text style={styles.tagText}>{t}</Text>
                  </View>
                ))}
              </View>
            ) : null}
            {sale.groups && sale.groups.length > 0 ? (
              <View style={styles.tagRow}>
                {sale.groups.map((g) => (
                  <View key={g.id} style={styles.groupChip}>
                    <Text style={styles.groupChipText}>{g.name}</Text>
                  </View>
                ))}
              </View>
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
  schedule: {
    backgroundColor: "#f8fafc",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    paddingVertical: 8,
    paddingHorizontal: 12,
    marginBottom: 16,
  },
  scheduleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 4,
  },
  scheduleDate: { fontSize: 14, color: "#334155", fontWeight: "600" },
  scheduleHours: { fontSize: 14, color: "#475569" },
  tagRow: { flexDirection: "row", flexWrap: "wrap", marginBottom: 16 },
  tagChip: {
    backgroundColor: "#eff6ff",
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 4,
    marginRight: 6,
    marginBottom: 6,
    borderWidth: 1,
    borderColor: "#bfdbfe",
  },
  tagText: {
    fontSize: 12,
    color: "#1d4ed8",
    fontWeight: "600",
    textTransform: "capitalize",
  },
  groupChip: {
    backgroundColor: "#ede9fe",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    marginRight: 6,
    marginTop: 4,
  },
  groupChipText: { fontSize: 12, color: "#6d28d9", fontWeight: "600" },
  carousel: { height: 240, marginBottom: 12 },
  carouselImage: { height: 240, borderRadius: 12, marginRight: 8 },
});
