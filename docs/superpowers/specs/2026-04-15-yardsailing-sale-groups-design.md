# Yardsailing Sale Groups — Design Spec

**Date:** 2026-04-15
**Status:** Draft
**Plugin:** yardsailing (internal)

## Goal

Let users coordinate multiple individual sales under a named group — e.g. "Maple Street Neighborhood Sale" or "100 Mile Yard Sale" (an annual event on the first weekend of May). Buyers can filter the map/list to a specific group. Groups are lightweight: anyone can create one, any sale can join multiple groups.

## Scope

- **Anyone can create a group.** No admin gating in v1.
- **Many-to-many.** A sale can belong to zero or more groups; a group contains zero or more sales.
- **Optional date window.** A group can declare a required `start_date`/`end_date`. If set, a sale's dates must fall entirely within that window to join the group. Open-ended groups (no window) accept any sale.
- **Public by default.** All groups are discoverable in v1. No private/invite-only groups.
- **No membership approval.** Any sale owner can attach their sale to any group that accepts the dates. (A future iteration can add owner-moderated groups.)

Out of scope for v1: moderation, membership requests, geographic bounds on groups, recurring annual events that auto-roll their dates year-over-year.

## User Flow

### Owner — attach sale to groups

In `SaleForm`, a new "Groups" section below the tag chips:
- A search field with "Find or create a group…" placeholder.
- Typing shows matching groups (by name, prefix match). Each result is a chip with the group name plus its date window (if any).
- Tapping a result adds that group to the sale's `groups` set. Selected groups render as removable chips above the search field.
- If no result matches, a "Create '<name>'" option appears. Tapping it opens a small inline dialog: name (prefilled), optional description, optional start/end dates. Submit creates the group and attaches it.
- Client-side guard: the sale's current `start_date`/`end_date` must fall within any selected group's window. If not, the group chip is disabled with a tooltip-style hint ("This group runs May 1–3; your sale dates don't match").

### Buyer — filter by group

- Map tab gains a "Groups" control alongside the existing tag filter. Tapping opens a sheet listing public groups (by name, sorted by upcoming date window first, then alphabetical). Selecting one filters map pins to only sales in that group.
- Chat / "find sales" flow: the LLM can accept `group` as a search param (e.g. "yard sales in the 100 mile sale"). The backend search endpoint gets a `group_id` filter.

### Group detail (future, not v1)

Out of scope: dedicated group detail page, group feed, RSVP, follower notifications.

## Architecture

### Backend

**New models** — `backend/app/plugins/yardsailing/models.py`:

`SaleGroup`:
| Column        | Type         | Notes                                          |
|---------------|--------------|------------------------------------------------|
| `id`          | `str(36)` PK | UUID4                                          |
| `name`        | `str(120)`   | Unique (case-insensitive)                      |
| `slug`        | `str(140)`   | Unique, derived from name                      |
| `description` | `str(500)`   | Nullable                                       |
| `start_date`  | `date`       | Nullable; required window start                |
| `end_date`    | `date`       | Nullable; required window end                  |
| `created_by`  | `str(36)` FK | `users.id`                                     |
| `created_at`  | `datetime`   |                                                |

`SaleGroupMembership` (join table):
| Column       | Type         | Notes                                      |
|--------------|--------------|--------------------------------------------|
| `sale_id`    | `str(36)` FK | `sales.id`, `ON DELETE CASCADE`            |
| `group_id`   | `str(36)` FK | `sale_groups.id`, `ON DELETE CASCADE`      |
| `created_at` | `datetime`   |                                            |

Primary key: `(sale_id, group_id)`.

Relationships: `Sale.groups = relationship(SaleGroup, secondary=SaleGroupMembership)` and reverse.

**New module** — `backend/app/plugins/yardsailing/groups.py`:
- `async def search_groups(db, query: str, limit=20) -> list[SaleGroup]` — case-insensitive prefix match on `name`.
- `async def create_group(db, user, name, description=None, start_date=None, end_date=None) -> SaleGroup` — slugifies, enforces unique name, returns the row.
- `async def attach_sale_to_group(db, sale, group) -> None` — validates the date-window constraint; raises a typed error if the sale falls outside the window. Idempotent.
- `async def detach_sale_from_group(db, sale, group) -> None` — removes membership; idempotent.
- `def validate_dates_within_group(sale, group) -> bool` — reusable guard.

**Endpoints** — `backend/app/plugins/yardsailing/routes.py`:
- `GET /api/plugins/yardsailing/groups?q=<query>&limit=20` — search groups (prefix, public).
- `POST /api/plugins/yardsailing/groups` — create. Body: `{name, description?, start_date?, end_date?}`.
- `GET /api/plugins/yardsailing/groups/{id}` — group details + computed `sales_count`.
- `GET /api/plugins/yardsailing/groups/{id}/sales` — list member sales (same shape as `/sales` listing).
- `POST /api/plugins/yardsailing/sales/{sale_id}/groups` — body `{group_ids: [...]}` — replace the sale's group set. Owner-only. Validates every group's date window; returns 422 with per-group error details if any fail.
- `GET /api/plugins/yardsailing/sales` — add optional `?group_id=<id>` filter.

Sale serialization (`services.serialize_sale`) gets a new `groups: [{id, name, slug, start_date, end_date}]` field.

### Frontend (plugin bundle)

`SaleForm.tsx`:
- New state `groups: SaleGroup[]` on `SaleFormData`.
- New `GroupPicker` sub-component: search input with debounced `/groups?q=` call, selected-chip list, "Create new" affordance opening an inline `CreateGroupDialog`.
- On submit, after `create_yard_sale` returns the new sale id, call `POST /sales/{id}/groups` with the chosen group ids.
- If the sale's dates change and a selected group no longer fits, show an inline warning next to the chip and block submit until resolved.

`DataCard` (map/chat sale rows):
- Render selected group names as small subtitle chips below the title, when `sale.groups.length > 0`.

`SaleDetailsModal`:
- Show group chips in the header section. Tapping a chip (future) would filter the map to that group; v1 is display-only.

Map tab filter UI (out of this plugin's bundle — in the mobile app's map screen):
- Group filter chip/sheet fed by `GET /groups`. Feeds `group_id` into the existing pin fetch.

### Migrations

- Add `sale_groups` table.
- Add `sale_group_memberships` table.
- No changes to existing `sales` schema (relationship is via the join table).

## Validation Rules

- `group.name` is 2–120 chars, unique (case-insensitive).
- `group.start_date` ≤ `group.end_date` when both set; both-or-neither (either both null or both present).
- On attach: if the group has a date window, `sale.start_date >= group.start_date` AND `(sale.end_date ?? sale.start_date) <= group.end_date`. Otherwise, allow.
- If a sale's dates are edited after joining a group: the update endpoint re-validates every group membership and returns 422 if any would be invalidated. The client surfaces which groups need to be removed before saving.

## Test Plan

- Backend unit tests for `groups.py` (search, create, slug collisions, date-window validation, attach/detach idempotency).
- Backend route tests for each endpoint, including 422 paths for date conflicts and cross-user writes.
- Sale-serialization test: `groups` field present, ordered deterministically.
- Frontend: tsc clean, manual smoke through the SaleForm group picker (search, create, attach, date-conflict block).

## Open Questions

- Should group search be prefix-only or full-text? (v1: prefix — matches iMessage/Slack autocomplete feel; revisit if users complain.)
- Should the group detail endpoint expose `created_by`? (v1: yes, as id + display name, for future moderation hooks.)
