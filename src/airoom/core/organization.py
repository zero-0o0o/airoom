"""AIroom core artifact organization engine.

This module implements the artifact-organization skill logic programmatically,
handling relocation planning, safe filesystem moves, registry updates,
and post-verification with rollback capability.
"""

from __future__ import annotations

import errno
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from airoom.core.atomic import atomic_write
from airoom.core.discovery import DiscoveryReport
from airoom.core.project import Project
from airoom.core.registry import RegistryManager


@dataclass
class RelocationAction:
    """Represents a single artifact relocation action.

    Attributes:
        source: Current path of the artifact.
        target: Target path under airoom/artifacts/ (or same as source for external).
        artifact_id: Unique identifier for the artifact in the registry.
        tool_id: The tool that owns this artifact (e.g., "Graphify", "Superpowers").
        management: "managed" if relocating under airoom/artifacts/, "external" if staying in place.
        env_var: Environment variable to configure tool output path, if applicable.
    """

    source: Path
    target: Path
    artifact_id: str
    tool_id: str
    management: Literal["managed", "external"]
    env_var: str | None


@dataclass
class RelocationPlan:
    """Complete relocation plan generated from a discovery report.

    Attributes:
        actions: List of relocation actions to execute.
        tool_configs: Mapping of tool_id to configuration dict with output_path and output_env.
    """

    actions: list[RelocationAction]
    tool_configs: dict[str, dict]


class OrganizationEngine:
    """Engine for organizing AI artifacts under airoom/artifacts/.

    Implements the artifact-organization skill workflow:
    1. Plan relocations based on discovery report and decision matrix
    2. Pre-flight safety checks
    3. Execute moves (atomic rename or copy-verify-remove fallback)
    4. Update tool configurations and register artifacts
    5. Post-verification with rollback on failure
    """

    # Tool-specific configuration for well-known tools
    TOOL_CONFIGS = {
        "Graphify": {
            "canonical_path": "airoom/artifacts/graphify-out",
            "env_var": "GRAPHIFY_OUT",
            "management": "managed",
        },
        "Superpowers": {
            "canonical_path": "airoom/artifacts/docs/superpowers",
            "env_var": None,  # Configured via skills/project config
            "management": "managed",
        },
        "Claude": {
            "canonical_path": ".claude",
            "env_var": None,
            "management": "external",
        },
        "Aider": {
            "canonical_path": ".aider",
            "env_var": None,
            "management": "external",
        },
        "Cursor": {
            "canonical_path": ".cursor",
            "env_var": None,
            "management": "external",
        },
        "Brainstorm": {
            "canonical_path": "airoom/artifacts/brainstorm",
            "env_var": None,
            "management": "managed",
        },
        "LLM Plans": {
            "canonical_path": "airoom/artifacts/llm-plans",
            "env_var": None,
            "management": "managed",
        },
        "LLM Specs": {
            "canonical_path": "airoom/artifacts/llm-specs",
            "env_var": None,
            "management": "managed",
        },
        "AI Plans": {
            "canonical_path": "airoom/artifacts/ai-plans",
            "env_var": None,
            "management": "managed",
        },
        "AI Specs": {
            "canonical_path": "airoom/artifacts/ai-specs",
            "env_var": None,
            "management": "managed",
        },
    }

    def __init__(
        self,
        project: Project,
        registry: RegistryManager,
    ) -> None:
        """Initialize the OrganizationEngine.

        Args:
            project: The AIroom project.
            registry: The registry manager.
        """
        self.project = project
        self.registry = registry

    def plan(self, discovery_report: DiscoveryReport) -> RelocationPlan:
        """Generate a relocation plan from a discovery report.

        Args:
            discovery_report: Report from DiscoveryEngine.scan().

        Returns:
            RelocationPlan with actions and tool configurations.
        """
        actions: list[RelocationAction] = []
        tool_configs: dict[str, dict] = {}
        used_artifact_ids: set[str] = set()

        # Read existing artifact IDs from registry to avoid collisions
        registry_data = self.registry.read()
        for existing_id in registry_data.get("artifacts", {}).keys():
            used_artifact_ids.add(existing_id)

        for candidate in discovery_report.unregistered_candidates:
            tool_config = self.TOOL_CONFIGS.get(candidate.likely_owner, {})
            management = tool_config.get("management", candidate.recommended_mode)
            canonical_path = tool_config.get("canonical_path")
            env_var = tool_config.get("env_var")

            # Determine artifact_id from path (sanitized), avoiding collisions
            artifact_id = self._sanitize_artifact_id(candidate.path, used_artifact_ids)
            used_artifact_ids.add(artifact_id)

            if management == "managed" and canonical_path:
                # For managed artifacts, target is under airoom/artifacts/
                # Use the canonical path but preserve the artifact name if needed
                target_rel = canonical_path
                # If multiple artifacts of same tool type, append unique suffix
                base_target = self.project.root / target_rel
                target = self._get_unique_target(base_target, artifact_id)
                target_rel = target.relative_to(self.project.root).as_posix()

                action = RelocationAction(
                    source=self.project.root / candidate.path,
                    target=target,
                    artifact_id=artifact_id,
                    tool_id=candidate.likely_owner,
                    management="managed",
                    env_var=env_var,
                )
                actions.append(action)

                # Track tool config
                if candidate.likely_owner not in tool_configs:
                    tool_configs[candidate.likely_owner] = {
                        "output_path": target_rel,
                        "output_env": env_var,
                    }
            else:
                # External management - stays in place
                source = self.project.root / candidate.path
                action = RelocationAction(
                    source=source,
                    target=source,  # Same path for external
                    artifact_id=artifact_id,
                    tool_id=candidate.likely_owner,
                    management="external",
                    env_var=None,
                )
                actions.append(action)

                # Track tool config for external tools
                if candidate.likely_owner not in tool_configs:
                    tool_configs[candidate.likely_owner] = {
                        "output_path": candidate.path,
                        "output_env": None,
                    }

        return RelocationPlan(actions=actions, tool_configs=tool_configs)

    def execute(self, plan: RelocationPlan, dry_run: bool = False) -> tuple[bool, list[str]]:
        """Execute a relocation plan.

        Args:
            plan: The relocation plan to execute.
            dry_run: If True, only simulate the actions without modifying filesystem.

        Returns:
            Tuple of (success: bool, messages: list[str]).
        """
        messages: list[str] = []
        overall_success = True

        for action in plan.actions:
            if dry_run:
                if action.management == "managed":
                    messages.append(
                        f"[DRY RUN] Would move {action.source.relative_to(self.project.root)} "
                        f"→ {action.target.relative_to(self.project.root)} "
                        f"({action.management}, tool: {action.tool_id})"
                    )
                else:
                    messages.append(
                        f"[DRY RUN] Would register {action.source.relative_to(self.project.root)} "
                        f"as external (tool: {action.tool_id})"
                    )
                continue

            # Pre-flight checks
            ok, msg = self._preflight_checks(action)
            if not ok:
                messages.append(f"✗ Pre-flight failed for {action.artifact_id}: {msg}")
                overall_success = False
                continue

            # Execute move for managed artifacts
            if action.management == "managed":
                ok = self._move_artifact(action)
                if not ok:
                    messages.append(f"✗ Failed to move {action.artifact_id}")
                    overall_success = False
                    continue
                messages.append(
                    f"✓ Moved {action.source.relative_to(self.project.root)} "
                    f"→ {action.target.relative_to(self.project.root)}"
                )
            else:
                messages.append(
                    f"✓ Registered {action.source.relative_to(self.project.root)} as external"
                )

            # Post-verification with rollback
            ok = self._verify_and_rollback(action)
            if not ok:
                messages.append(f"✗ Verification failed for {action.artifact_id}, rolled back")
                overall_success = False
                continue
            messages.append(f"✓ Verified {action.artifact_id}")

            # Update tool configuration in registry (only after successful verification)
            tool_config = plan.tool_configs.get(action.tool_id)
            if tool_config:
                self._update_tool_config(action.tool_id, tool_config)

            # Register artifact in registry (only after successful verification)
            self._register_artifact(action)
            messages.append(f"✓ Registered artifact '{action.artifact_id}' in registry")

        # Update .gitignore if needed (only in real execution)
        if not dry_run:
            self._update_gitignore(plan)
            messages.append("✓ Updated .gitignore")

        return overall_success, messages

    def _preflight_checks(self, action: RelocationAction) -> tuple[bool, str]:
        """Perform pre-flight safety checks before relocation.

        Args:
            action: The relocation action to check.

        Returns:
            Tuple of (passed: bool, message: str).
        """
        # 1. Verify source exists and is inside project root
        if not action.source.exists():
            return False, f"Source does not exist: {action.source}"

        try:
            self.project.assert_safe(action.source)
        except ValueError as e:
            return False, f"Source path unsafe: {e}"

        # 2. Confirm neither source nor any parent is a symlink
        # (assert_safe already checks this for source, but check target parents too)
        try:
            self.project.assert_safe(action.target)
        except ValueError as e:
            return False, f"Target path unsafe: {e}"

        # 3. Verify target canonical path starts with airoom/artifacts/ (for managed)
        if action.management == "managed":
            try:
                target_rel = action.target.relative_to(self.project.root).as_posix()
                if not target_rel.startswith("airoom/artifacts/"):
                    return False, f"Managed target must be under airoom/artifacts/: {target_rel}"
            except ValueError:
                return False, f"Target is outside project root: {action.target}"

        # 4. Verify target does not already exist (skip for external, where source == target)
        if action.management == "managed" and action.target.exists():
            return False, f"Target already exists: {action.target}"

        # 5. Parent directories will be created by _move_artifact
        # No check needed here

        return True, ""

    def _move_artifact(self, action: RelocationAction) -> bool:
        """Move artifact to target location.

        Uses atomic rename on same filesystem, copy-verify-remove fallback for cross-filesystem.

        Args:
            action: The relocation action to execute.

        Returns:
            True if move succeeded, False otherwise.
        """
        # Ensure parent directories exist
        action.target.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Try atomic rename first (same filesystem)
            os.replace(action.source, action.target)
            return True
        except OSError as e:
            if e.errno == errno.EXDEV:
                # Cross-filesystem: copy, verify, remove
                return self._copy_verify_remove(action.source, action.target)
            else:
                # Other error
                return False
        except Exception:
            return False

    def _copy_verify_remove(self, source: Path, target: Path) -> bool:
        """Copy-verify-remove fallback for cross-filesystem moves.

        Args:
            source: Source path.
            target: Target path.

        Returns:
            True if successful, False otherwise (source restored on failure).
        """
        try:
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)

            # Verify copy: compare file counts and sizes
            if not self._verify_copy(source, target):
                # Verification failed, clean up target
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                else:
                    target.unlink(missing_ok=True)
                return False

            # Remove source
            if source.is_dir():
                shutil.rmtree(source)
            else:
                source.unlink()

            return True
        except Exception:
            # Clean up target on any error
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                else:
                    target.unlink(missing_ok=True)
            return False

    def _verify_copy(self, source: Path, target: Path) -> bool:
        """Verify that copy matches source.

        Args:
            source: Original source path.
            target: Copied target path.

        Returns:
            True if verification passes.
        """
        if source.is_file() and target.is_file():
            return source.stat().st_size == target.stat().st_size

        if source.is_dir() and target.is_dir():
            # Count files and total size
            source_files = list(source.rglob("*"))
            target_files = list(target.rglob("*"))
            if len(source_files) != len(target_files):
                return False

            source_size = sum(f.stat().st_size for f in source_files if f.is_file())
            target_size = sum(f.stat().st_size for f in target_files if f.is_file())
            return source_size == target_size

        return False

    def _update_tool_config(self, tool_id: str, config: dict) -> None:
        """Update tool configuration in registry.

        Args:
            tool_id: The tool identifier.
            config: Configuration dict with output_path and output_env.
        """
        data = self.registry.read()
        tools = data.setdefault("tools", {})

        tool_config = {
            "name": tool_id,
            "status": "active",
            "config_path": config.get("output_path"),
        }
        if config.get("output_env"):
            tool_config["config"] = {"output_env": config["output_env"]}

        if tool_id in tools:
            # Update existing, preserving any other fields
            tools[tool_id].update(tool_config)
        else:
            # Add new
            tools[tool_id] = tool_config

        self.registry.write(data)

    def _register_artifact(self, action: RelocationAction) -> None:
        """Register artifact in registry.

        Args:
            action: The relocation action that was executed.
        """
        data = self.registry.read()
        artifacts = data.setdefault("artifacts", {})

        # Determine type
        artifact_type = "directory" if action.target.is_dir() else "file"

        # Build artifact entry
        entry = {
            "owner": action.tool_id,
            "path": action.target.relative_to(self.project.root).as_posix(),
            "type": artifact_type,
            "management": action.management,
            "status": "active",
        }

        if action.management == "managed":
            # Record original path for managed artifacts
            entry["original_path"] = action.source.relative_to(self.project.root).as_posix()

        artifacts[action.artifact_id] = entry
        self.registry.write(data)

    def _verify_and_rollback(self, action: RelocationAction) -> bool:
        """Verify relocated artifact is accessible, rollback on failure.

        Args:
            action: The relocation action to verify.

        Returns:
            True if verification passes, False if rolled back.
        """
        # Basic verification: target exists and is accessible
        if not action.target.exists():
            # Rollback: restore source from target if target was moved
            # (In practice, target shouldn't exist if verification fails here)
            return False

        if action.management == "managed":
            # Verify we can read the target
            try:
                if action.target.is_dir():
                    list(action.target.iterdir())
                else:
                    action.target.read_text(encoding="utf-8")
            except Exception:
                # Rollback: move back to source
                self._rollback_move(action)
                return False

        return True

    def _rollback_move(self, action: RelocationAction) -> None:
        """Rollback a move by restoring source from target.

        Args:
            action: The action to rollback.
        """
        try:
            if action.target.exists():
                # Ensure source parent exists
                action.source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(action.target, action.source)
        except Exception:
            # Best effort rollback
            pass

    def _update_gitignore(self, plan: RelocationPlan) -> None:
        """Update .gitignore for managed artifact paths.

        Args:
            plan: The relocation plan.
        """
        gitignore_path = self.project.root / ".gitignore"
        entries_to_add = set()

        for action in plan.actions:
            if action.management == "managed":
                # Add the canonical artifact path
                rel_path = action.target.relative_to(self.project.root).as_posix()
                entries_to_add.add(rel_path)

        if not entries_to_add:
            return

        # Read existing .gitignore once
        content = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
        existing_entries = set()
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                existing_entries.add(line)

        # Add new entries
        new_entries = entries_to_add - existing_entries
        if not new_entries:
            return

        # Write updated .gitignore
        lines = content.splitlines()

        # Ensure blank line before new entries
        if lines and lines[-1].strip():
            lines.append("")

        lines.append("# AIroom managed artifacts")
        for entry in sorted(new_entries):
            lines.append(entry)

        content = "\n".join(lines) + "\n"
        atomic_write(gitignore_path, content)

    def _sanitize_artifact_id(self, path: str, existing_ids: set[str] | None = None) -> str:
        """Sanitize a path into a valid artifact ID, avoiding collisions.

        Args:
            path: Relative path.
            existing_ids: Set of existing artifact IDs to avoid collisions.

        Returns:
            Sanitized artifact ID.
        """
        # Replace path separators and special chars
        artifact_id = path.replace("/", "-").replace(".", "-").replace("_", "-")
        # Remove duplicate dashes
        while "--" in artifact_id:
            artifact_id = artifact_id.replace("--", "-")
        # Strip leading/trailing dashes
        artifact_id = artifact_id.strip("-")
        # Ensure it's not empty
        if not artifact_id:
            artifact_id = "artifact"

        # Disambiguate if collision with existing IDs
        if existing_ids is not None:
            original_id = artifact_id
            counter = 1
            while artifact_id in existing_ids:
                artifact_id = f"{original_id}-{counter}"
                counter += 1

        return artifact_id

    def _get_unique_target(self, base_target: Path, artifact_id: str) -> Path:
        """Get a unique target path, appending numeric suffix if needed.

        Args:
            base_target: Base target path.
            artifact_id: Artifact identifier (unused, kept for compatibility).

        Returns:
            Unique target path.
        """
        if not base_target.exists():
            return base_target

        parent = base_target.parent
        name = base_target.name
        counter = 1
        candidate = parent / f"{name}-{counter}"
        while candidate.exists():
            counter += 1
            candidate = parent / f"{name}-{counter}"

        return candidate
