"""AIroom core project management.

This module provides the Project class and path safety utilities
extracted from the init and update commands.
"""

from pathlib import Path
from typing import Optional


class Project:
    """Represents an AIroom project with all its standard paths."""

    def __init__(self, root: Path):
        """Initialize a Project with the given root directory.

        Args:
            root: The project root directory. Will be resolved to absolute path.
        """
        self.root = root.resolve()
        self.airoom_dir = self.root / "airoom"
        self.skills_dir = self.airoom_dir / "skills"
        self.artifacts_dir = self.airoom_dir / "artifacts"
        self.registry_path = self.airoom_dir / "registry.yaml"
        self.version_path = self.airoom_dir / ".airoom-version"
        self.baseline_path = self.airoom_dir / ".airoom-baseline.json"
        self.airoom_md_path = self.airoom_dir / "AIROOM.md"
        self.agents_path = self.root / "AGENTS.md"

    def assert_safe(self, path: Path) -> None:
        """Assert that a path is safe within this project.

        Delegates to the standalone assert_safe_project_path function.

        Args:
            path: The path to validate.

        Raises:
            ValueError: If the path is outside the project, traverses a symlink,
                or resolves outside the project.
        """
        assert_safe_project_path(self.root, path)


def find_project_root(start_path: Optional[Path] = None) -> Path:
    """Find the project root directory.

    For init, we use the current working directory unless specified otherwise.

    Args:
        start_path: Optional starting path. If None, uses current working directory.

    Returns:
        The resolved project root path.

    Raises:
        NotADirectoryError: If the path does not exist or is not a directory.
    """
    root = Path.cwd() if start_path is None else Path(start_path)
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise NotADirectoryError(f"Project directory does not exist or is not a directory: {root}")
    return root


def assert_safe_project_path(project_root: Path, path: Path) -> None:
    """Reject paths that escape the project or traverse existing symlinks.

    This function performs three safety checks:
    1. The path must be within the project root (relative_to check)
    2. No component of the path within the project can be a symlink
    3. The fully resolved path must still be within the project root

    Args:
        project_root: The project root directory (must be resolved).
        path: The path to validate.

    Raises:
        ValueError: If the path is outside the project, traverses a symlink,
            or resolves outside the project.
    """
    root = project_root.resolve()
    try:
        relative = path.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"Path is outside the project: {path}") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Refusing to follow symlink in AIroom resource path: {current}")
    if not path.resolve(strict=False).is_relative_to(root):
        raise ValueError(f"Path resolves outside the project: {path}")