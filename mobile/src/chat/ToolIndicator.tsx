import React from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

export interface ToolIndicatorProps {
  visible: boolean;
  label?: string;
}

export function ToolIndicator({ visible, label = "Thinking..." }: ToolIndicatorProps) {
  if (!visible) return null;
  return (
    <View style={styles.row}>
      <ActivityIndicator size="small" />
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    padding: 8,
    paddingHorizontal: 12,
  },
  label: { marginLeft: 8, color: "#64748b", fontSize: 14 },
});
