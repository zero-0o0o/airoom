"""Tests for the `airoom discover` Typer command."""

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from airoom.cli import app


class TestDiscoverCommand:
    """Tests for the discover command."""

    def setup_method(self):
        self.runner = CliRunner()

    def _init_project(self, tmpdir: str) -> Path:
        """Initialize an AIroom project in a temp directory."""
        result = self.runner.invoke(app, ["--path", tmpdir, "legacy", "init"])
        assert result.exit_code == 0
        return Path(tmpdir)

    def test_discover_command_exists(self):
        """Test that the discover command is registered."""
        result = self.runner.invoke(app, ["discover", "--help"])
        assert result.exit_code == 0
        assert "Discover AI artifacts and registry discrepancies" in result.stdout
        assert "--type" in result.stdout
        assert "graphify" in result.stdout.lower() or "superpowers" in result.stdout.lower() or "all" in result.stdout.lower()
        assert "--json" in result.stdout

    def test_discover_human_output_no_project(self):
        """Test discover command on a directory without AIroom initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["--path", tmpdir, "discover"])
            assert result.exit_code != 0
            assert "not initialized" in result.stdout.lower() or "not found" in result.stdout.lower()

    def test_discover_human_output_basic(self):
        """Test discover command on a fresh initialized project (human output)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "discover"])
            assert result.exit_code == 0
            # Check for key sections in human output
            assert "Inspected Locations" in result.stdout or "inspected" in result.stdout.lower()
            assert "Registered Artifacts" in result.stdout or "registered" in result.stdout.lower()
            assert "Unregistered" in result.stdout or "candidate" in result.stdout.lower()
            assert "Discrepanc" in result.stdout or "discrepanc" in result.stdout.lower()
            assert "Recommendation" in result.stdout or "recommend" in result.stdout.lower()

    def test_discover_json_output_basic(self):
        """Test discover command with --json flag on a fresh project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "discover", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Check structured output
            assert "inspected_locations" in data
            assert "registered_artifacts" in data
            assert "unregistered_candidates" in data
            assert "discrepancies" in data
            assert "recommendations" in data
            # Each section should be a list
            assert isinstance(data["inspected_locations"], list)
            assert isinstance(data["registered_artifacts"], list)
            assert isinstance(data["unregistered_candidates"], list)
            assert isinstance(data["discrepancies"], list)
            assert isinstance(data["recommendations"], list)

    def test_discover_type_filter_graphify(self):
        """Test discover with --type graphify filter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Create a graphify-out directory
            graphify_dir = Path(tmpdir) / "graphify-out"
            graphify_dir.mkdir()
            (graphify_dir / "output.txt").write_text("graphify output", encoding="utf-8")
            
            result = self.runner.invoke(app, ["--path", tmpdir, "discover", "--type", "graphify", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Should only have graphify candidates
            for candidate in data["unregistered_candidates"]:
                assert candidate["likely_owner"] == "Graphify"

    def test_discover_type_filter_superpowers(self):
        """Test discover with --type superpowers filter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Create a superpowers directory
            superpowers_dir = Path(tmpdir) / "docs" / "superpowers"
            superpowers_dir.mkdir(parents=True)
            (superpowers_dir / "session.log").write_text("superpowers session", encoding="utf-8")
            
            result = self.runner.invoke(app, ["--path", tmpdir, "discover", "--type", "superpowers", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Should only have superpowers candidates
            for candidate in data["unregistered_candidates"]:
                assert candidate["likely_owner"] == "Superpowers"

    def test_discover_type_filter_all(self):
        """Test discover with --type all (default) shows all candidates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Create graphify and superpowers artifacts
            graphify_dir = Path(tmpdir) / "graphify-out"
            graphify_dir.mkdir()
            (graphify_dir / "output.txt").write_text("graphify output", encoding="utf-8")
            
            superpowers_dir = Path(tmpdir) / "docs" / "superpowers"
            superpowers_dir.mkdir(parents=True)
            (superpowers_dir / "session.log").write_text("superpowers session", encoding="utf-8")
            
            result = self.runner.invoke(app, ["--path", tmpdir, "discover", "--type", "all", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Should have both graphify and superpowers candidates
            owners = {c["likely_owner"] for c in data["unregistered_candidates"]}
            assert "Graphify" in owners
            assert "Superpowers" in owners

    def test_discover_detects_registered_artifacts(self):
        """Test discover shows registered artifacts and their existence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Add a managed artifact to registry
            registry_file = Path(tmpdir) / "airoom" / "registry.yaml"
            from ruamel.yaml import YAML
            yaml = YAML()
            data = yaml.load(registry_file.read_text(encoding="utf-8"))
            data["artifacts"]["test-artifact"] = {
                "owner": "test-tool",
                "path": "airoom/artifacts/test-artifact",
                "type": "file",
                "management": "managed",
                "status": "active"
            }
            from io import StringIO
            output = StringIO()
            yaml.dump(data, output)
            registry_file.write_text(output.getvalue(), encoding="utf-8")
            
            # Create the artifact file
            artifact_file = Path(tmpdir) / "airoom" / "artifacts" / "test-artifact"
            artifact_file.parent.mkdir(parents=True, exist_ok=True)
            artifact_file.write_text("test content", encoding="utf-8")
            
            result = self.runner.invoke(app, ["--path", tmpdir, "discover", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Check registered artifacts list
            registered = data["registered_artifacts"]
            assert len(registered) >= 1
            # Find our test artifact
            found = False
            for artifact in registered:
                if artifact["id"] == "test-artifact":
                    assert artifact["exists"] is True
                    found = True
                    break
            assert found

    def test_discover_detects_missing_registered_artifacts(self):
        """Test discover detects registered artifacts missing from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Add a managed artifact to registry but don't create the file
            registry_file = Path(tmpdir) / "airoom" / "registry.yaml"
            from ruamel.yaml import YAML
            yaml = YAML()
            data = yaml.load(registry_file.read_text(encoding="utf-8"))
            data["artifacts"]["missing-artifact"] = {
                "owner": "test-tool",
                "path": "airoom/artifacts/missing-artifact",
                "type": "file",
                "management": "managed",
                "status": "active"
            }
            from io import StringIO
            output = StringIO()
            yaml.dump(data, output)
            registry_file.write_text(output.getvalue(), encoding="utf-8")
            
            result = self.runner.invoke(app, ["--path", tmpdir, "discover", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Check registered artifacts list
            registered = data["registered_artifacts"]
            found = False
            for artifact in registered:
                if artifact["id"] == "missing-artifact":
                    assert artifact["exists"] is False
                    found = True
                    break
            assert found
            # Should have discrepancy for missing path
            discrepancies = data["discrepancies"]
            missing_discrepancies = [d for d in discrepancies if d["kind"] == "missing_path"]
            assert len(missing_discrepancies) >= 1

    def test_discover_detects_unregistered_candidates(self):
        """Test discover finds unregistered AI artifact candidates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Create a graphify-out directory (unregistered)
            graphify_dir = Path(tmpdir) / "graphify-out"
            graphify_dir.mkdir()
            (graphify_dir / "output.txt").write_text("graphify output", encoding="utf-8")
            
            result = self.runner.invoke(app, ["--path", tmpdir, "discover", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            candidates = data["unregistered_candidates"]
            # Should find the graphify-out directory
            graphify_candidates = [c for c in candidates if c["likely_owner"] == "Graphify"]
            assert len(graphify_candidates) >= 1
            assert graphify_candidates[0]["path"] == "graphify-out"
            assert graphify_candidates[0]["type"] == "directory"

    def test_discover_recommendations(self):
        """Test discover generates recommendations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "discover", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Should have at least one recommendation
            assert len(data["recommendations"]) >= 1
            # Fresh project should have "no issues found" type recommendation
            assert any("no issues" in r.lower() or "consistent" in r.lower() for r in data["recommendations"])

    def test_discover_global_json_flag(self):
        """Test that global --json flag works with discover command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--json", "--path", tmpdir, "discover"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "inspected_locations" in data

    def test_discover_global_path_option(self):
        """Test that global --path option works with discover command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "discover"])
            assert result.exit_code == 0
            assert "Inspected" in result.stdout or "inspected" in result.stdout.lower()

    def test_discover_human_output_format(self):
        """Test human output uses Rich table with proper formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "discover"])
            assert result.exit_code == 0
            # Should contain table-like output
            assert "│" in result.stdout or "┌" in result.stdout or "└" in result.stdout or "┐" in result.stdout or "┘" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])