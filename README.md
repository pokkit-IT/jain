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

## Phase 1 status

See `docs/superpowers/plans/2026-04-09-jain-phase-1.md`.
