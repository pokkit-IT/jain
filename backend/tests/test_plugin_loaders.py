from pathlib import Path

from app.plugins.core.loaders import ExternalPluginLoader, InternalPluginLoader
from app.plugins.core.registry import PluginRegistry

FIXTURES = Path(__file__).parent / "fixtures" / "plugins"


def test_internal_loader_discovers_package_with_register_function(tmp_path):
    # Build a tiny plugin package on disk
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "from app.plugins.core.types import PluginRegistration\n"
        "def register():\n"
        "    return PluginRegistration(name='demo', version='1', type='internal')\n"
    )
    # Marker so the manifest step has something to find
    (pkg / "plugin.json").write_text('{"name":"demo","version":"1","type":"internal",'
                                     '"description":"d","skills":[]}')

    registry = PluginRegistry(plugins_dir=tmp_path)
    loader = InternalPluginLoader(plugins_dir=tmp_path)
    loader.load_all(registry)

    plugin = registry.get_plugin("demo")
    assert plugin is not None
    assert plugin.manifest.name == "demo"
    assert plugin.manifest.type == "internal"


def test_external_loader_reads_existing_filesystem_path(tmp_path):
    """Stage 1 behavior: the external loader still reads a filesystem path.
    Eventually (Stage 4) it will read from the DB."""
    registry = PluginRegistry(plugins_dir=FIXTURES)
    loader = ExternalPluginLoader(plugins_dir=FIXTURES)
    loader.load_all(registry)

    names = [p.name for p in registry.list_plugins()]
    # The exact fixture set varies — at minimum, some external plugin should load.
    assert len(names) >= 1


def test_get_registry_runs_both_loaders(monkeypatch, tmp_path):
    """get_registry() should invoke both InternalPluginLoader.load_all
    and ExternalPluginLoader.load_all on the shared registry."""
    from app import dependencies
    from app.plugins.core.registry import PluginRegistry

    dependencies.reset_registry_for_tests()
    monkeypatch.setattr(dependencies.settings, "PLUGINS_DIR", str(tmp_path))

    internal_called = {"v": False}
    external_called = {"v": False}

    real_internal = dependencies.InternalPluginLoader
    real_external = dependencies.ExternalPluginLoader

    class SpyInternal(real_internal):
        def load_all(self, registry: PluginRegistry) -> None:
            internal_called["v"] = True
            return super().load_all(registry)

    class SpyExternal(real_external):
        def load_all(self, registry: PluginRegistry) -> None:
            external_called["v"] = True
            return super().load_all(registry)

    monkeypatch.setattr(dependencies, "InternalPluginLoader", SpyInternal)
    monkeypatch.setattr(dependencies, "ExternalPluginLoader", SpyExternal)

    dependencies.get_registry()

    assert internal_called["v"]
    assert external_called["v"]

    dependencies.reset_registry_for_tests()


async def test_external_loader_reads_installed_plugins_table():
    import json
    from datetime import datetime
    from uuid import uuid4

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.models.base import Base
    from app.models.installed_plugin import InstalledPlugin
    from app.models.user import User
    from app.plugins.core.loaders import ExternalPluginLoader
    from app.plugins.core.registry import PluginRegistry

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as s:
        user = User(
            id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.flush()

        manifest = {
            "name": "weather",
            "version": "1.0.0",
            "type": "external",
            "description": "Weather lookup",
            "skills": [],
            "api": {"base_url": "https://weather.example.com"},
        }
        s.add(InstalledPlugin(
            name="weather",
            manifest_url="https://weather.example.com/plugin.json",
            manifest_json=json.dumps(manifest),
            service_key="sk-1",
            bundle_path=None,
            installed_at=datetime.utcnow(),
            installed_by=user.id,
        ))
        await s.commit()

    registry = PluginRegistry(plugins_dir="/tmp/unused")
    loader = ExternalPluginLoader(plugins_dir="/tmp/unused")

    async with maker() as s:
        await loader.load_from_db(registry, s)

    plugin = registry.get_plugin("weather")
    assert plugin is not None
    assert plugin.manifest.type == "external"
    assert plugin.manifest.api.base_url == "https://weather.example.com"

    await engine.dispose()
