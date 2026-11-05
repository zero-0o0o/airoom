"""Validation and safe round-trip helpers for the project artifact registry.

This module re-exports all functionality from airoom.core.registry
for backward compatibility.
"""

from __future__ import annotations

from pathlib import Path

from airoom.core.atomic import atomic_write as _core_atomic_write, AtomicWriteError
from airoom.core.registry import (
    RegistryError,
    _yaml,
    _relative_path,
    validate_registry,
    parse_registry,
    dump_registry,
)


def atomic_write(
    path: Path,
    content: str,
    *,
    expected_text: str | None = None,
    expected_absent: bool = False,
) -> None:
    """Atomically replace a file, optionally aborting if it changed since read.

    This is a backward-compatible wrapper that converts AtomicWriteError to RegistryError.
    """
    try:
        _core_atomic_write(
            path, content, expected_text=expected_text, expected_absent=expected_absent
        )
    except AtomicWriteError as exc:
        raise RegistryError(str(exc)) from exc


__all__ = [
    "RegistryError",
    "_yaml",
    "_relative_path",
    "validate_registry",
    "parse_registry",
    "atomic_write",
    "dump_registry",
]
