import { useEffect, useState } from "react";

import { sendChatMessage } from "../api/chat";
import { useAppStore } from "../store/useAppStore";
import { ChatResponse, Sale } from "../types";

export function useChat() {
  const messages = useAppStore((s) => s.messages);
  const appendMessage = useAppStore((s) => s.appendMessage);
  const setSales = useAppStore((s) => s.setSales);
  const showComponent = useAppStore((s) => s.showComponent);
  const location = useAppStore((s) => s.location);
  const plugins = useAppStore((s) => s.plugins);
  const session = useAppStore((s) => s.session);
  const pendingRetry = useAppStore((s) => s.pendingRetry);
  const setPendingRetry = useAppStore((s) => s.setPendingRetry);
  const clearPendingRetry = useAppStore((s) => s.clearPendingRetry);

  const [sending, setSending] = useState(false);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);

  const send = async (text: string) => {
    if (!text.trim() || sending) return;

    // Manual send always clears any stale pending retry
    clearPendingRetry();

    const userTurn = { role: "user" as const, content: text };
    appendMessage(userTurn);
    setSending(true);

    try {
      const res = await sendChatMessage({
        message: text,
        history: messages,
        lat: location?.lat,
        lng: location?.lng,
      });
      setLastResponse(res);
      appendMessage({ role: "assistant", content: res.reply || "(no reply)" });

      // Handle display_hint and data
      if (res.display_hint === "map" && res.data && typeof res.data === "object") {
        const maybeSales = (res.data as { sales?: Sale[] }).sales;
        if (Array.isArray(maybeSales)) setSales(maybeSales);
      }

      if (res.display_hint === "auth_required") {
        // Store the original user message so we can auto-retry after sign-in
        setPendingRetry(text);
      }

      if (res.display_hint?.startsWith("component:")) {
        const [, name] = res.display_hint.split(":");
        const owner = plugins.find((p) => p.components?.exports.includes(name));
        if (owner) showComponent(owner.name, name, res.data ?? undefined);
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

  // Phase 2B: auto-retry the pending message when the user signs in.
  useEffect(() => {
    if (session && pendingRetry) {
      const message = pendingRetry;
      clearPendingRetry();
      // Small tick so the UI has time to dismiss the AuthPrompt and
      // re-render the logged-in state before the new request fires.
      const timer = setTimeout(() => {
        void send(message);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [session, pendingRetry]);

  return { messages, send, sending, lastResponse };
}
