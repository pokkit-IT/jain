from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class InstalledPlugin(Base):
    """Persistence for runtime-installed external plugins.

    Internal plugins are discovered from the filesystem and never written
    to this table. External plugins are installed via POST /api/plugins/install
    and each installation gets a row here. On startup, the external plugin
    loader reads this table and registers each row from its cached manifest.
    """

    __tablename__ = "installed_plugins"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    manifest_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    service_key: Mapped[str] = mapped_column(String(256), nullable=False)
    bundle_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    installed_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
