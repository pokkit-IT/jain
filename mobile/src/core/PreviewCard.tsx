import React from "react";
import { StyleSheet, Text, TouchableOpacity } from "react-native";

export interface PreviewCardProps {
  title: string;
  subtitle?: string;
  body?: string;
  onPress?: () => void;
}

export function PreviewCard({ title, subtitle, body, onPress }: PreviewCardProps) {
  return (
    <TouchableOpacity style={styles.card} onPress={onPress} disabled={!onPress}>
      <Text style={styles.title}>{title}</Text>
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      {body ? <Text style={styles.body}>{body}</Text> : null}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#fff",
    padding: 12,
    marginVertical: 6,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  title: { fontSize: 16, fontWeight: "600" },
  subtitle: { fontSize: 13, color: "#64748b", marginTop: 2 },
  body: { fontSize: 14, color: "#1f2937", marginTop: 6 },
});
