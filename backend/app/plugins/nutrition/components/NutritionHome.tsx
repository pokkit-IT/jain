import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

interface Profile {
  calorie_target: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

interface MealItem {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

interface Meal {
  id: string;
  raw_input: string;
  items: MealItem[];
}

export interface NutritionHomeProps {
  bridge: {
    callPluginApi: (path: string, method: string, body: unknown) => Promise<unknown>;
    navigateToChat?: (prefill?: string) => void;
    showToast: (msg: string) => void;
  };
}

export function NutritionHome({ bridge }: NutritionHomeProps) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [meals, setMeals] = useState<Meal[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [profileRes, mealsRes] = await Promise.all([
        bridge.callPluginApi("/api/plugins/nutrition/profile", "GET", null),
        bridge.callPluginApi("/api/plugins/nutrition/meals/today", "GET", null),
      ]);
      setProfile(profileRes as Profile);
      // /meals/today returns { "meals": [...] }
      const mealsData = (mealsRes as { meals: Meal[] }).meals ?? [];
      setMeals(mealsData);
    } catch (e) {
      setError((e as Error).message || "Could not load nutrition data.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [bridge]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    void load();
  }, [load]);

  useEffect(() => {
    void load();
  }, [load]);

  const totals = (meals ?? []).reduce(
    (acc, meal) => {
      for (const item of meal.items) {
        acc.calories += item.calories;
        acc.protein += item.protein_g;
        acc.carbs += item.carbs_g;
        acc.fat += item.fat_g;
      }
      return acc;
    },
    { calories: 0, protein: 0, carbs: 0, fat: 0 },
  );

  // Profile always has non-zero defaults (2000 cal etc.), so hasTargets is
  // true for all users in practice. The banner is a safety net for zero-target edge cases.
  const hasTargets = profile != null && profile.calorie_target > 0;

  const goToChat = (prefill: string) => {
    if (bridge.navigateToChat) {
      bridge.navigateToChat(prefill);
    } else {
      bridge.showToast("Open Chat to continue.");
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Could not load nutrition data.</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      {/* Macro cards — no header label */}
      <View style={styles.cardsRow}>
        <MacroCard
          value={Math.round(totals.calories)}
          target={profile?.calorie_target ?? 0}
          label="cal"
          color="#e0f2fe"
          textColor="#0369a1"
        />
        <MacroCard
          value={Math.round(totals.protein)}
          target={profile?.protein_g ?? 0}
          label="protein"
          unit="g"
          color="#dcfce7"
          textColor="#15803d"
        />
        <MacroCard
          value={Math.round(totals.carbs)}
          target={profile?.carbs_g ?? 0}
          label="carbs"
          unit="g"
          color="#fef3c7"
          textColor="#b45309"
        />
        <MacroCard
          value={Math.round(totals.fat)}
          target={profile?.fat_g ?? 0}
          label="fat"
          unit="g"
          color="#fce7f3"
          textColor="#9d174d"
        />
      </View>

      {/* Targets entry point */}
      {!hasTargets ? (
        <Pressable
          style={styles.setupBanner}
          onPress={() => goToChat("Help me figure out my macro targets")}
        >
          <Text style={styles.setupBannerText}>
            Set your macro targets — tap to get started.
          </Text>
        </Pressable>
      ) : (
        <Pressable onPress={() => goToChat("I want to update my macro targets")}>
          <Text style={styles.manageLink}>Manage targets</Text>
        </Pressable>
      )}

      {/* Meal list */}
      {meals != null && meals.length === 0 ? (
        <Text style={styles.emptyText}>No meals logged yet.</Text>
      ) : (
        meals?.map((meal) => {
          const cal = Math.round(meal.items.reduce((s, i) => s + i.calories, 0));
          const protein = Math.round(
            meal.items.reduce((s, i) => s + i.protein_g, 0),
          );
          return (
            <View key={meal.id} style={styles.mealRow}>
              <Text style={styles.mealName} numberOfLines={1}>
                {meal.raw_input}
              </Text>
              <Text style={styles.mealMeta}>
                {cal} cal · {protein}g protein
              </Text>
            </View>
          );
        })
      )}

      {/* Log a meal */}
      <Pressable
        style={styles.logBtn}
        onPress={() => goToChat("Log meal: ")}
      >
        <Text style={styles.logBtnText}>+ Log a meal</Text>
      </Pressable>
    </ScrollView>
  );
}

interface MacroCardProps {
  value: number;
  target: number;
  label: string;
  unit?: string;
  color: string;
  textColor: string;
}

function MacroCard({
  value,
  target,
  label,
  unit = "",
  color,
  textColor,
}: MacroCardProps) {
  return (
    <View style={[styles.card, { backgroundColor: color }]}>
      <Text style={[styles.cardValue, { color: textColor }]}>
        {value}
        {unit}
      </Text>
      {target > 0 ? (
        <Text style={styles.cardTarget}>
          / {target}
          {unit} {label}
        </Text>
      ) : (
        <Text style={styles.cardTarget}>{label}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  content: { padding: 12 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  errorText: { color: "#b91c1c", textAlign: "center", fontSize: 14 },
  cardsRow: { flexDirection: "row", gap: 6, marginBottom: 12 },
  card: { flex: 1, borderRadius: 8, padding: 10, alignItems: "center" },
  cardValue: { fontSize: 16, fontWeight: "700" },
  cardTarget: {
    fontSize: 9,
    color: "#475569",
    marginTop: 2,
    textAlign: "center",
  },
  setupBanner: {
    backgroundColor: "#eff6ff",
    borderWidth: 1,
    borderColor: "#bfdbfe",
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  setupBannerText: {
    color: "#1d4ed8",
    fontSize: 14,
    fontWeight: "600",
    textAlign: "center",
  },
  manageLink: {
    color: "#2563eb",
    fontSize: 13,
    fontWeight: "600",
    textAlign: "right",
    marginBottom: 12,
  },
  emptyText: {
    color: "#64748b",
    fontSize: 14,
    textAlign: "center",
    paddingVertical: 24,
  },
  mealRow: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  mealName: { fontSize: 14, fontWeight: "600", color: "#0f172a" },
  mealMeta: { fontSize: 12, color: "#64748b", marginTop: 2 },
  logBtn: {
    backgroundColor: "#f0fdf4",
    borderWidth: 1,
    borderColor: "#86efac",
    borderStyle: "dashed",
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
    marginTop: 8,
  },
  logBtnText: { color: "#16a34a", fontSize: 14, fontWeight: "700" },
});
