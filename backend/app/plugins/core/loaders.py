"""Two plugin loaders: internal (Python packages with register()) and
external (manifest-based HTTP services).

Both share the same `load_all(registry)` entry point. The dispatch
fork between internal and external tool calls happens in `ToolExecutor`,
not here — a loader's only job is to populate the registry.
"""

import importlib.util
import logging
import sys
from pathlib import Path

from .loader import LoadedPlugin, load_plugins_from_dir
from .registry import PluginRegistry
from .schema import PluginManifest
from .types import PluginRegistration

_log = logging.getLogger("jain.plugins.loader")


class InternalPluginLoader:
    """Walks a directory of Python packages, imports each one, and calls
    its `register()` function to obtain a `PluginRegistration`.
    """

    def __init__(self, plugins_dir: Path | str):
        self.plugins_dir = Path(plugins_dir)

    def load_all(self, registry: PluginRegistry) -> None:
        if not self.plugins_dir.exists():
            return

        for child in sorted(self.plugins_dir.iterdir()):
            if not child.is_dir() or not (child / "__init__.py").exists():
                continue
            try:
                self._load_one(child, registry)
            except Exception as e:
                _log.warning(
                    "internal plugin '%s' failed to load: %s: %s",
                    child.name, type(e).__name__, e,
                )

    def _load_one(self, pkg_dir: Path, registry: PluginRegistry) -> None:
        name = pkg_dir.name
        if name.startswith("_") and name != "_hello":
            # Skip private helpers unless it's the Stage-2 test plugin.
            return

        module_name = f"app.plugins.{name}"
        # Prefer normal import (if the package is already on sys.path via
        # app.plugins.<name>). Fall back to spec-based loading for plugins
        # outside app/plugins/ (e.g. a tmp_path used by tests).
        try:
            module = __import__(module_name, fromlist=["register"])
        except ModuleNotFoundError:
            spec = importlib.util.spec_from_file_location(
                module_name, pkg_dir / "__init__.py",
            )
            if spec is None or spec.loader is None:
                raise
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

        if not hasattr(module, "register"):
            _log.info("internal plugin '%s' has no register() — skipping", name)
            return

        registration: PluginRegistration = module.register()

        manifest_path = pkg_dir / "plugin.json"
        if manifest_path.exists():
            manifest = PluginManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8"),
            )
        else:
            manifest = PluginManifest(
                name=registration.name,
                version=registration.version,
                description=f"internal plugin {registration.name}",
                type="internal",
                skills=[],
            )

        loaded = LoadedPlugin(
            manifest=manifest,
            plugin_dir=pkg_dir,
            tools=list(registration.tools),
        )
        # Stash the registration on the LoadedPlugin for the dispatcher.
        loaded.registration = registration  # type: ignore[attr-defined]
        registry.register(loaded)


class ExternalPluginLoader:
    """Stage 2: still reads a filesystem path.
    Stage 4: reads the installed_plugins DB table instead.
    """

    def __init__(self, plugins_dir: Path | str):
        self.plugins_dir = Path(plugins_dir)

    def load_all(self, registry: PluginRegistry) -> None:
        for plugin in load_plugins_from_dir(self.plugins_dir):
            # Only load plugins whose manifest says external (or legacy,
            # where type defaults to external).
            if plugin.manifest.type != "external":
                continue
            # Don't overwrite a plugin that was already registered as internal.
            existing = registry.get_plugin(plugin.manifest.name)
            if existing is not None and existing.manifest.type == "internal":
                continue
            registry.register(plugin)

    async def load_from_db(self, registry: PluginRegistry, db) -> None:
        """Phase 3 Stage 4: load external plugins from the installed_plugins table.

        Each row's manifest_json is trusted because it was validated at install
        time. If a row fails to parse, skip it and log a warning.
        """
        from pathlib import Path as _Path
        from sqlalchemy import select

        from app.models.installed_plugin import InstalledPlugin

        result = await db.execute(select(InstalledPlugin))
        for row in result.scalars().all():
            try:
                manifest = PluginManifest.model_validate_json(row.manifest_json)
            except Exception as e:
                _log.warning(
                    "installed plugin '%s' has invalid manifest_json: %s", row.name, e,
                )
                continue

            plugin_dir = (
                _Path(row.bundle_path).parent
                if row.bundle_path
                else _Path(".")
            )
            loaded = LoadedPlugin(
                manifest=manifest,
                plugin_dir=plugin_dir,
            )
            # Stash the per-plugin service key on the loaded plugin so the
            # tool executor can forward it in service-to-service calls.
            loaded.service_key = row.service_key  # type: ignore[attr-defined]
            registry.register(loaded)
