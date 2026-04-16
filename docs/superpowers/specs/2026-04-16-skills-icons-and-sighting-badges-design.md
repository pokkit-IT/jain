# Skills Icons + Sighting Badges — Design Spec

**Date:** 2026-04-16
**Status:** Draft
**Scope:** Mobile app only

## Goal

Polish the Skills surface introduced in PR #5 and the `display_hint="map"` chat card introduced in PR #4:

1. Render each Skill's declared icon in the Skills list so plugins have a visual identity.
2. Distinguish pin-drop sightings from host-created sales when they appear in the chat "map" card list, matching the badge treatment `SightingPopup` already uses on the Map tab.

Both are small, user-visible touch-ups. No backend changes, no plugin manifest schema changes, no new plugin bundle work.

## Scope

**In scope:**
- `mobile/src/screens/SkillsScreen.tsx` — render icon on each Skill row.
- `mobile/src/chat/DataCard.tsx` — render a Confirmed/Unconfirmed badge on sighting cards in the `display_hint="map"` branch.

**Out of scope:**
- No filter UI on chat map cards (no groups/tags/now chips). Natural-language filtering through Jain is sufficient; adding a parallel filter bar in the chat bubble is premature.
- No changes to `MapScreen`, `SightingPopup`, `SaleDetailsModal`, or the yardsailing plugin bundle.
- No backend, schema, or `plugin.json` changes.
- One dependency change: promote `@expo/vector-icons` from a transitive (nested under `expo`) to a direct dependency in `mobile/package.json`. No new library introduced — the package is already pinned via `expo@54.0.33`, we just need it at the top level of `node_modules` so `mobile/src/*` can resolve the import. Use the Expo SDK 54-aligned version (`^15.1.1`).
- No icon-name migration. Existing `home.icon: "storefront-outline"` in `yardsailing/plugin.json` is already an Ionicons name.

## Feature 1 — Icons on the Skills list

### Data path

Already wired end-to-end:

- `backend/app/plugins/yardsailing/plugin.json` → `home.icon: "storefront-outline"`.
- `backend/app/plugins/core/schema.py` serializes `icon: str | None` on the home block.
- `GET /api/plugins` returns it; test at `backend/tests/test_plugins_router.py:40` asserts the yardsailing icon value.
- `mobile/src/types.ts` → `PluginHome.icon?: string | null` (already present).
- `SkillsScreen` reads the home block but ignores `icon` today.

No changes to any of the above.

### Rendering

In `SkillsScreen.tsx`:

- Import `Ionicons` from `@expo/vector-icons`.
- Each row in the plugin list renders `<Ionicons name={item.home.icon ?? "apps-outline"} size={28} color="#475569" style={{ marginRight: 12 }} />` before the text column.
- When `item.home.icon` is null/undefined, the fallback `"apps-outline"` is used.
- When `item.home.icon` names a glyph Ionicons doesn't recognize, the library logs a warning and the icon renders empty (no glyph). Acceptable for internal plugins; the warning is visible in dev.

### Edge cases

- No plugins with a `home` block → empty-state message unchanged.
- Plugin declares an unknown Ionicon name → Ionicons renders its built-in missing-glyph placeholder. Internal-only concern; document valid-names note inline.

### Non-goals

- Icon color theming per plugin.
- Allowing plugins to ship their own icon asset (PNG/SVG) — would require bundle protocol work. Defer until a real need.

## Feature 2 — Sighting badge on chat list cards

### Where

`DataCard.tsx`, inside the `displayHint === "map"` branch. Each card in the horizontal list becomes sighting-aware.

### Trigger

A card renders the badge only when `sale.source === "sighting"`. Host-created sales (`source === "host"` or undefined) render unchanged.

### Badge content

- Unconfirmed (`(sale.confirmations ?? 1) < 2`): text `"Unconfirmed"`, background `#fef3c7`.
- Confirmed (`(sale.confirmations ?? 1) >= 2`): text `"Confirmed"`, background `#dcfce7`.
- Text style: `fontSize: 11, fontWeight: 700, color: #0f172a, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10`.

This is a direct lift of the badge treatment in `SightingPopup.tsx` — same colors, same radii, same thresholds — so the UI is consistent across the Map tab and the chat card.

### Layout

In the existing `cardInnerRow` (the flex row holding title and distance), the badge is prepended before the title:

```
[badge] [title] [distance]
```

- Badge has `marginRight: 6` and `flexShrink: 0` so it never truncates.
- Title keeps `numberOfLines={1}`; it truncates first if space is tight.
- When the card has a photo, the badge sits in the text column next to the title — never overlaid on the image.

### Edge cases

- Sighting without `confirmations` set → `?? 1` falls through to Unconfirmed. Matches `SightingPopup`'s fallback.
- Sighting without `start_time`/`end_time`/`tags` → existing conditional rendering covers it.
- Mixed host + sighting results in the same card list → badges appear only on sighting cards; no layout reshuffle.

### Non-goals

- No confirmation count displayed (keeps the badge small).
- No CTA to confirm a sighting from the chat card. The existing map long-press flow is the confirm path.

## Architecture diagrams

None needed — two small rendering changes.

## Test Plan

- `npx tsc --noEmit` in `mobile/` is clean after changes.
- Manual: open Skills tab → confirm Yardsailing row shows a storefront icon. Temporarily null out the icon in the plugin manifest response (or fall through via a bogus name) → confirm the fallback shows or the row renders without crashing.
- Manual: ask Jain "find yard sales near me" in chat. If any returned sale has `source === "sighting"`, its card shows the yellow/green badge. Host sales show no badge.
- No new automated tests. The logic is thin rendering; visual verification via the app is the meaningful check.

## Rollout

Single PR, single commit acceptable. No feature flag. Changes are additive and scoped to two files.

## Non-goals

- Filter UI on chat cards.
- `@expo/vector-icons` used for any other icon refresh (tabs, buttons, etc.).
- Sighting badge on `SaleDetailsModal`, `MySales` legacy views, or anywhere outside the chat `DataCard`.
