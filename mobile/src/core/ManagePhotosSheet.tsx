import React from "react";
import {
  Image,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";

import { absUrl } from "../api/client";
import {
  uploadSalePhoto,
  deleteSalePhoto,
  reorderSalePhotos,
} from "../api/yardsailing";
import type { SalePhoto } from "../types";

interface Props {
  visible: boolean;
  saleId: string;
  photos: SalePhoto[];
  onClose: () => void;
  onChange: (photos: SalePhoto[]) => void;
}

const MAX = 5;

export function ManagePhotosSheet({
  visible,
  saleId,
  photos,
  onClose,
  onChange,
}: Props) {
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const pick = async () => {
    if (photos.length >= MAX) return;
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      setError("Photo library permission denied");
      return;
    }
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });
    if (res.canceled) return;
    setBusy(true);
    setError(null);
    try {
      const asset = res.assets[0];
      const uri = asset.uri;
      const name = asset.fileName ?? `photo-${Date.now()}.jpg`;
      const type = asset.mimeType ?? "image/jpeg";
      const uploaded = await uploadSalePhoto(saleId, { uri, name, type });
      onChange([...photos, uploaded]);
    } catch {
      setError("Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (photoId: string) => {
    setBusy(true);
    setError(null);
    try {
      await deleteSalePhoto(saleId, photoId);
      onChange(photos.filter((p) => p.id !== photoId));
    } catch {
      setError("Delete failed");
    } finally {
      setBusy(false);
    }
  };

  const move = async (index: number, delta: number) => {
    const target = index + delta;
    if (target < 0 || target >= photos.length) return;
    const newOrder = [...photos];
    const [moved] = newOrder.splice(index, 1);
    newOrder.splice(target, 0, moved);
    const ids = newOrder.map((p) => p.id);
    setBusy(true);
    setError(null);
    try {
      const updated = await reorderSalePhotos(saleId, ids);
      onChange(updated);
    } catch {
      setError("Reorder failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>
            Manage Photos ({photos.length}/{MAX})
          </Text>
          <Pressable onPress={onClose}>
            <Text style={styles.close}>Done</Text>
          </Pressable>
        </View>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <ScrollView contentContainerStyle={styles.grid}>
          {photos.map((p, i) => (
            <View key={p.id} style={styles.tile}>
              <Image
                source={{ uri: absUrl(p.thumb_url) }}
                style={styles.thumb}
              />
              <View style={styles.tileActions}>
                <Pressable
                  style={[styles.tileBtn, i === 0 && styles.tileBtnDisabled]}
                  onPress={() => move(i, -1)}
                  disabled={i === 0 || busy}
                >
                  <Text style={styles.tileBtnText}>↑</Text>
                </Pressable>
                <Pressable
                  style={[
                    styles.tileBtn,
                    i === photos.length - 1 && styles.tileBtnDisabled,
                  ]}
                  onPress={() => move(i, 1)}
                  disabled={i === photos.length - 1 || busy}
                >
                  <Text style={styles.tileBtnText}>↓</Text>
                </Pressable>
                <Pressable
                  style={styles.tileBtn}
                  onPress={() => remove(p.id)}
                  disabled={busy}
                >
                  <Text style={styles.tileBtnText}>✕</Text>
                </Pressable>
              </View>
            </View>
          ))}
          {photos.length < MAX ? (
            <Pressable
              style={[styles.tile, styles.addTile]}
              onPress={pick}
              disabled={busy}
            >
              <Text style={styles.addPlus}>+</Text>
              <Text style={styles.addLabel}>{busy ? "…" : "Add"}</Text>
            </Pressable>
          ) : null}
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff", paddingTop: 60 },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  title: { fontSize: 16, fontWeight: "700", color: "#0f172a" },
  close: { fontSize: 14, color: "#2563eb", fontWeight: "600" },
  error: {
    color: "#b91c1c",
    textAlign: "center",
    padding: 8,
    fontSize: 13,
  },
  grid: { flexDirection: "row", flexWrap: "wrap", padding: 12 },
  tile: {
    width: "31%",
    aspectRatio: 1,
    margin: "1%",
    borderRadius: 10,
    overflow: "hidden",
    backgroundColor: "#f1f5f9",
    position: "relative",
  },
  thumb: { width: "100%", height: "100%" },
  tileActions: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: "row",
    justifyContent: "space-around",
    backgroundColor: "rgba(0,0,0,0.5)",
    paddingVertical: 4,
  },
  tileBtn: { paddingHorizontal: 6, paddingVertical: 2 },
  tileBtnDisabled: { opacity: 0.3 },
  tileBtnText: { color: "#fff", fontSize: 14, fontWeight: "700" },
  addTile: {
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: "#cbd5e1",
    borderStyle: "dashed",
    backgroundColor: "#fff",
  },
  addPlus: { fontSize: 28, color: "#64748b" },
  addLabel: { fontSize: 11, color: "#64748b", marginTop: 2 },
});
