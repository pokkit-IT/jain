import { create } from "zustand";
import { ChatTurn, LocationState, PluginSummary, Sale } from "../types";

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
}));
