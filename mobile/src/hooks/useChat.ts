import { useEffect, useRef, useState } from "react";

import { sendChatMessage } from "../api/chat";
import { useAppStore } from "../store/useAppStore";
import { ChatResponse, Sale } from "../types";

export function useChat() {
  const appendMessage = useAppStore((s) => s.appendMessage);
  const setSales = useAppStore((s) => s.setSales);
  const showComponent = useAppStore((s) => s.showComponent);
  const session = useAppStore((s) => s.session);
  const pendingRetry = useAppStore((s) => s.pendingRetry);
  const setPendingRetry = useAppStore((s) => s.setPendingRetry);
  const clearPendingRetry = useAppStore((s) => s.clearPendingRetry);
  // NOTE: intentionally NOT subscribing to `messages` here — we read it
  // via useAppStore.getState() at send time to avoid stale closures from
  // the useEffect auto-retry path. Subscribing to messages would cause
  // the `send` closure to be recreated on every chat message, breaking
  // ref-based call patterns used by AuthPrompt.

  const [sending, setSending] = useState(false);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);

  // Keep `send` in a ref so AuthPrompt (and any other caller) can invoke
  // the latest version even from an async callback. The function body
  // reads all mutable state fresh from the store, so the ref indirection
  // is just for stable identity, not for closure freshness.
  const sendRef = useRef<((text: string) => Promise<void>) | null>(null);

  const send = async (text: string) => {
    console.log("[useChat] send called with:", text.slice(0, 40));
    if (!text.trim()) return;

    // Read current state fresh from the store at send time.
    const store = useAppStore.getState();
    if (sending) {
      console.log("[useChat] already sending, ignoring");
      return;
    }

    // Manual send always clears any stale pending retry
    store.clearPendingRetry();
    store.clearActiveChoices();

    const userTurn = { role: "user" as const, content: text };
    store.appendMessage(userTurn);
    setSending(true);

    try {
      const historyAtSend = useAppStore.getState().messages.slice(0, -1);
      // ^ Exclude the just-appended user turn — that's sent separately
      // as the `message` param. Matches Phase 1 semantics.
      const res = await sendChatMessage({
        message: text,
        history: historyAtSend,
        lat: store.location?.lat,
        lng: store.location?.lng,
      });
      console.log("[useChat] response:", res.display_hint, res.reply?.slice(0, 40));
      setLastResponse(res);
      store.appendMessage({ role: "assistant", content: res.reply || "(no reply)" });

      // Handle display_hint and data
      if (res.display_hint === "map" && res.data && typeof res.data === "object") {
        const maybeSales = (res.data as { sales?: Sale[] }).sales;
        if (Array.isArray(maybeSales)) setSales(maybeSales);
      }

      if (res.display_hint === "auth_required") {
        // Store the original user message so we can auto-retry after sign-in
        console.log("[useChat] auth_required, setting pendingRetry:", text.slice(0, 40));
        store.setPendingRetry(text);
      }

      if (res.display_hint?.startsWith("component:")) {
        const [, name] = res.display_hint.split(":");
        // Read plugins fresh from the store — it may have been populated
        // after this closure was captured (e.g. App.tsx loads them async).
        const currentPlugins = useAppStore.getState().plugins;
        const owner = currentPlugins.find((p) =>
          p.components?.exports.includes(name),
        );
        console.log(
          "[useChat] component:",
          name,
          "owner:",
          owner?.name ?? "<NOT FOUND>",
          "plugins loaded:",
          currentPlugins.map((p) => p.name),
        );
        if (owner) showComponent(owner.name, name, res.data ?? undefined);
      }

      // Quick-reply choices
      if (res.choices && res.choices.length > 0) {
        store.setActiveChoices(res.choices);
      }
    } catch (e) {
      appendMessage({
        role: "assistant",
        content: `(error: ${(e as Error).message})`,
      });
    } finally {
      setSending(false);
    }
  };

  sendRef.current = send;

  // Phase 2B: auto-retry the pending message when the user signs in.
  // This path handles the case where the user signed in via the Settings
  // tab (not via the inline AuthPrompt which calls send directly).
  useEffect(() => {
    if (session && pendingRetry) {
      const message = pendingRetry;
      console.log("[useChat] session flipped, retrying pending:", message.slice(0, 40));
      clearPendingRetry();
      const timer = setTimeout(() => {
        void sendRef.current?.(message);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [session, pendingRetry, clearPendingRetry]);

  // Read messages from the store for the FlatList. Subscribing here is fine —
  // it only affects the component that renders the list, not the send closure.
  const messages = useAppStore((s) => s.messages);

  return { messages, send, sending, lastResponse };
}
