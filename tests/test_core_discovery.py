"""Tests for airoom.core.discovery module."""

import tempfile
from pathlib import Path

import pytest

from airoom.core.project import Project
from airoom.core.registry import RegistryManager
from airoom.core.discovery import (
    DiscoveredArtifact,
    RegistryDiscrepancy,
    DiscoveryReport,
    DiscoveryEngine,
)


class TestDiscoveryEngine:
    """Tests for DiscoveryEngine class."""

    def setup_method(self):
        """Create a temporary project directory with airoom structure."""
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir).resolve()
        self.project = Project(self.project_root)
        # Create the airoom directory structure
        self.project.airoom_dir.mkdir(parents=True, exist_ok=True)
        self.project.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.manager = RegistryManager(self.project)
        self.engine = DiscoveryEngine(self.project, self.manager)

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_with_project_and_registry(self):
        """Test DiscoveryEngine initialization with Project and RegistryManager."""
        assert self.engine.project == self.project
        assert self.engine.registry == self.manager

    def test_scan_empty_project_returns_report(self):
        """Test scanning an empty project returns a valid report."""
        report = self.engine.scan()
        
        assert isinstance(report, DiscoveryReport)
        assert isinstance(report.inspected_locations, list)
        assert isinstance(report.registered_artifacts, list)
        assert isinstance(report.unregistered_candidates, list)
        assert isinstance(report.discrepancies, list)
        assert isinstance(report.recommendations, list)

    def test_scan_inspects_expected_locations(self):
        """Test that scan inspects project root and known AI tool locations."""
        report = self.engine.scan()
        
        # Should at least inspect project root and airoom/artifacts
        inspected = report.inspected_locations
        assert any("airoom/artifacts" in loc for loc in inspected)
        # Project root should be inspected
        assert any(loc == "." or loc == self.project_root.name for loc in inspected)

    def test_scan_with_registered_artifact_tracks_existence(self):
        """Test that registered artifacts are tracked with existence status."""
        # Add a managed artifact to registry
        self.manager.add_artifact("test-artifact", {
            "owner": "test-tool",
            "path": "airoom/artifacts/test-artifact",
            "type": "directory",
            "management": "managed",
            "status": "active"
        })
        # Create the artifact on disk
        (self.project.artifacts_dir / "test-artifact").mkdir()
        
        report = self.engine.scan()
        
        # Should find the registered artifact and mark it as existing
        registered = report.registered_artifacts
        assert len(registered) == 1
        artifact_id, exists = registered[0]
        assert artifact_id == "test-artifact"
        assert exists is True

    def test_scan_registered_artifact_missing_on_disk(self):
        """Test that missing registered artifacts are detected."""
        # Add artifact to registry but don't create on disk
        self.manager.add_artifact("missing-artifact", {
            "owner": "test-tool",
            "path": "airoom/artifacts/missing-artifact",
            "type": "directory",
            "management": "managed",
            "status": "active"
        })
        
        report = self.engine.scan()
        
        registered = report.registered_artifacts
        assert len(registered) == 1
        artifact_id, exists = registered[0]
        assert artifact_id == "missing-artifact"
        assert exists is False
        
        # Should have a missing_path discrepancy
        discrepancies = report.discrepancies
        assert any(d.kind == "missing_path" for d in discrepancies)

    def test_scan_detects_graphify_candidates(self):
        """Test detection of Graphify output directories."""
        # Create Graphify output directory
        graphify_out = self.project_root / "graphify-out"
        graphify_out.mkdir()
        (graphify_out / "graph.json").write_text('{"nodes": []}')
        
        report = self.engine.scan()
        
        candidates = report.unregistered_candidates
        graphify_candidates = [c for c in candidates if c.likely_owner == "Graphify"]
        assert len(graphify_candidates) >= 1
        candidate = graphify_candidates[0]
        assert candidate.path == "graphify-out"
        assert candidate.type == "directory"
        assert "Graphify pattern" in candidate.evidence[0]

    def test_scan_detects_graphify_dot_files(self):
        """Test detection of Graphify dot files."""
        # Create Graphify dot file
        graphify_cache = self.project_root / ".graphify_cache"
        graphify_cache.write_text("cache data")
        
        report = self.engine.scan()
        
        candidates = report.unregistered_candidates
        graphify_candidates = [c for c in candidates if c.likely_owner == "Graphify"]
        assert len(graphify_candidates) >= 1
        candidate = graphify_candidates[0]
        assert candidate.path == ".graphify_cache"
        assert candidate.type == "file"

    def test_scan_detects_superpowers_candidates(self):
        """Test detection of Superpowers output directories."""
        # Create Superpowers directory
        superpowers_dir = self.project_root / "docs" / "superpowers"
        superpowers_dir.mkdir(parents=True)
        (superpowers_dir / "session.md").write_text("# Session")
        
        report = self.engine.scan()
        
        candidates = report.unregistered_candidates
        sp_candidates = [c for c in candidates if c.likely_owner == "Superpowers"]
        assert len(sp_candidates) >= 1
        candidate = sp_candidates[0]
        assert candidate.path == "docs/superpowers"
        assert candidate.type == "directory"

    def test_scan_detects_superpowers_dot_directory(self):
        """Test detection of .superpowers directory."""
        # Create .superpowers directory
        sp_dot = self.project_root / ".superpowers"
        sp_dot.mkdir()
        (sp_dot / "config.yaml").write_text("key: value")
        
        report = self.engine.scan()
        
        candidates = report.unregistered_candidates
        sp_candidates = [c for c in candidates if c.likely_owner == "Superpowers"]
        assert len(sp_candidates) >= 1
        candidate = sp_candidates[0]
        assert candidate.path == ".superpowers"
        assert candidate.type == "directory"

    def test_scan_detects_claude_scratchpad(self):
        """Test detection of .claude directory."""
        claude_dir = self.project_root / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text('{}')
        
        report = self.engine.scan()
        
        candidates = report.unregistered_candidates
        claude_candidates = [c for c in candidates if c.likely_owner == "Claude"]
        assert len(claude_candidates) >= 1
        candidate = claude_candidates[0]
        assert candidate.path == ".claude"
        assert candidate.type == "directory"

    def test_scan_detects_aider_scratchpad(self):
        """Test detection of .aider* directories/files."""
        aider_dir = self.project_root / ".aider"
        aider_dir.mkdir()
        (aider_dir / "history.json").write_text('[]')
        
        report = self.engine.scan()
        
        candidates = report.unregistered_candidates
        aider_candidates = [c for c in candidates if c.likely_owner == "Aider"]
        assert len(aider_candidates) >= 1
        candidate = aider_candidates[0]
        assert candidate.path == ".aider"
        assert candidate.type == "directory"

    def test_scan_detects_cursor_scratchpad(self):
        """Test detection of .cursor directory."""
        cursor_dir = self.project_root / ".cursor"
        cursor_dir.mkdir()
        (cursor_dir / "rules").mkdir()
        
        report = self.engine.scan()
        
        candidates = report.unregistered_candidates
        cursor_candidates = [c for c in candidates if c.likely_owner == "Cursor"]
        assert len(cursor_candidates) >= 1
        candidate = cursor_candidates[0]
        assert candidate.path == ".cursor"
        assert candidate.type == "directory"

    def test_scan_detects_brainstorm_logs(self):
        """Test detection of brainstorm log files."""
        brainstorm = self.project_root / "brainstorm.log"
        brainstorm.write_text("Brainstorming session...")
        
        report = self.engine.scan()
        
        candidates = report.unregistered_candidates
        # Could be categorized under a generic owner or specific tool
        assert len(candidates) >= 1

    def test_scan_detects_llm_plan_spec_folders(self):
        """Test detection of LLM plan/spec folders."""
        plans_dir = self.project_root / "llm-plans"
        plans_dir.mkdir()
        (plans_dir / "plan.md").write_text("# Plan")
        
        report = self.engine.scan()
        
        candidates = report.unregistered_candidates
        assert len(candidates) >= 1

    def test_scan_ignores_project_source_code(self):
        """Test that project source code is not flagged as AI artifact."""
        # Create typical project source files
        src_dir = self.project_root / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("print('hello')")
        (src_dir / "lib.rs").write_text("fn main() {}")
        (self.project_root / "package.json").write_text('{"name": "test"}')
        (self.project_root / "Cargo.toml").write_text('[package]\nname = "test"')
        (self.project_root / "pyproject.toml").write_text('[project]\nname = "test"')
        
        report = self.engine.scan()
        
        # Should not flag these as AI artifacts
        source_paths = {"src/main.py", "src/lib.rs", "package.json", "Cargo.toml", "pyproject.toml"}
        candidate_paths = {c.path for c in report.unregistered_candidates}
        assert source_paths.isdisjoint(candidate_paths)

    def test_scan_ignores_dependencies(self):
        """Test that dependency directories are not flagged."""
        # Create dependency directories
        (self.project_root / "node_modules").mkdir()
        (self.project_root / "node_modules" / "some-package").mkdir()
        (self.project_root / ".venv").mkdir()
        (self.project_root / ".venv" / "bin").mkdir()
        (self.project_root / "vendor").mkdir()
        
        report = self.engine.scan()
        
        candidate_paths = {c.path for c in report.unregistered_candidates}
        dep_paths = {"node_modules", ".venv", "vendor"}
        assert dep_paths.isdisjoint(candidate_paths)

    def test_scan_ignores_build_artifacts(self):
        """Test that build artifact directories are not flagged."""
        (self.project_root / "build").mkdir()
        (self.project_root / "dist").mkdir()
        (self.project_root / "target").mkdir()
        (self.project_root / ".cache").mkdir()
        
        report = self.engine.scan()
        
        candidate_paths = {c.path for c in report.unregistered_candidates}
        build_paths = {"build", "dist", "target", ".cache"}
        assert build_paths.isdisjoint(candidate_paths)

    def test_scan_ignores_git_directory(self):
        """Test that .git directory is not flagged."""
        (self.project_root / ".git").mkdir()
        (self.project_root / ".git" / "config").write_text("[core]")
        
        report = self.engine.scan()
        
        candidate_paths = {c.path for c in report.unregistered_candidates}
        assert ".git" not in candidate_paths

    def test_scan_detects_type_mismatch(self):
        """Test detection of type mismatch (file vs directory)."""
        # Register as file but create as directory
        self.manager.add_artifact("type-mismatch", {
            "owner": "test-tool",
            "path": "airoom/artifacts/type-mismatch",
            "type": "file",
            "management": "managed",
            "status": "active"
        })
        (self.project.artifacts_dir / "type-mismatch").mkdir()
        
        report = self.engine.scan()
        
        discrepancies = report.discrepancies
        assert any(d.kind == "type_mismatch" for d in discrepancies)

    def test_scan_detects_placement_mismatch(self):
        """Test detection of managed artifact not under airoom/artifacts/."""
        # Register as managed but with path outside airoom/artifacts
        # Bypass validation by writing directly to registry file
        import yaml
        data = {"version": 1, "artifacts": {
            "placement-mismatch": {
                "owner": "test-tool",
                "path": "generated/outside",
                "type": "directory",
                "management": "managed",
                "status": "active"
            }
        }, "tools": {}}
        self.project.registry_path.write_text(yaml.dump(data))
        (self.project_root / "generated" / "outside").mkdir(parents=True)
        
        report = self.engine.scan()
        
        discrepancies = report.discrepancies
        assert any(d.kind == "placement_mismatch" for d in discrepancies)

    def test_scan_detects_duplicate_claims(self):
        """Test detection of duplicate path claims in registry."""
        # Add two artifacts with same path, bypassing validation
        import yaml
        data = {"version": 1, "artifacts": {
            "artifact1": {
                "owner": "tool1",
                "path": "airoom/artifacts/shared",
                "type": "directory",
                "management": "managed",
                "status": "active"
            },
            "artifact2": {
                "owner": "tool2",
                "path": "airoom/artifacts/shared",
                "type": "directory",
                "management": "managed",
                "status": "active"
            }
        }, "tools": {}}
        self.project.registry_path.write_text(yaml.dump(data))
        (self.project.artifacts_dir / "shared").mkdir()
        
        report = self.engine.scan()
        
        discrepancies = report.discrepancies
        assert any(d.kind == "duplicate_claim" for d in discrepancies)

    def test_scan_evaluates_relocation_feasibility(self):
        """Test that relocation feasibility is assessed for candidates."""
        graphify_out = self.project_root / "graphify-out"
        graphify_out.mkdir()
        
        report = self.engine.scan()
        
        candidates = report.unregistered_candidates
        graphify_candidates = [c for c in candidates if c.likely_owner == "Graphify"]
        assert len(graphify_candidates) >= 1
        candidate = graphify_candidates[0]
        assert candidate.relocation_feasibility is not None
        assert len(candidate.relocation_feasibility) > 0

    def test_scan_recommends_managed_for_relocatable(self):
        """Test that relocatable candidates get 'managed' recommendation."""
        # Graphify supports GRAPHIFY_OUT env var
        graphify_out = self.project_root / "graphify-out"
        graphify_out.mkdir()
        
        report = self.engine.scan()
        
        candidates = report.unregistered_candidates
        graphify_candidates = [c for c in candidates if c.likely_owner == "Graphify"]
        candidate = graphify_candidates[0]
        # Graphify supports custom output path via env var
        assert candidate.recommended_mode in ("managed", "external")

    def test_scan_treats_symlinks_as_opaque(self):
        """Test that symlinks are not followed and reported as-is."""
        # Create a real directory outside project
        outside_dir = Path("/tmp") / f"airoom-test-outside-{id(self)}"
        outside_dir.mkdir(exist_ok=True)
        (outside_dir / "target.txt").write_text("target")
        
        # Create symlink inside project
        link_path = self.project_root / "symlink-to-outside"
        link_path.symlink_to(outside_dir, target_is_directory=True)
        
        try:
            report = self.engine.scan()
            
            # Should not crash, and should not follow symlink
            # Symlink itself might be detected but not traversed
            candidate_paths = {c.path for c in report.unregistered_candidates}
            # The symlink target contents should not be scanned
            assert "target.txt" not in candidate_paths
        finally:
            link_path.unlink()
            (outside_dir / "target.txt").unlink()
            outside_dir.rmdir()

    def test_scan_is_read_only(self):
        """Test that scan does not modify filesystem or registry."""
        # Create some candidates
        graphify_out = self.project_root / "graphify-out"
        graphify_out.mkdir()
        
        # Record initial state
        initial_registry = self.manager.read()
        initial_files = set(self.project_root.rglob("*"))
        
        report = self.engine.scan()
        
        # Registry should be unchanged
        assert self.manager.read() == initial_registry
        # No new files should be created
        final_files = set(self.project_root.rglob("*"))
        assert final_files == initial_files

    def test_discovered_artifact_dataclass_fields(self):
        """Test DiscoveredArtifact dataclass has all required fields."""
        artifact = DiscoveredArtifact(
            path="test/path",
            likely_owner="TestTool",
            evidence=["evidence1", "evidence2"],
            type="directory",
            recommended_mode="managed",
            relocation_feasibility="Supported via ENV_VAR"
        )
        assert artifact.path == "test/path"
        assert artifact.likely_owner == "TestTool"
        assert artifact.evidence == ["evidence1", "evidence2"]
        assert artifact.type == "directory"
        assert artifact.recommended_mode == "managed"
        assert artifact.relocation_feasibility == "Supported via ENV_VAR"

    def test_registry_discrepancy_dataclass_fields(self):
        """Test RegistryDiscrepancy dataclass has all required fields."""
        discrepancy = RegistryDiscrepancy(
            kind="missing_path",
            details="Artifact 'test' path does not exist"
        )
        assert discrepancy.kind == "missing_path"
        assert discrepancy.details == "Artifact 'test' path does not exist"

    def test_discovery_report_dataclass_fields(self):
        """Test DiscoveryReport dataclass has all required fields."""
        report = DiscoveryReport(
            inspected_locations=["."],
            registered_artifacts=[("test", True)],
            unregistered_candidates=[],
            discrepancies=[],
            recommendations=["No action needed"]
        )
        assert report.inspected_locations == ["."]
        assert report.registered_artifacts == [("test", True)]
        assert report.unregistered_candidates == []
        assert report.discrepancies == []
        assert report.recommendations == ["No action needed"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])