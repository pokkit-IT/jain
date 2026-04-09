import React from "react";
import { StyleSheet, View, Text } from "react-native";
import MapView, { Marker, Region } from "react-native-maps";

import { Sale } from "../types";

export interface MapProps {
  region?: Region;
  sales: Sale[];
  onPinPress?: (sale: Sale) => void;
}

export function Map({ region, sales, onPinPress }: MapProps) {
  if (!region) {
    return (
      <View style={[styles.container, styles.empty]}>
        <Text>Waiting for location...</Text>
      </View>
    );
  }

  return (
    <MapView style={styles.container} initialRegion={region}>
      {sales.map((sale) => (
        <Marker
          key={sale.id}
          coordinate={{ latitude: sale.lat, longitude: sale.lng }}
          title={sale.title}
          description={sale.address}
          onPress={() => onPinPress?.(sale)}
        />
      ))}
    </MapView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  empty: { alignItems: "center", justifyContent: "center" },
});
