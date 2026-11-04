"""AIroom core configuration management.

This module provides configuration management for project-level settings,
used by config CLI, logging setup, and other components.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from airoom.core.atomic import atomic_write, AtomicWriteError
from airoom.core.project import Project


@dataclass
class Config:
    """Project configuration.

    Attributes:
        skips: List of skills/features to skip by default.
        defaults: Default values for various settings.
        dry_run: Whether to run in dry-run mode by default.
        verbose: Verbosity level (0=normal, 1=verbose, 2=debug).
    """

    skips: list[str]
    defaults: dict[str, Any]
    dry_run: bool
    verbose: int


def _default_config() -> Config:
    """Return a fresh default Config instance."""
    return Config(
        skips=[],
        defaults={},
        dry_run=False,
        verbose=0,
    )

# Known top-level config keys
TOP_LEVEL_KEYS = {"skips", "defaults", "dry_run", "verbose"}


class ConfigManager:
    """High-level configuration management for CLI consumption.

    Wraps low-level config file operations with project-aware operations
    including atomic writes and defaults merging.
    """

    def __init__(self, project: Project) -> None:
        """Initialize with a Project instance.

        Args:
            project: The AIroom project.
        """
        self.project = project
        self.config_path = project.root / "airoom.config.yaml"

    def _read_raw(self) -> dict[str, Any]:
        """Read and parse the config file as raw dict.

        Returns:
            Raw config data from file, or empty dict if file doesn't exist or is empty.
        """
        if not self.config_path.exists():
            return {}

        text = self.config_path.read_text(encoding="utf-8")
        if not text.strip():
            return {}

        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise yaml.YAMLError(f"invalid config YAML: {exc}") from exc

        if not isinstance(data, dict):
            return {}

        return data

    def read(self) -> Config:
        """Read and parse the config file, merging with defaults.

        Returns:
            Config object with merged values.

        Raises:
            yaml.YAMLError: If the config file exists but contains invalid YAML.
        """
        data = self._read_raw()
        default = _default_config()

        # Merge with defaults
        skips = data.get("skips", default.skips)
        if not isinstance(skips, list):
            skips = default.skips

        defaults = data.get("defaults", default.defaults)
        if not isinstance(defaults, dict):
            defaults = default.defaults

        dry_run = data.get("dry_run", default.dry_run)
        if not isinstance(dry_run, bool):
            dry_run = default.dry_run

        verbose = data.get("verbose", default.verbose)
        if not isinstance(verbose, int):
            verbose = default.verbose

        return Config(
            skips=skips,
            defaults=defaults,
            dry_run=dry_run,
            verbose=verbose,
        )

    def write(self, config: Config) -> None:
        """Write config data atomically.

        Args:
            config: The Config object to write.

        Raises:
            AtomicWriteError: If concurrent modification is detected.
            OSError: If filesystem operations fail.
        """
        # Convert Config to dict for YAML serialization
        data = {
            "skips": config.skips,
            "defaults": config.defaults,
            "dry_run": config.dry_run,
            "verbose": config.verbose,
        }

        content = yaml.dump(data, default_flow_style=False, sort_keys=False)

        # Read current content for concurrent modification detection
        expected_text = None
        if self.config_path.exists():
            expected_text = self.config_path.read_text(encoding="utf-8")

        try:
            atomic_write(self.config_path, content, expected_text=expected_text)
        except AtomicWriteError as exc:
            raise AtomicWriteError(str(exc)) from exc

    def _get_nested(self, data: dict, key: str, default: Any = None) -> Any:
        """Get a nested value using dot notation.

        Args:
            data: The dictionary to search.
            key: Dot-notation key (e.g., "defaults.registry_management").
            default: Default value if key not found.

        Returns:
            The value at the key path, or default.
        """
        parts = key.split(".")
        current = data
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    def _set_nested(self, data: dict, key: str, value: Any) -> None:
        """Set a nested value using dot notation, creating intermediate dicts.

        Args:
            data: The dictionary to modify.
            key: Dot-notation key (e.g., "defaults.registry_management").
            value: The value to set.
        """
        parts = key.split(".")
        current = data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def _unset_nested(self, data: dict, key: str) -> bool:
        """Unset a nested value using dot notation, removing empty parent dicts.

        Args:
            data: The dictionary to modify.
            key: Dot-notation key (e.g., "defaults.registry_management").

        Returns:
            True if the key was found and removed, False otherwise.
        """
        parts = key.split(".")
        current = data
        for part in parts[:-1]:
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]

        if not isinstance(current, dict) or parts[-1] not in current:
            return False

        del current[parts[-1]]

        # Clean up empty parent dicts
        if not current and len(parts) > 1:
            # Need to walk back up and clean
            parent = data
            for part in parts[:-2]:
                if not isinstance(parent, dict) or part not in parent:
                    break
                parent = parent[part]
            if isinstance(parent, dict) and parts[-2] in parent and not parent[parts[-2]]:
                del parent[parts[-2]]

        return True

    def _ensure_top_level_keys(self, data: dict) -> None:
        """Ensure all top-level keys exist with defaults."""
        default = _default_config()
        if "skips" not in data:
            data["skips"] = default.skips
        if "defaults" not in data:
            data["defaults"] = default.defaults
        if "dry_run" not in data:
            data["dry_run"] = default.dry_run
        if "verbose" not in data:
            data["verbose"] = default.verbose

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation.

        Args:
            key: Dot-notation key (e.g., "defaults.registry_management").
            default: Default value if key not found.

        Returns:
            The value at the key path, or default.
        """
        # Read raw data to distinguish between "not in file" and "default value"
        raw_data = self._read_raw()
        if not raw_data:
            return default

        return self._get_nested(raw_data, key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value using dot notation.

        Args:
            key: Dot-notation key (e.g., "defaults.registry_management").
            value: The value to set.
        """
        config = self.read()
        data = {
            "skips": config.skips,
            "defaults": config.defaults,
            "dry_run": config.dry_run,
            "verbose": config.verbose,
        }

        parts = key.split(".")
        # If the first part is not a known top-level key, treat it as under defaults
        if parts[0] not in TOP_LEVEL_KEYS:
            key = "defaults." + key

        self._set_nested(data, key, value)

        new_config = Config(
            skips=data["skips"],
            defaults=data["defaults"],
            dry_run=data["dry_run"],
            verbose=data["verbose"],
        )
        self.write(new_config)

    def unset(self, key: str) -> None:
        """Unset a configuration value using dot notation.

        Args:
            key: Dot-notation key (e.g., "defaults.registry_management").
        """
        config = self.read()
        data = {
            "skips": config.skips,
            "defaults": config.defaults,
            "dry_run": config.dry_run,
            "verbose": config.verbose,
        }

        parts = key.split(".")
        # If the first part is not a known top-level key, treat it as under defaults
        if parts[0] not in TOP_LEVEL_KEYS:
            key = "defaults." + key

        self._unset_nested(data, key)

        # Ensure all top-level keys exist
        self._ensure_top_level_keys(data)

        new_config = Config(
            skips=data["skips"],
            defaults=data["defaults"],
            dry_run=data["dry_run"],
            verbose=data["verbose"],
        )
        self.write(new_config)