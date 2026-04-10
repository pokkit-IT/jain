import React from "react";
import { StyleSheet, Text, View } from "react-native";

export interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
}

export function MessageBubble({ role, content }: MessageBubbleProps) {
  const isUser = role === "user";
  return (
    <View style={[styles.row, isUser ? styles.rowRight : styles.rowLeft]}>
      <View style={[styles.bubble, isUser ? styles.user : styles.assistant]}>
        <Text style={isUser ? styles.userText : styles.assistantText}>{content}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", marginVertical: 4, paddingHorizontal: 12 },
  rowLeft: { justifyContent: "flex-start" },
  rowRight: { justifyContent: "flex-end" },
  bubble: { maxWidth: "80%", padding: 10, borderRadius: 12 },
  user: { backgroundColor: "#2563eb" },
  assistant: { backgroundColor: "#e2e8f0" },
  userText: { color: "#fff", fontSize: 15 },
  assistantText: { color: "#1f2937", fontSize: 15 },
});
