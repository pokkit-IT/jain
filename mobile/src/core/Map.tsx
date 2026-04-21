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
