from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers import auth, chat, health, plugins
from .routers import settings as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Phase 3 Stage 4: load runtime-installed external plugins from the DB.
    from .database import async_session
    from .dependencies import get_registry
    from .plugins.core.loaders import ExternalPluginLoader

    registry = get_registry()
    loader = ExternalPluginLoader(plugins_dir=settings.PLUGINS_DIR)
    async with async_session() as db:
        await loader.load_from_db(registry, db)

    yield


def create_app() -> FastAPI:
    app = FastAPI(title="JAIN API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(plugins.router)
    app.include_router(settings_router.router)
    app.include_router(auth.router)

    # Phase 3: mount internal plugin routers. get_registry() loads both
    # internal and external plugins (external are HTTP services with no
    # router — skip them). Each internal plugin's router has its own
    # /api/plugins/<name>/... prefix baked in.
    from .dependencies import get_registry
    registry = get_registry()
    for plugin in registry.list_plugins():
        if plugin.type != "internal":
            continue
        loaded = registry.get_plugin(plugin.name)
        registration = getattr(loaded, "registration", None)
        if registration is None or registration.router is None:
            continue
        app.include_router(registration.router)

    return app


app = create_app()
