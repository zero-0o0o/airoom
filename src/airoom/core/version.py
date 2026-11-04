"""AIroom core version file management.

This module provides functions for reading and writing the AIroom version file
(.airoom-version) used by status, init, and upgrade commands.

Extracted from commands/update.py (read_version_file, write_version_file)
and commands/upgrade.py (get_installed_version).
"""

from pathlib import Path

from airoom.core.atomic import atomic_write, AtomicWriteError


def read_version_file(version_path: Path) -> str:
    """Read version from .airoom-version file.

    Args:
        version_path: Path to the .airoom-version file.

    Returns:
        The version string stripped of whitespace, or empty string if file
        doesn't exist or is empty/whitespace-only.
    """
    if version_path.exists():
        return version_path.read_text(encoding="utf-8").strip()
    return ""


def write_version_file(version_path: Path, version: str) -> None:
    """Write version to .airoom-version file atomically.

    Uses atomic_write to ensure the version file is updated safely with
    concurrent modification detection. If the file already contains the
    same version (including newline), no write is performed.

    Args:
        version_path: Path to the .airoom-version file.
        version: The version string to write.

    Raises:
        AtomicWriteError: If concurrent modification or creation is detected.
        OSError: If filesystem operations fail.
    """
    content = version + "\n"
    if version_path.exists():
        previous = version_path.read_text(encoding="utf-8")
        if previous == content:
            return
        atomic_write(version_path, content, expected_text=previous)
    else:
        atomic_write(version_path, content, expected_absent=True)


def get_installed_version() -> str:
    """Get the currently installed AIroom version.

    Returns:
        The version string from the airoom package metadata.
    """
    from airoom import __version__

    return __version__


__all__ = ["read_version_file", "write_version_file", "get_installed_version"]