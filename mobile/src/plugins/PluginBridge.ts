import { apiClient } from "../api/client";
import { useAppStore } from "../store/useAppStore";

export interface PluginBridge {
  callPluginApi: (path: string, method: string, body?: unknown) => Promise<unknown>;
  closeComponent: () => void;
  openComponent: (name: string, props?: Record<string, unknown>) => void;
  showToast: (msg: string) => void;
  // Navigate to the Chat tab and pre-fill the input. Does NOT auto-send.
  navigateToChat: (prefill?: string) => void;
}

export function makeBridgeForPlugin(
  pluginName: string,
  navigate?: (tab: string) => void,
): PluginBridge {
  return {
    async callPluginApi(path, method, body) {
      // Phase 2B: route plugin API calls THROUGH JAIN's backend instead
      // of directly from the browser. This gives us:
      //   1. No CORS issues (same-origin to JAIN)
      //   2. JAIN's service-key + user identity headers are forwarded to
      //      the plugin via /api/plugins/{name}/call — same auth path as
      //      the tool executor
      //   3. apiClient already attaches the JAIN JWT Authorization header
      //      via the interceptor, so JAIN knows who's calling
      const res = await apiClient.post(
        `/api/plugins/${pluginName}/call`,
        { method, path, body },
      );
      return res.data;
    },
    closeComponent() {
      useAppStore.getState().hideComponent();
    },
    openComponent(name, props) {
      useAppStore.getState().showComponent(pluginName, name, props);
    },
    showToast(msg) {
      // Best-effort inline toast via window.alert on web. Native toast
      // libraries are out of Phase 2B scope; SaleForm displays its own
      // inline success message so this is just a fallback.
      if (typeof window !== "undefined" && typeof window.alert === "function") {
        window.alert(msg);
      }
    },
    navigateToChat(prefill) {
      if (!navigate) {
        // Navigation not available in this context (e.g., modal overlay).
        // Don't write prefill that will never be consumed.
        return;
      }
      if (prefill) {
        useAppStore.getState().setPendingChatPrefill(prefill);
      }
      navigate("Jain");
    },
  };
}
