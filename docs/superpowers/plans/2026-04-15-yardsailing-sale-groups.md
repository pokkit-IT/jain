# Yardsailing Sale Groups — Implementation Plan

**Date:** 2026-04-15
**Spec:** `docs/superpowers/specs/2026-04-15-yardsailing-sale-groups-design.md`
**Branch:** `feature/yardsailing-sale-groups`

## Phases

### Phase 1 — Backend models & migrations

1. Add `SaleGroup` and `SaleGroupMembership` to `backend/app/plugins/yardsailing/models.py`. Wire up the many-to-many `Sale.groups` relationship.
2. Register the new models in `backend/app/models/__init__.py` so `create_all` picks them up.
3. Write unit tests for model constraints: unique name (case-insensitive), slug uniqueness, both-or-neither dates, start ≤ end.

Exit: `pytest backend/tests/plugins/yardsailing/test_models.py` passes with new cases.

### Phase 2 — Group service module

1. Create `backend/app/plugins/yardsailing/groups.py` with `search_groups`, `create_group`, `attach_sale_to_group`, `detach_sale_from_group`, `validate_dates_within_group`.
2. Raise a typed `GroupDateMismatch` error when attach fails due to date window.
3. Slugify via existing util or a small local helper (`re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")`; append `-2`, `-3`, … on collision).
4. Unit tests for every service function including idempotent attach/detach and date-window edge cases (sale exactly at boundary, single-day sale, no end_date).

Exit: `pytest backend/tests/plugins/yardsailing/test_groups_module.py` passes.

### Phase 3 — Backend routes

1. Add the six endpoints from the spec to `routes.py`. Use `require_user` for create/attach; read endpoints are public (match existing sale listing).
2. Update `services.serialize_sale` to include `groups` (id, name, slug, start_date, end_date).
3. Update sale-update endpoint: re-validate group memberships whenever `start_date`/`end_date` change; return 422 with `{conflicts: [{group_id, reason}]}` so the client can prompt.
4. Update `GET /sales` to accept `?group_id=` and filter via the join table.
5. Route tests covering: unauth create (401), cross-user attach (403 on sale ownership), 422 on date conflict, happy-path attach/detach/replace, search returns expected ordering.

Exit: `pytest backend/tests/plugins/yardsailing/test_routes.py` passes.

### Phase 4 — Plugin frontend: `GroupPicker`

1. New types in `SaleForm.tsx` (or a small sibling): `SaleGroup`, `GroupPickerProps`.
2. `GroupPicker` component: search input → debounced `/groups?q=` call via `bridge.callPluginApi`; results render as tappable rows; selected groups render as removable chips; "Create '<name>'" affordance appears when no exact match.
3. Inline `CreateGroupDialog` (Modal) with name (prefilled), description, optional date range (two date pickers reusing the existing picker infra).
4. Client-side date-window guard: a selected group whose window excludes the current sale dates renders in a disabled/warning state.
5. Wire the picker into `SaleForm` below the tag chips.

Exit: `tsc --noEmit` clean in the mobile project; plugin bundle rebuilds.

### Phase 5 — Plugin frontend: submit wiring

1. On `SaleForm` submit success (after `create_yard_sale` returns new id), call `POST /sales/{id}/groups` with the chosen group ids. If the call 422s, surface the per-group conflict inline and keep the sale (do not roll back).
2. Render `sale.groups` as subtitle chips in `DataCard` and in `SaleDetailsModal` header.

Exit: Manual smoke: create a group with a date window, create a sale inside that window and join it, edit sale dates outside the window — form blocks with inline error.

### Phase 6 — Map filter (mobile app, outside plugin bundle)

1. Map screen gains a "Groups" chip/sheet fed by `GET /groups`. Selecting a group passes `group_id` to the existing sale-fetch query.
2. Include a "Clear" affordance.

Exit: Manual smoke: filter map to a group, verify only member pins render.

### Phase 7 — Docs & ship

1. Update `help.md` with a "Groups" section explaining creation, joining, and filtering.
2. Update `plugin.json` `examples` with a group-related prompt (e.g. *"Find yard sales in the 100 Mile Sale"*).
3. Rebuild bundle, commit, PR, merge.

## Risks / Notes

- **LLM discoverability.** The `find-sales` skill description needs a sentence about groups so the LLM knows to extract group names from natural queries. Update skill description in `plugin.json`.
- **Case-insensitive uniqueness.** SQLAlchemy default is case-sensitive on SQLite; use `func.lower` in the uniqueness check (or a `CITEXT` equivalent if on Postgres — the current deploy is SQLite, so lowercase-on-write is simplest).
- **Slug collisions.** Use a small counter suffix loop (`foo`, `foo-2`, `foo-3`) — fine at this scale.
- **Sale dates vs group window boundary inclusivity.** Spec says inclusive on both ends (`>= start`, `<= end`). Tests pin this.
- **Plugin bundle size.** GroupPicker + CreateGroupDialog adds ~3–4 KB. Acceptable.

## Deliberate non-goals

- No moderation, no owner approval of sale joins.
- No group detail screen / feed.
- No recurring-event auto-rollover (100 Mile Sale's 2027 instance is a separate group row).
- No private groups / invite links.
- No geographic bounds on groups.
