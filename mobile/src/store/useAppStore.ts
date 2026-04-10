import { create } from "zustand";
import { ChatTurn, LocationState, PluginSummary, Sale, Session } from "../types";

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

  // Component the chat screen should show inline (e.g., "yardsailing:SaleForm")
  activeComponent: { plugin: string; name: string; props?: unknown } | null;
  showComponent: (plugin: string, name: string, props?: unknown) => void;
  hideComponent: () => void;

  // Per-plugin auth state. Layer 1: hardcoded false until login UI lands.
  auth: Record<string, boolean>;
  setPluginAuth: (plugin: string, authenticated: boolean) => void;

  // Phase 2A: real JAIN session (Google OAuth). Null when signed out.
  session: Session | null;
  setSession: (session: Session | null) => void;
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

  activeComponent: null,
  showComponent: (plugin, name, props) =>
    set({ activeComponent: { plugin, name, props } }),
  hideComponent: () => set({ activeComponent: null }),

  // Layer 1: yardsailing auth defaults to false until we add a login flow.
  // Jain reads this via the chat request and prompts the user accordingly.
  auth: { yardsailing: false },
  setPluginAuth: (plugin, authenticated) =>
    set((s) => ({ auth: { ...s.auth, [plugin]: authenticated } })),

  // Phase 2A: real JAIN session (Google OAuth). Null when signed out.
  session: null,
  setSession: (session) => set({ session }),
}));
