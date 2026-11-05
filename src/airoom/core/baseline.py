"""AIroom baseline management for tracking resource hashes.

This module provides the BaselineManager class for reading, writing, and verifying
SHA256 hashes of AIroom-managed resources. Extracted from commands/init.py and
commands/update.py to provide a shared, reusable core module.
"""

import json

from airoom.core.atomic import atomic_write
from airoom.core.project import Project


class BaselineManager:
    """Manages the AIroom resource baseline file (.airoom-baseline.json).

    The baseline stores SHA256 hashes of resource content to detect user
    modifications during updates. It uses atomic writes to ensure integrity.

    Args:
        project: The Project instance providing paths and safety checks.
    """

    def __init__(self, project: Project) -> None:
        """Initialize the BaselineManager with a project.

        Args:
            project: The Project instance.
        """
        self.project = project

    def read(self) -> dict[str, str]:
        """Read the baseline from disk.

        Returns:
            Dictionary mapping resource paths to SHA256 hashes.
            Returns empty dict if baseline file doesn't exist.

        Raises:
            json.JSONDecodeError: If the baseline file contains invalid JSON.
            ValueError: If the baseline is not a dict or contains non-string keys/values.
        """
        baseline_path = self.project.baseline_path
        if not baseline_path.exists():
            return {}

        baseline_text = baseline_path.read_text(encoding="utf-8")
        baseline = json.loads(baseline_text)

        if not isinstance(baseline, dict):
            raise ValueError("baseline must be a dictionary")

        if not all(
            isinstance(key, str) and isinstance(value, str) for key, value in baseline.items()
        ):
            raise ValueError("baseline must map resource paths to SHA-256 hashes")

        return baseline

    def write(self, baseline: dict[str, str]) -> None:
        """Write the baseline to disk atomically.

        Args:
            baseline: Dictionary mapping resource paths to SHA256 hashes.

        Raises:
            AtomicWriteError: If concurrent modification is detected.
            OSError: If filesystem operations fail.
        """
        content = json.dumps(baseline, indent=2, sort_keys=True) + "\n"
        atomic_write(self.project.baseline_path, content)

    def update_hash(self, relpath: str, content: bytes) -> None:
        """Update the hash for a resource in the baseline.

        Args:
            relpath: Relative path of the resource (e.g., "skills/test/SKILL.md").
            content: The resource content to hash.
        """
        baseline = self.read()
        baseline[relpath] = compute_file_hash_from_bytes(content)
        self.write(baseline)

    def remove_hash(self, relpath: str) -> None:
        """Remove a resource hash from the baseline.

        Args:
            relpath: Relative path of the resource to remove.
        """
        baseline = self.read()
        baseline.pop(relpath, None)
        self.write(baseline)

    def verify(self, relpath: str, content: bytes) -> bool:
        """Verify that content matches the stored baseline hash.

        Args:
            relpath: Relative path of the resource.
            content: The resource content to verify.

        Returns:
            True if content matches the baseline hash, False otherwise.
        """
        baseline = self.read()
        stored_hash = baseline.get(relpath)
        if stored_hash is None:
            return False
        return stored_hash == compute_file_hash_from_bytes(content)


def compute_file_hash_from_bytes(content: bytes) -> str:
    """Compute SHA256 hash of bytes content.

    Args:
        content: The bytes to hash.

    Returns:
        Hexadecimal SHA256 digest.
    """
    import hashlib

    return hashlib.sha256(content).hexdigest()
