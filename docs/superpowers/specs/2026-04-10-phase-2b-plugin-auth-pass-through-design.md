# Phase 2B Design: Plugin Auth Pass-Through + Chat-Triggered Login

**Date:** 2026-04-10
**Status:** Approved for implementation planning
**Related:** Phase 2 brainstorm at `2026-04-09-phase-2-brainstorm.md`; Phase 2A design at `2026-04-10-phase-2a-jain-identity-google-oauth-design.md`

## Overview

Phase 2B completes the identity story started in Phase 2A by wiring JAIN-authenticated requests through to plugin APIs. It delivers two coupled capabilities:

1. **Authentication as a core concern.** The JAIN backend forwards the authenticated user's identity to plugin APIs via a shared service key + trusted headers. Plugins don't verify JWTs themselves — they trust JAIN, look up users by email, and serve data. This is a one-time architectural investment: every future plugin reuses the same contract.

2. **Chat-triggered login UX.** When an anonymous user asks Jain to do something that requires authentication, Jain refuses with an inline "Sign in with Google" button. Tapping it opens the Google OAuth flow, and on success the original message auto-retries. No more "go to the Settings tab" detour.

After Phase 2B ships, `I want to create a yard sale` works end-to-end for the first time — from logged-out prompt, through inline login, through conversational gathering, to a real yard sale row in yardsailing's database.

## Goals

1. Move authentication entirely into JAIN core. Plugins are "dumb" — they trust JAIN via a shared service key and accept user identity as request headers.
2. Enable end-to-end create flows that require authentication (yardsailing's `create_yard_sale` being the immediate target).
3. Deliver the magic UX moment: sign in from inside the chat, continue where you left off without retyping.
4. Remove Phase 1 Layer 1 scaffolding (the `ChatRequest.auth` dict, the store's `setPluginAuth`, the SKILL.md STEP 1 auth check). The platform handles auth now, not each skill.
5. Keep yardsailing backward compatible — existing session cookie auth still works; JAIN integration is env-var gated.

## Non-Goals for Phase 2B

- **Apple Sign In, Facebook Sign In** — Phase 2C
- **iPhone Expo Go support** — still architecturally blocked; Phase 2A.1 (EAS dev build) handles that
- **Short-lived per-plugin tokens** — Phase 2B forwards a static service key; per-call short-lived tokens are a Phase 3 hardening move
- **Per-tool auth granularity beyond boolean** — `auth_required: true | false` is the full vocabulary. No "require premium," "require admin," etc.
- **Token refresh, remote sign-out, token revocation** — Phase 3
- **Alembic migrations for JAIN** — still on the Phase 3 hygiene list
- **Mobile unit tests** — Phase 3 hygiene
- **Phase 2B does NOT add Apple/Facebook client IDs to Google Cloud Console setup**

## Locked-in Design Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | JWT verification between JAIN ↔ yardsailing | **Not needed.** Shared service key + trusted user headers instead of per-plugin JWT verification |
| 2 | User matching in yardsailing | Match by email; auto-create yardsailing user if missing |
| 3 | Auth source of truth in chat router | JAIN JWT via optional FastAPI dependency; remove Phase 1 `ChatRequest.auth` field |
| 4a | Refusal trigger mechanism | Tool executor returns synthetic `{"error": "auth_required"}`; chat service short-circuits |
| 4b | UI rendering | Inline `<AuthPrompt />` component rendered under the refusal bubble |
| 5 | Post-login behavior | Auto-retry the original message via `pendingRetry` state in the store |
| 6a | Yardsailing integration point | Modify `get_current_user` with env-var-gated JAIN service-key branch |
| 6b | Yardsailing schema changes | None |
| 7 | Token forwarding scope | Always forward headers when user is authenticated — authentication is a core concern, not per-plugin |

## System Architecture

### Data flow: authenticated user creating a yard sale

```
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│ JAIN Mobile  │        │ JAIN Backend │        │  Yardsailing │
│              │        │              │        │              │
│ ChatScreen   │───1───▶│ /api/chat    │        │              │
│              │        │              │        │              │
│ Axios attaches│        │ get_current_│        │              │
│ Authorization│        │ user_optional│        │              │
│ Bearer <jwt>  │        │ reads header │        │              │
│              │        │ → User       │        │              │
│              │        │              │        │              │
│              │        │ ChatService  │        │              │
│              │        │ passes user  │        │              │
│              │        │ to context   │        │              │
│              │        │ builder +    │        │              │
│              │        │ tool executor│        │              │
│              │        │              │        │              │
│              │        │ LLM sees     │        │              │
│              │        │ "[user signed│        │              │
│              │        │  in as ...]" │        │              │
│              │        │ in system    │        │              │
│              │        │ prompt       │        │              │
│              │        │              │        │              │
│              │        │ LLM decides  │        │              │
│              │        │ to call      │        │              │
│              │        │ create_yard_ │        │              │
│              │        │ sale         │        │              │
│              │        │              │        │              │
│              │        │ ToolExecutor ├───2───▶│ POST /api/   │
│              │        │ forwards:    │        │ sales        │
│              │        │ X-Jain-      │        │              │
│              │        │ Service-Key, │        │ get_current_ │
│              │        │ X-Jain-User- │        │ user checks  │
│              │        │ Email,       │        │ service key  │
│              │        │ X-Jain-User- │        │ → valid →    │
│              │        │ Name         │        │ looks up     │
│              │        │              │        │ user by email│
│              │        │              │        │ → auto-      │
│              │        │              │        │ creates if   │
│              │        │              │        │ missing →    │
│              │        │              │◀───3───│ returns      │
│              │        │              │        │ yardsailing  │
│              │        │              │        │ user →       │
│              │        │              │        │ creates sale │
│              │        │              │        │              │
│              │◀───4───│ Final reply  │        │              │
│              │        │ flows back   │        │              │
└──────────────┘        └──────────────┘        └──────────────┘
```

### Data flow: anonymous user asking for something auth-required

```
User: "create a yard sale"
  → POST /api/chat (NO Authorization header)
  → Chat router: get_current_user_optional returns None
  → Context builder: "[user not authenticated...]" in system prompt
  → LLM decides to call create_yard_sale
  → ToolExecutor sees tool.auth_required=True AND user is None
  → Returns synthetic ToolResult(
      content='{"error": "auth_required", "plugin": "yardsailing"}'
    )
  → ChatService detects the auth_required error
  → Short-circuits: ChatReply(
      text="I'd love to help with that — you'll need to sign in first.",
      display_hint="auth_required",
      data={"plugin": "yardsailing"},
      tool_events=[...]  # the attempted call is logged
    )
  → Mobile ChatScreen renders refusal bubble + <AuthPrompt /> component
  → Mobile store: pendingRetry = "create a yard sale"
  → User taps login button
  → Google OAuth → JAIN JWT stored via tokenStorage → setSession(...)
  → useEffect in useChat detects session null → Session AND pendingRetry set
  → Fires send(pendingRetry), clears pendingRetry
  → Same flow as top of section, now authenticated, all the way to sale creation
```

## Backend Changes (JAIN)

### New files

```
backend/
├── app/
│   └── auth/
│       └── optional_user.py          # get_current_user_optional dep
```

### Modified files

| File | Change |
|------|--------|
| `app/schemas/chat.py` | Remove `auth: dict[str, bool]` field from `ChatRequest` |
| `app/routers/chat.py` | Add `Depends(get_current_user_optional)` param; pass user to chat service |
| `app/services/chat_service.py` | Accept optional `User` parameter; pass to context builder and tool executor; detect synthetic `auth_required` errors and short-circuit |
| `app/services/context_builder.py` | Build auth-state context line from `User | None` |
| `app/engine/tool_executor.py` | Accept `user: User \| None`; short-circuit auth-required tools when user is None; forward service-key headers when user is present |
| `app/plugins/schema.py` | Add `auth_required: bool = False` field to `ToolDef` |
| `app/config.py` | Add `JAIN_SERVICE_KEY: str = ""` (shared secret for plugin calls) |

### `get_current_user_optional` dependency

Reads `Authorization: Bearer ...` header. Returns:
- `User` if the JWT is valid, not expired, and the user exists in the DB
- `None` in all failure cases (missing header, bad JWT, expired, user deleted)

Does NOT raise 401. Anonymous chat must continue working for public tools.

### `ToolExecutor.execute(call, user)` signature change

```python
async def execute(self, call: ToolCall, user: User | None) -> ToolResult:
    plugin, tool = self.registry.find_tool(call.name)
    # ... plugin/tool lookup error handling (existing) ...

    # Phase 2B: gate auth-required tools
    if tool.auth_required and user is None:
        return ToolResult(
            tool_call_id=call.id,
            content=json.dumps({
                "error": "auth_required",
                "plugin": plugin.manifest.name,
            }),
        )

    # ... build URL, method, body as before ...

    headers = {"X-Requested-With": "XMLHttpRequest"}
    if user is not None:
        headers["X-Jain-Service-Key"] = settings.JAIN_SERVICE_KEY
        headers["X-Jain-User-Email"] = user.email
        headers["X-Jain-User-Name"] = user.name

    # ... existing HTTP call + error handling ...
```

**Key property:** JAIN's own JWT is never forwarded to plugins. Plugins only see the service key + email + name. The JWT stays inside JAIN as an internal implementation detail of JAIN's identity layer.

### ChatService short-circuit

After executing the tools in a round, inspect the tool results. If any result's content parses as JSON and has `error == "auth_required"`, the chat service returns:

```python
return ChatReply(
    text="I'd love to help with that — you'll need to sign in first.",
    data={"plugin": "<plugin-name>"},
    display_hint="auth_required",
    tool_events=tool_events,
)
```

The LLM's in-progress response (which triggered the tool call) is discarded. The user sees only the short "sign in first" message and the `<AuthPrompt />` button. The tool_events log still includes the attempted call for debugging.

### Context builder auth line

Phase 1 injected `[auth state: yardsailing=not_logged_in]`. Phase 2B replaces this with a generic global marker:

- `user is None` → `[user not authenticated — refuse auth-required requests and suggest signing in]`
- `user is not None` → `[user signed in as {email} ({name})]`

No per-plugin state. The LLM knows whether the user is authenticated globally, and the platform enforces the rest.

### Phase 1 Layer 1 removal

- `ChatRequest.auth: dict[str, bool]` field — **removed**
- Context builder's per-plugin auth_pairs logic — **removed**
- `create-sale/SKILL.md` Phase 1 STEP 1 auth check block — **removed** (platform handles it now, the SKILL.md just describes the conversational/form flow)

## Yardsailing Changes

Scope is deliberately minimal — three modifications to one file plus one config field.

### Modified files

```
yardsailing/backend/
├── app/
│   ├── config.py              # add JAIN_SERVICE_KEY env var
│   └── dependencies.py        # modify get_current_user with JAIN branch
```

No new routers, no new services, no new models, no migrations, **no pyjwt dependency.**

### `config.py` addition

```python
class Settings(BaseSettings):
    # ... existing yardsailing settings ...

    # Phase 2B JAIN integration — env-var gated.
    # When empty, the JAIN branch is disabled entirely and get_current_user
    # behaves exactly like pre-Phase-2B.
    JAIN_SERVICE_KEY: str = ""
```

### `get_current_user` modification

Current yardsailing `get_current_user` reads a session cookie and looks up a user. New version adds a branch at the top:

```python
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    # Phase 2B: accept JAIN service-key + trusted user headers.
    if settings.JAIN_SERVICE_KEY:
        service_key = request.headers.get("x-jain-service-key", "")
        if service_key and service_key == settings.JAIN_SERVICE_KEY:
            email = request.headers.get("x-jain-user-email", "").strip().lower()
            name = request.headers.get("x-jain-user-name", "").strip()
            if email:
                user = await _get_or_create_user_by_email(db, email, name)
                return user
        # If the service key is present but doesn't match, fall through to
        # existing session-cookie logic rather than 401 — the caller may still
        # have a valid yardsailing session.

    # ... existing session cookie logic unchanged ...
```

**Key properties:**

1. **Backward compatible.** The old session cookie path is untouched. Existing yardsailing users signing in via magic link keep working.
2. **Env-var gated.** With `JAIN_SERVICE_KEY=""`, the entire JAIN branch is skipped. Toggle JAIN integration on/off via env var, no code changes.
3. **Service key comparison.** Simple string equality against the env var. Forgery requires knowing the shared secret.
4. **Email normalization.** Lowercased and stripped for case-insensitive matching.
5. **Failed service key → fall through.** Doesn't 401 the request; yardsailing still has its own auth mechanism that may succeed.

### `_get_or_create_user_by_email` helper

```python
async def _get_or_create_user_by_email(
    db: AsyncSession, email: str, name: str
) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is not None:
        return user
    # Auto-provision for this JAIN identity
    user = User(
        email=email,
        name=name or email,
        # ... other required fields set to sensible defaults per yardsailing's User model ...
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
```

Lives in `dependencies.py` alongside `get_current_user`. Private to the module.

**Implementation note:** Yardsailing's existing `User` model schema is not fully inspected at spec time. The implementation plan's first yardsailing task will read `yardsailing/backend/app/models/user.py` to determine the exact `INSERT` field requirements before writing the auto-provision code. If required fields (password_hash, created_at defaults, etc.) need handling, the plan addresses them specifically rather than guessing.

### Security properties

- **Forgery:** impossible without the shared service key (same property as the JWT approach, but with simpler implementation)
- **Replay:** N/A — no tokens to replay; each HTTP request's authority is verified live against the shared key
- **Email trust:** JAIN only populates `X-Jain-User-Email` for users who have authenticated with Google (`email_verified: true`). So the email is Google-vouched before yardsailing sees it.
- **Header spoofing:** impossible without knowing the service key, because yardsailing only trusts the user headers after the service key check passes

### Interaction with yardsailing's existing payment gate

Yardsailing's `POST /api/sales` checks `count_user_sales(user.id)` and requires a payment token when the count is ≥ 1 (first sale free, subsequent sales $3 each). This logic stays unchanged in Phase 2B. The implications:

- **First JAIN-driven create for a newly auto-provisioned user:** succeeds without payment (count is 0).
- **First JAIN-driven create for a user who already has yardsailing sales from before:** requires a payment token, which Jain does not provide, so it 402s. The LLM receives the 402 error and explains to the user. Phase 2B does NOT handle Stripe payment flows — that's a dedicated future task.
- **Subsequent creates for any user:** same 402 behavior.

For Phase 2B acceptance, the test walkthrough should use a fresh Google account (or confirm that the existing account has 0 yardsailing sales) so the first create goes through cleanly without hitting the payment gate. This is a test-time consideration, not a design flaw — it's the existing yardsailing business logic working as designed.

## Mobile Changes

Mostly subtractive (removing Phase 1 Layer 1) plus the chat-triggered login button and auto-retry state.

### New files

```
mobile/src/chat/
└── AuthPrompt.tsx              # inline login button component
```

### Modified files

| File | Change |
|------|--------|
| `src/types.ts` | Expand `display_hint` to include `"auth_required"` (no breaking changes) |
| `src/api/chat.ts` | Remove `auth: Record<string, boolean>` from `sendChatMessage` params |
| `src/store/useAppStore.ts` | Remove `auth` + `setPluginAuth`. Add `pendingRetry: string \| null`, `setPendingRetry`, `clearPendingRetry` |
| `src/hooks/useChat.ts` | Stop sending `auth`. Set `pendingRetry` on `display_hint: "auth_required"`. Add `useEffect` for session-transition auto-retry |
| `src/screens/ChatScreen.tsx` | Render `<AuthPrompt />` below the last assistant message when `lastResponse.display_hint === "auth_required"` |
| `src/screens/SettingsScreen.tsx` | No direct changes — Settings-tab sign-in automatically triggers the same auto-retry effect because it updates `session` in the same store |

### `AuthPrompt` component

Dedicated small component in `src/chat/` alongside `MessageBubble`, `DataCard`, `ToolIndicator`. Renders as a card styled like a bubble:

- Headline: "Sign in to continue"
- Subtext: "You'll need to sign in with Google to continue with that request."
- Primary button: "Sign in with Google" — uses `useGoogleSignIn()` + `signInWithGoogle()` + `setToken()` + `setSession()`, same sequence as Settings
- "X" dismiss button in the corner — clears `pendingRetry` and hides the prompt

The component takes no plugin-specific props. The prompt text is generic because the user's mental model is "sign in" globally, not per-plugin.

### Auto-retry mechanism

`pendingRetry` is a string (the most recent user-message text that hit an `auth_required` refusal) or `null`. Managed in zustand.

```typescript
// in useChat
useEffect(() => {
  if (session && pendingRetry) {
    const message = pendingRetry;
    clearPendingRetry();
    setTimeout(() => send(message), 100);  // tick delay so UI updates first
  }
}, [session, pendingRetry]);
```

**Behavior:**

- Anonymous user asks for auth-required thing → `pendingRetry` set → taps login button → session flips → effect fires → auto-retry runs → success. ✓
- Already-signed-in user asks anything → no refusal → `pendingRetry` stays null → effect inert. ✓
- User asks something → refused → types a different message → first `pendingRetry` gets overwritten by the new user text (set before send). When they eventually sign in, the auto-retry fires the most recent pending message, which may be what they actually want. If they don't want the retry, they can tap the `<AuthPrompt />` X button to clear.
- Refused user signs in via Settings tab (not via the chat button) → session flips → effect fires → auto-retry runs if `pendingRetry` is still set → works.

### Setting `pendingRetry` in `useChat.send()`

```typescript
const send = async (text: string) => {
  // ...
  // Clear any stale pending retry when user manually sends a new message
  clearPendingRetry();

  // ... post to /api/chat ...

  if (res.display_hint === "auth_required") {
    setPendingRetry(text);
  }

  // ... other display_hint handling ...
};
```

Clearing on manual send prevents the stale-retry edge case.

### Removing Phase 1 Layer 1 scaffolding

- `auth: Record<string, boolean>` field on `AppState` — removed
- `setPluginAuth` method — removed
- Default `{ yardsailing: false }` initializer — removed
- All `store.auth` references in the codebase — removed

`tsc --noEmit` passing with zero errors is a success criterion. Any stale references surface there.

## Testing Strategy

### Backend (automated, TDD)

| Test file | Coverage |
|-----------|----------|
| `test_optional_user.py` (new) | Valid JWT → returns user; missing header → None; bad JWT → None; expired JWT → None; user not in DB → None |
| `test_plugin_schema.py` (updated) | `ToolDef.auth_required` defaults to `False`, accepts `True` |
| `test_tool_executor.py` (updated) | auth_required tool + no user → synthetic error (no HTTP call); auth_required tool + user → HTTP call with service-key headers; public tool + no user → anonymous call (existing); public tool + user → forwards service-key headers; headers contain expected values |
| `test_chat_service.py` (updated) | `send()` accepts optional user; auth_required tool result short-circuits to `display_hint: "auth_required"`; successful tool call with user flows normally; tool_events still logged on short-circuit |
| `test_context_builder.py` (updated) | `build_system_prompt(registry, user=None)` contains "user not authenticated"; `build_system_prompt(registry, user=User(...))` contains email and name |
| `test_chat_router.py` (updated) | Chat with valid Authorization → user resolved; chat with no header → anonymous; chat with expired JWT → anonymous (not 401); remove/update tests referencing old `auth: {}` field |

**Target:** ~68 existing Phase 2A tests + ~14 new/modified = **~82 tests**, all green.

### Yardsailing (automated)

| Test file | Coverage |
|-----------|----------|
| `tests/test_jain_service_auth.py` (new) | Valid service key + user headers + email found → returns existing user; valid service key + user headers + email new → auto-creates user; missing service key header → falls through to session cookie logic; wrong service key → falls through; `JAIN_SERVICE_KEY` empty in settings → branch disabled entirely; missing email header → falls through; email normalization (case, whitespace) works |

Existing yardsailing test suite remains 100% green.

### Mobile (manual smoke tests)

Phase 2B continues the "no automated mobile tests" pattern. Manual verification:

1. Logged out, ask `find yard sales near me` → works, no login prompt
2. Logged out, ask `I want to create a yard sale` → Jain refuses with inline `<AuthPrompt />`
3. Tap the inline login button → OAuth → return to chat → auto-retry fires → Jain continues ("What's the address?")
4. Complete the conversational create flow → real sale lands in yardsailing's DB
5. Sign out → ask create-sale again → refusal + login button reappears
6. Sign in via Settings tab (not via the inline button) → if you had a pending retry, it fires when you navigate back to chat; otherwise no-op
7. Verify no references to `auth: { yardsailing: ... }` anywhere; `tsc --noEmit` passes

## Deployment / Ops

### JAIN `.env` additions

```env
# Shared key for JAIN ↔ plugin service-to-service calls
JAIN_SERVICE_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">
```

### Yardsailing `.env` additions

```env
# Same key as JAIN_SERVICE_KEY in JAIN's .env. When empty, the JAIN
# integration branch in get_current_user is skipped entirely.
JAIN_SERVICE_KEY=<paste same value as in JAIN>
```

**Rotation:** Generate a new value with `secrets.token_urlsafe(32)`, paste into both `.env` files, restart both backends. No code changes required.

### No database migrations

Neither JAIN nor yardsailing changes schema in Phase 2B. Create-time `Base.metadata.create_all()` handles everything.

## Error Handling

### JAIN backend

| Scenario | Response |
|----------|----------|
| Chat request with no Authorization header | 200, user = None, anonymous flow |
| Chat request with malformed JWT | 200, user = None (optional dep catches silently) |
| Chat request with expired JWT | 200, user = None |
| Chat request with JWT for deleted user | 200, user = None |
| Tool call to auth-required tool by anonymous user | Synthetic ToolResult → chat service short-circuits to `display_hint: "auth_required"` |
| Plugin HTTP 500 after forwarding headers | Wrapped in error dict, LLM receives and explains |
| Plugin HTTP 401 (service key rejected) | Same as 500 — config error, shouldn't happen at runtime |
| `JAIN_SERVICE_KEY` empty in JAIN config | Headers sent with empty value; yardsailing rejects, falls through to cookies (no cookie → 401 → LLM explains). This is a misconfiguration, not a user error. |

### Yardsailing backend

| Scenario | Response |
|----------|----------|
| Service key valid, email missing | Fall through to session cookie logic |
| Service key valid, user auto-provision fails (DB constraint) | 500 — let exception propagate; indicates a bug in the INSERT |
| Service key valid, email is garbage | Existing column validation catches it; 422 |
| Public GET `/api/sales` with JAIN headers but no cookie | Route doesn't depend on `get_current_user`; headers ignored; works normally |

### Mobile

| Scenario | UX |
|----------|-----|
| Chat response has `display_hint: "auth_required"` | Render `<AuthPrompt />` below bubble; set `pendingRetry` |
| User taps login button → OAuth cancelled | Silent; prompt stays; `pendingRetry` stays set |
| Login succeeds → auto-retry → retry also fails | Show the new error normally; `pendingRetry` already cleared; no infinite loop |
| User dismisses prompt (X button) | Clears `pendingRetry`; prompt disappears |
| Session expires mid-session | Backend treats them as anonymous on next request; they get the prompt again if they try something auth-required |

## Success Criteria

- [ ] JAIN backend: all existing Phase 1 + 2A tests pass; ~14 new/modified tests pass; target ~82 total tests green
- [ ] JAIN backend: `get_current_user_optional` returns user for valid JWT, None otherwise
- [ ] JAIN backend: `ToolDef.auth_required: true` + no user → tool executor returns synthetic error without HTTP call
- [ ] JAIN backend: tool executor forwards `X-Jain-Service-Key`, `X-Jain-User-Email`, `X-Jain-User-Name` headers on all plugin calls when user is authenticated
- [ ] JAIN backend: chat service short-circuits auth-required errors to `display_hint: "auth_required"`
- [ ] JAIN backend: Phase 1 `ChatRequest.auth: dict[str, bool]` field is removed; context builder no longer references it
- [ ] Yardsailing: all existing tests still pass
- [ ] Yardsailing: 6-8 new tests for the JAIN service-key branch in `get_current_user`
- [ ] Yardsailing: `JAIN_SERVICE_KEY` config field added; empty default means disabled
- [ ] Yardsailing: `get_current_user` accepts JAIN service-key + user headers; backward compatible (old sessions still work)
- [ ] Yardsailing: auto-provisions a user when email from header doesn't match existing row
- [ ] Mobile: `sendChatMessage` no longer sends an `auth` field
- [ ] Mobile: Phase 1 `auth: Record<string, boolean>` and `setPluginAuth` removed from store
- [ ] Mobile: `pendingRetry` state added to store; cleared on manual send and on successful retry
- [ ] Mobile: `<AuthPrompt />` component renders when `lastResponse.display_hint === "auth_required"`
- [ ] Mobile: Tapping the inline login button triggers the same Google OAuth flow as Settings tab
- [ ] Mobile: Auto-retry fires when session transitions null → non-null AND pendingRetry is set
- [ ] Mobile: `tsc --noEmit` passes with zero errors
- [ ] `create-sale` plugin SKILL.md no longer has the Phase 1 Layer 1 STEP 1 auth check
- [ ] End-to-end: logged-out user asks "create a yard sale" → refusal + inline login → taps button → Google OAuth → returns → Jain continues conversation → completes create → real sale in yardsailing's DB under the correct user (matched by email). **Acceptance must be run with a fresh Google account (or an existing account that has 0 yardsailing sales) to avoid the existing yardsailing payment gate on subsequent sales.**
- [ ] Phase 1 regression: `find_yard_sales` still works anonymously; map pins still render

## Open Questions (for implementation plan)

1. **Yardsailing User model required fields** — the first yardsailing task must inspect `yardsailing/backend/app/models/user.py` and identify required fields that need values during auto-provisioning. Plan will address specifics after inspection.
2. **SKILL.md `auth_required` declaration** — the plan needs to update `jain-plugins/plugins/yardsailing/skills/create-sale/tools.json` to set `"auth_required": true` on `create_yard_sale`, and `skills/manage-sales/tools.json` to set it on `update_yard_sale` / `delete_yard_sale`. `find_yard_sales` and `get_my_sales` stay without it (reads are public or gracefully handle unauthenticated).
3. **Axios interceptor on mobile** — already attaches JAIN JWT to every backend request. Phase 2B doesn't change this; we just start using it on the server side.
4. **Pending retry edge case** — if the user manually sends a message between the refusal and the sign-in, `pendingRetry` gets overwritten. Resolved by clearing on every manual send (documented above).
5. **Yardsailing payment gate on second+ sales** — Phase 2B does not handle Stripe payment flows. Users who already have 1+ sales on yardsailing will hit a 402 on their second JAIN-driven create. Phase 2B test walkthrough uses a fresh account to avoid this. Handling the payment flow through Jain is a future task (Phase 3 or later).
