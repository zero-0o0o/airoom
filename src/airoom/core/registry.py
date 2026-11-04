"""AIroom core registry validation and management.

This module provides validation, parsing, and safe round-trip helpers
for the project artifact registry, plus a RegistryManager class for
high-level registry operations.
"""

from __future__ import annotations

import os
import tempfile
from io import StringIO
from pathlib import Path, PurePosixPath
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from airoom.core.atomic import atomic_write, AtomicWriteError
from airoom.core.project import Project


class RegistryError(ValueError):
    """Raised when a registry is malformed or unsafe to update."""


def _yaml() -> YAML:
    """Return a configured YAML instance for registry I/O."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def _relative_path(value: Any, field: str) -> str:
    """Validate and normalize a project-relative path.

    Args:
        value: The path value to validate.
        field: The field name for error messages.

    Returns:
        The validated path string with trailing slashes stripped.

    Raises:
        RegistryError: If the path is invalid.
    """
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{field} must be a non-empty project-relative path")
    # Use PurePosixPath for consistent cross-platform validation
    posix_path = PurePosixPath(value)
    if posix_path.is_absolute() or ".." in posix_path.parts or "\\" in value:
        raise RegistryError(f"{field} must not be absolute or contain '..': {value!r}")
    if any(part in ("", ".") for part in posix_path.parts):
        raise RegistryError(f"{field} contains an invalid path component: {value!r}")
    return value.rstrip("/")


def validate_registry(data: Any) -> None:
    """Validate supported registry structure while permitting unknown fields.

    Args:
        data: The parsed registry data to validate.

    Raises:
        RegistryError: If the registry structure is invalid.
    """
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
    """Parse YAML with duplicate-key rejection and validate its schema.

    Args:
        text: The YAML text to parse.

    Returns:
        The parsed and validated registry data.

    Raises:
        RegistryError: If the YAML is invalid or fails validation.
    """
    try:
        data = _yaml().load(text)
    except YAMLError as exc:
        raise RegistryError(f"invalid registry YAML: {exc}") from exc
    validate_registry(data)
    return data


def dump_registry(data: Any) -> str:
    """Serialize registry data to YAML string after validation.

    Args:
        data: The registry data to serialize.

    Returns:
        YAML string representation.

    Raises:
        RegistryError: If the data fails validation.
    """
    validate_registry(data)

    output = StringIO()
    _yaml().dump(data, output)
    return output.getvalue()


class RegistryManager:
    """High-level registry management for CLI consumption.

    Wraps the low-level registry functions with project-aware operations
    including atomic writes and validation.
    """

    def __init__(self, project: Project) -> None:
        """Initialize with a Project instance.

        Args:
            project: The AIroom project.
        """
        self.project = project
        self.registry_path = project.registry_path

    def read(self) -> dict:
        """Read and parse the registry file.

        Returns:
            Parsed registry data. Returns default empty registry if file doesn't exist.

        Raises:
            RegistryError: If the registry file exists but is invalid.
        """
        if not self.registry_path.exists():
            return {"version": 1, "artifacts": {}, "tools": {}}
        text = self.registry_path.read_text(encoding="utf-8")
        return parse_registry(text)

    def write(self, data: dict) -> None:
        """Write registry data atomically.

        Args:
            data: The registry data to write. Will be validated before writing.

        Raises:
            RegistryError: If validation fails or atomic write fails.
            AtomicWriteError: If concurrent modification is detected.
        """
        # Validate first
        validate_registry(data)
        content = dump_registry(data)
        # Read current content for concurrent modification detection
        expected_text = None
        if self.registry_path.exists():
            expected_text = self.registry_path.read_text(encoding="utf-8")
        # Use atomic_write from core with expected_text for concurrency detection
        try:
            atomic_write(self.registry_path, content, expected_text=expected_text)
        except AtomicWriteError as exc:
            raise RegistryError(str(exc)) from exc

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the current registry file.

        Returns:
            Tuple of (is_valid, list_of_errors). Empty registry is valid.
        """
        try:
            data = self.read()
            validate_registry(data)
            return True, []
        except RegistryError as exc:
            return False, [str(exc)]

    def add_artifact(self, artifact_id: str, entry: dict) -> None:
        """Add an artifact to the registry.

        Args:
            artifact_id: Unique identifier for the artifact.
            entry: Artifact entry dict with required fields.

        Raises:
            RegistryError: If artifact_id already exists, path conflicts,
                or entry is invalid.
        """
        data = self.read()
        if artifact_id in data["artifacts"]:
            raise RegistryError(f"artifact {artifact_id!r} already exists")
        # Validate by attempting to add to a copy
        data["artifacts"][artifact_id] = entry
        validate_registry(data)
        # If validation passes, write
        self.write(data)

    def remove_artifact(self, artifact_id: str) -> None:
        """Remove an artifact from the registry.

        Args:
            artifact_id: The artifact to remove.

        Raises:
            RegistryError: If artifact_id does not exist.
        """
        data = self.read()
        if artifact_id not in data["artifacts"]:
            raise RegistryError(f"artifact {artifact_id!r} not found")
        del data["artifacts"][artifact_id]
        self.write(data)

    def add_tool(self, tool_id: str, entry: dict) -> None:
        """Add a tool to the registry.

        Args:
            tool_id: Unique identifier for the tool.
            entry: Tool entry dict with required fields.

        Raises:
            RegistryError: If tool_id already exists or entry is invalid.
        """
        data = self.read()
        if tool_id in data["tools"]:
            raise RegistryError(f"tool {tool_id!r} already exists")
        # Validate by attempting to add to a copy
        data["tools"][tool_id] = entry
        validate_registry(data)
        # If validation passes, write
        self.write(data)

    def remove_tool(self, tool_id: str) -> None:
        """Remove a tool from the registry.

        Args:
            tool_id: The tool to remove.

        Raises:
            RegistryError: If tool_id does not exist.
        """
        data = self.read()
        if tool_id not in data["tools"]:
            raise RegistryError(f"tool {tool_id!r} not found")
        del data["tools"][tool_id]
        self.write(data)

