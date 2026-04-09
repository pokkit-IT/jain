import React from "react";
import { FlatList, StyleSheet, Text, View } from "react-native";

import { PreviewCard } from "./PreviewCard";

export interface CardListItem {
  id: string | number;
  title: string;
  subtitle?: string;
  body?: string;
}

export interface CardListProps {
  items: CardListItem[];
  onItemPress?: (item: CardListItem) => void;
  emptyText?: string;
}

export function CardList({ items, onItemPress, emptyText = "No items" }: CardListProps) {
  if (items.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>{emptyText}</Text>
      </View>
    );
  }

  return (
    <FlatList
      style={styles.list}
      data={items}
      keyExtractor={(i) => String(i.id)}
      renderItem={({ item }) => (
        <PreviewCard
          title={item.title}
          subtitle={item.subtitle}
          body={item.body}
          onPress={onItemPress ? () => onItemPress(item) : undefined}
        />
      )}
    />
  );
}

const styles = StyleSheet.create({
  list: { flex: 1, padding: 12 },
  empty: { flex: 1, alignItems: "center", justifyContent: "center" },
  emptyText: { color: "#64748b" },
});
