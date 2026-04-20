# Map Plugin Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple the map from yardsailing by making MapScreen a generic plugin shell, moving all yardsailing map UI into a plugin bundle component, and adding a Drop-Pin FAB.

**Architecture:** `plugin.json` gains a `map.component` field. MapScreen reads loaded plugins, renders their declared map components as `absoluteFill` overlays, and wires long-press/marker-press events through a module-level `mapEventBus`. The plugin overlay owns markers, filter chips, FABs, and modals; core knows nothing about yardsailing.

**Tech Stack:** Python/Pydantic (backend schema), TypeScript/React Native (mobile), esbuild (plugin bundle)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/plugins/core/schema.py` | Modify | Add `MapConfig` model + `map` field to `PluginManifest` |
| `backend/app/plugins/yardsailing/plugin.json` | Modify | Declare `map.component` and add export |
| `mobile/src/types.ts` | Modify | Add `MapMarker`; extend `PluginSummary` with `map` |
| `mobile/src/store/useAppStore.ts` | Modify | Add `mapMarkers` state |
| `mobile/src/core/mapEventBus.ts` | Create | Module-level long-press / marker-press pub/sub |
| `mobile/src/core/Map.tsx` | Modify | Replace `sales`+dual-callbacks with `markers`+`onMarkerPress` |
| `mobile/src/core/Map.web.tsx` | Modify | Same prop changes as `Map.tsx` |
| `mobile/src/plugins/PluginBridge.ts` | Modify | Add `absUrl`, `getCurrentUserId`; add `MapBridgeExtension`; add `makeMapBridgeExtension` |
| `mobile/src/plugins/PluginHost.tsx` | Modify | Add `bridgeExtension` prop merged into bridge |
| `mobile/src/screens/MapScreen.tsx` | Rewrite | Generic shell: map + plugin overlays |
| `mobile/App.tsx` | Modify | Show Map tab only when a plugin declares `map.component` |
| `backend/app/plugins/yardsailing/components/SightingPopup.tsx` | Create | Plugin-local sighting popup (no core imports) |
| `backend/app/plugins/yardsailing/components/SaleDetailsModal.tsx` | Create | Simplified sale detail modal (no ManagePhotosSheet) |
| `backend/app/plugins/yardsailing/components/YardsailingMapLayer.tsx` | Create | Full map overlay: filters, FABs, modals, marker management |
| `backend/app/plugins/yardsailing/components/index.ts` | Modify | Register `YardsailingMapLayer` on `globalThis.JainPlugins` |
| `mobile/src/core/SightingPopup.tsx` | Delete | Replaced by plugin version; no longer used in core |

**Leave unchanged:**
- `mobile/src/core/SaleDetailsModal.tsx` — still used by `DataCard.tsx`
- `mobile/src/api/yardsailing.ts` — still used by `DataCard.tsx` and `RouteCard.tsx`
- `mobile/src/core/ManagePhotosSheet.tsx` — still used by core `SaleDetailsModal`

---

## Task 1: Backend — Add `MapConfig` to plugin schema

**Files:**
- Modify: `backend/app/plugins/core/schema.py`

- [ ] **Add `MapConfig` model and `map` field to `PluginManifest`**

  Open `backend/app/plugins/core/schema.py`. Add after the `PluginHome` class and before `HelpExample`:

  ```python
  class MapConfig(BaseModel):
      component: str  # exported React component name rendered as map overlay
  ```

  Add to `PluginManifest` (after the `home` field):

  ```python
  map: MapConfig | None = None
  ```

  Full updated tail of the file:

  ```python
  class PluginHome(BaseModel):
      component: str
      label: str
      icon: str | None = None
      description: str | None = None


  class MapConfig(BaseModel):
      component: str


  class HelpExample(BaseModel):
      prompt: str
      description: str = ""


  class PluginManifest(BaseModel):
      name: str
      version: str
      description: str
      author: str = ""
      type: Literal["internal", "external"] = "external"
      skills: list[SkillDef]
      components: PluginComponents | None = None
      api: PluginApi | None = None
      assets: list[str] = Field(default_factory=list)
      examples: list[HelpExample] = Field(default_factory=list)
      home: PluginHome | None = None
      map: MapConfig | None = None
  ```

- [ ] **Verify the backend starts without error**

  ```bash
  cd backend && .venv/Scripts/python -c "from app.plugins.core.schema import PluginManifest; print('ok')"
  ```
  Expected: `ok`

- [ ] **Commit**

  ```bash
  git add backend/app/plugins/core/schema.py
  git commit -m "feat(map): add MapConfig to PluginManifest schema"
  ```

---

## Task 2: Mobile — `MapMarker` type + `PluginSummary.map`

**Files:**
- Modify: `mobile/src/types.ts`

- [ ] **Add `MapMarker` interface and `map` field to `PluginSummary`**

  Add after the `LocationState` interface in `mobile/src/types.ts`:

  ```typescript
  export interface MapMarker {
    id: string;
    lat: number;
    lng: number;
    color?: string;
    title?: string;
    description?: string;
    data?: unknown;
  }
  ```

  Update `PluginSummary` to add the `map` field:

  ```typescript
  export interface PluginSummary {
    name: string;
    version: string;
    description: string;
    skills: Array<{ name: string; description: string; components?: string[] }>;
    components?: { bundle: string; exports: string[] };
    api?: { base_url: string };
    home?: PluginHome | null;
    map?: { component: string } | null;
  }
  ```

- [ ] **Commit**

  ```bash
  git add mobile/src/types.ts
  git commit -m "feat(map): add MapMarker type and PluginSummary.map field"
  ```

---

## Task 3: Mobile — `mapMarkers` in app store

**Files:**
- Modify: `mobile/src/store/useAppStore.ts`

- [ ] **Add `mapMarkers` state to `useAppStore`**

  Add to the `AppState` interface (after the `sales` fields):

  ```typescript
  mapMarkers: MapMarker[];
  setMapMarkers: (markers: MapMarker[]) => void;
  ```

  Add the import at the top (update the existing types import):

  ```typescript
  import { ChatTurn, LocationState, MapMarker, PluginSummary, Sale, Session } from "../types";
  ```

  Add to the `create<AppState>` implementation (after `setSales`):

  ```typescript
  mapMarkers: [],
  setMapMarkers: (mapMarkers) => set({ mapMarkers }),
  ```

- [ ] **Commit**

  ```bash
  git add mobile/src/store/useAppStore.ts
  git commit -m "feat(map): add mapMarkers state to app store"
  ```

---

## Task 4: Mobile — `mapEventBus`

**Files:**
- Create: `mobile/src/core/mapEventBus.ts`
- Create: `mobile/src/core/__tests__/mapEventBus.test.ts`

- [ ] **Create `mapEventBus.ts`**

  Create `mobile/src/core/mapEventBus.ts`:

  ```typescript
  import type { MapMarker } from "../types";

  type Coord = { lat: number; lng: number };
  type CoordCb = (coord: Coord) => void;
  type MarkerCb = (marker: MapMarker) => void;

  const longPressSubscribers = new Set<CoordCb>();
  const markerPressSubscribers = new Set<MarkerCb>();

  export const mapEventBus = {
    emitLongPress(coord: Coord): void {
      longPressSubscribers.forEach((cb) => cb(coord));
    },
    emitMarkerPress(marker: MapMarker): void {
      markerPressSubscribers.forEach((cb) => cb(marker));
    },
    subscribeLongPress(cb: CoordCb): void {
      longPressSubscribers.add(cb);
    },
    unsubscribeLongPress(cb: CoordCb): void {
      longPressSubscribers.delete(cb);
    },
    subscribeMarkerPress(cb: MarkerCb): void {
      markerPressSubscribers.add(cb);
    },
    unsubscribeMarkerPress(cb: MarkerCb): void {
      markerPressSubscribers.delete(cb);
    },
  };
  ```

- [ ] **Create unit test**

  Create `mobile/src/core/__tests__/mapEventBus.test.ts`:

  ```typescript
  import { mapEventBus } from "../mapEventBus";

  afterEach(() => {
    // Reset module-level sets between tests by unsubscribing all added callbacks
  });

  describe("mapEventBus", () => {
    it("calls long-press subscribers with the coord", () => {
      const cb = jest.fn();
      mapEventBus.subscribeLongPress(cb);
      mapEventBus.emitLongPress({ lat: 1.23, lng: 4.56 });
      expect(cb).toHaveBeenCalledWith({ lat: 1.23, lng: 4.56 });
      mapEventBus.unsubscribeLongPress(cb);
    });

    it("does not call long-press subscriber after unsubscribe", () => {
      const cb = jest.fn();
      mapEventBus.subscribeLongPress(cb);
      mapEventBus.unsubscribeLongPress(cb);
      mapEventBus.emitLongPress({ lat: 0, lng: 0 });
      expect(cb).not.toHaveBeenCalled();
    });

    it("calls marker-press subscribers with the marker", () => {
      const cb = jest.fn();
      mapEventBus.subscribeMarkerPress(cb);
      const marker = { id: "m1", lat: 1, lng: 2, data: { source: "host" } };
      mapEventBus.emitMarkerPress(marker);
      expect(cb).toHaveBeenCalledWith(marker);
      mapEventBus.unsubscribeMarkerPress(cb);
    });

    it("does not call marker-press subscriber after unsubscribe", () => {
      const cb = jest.fn();
      mapEventBus.subscribeMarkerPress(cb);
      mapEventBus.unsubscribeMarkerPress(cb);
      mapEventBus.emitMarkerPress({ id: "m1", lat: 0, lng: 0 });
      expect(cb).not.toHaveBeenCalled();
    });

    it("calls multiple subscribers independently", () => {
      const cb1 = jest.fn();
      const cb2 = jest.fn();
      mapEventBus.subscribeLongPress(cb1);
      mapEventBus.subscribeLongPress(cb2);
      mapEventBus.emitLongPress({ lat: 5, lng: 6 });
      expect(cb1).toHaveBeenCalledTimes(1);
      expect(cb2).toHaveBeenCalledTimes(1);
      mapEventBus.unsubscribeLongPress(cb1);
      mapEventBus.unsubscribeLongPress(cb2);
    });
  });
  ```

- [ ] **Run tests**

  ```bash
  cd mobile && npx jest src/core/__tests__/mapEventBus.test.ts --no-coverage
  ```

  Expected: 5 passing tests.

- [ ] **Commit**

  ```bash
  git add mobile/src/core/mapEventBus.ts mobile/src/core/__tests__/mapEventBus.test.ts
  git commit -m "feat(map): add mapEventBus for plugin map event subscriptions"
  ```

---

## Task 5: Mobile — Update `Map.tsx` and `Map.web.tsx`

**Files:**
- Modify: `mobile/src/core/Map.tsx`
- Modify: `mobile/src/core/Map.web.tsx`

- [ ] **Rewrite `Map.tsx` to use `MapMarker[]`**

  Replace the entire contents of `mobile/src/core/Map.tsx`:

  ```typescript
  import React from "react";
  import { StyleSheet, View, Text } from "react-native";
  import MapView, { LongPressEvent, Marker, Region } from "react-native-maps";

  import type { MapMarker } from "../types";

  export interface MapProps {
    region?: Region;
    markers: MapMarker[];
    onMarkerPress?: (marker: MapMarker) => void;
    onLongPress?: (coord: { lat: number; lng: number }) => void;
  }

  export function Map({ region, markers, onMarkerPress, onLongPress }: MapProps) {
    if (!region) {
      return (
        <View style={[styles.container, styles.empty]}>
          <Text>Waiting for location...</Text>
        </View>
      );
    }

    const handleLongPress = (e: LongPressEvent) => {
      const { latitude, longitude } = e.nativeEvent.coordinate;
      onLongPress?.({ lat: latitude, lng: longitude });
    };

    return (
      <MapView
        style={styles.container}
        initialRegion={region}
        onLongPress={handleLongPress}
      >
        {markers.map((marker) => (
          <Marker
            key={marker.id}
            coordinate={{ latitude: marker.lat, longitude: marker.lng }}
            title={marker.title}
            description={marker.description}
            pinColor={marker.color ?? "#2563eb"}
            onPress={() => onMarkerPress?.(marker)}
          />
        ))}
      </MapView>
    );
  }

  const styles = StyleSheet.create({
    container: { flex: 1 },
    empty: { alignItems: "center", justifyContent: "center" },
  });
  ```

- [ ] **Rewrite `Map.web.tsx` to use `MapMarker[]`**

  Replace the entire contents of `mobile/src/core/Map.web.tsx`:

  ```typescript
  import React from "react";
  import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

  import type { MapMarker } from "../types";

  export interface MapProps {
    region?: { latitude: number; longitude: number; latitudeDelta: number; longitudeDelta: number };
    markers: MapMarker[];
    onMarkerPress?: (marker: MapMarker) => void;
    onLongPress?: (coord: { lat: number; lng: number }) => void;
  }

  export function Map({ region, markers, onMarkerPress }: MapProps) {
    return (
      <View style={styles.container}>
        <View style={styles.banner}>
          <Text style={styles.bannerText}>
            Map view is mobile-only. Showing list view on web.
          </Text>
          {region ? (
            <Text style={styles.coords}>
              Centered at {region.latitude.toFixed(4)}, {region.longitude.toFixed(4)}
            </Text>
          ) : null}
        </View>
        <ScrollView style={styles.list}>
          {markers.length === 0 ? (
            <Text style={styles.empty}>No sales loaded yet. Ask Jain to find some.</Text>
          ) : (
            markers.map((marker) => (
              <Pressable
                key={marker.id}
                style={styles.item}
                onPress={() => onMarkerPress?.(marker)}
              >
                <Text style={styles.title}>{marker.title}</Text>
                <Text style={styles.address}>{marker.description}</Text>
              </Pressable>
            ))
          )}
        </ScrollView>
      </View>
    );
  }

  const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: "#f8fafc" },
    banner: {
      backgroundColor: "#fef3c7",
      padding: 12,
      borderBottomWidth: 1,
      borderBottomColor: "#fde68a",
    },
    bannerText: { fontSize: 14, fontWeight: "600", color: "#92400e" },
    coords: { fontSize: 12, color: "#92400e", marginTop: 4 },
    list: { flex: 1, padding: 12 },
    empty: { color: "#64748b", textAlign: "center", marginTop: 40 },
    item: {
      backgroundColor: "#fff",
      padding: 12,
      borderRadius: 10,
      borderWidth: 1,
      borderColor: "#e2e8f0",
      marginBottom: 8,
    },
    title: { fontSize: 16, fontWeight: "600" },
    address: { fontSize: 13, color: "#64748b", marginTop: 2 },
  });
  ```

- [ ] **Commit**

  ```bash
  git add mobile/src/core/Map.tsx mobile/src/core/Map.web.tsx
  git commit -m "feat(map): replace sales prop with generic MapMarker[] in Map component"
  ```

---

## Task 6: Mobile — Extend `PluginBridge`

**Files:**
- Modify: `mobile/src/plugins/PluginBridge.ts`

- [ ] **Add `absUrl`, `getCurrentUserId`, `MapBridgeExtension`, and `makeMapBridgeExtension`**

  Replace the entire contents of `mobile/src/plugins/PluginBridge.ts`:

  ```typescript
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
  ```

- [ ] **Commit**

  ```bash
  git add mobile/src/plugins/PluginBridge.ts
  git commit -m "feat(map): add absUrl/getCurrentUserId to bridge; add MapBridgeExtension"
  ```

---

## Task 7: Mobile — `PluginHost` `bridgeExtension` prop

**Files:**
- Modify: `mobile/src/plugins/PluginHost.tsx`

- [ ] **Add `bridgeExtension` prop and merge into bridge**

  Update the `PluginHostProps` interface and `PluginHost` function. Replace the file contents:

  ```typescript
  import React, { useEffect, useState } from "react";
  import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

  import { apiClient } from "../api/client";
  import { useAppStore } from "../store/useAppStore";
  import { makeBridgeForPlugin, MapBridgeExtension } from "./PluginBridge";

  declare const globalThis: {
    JainPlugins?: Record<string, Record<string, React.ComponentType<any>>>;
  };

  const loadedBundles = new Set<string>();

  async function loadBundle(pluginName: string, bundlePath: string): Promise<void> {
    const cacheKey = `${pluginName}:${bundlePath}`;
    if (loadedBundles.has(cacheKey)) return;

    const { data: source } = await apiClient.get<string>(
      `/api/plugins/${pluginName}/bundle`,
      { responseType: "text" }
    );

    const reactModule = require("react");
    const rnModule = require("react-native");
    const dateTimePickerModule = require("@react-native-community/datetimepicker");
    if (!reactModule.default) reactModule.default = reactModule;
    if (!rnModule.default) rnModule.default = rnModule;
    if (!dateTimePickerModule.default) {
      dateTimePickerModule.default = dateTimePickerModule;
    }
    let jsxRuntimeModule: unknown;
    try {
      jsxRuntimeModule = require("react/jsx-runtime");
    } catch {
      jsxRuntimeModule = undefined;
    }
    const shim = (mod: string) => {
      if (mod === "react") return reactModule;
      if (mod === "react-native") return rnModule;
      if (mod === "@react-native-community/datetimepicker") return dateTimePickerModule;
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
    navigate?: (tab: string) => void;
    bridgeExtension?: Partial<MapBridgeExtension>;
  }

  export function PluginHost({ pluginName, componentName, props, navigate, bridgeExtension }: PluginHostProps) {
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

    const bridge = {
      ...makeBridgeForPlugin(pluginName, navigate),
      ...(bridgeExtension ?? {}),
    };
    return <Component {...(props ?? {})} bridge={bridge} />;
  }

  const styles = StyleSheet.create({
    center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 16 },
    err: { color: "#b91c1c", textAlign: "center" },
  });
  ```

- [ ] **Commit**

  ```bash
  git add mobile/src/plugins/PluginHost.tsx
  git commit -m "feat(map): add bridgeExtension prop to PluginHost"
  ```

---

## Task 8: Mobile — Rewrite `MapScreen`

**Files:**
- Modify: `mobile/src/screens/MapScreen.tsx`

- [ ] **Replace `MapScreen` with the generic plugin shell**

  Replace the entire contents of `mobile/src/screens/MapScreen.tsx`:

  ```typescript
  import React from "react";
  import { StyleSheet, View } from "react-native";

  import { Map } from "../core/Map";
  import { mapEventBus } from "../core/mapEventBus";
  import { makeMapBridgeExtension } from "../plugins/PluginBridge";
  import { PluginHost } from "../plugins/PluginHost";
  import { useLocation } from "../hooks/useLocation";
  import { useAppStore } from "../store/useAppStore";

  export function MapScreen() {
    useLocation(); // ensures location is written to the store
    const plugins = useAppStore((s) => s.plugins);
    const mapMarkers = useAppStore((s) => s.mapMarkers);
    const location = useAppStore((s) => s.location);

    const mapPlugins = plugins.filter((p) => p.map?.component);

    const region = location
      ? {
          latitude: location.lat,
          longitude: location.lng,
          latitudeDelta: 0.1,
          longitudeDelta: 0.1,
        }
      : undefined;

    const mapBridgeExtension = React.useMemo(() => makeMapBridgeExtension(), []);

    return (
      <View style={styles.container}>
        <Map
          region={region}
          markers={mapMarkers}
          onLongPress={(coord) => mapEventBus.emitLongPress(coord)}
          onMarkerPress={(marker) => mapEventBus.emitMarkerPress(marker)}
        />
        {mapPlugins.map((plugin) => (
          <View key={plugin.name} style={StyleSheet.absoluteFill} pointerEvents="box-none">
            <PluginHost
              pluginName={plugin.name}
              componentName={plugin.map!.component}
              bridgeExtension={mapBridgeExtension}
            />
          </View>
        ))}
      </View>
    );
  }

  const styles = StyleSheet.create({
    container: { flex: 1 },
  });
  ```

- [ ] **Commit**

  ```bash
  git add mobile/src/screens/MapScreen.tsx
  git commit -m "feat(map): rewrite MapScreen as generic plugin overlay shell"
  ```

---

## Task 9: Mobile — Conditional Map tab in `App.tsx`

**Files:**
- Modify: `mobile/App.tsx`

- [ ] **Read `plugins` from store and conditionally render the Map tab**

  In `mobile/App.tsx`, add the `useAppStore` read inside the `App` component and make the Map tab conditional. Replace the `App` function:

  ```typescript
  export default function App() {
    useHydrateSession();
    useHydratePlugins();
    const plugins = useAppStore((s) => s.plugins);
    const hasMapPlugin = plugins.some((p) => p.map?.component);

    return (
      <SafeAreaProvider>
        <NavigationContainer>
          <Tab.Navigator
            screenOptions={{
              headerStyle: { backgroundColor: "#2563eb" },
              headerTintColor: "#fff",
              tabBarActiveTintColor: "#2563eb",
            }}
          >
            <Tab.Screen name="Jain" component={ChatScreen} />
            {hasMapPlugin ? <Tab.Screen name="Map" component={MapScreen} /> : null}
            <Tab.Screen name="Skills" component={SkillsScreen} />
            <Tab.Screen name="Help" component={HelpScreen} />
            <Tab.Screen name="Settings" component={SettingsScreen} />
          </Tab.Navigator>
          <PluginOverlay />
        </NavigationContainer>
        <StatusBar style="light" />
      </SafeAreaProvider>
    );
  }
  ```

  Also add `useAppStore` to the imports at the top of `App.tsx`:

  ```typescript
  import { useAppStore } from "./src/store/useAppStore";
  ```

- [ ] **Commit**

  ```bash
  git add mobile/App.tsx
  git commit -m "feat(map): hide Map tab when no plugin declares map.component"
  ```

---

## Task 10: Plugin — `SightingPopup` component

**Files:**
- Create: `backend/app/plugins/yardsailing/components/SightingPopup.tsx`

- [ ] **Create the plugin-local sighting popup**

  Create `backend/app/plugins/yardsailing/components/SightingPopup.tsx`:

  ```typescript
  import React from "react";
  import {
    Linking,
    Modal,
    Platform,
    Pressable,
    StyleSheet,
    Text,
    View,
  } from "react-native";

  interface Sale {
    id: string;
    address: string;
    lat?: number | null;
    lng?: number | null;
    start_time?: string;
    end_time?: string;
    confirmations?: number;
  }

  export interface SightingPopupProps {
    sale: Sale | null;
    onClose: () => void;
  }

  function directionsUrl(sale: Sale): string {
    if (sale.lat != null && sale.lng != null) {
      const coords = `${sale.lat},${sale.lng}`;
      return Platform.OS === "ios"
        ? `https://maps.apple.com/?daddr=${coords}`
        : `https://www.google.com/maps/dir/?api=1&destination=${coords}`;
    }
    return "";
  }

  export function SightingPopup({ sale, onClose }: SightingPopupProps) {
    if (!sale) return null;
    const confirmed = (sale.confirmations ?? 1) >= 2;
    return (
      <Modal visible transparent animationType="fade" onRequestClose={onClose}>
        <Pressable style={styles.backdrop} onPress={onClose}>
          <Pressable style={styles.card} onPress={() => { /* swallow tap */ }}>
            <View
              style={[
                styles.badge,
                confirmed ? styles.badgeConfirmed : styles.badgeUnconfirmed,
              ]}
            >
              <Text style={styles.badgeText}>
                {confirmed ? "Confirmed" : "Unconfirmed"}
              </Text>
            </View>
            <Text style={styles.address}>{sale.address}</Text>
            {sale.start_time && sale.end_time ? (
              <Text style={styles.hours}>
                {sale.start_time} – {sale.end_time}
              </Text>
            ) : null}
            <Pressable
              style={styles.button}
              onPress={() => Linking.openURL(directionsUrl(sale))}
            >
              <Text style={styles.buttonText}>Get directions</Text>
            </Pressable>
            <Pressable style={styles.closeBtn} onPress={onClose}>
              <Text style={styles.closeText}>Close</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>
    );
  }

  const styles = StyleSheet.create({
    backdrop: {
      flex: 1,
      backgroundColor: "rgba(0,0,0,0.4)",
      justifyContent: "center",
      paddingHorizontal: 24,
    },
    card: { backgroundColor: "#fff", borderRadius: 14, padding: 20 },
    badge: {
      alignSelf: "flex-start",
      paddingHorizontal: 10,
      paddingVertical: 4,
      borderRadius: 10,
      marginBottom: 10,
    },
    badgeUnconfirmed: { backgroundColor: "#fef3c7" },
    badgeConfirmed: { backgroundColor: "#dcfce7" },
    badgeText: { fontSize: 12, fontWeight: "700", color: "#0f172a" },
    address: { fontSize: 15, color: "#0f172a", marginBottom: 4 },
    hours: { fontSize: 13, color: "#475569", marginBottom: 12 },
    button: {
      backgroundColor: "#2563eb",
      paddingVertical: 12,
      borderRadius: 10,
      alignItems: "center",
    },
    buttonText: { color: "#fff", fontWeight: "600", fontSize: 15 },
    closeBtn: { paddingVertical: 12, alignItems: "center", marginTop: 4 },
    closeText: { color: "#64748b", fontSize: 14 },
  });
  ```

- [ ] **Commit**

  ```bash
  git add backend/app/plugins/yardsailing/components/SightingPopup.tsx
  git commit -m "feat(yardsailing): add SightingPopup to plugin bundle"
  ```

---

## Task 11: Plugin — Simplified `SaleDetailsModal`

**Files:**
- Create: `backend/app/plugins/yardsailing/components/SaleDetailsModal.tsx`

- [ ] **Create the plugin-local sale details modal**

  This version drops `ManagePhotosSheet` (photos are shown read-only) and uses the bridge for `absUrl` and `getCurrentUserId`.

  Create `backend/app/plugins/yardsailing/components/SaleDetailsModal.tsx`:

  ```typescript
  import React from "react";
  import {
    Dimensions,
    Image,
    Linking,
    Modal,
    Platform,
    Pressable,
    ScrollView,
    StyleSheet,
    Text,
    View,
  } from "react-native";

  interface DayHours {
    day_date: string;
    start_time: string;
    end_time: string;
  }

  interface SalePhoto {
    id: string;
    url: string;
    position: number;
  }

  interface SaleGroup {
    id: string;
    name: string;
  }

  interface Sale {
    id: string;
    owner_id?: string;
    title: string;
    address: string;
    lat?: number | null;
    lng?: number | null;
    description?: string | null;
    start_date?: string;
    end_date?: string | null;
    start_time?: string;
    end_time?: string;
    tags?: string[];
    days?: DayHours[];
    photos?: SalePhoto[];
    groups?: SaleGroup[];
  }

  interface Bridge {
    absUrl: (path: string) => string;
    getCurrentUserId: () => string | null;
  }

  export interface SaleDetailsModalProps {
    sale: Sale | null;
    onClose: () => void;
    bridge: Bridge;
  }

  function directionsUrl(sale: Sale): string {
    if (sale.lat != null && sale.lng != null) {
      const coords = `${sale.lat},${sale.lng}`;
      return Platform.OS === "ios"
        ? `https://maps.apple.com/?daddr=${coords}`
        : `https://www.google.com/maps/dir/?api=1&destination=${coords}`;
    }
    const q = encodeURIComponent(sale.address);
    return Platform.OS === "ios"
      ? `https://maps.apple.com/?daddr=${q}`
      : `https://www.google.com/maps/dir/?api=1&destination=${q}`;
  }

  const SCREEN_WIDTH = Dimensions.get("window").width;

  export function SaleDetailsModal({ sale, onClose, bridge }: SaleDetailsModalProps) {
    if (!sale) return null;

    const days = sale.days ?? [];
    const isMultiDay = days.length > 1;
    const when = !isMultiDay
      ? sale.start_date
        ? sale.end_date && sale.end_date !== sale.start_date
          ? `${sale.start_date} – ${sale.end_date}`
          : sale.start_date
        : null
      : null;
    const hours =
      !isMultiDay && sale.start_time && sale.end_time
        ? `${sale.start_time} – ${sale.end_time}`
        : null;
    const photos = sale.photos ?? [];

    return (
      <Modal
        visible={sale !== null}
        transparent
        animationType="slide"
        onRequestClose={onClose}
      >
        <Pressable style={styles.backdrop} onPress={onClose}>
          <Pressable style={styles.sheet} onPress={() => { /* swallow */ }}>
            <ScrollView contentContainerStyle={styles.body}>
              {photos.length > 0 ? (
                <ScrollView
                  horizontal
                  pagingEnabled
                  showsHorizontalScrollIndicator={false}
                  style={styles.carousel}
                >
                  {photos.map((p) => (
                    <Image
                      key={p.id}
                      source={{ uri: bridge.absUrl(p.url) }}
                      style={[styles.carouselImage, { width: SCREEN_WIDTH - 24 }]}
                      resizeMode="cover"
                    />
                  ))}
                </ScrollView>
              ) : null}
              <Text style={styles.title}>{sale.title}</Text>
              <Text style={styles.address}>{sale.address}</Text>
              {when || hours ? (
                <Text style={styles.meta}>
                  {[when, hours].filter(Boolean).join(" · ")}
                </Text>
              ) : null}
              {isMultiDay ? (
                <View style={styles.schedule}>
                  {days.map((d) => (
                    <View key={d.day_date} style={styles.scheduleRow}>
                      <Text style={styles.scheduleDate}>{d.day_date}</Text>
                      <Text style={styles.scheduleHours}>
                        {d.start_time} – {d.end_time}
                      </Text>
                    </View>
                  ))}
                </View>
              ) : null}
              {sale.tags && sale.tags.length > 0 ? (
                <View style={styles.tagRow}>
                  {sale.tags.map((t) => (
                    <View key={t} style={styles.tagChip}>
                      <Text style={styles.tagText}>{t}</Text>
                    </View>
                  ))}
                </View>
              ) : null}
              {sale.groups && sale.groups.length > 0 ? (
                <View style={styles.tagRow}>
                  {sale.groups.map((g) => (
                    <View key={g.id} style={styles.groupChip}>
                      <Text style={styles.groupChipText}>{g.name}</Text>
                    </View>
                  ))}
                </View>
              ) : null}
              {sale.description ? (
                <Text style={styles.desc}>{sale.description}</Text>
              ) : null}
              <Pressable
                style={styles.button}
                onPress={() => Linking.openURL(directionsUrl(sale))}
              >
                <Text style={styles.buttonText}>Get directions</Text>
              </Pressable>
              <Pressable style={styles.closeBtn} onPress={onClose}>
                <Text style={styles.closeText}>Close</Text>
              </Pressable>
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    );
  }

  const styles = StyleSheet.create({
    backdrop: {
      flex: 1,
      backgroundColor: "rgba(0,0,0,0.4)",
      justifyContent: "flex-end",
    },
    sheet: {
      backgroundColor: "#fff",
      borderTopLeftRadius: 16,
      borderTopRightRadius: 16,
      maxHeight: "70%",
    },
    body: { padding: 20 },
    title: { fontSize: 20, fontWeight: "700", marginBottom: 4 },
    address: { fontSize: 15, color: "#475569", marginBottom: 8 },
    meta: { fontSize: 13, color: "#64748b", marginBottom: 12 },
    desc: { fontSize: 15, color: "#1f2937", marginBottom: 16, lineHeight: 22 },
    button: {
      backgroundColor: "#2563eb",
      paddingVertical: 14,
      borderRadius: 10,
      alignItems: "center",
      marginTop: 8,
    },
    buttonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
    closeBtn: { paddingVertical: 14, alignItems: "center", marginTop: 8 },
    closeText: { color: "#64748b", fontSize: 15 },
    schedule: {
      backgroundColor: "#f8fafc",
      borderRadius: 10,
      borderWidth: 1,
      borderColor: "#e2e8f0",
      paddingVertical: 8,
      paddingHorizontal: 12,
      marginBottom: 16,
    },
    scheduleRow: {
      flexDirection: "row",
      justifyContent: "space-between",
      paddingVertical: 4,
    },
    scheduleDate: { fontSize: 14, color: "#334155", fontWeight: "600" },
    scheduleHours: { fontSize: 14, color: "#475569" },
    tagRow: { flexDirection: "row", flexWrap: "wrap", marginBottom: 16 },
    tagChip: {
      backgroundColor: "#eff6ff",
      borderRadius: 12,
      paddingHorizontal: 10,
      paddingVertical: 4,
      marginRight: 6,
      marginBottom: 6,
      borderWidth: 1,
      borderColor: "#bfdbfe",
    },
    tagText: {
      fontSize: 12,
      color: "#1d4ed8",
      fontWeight: "600",
      textTransform: "capitalize",
    },
    groupChip: {
      backgroundColor: "#ede9fe",
      paddingHorizontal: 10,
      paddingVertical: 4,
      borderRadius: 12,
      marginRight: 6,
      marginTop: 4,
    },
    groupChipText: { fontSize: 12, color: "#6d28d9", fontWeight: "600" },
    carousel: { height: 240, marginBottom: 12 },
    carouselImage: { height: 240, borderRadius: 12, marginRight: 8 },
  });
  ```

- [ ] **Commit**

  ```bash
  git add backend/app/plugins/yardsailing/components/SaleDetailsModal.tsx
  git commit -m "feat(yardsailing): add simplified SaleDetailsModal to plugin bundle"
  ```

---

## Task 12: Plugin — `YardsailingMapLayer`

**Files:**
- Create: `backend/app/plugins/yardsailing/components/YardsailingMapLayer.tsx`

- [ ] **Create the main map overlay component**

  Create `backend/app/plugins/yardsailing/components/YardsailingMapLayer.tsx`:

  ```typescript
  import React from "react";
  import {
    ActivityIndicator,
    Modal,
    Pressable,
    ScrollView,
    StyleSheet,
    Text,
    View,
  } from "react-native";

  import { SaleDetailsModal } from "./SaleDetailsModal";
  import { SightingPopup } from "./SightingPopup";

  // ─── Local types (no core imports allowed in plugin bundles) ─────────────────

  interface MapMarker {
    id: string;
    lat: number;
    lng: number;
    color?: string;
    title?: string;
    description?: string;
    data?: unknown;
  }

  interface DayHours {
    day_date: string;
    start_time: string;
    end_time: string;
  }

  interface SalePhoto {
    id: string;
    url: string;
    position: number;
  }

  interface SaleGroup {
    id: string;
    name: string;
    slug: string;
  }

  interface Sale {
    id: string;
    owner_id?: string;
    title: string;
    address: string;
    lat?: number | null;
    lng?: number | null;
    description?: string | null;
    start_date?: string;
    end_date?: string | null;
    start_time?: string;
    end_time?: string;
    tags?: string[];
    days?: DayHours[];
    photos?: SalePhoto[];
    source?: "host" | "sighting";
    confirmations?: number;
    groups?: SaleGroup[];
  }

  interface SaleGroupSummary {
    id: string;
    name: string;
    slug: string;
  }

  interface MapLayerBridge {
    callPluginApi: (path: string, method: string, body?: unknown) => Promise<unknown>;
    showToast: (msg: string) => void;
    absUrl: (path: string) => string;
    getCurrentUserId: () => string | null;
    setMarkers: (markers: MapMarker[]) => void;
    onLongPress: (cb: (coord: { lat: number; lng: number }) => void) => void;
    offLongPress: (cb: (coord: { lat: number; lng: number }) => void) => void;
    onMarkerPress: (cb: (marker: MapMarker) => void) => void;
    offMarkerPress: (cb: (marker: MapMarker) => void) => void;
    getLocation: () => { lat: number; lng: number } | null;
  }

  // ─── Helpers ─────────────────────────────────────────────────────────────────

  function pad2(n: number): string {
    return n < 10 ? `0${n}` : String(n);
  }

  function nowHHMM(): string {
    const d = new Date();
    return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
  }

  function toMapMarker(sale: Sale): MapMarker {
    let color = "#2563eb";
    if (sale.source === "sighting") {
      color = (sale.confirmations ?? 1) >= 2 ? "#16a34a" : "#f59e0b";
    }
    return {
      id: sale.id,
      lat: sale.lat ?? 0,
      lng: sale.lng ?? 0,
      color,
      title: sale.title,
      description: sale.address,
      data: sale,
    };
  }

  // ─── Chip sub-component ───────────────────────────────────────────────────────

  function Chip({
    label,
    active,
    onPress,
    accent,
  }: {
    label: string;
    active: boolean;
    onPress: () => void;
    accent?: boolean;
  }) {
    return (
      <Pressable
        onPress={onPress}
        style={[
          styles.chip,
          active && (accent ? styles.chipActiveAccent : styles.chipActive),
        ]}
      >
        <Text style={[styles.chipText, active && styles.chipTextActive]}>
          {label}
        </Text>
      </Pressable>
    );
  }

  // ─── Main component ───────────────────────────────────────────────────────────

  export interface YardsailingMapLayerProps {
    bridge: MapLayerBridge;
  }

  export function YardsailingMapLayer({ bridge }: YardsailingMapLayerProps) {
    const [activeTags, setActiveTags] = React.useState<string[]>([]);
    const [happeningNow, setHappeningNow] = React.useState(false);
    const [activeGroup, setActiveGroup] = React.useState<SaleGroupSummary | null>(null);
    const [availableTags, setAvailableTags] = React.useState<string[]>([]);
    const [availableGroups, setAvailableGroups] = React.useState<SaleGroupSummary[]>([]);
    const [groupSheetOpen, setGroupSheetOpen] = React.useState(false);
    const [loading, setLoading] = React.useState(false);
    const [pendingDrop, setPendingDrop] = React.useState<{ lat: number; lng: number } | null>(null);
    const [dropping, setDropping] = React.useState(false);
    const [selectedSale, setSelectedSale] = React.useState<Sale | null>(null);
    const [selectedSighting, setSelectedSighting] = React.useState<Sale | null>(null);

    // ── Load curated tags and groups once ──────────────────────────────────────
    React.useEffect(() => {
      bridge
        .callPluginApi("/api/plugins/yardsailing/tags", "GET", null)
        .then((res: unknown) => {
          if (res && typeof res === "object" && "tags" in res) {
            setAvailableTags((res as { tags: string[] }).tags);
          }
        })
        .catch(() => {});

      bridge
        .callPluginApi("/api/plugins/yardsailing/groups", "GET", null)
        .then((res: unknown) => {
          setAvailableGroups(Array.isArray(res) ? (res as SaleGroupSummary[]) : []);
        })
        .catch(() => {});
    }, [bridge]);

    // ── Fetch sales and push markers whenever filters change ───────────────────
    const loadSales = React.useCallback(async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        activeTags.forEach((t) => params.append("tag", t));
        if (happeningNow) params.set("happening_now", "1");
        if (activeGroup) params.set("group_id", activeGroup.id);
        const qs = params.toString();
        const path = `/api/plugins/yardsailing/sales/recent${qs ? `?${qs}` : ""}`;
        const res = await bridge.callPluginApi(path, "GET", null);
        const sales = Array.isArray(res) ? (res as Sale[]) : [];
        bridge.setMarkers(
          sales
            .filter((s) => s.lat != null && s.lng != null)
            .map(toMapMarker),
        );
      } catch {
        // silent — map shows stale data on error
      } finally {
        setLoading(false);
      }
    }, [bridge, activeTags, happeningNow, activeGroup]);

    React.useEffect(() => {
      loadSales();
    }, [loadSales]);

    // ── Subscribe to map events ─────────────────────────────────────────────────
    React.useEffect(() => {
      const handleLongPress = (coord: { lat: number; lng: number }) => {
        const hh = parseInt(nowHHMM().slice(0, 2), 10);
        if (hh >= 17) return;
        setPendingDrop(coord);
      };

      const handleMarkerPress = (marker: MapMarker) => {
        const sale = marker.data as Sale;
        if (sale.source === "sighting") {
          setSelectedSighting(sale);
        } else {
          setSelectedSale(sale);
        }
      };

      bridge.onLongPress(handleLongPress);
      bridge.onMarkerPress(handleMarkerPress);

      return () => {
        bridge.offLongPress(handleLongPress);
        bridge.offMarkerPress(handleMarkerPress);
        bridge.setMarkers([]);
      };
    }, [bridge]);

    // ── Drop-pin handlers ───────────────────────────────────────────────────────
    const confirmDrop = async () => {
      if (!pendingDrop) return;
      setDropping(true);
      try {
        await bridge.callPluginApi("/api/plugins/yardsailing/sightings", "POST", {
          lat: pendingDrop.lat,
          lng: pendingDrop.lng,
          now_hhmm: nowHHMM(),
        });
        setPendingDrop(null);
        await loadSales();
      } catch {
        bridge.showToast("Failed to drop pin. Try again.");
      } finally {
        setDropping(false);
      }
    };

    const handleDropPinFab = () => {
      const hh = parseInt(nowHHMM().slice(0, 2), 10);
      if (hh >= 17) {
        bridge.showToast("Sale drop closed after 5 PM.");
        return;
      }
      const loc = bridge.getLocation();
      if (!loc) {
        bridge.showToast("Location unavailable.");
        return;
      }
      setPendingDrop(loc);
    };

    // ─────────────────────────────────────────────────────────────────────────────

    return (
      <View style={styles.overlay} pointerEvents="box-none">

        {/* ── Filter bar ──────────────────────────────────────────────────────── */}
        <View style={styles.filterBar} pointerEvents="auto">
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chipRow}
          >
            <Chip
              label="Now"
              active={happeningNow}
              onPress={() => setHappeningNow((v) => !v)}
              accent
            />
            <Chip
              label={activeGroup ? activeGroup.name : "Groups"}
              active={!!activeGroup}
              onPress={() => setGroupSheetOpen(true)}
            />
            {availableTags.map((tag) => (
              <Chip
                key={tag}
                label={tag}
                active={activeTags.includes(tag)}
                onPress={() =>
                  setActiveTags((prev) =>
                    prev.includes(tag)
                      ? prev.filter((t) => t !== tag)
                      : [...prev, tag],
                  )
                }
              />
            ))}
          </ScrollView>
          {activeTags.length > 0 || happeningNow || activeGroup ? (
            <Pressable
              style={styles.clearBtn}
              onPress={() => {
                setActiveTags([]);
                setHappeningNow(false);
                setActiveGroup(null);
              }}
            >
              <Text style={styles.clearText}>Clear</Text>
            </Pressable>
          ) : null}
        </View>

        {/* ── Drop-Pin FAB (above Refresh) ─────────────────────────────────── */}
        <Pressable
          style={[styles.fab, styles.fabDrop]}
          onPress={handleDropPinFab}
          pointerEvents="auto"
          accessibilityLabel="Drop a pin"
        >
          <Text style={styles.fabText}>📍</Text>
        </Pressable>

        {/* ── Refresh FAB ──────────────────────────────────────────────────── */}
        <Pressable
          style={styles.fab}
          onPress={loadSales}
          disabled={loading}
          pointerEvents="auto"
          accessibilityLabel="Refresh sales"
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.fabText}>↻</Text>
          )}
        </Pressable>

        {/* ── Modals ───────────────────────────────────────────────────────── */}
        <SaleDetailsModal
          sale={selectedSale}
          onClose={() => setSelectedSale(null)}
          bridge={bridge}
        />
        <SightingPopup
          sale={selectedSighting}
          onClose={() => setSelectedSighting(null)}
        />

        {/* ── Sighting drop confirmation ────────────────────────────────────── */}
        <Modal
          transparent
          animationType="fade"
          visible={pendingDrop !== null}
          onRequestClose={() => setPendingDrop(null)}
        >
          <View style={styles.dropBackdrop}>
            <Pressable
              style={StyleSheet.absoluteFill}
              onPress={() => !dropping && setPendingDrop(null)}
            />
            <View style={styles.dropCard}>
              <Text style={styles.dropTitle}>Drop unconfirmed sale?</Text>
              {pendingDrop ? (
                <Text style={styles.dropCoords}>
                  {pendingDrop.lat.toFixed(5)}, {pendingDrop.lng.toFixed(5)}
                </Text>
              ) : null}
              <Text style={styles.dropHint}>
                If someone else drops a pin here too, it'll be marked Confirmed.
              </Text>
              <Pressable
                style={[styles.dropBtn, dropping && { opacity: 0.6 }]}
                disabled={dropping || !pendingDrop}
                onPress={confirmDrop}
              >
                <Text style={styles.dropBtnText}>
                  {dropping ? "Dropping…" : "Drop pin"}
                </Text>
              </Pressable>
              <Pressable
                style={styles.dropCancel}
                onPress={() => !dropping && setPendingDrop(null)}
              >
                <Text style={styles.dropCancelText}>Cancel</Text>
              </Pressable>
            </View>
          </View>
        </Modal>

        {/* ── Groups picker ─────────────────────────────────────────────────── */}
        <Modal
          transparent
          animationType="slide"
          visible={groupSheetOpen}
          onRequestClose={() => setGroupSheetOpen(false)}
        >
          <View style={styles.groupBackdrop}>
            <Pressable
              style={StyleSheet.absoluteFill}
              onPress={() => setGroupSheetOpen(false)}
            />
            <View style={styles.groupSheet}>
              <Text style={styles.groupTitle}>Filter by Group</Text>
              <Pressable
                style={styles.groupRow}
                onPress={() => {
                  setActiveGroup(null);
                  setGroupSheetOpen(false);
                }}
              >
                <Text
                  style={[
                    styles.groupName,
                    !activeGroup && styles.groupNameActive,
                  ]}
                >
                  All groups
                </Text>
              </Pressable>
              {availableGroups.map((g) => (
                <Pressable
                  key={g.id}
                  style={styles.groupRow}
                  onPress={() => {
                    setActiveGroup(g);
                    setGroupSheetOpen(false);
                  }}
                >
                  <Text
                    style={[
                      styles.groupName,
                      activeGroup?.id === g.id && styles.groupNameActive,
                    ]}
                  >
                    {g.name}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
        </Modal>
      </View>
    );
  }

  // ─── Styles ──────────────────────────────────────────────────────────────────

  const styles = StyleSheet.create({
    overlay: { ...StyleSheet.absoluteFillObject },
    filterBar: {
      flexDirection: "row",
      alignItems: "center",
      backgroundColor: "#fff",
      borderBottomWidth: 1,
      borderBottomColor: "#e2e8f0",
    },
    chipRow: { paddingHorizontal: 10, paddingVertical: 8, gap: 6 },
    chip: {
      paddingHorizontal: 12,
      paddingVertical: 6,
      borderRadius: 16,
      borderWidth: 1,
      borderColor: "#cbd5e1",
      backgroundColor: "#f8fafc",
      marginRight: 6,
    },
    chipActive: { backgroundColor: "#2563eb", borderColor: "#2563eb" },
    chipActiveAccent: { backgroundColor: "#16a34a", borderColor: "#16a34a" },
    chipText: { fontSize: 13, color: "#334155", fontWeight: "600" },
    chipTextActive: { color: "#fff" },
    clearBtn: { paddingHorizontal: 10, paddingVertical: 8 },
    clearText: { color: "#64748b", fontSize: 13, fontWeight: "600" },
    fab: {
      position: "absolute",
      right: 16,
      bottom: 24,
      width: 52,
      height: 52,
      borderRadius: 26,
      backgroundColor: "#2563eb",
      alignItems: "center",
      justifyContent: "center",
      shadowColor: "#000",
      shadowOpacity: 0.2,
      shadowRadius: 6,
      shadowOffset: { width: 0, height: 2 },
      elevation: 4,
    },
    fabDrop: { bottom: 88 },
    fabText: { color: "#fff", fontSize: 24, lineHeight: 26, fontWeight: "700" },
    dropBackdrop: {
      flex: 1,
      backgroundColor: "rgba(0,0,0,0.5)",
      justifyContent: "center",
      paddingHorizontal: 24,
    },
    dropCard: { backgroundColor: "#fff", borderRadius: 14, padding: 20 },
    dropTitle: { fontSize: 18, fontWeight: "700", marginBottom: 8 },
    dropCoords: { fontSize: 14, color: "#475569", marginBottom: 8 },
    dropHint: { fontSize: 13, color: "#64748b", marginBottom: 16 },
    dropBtn: {
      backgroundColor: "#f59e0b",
      paddingVertical: 12,
      borderRadius: 10,
      alignItems: "center",
    },
    dropBtnText: { color: "#fff", fontSize: 15, fontWeight: "700" },
    dropCancel: { paddingVertical: 12, alignItems: "center", marginTop: 4 },
    dropCancelText: { color: "#64748b", fontSize: 14 },
    groupBackdrop: {
      flex: 1,
      backgroundColor: "rgba(0,0,0,0.4)",
      justifyContent: "flex-end",
    },
    groupSheet: {
      backgroundColor: "#fff",
      borderTopLeftRadius: 16,
      borderTopRightRadius: 16,
      padding: 20,
      paddingBottom: 36,
    },
    groupTitle: {
      fontSize: 17,
      fontWeight: "700",
      marginBottom: 14,
      color: "#0f172a",
    },
    groupRow: { paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#f1f5f9" },
    groupName: { fontSize: 15, color: "#334155" },
    groupNameActive: { color: "#2563eb", fontWeight: "700" },
  });
  ```

- [ ] **Commit**

  ```bash
  git add backend/app/plugins/yardsailing/components/YardsailingMapLayer.tsx
  git commit -m "feat(yardsailing): add YardsailingMapLayer overlay component"
  ```

---

## Task 13: Plugin — Register + update `plugin.json` + rebuild bundle

**Files:**
- Modify: `backend/app/plugins/yardsailing/components/index.ts`
- Modify: `backend/app/plugins/yardsailing/plugin.json`
- Rebuild bundle

- [ ] **Register `YardsailingMapLayer` in `index.ts`**

  Replace the entire contents of `backend/app/plugins/yardsailing/components/index.ts`:

  ```typescript
  import { SaleForm } from "./SaleForm";
  import { YardsailingHome } from "./YardsailingHome";
  import { YardsailingMapLayer } from "./YardsailingMapLayer";

  declare const globalThis: {
    JainPlugins?: Record<string, Record<string, unknown>>;
  };

  globalThis.JainPlugins = globalThis.JainPlugins || {};
  globalThis.JainPlugins.yardsailing = {
    SaleForm,
    YardsailingHome,
    YardsailingMapLayer,
  };

  export { SaleForm, YardsailingHome, YardsailingMapLayer };
  ```

- [ ] **Add `map` field and `YardsailingMapLayer` export to `plugin.json`**

  Edit `backend/app/plugins/yardsailing/plugin.json`. Update `components.exports` and add the `map` field:

  ```json
  {
    "name": "yardsailing",
    "version": "1.0.0",
    "description": "Find, create, and manage yard sales",
    "author": "jim shelly",
    "type": "internal",
    "skills": [
      {
        "name": "find-sales",
        "description": "Find yard sales near a location. Use when user asks about sales, garage sales, or estate sales nearby.",
        "tools": ["find_yard_sales"]
      },
      {
        "name": "create-sale",
        "description": "Help user create a yard sale listing. Gather info conversationally or present a form.",
        "tools": ["create_yard_sale", "show_sale_form"],
        "components": ["SaleForm"]
      }
    ],
    "components": {
      "bundle": "bundle/yardsailing.js",
      "exports": ["SaleForm", "YardsailingHome", "YardsailingMapLayer"]
    },
    "map": {
      "component": "YardsailingMapLayer"
    },
    "home": {
      "component": "YardsailingHome",
      "label": "Yardsailing",
      "icon": "storefront-outline",
      "description": "Find, drop pins, and manage your yard sales."
    },
    "examples": [
      {
        "prompt": "Show me yard sales near me",
        "description": "Lists upcoming sales within 25 miles"
      },
      {
        "prompt": "Find yard sales near me with baby items",
        "description": "Filter by tag — try toys, tools, furniture, etc."
      },
      {
        "prompt": "What yard sales are happening right now?",
        "description": "Only sales currently open"
      },
      {
        "prompt": "I want to create a yard sale",
        "description": "Opens the sale creation form"
      },
      {
        "prompt": "Find yard sales in the 100 Mile Yard Sale",
        "description": "Filter the map by a named group/event"
      }
    ]
  }
  ```

- [ ] **Rebuild the plugin bundle**

  ```bash
  cd backend/app/plugins/yardsailing && node build.mjs
  ```

  Expected output:
  ```
  [yardsailing] built .../bundle/yardsailing.js
  ```

- [ ] **Commit**

  ```bash
  git add backend/app/plugins/yardsailing/components/index.ts \
          backend/app/plugins/yardsailing/plugin.json \
          backend/app/plugins/yardsailing/bundle/yardsailing.js
  git commit -m "feat(yardsailing): register YardsailingMapLayer; add map declaration to plugin.json"
  ```

---

## Task 14: Cleanup

**Files:**
- Delete: `mobile/src/core/SightingPopup.tsx`

- [ ] **Delete the now-unused core `SightingPopup`**

  ```bash
  rm mobile/src/core/SightingPopup.tsx
  ```

  Verify nothing else imports it:

  ```bash
  grep -r "SightingPopup" mobile/src --include="*.tsx" --include="*.ts"
  ```

  Expected: no output (only the plugin bundle's version remains, which is not in `mobile/src`).

- [ ] **Commit**

  ```bash
  git add -A
  git commit -m "chore: remove SightingPopup from core (moved to yardsailing plugin bundle)"
  ```

---

## Task 15: Integration test

- [ ] **Start the backend**

  ```bash
  cd backend && .venv/Scripts/uvicorn app.main:app --reload
  ```

- [ ] **Start the mobile app**

  ```bash
  cd mobile && npx expo start
  ```

- [ ] **Verify Map tab visibility**

  With yardsailing enabled (`backend/app/plugins/yardsailing/` present, not `_yardsailing`):
  - Map tab should appear in the bottom nav.

  To verify tab disappears: rename `yardsailing` → `_yardsailing`, restart backend, reload app.
  - Map tab should be gone.
  - Rename back.

- [ ] **Verify filter chips**

  Open the Map tab. Confirm the filter bar appears at the top with "Now", "Groups", and any available tags.

- [ ] **Verify sales markers**

  If sales exist in the database with lat/lng, confirm pins appear on the map.

- [ ] **Verify Drop-Pin FAB**

  Tap the 📍 FAB. Confirm the sighting drop modal appears pre-filled with current coordinates.
  Tap "Drop pin" and confirm the sighting is submitted and map refreshes.

- [ ] **Verify long-press still works**

  Long-press on the map. Confirm the same sighting drop modal appears with the tapped coordinates.

- [ ] **Verify pin tap opens correct modal**

  Tap a blue (host) pin → `SaleDetailsModal` should appear.
  Tap an orange/green (sighting) pin → `SightingPopup` should appear.

- [ ] **Final commit**

  ```bash
  git add -A
  git commit -m "chore: integration verified — map plugin overlay complete"
  ```
