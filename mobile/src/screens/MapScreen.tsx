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
