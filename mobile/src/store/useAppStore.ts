import { create } from "zustand";
import { ChatTurn, LocationState, MapMarker, PluginSummary, Sale, Session } from "../types";

interface AppState {
  location: LocationState | null;
  setLocation: (loc: LocationState) => void;

  plugins: PluginSummary[];
  setPlugins: (plugins: PluginSummary[]) => void;

  messages: ChatTurn[];
  appendMessage: (msg: ChatTurn) => void;
  resetMessages: () => void;

  // Most recent sales list surfaced by a tool call
  sales: Sale[];
  setSales: (sales: Sale[]) => void;

  mapMarkers: MapMarker[];
  setMapMarkers: (markers: MapMarker[]) => void;

  // Component the chat screen should show inline (e.g., "yardsailing:SaleForm")
  activeComponent: { plugin: string; name: string; props?: unknown } | null;
  showComponent: (plugin: string, name: string, props?: unknown) => void;
  hideComponent: () => void;

  // Phase 2A: real JAIN session (Google OAuth). Null when signed out.
  session: Session | null;
  setSession: (session: Session | null) => void;

  // Phase 2B: pending user message that needs to be auto-retried after sign-in.
  // Set by useChat when an auth_required response comes back. Cleared on manual
  // send and on successful retry.
  pendingRetry: string | null;
  setPendingRetry: (message: string | null) => void;
  clearPendingRetry: () => void;

  // Quick-reply choice buttons offered by the LLM
  activeChoices: string[] | null;
  setActiveChoices: (choices: string[] | null) => void;
  clearActiveChoices: () => void;

  // Prompt to auto-send on the next ChatScreen focus. Used by the Help
  // tab's example chips: tap chip → set pendingPrompt → jump to Jain tab
  // → ChatScreen focus effect sends it and clears it.
  pendingPrompt: string | null;
  setPendingPrompt: (prompt: string | null) => void;

  // Pre-fills the chat input on next Chat tab focus (does NOT auto-send).
  // Used by plugin home screens' "Log a meal" / "Manage targets" buttons.
  pendingChatPrefill: string | null;
  setPendingChatPrefill: (prefill: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  location: null,
  setLocation: (location) => set({ location }),

  plugins: [],
  setPlugins: (plugins) => set({ plugins }),

  messages: [
    {
      role: "assistant",
      content: "Hi! I'm Jain. Ask me about yard sales near you, or anything else.",
    },
  ],
  appendMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  resetMessages: () =>
    set({
      messages: [
        {
          role: "assistant",
          content: "Hi! I'm Jain. Ask me about yard sales near you, or anything else.",
        },
      ],
    }),

  sales: [],
  setSales: (sales) => set({ sales }),

  mapMarkers: [],
  setMapMarkers: (mapMarkers) => set({ mapMarkers }),

  activeComponent: null,
  showComponent: (plugin, name, props) =>
    set({ activeComponent: { plugin, name, props } }),
  hideComponent: () => set({ activeComponent: null }),

  // Phase 2A: real JAIN session (Google OAuth). Null when signed out.
  session: null,
  setSession: (session) => set({ session }),

  // Phase 2B: pending user message for auto-retry after sign-in.
  pendingRetry: null,
  setPendingRetry: (message) => set({ pendingRetry: message }),
  clearPendingRetry: () => set({ pendingRetry: null }),

  activeChoices: null,
  setActiveChoices: (choices) => set({ activeChoices: choices }),
  clearActiveChoices: () => set({ activeChoices: null }),

  pendingPrompt: null,
  setPendingPrompt: (pendingPrompt) => set({ pendingPrompt }),

  pendingChatPrefill: null,
  setPendingChatPrefill: (pendingChatPrefill) => set({ pendingChatPrefill }),
}));
