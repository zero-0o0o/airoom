"""AIroom core modules - shared infrastructure and coordination layer for AI agents and tools.

This package aggregates all public exports from core modules for easy importing.
"""

# Project management
from airoom.core.project import (
    Project,
    find_project_root,
    assert_safe_project_path,
)

# Path safety and filesystem utilities
from airoom.core.safety import (
    validate_path,
    check_symlinks,
    ensure_directory,
)

# Atomic file operations and hash computation
from airoom.core.atomic import (
    AtomicWriteError,
    atomic_write,
    compute_file_hash,
)

# Registry validation and management
from airoom.core.registry import (
    RegistryError,
    _yaml,
    _relative_path,
    validate_registry,
    parse_registry,
    dump_registry,
    RegistryManager,
)

# Baseline management
from airoom.core.baseline import (
    BaselineManager,
    compute_file_hash_from_bytes,
)

# Version file management
from airoom.core.version import (
    read_version_file,
    write_version_file,
    get_installed_version,
)

# Artifact discovery engine
from airoom.core.discovery import (
    DiscoveredArtifact,
    RegistryDiscrepancy,
    DiscoveryReport,
    DiscoveryEngine,
)

# Artifact organization engine
from airoom.core.organization import (
    RelocationAction,
    RelocationPlan,
    OrganizationEngine,
)

# Packaged resource access
from airoom.core.resources import (
    ResourceManager,
)

# Configuration management
from airoom.core.config import (
    Config,
    ConfigManager,
    _default_config,
    TOP_LEVEL_KEYS,
)


__all__ = [
    # Project
    "Project",
    "find_project_root",
    "assert_safe_project_path",
    # Safety
    "validate_path",
    "check_symlinks",
    "ensure_directory",
    # Atomic
    "AtomicWriteError",
    "atomic_write",
    "compute_file_hash",
    # Registry
    "RegistryError",
    "_yaml",
    "_relative_path",
    "validate_registry",
    "parse_registry",
    "dump_registry",
    "RegistryManager",
    # Baseline
    "BaselineManager",
    "compute_file_hash_from_bytes",
    # Version
    "read_version_file",
    "write_version_file",
    "get_installed_version",
    # Discovery
    "DiscoveredArtifact",
    "RegistryDiscrepancy",
    "DiscoveryReport",
    "DiscoveryEngine",
    # Organization
    "RelocationAction",
    "RelocationPlan",
    "OrganizationEngine",
    # Resources
    "ResourceManager",
    # Config
    "Config",
    "ConfigManager",
    "_default_config",
    "TOP_LEVEL_KEYS",
]