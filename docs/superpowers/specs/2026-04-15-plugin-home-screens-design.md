# Plugin Home Screens + Skills Tab — Design Spec

*User-facing label is **Skills** — Jain is an assistant, not an app, and assistants have skills. Internal plumbing (code identifiers, API routes, `plugin.json`) keeps the `plugin` term; don't search-and-replace blindly.*

**Date:** 2026-04-15
**Status:** Draft
**Scope:** Core mobile app + yardsailing plugin

## Goal

Stop hardcoding plugin-specific destinations in the bottom nav. Add a generic **Skills** tab that lists every installed plugin, and let each plugin declare a home-screen component rendered via the existing `PluginHost` bridge. As the first consumer, yardsailing moves its "My Sales" + "Create sale" + future surfaces into a plugin-owned home. The fixed **My Sales** tab is deleted.

## Scope

- Core mobile app: replace the `My Sales` bottom-tab with a generic `Skills` tab.
- Plugin manifest (`plugin.json`) gains an optional `home` section declaring the home component name, label, and icon hint.
- Plugin bundle can export a home component reachable through the existing `PluginHost`.
- `MySalesScreen` and its route are deleted; the equivalent UI lives inside a new `YardsailingHome` component inside the yardsailing bundle.
- No new auth surfaces; home components use the same bridge (auth, toasts, API proxy).

Out of scope for v1:
- Deep-linking into plugin sub-screens from chat.
- Per-plugin settings surface separate from the home.
- Multiple home tabs (one home per plugin; if a plugin wants sub-navigation, it implements its own).
- Plugin-contributed top-level tabs beyond the single `Skills` tab (deferred until there's actual demand).

## User Flow

1. Open the app → bottom nav shows **Chat / Map / Skills / Help / Settings**.
2. Tap **Skills** → list of Jain's skills (one per installed plugin with a home) with label, description, and a right chevron. For now just yardsailing.
3. Tap `Yardsailing` → the plugin's `YardsailingHome` renders in a screen pushed on the Skills stack.
4. `YardsailingHome` shows:
   - Intro text + a **Create yard sale** button (opens `SaleForm` via the plugin component surface, same as chat today).
   - A **My Sales** section (list of the user's sales; tap → `SaleDetailsModal` like today).
   - Pointer to Help for discovery.

## Architecture

### Plugin manifest

`plugin.json` gains an optional `home`:

```json
{
  "name": "yardsailing",
  "home": {
    "component": "YardsailingHome",
    "label": "Yardsailing",
    "icon": "storefront"
  }
}
```

- `component` — name of an exported React component in the plugin bundle.
- `label` — user-facing string shown in the Skills list.
- `icon` — optional name that the core app maps to an `@expo/vector-icons` glyph (e.g. `Ionicons`). If unknown or missing, render a generic plugin icon.

### Backend

`PluginRegistration` / the `PluginSummary` API payload exposes the `home` block so the client can discover it without re-fetching plugin.json:

```python
home: dict | None = None  # {"component": str, "label": str, "icon": str | None}
```

Existing `GET /api/plugins` response grows a `home` field when present.

### Mobile — navigation

- Remove `MySales` from `App.tsx` bottom tab navigator.
- Add a `Skills` tab (route name `Skills`) whose stack has two routes:
  - `SkillList` — renders the list of installed plugins (filtered to ones with a `home` declaration) as Jain's "skills".
  - `PluginHome` — takes `{ pluginName: string, componentName: string, label: string }` as params and renders `<PluginHost pluginName=... componentName=... />`.
- Bottom-tab icon mapping extended with `storefront` / `extension` defaults.

### Mobile — `PluginSummary` typing

`PluginSummary` in `types.ts` adds `home?: { component: string; label: string; icon?: string | null }`.

### Yardsailing plugin

- Add `YardsailingHome.tsx` in `backend/app/plugins/yardsailing/components/`. Exports a React component consuming the existing `bridge`.
- The component:
  - Calls `GET /api/plugins/yardsailing/sales` to load the user's sales.
  - Renders a list identical to the old `MySalesScreen` cards (tappable → opens a modal with details; Delete via confirm).
  - Includes a `Create Sale` button that asks the bridge to mount `SaleForm` (new bridge verb: `openComponent(name)`).
  - For `SaleDetailsModal`-equivalent behavior, inline a minimal detail modal inside the bundle (owner-only "Manage Photos" button still works; re-uses `ManagePhotosSheet`).
- Extend `plugin.json` `components.exports` with `YardsailingHome`.
- Update `register()` to list it in `ui_components`.

### Bridge additions

Add one verb:

```ts
openComponent(name: string, props?: Record<string, unknown>): void
```

Core-side implementation mounts `<PluginHost pluginName={currentPlugin} componentName={name} props={props} />` inside a modal/sheet stack. Close via the existing `closeComponent()` verb.

This unblocks the home component opening `SaleForm` without coupling to navigation primitives.

### Manage Photos reuse

`ManagePhotosSheet` lives in the mobile app today. The plugin home re-uses it when the user taps a sale, via a new bridge verb we skip for v1 — instead, render a plugin-local `SaleDetailsInline` mini-component with a **Manage Photos** button that opens the same `ManagePhotosSheet` via a small `openSheet` bridge verb. Simpler alternative: keep `SaleDetailsModal` in the core app, expose it via the bridge as `openSaleDetails(saleId)`. Pick on implementation.

## Migration / Compat

- Any user currently relying on the `MySales` tab gets the same content one tap deeper (`Skills → Yardsailing`).
- Keep a one-line placeholder notice in the Help screen: "My Sales has moved under Skills → Yardsailing."

## Test Plan

- Backend: `GET /api/plugins` returns `home` object for yardsailing; absent for plugins without it.
- Backend: existing plugin tests still pass.
- Mobile tsc clean; unit test the PluginList filtering to homes-only.
- Manual smoke: open Plugins tab, tap Yardsailing, see My Sales list, create a new sale, see it appear.

## Open Questions

- **Icon set.** Use `Ionicons` to match existing tabs. Plugins with unknown icon strings fall back to a puzzle-piece glyph.
- **Component-open bridge verb.** Use `openComponent(name, props)` vs. forcing the plugin to manage its own modal stack? v1: add it to the bridge — plugin bundles don't own React Navigation.

## Non-goals

- No dynamic top-level tabs contributed by plugins.
- No plugin storefront / marketplace.
- No per-plugin settings UI.
- No removal of the chat-initiated `SaleForm` entry point — still works as before.
