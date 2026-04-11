import React, { useRef, useState } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Modal,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useHeaderHeight } from "@react-navigation/elements";

import { AuthPrompt } from "../chat/AuthPrompt";
import { DataCard } from "../chat/DataCard";
import { MessageBubble } from "../chat/MessageBubble";
import { ToolIndicator } from "../chat/ToolIndicator";
import { useChat } from "../hooks/useChat";
import { useLocation } from "../hooks/useLocation";
import { PluginHost } from "../plugins/PluginHost";
import { useAppStore } from "../store/useAppStore";

export function ChatScreen() {
  useLocation();
  const { messages, send, sending, lastResponse } = useChat();
  const [input, setInput] = useState("");
  const listRef = useRef<FlatList>(null);
  const inputRef = useRef<TextInput>(null);
  const headerHeight = useHeaderHeight();

  const activeComponent = useAppStore((s) => s.activeComponent);
  const hideComponent = useAppStore((s) => s.hideComponent);

  const onSend = async () => {
    const text = input.trim();
    setInput("");
    await send(text);
    listRef.current?.scrollToEnd({ animated: true });
    // Refocus the input so the user can keep typing without tapping back.
    inputRef.current?.focus();
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={Platform.OS === "ios" ? headerHeight : 0}
    >
      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(_, i) => String(i)}
        renderItem={({ item }) => <MessageBubble role={item.role} content={item.content} />}
        contentContainerStyle={styles.list}
      />
      {lastResponse?.display_hint === "auth_required" ? <AuthPrompt /> : null}
      {lastResponse?.display_hint &&
      lastResponse.display_hint !== "auth_required" &&
      lastResponse.data ? (
        <DataCard displayHint={lastResponse.display_hint} data={lastResponse.data} />
      ) : null}
      <ToolIndicator visible={sending} />

      <View style={styles.inputRow}>
        <TextInput
          ref={inputRef}
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder="Ask Jain anything..."
          editable={!sending}
          onSubmitEditing={onSend}
          autoFocus
          blurOnSubmit={false}
          returnKeyType="send"
        />
        <TouchableOpacity
          style={[styles.sendButton, sending && styles.sendDisabled]}
          onPress={onSend}
          disabled={sending}
        >
          <Text style={styles.sendText}>Send</Text>
        </TouchableOpacity>
      </View>

      <Modal visible={activeComponent !== null} animationType="slide">
        <View style={styles.modalHeader}>
          <TouchableOpacity onPress={hideComponent}>
            <Text style={styles.close}>Close</Text>
          </TouchableOpacity>
        </View>
        {activeComponent ? (
          <PluginHost
            pluginName={activeComponent.plugin}
            componentName={activeComponent.name}
            props={{ initialData: activeComponent.props }}
          />
        ) : null}
      </Modal>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  list: { paddingVertical: 8 },
  inputRow: {
    flexDirection: "row",
    padding: 8,
    borderTopWidth: 1,
    borderTopColor: "#e2e8f0",
    backgroundColor: "#fff",
  },
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#cbd5e1",
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    fontSize: 15,
  },
  sendButton: {
    marginLeft: 8,
    backgroundColor: "#2563eb",
    paddingHorizontal: 16,
    justifyContent: "center",
    borderRadius: 20,
  },
  sendDisabled: { backgroundColor: "#94a3b8" },
  sendText: { color: "#fff", fontWeight: "600" },
  modalHeader: {
    paddingTop: 50,
    paddingHorizontal: 16,
    paddingBottom: 12,
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  close: { color: "#2563eb", fontSize: 16 },
});
