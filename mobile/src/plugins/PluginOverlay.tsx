import React from "react";
import {
  Modal,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { useAppStore } from "../store/useAppStore";
import { PluginHost } from "./PluginHost";

// The modal lives above the tab navigator so plugin components opened
// via bridge.openComponent (e.g. YardsailingHome → SaleForm) are visible
// no matter which tab is currently active. Previously this modal was
// inside ChatScreen, so tapping Create yard sale from the Skills tab
// silently did nothing until Chat had been mounted.
export function PluginOverlay() {
  const activeComponent = useAppStore((s) => s.activeComponent);
  const hideComponent = useAppStore((s) => s.hideComponent);

  return (
    <Modal
      visible={activeComponent !== null}
      animationType="slide"
      onRequestClose={hideComponent}
    >
      <View style={styles.header}>
        <TouchableOpacity onPress={hideComponent}>
          <Text style={styles.close}>Close</Text>
        </TouchableOpacity>
      </View>
      {activeComponent ? (
        <PluginHost
          pluginName={activeComponent.plugin}
          componentName={activeComponent.name}
          props={{ initialData: activeComponent.props }}
        />
      ) : null}
    </Modal>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingTop: 50,
    paddingHorizontal: 16,
    paddingBottom: 12,
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  close: { color: "#2563eb", fontSize: 16 },
});
