# Map Plugin Overlay — Design Spec

**Date:** 2026-04-19
**Status:** Approved

## Problem

`MapScreen` is tightly coupled to the yardsailing plugin — it imports yardsailing API functions directly and contains all yardsailing-specific UI (filter chips, modals, FABs). This prevents the map from being useful to other plugins and makes it impossible to disable yardsailing without breaking the map tab.

## Goal

- Map is a generic core screen that knows nothing about yardsailing.
- Plugins declare a map component in their manifest; the core renders it as an overlay.
- Map tab appears only when at least one loaded plugin declares a map component.
- Yardsailing plugin owns its entire map experience: markers, filter chips, FABs, modals.
- New "Drop Pin" FAB for quickly sighting a yard sale at the user's current location.

---

## Architecture

### Plugin manifest (`plugin.json`)

Plugins that want to contribute to the map declare a `map` field:

```json
{
  "map": {
    "component": "YardsailingMapLayer"
  }
}
```

### Backend schema (`core/schema.py`)

Add `MapConfig` and wire it into `PluginManifest`:

```python
class MapConfig(BaseModel):
    component: str

class PluginManifest(BaseModel):
    ...
    map: Optional[MapConfig] = None
```

---

## Key Interfaces

### `MapMarker` (mobile `types.ts`)

Generic marker type that plugins push to the map:

```typescript
interface MapMarker {
  id: string;
  lat: number;
  lng: number;
  color?: string;       // pin color — plugin decides
  title?: string;
  description?: string;
  data?: unknown;       // passed back on markerPress so plugin can open its own modal
}
```

### `MapBridgeExtension` (mobile `plugins/PluginBridge.ts`)

Additional bridge methods available to components rendered as map overlays. Merged into the standard `PluginBridge` by `PluginHost` when a `bridgeExtension` prop is provided.

```typescript
interface MapBridgeExtension {
  setMarkers: (markers: MapMarker[]) => void;
  onLongPress: (cb: (coord: { lat: number; lng: number }) => void) => void;
  offLongPress: (cb: (coord: { lat: number; lng: number }) => void) => void;
  onMarkerPress: (cb: (marker: MapMarker) => void) => void;
  offMarkerPress: (cb: (marker: MapMarker) => void) => void;
  getLocation: () => { lat: number; lng: number } | null;
}
```

### `mapEventBus` (`core/mapEventBus.ts` — new)

Module-level singleton (not store state) to avoid re-renders on every map interaction:

```typescript
export const mapEventBus = {
  emitLongPress(coord: { lat: number; lng: number }): void
  emitMarkerPress(marker: MapMarker): void
  subscribeLongPress(cb): void
  unsubscribeLongPress(cb): void
  subscribeMarkerPress(cb): void
  unsubscribeMarkerPress(cb): void
}
```

`MapScreen` calls `emit*`. Plugin map components subscribe via `mapBridge.onLongPress` / `onMarkerPress` (which delegate to this bus) and must unsubscribe on unmount.

---

## Changes by File

### Backend

| File | Change |
|------|--------|
| `backend/app/plugins/core/schema.py` | Add `MapConfig` model; add `map: Optional[MapConfig]` to `PluginManifest` |
| `backend/app/plugins/yardsailing/plugin.json` | Add `"map": { "component": "YardsailingMapLayer" }` |

### Mobile — Core

| File | Change |
|------|--------|
| `mobile/src/types.ts` | Add `MapMarker` interface; add `map?: { component: string }` to `PluginSummary` |
| `mobile/src/store/useAppStore.ts` | Add `mapMarkers: MapMarker[]` + `setMapMarkers(markers)` |
| `mobile/src/core/mapEventBus.ts` | New — module-level long-press and marker-press pub/sub |
| `mobile/src/core/Map.tsx` | Replace `sales: Sale[]` + dual callbacks with `markers: MapMarker[]` + `onMarkerPress(marker)` |
| `mobile/src/core/Map.web.tsx` | Same prop changes as `Map.tsx` |
| `mobile/src/screens/MapScreen.tsx` | Strip all yardsailing code; render plugin overlays; wire map events to `mapEventBus`; construct `mapBridgeExtension` object passed to `PluginHost` |
| `mobile/App.tsx` | Conditionally render `<Tab.Screen name="Map" …>` only when `plugins.some(p => p.map?.component)` is true |
| `mobile/src/plugins/PluginHost.tsx` | Add `bridgeExtension?: Partial<MapBridgeExtension>` prop; merge into bridge passed to component |
| `mobile/src/api/yardsailing.ts` | Delete or gut — `fetchRecentSales`, `postSighting`, etc. are replaced by `callPluginApi` calls inside the plugin bundle |

### Mobile — Yardsailing Plugin Bundle

| File | Change |
|------|--------|
| `backend/app/plugins/yardsailing/components/YardsailingMapLayer.tsx` | New — full map overlay component (see below) |
| `backend/app/plugins/yardsailing/components/index.ts` | Export `YardsailingMapLayer` |
| `backend/app/plugins/yardsailing/plugin.json` | Add `map.component`; add `"YardsailingMapLayer"` to `components.exports` |
| Plugin bundle | Rebuild `bundle/yardsailing.js` |

---

## `MapScreen` After Refactor

Responsibilities (only):
1. Read `plugins` from store; find those with `map.component` declared.
2. Read `mapMarkers` from store; pass to `<Map>`.
3. Pass `onLongPress` and `onMarkerPress` callbacks that forward to `mapEventBus`.
4. Read location from `useLocation()`; pass region to `<Map>`.
5. For each plugin with a `map.component`, render a `PluginHost` with `absoluteFill` style and the `mapBridgeExtension` injected.

Estimated size: ~50 lines (down from ~300).

---

## `YardsailingMapLayer` Component

Lives in the plugin bundle. Rendered as an `absoluteFill` transparent overlay on top of the map.

**On mount:**
- Fetches sales (with current filter state).
- Calls `mapBridge.setMarkers(sales.map(toMapMarker))`.
- Subscribes to `mapBridge.onLongPress` → opens sighting drop modal.
- Subscribes to `mapBridge.onMarkerPress` → opens `SaleDetailsModal` (host) or `SightingPopup` (sighting).

**On unmount:**
- Calls `mapBridge.setMarkers([])`.
- Calls `mapBridge.offLongPress` and `mapBridge.offMarkerPress`.

**Renders (all absolute-positioned):**
- **Filter bar** — top of screen, horizontal scroll chips: Now · Groups · Tags · Clear
- **Refresh FAB** — bottom-right
- **Drop-Pin FAB** — bottom-right, above Refresh FAB
- **Sighting drop modal** — triggered by Drop-Pin FAB tap or map long-press; pre-fills coords from `mapBridge.getLocation()` when triggered via FAB
- **`SaleDetailsModal`** — triggered by `onMarkerPress` for host sales
- **`SightingPopup`** — triggered by `onMarkerPress` for sighting sales

**Drop-Pin FAB behavior:**
- Tap → reads current location via `mapBridge.getLocation()` → opens sighting confirmation modal with coords pre-filled.
- No "crosshair mode" — the FAB is for "I'm standing at a sale right now."
- Long-press anywhere on the map still works for dropping a pin at an arbitrary location.

**Pin color logic** (moves from `Map.tsx` into this component via `MapMarker.color`):
- Host sale → `#2563eb` (blue)
- Unconfirmed sighting → `#f59e0b` (orange)
- Confirmed sighting (≥2 confirmations) → `#16a34a` (green)

---

## Tab Visibility

The tab navigator checks:

```typescript
const hasMapPlugin = plugins.some(p => p.map?.component);
```

Map tab is shown only when `hasMapPlugin` is true. When yardsailing is disabled (renamed to `_yardsailing`), the tab disappears automatically.
