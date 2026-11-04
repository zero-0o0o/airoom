"""Validation and safe round-trip helpers for the project artifact registry."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


class RegistryError(ValueError):
    """Raised when a registry is malformed or unsafe to update."""


def _yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def _relative_path(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{field} must be a non-empty project-relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise RegistryError(f"{field} must not be absolute or contain '..': {value!r}")
    if any(part in ("", ".") for part in path.parts):
        raise RegistryError(f"{field} contains an invalid path component: {value!r}")
    return value.rstrip("/")


def validate_registry(data: Any) -> None:
    """Validate supported registry structure while permitting unknown fields."""
    if not isinstance(data, dict):
        raise RegistryError("registry must be a YAML mapping")
    if data.get("version") != 1 or isinstance(data.get("version"), bool):
        raise RegistryError("registry.version must be integer 1")

    artifacts = data.get("artifacts", {})
    tools = data.get("tools", {})
    if not isinstance(artifacts, dict) or not isinstance(tools, dict):
        raise RegistryError("registry.artifacts and registry.tools must be mappings")

    seen_paths: set[str] = set()
    seen_originals: set[str] = set()
    for artifact_id, entry in artifacts.items():
        if not isinstance(artifact_id, str) or not artifact_id.strip() or "/" in artifact_id:
            raise RegistryError(f"invalid artifact id: {artifact_id!r}")
        if not isinstance(entry, dict):
            raise RegistryError(f"artifacts.{artifact_id} must be a mapping")
        for field in ("owner", "path", "type", "management", "status"):
            if field not in entry:
                raise RegistryError(f"artifacts.{artifact_id}.{field} is required")
        if not isinstance(entry["owner"], str) or not entry["owner"].strip():
            raise RegistryError(f"artifacts.{artifact_id}.owner must be a non-empty string")
        path = _relative_path(entry["path"], f"artifacts.{artifact_id}.path")
        management = entry["management"]
        if management not in ("managed", "external"):
            raise RegistryError(f"artifacts.{artifact_id}.management must be managed or external")
        if management == "managed" and not path.startswith("airoom/artifacts/"):
            raise RegistryError(f"managed artifact path must be under airoom/artifacts/: {path!r}")
        if entry["type"] not in ("file", "directory"):
            raise RegistryError(f"artifacts.{artifact_id}.type must be file or directory")
        if entry["status"] not in ("active", "inactive"):
            raise RegistryError(f"artifacts.{artifact_id}.status must be active or inactive")
        if path in seen_paths:
            raise RegistryError(f"duplicate artifact path: {path!r}")
        seen_paths.add(path)
        if "original_path" in entry:
            original = _relative_path(
                entry["original_path"], f"artifacts.{artifact_id}.original_path"
            )
            if original in seen_originals:
                raise RegistryError(f"duplicate original_path: {original!r}")
            seen_originals.add(original)

    for tool_id, entry in tools.items():
        if not isinstance(tool_id, str) or not tool_id.strip() or "/" in tool_id:
            raise RegistryError(f"invalid tool id: {tool_id!r}")
        if not isinstance(entry, dict):
            raise RegistryError(f"tools.{tool_id} must be a mapping")
        if not isinstance(entry.get("name"), str) or not entry["name"].strip():
            raise RegistryError(f"tools.{tool_id}.name must be a non-empty string")
        if entry.get("status") not in ("active", "inactive"):
            raise RegistryError(f"tools.{tool_id}.status must be active or inactive")
        for field in ("config_path", "runtime_path"):
            if field in entry:
                _relative_path(entry[field], f"tools.{tool_id}.{field}")


def parse_registry(text: str) -> Any:
    """Parse YAML with duplicate-key rejection and validate its schema."""
    try:
        data = _yaml().load(text)
    except YAMLError as exc:
        raise RegistryError(f"invalid registry YAML: {exc}") from exc
    validate_registry(data)
    return data


def atomic_write(
    path: Path,
    content: str,
    *,
    expected_text: str | None = None,
    expected_absent: bool = False,
) -> None:
    """Atomically replace a file, optionally aborting if it changed since read."""
    if expected_text is not None and path.read_text(encoding="utf-8") != expected_text:
        raise RegistryError(f"concurrent modification detected: {path}")
    if expected_absent and path.exists():
        raise RegistryError(f"concurrent creation detected: {path}")
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
            raise RegistryError(f"concurrent modification detected: {path}")
        if expected_absent and path.exists():
            raise RegistryError(f"concurrent creation detected: {path}")
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def dump_registry(data: Any) -> str:
    validate_registry(data)
    from io import StringIO

    output = StringIO()
    _yaml().dump(data, output)
    return output.getvalue()
