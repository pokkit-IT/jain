import React from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";

interface ChoiceButtonsProps {
  choices: string[];
  onChoose: (label: string) => void;
}

export function ChoiceButtons({ choices, onChoose }: ChoiceButtonsProps) {
  return (
    <View style={styles.container}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scroll}
      >
        {choices.map((label) => (
          <TouchableOpacity
            key={label}
            style={styles.pill}
            onPress={() => onChoose(label)}
          >
            <Text style={styles.pillText}>{label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderTopWidth: 1,
    borderTopColor: "#e2e8f0",
    backgroundColor: "#fff",
    paddingVertical: 8,
  },
  scroll: {
    paddingHorizontal: 8,
    gap: 8,
  },
  pill: {
    borderWidth: 1.5,
    borderColor: "#2563eb",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: "#fff",
  },
  pillText: {
    color: "#2563eb",
    fontSize: 14,
    fontWeight: "500",
  },
});
