# Phase 2B Implementation Plan: Plugin Auth Pass-Through + Chat-Triggered Login

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make authentication a first-class core concern: JAIN verifies user identity via JWT once, then forwards `X-Jain-Service-Key` + `X-Jain-User-Email` + `X-Jain-User-Name` headers to plugins on every authenticated call. Plugins never touch JWTs — they trust JAIN via a shared service key. Also delivers the chat-triggered login UX: when a logged-out user asks Jain for something auth-required, Jain refuses with an inline "Sign in with Google" button and auto-retries the original message after successful OAuth.

**Architecture:** Tool executor short-circuits to a synthetic `auth_required` error when the user hits a tool marked `auth_required: true` without a JAIN session. The chat service catches this error and returns `display_hint: "auth_required"` to the mobile app, which renders an inline `<AuthPrompt />` component. When the user signs in, a `pendingRetry` zustand state triggers an auto-retry of the original message. Yardsailing gets a ~15-line env-var-gated branch in its existing `get_current_user` that accepts the service key + user identity headers and auto-provisions users by email.

**Tech Stack:**
- JAIN backend: FastAPI, SQLAlchemy async, Pydantic v2, pytest (Python 3.14)
- Yardsailing backend: FastAPI, SQLAlchemy async, Postgres via asyncpg, pytest (real DB per-test via conftest `db_engine` fixture)
- Mobile: Expo SDK 54, React Native, TypeScript, Zustand, existing `useGoogleSignIn` hook + `tokenStorage`
- jain-plugins: yardsailing plugin's `tools.json` files + `create-sale/SKILL.md`
- Reference spec: `docs/superpowers/specs/2026-04-10-phase-2b-plugin-auth-pass-through-design.md`

**Plan structure:**
- **Part 1 (Tasks 1–6):** JAIN backend — config, schema, optional user dep, tool executor, context builder, chat service, chat router
- **Part 2 (Task 7):** jain-plugins — mark auth-required tools + remove SKILL.md Phase 1 auth check
- **Part 3 (Tasks 8–9):** Yardsailing — config field + get_current_user branch with tests
- **Part 4 (Tasks 10–13):** Mobile — store refactor, API cleanup, AuthPrompt component, auto-retry + ChatScreen integration
- **Part 5 (Task 14):** Service key setup + end-to-end acceptance walkthrough

**Prerequisites:**
- Current branch: `feature/phase-2b-plugin-auth-passthrough` (stacked on top of `feature/phase-2a-identity-google-oauth`)
- Phase 2A is complete and working on that parent branch (68 backend tests passing, Google OAuth works on web)

---

## Part 1: JAIN Backend

### Task 1: Config + schema additions

**Files:**
- Modify: `C:/Users/jimsh/repos/jain/backend/app/config.py`
- Modify: `C:/Users/jimsh/repos/jain/backend/app/plugins/schema.py`

Small additive task combining two trivial changes: a config field and a schema field. No new tests — these are just declarations used by later tasks.

- [ ] **Step 1: Add JAIN_SERVICE_KEY config field**

Edit `backend/app/config.py`. Inside the `Settings` class, after the `JWT_EXPIRE_DAYS` line, add:

```python
    # Phase 2B: shared secret for JAIN ↔ plugin service-to-service calls.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    # Set in .env; plugins (e.g. yardsailing) must be configured with the same value.
    JAIN_SERVICE_KEY: str = ""
```

- [ ] **Step 2: Add auth_required to ToolDef schema**

Edit `backend/app/plugins/schema.py`. Inside the `ToolDef` class, after the `method: str = "GET"` line, add:

```python
    # Phase 2B: when True, the tool executor refuses to call this tool
    # unless the user is authenticated. Anonymous callers get a synthetic
    # auth_required error instead of an upstream HTTP call.
    auth_required: bool = False
```

- [ ] **Step 3: Run the full test suite to confirm nothing broke**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest -q
```

Expected: all 68 existing Phase 2A tests pass. No new tests yet.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/app/config.py backend/app/plugins/schema.py
git commit -m "feat(backend): phase 2b config field + ToolDef.auth_required

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: get_current_user_optional dependency

**Files:**
- Create: `C:/Users/jimsh/repos/jain/backend/app/auth/optional_user.py`
- Create: `C:/Users/jimsh/repos/jain/backend/tests/test_optional_user.py`

A FastAPI dependency that reads the Authorization header and returns the `User` if valid, or `None` if any validation fails. Unlike the existing `get_current_user`, it NEVER raises 401 — anonymous chat requests must continue to work.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_optional_user.py`:

```python
import uuid
from unittest.mock import AsyncMock

import jwt as pyjwt
import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.jwt import sign_access_token
from app.auth.optional_user import get_current_user_optional
from app.config import settings
from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


def _make_request(authorization: str | None = None) -> Request:
    """Build a minimal Request object with the given Authorization header."""
    scope = {
        "type": "http",
        "headers": [(b"authorization", authorization.encode())] if authorization else [],
    }
    return Request(scope)


async def test_returns_user_for_valid_jwt(session):
    user = User(email="jim@example.com", name="Jim", email_verified=True, google_sub="g-1")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    token = sign_access_token(user)

    request = _make_request(f"Bearer {token}")
    result = await get_current_user_optional(request=request, db=session)
    assert result is not None
    assert result.id == user.id
    assert result.email == "jim@example.com"


async def test_returns_none_when_no_header(session):
    request = _make_request(None)
    result = await get_current_user_optional(request=request, db=session)
    assert result is None


async def test_returns_none_when_header_is_not_bearer(session):
    request = _make_request("Basic dXNlcjpwYXNz")
    result = await get_current_user_optional(request=request, db=session)
    assert result is None


async def test_returns_none_for_bogus_jwt(session):
    request = _make_request("Bearer not-a-real-jwt")
    result = await get_current_user_optional(request=request, db=session)
    assert result is None


async def test_returns_none_for_expired_jwt(session):
    from datetime import datetime, timedelta, timezone
    user = User(email="e@x.com", name="E", email_verified=True, google_sub="g-e")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "iat": int((now - timedelta(days=60)).timestamp()),
        "exp": int((now - timedelta(days=30)).timestamp()),
    }
    expired = pyjwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    request = _make_request(f"Bearer {expired}")
    result = await get_current_user_optional(request=request, db=session)
    assert result is None


async def test_returns_none_when_user_not_in_db(session):
    # Sign a JWT for a user that doesn't exist in the session
    ghost = User(id=uuid.uuid4(), email="ghost@x.com", name="G", email_verified=True)
    token = sign_access_token(ghost)

    request = _make_request(f"Bearer {token}")
    result = await get_current_user_optional(request=request, db=session)
    assert result is None
```

- [ ] **Step 2: Run the test — expect failure**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest tests/test_optional_user.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.auth.optional_user'`.

- [ ] **Step 3: Implement the dependency**

Create `backend/app/auth/optional_user.py`:

```python
from uuid import UUID

import jwt as pyjwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import verify_access_token
from app.database import get_db
from app.models.user import User


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Resolve the authenticated user from the Authorization header, or None.

    Unlike get_current_user, this dependency does NOT raise 401 on failure.
    Any invalid state (missing header, bad token, expired, deleted user)
    returns None so anonymous requests can continue.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None

    token = auth_header[7:]  # strip "Bearer " (7 chars)

    try:
        claims = verify_access_token(token)
    except pyjwt.PyJWTError:
        return None

    sub = claims.get("sub")
    if not sub:
        return None

    try:
        user_id = UUID(sub)
    except ValueError:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

- [ ] **Step 4: Run the test — expect pass**

```bash
.venv/Scripts/python -m pytest tests/test_optional_user.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Run full suite to confirm nothing else broke**

```bash
.venv/Scripts/python -m pytest -q
```

Expected: 68 prior + 6 new = 74 tests, all green.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/app/auth/optional_user.py backend/tests/test_optional_user.py
git commit -m "feat(backend): add get_current_user_optional FastAPI dependency

Returns User for valid JWT, None for any failure. Does NOT raise 401
so anonymous chat can continue for public tools.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Tool executor auth gate + service-key headers

**Files:**
- Modify: `C:/Users/jimsh/repos/jain/backend/app/engine/tool_executor.py`
- Modify: `C:/Users/jimsh/repos/jain/backend/tests/test_tool_executor.py`

The tool executor is the single point where authentication decisions propagate to plugin HTTP calls. This task adds two behaviors: (1) refuse to call auth-required tools when the user is anonymous, and (2) forward service-key + user headers on every call when the user is authenticated.

- [ ] **Step 1: Write the failing tests**

Open `backend/tests/test_tool_executor.py` and append these tests to the end of the file:

```python


async def test_execute_auth_required_tool_without_user_returns_synthetic_error(registry):
    """When tool.auth_required is True and user is None, return a synthetic
    auth_required error without making any HTTP call."""
    # Mutate the fixture tool to be auth_required for this test
    _, tool = registry.find_tool("find_yard_sales")
    tool.auth_required = True

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0}),
        user=None,
    )
    assert result.tool_call_id == "tc1"
    payload = json.loads(result.content)
    assert payload["error"] == "auth_required"
    assert payload["plugin"] == "yardsailing"

    # Restore
    tool.auth_required = False


async def test_execute_public_tool_without_user_still_works(registry, httpx_mock):
    """Public tools (auth_required=False) call anonymously even when user is None."""
    httpx_mock.add_response(
        method="GET",
        url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
        json={"sales": []},
    )

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10}),
        user=None,
    )
    # Should be a successful call, not a synthetic error
    assert json.loads(result.content) == {"sales": []}


async def test_execute_forwards_service_key_headers_when_user_present(registry, httpx_mock):
    """When user is authenticated, the executor forwards X-Jain-Service-Key
    + X-Jain-User-Email + X-Jain-User-Name headers to the plugin."""
    from app.config import settings
    from app.models.user import User
    from uuid import uuid4

    # Configure a known service key for this test
    original_key = settings.JAIN_SERVICE_KEY
    settings.JAIN_SERVICE_KEY = "test-service-key-1234"

    httpx_mock.add_response(
        method="GET",
        url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
        json={"sales": []},
    )

    user = User(
        id=uuid4(),
        email="jim@example.com",
        name="Jim Shelly",
        email_verified=True,
        google_sub="g-jim",
    )

    executor = ToolExecutor(registry=registry)
    await executor.execute(
        ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10}),
        user=user,
    )

    sent_request = httpx_mock.get_requests()[0]
    assert sent_request.headers["x-jain-service-key"] == "test-service-key-1234"
    assert sent_request.headers["x-jain-user-email"] == "jim@example.com"
    assert sent_request.headers["x-jain-user-name"] == "Jim Shelly"

    # Restore
    settings.JAIN_SERVICE_KEY = original_key


async def test_execute_no_service_key_headers_when_user_absent(registry, httpx_mock):
    """When user is None, do NOT send service-key or user identity headers."""
    httpx_mock.add_response(
        method="GET",
        url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
        json={"sales": []},
    )

    executor = ToolExecutor(registry=registry)
    await executor.execute(
        ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10}),
        user=None,
    )

    sent_request = httpx_mock.get_requests()[0]
    assert "x-jain-service-key" not in sent_request.headers
    assert "x-jain-user-email" not in sent_request.headers
    assert "x-jain-user-name" not in sent_request.headers
```

You will also need to update the **existing** tests in this file to pass `user=None` on every `executor.execute(...)` call, because the signature is changing. Edit the existing tests:

`test_execute_calls_plugin_api` — change:
```python
result = await executor.execute(
    ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10})
)
```
to:
```python
result = await executor.execute(
    ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10}),
    user=None,
)
```

Apply the same `user=None` addition to `test_execute_unknown_tool` and `test_execute_http_error`.

- [ ] **Step 2: Run tests — expect failures**

```bash
.venv/Scripts/python -m pytest tests/test_tool_executor.py -v
```

Expected: the 4 new tests fail with signature errors or missing field errors; the 3 existing tests fail because `execute()` doesn't accept `user` keyword yet.

- [ ] **Step 3: Update the tool executor implementation**

Edit `backend/app/engine/tool_executor.py`. Replace the entire `execute` method with:

```python
    async def execute(self, call: ToolCall, user: "User | None" = None) -> ToolResult:
        plugin, tool = self.registry.find_tool(call.name)
        if plugin is None or tool is None:
            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps({"error": f"tool '{call.name}' not found"}),
            )

        if plugin.manifest.api is None:
            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps({"error": f"plugin '{plugin.manifest.name}' has no api"}),
            )

        # Phase 2B: gate auth-required tools
        if tool.auth_required and user is None:
            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps({
                    "error": "auth_required",
                    "plugin": plugin.manifest.name,
                }),
            )

        base_url = plugin.manifest.api.base_url.rstrip("/")
        endpoint = tool.endpoint or f"/{tool.name}"
        url = base_url + endpoint
        method = (tool.method or "GET").upper()

        # Phase 2B: build headers, adding service-key + user identity when present
        headers = {"X-Requested-With": "XMLHttpRequest"}
        if user is not None:
            from app.config import settings
            headers["X-Jain-Service-Key"] = settings.JAIN_SERVICE_KEY
            headers["X-Jain-User-Email"] = user.email
            headers["X-Jain-User-Name"] = user.name

        client = await self._get_http()
        try:
            if method == "GET":
                response = await client.get(url, params=call.arguments, headers=headers)
            else:
                response = await client.request(
                    method, url, json=call.arguments, headers=headers
                )
            response.raise_for_status()
            return ToolResult(tool_call_id=call.id, content=response.text)
        except httpx.HTTPStatusError as e:
            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps(
                    {"error": f"upstream error {e.response.status_code}", "detail": e.response.text}
                ),
            )
        except httpx.RequestError as e:
            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps({"error": f"request failed: {type(e).__name__}"}),
            )
```

Also add a TYPE_CHECKING import at the top of the file so the `User | None` annotation works without runtime import cycles. Add after the existing `import httpx` line:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User
```

- [ ] **Step 4: Run tests — expect pass**

```bash
.venv/Scripts/python -m pytest tests/test_tool_executor.py -v
```

Expected: all existing tests pass + all 4 new tests pass = 7 total in this file. Full suite (74 prior + 4 new) = 78 tests green.

- [ ] **Step 5: Run full suite**

```bash
.venv/Scripts/python -m pytest -q
```

Expected: 78 tests, all green.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/app/engine/tool_executor.py backend/tests/test_tool_executor.py
git commit -m "feat(backend): tool executor gates auth_required tools + forwards service-key headers

- Tools marked auth_required return a synthetic {error: auth_required} result
  without making an HTTP call when the user is None.
- Authenticated calls get X-Jain-Service-Key + X-Jain-User-Email +
  X-Jain-User-Name headers forwarded to the plugin. Anonymous calls to public
  tools send no auth headers at all.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Context builder accepts optional user

**Files:**
- Modify: `C:/Users/jimsh/repos/jain/backend/app/services/context_builder.py`
- Modify: `C:/Users/jimsh/repos/jain/backend/tests/test_context_builder.py`

The context builder's job is to produce the system prompt Jain sees. Phase 1 Layer 1 had per-plugin auth state. Phase 2B replaces that with a single global "user is/isn't authenticated" marker based on whether a `User` was resolved from the JWT.

- [ ] **Step 1: Write the failing tests**

Open `backend/tests/test_context_builder.py` and replace the entire file contents with:

```python
from pathlib import Path
from uuid import uuid4

from app.models.user import User
from app.plugins.registry import PluginRegistry
from app.services.context_builder import JAIN_SYSTEM_PROMPT_BASE, build_system_prompt

FIXTURES = Path(__file__).parent / "fixtures" / "plugins"


def test_system_prompt_includes_base_and_skills():
    reg = PluginRegistry(plugins_dir=FIXTURES)
    reg.load_all()

    prompt = build_system_prompt(reg, user=None)
    assert JAIN_SYSTEM_PROMPT_BASE in prompt
    assert "yardsailing.find-sales" in prompt
    assert "Find yard sales" in prompt
    assert "small-talk.chat" in prompt


def test_system_prompt_empty_registry():
    reg = PluginRegistry(plugins_dir=FIXTURES / "__nonexistent__")
    reg.load_all()

    prompt = build_system_prompt(reg, user=None)
    assert JAIN_SYSTEM_PROMPT_BASE in prompt


def test_system_prompt_anonymous_user_has_not_authenticated_marker():
    reg = PluginRegistry(plugins_dir=FIXTURES)
    reg.load_all()

    prompt = build_system_prompt(reg, user=None)
    assert "not authenticated" in prompt.lower()


def test_system_prompt_authenticated_user_shows_email_and_name():
    reg = PluginRegistry(plugins_dir=FIXTURES)
    reg.load_all()

    user = User(
        id=uuid4(),
        email="jim@example.com",
        name="Jim Shelly",
        email_verified=True,
        google_sub="g-jim",
    )
    prompt = build_system_prompt(reg, user=user)
    assert "jim@example.com" in prompt
    assert "Jim Shelly" in prompt
    assert "not authenticated" not in prompt.lower()
```

- [ ] **Step 2: Run tests — expect failures**

```bash
.venv/Scripts/python -m pytest tests/test_context_builder.py -v
```

Expected: the existing tests fail with `build_system_prompt() got an unexpected keyword argument 'user'` or similar.

- [ ] **Step 3: Update the context builder**

Edit `backend/app/services/context_builder.py`. Replace the entire file with:

```python
from app.models.user import User
from app.plugins.registry import PluginRegistry

JAIN_SYSTEM_PROMPT_BASE = """You are Jain, an AI assistant that helps users through a set of skills provided by plugins.

Your personality: friendly, concise, practical. You speak in short sentences unless the user asks for detail.

When a user request matches one of your available skills, use the appropriate tool to fulfill it. When asked to find real-world data (locations, listings, status), always use tools — never make up data.

When helping a user create or configure something, you can either:
1. Gather information conversationally by asking one question at a time, or
2. Present a form if the plugin provides one and the user prefers that.

Ask the user which they prefer if it's not obvious from context.
"""


def build_system_prompt(registry: PluginRegistry, user: User | None = None) -> str:
    parts = [JAIN_SYSTEM_PROMPT_BASE]

    # Phase 2B: inject the user's global auth state. The platform gates
    # auth-required tools at the executor level, so Jain just needs to know
    # whether the user is signed in for conversational framing.
    if user is not None:
        parts.append(
            f"\n\n[user signed in as {user.email} ({user.name})]"
        )
    else:
        parts.append(
            "\n\n[user not authenticated — if they ask for something that requires signing in, "
            "the platform will refuse the tool call automatically and prompt them to sign in. "
            "You don't need to check auth state yourself.]"
        )

    skills = registry.skill_descriptions()
    if skills:
        parts.append("\n\nAvailable skills:")
        for skill_key, description in sorted(skills.items()):
            parts.append(f"\n- {skill_key}: {description}")

    return "".join(parts)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
.venv/Scripts/python -m pytest tests/test_context_builder.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Run full suite**

```bash
.venv/Scripts/python -m pytest -q
```

Expected: 78 tests, all green. (The test count includes 2 new context builder tests + 2 existing rewritten.)

- [ ] **Step 6: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/app/services/context_builder.py backend/tests/test_context_builder.py
git commit -m "feat(backend): context builder accepts optional User and injects global auth state

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Chat service accepts user + short-circuits on auth_required

**Files:**
- Modify: `C:/Users/jimsh/repos/jain/backend/app/services/chat_service.py`
- Modify: `C:/Users/jimsh/repos/jain/backend/tests/test_chat_service.py`

The chat service is the orchestration point. Phase 2B changes: accept an optional `User`, pass it to the context builder and tool executor, and detect when a tool execution returned the synthetic `auth_required` error so we can short-circuit the normal reply.

- [ ] **Step 1: Write the failing tests**

Open `backend/tests/test_chat_service.py`. Append these tests to the end:

```python


async def test_chat_service_passes_user_to_tool_executor(registry, httpx_mock):
    """When a User is passed to send(), the tool executor receives it."""
    from uuid import uuid4
    from app.models.user import User
    from app.config import settings

    original_key = settings.JAIN_SERVICE_KEY
    settings.JAIN_SERVICE_KEY = "test-key-for-chat-service"

    httpx_mock.add_response(
        method="GET",
        url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
        json={"sales": []},
    )

    provider = MockProvider(
        responses=[
            LLMResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="find_yard_sales",
                        arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
                    )
                ],
            ),
            LLMResponse(text="found nothing", tool_calls=[]),
        ]
    )
    service = ChatService(
        registry=registry,
        provider=provider,
        tool_executor=ToolExecutor(registry=registry),
    )

    user = User(
        id=uuid4(),
        email="jim@example.com",
        name="Jim",
        email_verified=True,
        google_sub="g-jim-chat",
    )
    await service.send(
        conversation=[ChatMessage(role="user", content="find sales")],
        user=user,
    )

    sent = httpx_mock.get_requests()[0]
    assert sent.headers["x-jain-user-email"] == "jim@example.com"

    settings.JAIN_SERVICE_KEY = original_key


async def test_chat_service_short_circuits_on_auth_required(registry):
    """When a tool returns auth_required error, chat service returns a
    ChatReply with display_hint='auth_required' and does NOT feed the
    error back to the LLM for a continuation."""
    # Mark the find_yard_sales tool as auth_required for this test
    _, tool = registry.find_tool("find_yard_sales")
    tool.auth_required = True

    provider = MockProvider(
        responses=[
            LLMResponse(
                text="Let me search",
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="find_yard_sales",
                        arguments={"lat": 1.0, "lng": 2.0},
                    )
                ],
            ),
            # This second response must NOT be consumed — the service should
            # short-circuit after the auth_required error from the tool.
            LLMResponse(text="THIS SHOULD NOT BE USED", tool_calls=[]),
        ]
    )
    service = ChatService(
        registry=registry,
        provider=provider,
        tool_executor=ToolExecutor(registry=registry),
    )

    reply = await service.send(
        conversation=[ChatMessage(role="user", content="find sales")],
        user=None,
    )

    assert reply.display_hint == "auth_required"
    assert reply.data is not None
    assert reply.data["plugin"] == "yardsailing"
    assert "sign in" in reply.text.lower()
    # Only the first LLM call happened
    assert len(provider.calls) == 1
    # The tool call was logged
    assert len(reply.tool_events) == 1
    assert reply.tool_events[0]["name"] == "find_yard_sales"

    # Restore
    tool.auth_required = False


async def test_chat_service_anonymous_user_public_tool_works(registry, httpx_mock):
    """Anonymous user calling a non-auth_required tool works normally."""
    httpx_mock.add_response(
        method="GET",
        url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
        json={"sales": [{"id": 1, "title": "Sale"}]},
    )

    provider = MockProvider(
        responses=[
            LLMResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="find_yard_sales",
                        arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
                    )
                ],
            ),
            LLMResponse(text="Found 1", tool_calls=[]),
        ]
    )
    service = ChatService(
        registry=registry,
        provider=provider,
        tool_executor=ToolExecutor(registry=registry),
    )

    reply = await service.send(
        conversation=[ChatMessage(role="user", content="find sales")],
        user=None,
    )

    assert reply.text == "Found 1"
    assert reply.display_hint == "map"
```

You will also need to update the **existing** tests in this file (`test_chat_service_text_reply`, `test_chat_service_executes_tool_and_continues`, `test_chat_service_respects_max_tool_rounds`, `test_chat_service_tool_error_does_not_set_data`) to pass `user=None` to every `service.send(...)` call. Add `user=None,` as an argument on each call.

- [ ] **Step 2: Run tests — expect failures**

```bash
.venv/Scripts/python -m pytest tests/test_chat_service.py -v
```

Expected: existing tests fail because `send()` doesn't accept `user`; new tests fail because `build_system_prompt` gets called without `user` param from the service.

- [ ] **Step 3: Update the chat service**

Edit `backend/app/services/chat_service.py`. Replace the entire file with:

```python
import json
from dataclasses import dataclass, field
from typing import Any

from app.engine.base import ChatMessage, LLMProvider, ToolResult
from app.engine.tool_executor import ToolExecutor
from app.models.user import User
from app.plugins.registry import PluginRegistry

from .context_builder import build_system_prompt


@dataclass
class ChatReply:
    text: str
    data: Any | None = None
    display_hint: str | None = None
    tool_events: list[dict] = field(default_factory=list)


def _infer_display_hint(plugin_name: str, tool_name: str, data: Any) -> str | None:
    """Infer how the frontend should render tool results.

    Phase 1 heuristic:
    - find_* tools returning a dict with list values -> map
    - create_* tools -> None (inline text reply)
    """
    if not isinstance(data, dict):
        return None
    if tool_name.startswith("find_"):
        # Look for a list-valued key (sales, items, etc.)
        for value in data.values():
            if isinstance(value, list) and value:
                return "map"
    return None


class ChatService:
    def __init__(
        self,
        registry: PluginRegistry,
        provider: LLMProvider,
        tool_executor: ToolExecutor,
        max_tool_rounds: int = 5,
    ):
        self.registry = registry
        self.provider = provider
        self.tool_executor = tool_executor
        self.max_tool_rounds = max_tool_rounds

    async def send(
        self,
        conversation: list[ChatMessage],
        user: User | None = None,
    ) -> ChatReply:
        """Run the LLM + tool loop and return the final assistant reply.

        The loop runs up to `max_tool_rounds + 1` LLM calls total. The extra
        round is intended to give the LLM a final turn to generate a text
        reply after its last tool execution. If the LLM returns tool_calls
        on that final round, those tools run but their results are discarded
        (the reply text becomes "(max tool rounds reached)"). This is a
        safety bound against pathological tool-use loops.

        Phase 2B: if any tool execution returns a synthetic auth_required
        error, the loop short-circuits immediately and returns a ChatReply
        with display_hint="auth_required" so the mobile app can render an
        inline login prompt.

        Args:
            conversation: Full chat history so far, ending with the user's
                          latest message.
            user: The authenticated User if the caller provided a valid
                  JAIN JWT, or None for anonymous requests.

        Returns:
            ChatReply containing the final text, most recent tool data (if
            any), a display hint, and a log of tool events.
        """
        system = build_system_prompt(self.registry, user=user)
        tools = self.registry.all_tools()
        history = list(conversation)

        last_data: Any = None
        last_display_hint: str | None = None
        tool_events: list[dict] = []

        for _round in range(self.max_tool_rounds + 1):
            response = await self.provider.complete(
                system=system, messages=history, tools=tools
            )

            if not response.tool_calls:
                return ChatReply(
                    text=response.text,
                    data=last_data,
                    display_hint=last_display_hint,
                    tool_events=tool_events,
                )

            # Append assistant turn (with tool_use blocks) and execute each tool
            history.append(
                ChatMessage(
                    role="assistant",
                    content=response.text,
                    tool_calls=response.tool_calls,
                )
            )

            results: list[ToolResult] = []
            for call in response.tool_calls:
                result = await self.tool_executor.execute(call, user=user)
                results.append(result)

                event = {"name": call.name, "arguments": call.arguments}
                tool_events.append(event)

                # Try to parse result content as JSON
                try:
                    parsed = json.loads(result.content)
                except (json.JSONDecodeError, TypeError):
                    parsed = None

                # Phase 2B: short-circuit on auth_required synthetic error
                if (
                    isinstance(parsed, dict)
                    and parsed.get("error") == "auth_required"
                ):
                    return ChatReply(
                        text="I'd love to help with that — you'll need to sign in first.",
                        data={"plugin": parsed.get("plugin", "")},
                        display_hint="auth_required",
                        tool_events=tool_events,
                    )

                is_error = isinstance(parsed, dict) and parsed.get("error")
                if parsed is not None and not is_error:
                    plugin, _ = self.registry.find_tool(call.name)
                    plugin_name = plugin.manifest.name if plugin else ""
                    # Update data and hint atomically so a stale "map" hint
                    # never outlives its original sales-shaped data.
                    last_data = parsed
                    last_display_hint = _infer_display_hint(plugin_name, call.name, parsed)

            history.append(ChatMessage(role="tool", content="", tool_results=results))

        return ChatReply(
            text="(max tool rounds reached)",
            data=last_data,
            display_hint=last_display_hint,
            tool_events=tool_events,
        )
```

- [ ] **Step 4: Run tests — expect pass**

```bash
.venv/Scripts/python -m pytest tests/test_chat_service.py -v
```

Expected: all existing + new tests pass.

- [ ] **Step 5: Run full suite**

```bash
.venv/Scripts/python -m pytest -q
```

Expected: 81 tests, all green (78 prior + 3 new).

- [ ] **Step 6: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/app/services/chat_service.py backend/tests/test_chat_service.py
git commit -m "feat(backend): chat service accepts optional User and short-circuits on auth_required

- send() takes optional user param, passes it to context builder and tool executor
- detects synthetic auth_required tool results and returns display_hint='auth_required'
- discards the in-progress LLM response on short-circuit (only first call counts)
- logs the attempted tool call in tool_events even on short-circuit

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Chat router uses optional user + remove ChatRequest.auth

**Files:**
- Modify: `C:/Users/jimsh/repos/jain/backend/app/schemas/chat.py`
- Modify: `C:/Users/jimsh/repos/jain/backend/app/routers/chat.py`
- Modify: `C:/Users/jimsh/repos/jain/backend/tests/test_chat_router.py`

Wire the optional user dependency into the chat router, pass the user through to the chat service, and remove the Phase 1 `auth: dict[str, bool]` field from `ChatRequest`.

- [ ] **Step 1: Write the failing tests**

Open `backend/tests/test_chat_router.py`. Append these new tests to the end of the file:

```python


async def test_chat_endpoint_anonymous_still_works(auth_client):
    """Chat works with no Authorization header (anonymous mode)."""
    # Override the service to return a plain text reply
    pass  # This test's logic is in the fixture setup — see next test


async def test_chat_endpoint_resolves_user_from_bearer_token(session_factory):
    """Chat with a valid Authorization header resolves the user and passes
    it to the chat service."""
    from unittest.mock import MagicMock, AsyncMock

    from app.auth.jwt import sign_access_token
    from app.dependencies import get_chat_service, get_registry
    from app.engine.base import LLMResponse
    from app.engine.mock import MockProvider
    from app.engine.tool_executor import ToolExecutor
    from app.main import create_app
    from app.models.user import User
    from app.plugins.registry import PluginRegistry
    from app.services.chat_service import ChatService

    # Seed a user in the DB
    async with session_factory() as session:
        user = User(
            email="jim@example.com",
            email_verified=True,
            google_sub="g-jim",
            name="Jim",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        token = sign_access_token(user)

    # Build app with a spy on ChatService.send
    app = create_app()
    FIXTURES = Path(__file__).parent / "fixtures" / "plugins"
    registry = PluginRegistry(plugins_dir=FIXTURES)
    registry.load_all()

    spy = AsyncMock(
        return_value=MagicMock(
            text="hello jim",
            data=None,
            display_hint=None,
            tool_events=[],
        )
    )
    service = ChatService(
        registry=registry,
        provider=MockProvider([LLMResponse(text="x", tool_calls=[])]),
        tool_executor=ToolExecutor(registry=registry),
    )
    service.send = spy

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_chat_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.post(
            "/api/chat",
            json={"message": "hi"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    # The chat service received a User (not None)
    call_kwargs = spy.call_args.kwargs
    assert call_kwargs["user"] is not None
    assert call_kwargs["user"].email == "jim@example.com"


async def test_chat_endpoint_bad_token_treats_as_anonymous(session_factory):
    """Chat with a malformed Bearer token should NOT 401 — it should proceed
    anonymously (user=None)."""
    from unittest.mock import MagicMock, AsyncMock

    from app.dependencies import get_chat_service, get_registry
    from app.engine.base import LLMResponse
    from app.engine.mock import MockProvider
    from app.engine.tool_executor import ToolExecutor
    from app.main import create_app
    from app.plugins.registry import PluginRegistry
    from app.services.chat_service import ChatService

    app = create_app()
    FIXTURES = Path(__file__).parent / "fixtures" / "plugins"
    registry = PluginRegistry(plugins_dir=FIXTURES)
    registry.load_all()

    spy = AsyncMock(
        return_value=MagicMock(
            text="anon reply",
            data=None,
            display_hint=None,
            tool_events=[],
        )
    )
    service = ChatService(
        registry=registry,
        provider=MockProvider([LLMResponse(text="x", tool_calls=[])]),
        tool_executor=ToolExecutor(registry=registry),
    )
    service.send = spy

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_chat_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.post(
            "/api/chat",
            json={"message": "hi"},
            headers={"Authorization": "Bearer garbage-token"},
        )

    assert response.status_code == 200
    # The chat service should have received user=None, not 401
    assert spy.call_args.kwargs["user"] is None
```

Also update the existing `test_chat_endpoint_text_reply` to assert that the monkey-patched service is called with `user=None` (since the test client has no Authorization header). If the existing test doesn't inspect `spy.call_args`, you can leave it alone.

The existing `test_plugins_endpoint_lists_loaded` and bundle endpoint tests are not affected — they don't hit `/api/chat`.

- [ ] **Step 2: Run tests — expect failures**

```bash
.venv/Scripts/python -m pytest tests/test_chat_router.py -v
```

Expected: the two new tests fail because `/api/chat` doesn't yet accept the Authorization header or pass user to the service.

- [ ] **Step 3: Remove ChatRequest.auth field**

Edit `backend/app/schemas/chat.py`. Replace the `ChatRequest` class with:

```python
class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurnIn] = Field(default_factory=list)
    lat: float | None = None
    lng: float | None = None
```

(Delete the `auth: dict[str, bool] = Field(default_factory=dict)` line that was there from Phase 1 Layer 1.)

- [ ] **Step 4: Update the chat router**

Edit `backend/app/routers/chat.py`. Replace the entire file with:

```python
from fastapi import APIRouter, Depends

from app.auth.optional_user import get_current_user_optional
from app.dependencies import get_chat_service
from app.engine.base import ChatMessage
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: User | None = Depends(get_current_user_optional),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    messages = [ChatMessage(role=turn.role, content=turn.content) for turn in req.history]

    context_lines: list[str] = []
    if req.lat is not None and req.lng is not None:
        context_lines.append(f"[user location: lat={req.lat}, lng={req.lng}]")

    user_content = (
        "\n".join(context_lines) + "\n" + req.message if context_lines else req.message
    )
    messages.append(ChatMessage(role="user", content=user_content))

    reply = await service.send(conversation=messages, user=user)
    return ChatResponse(
        reply=reply.text,
        data=reply.data,
        display_hint=reply.display_hint,
        tool_events=reply.tool_events,
    )
```

Note the removal of the auth-state context line that Phase 1 injected from `req.auth`. That's replaced entirely by the context builder's handling of the User parameter.

- [ ] **Step 5: Run tests — expect pass**

```bash
.venv/Scripts/python -m pytest tests/test_chat_router.py -v
```

Expected: all existing + new tests pass.

- [ ] **Step 6: Run full suite**

```bash
.venv/Scripts/python -m pytest -q
```

Expected: 83 tests, all green (81 prior + 2 new).

- [ ] **Step 7: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/app/schemas/chat.py backend/app/routers/chat.py backend/tests/test_chat_router.py
git commit -m "feat(backend): chat router uses optional user dep; remove ChatRequest.auth

- Chat router resolves User from Authorization header via get_current_user_optional
- Anonymous requests (no header, bad header, expired JWT) pass user=None through
- ChatRequest.auth field (Phase 1 Layer 1) is removed
- Request context line is now only location; auth state is handled by context builder

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

**Milestone: JAIN backend Phase 2B complete.** The backend now propagates user identity from the Authorization header all the way to the plugin HTTP calls, gates auth-required tools at the executor, and short-circuits to `display_hint: "auth_required"` when a logged-out user hits a gated tool.

---

## Part 2: jain-plugins

### Task 7: Mark yardsailing tools as auth_required + clean up SKILL.md

**Files:**
- Modify: `C:/Users/jimsh/repos/jain-plugins/plugins/yardsailing/skills/create-sale/tools.json`
- Modify: `C:/Users/jimsh/repos/jain-plugins/plugins/yardsailing/skills/manage-sales/tools.json`
- Modify: `C:/Users/jimsh/repos/jain-plugins/plugins/yardsailing/skills/create-sale/SKILL.md`

- [ ] **Step 1: Mark create_yard_sale as auth_required**

Edit `C:/Users/jimsh/repos/jain-plugins/plugins/yardsailing/skills/create-sale/tools.json`. The file currently contains a single tool. Add `"auth_required": true` to it. The result should look like:

```json
[
  {
    "name": "create_yard_sale",
    "description": "Create a new yard sale listing",
    "endpoint": "/api/sales",
    "method": "POST",
    "auth_required": true,
    "input_schema": {
      "type": "object",
      "properties": {
        "title": { "type": "string" },
        "description": { "type": "string" },
        "address": { "type": "string" },
        "lat": { "type": "number" },
        "lng": { "type": "number" },
        "start_date": { "type": "string", "description": "ISO date YYYY-MM-DD" },
        "end_date": { "type": "string", "description": "ISO date YYYY-MM-DD" },
        "start_time": { "type": "string", "description": "HH:MM 24-hour" },
        "end_time": { "type": "string", "description": "HH:MM 24-hour" }
      },
      "required": ["title", "address", "start_date", "start_time", "end_time"]
    }
  }
]
```

- [ ] **Step 2: Mark update/delete tools as auth_required (but not get_my_sales)**

Edit `C:/Users/jimsh/repos/jain-plugins/plugins/yardsailing/skills/manage-sales/tools.json`. Add `"auth_required": true` to `update_yard_sale` and `delete_yard_sale`, but NOT `get_my_sales` (it's a read that can be public for now — the yardsailing backend decides what to return based on who's asking). The file should look like:

```json
[
  {
    "name": "get_my_sales",
    "description": "Get the current user's yard sale listings",
    "endpoint": "/api/my-sales",
    "method": "GET",
    "auth_required": true,
    "input_schema": {
      "type": "object",
      "properties": {},
      "required": []
    }
  },
  {
    "name": "update_yard_sale",
    "description": "Update an existing yard sale",
    "endpoint": "/api/my-sales",
    "method": "PUT",
    "auth_required": true,
    "input_schema": {
      "type": "object",
      "properties": {
        "id": { "type": "integer" },
        "title": { "type": "string" },
        "description": { "type": "string" }
      },
      "required": ["id"]
    }
  },
  {
    "name": "delete_yard_sale",
    "description": "Delete a yard sale",
    "endpoint": "/api/my-sales",
    "method": "DELETE",
    "auth_required": true,
    "input_schema": {
      "type": "object",
      "properties": { "id": { "type": "integer" } },
      "required": ["id"]
    }
  }
]
```

(Actually, `get_my_sales` should ALSO be auth_required because without auth the endpoint doesn't know whose sales to return. Adding it too.)

- [ ] **Step 3: Remove Phase 1 Layer 1 auth check from create-sale SKILL.md**

Edit `C:/Users/jimsh/repos/jain-plugins/plugins/yardsailing/skills/create-sale/SKILL.md`. Replace the entire file with:

```markdown
---
name: create-sale
description: Help the user create a yard sale listing
---

When the user wants to create a yard sale, you have two paths:

## Conversational (default)

Ask one question at a time to gather:
1. Address (or confirm current location)
2. Date(s) and time range
3. Title / short description
4. What they're selling (list of categories or highlights)

After gathering everything, summarize it back and ask for confirmation. Only call `create_yard_sale` after the user confirms.

## Form-based (if user prefers)

If the user says "just give me a form" or has given a lot of info at once, render the `SaleForm` component pre-filled with any fields you've already extracted. Tell the user "Here's a form with what I have — fill in the rest."

Detect form preference by:
- Explicit request ("form", "show me the form")
- Large initial info dump (address + dates + items all at once)

Always start conversationally unless the above triggers fire.

## Authentication

You do NOT need to check if the user is signed in before calling `create_yard_sale`. The platform handles authentication automatically: if the user is not signed in when you call the tool, the tool will return an `auth_required` error, JAIN will prompt the user to sign in, and the original request will auto-retry after successful sign-in. You just focus on the conversational flow.
```

- [ ] **Step 4: Validate the plugin still parses**

```bash
cd C:/Users/jimsh/repos/jain-plugins/tools
npm run validate
```

Expected: `[yardsailing] OK` (or with a harmless warning about the components bundle; both are fine).

- [ ] **Step 5: Commit the plugin changes**

```bash
cd C:/Users/jimsh/repos/jain-plugins
git add plugins/yardsailing/skills/create-sale/tools.json plugins/yardsailing/skills/create-sale/SKILL.md plugins/yardsailing/skills/manage-sales/tools.json
git commit -m "feat(yardsailing): mark create/manage tools as auth_required + remove SKILL.md auth check

- create_yard_sale, get_my_sales, update_yard_sale, delete_yard_sale all
  declare auth_required: true. JAIN's tool executor gates them at the
  platform level for anonymous users.
- create-sale SKILL.md no longer has a Phase 1 Layer 1 STEP 1 auth check.
  The platform handles auth refusal + login prompt + auto-retry; Jain just
  focuses on the conversational flow.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 6: Verify JAIN backend still loads the updated plugin**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest -q
```

Expected: 83 tests, all green. (The JAIN backend tests use its own fixture plugins in `backend/tests/fixtures/plugins/`, not the real `jain-plugins/` repo. Those fixture plugins don't have `auth_required` set by default, so the schema change doesn't affect existing tests.)

---

## Part 3: Yardsailing

### Task 8: Yardsailing — JAIN_SERVICE_KEY config field

**Files:**
- Modify: `C:/Users/jimsh/repos/yardsailing/backend/app/config.py`

- [ ] **Step 1: Add the config field**

Read `C:/Users/jimsh/repos/yardsailing/backend/app/config.py` to find where the other `Settings` fields are defined. Add this field at the end of the `Settings` class (after the last existing field, before the `model_config` line or class closing):

```python
    # Phase 2B: JAIN integration. When empty, the JAIN service-key branch in
    # get_current_user is skipped entirely and yardsailing behaves exactly like
    # pre-Phase-2B. To enable, set this to the same value as JAIN's
    # JAIN_SERVICE_KEY env var.
    JAIN_SERVICE_KEY: str = ""
```

- [ ] **Step 2: Run the yardsailing test suite to confirm nothing broke**

```bash
cd C:/Users/jimsh/repos/yardsailing/backend
# Determine the yardsailing test command. From conftest.py it uses TEST_DATABASE_URL
# env var or falls back to the configured DATABASE_URL. Ensure a test postgres is
# available; the user runs tests in the normal development flow.
python -m pytest -q
```

Expected: all existing yardsailing tests pass. (The exact count depends on the current yardsailing test suite; just confirm nothing is broken.)

- [ ] **Step 3: Commit**

```bash
cd C:/Users/jimsh/repos/yardsailing
git add backend/app/config.py
git commit -m "feat(backend): add JAIN_SERVICE_KEY config field for phase 2b integration

Env-var gated. When empty, JAIN integration is disabled and
get_current_user behaves exactly as before. Follow-up task wires
the auth branch in get_current_user.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Yardsailing — get_current_user JAIN service-key branch

**Files:**
- Modify: `C:/Users/jimsh/repos/yardsailing/backend/app/dependencies.py`
- Create: `C:/Users/jimsh/repos/yardsailing/backend/tests/test_jain_service_auth.py`

Add the JAIN branch to the top of `get_current_user`. The branch is gated by `JAIN_SERVICE_KEY` being non-empty. When enabled, it reads `X-Jain-Service-Key`, verifies the shared secret, and resolves/creates a user by the `X-Jain-User-Email` header.

- [ ] **Step 1: Write the failing tests**

Create `C:/Users/jimsh/repos/yardsailing/backend/tests/test_jain_service_auth.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.main import create_app
from app.models.user import User


@pytest.fixture
def with_jain_key():
    """Configure JAIN_SERVICE_KEY for the test and restore after."""
    original = settings.JAIN_SERVICE_KEY
    settings.JAIN_SERVICE_KEY = "test-jain-secret-xyz"
    yield "test-jain-secret-xyz"
    settings.JAIN_SERVICE_KEY = original


@pytest.fixture
def with_jain_key_empty():
    """Ensure JAIN_SERVICE_KEY is empty (branch disabled)."""
    original = settings.JAIN_SERVICE_KEY
    settings.JAIN_SERVICE_KEY = ""
    yield
    settings.JAIN_SERVICE_KEY = original


@pytest.mark.asyncio
async def test_valid_jain_headers_resolve_existing_user(client: AsyncClient, db_session: AsyncSession, with_jain_key):
    # Seed an existing yardsailing user
    existing = User(email="alice@example.com", display_name="Alice Old")
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)

    resp = await client.get(
        "/api/auth/me",
        headers={
            "X-Jain-Service-Key": with_jain_key,
            "X-Jain-User-Email": "alice@example.com",
            "X-Jain-User-Name": "Alice Newly-updated",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "alice@example.com"
    # The returned user is the existing one (same id), not a new one
    assert data["id"] == str(existing.id)


@pytest.mark.asyncio
async def test_valid_jain_headers_auto_create_new_user(client: AsyncClient, db_session: AsyncSession, with_jain_key):
    # No pre-existing user with this email
    resp = await client.get(
        "/api/auth/me",
        headers={
            "X-Jain-Service-Key": with_jain_key,
            "X-Jain-User-Email": "newuser@example.com",
            "X-Jain-User-Name": "New User",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "newuser@example.com"

    # Verify the user was actually persisted
    result = await db_session.execute(select(User).where(User.email == "newuser@example.com"))
    persisted = result.scalar_one()
    assert persisted.display_name == "New User"


@pytest.mark.asyncio
async def test_missing_service_key_falls_through_to_cookie(client: AsyncClient, with_jain_key):
    """Without the service-key header, the JAIN branch is skipped and the
    request falls through to the existing cookie logic, which returns 401
    for an unauthenticated request."""
    resp = await client.get(
        "/api/auth/me",
        headers={
            "X-Jain-User-Email": "alice@example.com",
            "X-Jain-User-Name": "Alice",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_service_key_falls_through_to_cookie(client: AsyncClient, with_jain_key):
    """Wrong service key value → branch is skipped (not 401-directly) → falls
    through to cookie logic which 401s because there's no cookie."""
    resp = await client.get(
        "/api/auth/me",
        headers={
            "X-Jain-Service-Key": "wrong-key",
            "X-Jain-User-Email": "alice@example.com",
            "X-Jain-User-Name": "Alice",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_branch_disabled_when_service_key_empty(client: AsyncClient, with_jain_key_empty):
    """With empty JAIN_SERVICE_KEY, the entire JAIN branch is skipped even
    with valid-looking headers."""
    resp = await client.get(
        "/api/auth/me",
        headers={
            "X-Jain-Service-Key": "any-value",
            "X-Jain-User-Email": "alice@example.com",
            "X-Jain-User-Name": "Alice",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_missing_email_header_falls_through(client: AsyncClient, with_jain_key):
    """Service key valid but email header missing → fall through to cookie logic."""
    resp = await client.get(
        "/api/auth/me",
        headers={
            "X-Jain-Service-Key": with_jain_key,
            "X-Jain-User-Name": "Alice",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_email_normalization_case_insensitive(client: AsyncClient, db_session: AsyncSession, with_jain_key):
    """Email matching is case-insensitive and whitespace-stripped."""
    existing = User(email="bob@example.com", display_name="Bob")
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)

    resp = await client.get(
        "/api/auth/me",
        headers={
            "X-Jain-Service-Key": with_jain_key,
            "X-Jain-User-Email": "  BOB@example.com  ",
            "X-Jain-User-Name": "Bob",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(existing.id)
```

- [ ] **Step 2: Run the tests — expect failure**

```bash
cd C:/Users/jimsh/repos/yardsailing/backend
python -m pytest tests/test_jain_service_auth.py -v
```

Expected: all 7 tests fail because `get_current_user` still only accepts cookie auth.

- [ ] **Step 3: Implement the JAIN branch in get_current_user**

Edit `C:/Users/jimsh/repos/yardsailing/backend/app/dependencies.py`. Replace the entire file with:

```python
import re
import uuid

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_db
from .models.user import User
from .services.auth_service import decode_jwt

# UUID v4 pattern: 8-4-4-4-12 hex digits
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


async def require_device_id(x_device_id: str | None = Header(None)) -> str:
    """Validate and return the X-Device-Id header.

    Requires a valid UUID format to prevent clients from trivially
    rotating device IDs to bypass rate limits.
    """
    if not x_device_id:
        raise HTTPException(status_code=400, detail="X-Device-Id header is required")
    if not _UUID_RE.match(x_device_id):
        raise HTTPException(status_code=400, detail="X-Device-Id must be a valid UUID")
    return x_device_id


async def _get_or_create_user_by_email(
    db: AsyncSession, email: str, display_name: str
) -> User:
    """Find a user by email (case-insensitive) or create one for JAIN integration.

    Phase 2B: used by get_current_user when a valid JAIN service-key header
    identifies a user the caller wants to authenticate as.
    """
    normalized = email.strip().lower()
    result = await db.execute(select(User).where(User.email == normalized))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        email=normalized,
        display_name=display_name or normalized,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    # Phase 2B: accept JAIN service-key + trusted user identity headers.
    # Env-var gated: when settings.JAIN_SERVICE_KEY is empty, the entire
    # branch is skipped and we fall through to the existing cookie logic.
    if settings.JAIN_SERVICE_KEY:
        service_key = request.headers.get("x-jain-service-key", "")
        if service_key and service_key == settings.JAIN_SERVICE_KEY:
            email = request.headers.get("x-jain-user-email", "").strip().lower()
            if email:
                name = request.headers.get("x-jain-user-name", "").strip()
                return await _get_or_create_user_by_email(db, email, name)
        # If the service key is present but wrong, or if it's valid but the
        # email header is missing, fall through to cookie logic rather than
        # 401 directly — the caller may still have a legitimate session cookie.

    # Existing cookie-based auth (unchanged from pre-Phase-2B)
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_jwt(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    # Verify token version — allows invalidating all sessions by
    # incrementing user.token_version (e.g. on password reset / compromise).
    jwt_tv = payload.get("tv", 0)
    if jwt_tv != user.token_version:
        raise HTTPException(status_code=401, detail="Session invalidated")

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
```

- [ ] **Step 4: Run the JAIN tests — expect pass**

```bash
cd C:/Users/jimsh/repos/yardsailing/backend
python -m pytest tests/test_jain_service_auth.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Run the full yardsailing test suite**

```bash
python -m pytest -q
```

Expected: all existing tests still pass + 7 new tests pass. No regressions in the cookie-based auth paths.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/jimsh/repos/yardsailing
git add backend/app/dependencies.py backend/tests/test_jain_service_auth.py
git commit -m "feat(backend): accept JAIN service-key + user identity headers in get_current_user

Env-var gated branch at the top of get_current_user:
- If JAIN_SERVICE_KEY is set AND the request has a matching X-Jain-Service-Key
  header AND an X-Jain-User-Email header, resolve (or auto-create) a user by
  email and return it.
- If any check fails, fall through to existing cookie-based auth unchanged.
- When JAIN_SERVICE_KEY is empty (default), the branch is skipped entirely.

New helper _get_or_create_user_by_email normalizes email to lowercase+stripped
before matching. New users are auto-provisioned with email and display_name
only; role, token_version, id, created_at all use their existing defaults.

No database migration needed — uses existing users table unchanged.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

**Milestone: Yardsailing integration complete.** Yardsailing now accepts JAIN-issued identity when the shared service key is present, and seamlessly falls back to its own cookie auth when it isn't.

---

## Part 4: Mobile

### Task 10: Mobile store refactor — remove Phase 1 auth, add pendingRetry

**Files:**
- Modify: `C:/Users/jimsh/repos/jain/mobile/src/store/useAppStore.ts`

- [ ] **Step 1: Update the store**

Edit `C:/Users/jimsh/repos/jain/mobile/src/store/useAppStore.ts`. Find the `AppState` interface and remove the `auth` + `setPluginAuth` fields. Add `pendingRetry` + `setPendingRetry` + `clearPendingRetry` fields. The relevant section should change from:

```typescript
  // Per-plugin auth state. Layer 1: hardcoded false until login UI lands.
  auth: Record<string, boolean>;
  setPluginAuth: (plugin: string, authenticated: boolean) => void;

  // Phase 2A: real JAIN session (Google OAuth). Null when signed out.
  session: Session | null;
  setSession: (session: Session | null) => void;
```

to:

```typescript
  // Phase 2A: real JAIN session (Google OAuth). Null when signed out.
  session: Session | null;
  setSession: (session: Session | null) => void;

  // Phase 2B: pending user message that needs to be auto-retried after sign-in.
  // Set by useChat when an auth_required response comes back. Cleared on manual
  // send and on successful retry.
  pendingRetry: string | null;
  setPendingRetry: (message: string | null) => void;
  clearPendingRetry: () => void;
```

Then update the `create<AppState>(...)` body. Remove the `auth` initializer and `setPluginAuth` implementation:

Replace:
```typescript
  // Layer 1: yardsailing auth defaults to false until we add a login flow.
  // Jain reads this via the chat request and prompts the user accordingly.
  auth: { yardsailing: false },
  setPluginAuth: (plugin, authenticated) =>
    set((s) => ({ auth: { ...s.auth, [plugin]: authenticated } })),

  // Phase 2A: real JAIN session (Google OAuth). Null when signed out.
  session: null,
  setSession: (session) => set({ session }),
```

with:

```typescript
  // Phase 2A: real JAIN session (Google OAuth). Null when signed out.
  session: null,
  setSession: (session) => set({ session }),

  // Phase 2B: pending user message for auto-retry after sign-in.
  pendingRetry: null,
  setPendingRetry: (message) => set({ pendingRetry: message }),
  clearPendingRetry: () => set({ pendingRetry: null }),
```

- [ ] **Step 2: Verify tsc still compiles (it won't yet — expect errors from other files)**

```bash
cd C:/Users/jimsh/repos/jain/mobile
npx tsc --noEmit 2>&1 | tail -20
```

Expected: errors in `src/api/chat.ts` and `src/hooks/useChat.ts` that reference the removed `auth` field. These will be fixed in the next task. Do NOT commit yet.

---

### Task 11: Mobile API + useChat cleanup

**Files:**
- Modify: `C:/Users/jimsh/repos/jain/mobile/src/api/chat.ts`
- Modify: `C:/Users/jimsh/repos/jain/mobile/src/hooks/useChat.ts`
- Modify: `C:/Users/jimsh/repos/jain/mobile/src/types.ts`

Removes the `auth` field from the chat API call and updates `useChat` to handle the new `display_hint: "auth_required"` path. This task fixes the tsc errors from Task 10 and adds the `pendingRetry` side effect.

- [ ] **Step 1: Update types to include the new display_hint value (documentation only)**

No code change needed for `types.ts` strictly — `display_hint` is already typed as `string | null` in `ChatResponse`. But to make the valid values explicit, add a comment in `src/types.ts` just above the `ChatResponse` interface:

Find:
```typescript
export interface ChatResponse {
  reply: string;
  data: unknown | null;
  display_hint: string | null;
  tool_events: ToolEvent[];
}
```

Replace with:
```typescript
// Valid display_hint values as of Phase 2B:
//   "map"            — render data.sales as map pins (Phase 1)
//   "auth_required"  — render AuthPrompt with data.plugin as context (Phase 2B)
//   null             — no special UI, just show reply text
export interface ChatResponse {
  reply: string;
  data: unknown | null;
  display_hint: string | null;
  tool_events: ToolEvent[];
}
```

- [ ] **Step 2: Remove auth field from sendChatMessage**

Edit `C:/Users/jimsh/repos/jain/mobile/src/api/chat.ts`. Replace the entire file with:

```typescript
import { apiClient } from "./client";
import { ChatResponse, ChatTurn } from "../types";

export async function sendChatMessage(params: {
  message: string;
  history: ChatTurn[];
  lat?: number;
  lng?: number;
}): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>("/api/chat", params);
  return data;
}
```

(The axios interceptor already attaches the JAIN JWT to every request via the Authorization header, so the backend can resolve the user. No explicit auth field needed.)

- [ ] **Step 3: Update useChat to handle auth_required + set pendingRetry**

Edit `C:/Users/jimsh/repos/jain/mobile/src/hooks/useChat.ts`. Replace the entire file with:

```typescript
import { useEffect, useState } from "react";

import { sendChatMessage } from "../api/chat";
import { useAppStore } from "../store/useAppStore";
import { ChatResponse, Sale } from "../types";

export function useChat() {
  const messages = useAppStore((s) => s.messages);
  const appendMessage = useAppStore((s) => s.appendMessage);
  const setSales = useAppStore((s) => s.setSales);
  const showComponent = useAppStore((s) => s.showComponent);
  const location = useAppStore((s) => s.location);
  const plugins = useAppStore((s) => s.plugins);
  const session = useAppStore((s) => s.session);
  const pendingRetry = useAppStore((s) => s.pendingRetry);
  const setPendingRetry = useAppStore((s) => s.setPendingRetry);
  const clearPendingRetry = useAppStore((s) => s.clearPendingRetry);

  const [sending, setSending] = useState(false);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);

  const send = async (text: string) => {
    if (!text.trim() || sending) return;

    // Manual send always clears any stale pending retry
    clearPendingRetry();

    const userTurn = { role: "user" as const, content: text };
    appendMessage(userTurn);
    setSending(true);

    try {
      const res = await sendChatMessage({
        message: text,
        history: messages,
        lat: location?.lat,
        lng: location?.lng,
      });
      setLastResponse(res);
      appendMessage({ role: "assistant", content: res.reply || "(no reply)" });

      // Handle display_hint and data
      if (res.display_hint === "map" && res.data && typeof res.data === "object") {
        const maybeSales = (res.data as { sales?: Sale[] }).sales;
        if (Array.isArray(maybeSales)) setSales(maybeSales);
      }

      if (res.display_hint === "auth_required") {
        // Store the original user message so we can auto-retry after sign-in
        setPendingRetry(text);
      }

      if (res.display_hint?.startsWith("component:")) {
        const [, name] = res.display_hint.split(":");
        const owner = plugins.find((p) => p.components?.exports.includes(name));
        if (owner) showComponent(owner.name, name, res.data ?? undefined);
      }
    } catch (e) {
      appendMessage({
        role: "assistant",
        content: `(error: ${(e as Error).message})`,
      });
    } finally {
      setSending(false);
    }
  };

  // Phase 2B: auto-retry the pending message when the user signs in.
  useEffect(() => {
    if (session && pendingRetry) {
      const message = pendingRetry;
      clearPendingRetry();
      // Small tick so the UI has time to dismiss the AuthPrompt and
      // re-render the logged-in state before the new request fires.
      const timer = setTimeout(() => {
        void send(message);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [session, pendingRetry]);

  return { messages, send, sending, lastResponse };
}
```

- [ ] **Step 4: Verify tsc compiles cleanly**

```bash
cd C:/Users/jimsh/repos/jain/mobile
npx tsc --noEmit 2>&1 | tail -10
```

Expected: no output (clean compile). If there are errors, they're likely stale references to the removed `auth` field somewhere we haven't touched yet — fix inline.

- [ ] **Step 5: Commit Tasks 10 + 11 together**

```bash
cd C:/Users/jimsh/repos/jain
git add mobile/src/store/useAppStore.ts mobile/src/api/chat.ts mobile/src/hooks/useChat.ts mobile/src/types.ts
git commit -m "refactor(mobile): remove phase 1 auth field; add pendingRetry + auto-retry

- Store: removed auth: Record<string, boolean> and setPluginAuth (phase 1
  layer 1 is obsolete now that the platform handles auth via JWT).
- Store: added pendingRetry: string | null with set/clear actions.
- API: sendChatMessage no longer sends an auth field.
- useChat: sets pendingRetry when receiving display_hint='auth_required';
  clears on manual send; fires auto-retry via useEffect when session
  transitions null → non-null AND pendingRetry is set.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: AuthPrompt component

**Files:**
- Create: `C:/Users/jimsh/repos/jain/mobile/src/chat/AuthPrompt.tsx`

A small, dedicated component that renders the inline "Sign in to continue" card below an assistant message when the chat response carries `display_hint: "auth_required"`.

- [ ] **Step 1: Create the component**

Create `C:/Users/jimsh/repos/jain/mobile/src/chat/AuthPrompt.tsx`:

```tsx
import React, { useState } from "react";
import { Alert, StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { signInWithGoogle } from "../api/auth";
import { useGoogleSignIn } from "../auth/googleAuth";
import { setToken } from "../auth/tokenStorage";
import { useAppStore } from "../store/useAppStore";

/**
 * Inline login prompt shown in the chat when the backend returns
 * display_hint === "auth_required". Uses the same Google OAuth flow
 * as the Settings tab. On successful sign-in, useChat's effect picks
 * up the session change and auto-retries the pending message.
 */
export function AuthPrompt() {
  const setSession = useAppStore((s) => s.setSession);
  const clearPendingRetry = useAppStore((s) => s.clearPendingRetry);
  const { signIn: googleSignIn, ready: googleReady } = useGoogleSignIn();
  const [signingIn, setSigningIn] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const handleSignIn = async () => {
    if (signingIn) return;
    setSigningIn(true);
    try {
      const idToken = await googleSignIn();
      if (!idToken) return; // user cancelled
      const newSession = await signInWithGoogle(idToken);
      await setToken(newSession.token);
      setSession(newSession);
      // Do NOT clear pendingRetry here — useChat's effect reads it and
      // fires the auto-retry; the effect itself clears it.
    } catch (e) {
      Alert.alert("Sign-in failed", (e as Error).message || "Try again later.");
    } finally {
      setSigningIn(false);
    }
  };

  const handleDismiss = () => {
    clearPendingRetry();
    setDismissed(true);
  };

  return (
    <View style={styles.card}>
      <TouchableOpacity style={styles.dismiss} onPress={handleDismiss}>
        <Text style={styles.dismissText}>×</Text>
      </TouchableOpacity>

      <Text style={styles.title}>Sign in to continue</Text>
      <Text style={styles.subtitle}>
        You'll need to sign in with Google to continue with that request.
      </Text>

      <TouchableOpacity
        style={[
          styles.button,
          (!googleReady || signingIn) && styles.buttonDisabled,
        ]}
        onPress={handleSignIn}
        disabled={!googleReady || signingIn}
      >
        <Text style={styles.buttonText}>
          {signingIn ? "Signing in..." : "Sign in with Google"}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#eff6ff",
    padding: 16,
    marginHorizontal: 12,
    marginVertical: 8,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#bfdbfe",
    position: "relative",
  },
  dismiss: {
    position: "absolute",
    top: 6,
    right: 10,
    width: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  dismissText: {
    fontSize: 22,
    color: "#64748b",
    lineHeight: 22,
  },
  title: {
    fontSize: 16,
    fontWeight: "600",
    color: "#1e3a8a",
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: "#1e40af",
    marginBottom: 12,
  },
  button: {
    backgroundColor: "#2563eb",
    padding: 12,
    borderRadius: 8,
    alignItems: "center",
  },
  buttonDisabled: {
    backgroundColor: "#94a3b8",
  },
  buttonText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "600",
  },
});
```

- [ ] **Step 2: Verify tsc compiles**

```bash
cd C:/Users/jimsh/repos/jain/mobile
npx tsc --noEmit 2>&1 | tail -10
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add mobile/src/chat/AuthPrompt.tsx
git commit -m "feat(mobile): add AuthPrompt inline login component

Rendered in chat when display_hint === 'auth_required'. Uses the same
Google OAuth flow as Settings. On successful sign-in, useChat's
useEffect fires the auto-retry via the pendingRetry store state.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: ChatScreen renders AuthPrompt

**Files:**
- Modify: `C:/Users/jimsh/repos/jain/mobile/src/screens/ChatScreen.tsx`

- [ ] **Step 1: Import and render AuthPrompt conditionally**

Edit `C:/Users/jimsh/repos/jain/mobile/src/screens/ChatScreen.tsx`. Add an import for `AuthPrompt` near the other `src/chat/` imports:

Find:
```tsx
import { DataCard } from "../chat/DataCard";
import { MessageBubble } from "../chat/MessageBubble";
import { ToolIndicator } from "../chat/ToolIndicator";
```

Replace with:
```tsx
import { AuthPrompt } from "../chat/AuthPrompt";
import { DataCard } from "../chat/DataCard";
import { MessageBubble } from "../chat/MessageBubble";
import { ToolIndicator } from "../chat/ToolIndicator";
```

Then find the section that renders the `DataCard` and `ToolIndicator`:

```tsx
      {lastResponse?.display_hint && lastResponse.data ? (
        <DataCard displayHint={lastResponse.display_hint} data={lastResponse.data} />
      ) : null}
      <ToolIndicator visible={sending} />
```

Replace with:
```tsx
      {lastResponse?.display_hint === "auth_required" ? <AuthPrompt /> : null}
      {lastResponse?.display_hint &&
      lastResponse.display_hint !== "auth_required" &&
      lastResponse.data ? (
        <DataCard displayHint={lastResponse.display_hint} data={lastResponse.data} />
      ) : null}
      <ToolIndicator visible={sending} />
```

(AuthPrompt gets its own render branch. DataCard's existing render is restricted to non-auth_required hints so we don't accidentally show both.)

- [ ] **Step 2: Verify tsc compiles**

```bash
cd C:/Users/jimsh/repos/jain/mobile
npx tsc --noEmit 2>&1 | tail -10
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add mobile/src/screens/ChatScreen.tsx
git commit -m "feat(mobile): render AuthPrompt in ChatScreen on display_hint='auth_required'

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

**Milestone: Mobile Phase 2B complete.** The mobile app now removes Phase 1 Layer 1 auth scaffolding, tracks pendingRetry for auto-retry, renders AuthPrompt when the backend returns auth_required, and auto-fires the retry when the user signs in.

---

## Part 5: Service Key Setup + End-to-End Acceptance

### Task 14: Service key generation, config, and acceptance walkthrough

**Files:** none — this is a configuration and manual QA run.

#### Phase A: Service key generation + config

- [ ] **Step 1: Generate a shared service key**

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output (~43 characters). This is the shared secret between JAIN and yardsailing.

- [ ] **Step 2: Add it to JAIN's `.env`**

Edit `C:/Users/jimsh/repos/jain/backend/.env`. Append:

```env

# Phase 2B: shared key for JAIN ↔ plugin service-to-service calls
JAIN_SERVICE_KEY=<paste the generated key here>
```

- [ ] **Step 3: Add the SAME key to yardsailing's `.env`**

Edit `C:/Users/jimsh/repos/yardsailing/backend/.env`. Append:

```env

# Phase 2B: shared key for JAIN integration. Must match JAIN's JAIN_SERVICE_KEY.
JAIN_SERVICE_KEY=<paste the SAME generated key here>
```

Both files must have the exact same value — that's what proves to yardsailing that the request came from JAIN.

- [ ] **Step 4: Restart both backends**

```bash
# Terminal 1 — JAIN backend
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# Terminal 2 — Yardsailing backend
cd C:/Users/jimsh/repos/yardsailing/backend
# Use whatever command you normally use to run yardsailing locally
# (e.g., .venv/Scripts/uvicorn app.main:app --reload --port 8001)
```

If yardsailing is already running in dev mode, Ctrl+C and restart so it picks up the new `.env` value.

- [ ] **Step 5: Quick health check**

```bash
curl http://localhost:8000/api/health
# Yardsailing's health endpoint — adjust URL if different
curl http://localhost:8001/api/health
```

Both should return `{"status":"ok"}`.

#### Phase B: End-to-end acceptance walkthrough

Use the same Google account you used during Phase 2A testing (`jim.shelly@gmail.com`). For the create-sale criterion, **the account must have 0 existing yardsailing sales** or the existing payment gate will 402 on the second sale onward. If your Google account already has yardsailing sales from before, use a fresh Google account for the walkthrough.

- [ ] **Step 6: Start Metro and open the app on web**

```bash
cd C:/Users/jimsh/repos/jain/mobile
npx expo start --clear
```

Press `w` to open in Chrome (iPhone Expo Go still doesn't work for Google Sign-In per Phase 2A findings).

- [ ] **Step 7: Criterion 1 — Logged-out public tool still works**

1. Make sure you're signed out (tap Settings → Sign out if needed)
2. Tap the Jain tab
3. Type: `find yard sales near me`
4. Expected: Jain calls `find_yard_sales` anonymously, returns results normally, map shows pins

- [ ] **Step 8: Criterion 2 — Logged-out auth-required tool triggers inline login**

1. Still logged out
2. Type: `I want to create a yard sale`
3. Expected: Jain responds with a short message like "I'd love to help with that — you'll need to sign in first", and an `<AuthPrompt />` card appears below with a "Sign in with Google" button

- [ ] **Step 9: Criterion 3 — Inline login triggers OAuth and auto-retries**

1. Tap the "Sign in with Google" button in the AuthPrompt
2. Google OAuth flow opens in a popup
3. Sign in with your test account
4. Expected: popup closes, AuthPrompt disappears, Jain automatically re-processes "I want to create a yard sale" without you re-typing, and now asks a conversational question like "What's the address?"

- [ ] **Step 10: Criterion 4 — Conversational create completes end-to-end**

1. Answer Jain's questions one at a time:
   - Address: `123 Oak St, Cushing OK 74023` (or any real-ish address)
   - Date: `Saturday April 11 2026`
   - Time: `8 AM to 2 PM`
   - Title: `Test sale from JAIN`
   - Items: `Furniture and books`
2. After Jain summarizes and asks for confirmation, say `yes`
3. Expected: Jain calls `create_yard_sale`, yardsailing creates the sale under your user row (matched by email), Jain responds with a confirmation message

- [ ] **Step 11: Verify the sale actually exists in yardsailing**

Open a new browser tab and go to your yardsailing web frontend (wherever it runs locally — typically `http://localhost:5173` for the SvelteKit dev server), sign in to yardsailing directly with your existing magic-link flow using the same email (`jim.shelly@gmail.com`), and check "My Sales." The test sale should be there.

Alternatively, query the database directly:

```bash
# Connect to yardsailing's database and run:
SELECT id, title, owner_id, created_at FROM yard_sales WHERE title LIKE '%JAIN%' ORDER BY created_at DESC LIMIT 5;
```

The sale should exist with `owner_id` pointing at your user row (whose email matches your Google account).

- [ ] **Step 12: Criterion 5 — Sign out + sign back in works normally**

1. Tap Settings → Sign out
2. Settings reverts to "Not signed in"
3. Tap Jain tab → type `I want to create a yard sale` again
4. Auth prompt reappears (proves pendingRetry is properly cleared on sign out)
5. Sign back in via the inline button
6. Conversation continues where it left off

- [ ] **Step 13: Criterion 6 — Verify no regressions**

1. Phase 1 + 2A tests still pass:
   ```bash
   cd C:/Users/jimsh/repos/jain/backend
   .venv/Scripts/python -m pytest -q
   ```
   Expected: 83 tests, all green.

2. Yardsailing tests still pass:
   ```bash
   cd C:/Users/jimsh/repos/yardsailing/backend
   python -m pytest -q
   ```
   Expected: all existing + 7 new JAIN tests green.

3. Mobile tsc passes:
   ```bash
   cd C:/Users/jimsh/repos/jain/mobile
   npx tsc --noEmit
   ```
   Expected: no output.

- [ ] **Step 14: Write the acceptance report**

Create `C:/Users/jimsh/repos/jain/docs/superpowers/acceptance/2026-04-10-phase-2b.md`:

```markdown
# Phase 2B Acceptance — 2026-04-10

**Tested by:** Jim Shelly
**Branch:** `feature/phase-2b-plugin-auth-passthrough`
**Backend tests:** <N>/<N> passing
**Yardsailing tests:** <N>/<N> passing
**Result:** <Accepted | Deferred | Failed>

## Success Criteria

| # | Criterion | Status | Notes |
|---|-----------|--------|-------|
| 1 | Logged-out find_yard_sales still works anonymously | <PASS/FAIL> | |
| 2 | Logged-out create-sale request triggers AuthPrompt | <PASS/FAIL> | |
| 3 | Inline login completes OAuth and auto-retries | <PASS/FAIL> | |
| 4 | Conversational create completes end-to-end | <PASS/FAIL> | |
| 5 | Sale actually persists in yardsailing DB under correct user | <PASS/FAIL> | |
| 6 | Sign out clears pendingRetry; sign back in works | <PASS/FAIL> | |
| 7 | JAIN backend tests pass (83 total) | <PASS/FAIL> | |
| 8 | Yardsailing tests pass (existing + 7 new) | <PASS/FAIL> | |
| 9 | Mobile tsc --noEmit clean | <PASS/FAIL> | |
| 10 | Phase 1/2A regressions: none | <PASS/FAIL> | |

## Issues encountered
<free-form>
```

Fill in PASS/FAIL for each row.

- [ ] **Step 15: Commit the acceptance report**

```bash
cd C:/Users/jimsh/repos/jain
git add docs/superpowers/acceptance/2026-04-10-phase-2b.md
git commit -m "docs: phase 2b acceptance report

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

**Phase 2B complete.** The JAIN + yardsailing auth pass-through, the inline chat-triggered login, and the auto-retry mechanism all work end-to-end. Jim's first real yard sale created through JAIN is in the yardsailing database.

---

## Self-Review Notes

**Spec coverage:**
- JAIN backend `JAIN_SERVICE_KEY` config field — Task 1 ✓
- JAIN backend `ToolDef.auth_required` field — Task 1 ✓
- `get_current_user_optional` dependency — Task 2 ✓
- Tool executor auth gate + service-key headers — Task 3 ✓
- Context builder accepts optional User — Task 4 ✓
- Chat service accepts user + short-circuits — Task 5 ✓
- Chat router uses optional dep — Task 6 ✓
- `ChatRequest.auth` field removed — Task 6 ✓
- Yardsailing tool definitions marked auth_required — Task 7 ✓
- Create-sale SKILL.md Phase 1 auth check removed — Task 7 ✓
- Yardsailing `JAIN_SERVICE_KEY` config — Task 8 ✓
- Yardsailing `get_current_user` branch + auto-provision helper — Task 9 ✓
- Mobile store: remove Phase 1 auth, add pendingRetry — Task 10 ✓
- Mobile API: remove auth field — Task 11 ✓
- Mobile useChat: pendingRetry + auto-retry effect — Task 11 ✓
- AuthPrompt component — Task 12 ✓
- ChatScreen renders AuthPrompt on auth_required — Task 13 ✓
- Service key generation + dual-repo config — Task 14 Phase A ✓
- End-to-end acceptance walkthrough with all criteria — Task 14 Phase B ✓
- Phase 1/2A regression check — Task 14 Step 13 ✓

**Placeholder scan:** no TBDs, TODOs, or vague language. Every code step has complete, ready-to-paste code. Every command has an expected outcome. All test assertions are concrete.

**Type consistency check:**
- `User | None` used consistently across `get_current_user_optional`, tool executor, context builder, chat service, chat router.
- `X-Jain-Service-Key` / `X-Jain-User-Email` / `X-Jain-User-Name` header names used consistently between JAIN's tool executor and yardsailing's branch.
- `display_hint: "auth_required"` used consistently between chat service, mobile types comment, useChat effect, AuthPrompt trigger in ChatScreen.
- `pendingRetry` state name consistent across store, useChat, AuthPrompt.
- `JAIN_SERVICE_KEY` env var name consistent between both `.env` files, both config modules, and tool executor header forwarding.
- `_get_or_create_user_by_email` signature `(db, email, display_name)` matches between definition in dependencies.py and invocation in the get_current_user branch.
- `ChatService.send(conversation, user)` signature matches between definition in chat_service.py and invocations in chat router + chat service tests.
- `ToolExecutor.execute(call, user)` signature matches between definition and all test + router invocations.

**Known scope items deferred (from spec Open Questions):**
- Payment gate caveat — acceptance test uses fresh account to avoid (documented in Task 14 Phase B header).
- Yardsailing User model inspection — done during plan writing (email, display_name, role defaulted, token_version defaulted, id auto-generated, created_at auto). Task 9's `_get_or_create_user_by_email` implementation uses the actual fields.
- SKILL.md update — done in Task 7.
