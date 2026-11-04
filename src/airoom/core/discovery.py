"""AIroom core artifact discovery engine.

This module implements the artifact-discovery skill logic programmatically,
detecting AI-generated files and directories, checking registry discrepancies,
and evaluating relocation feasibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ruamel.yaml import YAML

from airoom.core.project import Project
from airoom.core.registry import RegistryManager


def _yaml() -> YAML:
    """Return a configured YAML instance for registry I/O."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


@dataclass
class DiscoveredArtifact:
    """Represents a discovered AI artifact candidate."""
    path: str
    likely_owner: str
    evidence: list[str]
    type: Literal["file", "directory"]
    recommended_mode: Literal["managed", "external"]
    relocation_feasibility: str


@dataclass
class RegistryDiscrepancy:
    """Represents a discrepancy between registry and filesystem."""
    kind: Literal["missing_path", "unregistered_candidate", "type_mismatch", "placement_mismatch", "duplicate_claim"]
    details: str


@dataclass
class DiscoveryReport:
    """Complete discovery scan report."""
    inspected_locations: list[str]
    registered_artifacts: list[tuple[str, bool]]  # (id, exists)
    unregistered_candidates: list[DiscoveredArtifact]
    discrepancies: list[RegistryDiscrepancy]
    recommendations: list[str]


class DiscoveryEngine:
    """Engine for discovering AI artifacts and detecting registry discrepancies."""

    # Known AI tool signatures for candidate detection
    GRAPHIFY_PATTERNS = [
        ("graphify-out", "directory"),
        (".graphify_", "file"),
        (".graphify", "directory"),
    ]

    SUPERPOWERS_PATTERNS = [
        ("docs/superpowers", "directory"),
        (".superpowers", "directory"),
    ]

    SCRATCHPAD_PATTERNS = [
        (".claude", "directory", "Claude"),
        (".aider", "directory", "Aider"),
        (".cursor", "directory", "Cursor"),
        ("brainstorm", "file", "Brainstorm"),
        ("brainstorm.", "file", "Brainstorm"),  # Matches brainstorm.log, brainstorm.txt, etc.
        ("llm-plans", "directory", "LLM Plans"),
        ("llm-specs", "directory", "LLM Specs"),
        ("ai-plans", "directory", "AI Plans"),
        ("ai-specs", "directory", "AI Specs"),
    ]

    # Paths to ignore (not AI artifacts)
    IGNORE_PATTERNS = {
        "node_modules",
        ".venv",
        "venv",
        "vendor",
        "build",
        "dist",
        "target",
        ".cache",
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "htmlcov",
        ".coverage",
    }

    # Source code patterns to ignore
    SOURCE_EXTENSIONS = {
        ".py", ".rs", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".kt",
        ".c", ".cpp", ".cc", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
        ".scala", ".clj", ".hs", ".ml", ".fs", ".vb", ".dart", ".lua",
    }

    # Config files that are project files, not AI artifacts
    PROJECT_CONFIG_FILES = {
        "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "Cargo.toml", "Cargo.lock",
        "pyproject.toml", "requirements.txt", "setup.py", "setup.cfg",
        "pom.xml", "build.gradle", "build.gradle.kts",
        "go.mod", "go.sum",
        "composer.json", "composer.lock",
        "Gemfile", "Gemfile.lock",
        "Makefile", "CMakeLists.txt",
        "tsconfig.json", "jsconfig.json",
        ".eslintrc", ".eslintrc.json", ".eslintrc.js",
        ".prettierrc", ".prettierrc.json",
        "docker-compose.yml", "docker-compose.yaml", "Dockerfile",
        ".gitignore", ".dockerignore",
    }

    def __init__(self, project: Project, registry: RegistryManager) -> None:
        """Initialize the discovery engine.

        Args:
            project: The AIroom project.
            registry: The registry manager.
        """
        self.project = project
        self.registry = registry

    def _read_raw_registry(self) -> dict[str, Any]:
        """Read registry without validation for discrepancy detection.

        Returns:
            Raw registry data, or default empty registry if file doesn't exist or is invalid.
        """
        if not self.registry.registry_path.exists():
            return {"version": 1, "artifacts": {}, "tools": {}}
        try:
            text = self.registry.registry_path.read_text(encoding="utf-8")
            return _yaml().load(text) or {"version": 1, "artifacts": {}, "tools": {}}
        except Exception:
            return {"version": 1, "artifacts": {}, "tools": {}}

    def scan(self) -> DiscoveryReport:
        """Perform a full discovery scan.

        Returns:
            DiscoveryReport with all findings.
        """
        inspected_locations = self._get_inspected_locations()
        registered_artifacts = self._check_registered_artifacts()
        unregistered_candidates = self._find_candidates()
        report = DiscoveryReport(
            inspected_locations=inspected_locations,
            registered_artifacts=registered_artifacts,
            unregistered_candidates=unregistered_candidates,
            discrepancies=[],
            recommendations=[],
        )
        self._check_registry_discrepancies(
            report, registered_artifacts, unregistered_candidates
        )
        report.recommendations = self._generate_recommendations(
            unregistered_candidates, report.discrepancies
        )
        return report

    def _get_inspected_locations(self) -> list[str]:
        """Get list of locations that were inspected."""
        locations = [
            ".",  # Project root
            "airoom/artifacts",
        ]
        # Add known AI tool locations that we check
        for pattern, _ in self.GRAPHIFY_PATTERNS:
            if not pattern.startswith("."):
                locations.append(pattern)
        for pattern, _ in self.SUPERPOWERS_PATTERNS:
            if not pattern.startswith("."):
                locations.append(pattern)
        for pattern, _, _ in self.SCRATCHPAD_PATTERNS:
            if not pattern.startswith("."):
                locations.append(pattern)
        return locations

    def _check_registered_artifacts(self) -> list[tuple[str, bool]]:
        """Check existence of all registered artifacts.

        Returns:
            List of (artifact_id, exists) tuples.
        """
        data = self._read_raw_registry()
        results = []
        for artifact_id, entry in data.get("artifacts", {}).items():
            path = self.project.root / entry["path"]
            exists = path.exists()
            results.append((artifact_id, exists))
        return results

    def _find_candidates(self) -> list[DiscoveredArtifact]:
        """Find unregistered AI artifact candidates in the project.

        Returns:
            List of DiscoveredArtifact candidates.
        """
        candidates = []

        # Known locations to scan (root + known subdirectories, max depth 2)
        scan_roots = [
            self.project.root,
            self.project.root / "docs",
            self.project.root / ".github",
        ]

        for scan_root in scan_roots:
            if not scan_root.exists() or not scan_root.is_dir():
                continue
            # Use rglob with depth limit to avoid deep recursion
            for entry in self._rglob_depth(scan_root, max_depth=2):
                # Skip ignored directories (check parent directories too)
                if self._is_ignored(entry):
                    continue
                if entry.is_symlink():
                    # Treat symlinks as opaque - report but don't follow
                    continue

                # Get relative path from project root for path-based pattern matching
                try:
                    rel_path = entry.relative_to(self.project.root).as_posix()
                except ValueError:
                    # Entry is not under project root (shouldn't happen)
                    continue

                # Check Graphify patterns
                for pattern, expected_type in self.GRAPHIFY_PATTERNS:
                    if self._matches_pattern(entry.name, rel_path, pattern):
                        if self._type_matches(entry, expected_type):
                            candidates.append(self._create_candidate(
                                entry, "Graphify", [f"Matches Graphify pattern: {pattern}"],
                                expected_type
                            ))

                # Check Superpowers patterns
                for pattern, expected_type in self.SUPERPOWERS_PATTERNS:
                    if self._matches_pattern(entry.name, rel_path, pattern):
                        if self._type_matches(entry, expected_type):
                            candidates.append(self._create_candidate(
                                entry, "Superpowers", [f"Matches Superpowers pattern: {pattern}"],
                                expected_type
                            ))

                # Check scratchpad patterns
                for pattern, expected_type, owner in self.SCRATCHPAD_PATTERNS:
                    if self._matches_pattern(entry.name, rel_path, pattern):
                        if self._type_matches(entry, expected_type):
                            candidates.append(self._create_candidate(
                                entry, owner, [f"Matches {owner} pattern: {pattern}"],
                                expected_type
                            ))

        # Filter out candidates that are already registered
        registered_paths = self._get_registered_paths()
        candidates = [c for c in candidates if c.path not in registered_paths]

        return candidates

    def _rglob_depth(self, root: Path, max_depth: int):
        """Yield files/dirs under root up to max_depth (0=root only, 1=immediate children, etc.)."""
        if max_depth < 0:
            return
        yield root
        if max_depth == 0:
            return
        try:
            for entry in root.iterdir():
                if entry.is_dir() and not entry.is_symlink():
                    yield from self._rglob_depth(entry, max_depth - 1)
                else:
                    yield entry
        except (PermissionError, OSError):
            pass

    def _is_ignored(self, path: Path) -> bool:
        """Check if path or any parent is in IGNORE_PATTERNS."""
        for part in path.parts:
            if part in self.IGNORE_PATTERNS:
                return True
        return False

    def _matches_pattern(self, name: str, rel_path: str, pattern: str) -> bool:
        """Check if a name or relative path matches a pattern (exact or prefix)."""
        # If pattern contains path separator, match against relative path
        if "/" in pattern:
            if pattern.endswith("_"):
                return rel_path.startswith(pattern)
            if pattern.endswith("."):
                return rel_path.startswith(pattern)
            return rel_path == pattern
        # Otherwise match against name only
        if pattern.endswith("_"):
            return name.startswith(pattern)
        if pattern.endswith("."):
            return name.startswith(pattern)
        return name == pattern

    def _type_matches(self, path: Path, expected_type: str) -> bool:
        """Check if path type matches expected type."""
        if expected_type == "directory":
            return path.is_dir()
        return path.is_file()

    def _create_candidate(
        self,
        path: Path,
        owner: str,
        evidence: list[str],
        expected_type: Literal["file", "directory"]
    ) -> DiscoveredArtifact:
        """Create a DiscoveredArtifact from a discovered path."""
        rel_path = path.relative_to(self.project.root).as_posix()
        feasibility, recommended_mode = self._evaluate_relocation_feasibility(owner, path)

        return DiscoveredArtifact(
            path=rel_path,
            likely_owner=owner,
            evidence=evidence,
            type=expected_type,
            recommended_mode=recommended_mode,
            relocation_feasibility=feasibility,
        )

    def _evaluate_relocation_feasibility(self, owner: str, path: Path) -> tuple[str, Literal["managed", "external"]]:
        """Evaluate if an artifact can be relocated under airoom/artifacts/.

        Returns:
            Tuple of (feasibility_description, recommended_mode).
        """
        if owner == "Graphify":
            # Graphify supports GRAPHIFY_OUT environment variable
            return ("Supported via GRAPHIFY_OUT environment variable", "managed")
        elif owner == "Superpowers":
            # Superpowers can be configured via skills/project config
            return ("Supported via skill configuration or project settings", "managed")
        elif owner == "Claude":
            # .claude directory is managed by Claude Code, not easily relocatable
            return ("Hardcoded path (.claude), not relocatable", "external")
        elif owner == "Aider":
            # Aider uses .aider in project root
            return ("Hardcoded path (.aider), not relocatable", "external")
        elif owner == "Cursor":
            # Cursor uses .cursor in project root
            return ("Hardcoded path (.cursor), not relocatable", "external")
        elif owner in ("Brainstorm", "LLM Plans", "LLM Specs", "AI Plans", "AI Specs"):
            # Standalone documents/specs can be moved
            return ("Standalone document/spec, can be relocated safely", "managed")
        return ("Unknown tool, feasibility uncertain", "external")

    def _get_registered_paths(self) -> set[str]:
        """Get set of all registered artifact paths."""
        data = self._read_raw_registry()
        paths = set()
        for entry in data.get("artifacts", {}).values():
            paths.add(entry.get("path", ""))
        return paths

    def _check_registry_discrepancies(
        self,
        report: DiscoveryReport,
        registered_artifacts: list[tuple[str, bool]],
        unregistered_candidates: list[DiscoveredArtifact]
    ) -> None:
        """Check for registry discrepancies and add to report.discrepancies."""
        data = self._read_raw_registry()
        artifacts = data.get("artifacts", {})

        # Check for missing registered paths
        for artifact_id, exists in registered_artifacts:
            if not exists:
                entry = artifacts.get(artifact_id, {})
                path = entry.get("path", "unknown")
                report.discrepancies.append(RegistryDiscrepancy(
                    kind="missing_path",
                    details=f"Registered artifact '{artifact_id}' path does not exist: {path}"
                ))

        # Check for type mismatches
        for artifact_id, exists in registered_artifacts:
            if exists:
                entry = artifacts.get(artifact_id, {})
                path = self.project.root / entry.get("path", "")
                expected_type = entry.get("type", "unknown")
                actual_type = "directory" if path.is_dir() else "file" if path.is_file() else "unknown"
                if actual_type != expected_type:
                    report.discrepancies.append(RegistryDiscrepancy(
                        kind="type_mismatch",
                        details=f"Artifact '{artifact_id}' declared as {expected_type} but is {actual_type} on disk: {entry.get('path', 'unknown')}"
                    ))

        # Check for placement mismatches (managed but not under airoom/artifacts/)
        for artifact_id, entry in artifacts.items():
            if entry.get("management") == "managed":
                path = entry.get("path", "")
                if not path.startswith("airoom/artifacts/"):
                    report.discrepancies.append(RegistryDiscrepancy(
                        kind="placement_mismatch",
                        details=f"Managed artifact '{artifact_id}' path is not under airoom/artifacts/: {path}"
                    ))

        # Check for duplicate claims (same path registered multiple times)
        path_to_ids: dict[str, list[str]] = {}
        for artifact_id, entry in artifacts.items():
            path = entry.get("path", "")
            if path not in path_to_ids:
                path_to_ids[path] = []
            path_to_ids[path].append(artifact_id)

        for path, ids in path_to_ids.items():
            if len(ids) > 1:
                report.discrepancies.append(RegistryDiscrepancy(
                    kind="duplicate_claim",
                    details=f"Multiple artifacts claim the same path '{path}': {', '.join(ids)}"
                ))

        # Note: unregistered candidates are already in report.unregistered_candidates,
        # so we don't add redundant "unregistered_candidate" discrepancies.

    def _generate_recommendations(
        self,
        unregistered_candidates: list[DiscoveredArtifact],
        discrepancies: list[RegistryDiscrepancy]
    ) -> list[str]:
        """Generate recommendations based on scan results."""
        recommendations = []

        # Recommendations based on discrepancies
        missing_paths = [d for d in discrepancies if d.kind == "missing_path"]
        if missing_paths:
            recommendations.append(
                f"Found {len(missing_paths)} registered artifact(s) missing from disk. "
                "Consider removing stale registry entries or restoring files."
            )

        type_mismatches = [d for d in discrepancies if d.kind == "type_mismatch"]
        if type_mismatches:
            recommendations.append(
                f"Found {len(type_mismatches)} type mismatch(es). "
                "Update registry entries to match actual filesystem types."
            )

        placement_mismatches = [d for d in discrepancies if d.kind == "placement_mismatch"]
        if placement_mismatches:
            recommendations.append(
                f"Found {len(placement_mismatches)} managed artifact(s) outside airoom/artifacts/. "
                "Use 'artifact-organization' skill to relocate, or change management to 'external'."
            )

        duplicate_claims = [d for d in discrepancies if d.kind == "duplicate_claim"]
        if duplicate_claims:
            recommendations.append(
                f"Found {len(duplicate_claims)} duplicate path claim(s). "
                "Each artifact path must be unique; resolve conflicts in registry."
            )

        # Recommendations based on candidates
        if unregistered_candidates:
            managed_candidates = [c for c in unregistered_candidates if c.recommended_mode == "managed"]
            external_candidates = [c for c in unregistered_candidates if c.recommended_mode == "external"]

            if managed_candidates:
                recommendations.append(
                    f"Found {len(managed_candidates)} relocatable AI artifact(s). "
                    "Run 'airoom discover --organize' or use 'artifact-organization' skill to register and move them."
                )

            if external_candidates:
                recommendations.append(
                    f"Found {len(external_candidates)} AI artifact(s) that cannot be relocated. "
                    "Register them with 'management: external' using 'registry-management' skill."
                )

        if not recommendations:
            recommendations.append("No issues found. Registry is consistent with filesystem.")

        return recommendations
