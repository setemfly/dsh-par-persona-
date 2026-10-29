"""Governed versioned updates (no runtime code self-modification)."""

from par.updates.manager import (
    UpdateError,
    UpdateManager,
    Version,
    VersionStore,
    current_persona_path,
    validate_persona_file,
)

__all__ = [
    "UpdateError",
    "UpdateManager",
    "Version",
    "VersionStore",
    "current_persona_path",
    "validate_persona_file",
]
