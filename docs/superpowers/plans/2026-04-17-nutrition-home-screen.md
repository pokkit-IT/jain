# Nutrition Home Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `NutritionHome` React Native component bundle to the nutrition plugin so it appears in the mobile Skills tab, showing today's macro progress and meal list with entry points into Chat for logging and target-setting.

**Architecture:** Single `NutritionHome.tsx` component (mirrors yardsailing pattern) built with esbuild into `bundle/nutrition.js`. The mobile bridge gains a `navigateToChat(prefill?)` method backed by a new `pendingChatPrefill` store field, which `ChatScreen` consumes on focus to pre-fill the input.

**Tech Stack:** React Native (TSX), esbuild 0.24, FastAPI (no new backend logic — existing routes used), Zustand store, React Navigation.

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `mobile/src/store/useAppStore.ts` | Modify | Add `pendingChatPrefill` field + setter |
| `mobile/src/plugins/PluginBridge.ts` | Modify | Add `navigateToChat` to interface + factory |
| `mobile/src/plugins/PluginHost.tsx` | Modify | Accept + forward `navigate` prop to bridge factory |
| `mobile/src/screens/SkillsScreen.tsx` | Modify | Pass `navigation.navigate` to `PluginHost` |
| `mobile/src/screens/ChatScreen.tsx` | Modify | Consume `pendingChatPrefill` on focus |
| `backend/app/plugins/nutrition/plugin.json` | Modify | Add `components` + `home` blocks |
| `backend/app/plugins/nutrition/__init__.py` | Modify | Add `ui_bundle_path` + `ui_components` to `register()` |
| `backend/app/plugins/nutrition/build.mjs` | Create | esbuild IIFE config |
| `backend/app/plugins/nutrition/package.json` | Create | `{ "build": "node build.mjs" }`, esbuild dev-dep |
| `backend/app/plugins/nutrition/components/index.ts` | Create | Register `NutritionHome` on `globalThis.JainPlugins.nutrition` |
| `backend/app/plugins/nutrition/components/NutritionHome.tsx` | Create | Home screen component |
| `backend/app/plugins/nutrition/bundle/nutrition.js` | Build output | Produced by `npm run build`, committed |

---

## Task 1: Mobile bridge — add `navigateToChat`

**Files:**
- Modify: `mobile/src/store/useAppStore.ts`
- Modify: `mobile/src/plugins/PluginBridge.ts`
- Modify: `mobile/src/plugins/PluginHost.tsx`
- Modify: `mobile/src/screens/SkillsScreen.tsx`
- Modify: `mobile/src/screens/ChatScreen.tsx`

- [ ] **Step 1: Add `pendingChatPrefill` to the Zustand store**

In `mobile/src/store/useAppStore.ts`, add to the `AppState` interface (after the existing `pendingRetry` block, around line 32):

```typescript
  // Pre-fills the chat input on next Chat tab focus (does NOT auto-send).
  // Used by plugin home screens' "Log a meal" / "Manage targets" buttons.
  pendingChatPrefill: string | null;
  setPendingChatPrefill: (prefill: string | null) => void;
```

Then add to the `create<AppState>` object (after `clearPendingRetry`):

```typescript
  pendingChatPrefill: null,
  setPendingChatPrefill: (pendingChatPrefill) => set({ pendingChatPrefill }),
```

- [ ] **Step 2: Add `navigateToChat` to `PluginBridge`**

Replace the entire contents of `mobile/src/plugins/PluginBridge.ts` with:

```typescript
import { apiClient } from "../api/client";
import { useAppStore } from "../store/useAppStore";

export interface PluginBridge {
  callPluginApi: (path: string, method: string, body?: unknown) => Promise<unknown>;
  closeComponent: () => void;
  openComponent: (name: string, props?: Record<string, unknown>) => void;
  showToast: (msg: string) => void;
  // Navigate to the Chat tab and pre-fill the input. Does NOT auto-send.
  navigateToChat: (prefill?: string) => void;
}

export function makeBridgeForPlugin(
  pluginName: string,
  navigate?: (tab: string) => void,
): PluginBridge {
  return {
    async callPluginApi(path, method, body) {
      // Phase 2B: route plugin API calls THROUGH JAIN's backend instead
      // of directly from the browser. This gives us:
      //   1. No CORS issues (same-origin to JAIN)
      //   2. JAIN's service-key + user identity headers are forwarded to
      //      the plugin via /api/plugins/{name}/call — same auth path as
      //      the tool executor
      //   3. apiClient already attaches the JAIN JWT Authorization header
      //      via the interceptor, so JAIN knows who's calling
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
      // Best-effort inline toast via window.alert on web. Native toast
      // libraries are out of Phase 2B scope; SaleForm displays its own
      // inline success message so this is just a fallback.
      if (typeof window !== "undefined" && typeof window.alert === "function") {
        window.alert(msg);
      }
    },
    navigateToChat(prefill) {
      if (prefill) {
        useAppStore.getState().setPendingChatPrefill(prefill);
      }
      navigate?.("Jain");
    },
  };
}
```

- [ ] **Step 3: Add `navigate` prop to `PluginHost`**

In `mobile/src/plugins/PluginHost.tsx`, change the `PluginHostProps` interface and component signature:

```typescript
interface PluginHostProps {
  pluginName: string;
  componentName: string;
  props?: Record<string, unknown>;
  navigate?: (tab: string) => void;
}

export function PluginHost({ pluginName, componentName, props, navigate }: PluginHostProps) {
```

And update the bridge creation line near the bottom of the component (currently `const bridge = makeBridgeForPlugin(pluginName);`):

```typescript
  const bridge = makeBridgeForPlugin(pluginName, navigate);
```

- [ ] **Step 4: Pass `navigate` from `SkillsScreen` to `PluginHost`**

In `mobile/src/screens/SkillsScreen.tsx`, add the `useNavigation` import at the top:

```typescript
import { useNavigation } from "@react-navigation/native";
```

At the top of the `SkillsScreen` function body, add:

```typescript
  const navigation = useNavigation<any>();
```

Update the `<PluginHost .../>` call in the `if (selected)` branch:

```typescript
        <PluginHost
          pluginName={selected.pluginName}
          componentName={selected.componentName}
          navigate={(tab) => navigation.navigate(tab as never)}
        />
```

- [ ] **Step 5: Consume `pendingChatPrefill` in `ChatScreen`**

In `mobile/src/screens/ChatScreen.tsx`, add a new `useFocusEffect` after the existing three (after the `useFocusEffect` that handles `pendingPrompt`, around line 64):

```typescript
  // Pre-fill the chat input when a plugin navigates here with a prefill string.
  // Does NOT auto-send — the user types their message and taps Send themselves.
  useFocusEffect(
    useCallback(() => {
      const prefill = useAppStore.getState().pendingChatPrefill;
      if (!prefill) return;
      useAppStore.getState().setPendingChatPrefill(null);
      setInput(prefill);
      setTimeout(() => inputRef.current?.focus(), 50);
    }, []),
  );
```

- [ ] **Step 6: Run tsc to verify no type errors**

```bash
cd mobile
"C:/Program Files/nodejs/npx.cmd" tsc --noEmit
```

Expected: no errors. If errors appear, fix them before continuing.

- [ ] **Step 7: Commit**

```bash
"C:/Program Files/Git/bin/git.exe" add mobile/src/store/useAppStore.ts mobile/src/plugins/PluginBridge.ts mobile/src/plugins/PluginHost.tsx mobile/src/screens/SkillsScreen.tsx mobile/src/screens/ChatScreen.tsx
"C:/Program Files/Git/bin/git.exe" commit -m "feat(bridge): add navigateToChat — pre-fills Chat input from plugin home screens"
```

---

## Task 2: Backend manifest — wire up the bundle

**Files:**
- Modify: `backend/app/plugins/nutrition/plugin.json`
- Modify: `backend/app/plugins/nutrition/__init__.py`

- [ ] **Step 1: Add `components` and `home` blocks to `plugin.json`**

Replace the entire contents of `backend/app/plugins/nutrition/plugin.json` with:

```json
{
  "name": "nutrition",
  "version": "1.0.0",
  "description": "Conversational macro tracking and meal logging",
  "author": "pokkit-IT",
  "type": "internal",
  "skills": [
    {
      "name": "meal-log",
      "description": "Log a meal conversationally. Use when user describes eating something, mentions a meal, or says what they had.",
      "tools": ["log_meal"]
    },
    {
      "name": "macro-tracker",
      "description": "Check macro progress, set targets, or ask about daily nutrition status.",
      "tools": ["get_macro_summary", "set_macro_targets"]
    }
  ],
  "components": {
    "bundle": "bundle/nutrition.js",
    "exports": ["NutritionHome"]
  },
  "home": {
    "component": "NutritionHome",
    "label": "Nutrition",
    "icon": "nutrition-outline",
    "description": "Track your daily macros and meals."
  },
  "examples": [
    {"prompt": "Breakfast: 2 eggs, toast, peanut butter", "description": "Log a meal"},
    {"prompt": "I just had a protein shake", "description": "Quick meal log"},
    {"prompt": "What are my macros today?", "description": "Check daily progress"},
    {"prompt": "How am I doing on protein?", "description": "Macro status"},
    {"prompt": "Set my protein target to 180g", "description": "Update targets"}
  ]
}
```

- [ ] **Step 2: Add `ui_bundle_path` and `ui_components` to `register()`**

Replace the entire contents of `backend/app/plugins/nutrition/__init__.py` with:

```python
"""First-party internal nutrition plugin.

Conversational meal logging and macro tracking. Phase 1 = text-only
(no UI bundle). Models live in `models.py`, business logic in
`services.py`, USDA lookup in `usda.py`, LLM tool definitions in
`tools.py`, admin/debug HTTP routes in `routes.py`.
"""

from app.plugins.core.types import PluginRegistration


def register() -> PluginRegistration:
    # Lazy imports so the package can be imported cleanly between tasks.
    from .routes import router
    from .tools import TOOLS

    return PluginRegistration(
        name="nutrition",
        version="1.0.0",
        type="internal",
        router=router,
        tools=TOOLS,
        ui_bundle_path="bundle/nutrition.js",
        ui_components=["NutritionHome"],
    )
```

- [ ] **Step 3: Commit**

```bash
"C:/Program Files/Git/bin/git.exe" add backend/app/plugins/nutrition/plugin.json backend/app/plugins/nutrition/__init__.py
"C:/Program Files/Git/bin/git.exe" commit -m "feat(nutrition): add home block + components to manifest"
```

---

## Task 3: Bundle build setup

**Files:**
- Create: `backend/app/plugins/nutrition/build.mjs`
- Create: `backend/app/plugins/nutrition/package.json`

- [ ] **Step 1: Create `build.mjs`**

Create `backend/app/plugins/nutrition/build.mjs` with this exact content (mirrors yardsailing, only entry/output/log label differ):

```javascript
import { build } from "esbuild";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname);

const entry = join(ROOT, "components", "index.ts");
const outfile = join(ROOT, "bundle", "nutrition.js");
const outdir = dirname(outfile);
if (!existsSync(outdir)) mkdirSync(outdir, { recursive: true });

await build({
  entryPoints: [entry],
  bundle: true,
  outfile,
  format: "iife",
  platform: "neutral",
  target: "es2016",
  jsx: "transform",
  external: ["react", "react-native"],
  loader: { ".tsx": "tsx", ".ts": "ts" },
  logLevel: "info",
});

// Post-build patch: replace esbuild's __toESM wrapper with a passthrough.
// esbuild's __toESM creates Object.create(getPrototypeOf(mod)) which loses
// all own-property named exports (useState, etc.) from the require shim's
// React module. Passthrough is safe because the PluginHost shim already
// returns the real CJS module objects directly.
let content = readFileSync(outfile, "utf-8");
content = content.replace(
  /var __toESM = \([^)]*\) => \([^;]*\);/,
  "var __toESM = (mod) => mod;",
);
writeFileSync(outfile, content);

console.log(`[nutrition] built ${outfile}`);
```

- [ ] **Step 2: Create `package.json`**

Create `backend/app/plugins/nutrition/package.json`:

```json
{
  "name": "jain-nutrition-bundle",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "node build.mjs"
  },
  "devDependencies": {
    "esbuild": "^0.24.0"
  }
}
```

Note: no `@react-native-community/datetimepicker` dep — `NutritionHome` doesn't use date pickers.

- [ ] **Step 3: Install dependencies**

```bash
cd backend/app/plugins/nutrition
"C:/Program Files/nodejs/npm.cmd" install
```

Expected: creates `node_modules/` and `package-lock.json`.

- [ ] **Step 4: Commit `package.json` and `package-lock.json` (not `node_modules`)**

```bash
"C:/Program Files/Git/bin/git.exe" add backend/app/plugins/nutrition/package.json backend/app/plugins/nutrition/package-lock.json backend/app/plugins/nutrition/build.mjs
"C:/Program Files/Git/bin/git.exe" commit -m "feat(nutrition): add esbuild bundle build setup"
```

---

## Task 4: `NutritionHome` component + bundle

**Files:**
- Create: `backend/app/plugins/nutrition/components/index.ts`
- Create: `backend/app/plugins/nutrition/components/NutritionHome.tsx`
- Build output: `backend/app/plugins/nutrition/bundle/nutrition.js`

**Background:** `GET /api/plugins/nutrition/meals/today` returns `{ "meals": [...] }` (dict with a `"meals"` key). `GET /api/plugins/nutrition/profile` returns the profile object directly. Macro defaults (always set): 2000 cal / 150g protein / 200g carbs / 65g fat — so `hasTargets` is true for all users in practice; the setup banner is a safety net for the edge case where targets are somehow all zero.

- [ ] **Step 1: Create `components/index.ts`**

Create `backend/app/plugins/nutrition/components/index.ts`:

```typescript
import { NutritionHome } from "./NutritionHome";

// Register on global namespace for PluginHost to pick up.
declare const globalThis: {
  JainPlugins?: Record<string, Record<string, unknown>>;
};

globalThis.JainPlugins = globalThis.JainPlugins || {};
globalThis.JainPlugins.nutrition = {
  NutritionHome,
};

export { NutritionHome };
```

- [ ] **Step 2: Create `components/NutritionHome.tsx`**

Create `backend/app/plugins/nutrition/components/NutritionHome.tsx`:

```tsx
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
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
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
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
    }
  };

  useEffect(() => {
    void load();
  }, []);

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
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
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
```

- [ ] **Step 3: Build the bundle**

```bash
cd backend/app/plugins/nutrition
"C:/Program Files/nodejs/npm.cmd" run build
```

Expected output ends with: `[nutrition] built .../bundle/nutrition.js`

- [ ] **Step 4: Verify the bundle exists and is non-empty**

```bash
"C:/Program Files/Git/bin/git.exe" -C "C:/Users/jimsh/repos/jain" status backend/app/plugins/nutrition/bundle/
```

Expected: `bundle/nutrition.js` shows as an untracked or modified file.

- [ ] **Step 5: Run tsc to verify no type errors**

```bash
cd mobile
"C:/Program Files/nodejs/npx.cmd" tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Commit all new files + bundle**

```bash
"C:/Program Files/Git/bin/git.exe" add backend/app/plugins/nutrition/components/index.ts backend/app/plugins/nutrition/components/NutritionHome.tsx backend/app/plugins/nutrition/bundle/nutrition.js
"C:/Program Files/Git/bin/git.exe" commit -m "feat(nutrition): NutritionHome component — macro cards, meal list, chat nav buttons"
```

---

## Task 5: Push and verify

- [ ] **Step 1: Push the custody fix + all nutrition commits**

```bash
"C:/Program Files/Git/bin/git.exe" push origin main
```

- [ ] **Step 2: Restart the backend on Mac, then verify in the app**

On Mac, restart the FastAPI backend to pick up the new bundle path. Then in the mobile app:

1. Open Skills tab → Nutrition appears in the list with the `nutrition-outline` icon
2. Tap Nutrition → home screen loads (no "Plugin load failed" error)
3. Macro cards show today's consumed totals over targets (e.g. `0 / 2000 cal` if no meals yet)
4. "Manage targets" link is visible below the cards
5. Tap "Manage targets" → Chat tab opens, input pre-filled with `"I want to update my macro targets"`
6. Return to Skills → Nutrition → tap "+ Log a meal" → Chat tab opens, input pre-filled with `"Log meal: "`
7. Settings tab shows Nutrition 1.0.0 (was already showing — no regression)
8. Custody plugin also appears in Settings and Skills (custody fix from earlier commit)
