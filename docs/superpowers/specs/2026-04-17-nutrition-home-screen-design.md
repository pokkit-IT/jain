# Nutrition Home Screen — Design Spec

## Goal

Add a `NutritionHome` React Native component bundle to the nutrition plugin so it appears in the mobile Skills tab, showing today's macro progress and meal list with entry points into the conversational logging and target-setting flows.

## Architecture

New files in `backend/app/plugins/nutrition/`:

| File | Purpose |
|------|---------|
| `components/NutritionHome.tsx` | Single home screen component |
| `components/index.ts` | Registers `{ NutritionHome }` on `globalThis.JainPlugins.nutrition` |
| `build.mjs` | esbuild IIFE config — mirrors yardsailing's build exactly |
| `package.json` | `{ "scripts": { "build": "node build.mjs" }, "devDependencies": { "esbuild": "^0.24.0" } }` |
| `bundle/nutrition.js` | Build output (produced by `npm run build`, committed to repo) |

Modified files:

| File | Change |
|------|--------|
| `backend/app/plugins/nutrition/plugin.json` | Add `components` and `home` blocks |
| `backend/app/plugins/nutrition/__init__.py` | Add `ui_bundle_path` and `ui_components` to `register()` |
| `mobile/src/plugins/PluginBridge.ts` | Add `navigateToChat(prefill?: string)` method |

Plugins are standalone apps — no shared code, dependencies, or build infrastructure between plugins.

## plugin.json additions

```json
"components": {
  "bundle": "bundle/nutrition.js",
  "exports": ["NutritionHome"]
},
"home": {
  "component": "NutritionHome",
  "label": "Nutrition",
  "icon": "nutrition-outline",
  "description": "Track your daily macros and meals."
}
```

## __init__.py change

```python
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

## Bridge extension

`PluginBridge.ts` gains one new method:

```ts
navigateToChat(prefill?: string): void
```

Implementation: dispatches a navigation action to switch to the Chat tab and, if `prefill` is provided, sets the chat input value to that string with the cursor at the end. If the navigation system cannot fulfil the request, falls back to `showToast("Open Chat to continue")`.

This method is called by plugin components — it is not plugin-specific and is available to all plugins via the bridge.

## Data fetching

On mount, `NutritionHome` makes two parallel `bridge.callPluginApi` calls:

1. `GET /api/plugins/nutrition/profile` → macro targets + profile metadata
2. `GET /api/plugins/nutrition/meals/today` → today's meal list with items

Today's consumed macro totals are computed client-side by summing `MealItem` values across all meals returned by endpoint 2. This avoids a third request to `day-summaries`.

**No targets set** is detected when `profile.calorie_target` is null or 0.

## Screen layout

Top to bottom (no section labels):

### 1. Macro cards row

Four equal-width cards in a single row: **Calories**, **Protein**, **Carbs**, **Fat**.

Each card shows:
- Large number: today's consumed amount (summed from meal items)
- Small label below: `/ {target} {unit}` (e.g. `/ 180g protein`)
- If no target is set for that macro: show just the number, no denominator

Color coding (matches mockup): Calories → blue (`#e0f2fe`), Protein → green (`#dcfce7`), Carbs → yellow (`#fef3c7`), Fat → pink (`#fce7f3`).

### 2. Targets entry point

**When no targets are set** (first-time user): a banner card below the macro row reads:
> "Set your macro targets — tap to get started."

Tapping calls `bridge.navigateToChat("Help me figure out my macro targets")`.

**When targets are set**: a small tappable text link reads `"Manage targets"`. Tapping calls `bridge.navigateToChat("I want to update my macro targets")`.

### 3. Meal list

Scrollable list of today's meals. Each row shows:
- Meal name (`raw_input`, truncated to one line)
- Calorie total and protein total for that meal (e.g. `520 cal · 28g protein`)

Tapping a row does nothing (no detail view in this phase).

**Empty state**: if no meals logged today, show centered text `"No meals logged yet"` in place of the list.

### 4. Log a meal button

Always visible below the meal list (or empty state message):

```
+ Log a meal
```

Tapping calls `bridge.navigateToChat("Log meal: ")` — cursor lands after the colon so the user types what they ate.

### 5. Loading and error states

- **Loading**: `ActivityIndicator` centered while either fetch is in flight.
- **Error**: plain text message `"Could not load nutrition data."` centered on screen.

## Build process

```bash
cd backend/app/plugins/nutrition
npm install          # installs esbuild locally
npm run build        # produces bundle/nutrition.js
```

`build.mjs` config:
- Entry: `components/index.ts`
- Output: `bundle/nutrition.js`
- Format: IIFE
- External: `["react", "react-native"]`
- Loader: `{ ".tsx": "tsx", ".ts": "ts" }`
- Post-build: replace esbuild's `__toESM` wrapper with passthrough (same patch as yardsailing)

## Non-goals

- No macro history chart or weekly view (future phase)
- No meal detail / edit / delete from home screen
- No inline LLM feedback in the home screen — logging and target-setting go through Chat
- No fiber macro card (shown in chat summaries but not in the 4-card row to keep it compact)
- No image/barcode scanning

## Test plan

1. Fresh user (no profile, no meals): macro cards show all zeros, setup banner visible, no meal rows, empty state message shown.
2. User with targets set, no meals today: macro cards show zeros with denominators, "Manage targets" link visible, empty state message shown.
3. User with targets and meals: macro cards sum correctly, meals listed, "Manage targets" link visible.
4. "Set your macro targets" banner tap → Chat tab opens, input pre-filled with `"Help me figure out my macro targets"`.
5. "Manage targets" link tap → Chat tab opens, input pre-filled with `"I want to update my macro targets"`.
6. "+ Log a meal" tap → Chat tab opens, input pre-filled with `"Log meal: "`.
7. `tsc --noEmit` in `mobile/` passes with no errors after bridge extension.
8. `npm run build` in `nutrition/` produces `bundle/nutrition.js` without errors.
9. Nutrition appears in the Skills tab list after backend restart.
10. Tapping Nutrition in Skills renders the home screen without "Plugin load failed" error.
