"""AIroom path safety and filesystem utilities.

This module provides path validation, symlink checks, and directory creation
utilities used by registry, baseline, discovery, organization, and legacy
migration tasks.
"""

from pathlib import Path, PurePosixPath

from airoom.core.project import Project


def validate_path(project: Project, path: str, field: str) -> str:
    """Validate that a path is a safe project-relative path.

    This mirrors the behavior of registry._relative_path but accepts
    a Project instance for context.

    Args:
        project: The Project instance providing the project root.
        path: The path string to validate (must be a raw string, not a Path object,
            as Path normalizes paths before validation can occur).
        field: The field name for error messages.

    Returns:
        The validated path as a POSIX string with trailing slash stripped.

    Raises:
        ValueError: If the path is not a valid project-relative path
            (absolute, contains '..', contains backslashes, empty,
            or contains invalid components like '' or '.').
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f"{field} must be a non-empty project-relative path")

    pure_path = PurePosixPath(path)
    if pure_path.is_absolute() or ".." in pure_path.parts or "\\" in path:
        raise ValueError(f"{field} must not be absolute or contain '..': {path!r}")

    if any(part in ("", ".") for part in pure_path.parts):
        raise ValueError(f"{field} contains an invalid path component: {path!r}")

    return path.rstrip("/")


def check_symlinks(project: Project, path: Path) -> bool:
    """Check if any component of the path within the project is a symlink.

    This performs the symlink traversal check from assert_safe_project_path
    but returns a boolean instead of raising an exception.

    Args:
        project: The Project instance providing the project root.
        path: The path to check for symlinks.

    Returns:
        True if no symlinks are found in the path components within the project,
        False if any component is a symlink.
    """
    root = project.root.resolve()
    try:
        relative = path.relative_to(project.root)
    except ValueError:
        # Path is outside the project - no symlinks to check within project
        return False

    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return False

    return True


def ensure_directory(path: Path, verbose: bool = True) -> bool:
    """Create a directory if it doesn't exist.

    Mirrors the behavior of commands.init.create_directory.

    Args:
        path: The directory path to create.
        verbose: If True, print status messages.

    Returns:
        True if the directory was created, False if it already existed.

    Raises:
        FileExistsError: If the path exists but is not a directory.
        PermissionError: If the directory cannot be created due to permissions.
    """
    if path.exists():
        if path.is_dir():
            if verbose:
                print(f"  Directory already exists: {path}")
            return False
        else:
            raise FileExistsError(f"Path exists but is not a directory: {path}")

    try:
        path.mkdir(parents=True, exist_ok=False)
        if verbose:
            print(f"  Created directory: {path}")
        return True
    except PermissionError as e:
        raise PermissionError(f"Cannot create directory {path}: {e}") from e