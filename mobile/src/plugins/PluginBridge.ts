import { absUrl as coreAbsUrl, apiClient } from "../api/client";
import { mapEventBus } from "../core/mapEventBus";
import { useAppStore } from "../store/useAppStore";
import type { MapMarker } from "../types";

export interface PluginBridge {
  callPluginApi: (path: string, method: string, body?: unknown) => Promise<unknown>;
  closeComponent: () => void;
  openComponent: (name: string, props?: Record<string, unknown>) => void;
  showToast: (msg: string) => void;
  navigateToChat: (prefill?: string) => void;
  absUrl: (relativePath: string) => string;
  getCurrentUserId: () => string | null;
}

export interface MapBridgeExtension {
  setMarkers: (markers: MapMarker[]) => void;
  onLongPress: (cb: (coord: { lat: number; lng: number }) => void) => void;
  offLongPress: (cb: (coord: { lat: number; lng: number }) => void) => void;
  onMarkerPress: (cb: (marker: MapMarker) => void) => void;
  offMarkerPress: (cb: (marker: MapMarker) => void) => void;
  getLocation: () => { lat: number; lng: number } | null;
}

export function makeBridgeForPlugin(
  pluginName: string,
  navigate?: (tab: string) => void,
): PluginBridge {
  return {
    async callPluginApi(path, method, body) {
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
      if (typeof window !== "undefined" && typeof window.alert === "function") {
        window.alert(msg);
      }
    },
    navigateToChat(prefill) {
      if (!navigate) return;
      if (prefill) {
        useAppStore.getState().setPendingChatPrefill(prefill);
      }
      navigate("Jain");
    },
    absUrl(relativePath) {
      return coreAbsUrl(relativePath);
    },
    getCurrentUserId() {
      return useAppStore.getState().session?.user.id ?? null;
    },
  };
}

export function makeMapBridgeExtension(): MapBridgeExtension {
  return {
    setMarkers(markers) {
      useAppStore.getState().setMapMarkers(markers);
    },
    onLongPress(cb) {
      mapEventBus.subscribeLongPress(cb);
    },
    offLongPress(cb) {
      mapEventBus.unsubscribeLongPress(cb);
    },
    onMarkerPress(cb) {
      mapEventBus.subscribeMarkerPress(cb);
    },
    offMarkerPress(cb) {
      mapEventBus.unsubscribeMarkerPress(cb);
    },
    getLocation() {
      return useAppStore.getState().location;
    },
  };
}
