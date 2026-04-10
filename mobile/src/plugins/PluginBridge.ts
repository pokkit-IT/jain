import axios from "axios";
import { Alert } from "react-native";

import { useAppStore } from "../store/useAppStore";

export interface PluginBridge {
  callPluginApi: (path: string, method: string, body?: unknown) => Promise<unknown>;
  closeComponent: () => void;
  showToast: (msg: string) => void;
}

export function makeBridgeForPlugin(pluginName: string): PluginBridge {
  return {
    async callPluginApi(path, method, body) {
      const plugin = useAppStore.getState().plugins.find((p) => p.name === pluginName);
      if (!plugin?.api?.base_url) {
        throw new Error(`plugin ${pluginName} has no api base_url`);
      }
      const url = plugin.api.base_url.replace(/\/$/, "") + path;
      const res = await axios.request({ url, method, data: body });
      return res.data;
    },
    closeComponent() {
      useAppStore.getState().hideComponent();
    },
    showToast(msg) {
      Alert.alert(msg);
    },
  };
}
