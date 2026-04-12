import React, { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { apiClient } from "../api/client";
import { useAppStore } from "../store/useAppStore";
import { makeBridgeForPlugin } from "./PluginBridge";

// Global namespace populated by plugin bundles at load time
declare const globalThis: {
  JainPlugins?: Record<string, Record<string, React.ComponentType<any>>>;
};

// In-memory cache of loaded bundle URLs, so we only eval each once
const loadedBundles = new Set<string>();

async function loadBundle(pluginName: string, bundlePath: string): Promise<void> {
  const cacheKey = `${pluginName}:${bundlePath}`;
  if (loadedBundles.has(cacheKey)) return;

  // Fetch bundle text from backend static file server.
  // Phase 1: backend serves plugin bundles at /api/plugins/<name>/bundle
  const { data: source } = await apiClient.get<string>(
    `/api/plugins/${pluginName}/bundle`,
    { responseType: "text" }
  );

  // Evaluate with a minimal require shim. Bundles are built with esbuild
  // external: ["react", "react-native"] and jsx: "transform" (classic
  // runtime), so they only request these modules at runtime. If a future
  // plugin is built with jsx: "automatic", it will also request
  // "react/jsx-runtime" — shimmed here too for safety.
  const reactModule = require("react");
  const rnModule = require("react-native");
  // esbuild's ESM interop generates `import_react.default.createElement()`
  // for JSX, but CJS modules have no `.default`. Add a self-reference so
  // both `mod.useState` (named) and `mod.default.createElement` (default) work.
  if (!reactModule.default) reactModule.default = reactModule;
  if (!rnModule.default) rnModule.default = rnModule;
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  let jsxRuntimeModule: unknown;
  try {
    jsxRuntimeModule = require("react/jsx-runtime");
  } catch {
    // Metro may not include jsx-runtime in the bundle. That's OK —
    // classic-runtime plugins don't need it.
    jsxRuntimeModule = undefined;
  }
  const shim = (mod: string) => {
    if (mod === "react") return reactModule;
    if (mod === "react-native") return rnModule;
    if (mod === "react/jsx-runtime" || mod === "react/jsx-dev-runtime") {
      if (jsxRuntimeModule) return jsxRuntimeModule;
      throw new Error(
        `plugin bundle requested "${mod}" but Metro did not include it. ` +
          `Rebuild the plugin with esbuild option { jsx: "transform" } to use ` +
          `the classic runtime.`,
      );
    }
    throw new Error(`plugin bundle requested unknown module "${mod}"`);
  };

  // eslint-disable-next-line no-new-func
  const fn = new Function("require", source);
  fn(shim);

  loadedBundles.add(cacheKey);
}

interface PluginHostProps {
  pluginName: string;
  componentName: string;
  props?: Record<string, unknown>;
}

export function PluginHost({ pluginName, componentName, props }: PluginHostProps) {
  const plugin = useAppStore((s) => s.plugins.find((p) => p.name === pluginName));
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!plugin?.components?.bundle) {
      setError(`plugin ${pluginName} has no component bundle`);
      return;
    }

    loadBundle(pluginName, plugin.components.bundle)
      .then(() => setReady(true))
      .catch((e) => setError((e as Error).message));
  }, [plugin, pluginName]);

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.err}>Plugin load failed: {error}</Text>
      </View>
    );
  }
  if (!ready) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  const Component = globalThis.JainPlugins?.[pluginName]?.[componentName];
  if (!Component) {
    return (
      <View style={styles.center}>
        <Text style={styles.err}>
          Component {componentName} not found in plugin {pluginName}
        </Text>
      </View>
    );
  }

  const bridge = makeBridgeForPlugin(pluginName);
  return <Component {...(props ?? {})} bridge={bridge} />;
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 16 },
  err: { color: "#b91c1c", textAlign: "center" },
});
