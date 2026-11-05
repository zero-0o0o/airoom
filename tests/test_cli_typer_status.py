"""Tests for the `airoom status` Typer command."""

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from airoom.cli import app


class TestStatusCommand:
    """Tests for the status command."""

    def setup_method(self):
        self.runner = CliRunner()

    def _init_project(self, tmpdir: str) -> Path:
        """Initialize an AIroom project in a temp directory."""
        result = self.runner.invoke(app, ["--path", tmpdir, "init"])
        assert result.exit_code == 0
        return Path(tmpdir)

    def test_status_command_exists(self):
        """Test that the status command is registered."""
        result = self.runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0
        assert "Show project health summary" in result.stdout

    def test_status_human_output_no_project(self):
        """Test status command on a directory without AIroom initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["--path", tmpdir, "status"])
            # Should fail gracefully with an error message
            assert result.exit_code != 0
            assert "not initialized" in result.stdout.lower() or "not found" in result.stdout.lower()

    def test_status_human_output_basic(self):
        """Test status command on a fresh initialized project (human output)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "status"])
            assert result.exit_code == 0
            # Check for key sections in human output
            assert "Version" in result.stdout
            assert "Baseline" in result.stdout
            assert "Registry" in result.stdout
            assert "Artifacts" in result.stdout
            assert "Tools" in result.stdout
            # Should show checkmarks for healthy project
            assert "✓" in result.stdout or "✗" in result.stdout

    def test_status_json_output_basic(self):
        """Test status command with --json flag on a fresh project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Check structured output
            assert "version" in data
            assert "baseline" in data
            assert "registry" in data
            assert "artifacts" in data
            assert "tools" in data
            # Each check should have status and details
            for key in ["version", "baseline", "registry", "artifacts", "tools"]:
                assert "status" in data[key]
                assert "details" in data[key]
            # Fresh project should be healthy
            assert data["version"]["status"] == "ok"
            assert data["baseline"]["status"] == "ok"
            assert data["registry"]["status"] == "ok"
            assert data["artifacts"]["status"] == "ok"
            assert data["tools"]["status"] == "ok"

    def test_status_version_check_mismatch(self):
        """Test status detects version mismatch between installed and project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Modify the project version to simulate mismatch
            version_file = Path(tmpdir) / "airoom" / ".airoom-version"
            version_file.write_text("0.0.1\n", encoding="utf-8")
            
            result = self.runner.invoke(app, ["--path", tmpdir, "status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["version"]["status"] == "mismatch"
            assert "0.0.1" in data["version"]["details"]
            assert "installed" in data["version"]["details"].lower()

    def test_status_baseline_verification_failure(self):
        """Test status detects baseline hash mismatch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Modify a tracked resource file
            skill_file = Path(tmpdir) / "airoom" / "skills" / "artifact-discovery" / "SKILL.md"
            if skill_file.exists():
                skill_file.write_text("# Modified Skill\n\nContent changed.", encoding="utf-8")
            
            result = self.runner.invoke(app, ["--path", tmpdir, "status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["baseline"]["status"] == "mismatch"
            assert "mismatch" in data["baseline"]["details"].lower() or "modified" in data["baseline"]["details"].lower()

    def test_status_registry_validation_failure(self):
        """Test status detects invalid registry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Corrupt the registry
            registry_file = Path(tmpdir) / "airoom" / "registry.yaml"
            registry_file.write_text("version: 1\nversion: 1\nartifacts: {}\ntools: {}\n", encoding="utf-8")
            
            result = self.runner.invoke(app, ["--path", tmpdir, "status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["registry"]["status"] == "invalid"
            assert "duplicate" in data["registry"]["details"].lower() or "error" in data["registry"]["details"].lower()

    def test_status_artifact_existence_check_missing(self):
        """Test status detects missing managed artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Add a managed artifact to registry but don't create the file
            registry_file = Path(tmpdir) / "airoom" / "registry.yaml"
            import yaml
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
            
            result = self.runner.invoke(app, ["--path", tmpdir, "status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["artifacts"]["status"] == "missing"
            assert "missing-artifact" in data["artifacts"]["details"]

    def test_status_external_artifact_check_missing(self):
        """Test status detects missing external artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Add an external artifact to registry
            registry_file = Path(tmpdir) / "airoom" / "registry.yaml"
            from ruamel.yaml import YAML
            yaml = YAML()
            data = yaml.load(registry_file.read_text(encoding="utf-8"))
            data["artifacts"]["external-missing"] = {
                "owner": "test-tool",
                "path": "external/missing-file.txt",
                "type": "file",
                "management": "external",
                "status": "active"
            }
            from io import StringIO
            output = StringIO()
            yaml.dump(data, output)
            registry_file.write_text(output.getvalue(), encoding="utf-8")
            
            result = self.runner.invoke(app, ["--path", tmpdir, "status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["artifacts"]["status"] == "missing"
            assert "external-missing" in data["artifacts"]["details"]

    def test_status_tool_config_check(self):
        """Test status shows tool configurations from registry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Add a tool with config_path
            registry_file = Path(tmpdir) / "airoom" / "registry.yaml"
            from ruamel.yaml import YAML
            yaml = YAML()
            data = yaml.load(registry_file.read_text(encoding="utf-8"))
            data["tools"]["test-tool"] = {
                "name": "Test Tool",
                "status": "active",
                "config_path": "airoom/config/test-tool.yaml",
                "runtime_path": "airoom/runtime/test-tool"
            }
            from io import StringIO
            output = StringIO()
            yaml.dump(data, output)
            registry_file.write_text(output.getvalue(), encoding="utf-8")
            
            result = self.runner.invoke(app, ["--path", tmpdir, "status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["tools"]["status"] == "ok"
            assert "test-tool" in data["tools"]["details"]
            assert "Test Tool" in data["tools"]["details"]

    def test_status_human_output_format(self):
        """Test human output uses Rich table with proper formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "status"])
            assert result.exit_code == 0
            # Should contain table-like output
            assert "│" in result.stdout or "┌" in result.stdout or "└" in result.stdout or "┐" in result.stdout or "┘" in result.stdout
            # Should have status indicators
            assert "✓" in result.stdout or "✗" in result.stdout

    def test_status_global_json_flag(self):
        """Test that global --json flag works with status command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--json", "--path", tmpdir, "status"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "version" in data

    def test_status_global_path_option(self):
        """Test that global --path option works with status command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "status"])
            assert result.exit_code == 0
            assert "Version" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])