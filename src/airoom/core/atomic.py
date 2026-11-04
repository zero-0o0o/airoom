"""AIroom atomic file operations and hash computation.

This module provides atomic write utilities and file hash computation
used by registry, baseline, version, and all legacy commands.

Extracted from registry.py (atomic_write) and commands/update.py (compute_file_hash)
to provide a shared, reusable core module.
"""

import hashlib
import os
import tempfile
from pathlib import Path


class AtomicWriteError(Exception):
    """Raised when atomic write detects concurrent modification or creation."""
    pass


def atomic_write(
    path: Path,
    content: str,
    *,
    expected_text: str | None = None,
    expected_absent: bool = False,
) -> None:
    """Atomically replace a file, optionally aborting if it changed since read.

    This function writes to a temporary file in the same directory, fsyncs it,
    preserves the original file's permissions (or uses 0o644 for new files),
    then atomically replaces the target using os.replace.

    If expected_text is provided, the function verifies the file content matches
    both before writing the temp file and after fsync but before the atomic replace.
    If expected_absent is True, the function verifies the file does not exist
    at both check points.

    Args:
        path: The target file path to write.
        content: The content to write.
        expected_text: If provided, the file must contain this exact text at both
            check points, otherwise AtomicWriteError is raised.
        expected_absent: If True, the file must not exist at both check points,
            otherwise AtomicWriteError is raised.

    Raises:
        AtomicWriteError: If concurrent modification or creation is detected.
        OSError: If filesystem operations fail.
    """
    if expected_text is not None and path.read_text(encoding="utf-8") != expected_text:
        raise AtomicWriteError(f"concurrent modification detected: {path}")
    if expected_absent and path.exists():
        raise AtomicWriteError(f"concurrent creation detected: {path}")
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
        ) as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.chmod(tmp_path, mode)
        if expected_text is not None and path.read_text(encoding="utf-8") != expected_text:
            raise AtomicWriteError(f"concurrent modification detected: {path}")
        if expected_absent and path.exists():
            raise AtomicWriteError(f"concurrent creation detected: {path}")
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file.

    Args:
        file_path: The file to hash.

    Returns:
        Hexadecimal SHA256 digest, or empty string if file doesn't exist
        or is not a regular file.
    """
    if not file_path.exists() or not file_path.is_file():
        return ""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()