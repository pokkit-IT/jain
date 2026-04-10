# JAIN Phase 2 Brainstorm

**Date:** 2026-04-09 (created at end of Phase 1)
**Status:** Backlog — needs full brainstorming + spec before implementation

This document captures the architectural questions and design space for Phase 2. It is **not** a spec — it's the seed for a future brainstorming session.

## What Phase 2 needs to deliver

The Phase 1 acceptance run made it clear that the create-flow gap is the biggest blocker for JAIN being useful end-to-end. Phase 2 must deliver:

1. **Real authentication** so Jain can perform writes on behalf of the user
2. **Conversational and form-based yard sale creation** that actually persists to yardsailing's DB (Phase 1 success criteria 4a + 4b)
3. **At least one additional LLM provider** to validate the abstraction (Ollama is the natural choice for self-hosted use)

Stretch goals (defer to Phase 3 if Phase 2 is already heavy):
- Dynamic plugin downloads from a remote registry (currently filesystem-only)
- Plugin install/uninstall management UI
- Persistent agent settings (DB-backed instead of stub endpoint)

## Core architectural question: where does identity live?

### Option A — JAIN owns identity (recommended)

Google/Apple/Facebook OAuth → JAIN backend verifies the provider's ID token → JAIN issues its own JWT → all plugins trust JAIN's JWT and read claims like `email`, `sub`, `name`.

**Pros:**
- Single sign-on across all plugins (one login covers yardsailing, future tiffin-allegro, future small-talk, etc.)
- JAIN is the one identity provider — clean separation of concerns
- Plugins are stateless re: identity; they just verify a JAIN signature
- Adding new plugins doesn't require new OAuth flows

**Cons:**
- Requires modifying yardsailing to trust JAIN-issued JWTs (one new endpoint, well-scoped)
- JAIN takes on identity-storage responsibility (a `users` table with a unique constraint on `email`)

### Option B — Each plugin owns its own auth

Each plugin keeps its own user table and login flow. JAIN is just a UI shell that forwards plugin-specific session cookies/tokens.

**Pros:**
- Zero changes to yardsailing
- Plugins stay fully independent

**Cons:**
- User logs in N times for N plugins — bad UX
- JAIN can't reason about identity at all (can't say "as Jim, do X across two plugins")

**Recommendation: Option A.** Single sign-on is the better long-term bet, and the yardsailing change is small (one new endpoint, ~50 lines).

## Auth providers — which to support

### Required

- **Google** — most universal, easiest to set up
- **Apple Sign In** — *required by App Store guideline 4.8* if any other social login is offered on iOS. Not optional.

### Optional

- **Facebook** — broad reach but Meta requires more app-review work; defer if it slows Phase 2
- **Email magic link** — yardsailing already has this; reusing it inside JAIN would let users log in with their existing yardsailing identity. Could be a nice fallback for users who don't want to use OAuth.

**Recommendation:** Ship Google + Apple in Phase 2. Facebook and email-magic-link as optional follow-ons.

## How yardsailing learns about the new identity

When the user signs in with Google as `jim@gmail.com`, yardsailing should:

- **Map to existing yardsailing account by email** (most common case — user already has sales they created via the yardsailing web app)
- **Create a fresh yardsailing user** if no email match exists

The simplest mechanism:

1. JAIN issues a JWT with claims `{ sub: jain_user_id, email, name, providers: [google] }` signed with a key shared between JAIN and yardsailing
2. Yardsailing adds one new endpoint: `POST /api/auth/from-jain` accepts the JWT, validates the signature + expiration, looks up a user by email, creates one if missing, returns a yardsailing session token (or just trusts the JAIN JWT directly via a new dependency)
3. Yardsailing's existing `get_current_user` dependency gets a sibling `get_current_user_or_jain` that accepts either a yardsailing session OR a valid JAIN JWT

This is the **only yardsailing change**. It's well-scoped and reversible.

## Tool executor auth pass-through

The Phase 1 tool executor sends every request anonymously. Phase 2 must:

1. Accept an `auth_token` field on the chat request (the user's JAIN JWT)
2. When invoking a tool whose owning plugin declares `api.auth_required: true`, forward the JWT as `Authorization: Bearer <jwt>`
3. Plugins that don't require auth still get the anonymous flow

The plugin manifest schema may need a per-tool auth flag (some tools in a plugin are public, others require auth). Currently `auth_required` is per-plugin only.

## Mobile login UX

### LoginScreen / LoginModal

Three buttons (Google, Apple, Facebook), each launching `expo-auth-session` with the appropriate OAuth flow. On success:

1. Send the provider's ID token to JAIN backend (`POST /api/auth/google` etc.)
2. Receive a JAIN JWT
3. Store in `expo-secure-store`
4. Update zustand auth state
5. Dismiss the modal

### Triggering login

Two paths to the LoginScreen:

1. **Settings tab** — explicit "Sign in" button shown when not authenticated, "Sign out" when authenticated
2. **From Jain conversationally** — when Jain refuses an auth-required tool (Layer 1 behavior), the response could include a `display_hint: "auth_required"` that triggers the LoginModal directly from the chat screen. One-tap sign-in mid-conversation.

Option 2 is the magic UX moment — the user says "create a yard sale," Jain responds "Tap here to sign in," they tap, do the OAuth flow, and Jain immediately picks up where they left off. This is what makes JAIN feel like a real assistant.

## Ollama provider

Adding Ollama to validate the LLM provider abstraction:

```python
# app/engine/ollama_provider.py
class OllamaProvider(LLMProvider):
    async def complete(self, system, messages, tools) -> LLMResponse:
        # POST to http://localhost:11434/api/chat
        # Translate ChatMessage list to Ollama's message format
        # Translate ToolDef list to Ollama's tools format
        # Parse tool_use blocks from response
```

Ollama supports tool use in newer models (Llama 3.1+). The translation is similar to Anthropic but with different field names.

Add `OllamaProvider` to `dependencies._make_provider()` and set `LLM_PROVIDER=ollama` to switch. Zero changes to `chat_service.py`, `tool_executor.py`, or any other file. **If those files do need to change, the Phase 1 abstraction failed and we should fix it as part of Phase 2.**

## Open questions for the brainstorming session

1. **Token storage on mobile** — `expo-secure-store` is the obvious choice but has size limits. JWTs are typically fine. Confirm before committing.
2. **JWT expiration + refresh** — short-lived access token + long-lived refresh token (standard), or long-lived access token only (simpler)? Phase 2 probably wants standard.
3. **Yardsailing session vs. JAIN-JWT-passthrough** — does yardsailing return its own session token after `/api/auth/from-jain`, or do all subsequent yardsailing calls just send the JAIN JWT directly? The latter is simpler but couples yardsailing more tightly.
4. **Apple Sign In on Android** — is this needed? Apple Sign In is iOS-required when offering social login on iOS, but on Android there's no equivalent requirement. Consider whether to ship Apple on Android too for parity, or hide it.
5. **Account linking** — what happens if a user signs in with Google as `jim@gmail.com` and then later tries to sign in with Apple as `jim@gmail.com`? Should those be the same JAIN user (matched by email) or two separate users? Industry standard is "match by verified email."
6. **"Sign out" semantics** — does signing out of JAIN sign the user out of yardsailing too? Probably not — they might have a separate yardsailing browser session running.
7. **Per-tool auth requirement** — should the manifest support per-tool `auth_required` instead of per-plugin? `find_yard_sales` is public; `create_yard_sale` requires auth — same plugin.

## Suggested decomposition (rough — finalize during brainstorming)

This is too big for a single implementation plan. Suggested split into 3 sub-projects:

### Sub-project A: JAIN identity + Google OAuth
- JAIN `users` table + Pydantic schemas
- `/api/auth/google` endpoint (verify Google ID token, issue JAIN JWT)
- `/api/auth/me` endpoint (return current user)
- JWT signing key + verification utility
- Mobile: LoginScreen with Google button only, expo-auth-session integration, secure storage
- Mobile: zustand auth state hooked up
- **Deliverable:** User can sign in with Google and see their identity in Settings

### Sub-project B: Plugin auth pass-through + yardsailing bridge
- Tool executor accepts and forwards auth tokens
- Plugin manifest extension: per-tool auth flag
- Yardsailing repo: new `POST /api/auth/from-jain` endpoint + sibling `get_current_user_or_jain` dependency
- Update yardsailing `create-sale` skill to remove the "not logged in" branch and let real creates flow through
- **Deliverable:** Logged-in user can create a real yard sale via Jain (criterion 4a)

### Sub-project C: Apple Sign In + LoginModal-from-chat
- `/api/auth/apple` endpoint
- Mobile: Apple Sign In button via `expo-apple-authentication`
- Mobile: `display_hint: "auth_required"` in chat triggers LoginModal directly
- **Deliverable:** App Store compliant; magic mid-conversation login UX

### Sub-project D (optional): Ollama provider
- `app/engine/ollama_provider.py` with tool-use translation
- Wire into `dependencies._make_provider()`
- Validate the Phase 1 abstraction holds (no changes to chat_service / tool_executor / context_builder)
- **Deliverable:** JAIN runs against a self-hosted Ollama instance

Each sub-project is a brainstorming → spec → plan → execution cycle, like Phase 1.

## Minimum viable Phase 2

If you want the smallest possible Phase 2 that delivers the create flow, you can ship **just A + B**. That's Google login, JAIN identity, yardsailing bridge, real create. Apple Sign In is required to ship to App Store but not required for TestFlight beta or web preview, so it can be a fast follow.
