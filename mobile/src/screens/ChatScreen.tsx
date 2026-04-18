import React, { useCallback, useRef, useState } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useHeaderHeight } from "@react-navigation/elements";
import { useFocusEffect } from "@react-navigation/native";

import { AuthPrompt } from "../chat/AuthPrompt";
import { ChoiceButtons } from "../chat/ChoiceButtons";
import { DataCard } from "../chat/DataCard";
import { MessageBubble } from "../chat/MessageBubble";
import { ToolIndicator } from "../chat/ToolIndicator";
import { useChat } from "../hooks/useChat";
import { useLocation } from "../hooks/useLocation";
import { useAppStore } from "../store/useAppStore";
import { listPlugins } from "../api/plugins";

export function ChatScreen() {
  useLocation();
  const { messages, send, sending, lastResponse } = useChat();
  const [input, setInput] = useState("");
  const listRef = useRef<FlatList>(null);
  const inputRef = useRef<TextInput>(null);
  const headerHeight = useHeaderHeight();

  const activeChoices = useAppStore((s) => s.activeChoices);
  const setPlugins = useAppStore((s) => s.setPlugins);

  // Refocus the TextInput every time the Jain tab gains focus. Bottom-tab
  // navigator keeps screens mounted across tab switches, so `autoFocus`
  // only fires on first mount — this handles return visits.
  useFocusEffect(
    useCallback(() => {
      const timer = setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }, []),
  );

  // Refresh plugin list when the chat tab gains focus
  useFocusEffect(
    useCallback(() => {
      listPlugins().then(setPlugins).catch(() => {});
    }, [setPlugins]),
  );

  // Auto-send a prompt queued by the Help screen's example chips.
  useFocusEffect(
    useCallback(() => {
      const pending = useAppStore.getState().pendingPrompt;
      if (!pending) return;
      useAppStore.getState().setPendingPrompt(null);
      void send(pending);
      listRef.current?.scrollToEnd({ animated: true });
    }, [send]),
  );

  // Pre-fill the chat input when a plugin navigates here with a prefill string.
  // Does NOT auto-send — the user types their message and taps Send themselves.
  useFocusEffect(
    useCallback(() => {
      const prefill = useAppStore.getState().pendingChatPrefill;
      if (!prefill) return;
      useAppStore.getState().setPendingChatPrefill(null);
      setInput(prefill);
      setTimeout(() => inputRef.current?.focus(), 50);
    }, []),
  );

  const onSend = async () => {
    const text = input.trim();
    if (!text) return;
    setInput("");
    inputRef.current?.clear();
    await send(text);
    listRef.current?.scrollToEnd({ animated: true });
    // Refocus the input so the user can keep typing without tapping back.
    inputRef.current?.focus();
  };

  const onChoice = useCallback(
    (label: string) => {
      setInput("");
      inputRef.current?.clear();
      send(label);
      listRef.current?.scrollToEnd({ animated: true });
    },
    [send],
  );

  // Called by <AuthPrompt /> after a successful sign-in. Reads the
  // pending retry from the store and invokes send() directly — no
  // useEffect closure race.
  const handleSignInComplete = useCallback(() => {
    const store = useAppStore.getState();
    const pending = store.pendingRetry;
    console.log("[ChatScreen] sign-in complete, pendingRetry =", pending?.slice(0, 40));
    if (!pending) return;
    store.clearPendingRetry();
    // Give React a beat to propagate the session change before firing
    // the retry (the axios interceptor reads the token at request time).
    setTimeout(() => {
      void send(pending);
    }, 50);
  }, [send]);

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
      {lastResponse?.display_hint === "auth_required" ? (
        <AuthPrompt onSignInComplete={handleSignInComplete} />
      ) : null}
      {lastResponse?.display_hint &&
      lastResponse.display_hint !== "auth_required" &&
      lastResponse.data ? (
        <DataCard displayHint={lastResponse.display_hint} data={lastResponse.data} />
      ) : null}
      <ToolIndicator visible={sending} />
      {activeChoices && activeChoices.length > 0 ? (
        <ChoiceButtons choices={activeChoices} onChoose={onChoice} />
      ) : null}
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
});
