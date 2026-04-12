# JAIN

AI-first mobile app with a plugin-based skill system. Jain is the primary interface — conversational, LLM-agnostic, and extensible via plugins.

## Structure

- `backend/` — FastAPI app + plugin host + LLM engine
- `mobile/` — React Native (Expo) mobile app
- `docs/superpowers/` — specs and plans

Plugins live in a sibling repo: `../jain-plugins/`.

## Running Phase 1

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY, PLUGINS_DIR
.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

### Mobile

```bash
cd mobile
npm install
npx expo start
```

Press `w` for web, `a` for Android emulator, `i` for iOS simulator.

### Plugins

```bash
cd ../jain-plugins/tools
npm install
npm run validate
npm run build
```

## Plugin system (Phase 3)

JAIN has two plugin tiers:

- **Internal plugins** live under `backend/app/plugins/<name>/` as Python
  packages. They run in JAIN's process, share the SQLite database, and ship
  with a JAIN deployment. First-party code only.
- **External plugins** are standalone HTTP services installed at runtime
  via `POST /api/plugins/install`. JAIN proxies tool calls to them and
  forwards a per-plugin service key plus URL-encoded user identity headers.

**Writing an internal plugin:** see `backend/app/plugins/yardsailing/` as
the reference. Export a `register() -> PluginRegistration` function from
`__init__.py`. Define models in `models.py` (they auto-register on JAIN's
SQLAlchemy `Base`), routes in `routes.py`, tool handlers in `tools.py`.

**Writing an external plugin:** see the separate `jain-plugins` repo and
its `examples/hello-external/`.

**Installing an external plugin (admin only):**

```bash
curl -X POST http://localhost:8000/api/plugins/install \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"manifest_url":"https://my-plugin.example.com/plugin.json","service_key":"<shared-secret>"}'
```

Configure admins via `JAIN_ADMIN_EMAILS=you@example.com` in `backend/.env`.

## Status

- Phase 1: `docs/superpowers/plans/2026-04-09-jain-phase-1.md`
- Phase 2A/2B: Google OAuth + plugin auth pass-through
- Phase 3: `docs/superpowers/specs/2026-04-11-phase-3-plugin-tiers-design.md`
