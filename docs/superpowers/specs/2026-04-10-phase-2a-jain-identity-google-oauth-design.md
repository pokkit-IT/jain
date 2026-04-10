# Phase 2A Design: JAIN Identity + Google OAuth

**Date:** 2026-04-10
**Status:** Approved for implementation planning
**Related:** Phase 2 brainstorm at `2026-04-09-phase-2-brainstorm.md`; Phase 1 spec at `2026-04-09-jain-phase-1-design.md`

## Overview

Sub-project A of Phase 2 adds a real user identity layer to JAIN. Users sign in with their Google account from the Settings tab. The backend verifies Google ID tokens, stores users in its own `users` table, and issues a 30-day HS256 JWT that the mobile app stores securely and sends on subsequent requests.

This is the foundation layer. Sub-projects B (plugin auth pass-through + yardsailing JWT bridge), C (Apple Sign In + chat-triggered sign-in), and D (Ollama provider) all depend on A being in place.

## Goals

1. Give JAIN its own user identity — not borrowed from any plugin
2. Ship the smallest possible sign-in flow: Settings tab → Google → profile visible → done
3. Keep the Phase 1 Expo Go workflow intact (no native module rebuild required)
4. Stay stateless on the backend — no session tables, no refresh token rotation
5. Personal-use / Testing mode — no Google app verification, no privacy policy requirements yet

## Non-Goals for Sub-project A

- **Token refresh flow** — single 30-day access token, re-sign-in when it expires
- **Apple Sign In, Facebook Sign In** — sub-project C
- **Chat-triggered sign-in prompt (LoginModal from chat)** — sub-project B
- **Tool executor forwarding JAIN JWT to plugins** — sub-project B
- **Yardsailing JWT bridge endpoint** — sub-project B
- **Real yard sale creation via Jain** — sub-project B (depends on A + B both shipping)
- **Account deletion / data export** — Phase 3
- **Remote sign-out / token revocation** — Phase 3
- **Avatar upload / profile editing inside JAIN** — Phase 3 (profile fields are read-only from Google)
- **Alembic migrations** — Phase 3 hygiene (see Open Questions)
- **Mobile unit/integration tests** — Phase 3 hygiene

## Architecture

### System flow

```
┌─────────────────┐         ┌─────────────────┐         ┌──────────────┐
│   JAIN Mobile   │         │  JAIN Backend   │         │    Google    │
│                 │         │                 │         │              │
│  Settings tab   │         │ /api/auth/google│         │  OAuth 2.0   │
│  "Sign in" btn  │─────1──▶│                 │         │  endpoint    │
│                 │         │                 │         │              │
│  expo-auth-     │◀────2───│                 │         │              │
│  session opens  │         │                 │         │              │
│  in-app browser │─────3──▶│                 │◀────────│              │
│                 │         │                 │         │              │
│                 │◀────4───│                 │         │              │
│                 │         │                 │         │              │
│  Sends ID token │─────5──▶│ Verifies token, │         │              │
│  to backend     │         │ creates/updates │         │              │
│                 │         │ user, issues    │         │              │
│                 │◀────6───│ JAIN JWT        │         │              │
│  Stores JWT     │         │                 │         │              │
│  in secure      │         │                 │         │              │
│  store          │         │                 │         │              │
└─────────────────┘         └─────────────────┘         └──────────────┘
```

1. User taps "Sign in with Google" in Settings
2. Mobile opens Google OAuth via `expo-auth-session`
3. User authenticates with Google in the in-app browser
4. Google returns an ID token to the mobile device via the redirect URI
5. Mobile sends ID token to `POST /api/auth/google`
6. Backend verifies the ID token against Google's public keys, upserts the user row, signs a 30-day HS256 JWT, returns it plus the user record

Key property: **Google is consulted exactly twice per sign-in** — once during the OAuth dance (step 3, from the mobile device), once during token verification (step 5, from the backend). After sign-in, JAIN never calls Google again until the next sign-in.

### Locked-in design decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Google verification | ID token verification, not auth code exchange | Identity only, no Google API access needed, stateless |
| 2 | User table schema | id, email, email_verified, google_sub, name, picture_url, timestamps | Minimum viable profile; extensible for future providers |
| 3 | JAIN JWT lifetime | 30-day HS256 access token, no refresh | Simple, appropriate for a personal-use app |
| 4 | Mobile sign-in method | `expo-auth-session` in-app browser | Stays in Expo Go workflow; no native module rebuild |
| 5 | Sign-in trigger | Settings tab only | Chat-triggered deferred to sub-project B |
| 6 | Google Cloud project | Personal use / Testing mode | Ship in days, not weeks |

## Backend Changes

All changes in the `jain` repo under `backend/`. Zero changes to `jain-plugins` or `yardsailing`.

### New files

```
backend/
├── app/
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── jwt.py                    # sign/verify JAIN JWTs
│   │   ├── google_verify.py          # verify Google ID tokens
│   │   └── dependencies.py           # get_current_user FastAPI dep
│   ├── models/
│   │   └── user.py                   # SQLAlchemy User model
│   ├── schemas/
│   │   └── auth.py                   # Pydantic request/response
│   ├── services/
│   │   └── user_service.py           # upsert/lookup users
│   └── routers/
│       └── auth.py                   # /api/auth/* endpoints
└── tests/
    ├── test_auth_jwt.py              # sign+verify, tampered, expired
    ├── test_google_verify.py         # mocked Google verification
    ├── test_user_service.py          # upsert idempotency, email match
    └── test_auth_router.py           # endpoint integration
```

### Modified files

- `backend/app/config.py` — add `GOOGLE_CLIENT_ID`, `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_DAYS`
- `backend/app/main.py` — register the new auth router
- `backend/app/database.py` — no change (User is registered via the models import; `Base.metadata.create_all()` picks it up)
- `backend/requirements.txt` — add `google-auth>=2.35.0`, `pyjwt>=2.9.0`

### User table schema

```python
# backend/app/models/user.py
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    picture_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

`google_sub` is nullable now because sub-project C will add `apple_sub`, `facebook_sub`, etc. — a single user row can link to multiple providers over time. `email` remains the canonical match key for the Phase 2B yardsailing bridge.

### Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/auth/google` | none | Verify Google ID token, upsert user, return JAIN JWT + user |
| `GET` | `/api/auth/me` | JAIN JWT | Return the current user record |

### `POST /api/auth/google` flow

1. Accepts `{ id_token: str }` (Pydantic validation on the body)
2. Calls `google_verify.verify_id_token(id_token)` which returns a dataclass with `sub`, `email`, `email_verified`, `name`, `picture`, or raises `InvalidGoogleTokenError`
3. If `email_verified is False`, raise 401 (refuse to create users with unverified emails)
4. Calls `user_service.upsert_by_google(verified_claims)`:
   - If a user row exists with matching `google_sub` → update `name`, `picture_url`, `last_login_at`, return it
   - Else if a user row exists with matching `email` → link `google_sub` to that row, update profile fields, return it
   - Else → insert a new user row
5. Calls `jwt.sign_access_token(user)` which returns a 30-day HS256 JWT with claims `{ sub: str(user.id), email: user.email, name: user.name, iat, exp }`
6. Returns `{ access_token: str, user: UserOut }`

### `GET /api/auth/me` flow

1. Uses `Depends(get_current_user)` — a FastAPI dependency that:
   - Reads `Authorization: Bearer <jwt>` header (401 if missing)
   - Calls `jwt.verify_access_token(jwt)` (401 if invalid/expired)
   - Loads the user from DB by `sub` claim (401 if not found — catches deleted users)
   - Returns the `User` instance
2. Returns the user record as a Pydantic `UserOut` schema

### Configuration (`.env`)

```env
# Google OAuth
GOOGLE_CLIENT_ID=<from Google Cloud Console — Web client type>

# JAIN JWT signing
JWT_SECRET=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">
JWT_ALGORITHM=HS256
JWT_EXPIRE_DAYS=30
```

## Mobile Changes

All changes in the `jain` repo under `mobile/`. No `expo prebuild`; no native module rebuild.

### New files

```
mobile/
└── src/
    ├── auth/
    │   ├── googleAuth.ts             # expo-auth-session Google flow
    │   └── tokenStorage.ts           # expo-secure-store wrapper
    └── api/
        └── auth.ts                   # POST /api/auth/google, GET /api/auth/me
```

### Modified files

- `mobile/src/store/useAppStore.ts` — replace the placeholder `auth: { yardsailing: false }` (which stays in parallel for sub-project B) with an additional `session: { user, token } | null` field plus actions `signIn(session)` / `signOut()` / `setSession(session)`
- `mobile/src/api/client.ts` — add an axios request interceptor that reads the stored JWT via `tokenStorage.getToken()` and sets `Authorization: Bearer <jwt>` on every request
- `mobile/src/screens/SettingsScreen.tsx` — add the Account section above the LLM and Plugins sections
- `mobile/App.tsx` — on mount, hydrate `useAppStore.session` from secure storage and call `/api/auth/me` to validate the token. If valid, keep session. If 401, clear storage and show logged-out state. If network error, keep the cached session optimistically
- `mobile/package.json` — add `expo-auth-session`, `expo-crypto`, `expo-web-browser` (all installed via `npx expo install`)
- `mobile/app.json` — add `"scheme": "jain"` if not already present, for OAuth redirect handling

### New dependencies

| Package | Purpose |
|---------|---------|
| `expo-auth-session` | OAuth flow handler |
| `expo-crypto` | PKCE support for `expo-auth-session` |
| `expo-web-browser` | In-app browser for OAuth redirect |
| `expo-secure-store` | JWT storage (already installed for another use; reused) |

### Store shape (after sub-project A)

```typescript
// Relevant additions to useAppStore
session: {
  user: { id: string; email: string; name: string; pictureUrl: string | null };
  token: string;
} | null;

signIn: (session: Session) => void;
signOut: () => void;
setSession: (session: Session | null) => void;
```

The `auth: { yardsailing: boolean }` field from Phase 1 Layer 1 **stays** during sub-project A. Sub-project B will migrate it to derive from `session` once the yardsailing JWT bridge exists. Keeping both simplifies the sub-project A diff.

### User experience

#### First launch (logged out)

- App loads, no stored token, `session = null`
- Settings tab shows:
  - Account section: "Not signed in" + "Sign in with Google" button
  - LLM section (unchanged from Phase 1)
  - Installed Plugins section (unchanged from Phase 1)
- Chat works anonymously exactly like Phase 1 — no JWT sent, Jain still refuses create-sale per Layer 1

#### Tap "Sign in with Google"

1. `googleAuth.signIn()` is called
2. `expo-auth-session` opens the in-app browser to Google
3. User signs in, Google redirects back to the app with an ID token in the URL fragment
4. App sends the ID token to `POST /api/auth/google`
5. Backend returns a JAIN JWT + user record
6. App stores the JWT via `tokenStorage.setToken(jwt)` and updates `useAppStore.session`
7. Settings re-renders to show the user's avatar, name, email, and a "Sign out" button

#### Subsequent launches (logged in)

- App reads stored token from secure store
- Axios interceptor adds `Authorization: Bearer ...` to every backend request
- App calls `GET /api/auth/me` in the background to verify the token is still valid
- If 200: user is logged in, Settings shows the profile immediately
- If 401: clear storage, show logged-out state
- If network error: keep cached session optimistically; subsequent requests will surface any auth issue

#### Tap "Sign out"

- `tokenStorage.clearToken()` removes the JWT
- `useAppStore.signOut()` clears `session`
- Settings re-renders to logged-out state
- No backend call — JAIN has no session state to invalidate; the token just stops being sent

### Settings screen layout

**Logged out:**
```
┌──────────────────────────────┐
│         Settings             │
├──────────────────────────────┤
│  Account                     │
│  Not signed in               │
│  [ Sign in with Google ]     │
├──────────────────────────────┤
│  LLM                         │
│  Provider: anthropic         │
│  Model: claude-sonnet-4-...  │
│  Mode: copilot               │
├──────────────────────────────┤
│  Installed Plugins           │
│  yardsailing v1.0.0          │
│  Find, create, and manage... │
└──────────────────────────────┘
```

**Logged in:**
```
┌──────────────────────────────┐
│         Settings             │
├──────────────────────────────┤
│  Account                     │
│  ┌────┐                      │
│  │ JS │  Jim Shelly          │
│  └────┘  jim@gmail.com       │
│  [ Sign out ]                │
├──────────────────────────────┤
│  LLM (unchanged)             │
│  Installed Plugins (unchanged)│
└──────────────────────────────┘
```

## Testing Strategy

### Backend (automated, TDD)

| Test file | Coverage |
|-----------|----------|
| `test_auth_jwt.py` | Sign + verify roundtrip; tampered signature rejected; expired token rejected; missing claims rejected |
| `test_google_verify.py` | Mocks `google-auth`'s `id_token.verify_oauth2_token`. Valid token returns dataclass; invalid signature / wrong audience / expired token raise `InvalidGoogleTokenError` |
| `test_user_service.py` | New user insert; existing user matched by `google_sub` updates profile; existing user matched by `email` links `google_sub`; upsert is idempotent under concurrent calls |
| `test_auth_router.py` | `POST /api/auth/google` with mocked verifier: success returns JWT + user; malformed body returns 422; invalid Google token returns 401; unverified email returns 401. `GET /api/auth/me` with valid JWT returns user; with no JWT returns 401; with expired JWT returns 401; with JWT for deleted user returns 401 |

Target: ~15–20 new tests, existing Phase 1 suite (37 tests) keeps passing, total ~55 tests green.

### Mobile (manual smoke tests)

Phase 1 shipped without any mobile tests. Sub-project A continues that pattern — adding a mobile test framework is Phase 3 hygiene. Manual verification:

1. App launches logged-out, Settings shows "Sign in with Google"
2. Tap sign-in, complete Google OAuth, return to app, Settings shows profile
3. Close and reopen app — still logged in, profile visible immediately
4. Tap "Sign out", Settings reverts to logged-out, token gone from secure store
5. Sign in, manually delete the token from secure store, reopen — should fall back to logged-out gracefully (tests the `/api/auth/me` revalidation path)
6. Chat still works after sign-in — yardsailing find still works; create still politely refuses (sub-project A doesn't wire JWT into plugin calls)

## Deployment / Ops

### Google Cloud Console setup (user-performed)

The implementation plan will include this checklist verbatim:

1. Open https://console.cloud.google.com and create a new project named "JAIN" (or reuse an existing one)
2. **APIs & Services → OAuth consent screen**
   - User type: **External**
   - Publishing status: **Testing** (leave it here — Production requires Google app verification)
   - App name: `JAIN`
   - User support email: your Google account email
   - Developer contact: your Google account email
   - Scopes: select `email`, `profile`, `openid` (nothing else)
   - Test users: add your own Google account email (required while in Testing mode)
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Web application**
   - Name: `JAIN Expo Proxy`
   - Authorized redirect URIs: `https://auth.expo.io/@<your-expo-username>/jain`
     - Find your Expo username by running `npx expo whoami` in the mobile directory, or at expo.dev
4. Click Create. Copy the **Client ID** — that's your `GOOGLE_CLIENT_ID`
5. No Client Secret is needed for the Expo AuthSession proxy flow (PKCE handles it)

### JWT secret generation

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Produces a ~43-character base64 string. Paste into `.env` as `JWT_SECRET`.

### Database migration

Phase 1 uses SQLAlchemy `Base.metadata.create_all()` in the lifespan — no Alembic. Sub-project A adds a new table (`users`) but doesn't require Alembic because the lifespan still calls `create_all()` at startup and existing tables are unmodified. **Adding Alembic before sub-projects B/C/D is recommended** (Open Question 2), because those sub-projects may alter existing tables, but it's not a blocker for sub-project A.

## Error Handling

### Backend

| Scenario | Response |
|----------|----------|
| Missing `id_token` in body | 422 (Pydantic validation) |
| Invalid Google ID token signature | 401 `{"detail": "invalid google token"}` |
| Google ID token expired | 401 `{"detail": "invalid google token"}` |
| Google ID token `aud` mismatch | 401 `{"detail": "invalid google token"}` |
| `email_verified: false` in Google claims | 401 `{"detail": "email not verified"}` |
| Database error during upsert | 500 (existing FastAPI exception handler logs and returns generic error) |
| `/api/auth/me` with no Authorization header | 401 |
| `/api/auth/me` with bad/expired JWT | 401 |
| `/api/auth/me` with valid JWT but user not in DB | 401 |

### Mobile

| Scenario | UX |
|----------|-----|
| User cancels the OAuth browser | Silent: Settings stays on "Sign in with Google" button |
| Network failure during `/api/auth/google` | Alert: "Sign-in failed. Check your connection and try again." Button re-enabled |
| Backend returns 401 | Same alert — don't leak which validation step failed |
| Backend returns 500 | Alert: "Sign-in failed. Try again later." |
| `/api/auth/me` returns 401 on app launch | Silently clear token, show logged-out UI (no error alert) |
| `/api/auth/me` network error on app launch | Keep cached session visible; later requests will surface auth issues |

## Success Criteria

- [ ] Backend: `POST /api/auth/google` accepts a valid Google ID token, creates/updates a user, returns a JAIN JWT + user record
- [ ] Backend: `GET /api/auth/me` returns the current user for a valid JWT, 401 otherwise
- [ ] Backend: all new tests pass; existing Phase 1 tests still pass (target ~55 tests total, all green)
- [ ] Backend: sign-in with `email_verified: false` is rejected with 401
- [ ] Mobile: Settings tab shows "Sign in with Google" button when logged out
- [ ] Mobile: tapping the button completes the OAuth flow and shows the user's profile (name, email, picture) in Settings
- [ ] Mobile: closing and reopening the app preserves the logged-in state
- [ ] Mobile: tapping "Sign out" clears the stored token and reverts to logged-out UI
- [ ] Mobile: Phase 1 Layer 1 auth behavior still works — Jain still refuses create-sale politely because sub-project A doesn't wire JWT into plugin calls (fixing that is sub-project B)
- [ ] User can complete the Google Cloud Console setup using the implementation plan's checklist without asking follow-up questions

## Open Questions (flagged for implementation plan or later sub-projects)

1. **Exact `app.json` changes for OAuth redirect** — `scheme` field and any iOS/Android URL handler config. Will be resolved during plan writing when we verify against the current Expo SDK version.
2. **Alembic adoption** — Phase 3 hygiene. Not blocking sub-project A, but sub-projects B/C/D may want it before modifying existing tables. Decide at the end of sub-project A whether to slot Alembic before B or defer.
3. **Axios interceptor injection point** — whether to use `apiClient.interceptors.request.use(...)` at module load (simplest) vs. configure it from a React hook (allows reacting to sign-out via state). Resolve during plan writing; simplest path is module-load with the store accessed via `useAppStore.getState()`.
4. **`last_login_at` semantics** — updated on every sign-in, or only when a new JWT is issued (which is the same thing for sub-project A since there's no refresh)? Resolve during plan writing; default is "on every POST /api/auth/google call."
