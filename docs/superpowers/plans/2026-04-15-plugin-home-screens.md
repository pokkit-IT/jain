# Plugin Home Screens + Skills Tab — Implementation Plan

*End-user label is **Skills**; code identifiers keep `plugin`.*

**Date:** 2026-04-15
**Spec:** `docs/superpowers/specs/2026-04-15-plugin-home-screens-design.md`
**Branch:** `feature/plugin-home-screens`

## Phases

### Phase 1 — Backend manifest exposure

1. `PluginRegistration` dataclass gains `home: dict | None = None`.
2. The plugin loader reads `home` from `plugin.json` and includes it on the registration.
3. `GET /api/plugins` response grows a `home` field (nullable).
4. Tests covering: plugin without `home` returns null; plugin with `home` returns the dict.

Exit: `pytest backend/tests/test_plugin_registry.py` (or equivalent) green.

### Phase 2 — Yardsailing home component (bundle)

1. New `backend/app/plugins/yardsailing/components/YardsailingHome.tsx`.
2. Declares its own `SaleFormData` import; renders:
   - Header + "Create sale" button → calls `bridge.openComponent("SaleForm")`.
   - My Sales list (API `GET /sales`), tap → opens a local `SaleCardActions` modal with Directions, Manage Photos, Delete.
3. Update `plugin.json`: add `home` block + `YardsailingHome` to `components.exports`.
4. Rebuild bundle.

Exit: `npm run build` inside `yardsailing/` emits an updated bundle; manual sanity that the component loads via `PluginHost` directly.

### Phase 3 — Bridge `openComponent`

1. Extend `PluginBridge.ts` with `openComponent(name, props?)` and `closeComponent()`.
2. Core app owns a "plugin component stack" — a minimal modal-mounted slot that renders the requested plugin component. First version: one component at a time; re-calling `openComponent` replaces the current one.
3. Implementation: a `PluginOverlay` mounted at the app root subscribed to `useAppStore.pluginOverlay` (new slice). `openComponent` pushes state; `closeComponent` clears.

Exit: tsc clean; manual smoke that Chat-initiated `SaleForm` still works (it uses the same slot).

### Phase 4 — Skills tab navigation

1. Drop `MySales` from `App.tsx` bottom-tab navigator.
2. Add a `Skills` tab (tab label: "Skills") with a stack navigator:
   - `SkillListScreen` — fetches installed plugins from `useAppStore`, filters to `home != null`, renders a list with label + description + chevron.
   - `SkillHomeScreen` — takes `{ pluginName, componentName, label }`, renders `<PluginHost ... />` inside a `<View flex:1>`.
3. Icon map in the tab config: `storefront` → `Ionicons "storefront-outline"`; fallback "extension-puzzle-outline". Tab icon itself: `sparkles-outline` or similar.

Exit: tsc clean; Skills tab lists Yardsailing → tap → home screen renders.

### Phase 5 — Delete old MySalesScreen + docs

1. Delete `mobile/src/screens/MySalesScreen.tsx`.
2. Remove any nav references in `App.tsx`.
3. Update `help.md`: "Manage your sales" section points to **Skills → Yardsailing**.
4. PR against main.

Exit: tsc clean; docs reflect the new path.

## Risks / Notes

- **Overlay collision with chat-initiated components.** Both chat and the home will call `openComponent`. If chat opens `SaleForm` and then user switches to Plugins tab, what happens? Simplest v1: the overlay is global and persists across tabs until closed. Document this.
- **Plugin list empty states.** If `home` is absent for every plugin, show "No plugins with home screens yet." Keep the tab visible for discoverability.
- **Bridge reuse.** Yardsailing's home needs the same bridge verbs as `SaleForm` — already covered. `openComponent` is additive.
- **Mobile store shape.** Adding `pluginOverlay` slice has to coexist with existing slices; keep it null-by-default to avoid migration pain.
- **Backwards-compat for merged PRs.** PRs #3 (groups) and #4 (pin-drop) both added to `SaleResponse`; this branch doesn't touch that surface.

## Non-goals

- No plugin marketplace, storefront, discovery across devices.
- No per-plugin settings screen.
- No dynamic top-level tabs beyond the single Plugins tab.
- No animated transitions between plugin components; a swap is fine.
