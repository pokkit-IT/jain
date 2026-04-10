# Importing models here ensures they're registered with Base.metadata
# regardless of which router/service triggers the import chain. Required
# for Base.metadata.create_all() to see all tables at startup.
from .conversation import Conversation, Message  # noqa: F401
from .installed_plugin import InstalledPlugin  # noqa: F401
from .user import User  # noqa: F401
