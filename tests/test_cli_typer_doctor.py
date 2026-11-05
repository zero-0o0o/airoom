"""Tests for the `airoom doctor` Typer command."""

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from airoom.cli import app


class TestDoctorCommand:
    """Tests for the doctor command."""

    def setup_method(self):
        self.runner = CliRunner()

    def _init_project(self, tmpdir: str) -> Path:
        """Initialize an AIroom project in a temp directory."""
        result = self.runner.invoke(app, ["--path", tmpdir, "init"])
        assert result.exit_code == 0
        return Path(tmpdir)

    def test_doctor_command_exists(self):
        """Test that the doctor command is registered."""
        result = self.runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "Diagnose and repair common issues" in result.stdout
        assert "--fix" in result.stdout
        assert "--json" in result.stdout

    def test_doctor_human_output_no_project(self):
        """Test doctor command on a directory without AIroom initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["--path", tmpdir, "doctor"])
            assert result.exit_code != 0
            assert (
                "not initialized" in result.stdout.lower() or "not found" in result.stdout.lower()
            )

    def test_doctor_human_output_healthy(self):
        """Test doctor command on a fresh initialized project (human output)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "doctor"])
            assert result.exit_code == 0
            # Should show all checks
            assert "Version" in result.stdout
            assert "Baseline" in result.stdout
            assert "Registry" in result.stdout
            assert "Artifacts" in result.stdout
            assert "Symlinks" in result.stdout
            assert "Boundary" in result.stdout
            assert "Orphaned" in result.stdout
            # Should show checkmarks for healthy project
            assert "✓" in result.stdout or "✗" in result.stdout

    def test_doctor_json_output_healthy(self):
        """Test doctor command with --json flag on a fresh project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Check structured output
            assert "version" in data
            assert "baseline" in data
            assert "registry" in data
            assert "artifacts" in data
            assert "symlinks" in data
            assert "boundary" in data
            assert "orphaned_skills" in data
            # Each check should have status and details
            for key in [
                "version",
                "baseline",
                "registry",
                "artifacts",
                "symlinks",
                "boundary",
                "orphaned_skills",
            ]:
                assert "status" in data[key]
                assert "details" in data[key]
            # Fresh project should be healthy
            assert data["version"]["status"] == "ok"
            assert data["baseline"]["status"] == "ok"
            assert data["registry"]["status"] == "ok"
            assert data["artifacts"]["status"] == "ok"
            assert data["symlinks"]["status"] == "ok"
            assert data["boundary"]["status"] == "ok"
            assert data["orphaned_skills"]["status"] == "ok"

    def test_doctor_missing_version_file(self):
        """Test doctor detects missing .airoom-version file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            version_file = Path(tmpdir) / "airoom" / ".airoom-version"
            version_file.unlink()

            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["version"]["status"] == "missing"
            assert (
                "not found" in data["version"]["details"].lower()
                or "missing" in data["version"]["details"].lower()
            )

    def test_doctor_missing_version_file_fix(self):
        """Test doctor --fix recreates missing .airoom-version file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            version_file = Path(tmpdir) / "airoom" / ".airoom-version"
            version_file.unlink()

            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--fix", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["version"]["status"] == "ok"
            assert version_file.exists()
            assert version_file.read_text().strip() != ""

    def test_doctor_missing_baseline_file(self):
        """Test doctor detects missing .airoom-baseline.json file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            baseline_file = Path(tmpdir) / "airoom" / ".airoom-baseline.json"
            baseline_file.unlink()

            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["baseline"]["status"] == "missing"
            assert (
                "not found" in data["baseline"]["details"].lower()
                or "missing" in data["baseline"]["details"].lower()
            )

    def test_doctor_missing_baseline_file_fix(self):
        """Test doctor --fix recreates missing .airoom-baseline.json file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            baseline_file = Path(tmpdir) / "airoom" / ".airoom-baseline.json"
            baseline_file.unlink()

            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--fix", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["baseline"]["status"] == "ok"
            assert baseline_file.exists()
            baseline_content = json.loads(baseline_file.read_text())
            assert isinstance(baseline_content, dict)
            # Should have hashes for all installed skills
            assert len(baseline_content) > 0

    def test_doctor_baseline_mismatch(self):
        """Test doctor detects baseline hash mismatch (user-modified resource)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Modify a tracked resource file
            skill_file = Path(tmpdir) / "airoom" / "skills" / "artifact-discovery" / "SKILL.md"
            if skill_file.exists():
                skill_file.write_text("# Modified Skill\n\nContent changed.", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["baseline"]["status"] == "mismatch"
            assert (
                "modified" in data["baseline"]["details"].lower()
                or "mismatch" in data["baseline"]["details"].lower()
            )

    def test_doctor_baseline_mismatch_no_autofix(self):
        """Test doctor --fix does NOT auto-fix baseline mismatches (user data)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Modify a tracked resource file
            skill_file = Path(tmpdir) / "airoom" / "skills" / "artifact-discovery" / "SKILL.md"
            if skill_file.exists():
                skill_file.write_text("# Modified Skill\n\nContent changed.", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--fix", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Should still report mismatch - no auto-fix for user modifications
            assert data["baseline"]["status"] == "mismatch"
            # Original content should be preserved
            assert skill_file.read_text() == "# Modified Skill\n\nContent changed."

    def test_doctor_registry_schema_violation(self):
        """Test doctor detects registry schema violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Corrupt the registry with invalid schema
            registry_file = Path(tmpdir) / "airoom" / "registry.yaml"
            registry_file.write_text("version: 2\nartifacts: {}\ntools: {}\n", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["registry"]["status"] == "invalid"
            assert (
                "version" in data["registry"]["details"].lower()
                or "schema" in data["registry"]["details"].lower()
            )

    def test_doctor_registry_schema_violation_fix(self):
        """Test doctor --fix removes invalid registry entries with confirmation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Corrupt the registry with invalid schema
            registry_file = Path(tmpdir) / "airoom" / "registry.yaml"
            registry_file.write_text("version: 2\nartifacts: {}\ntools: {}\n", encoding="utf-8")

            # --fix should fix the registry (recreate from baseline/template)
            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--fix", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["registry"]["status"] == "ok"
            # Version should be restored to 1
            registry_content = registry_file.read_text()
            assert "version: 1" in registry_content

    def test_doctor_missing_artifact_paths(self):
        """Test doctor detects missing artifact paths (registered but not on disk)."""
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
                "status": "active",
            }
            from io import StringIO

            output = StringIO()
            yaml.dump(data, output)
            registry_file.write_text(output.getvalue(), encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["artifacts"]["status"] == "missing"
            assert "missing-artifact" in data["artifacts"]["details"]

    def test_doctor_missing_external_artifact_paths(self):
        """Test doctor detects missing external artifact paths."""
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
                "status": "active",
            }
            from io import StringIO

            output = StringIO()
            yaml.dump(data, output)
            registry_file.write_text(output.getvalue(), encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["artifacts"]["status"] == "missing"
            assert "external-missing" in data["artifacts"]["details"]

    def test_doctor_symlinks_in_airoom_dir(self):
        """Test doctor detects symlinks in airoom/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Create a symlink in the airoom directory
            airoom_dir = Path(tmpdir) / "airoom"
            target_file = airoom_dir / "target.txt"
            target_file.write_text("target", encoding="utf-8")
            symlink_path = airoom_dir / "link.txt"
            symlink_path.symlink_to(target_file)

            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["symlinks"]["status"] == "found"
            assert (
                "link.txt" in data["symlinks"]["details"]
                or "symlink" in data["symlinks"]["details"].lower()
            )

    def test_doctor_path_boundary_violations(self):
        """Test doctor detects path boundary violations in registry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Add artifact with path containing ..
            registry_file = Path(tmpdir) / "airoom" / "registry.yaml"
            from ruamel.yaml import YAML

            yaml = YAML()
            data = yaml.load(registry_file.read_text(encoding="utf-8"))
            data["artifacts"]["boundary-violation"] = {
                "owner": "test-tool",
                "path": "airoom/artifacts/../outside.txt",
                "type": "file",
                "management": "managed",
                "status": "active",
            }
            from io import StringIO

            output = StringIO()
            yaml.dump(data, output)
            registry_file.write_text(output.getvalue(), encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["boundary"]["status"] == "violation"
            assert (
                "boundary" in data["boundary"]["details"].lower()
                or ".." in data["boundary"]["details"]
            )

    def test_doctor_orphaned_skills(self):
        """Test doctor detects orphaned skills (in project but not packaged)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Create a user-created skill directory
            skills_dir = Path(tmpdir) / "airoom" / "skills"
            orphan_dir = skills_dir / "my-custom-skill"
            orphan_dir.mkdir(parents=True)
            (orphan_dir / "SKILL.md").write_text("# Custom Skill\n\nMy skill.", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["orphaned_skills"]["status"] == "found"
            assert "my-custom-skill" in data["orphaned_skills"]["details"]

    def test_doctor_fix_creates_missing_dirs(self):
        """Test doctor --fix recreates missing airoom subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Remove skills and artifacts directories
            skills_dir = Path(tmpdir) / "airoom" / "skills"
            artifacts_dir = Path(tmpdir) / "airoom" / "artifacts"
            import shutil

            shutil.rmtree(skills_dir)
            shutil.rmtree(artifacts_dir)

            result = self.runner.invoke(app, ["--path", tmpdir, "doctor", "--fix", "--json"])
            assert result.exit_code == 0
            # Should have fixed the missing directories
            assert skills_dir.exists()
            assert artifacts_dir.exists()

    def test_doctor_global_json_flag(self):
        """Test that global --json flag works with doctor command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--json", "--path", tmpdir, "doctor"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "version" in data

    def test_doctor_global_path_option(self):
        """Test that global --path option works with doctor command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "doctor"])
            assert result.exit_code == 0
            assert "Version" in result.stdout

    def test_doctor_dry_run_mode(self):
        """Test doctor --dry-run shows what would be fixed without making changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            version_file = Path(tmpdir) / "airoom" / ".airoom-version"
            version_file.unlink()

            result = self.runner.invoke(
                app, ["--path", tmpdir, "--dry-run", "doctor", "--fix", "--json"]
            )
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # In dry-run mode, version should still show as missing (not actually fixed)
            assert data["version"]["status"] == "missing"
            # File should not be recreated
            assert not version_file.exists()

    def test_doctor_human_output_format(self):
        """Test human output uses Rich table with proper formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "doctor"])
            assert result.exit_code == 0
            # Should contain table-like output
            assert (
                "│" in result.stdout
                or "┌" in result.stdout
                or "└" in result.stdout
                or "┐" in result.stdout
                or "┘" in result.stdout
            )
            # Should have status indicators
            assert "✓" in result.stdout or "✗" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
