# JAIN Phase 1 Design

**Date:** 2026-04-09
**Status:** Approved for implementation planning
**Related:** pokkit-IT/yardsailing#23

## Overview

JAIN is an AI-first mobile app where a conversational assistant ("Jain") is the primary interface. Capabilities are delivered via **plugins** — self-contained packages that each extend Jain with new skills, tools, UI, and data sources. The existing yardsailing app becomes the first plugin.

JAIN is LLM-agnostic: the backend talks to any configured LLM provider (Anthropic, Ollama, OpenAI, private/self-hosted) through a unified interface. Plugins are declarative and provider-neutral.

## Goals

1. Deliver an AI-first mobile experience where Jain is the primary entry point, not a secondary feature.
2. Establish a plugin architecture that supports lightweight (prompt-only) plugins and full plugins (with custom UI and backend routes).
3. Keep the existing yardsailing backend deployed and unchanged — the yardsailing plugin is an adapter layer.
4. Stay LLM-agnostic so the app can run against hosted or private LLMs without rewrites.
5. Ship Phase 1 narrow enough to prove the core loop works end-to-end.

## Non-Goals for Phase 1

- Dynamic plugin downloads from a remote registry (plugins load from local filesystem or hardcoded GitHub raw URL)
- Plugin install/uninstall management UI
- Ollama or OpenAI provider implementations (interface exists, only Anthropic is wired)
- User authentication (anonymous requests to yardsailing)
- Persistent agent/skills settings (endpoints stubbed, no DB table)
- Multiple plugins (only yardsailing)
- Push notifications, camera, voice, route planning

## System Architecture

### Three Repos

| Repo | Purpose |
|------|---------|
| **jain** (new) | Core app — React Native frontend + FastAPI backend + plugin host |
| **jain-plugins** (new) | Plugin registry — all plugins (yardsailing in Phase 1) |
| **yardsailing** (existing) | Stays deployed as-is. The yardsailing plugin calls its existing API. |

### Runtime Flow

```
User opens JAIN app
  → App loads → fetches plugin manifest from registry
  → Downloads installed plugins (SKILL.md + optional JS bundle)
  → Jain chat ready

User: "find yard sales near me"
  → Jain engine sees find-sales skill description in context
  → LLM invokes find_yard_sales tool
  → JAIN backend calls yardsailing API (https://api.yardsailing.sale)
  → Returns sales data
  → Core Map component renders pins

User: "I want to create a yard sale"
  → Jain engine sees create-sale skill
  → Skill supports conversational gathering OR form handoff
  → If form: JAIN loads yardsailing JS bundle, renders SaleForm natively
  → Submission → yardsailing API creates sale
```

## Plugin System

### Unified Format

Every capability is a plugin. Plugins range from lightweight (just a `SKILL.md`) to full (custom UI + backend routes + assets). One format handles all cases.

```
yardsailing/
├── plugin.json          # required (name, version, capabilities)
├── skills/
│   ├── find-sales/SKILL.md
│   ├── create-sale/SKILL.md
│   └── manage-sales/SKILL.md
├── src/                 # optional — custom React Native components
│   ├── SaleForm.tsx
│   └── SaleDetail.tsx
├── dist/                # built bundle output
│   └── components.bundle.js
├── assets/              # optional
│   └── icon.png
└── package.json         # when the plugin has buildable components
```

Lightweight example:

```
small-talk/
├── plugin.json
└── skills/
    └── chat/SKILL.md
```

### Plugin Manifest (`plugin.json`)

```json
{
  "name": "yardsailing",
  "version": "1.0.0",
  "description": "Find, create, and manage yard sales",
  "author": "pokkit-IT",
  "skills": [
    {
      "name": "find-sales",
      "description": "Find yard sales near a location. Use when user asks about sales, garage sales, or estate sales nearby.",
      "tools": ["find_yard_sales"]
    },
    {
      "name": "create-sale",
      "description": "Help user create a yard sale listing. Can gather info conversationally or present a form.",
      "tools": ["create_yard_sale"],
      "components": ["SaleForm"]
    },
    {
      "name": "manage-sales",
      "description": "Edit, delete, or check status of user's yard sales.",
      "tools": ["update_yard_sale", "delete_yard_sale", "get_my_sales"]
    }
  ],
  "components": {
    "bundle": "dist/components.bundle.js",
    "exports": ["SaleForm", "SaleDetail"]
  },
  "api": {
    "base_url": "https://api.yardsailing.sale",
    "auth_required": false
  },
  "assets": ["icons/yardsailing.png"]
}
```

### Tool Definitions

Tool schemas live alongside each skill and are provider-neutral. Jain's engine translates them to the active LLM provider's format at call time.

```json
{
  "name": "find_yard_sales",
  "description": "Search for yard sales near a location",
  "input_schema": {
    "type": "object",
    "properties": {
      "lat": { "type": "number" },
      "lng": { "type": "number" },
      "radius_miles": { "type": "integer", "default": 10 }
    },
    "required": ["lat", "lng"]
  }
}
```

### Plugin Lifecycle

```
Registry (jain-plugins repo)
  → JAIN app fetches registry index (Phase 1: local filesystem or GitHub raw URL)
  → Download: plugin.json + SKILL.md files + JS bundle (if any) + assets
  → Register: skill descriptions injected into Jain's system prompt
  → Register: tools added to LLM's tool definitions
  → Register: components available for Jain to render
  → Ready
```

## JAIN Core — Backend

FastAPI + SQLAlchemy async, SQLite in Phase 1 (Postgres later). Structure:

```
backend/
├── app/
│   ├── main.py                  # FastAPI app + lifespan
│   ├── config.py                # Settings (LLM provider, DB, plugin source)
│   ├── database.py              # SQLAlchemy async engine
│   │
│   ├── engine/                  # LLM abstraction
│   │   ├── base.py              # LLMProvider interface
│   │   ├── anthropic.py         # Anthropic provider (Phase 1)
│   │   ├── ollama.py            # Stub for Phase 2
│   │   ├── openai.py            # Stub for Phase 2
│   │   └── tool_executor.py     # Executes tool calls against plugins
│   │
│   ├── plugins/
│   │   ├── registry.py          # Discovers, loads, manages plugins
│   │   ├── loader.py            # Loads plugin packages (local/remote)
│   │   └── schema.py            # PluginManifest, SkillDef, ToolDef models
│   │
│   ├── routers/
│   │   ├── chat.py              # POST /api/chat
│   │   ├── plugins.py           # GET /api/plugins
│   │   ├── settings.py          # GET/PUT /api/settings (stubbed)
│   │   └── health.py            # GET /api/health
│   │
│   ├── services/
│   │   ├── chat_service.py      # Core chat loop
│   │   ├── plugin_service.py    # Plugin management
│   │   └── context_builder.py   # Builds system prompt from active skills
│   │
│   ├── models/
│   │   ├── conversation.py      # Chat history
│   │   └── installed_plugin.py
│   │
│   └── schemas/
│       ├── chat.py
│       ├── plugin.py
│       └── settings.py
│
├── alembic/
├── requirements.txt
└── tests/
```

### Chat Flow

```
POST /api/chat { message, lat?, lng? }
  │
  ├── context_builder.py
  │   ├── Load Jain system prompt
  │   ├── Load active skill descriptions from installed plugins
  │   ├── Build tool definitions from installed plugins
  │   └── Append conversation history
  │
  ├── engine/base.py → configured provider
  │   └── Send to LLM with system + messages + tools
  │
  ├── LLM response
  │   ├── Text only → return to user
  │   └── Tool call → tool_executor.py
  │       ├── Look up tool → find owning plugin
  │       ├── Call plugin's api.base_url + endpoint
  │       ├── Return tool result to LLM
  │       └── LLM generates final response
  │
  └── Response { reply, data?, display_hint? }
```

### Display Hints

The backend tells the frontend what to render via `display_hint`:

- `"map"` → core Map component with data as pins
- `"list"` → core CardList
- `"component:SaleForm"` → load plugin bundle, render component by name
- `null` → text-only reply in chat

### LLM Provider Abstraction

```python
class LLMProvider:
    async def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDef],
    ) -> LLMResponse: ...
```

Config:

```env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514
LLM_BASE_URL=
```

Only `AnthropicProvider` is implemented in Phase 1. The interface and configuration pathway exist so swapping providers is a pure Phase 2 addition.

## JAIN Core — Frontend

React Native + Expo, TypeScript.

```
mobile/
├── App.tsx
├── app.json
├── src/
│   ├── api/
│   │   └── client.ts              # Axios instance
│   │
│   ├── screens/
│   │   ├── ChatScreen.tsx         # Primary Jain interface
│   │   ├── MapScreen.tsx          # Full-screen map view
│   │   └── SettingsScreen.tsx     # LLM config, installed plugins
│   │
│   ├── core/                      # Shared UI primitives
│   │   ├── Map.tsx                # Reusable map component
│   │   ├── CardList.tsx           # Scrollable card list
│   │   ├── DetailSheet.tsx        # Bottom sheet
│   │   ├── PreviewCard.tsx        # In-chat summary card
│   │   └── FormRenderer.tsx       # Simple schema-based forms
│   │
│   ├── plugins/
│   │   ├── PluginHost.tsx         # Loads + renders plugin JS bundles
│   │   ├── PluginBridge.ts        # Bridge: plugin components → core services
│   │   └── registry.ts            # Local plugin state
│   │
│   ├── chat/
│   │   ├── MessageBubble.tsx
│   │   ├── DataCard.tsx           # Renders display_hint results inline
│   │   └── ToolIndicator.tsx      # "Searching for yard sales..." status
│   │
│   ├── store/
│   │   └── useAppStore.ts         # Zustand: location, plugins, messages, settings
│   │
│   └── hooks/
│       ├── useLocation.ts         # expo-location wrapper
│       └── useChat.ts             # Chat send/receive
│
├── package.json
└── tsconfig.json
```

### Navigation

Bottom tabs — three tabs total:

| Tab | Screen | Purpose |
|-----|--------|---------|
| Jain | ChatScreen | Primary interface — everything starts here |
| Map | MapScreen | Full-screen map, updated when skills return geo data |
| Settings | SettingsScreen | LLM config, plugin management (read-only in Phase 1) |

The List view is not a tab — it's a display mode Jain can trigger within chat or as an overlay on the map. Jain is the primary interface; the map is a secondary context.

### Plugin Component Loading

When a chat response carries `display_hint: "component:SaleForm"`:

```
ChatScreen receives response with display_hint
  → Calls PluginHost.load("yardsailing", "SaleForm")
  → PluginHost ensures components.bundle.js is cached
  → Evaluates bundle, registers exports on global namespace
  → Renders SaleForm with PluginBridge providing:
      - core services (location, auth, navigation, map handle)
      - data from LLM response (pre-filled fields)
  → SaleForm renders natively inside chat or as a modal
```

**Dynamic loading constraint:** React Native is the only mainstream cross-platform framework that allows compliant dynamic component loading on iOS. Apple's guideline 2.5.2 permits JavaScript executed by JavaScriptCore. Plugin bundles are JS — they execute natively via the existing RN runtime, no WebView required.

## Conversational UX — Create Sale Example

The create-sale skill supports three user paths:

### Path A: Conversational (Jain drives)

Jain asks a series of questions, builds the sale object internally, shows a preview card (core component), and posts on confirmation.

### Path B: Pre-filled form (Jain assists)

User gives partial info up front. Jain renders the plugin's `SaleForm` pre-populated with extracted fields. User completes and submits.

### Path C: Loose context

User expresses intent ambiguously ("my garage is overflowing"). Jain recognizes the opportunity, offers help, falls into Path A.

The skill's `SKILL.md` describes all three paths and lets the LLM choose based on conversation state. The `SaleForm` component is a tool Jain can produce, not the entry point.

## Plugin Registry (jain-plugins repo)

```
jain-plugins/
├── README.md
├── registry.json                  # Master index of all plugins
├── plugins/
│   ├── yardsailing/                # Phase 1: only this plugin
│   │   ├── plugin.json
│   │   ├── skills/
│   │   │   ├── find-sales/SKILL.md
│   │   │   ├── create-sale/SKILL.md
│   │   │   └── manage-sales/SKILL.md
│   │   ├── src/
│   │   │   ├── SaleForm.tsx
│   │   │   └── SaleDetail.tsx
│   │   ├── dist/
│   │   │   └── components.bundle.js
│   │   ├── assets/
│   │   │   └── icon.png
│   │   └── package.json
│
├── tools/
│   ├── build.ts                   # Builds plugin component bundles
│   ├── validate.ts                # Validates manifests + SKILL.md schemas
│   └── publish.ts                 # Phase 2
│
├── .github/workflows/
│   └── validate.yml               # CI: validate + build on PR
│
└── docs/
    ├── PLUGIN_FORMAT.md
    └── BUILDING.md
```

### registry.json

```json
{
  "version": "1.0.0",
  "updated": "2026-04-09T00:00:00Z",
  "plugins": [
    {
      "name": "yardsailing",
      "version": "1.0.0",
      "description": "Find, create, and manage yard sales",
      "author": "pokkit-IT",
      "category": "lifestyle",
      "icon": "plugins/yardsailing/assets/icon.png",
      "manifest_url": "plugins/yardsailing/plugin.json",
      "has_components": true,
      "has_api": true
    }
  ]
}
```

### Phase 1 Distribution

Plugins load from local filesystem (dev) or hardcoded GitHub raw URL (test builds). Dynamic CDN distribution is Phase 2.

### Build Pipeline

For plugins with components:

```
src/SaleForm.tsx  ─┐
src/SaleDetail.tsx ─┼──> esbuild ──> dist/components.bundle.js
package.json ──────┘                  (exports via global registry)
```

React, React Native, and core libs are treated as externals. Bundles contain only plugin-specific code and plugin-specific dependencies.

## Phase 1 Success Criteria

- [ ] User opens JAIN app → lands on ChatScreen with Jain greeting
- [ ] User asks "find yard sales near me" → Jain invokes `find_yard_sales` tool → core Map renders pins
- [ ] User taps Map tab → sees same pins on full-screen map
- [ ] User says "I want to create a yard sale" → Jain gathers info conversationally OR renders `SaleForm` from the yardsailing plugin bundle → submission creates a real sale in yardsailing's DB
- [ ] Settings screen shows configured LLM provider (read-only)
- [ ] LLM provider abstraction is in place: `LLMProvider` interface defined, `AnthropicProvider` implemented, config reads `LLM_PROVIDER` env var. Adding a second provider in Phase 2 requires zero changes to `chat_service.py`, `tool_executor.py`, or `context_builder.py` — only a new file under `engine/`.
- [ ] Yardsailing backend is unchanged — no code edits in that repo

## Phase 1 Deployment

- **JAIN backend**: Render
- **JAIN mobile**: Expo Go for dev, EAS Build for TestFlight/Play Store beta
- **jain-plugins**: GitHub repo, raw URLs for Phase 1

## Out of Scope (deferred)

- Phase 2: Ollama/OpenAI/private LLM providers, dynamic plugin downloads from CDN, plugin install/uninstall UI, multi-plugin support
- Phase 3: Authentication, agent/skills settings persistence, additional plugins (tiffin-allegro, small-talk)
- Phase 4: Push notifications, camera/vision, voice, route planning

## Open Questions (for implementation plan)

- Exact format for plugin JS bundle exports (global namespace vs. UMD vs. ESM-via-JSC)
- Whether PluginBridge uses React Context or an imperative handle
- SQLite schema for conversations (single table with JSONB-equivalent for messages, or normalized?)
- Whether Phase 1 mobile app targets Expo Go (easier dev) or EAS dev client (more flexibility for native modules)
