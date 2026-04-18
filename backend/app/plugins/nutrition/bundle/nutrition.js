(() => {
  var __create = Object.create;
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __getProtoOf = Object.getPrototypeOf;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __require = /* @__PURE__ */ ((x) => typeof require !== "undefined" ? require : typeof Proxy !== "undefined" ? new Proxy(x, {
    get: (a, b) => (typeof require !== "undefined" ? require : a)[b]
  }) : x)(function(x) {
    if (typeof require !== "undefined") return require.apply(this, arguments);
    throw Error('Dynamic require of "' + x + '" is not supported');
  });
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toESM = (mod) => mod;
  var __async = (__this, __arguments, generator) => {
    return new Promise((resolve, reject) => {
      var fulfilled = (value) => {
        try {
          step(generator.next(value));
        } catch (e) {
          reject(e);
        }
      };
      var rejected = (value) => {
        try {
          step(generator.throw(value));
        } catch (e) {
          reject(e);
        }
      };
      var step = (x) => x.done ? resolve(x.value) : Promise.resolve(x.value).then(fulfilled, rejected);
      step((generator = generator.apply(__this, __arguments)).next());
    });
  };

  // components/NutritionHome.tsx
  var import_react = __toESM(__require("react"), 1);
  var import_react_native = __require("react-native");
  function NutritionHome({ bridge }) {
    var _a, _b, _c, _d;
    const [profile, setProfile] = (0, import_react.useState)(null);
    const [meals, setMeals] = (0, import_react.useState)(null);
    const [loading, setLoading] = (0, import_react.useState)(true);
    const [refreshing, setRefreshing] = (0, import_react.useState)(false);
    const [error, setError] = (0, import_react.useState)(null);
    const load = (0, import_react.useCallback)(() => __async(this, null, function* () {
      var _a2;
      setError(null);
      try {
        const [profileRes, mealsRes] = yield Promise.all([
          bridge.callPluginApi("/api/plugins/nutrition/profile", "GET", null),
          bridge.callPluginApi("/api/plugins/nutrition/meals/today", "GET", null)
        ]);
        setProfile(profileRes);
        const mealsData = (_a2 = mealsRes.meals) != null ? _a2 : [];
        setMeals(mealsData);
      } catch (e) {
        setError(e.message || "Could not load nutrition data.");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    }), [bridge]);
    const onRefresh = (0, import_react.useCallback)(() => {
      setRefreshing(true);
      void load();
    }, [load]);
    (0, import_react.useEffect)(() => {
      void load();
    }, [load]);
    const totals = (meals != null ? meals : []).reduce(
      (acc, meal) => {
        for (const item of meal.items) {
          acc.calories += item.calories;
          acc.protein += item.protein_g;
          acc.carbs += item.carbs_g;
          acc.fat += item.fat_g;
        }
        return acc;
      },
      { calories: 0, protein: 0, carbs: 0, fat: 0 }
    );
    const hasTargets = profile != null && profile.calorie_target > 0;
    const goToChat = (prefill) => {
      if (bridge.navigateToChat) {
        bridge.navigateToChat(prefill);
      } else {
        bridge.showToast("Open Chat to continue.");
      }
    };
    if (loading) {
      return /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.center }, /* @__PURE__ */ import_react.default.createElement(import_react_native.ActivityIndicator, null));
    }
    if (error) {
      return /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.center }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.errorText }, "Could not load nutrition data."));
    }
    return /* @__PURE__ */ import_react.default.createElement(
      import_react_native.ScrollView,
      {
        style: styles.container,
        contentContainerStyle: styles.content,
        refreshControl: /* @__PURE__ */ import_react.default.createElement(import_react_native.RefreshControl, { refreshing, onRefresh })
      },
      /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.cardsRow }, /* @__PURE__ */ import_react.default.createElement(
        MacroCard,
        {
          value: Math.round(totals.calories),
          target: (_a = profile == null ? void 0 : profile.calorie_target) != null ? _a : 0,
          label: "cal",
          color: "#e0f2fe",
          textColor: "#0369a1"
        }
      ), /* @__PURE__ */ import_react.default.createElement(
        MacroCard,
        {
          value: Math.round(totals.protein),
          target: (_b = profile == null ? void 0 : profile.protein_g) != null ? _b : 0,
          label: "protein",
          unit: "g",
          color: "#dcfce7",
          textColor: "#15803d"
        }
      ), /* @__PURE__ */ import_react.default.createElement(
        MacroCard,
        {
          value: Math.round(totals.carbs),
          target: (_c = profile == null ? void 0 : profile.carbs_g) != null ? _c : 0,
          label: "carbs",
          unit: "g",
          color: "#fef3c7",
          textColor: "#b45309"
        }
      ), /* @__PURE__ */ import_react.default.createElement(
        MacroCard,
        {
          value: Math.round(totals.fat),
          target: (_d = profile == null ? void 0 : profile.fat_g) != null ? _d : 0,
          label: "fat",
          unit: "g",
          color: "#fce7f3",
          textColor: "#9d174d"
        }
      )),
      !hasTargets ? /* @__PURE__ */ import_react.default.createElement(
        import_react_native.Pressable,
        {
          style: styles.setupBanner,
          onPress: () => goToChat("Help me figure out my macro targets")
        },
        /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.setupBannerText }, "Set your macro targets \u2014 tap to get started.")
      ) : /* @__PURE__ */ import_react.default.createElement(import_react_native.Pressable, { onPress: () => goToChat("I want to update my macro targets") }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.manageLink }, "Manage targets")),
      meals != null && meals.length === 0 ? /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.emptyText }, "No meals logged yet.") : meals == null ? void 0 : meals.map((meal) => {
        const cal = Math.round(meal.items.reduce((s, i) => s + i.calories, 0));
        const protein = Math.round(
          meal.items.reduce((s, i) => s + i.protein_g, 0)
        );
        return /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { key: meal.id, style: styles.mealRow }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.mealName, numberOfLines: 1 }, meal.raw_input), /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.mealMeta }, cal, " cal \xB7 ", protein, "g protein"));
      }),
      /* @__PURE__ */ import_react.default.createElement(
        import_react_native.Pressable,
        {
          style: styles.logBtn,
          onPress: () => goToChat("Log meal: ")
        },
        /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.logBtnText }, "+ Log a meal")
      )
    );
  }
  function MacroCard({
    value,
    target,
    label,
    unit = "",
    color,
    textColor
  }) {
    return /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: [styles.card, { backgroundColor: color }] }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: [styles.cardValue, { color: textColor }] }, value, unit), target > 0 ? /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.cardTarget }, "/ ", target, unit, " ", label) : /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.cardTarget }, label));
  }
  var styles = import_react_native.StyleSheet.create({
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
      textAlign: "center"
    },
    setupBanner: {
      backgroundColor: "#eff6ff",
      borderWidth: 1,
      borderColor: "#bfdbfe",
      borderRadius: 8,
      padding: 12,
      marginBottom: 12
    },
    setupBannerText: {
      color: "#1d4ed8",
      fontSize: 14,
      fontWeight: "600",
      textAlign: "center"
    },
    manageLink: {
      color: "#2563eb",
      fontSize: 13,
      fontWeight: "600",
      textAlign: "right",
      marginBottom: 12
    },
    emptyText: {
      color: "#64748b",
      fontSize: 14,
      textAlign: "center",
      paddingVertical: 24
    },
    mealRow: {
      backgroundColor: "#fff",
      borderWidth: 1,
      borderColor: "#e2e8f0",
      borderRadius: 8,
      padding: 12,
      marginBottom: 8
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
      marginTop: 8
    },
    logBtnText: { color: "#16a34a", fontSize: 14, fontWeight: "700" }
  });

  // components/index.ts
  globalThis.JainPlugins = globalThis.JainPlugins || {};
  globalThis.JainPlugins.nutrition = {
    NutritionHome
  };
})();
