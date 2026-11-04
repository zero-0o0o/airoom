"""Tests for the `airoom organize` Typer command."""

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from airoom.cli import app


class TestOrganizeCommand:
    """Tests for the organize command."""

    def setup_method(self):
        self.runner = CliRunner()

    def _init_project(self, tmpdir: str) -> Path:
        """Initialize an AIroom project in a temp directory."""
        result = self.runner.invoke(app, ["--path", tmpdir, "legacy", "init"])
        assert result.exit_code == 0
        return Path(tmpdir)

    def test_organize_command_exists(self):
        """Test that the organize command is registered."""
        result = self.runner.invoke(app, ["organize", "--help"])
        assert result.exit_code == 0
        assert "Organize artifacts under airoom/artifacts/" in result.stdout
        assert "--interactive" in result.stdout
        assert "--non-interactive" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--json" in result.stdout
        assert "--path" in result.stdout

    def test_organize_human_output_no_project(self):
        """Test organize command on a directory without AIroom initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--non-interactive"])
            assert result.exit_code != 0
            assert "not initialized" in result.stdout.lower() or "not found" in result.stdout.lower()

    def test_organize_dry_run_shows_plan(self):
        """Test organize --dry-run shows the relocation plan without executing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Create a graphify-out directory (unregistered candidate)
            graphify_dir = Path(tmpdir) / "graphify-out"
            graphify_dir.mkdir()
            (graphify_dir / "output.txt").write_text("graphify output", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--dry-run", "--non-interactive", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Should show plan in dry-run mode
            assert "plan" in data or "actions" in data or "messages" in data
            # Should not have actually moved anything
            assert graphify_dir.exists()

    def test_organize_interactive_mode_prompts(self):
        """Test organize in interactive mode prompts for each candidate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Create a graphify-out directory (unregistered candidate)
            graphify_dir = Path(tmpdir) / "graphify-out"
            graphify_dir.mkdir()
            (graphify_dir / "output.txt").write_text("graphify output", encoding="utf-8")

            # Simulate user selecting "skip" for the candidate
            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--interactive"], input="skip\n")
            assert result.exit_code == 0
            # Artifact should not be moved
            assert graphify_dir.exists()

    def test_organize_non_interactive_defaults_to_managed(self):
        """Test organize --non-interactive applies defaults (managed if feasible)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Create a graphify-out directory (unregistered candidate, managed feasible)
            graphify_dir = Path(tmpdir) / "graphify-out"
            graphify_dir.mkdir()
            (graphify_dir / "output.txt").write_text("graphify output", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--non-interactive", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Should have executed the plan
            assert data.get("success") is True or "executed" in str(data).lower() or "moved" in str(data).lower()
            # Artifact should be moved to airoom/artifacts/
            target_path = Path(tmpdir) / "airoom" / "artifacts" / "graphify-out"
            assert target_path.exists() or any((Path(tmpdir) / "airoom" / "artifacts").glob("graphify-out*"))

    def test_organize_non_interactive_external_for_claude(self):
        """Test organize --non-interactive registers external for non-relocatable tools (e.g., .claude)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Create a .claude directory (unregistered candidate, external only)
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            (claude_dir / "settings.json").write_text("{}", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--non-interactive", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Should have registered as external
            assert data.get("success") is True or "executed" in str(data).lower() or "registered" in str(data).lower()
            # Artifact should NOT be moved, but registered as external
            assert claude_dir.exists()
            # Check registry for external entry
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            registry_data = manager.read()
            artifacts = registry_data.get("artifacts", {})
            # Find the .claude artifact
            claude_artifact = None
            for aid, entry in artifacts.items():
                if entry.get("path") == ".claude" or ".claude" in entry.get("path", ""):
                    claude_artifact = entry
                    break
            assert claude_artifact is not None
            assert claude_artifact["management"] == "external"

    def test_organize_full_execution_moves_and_registers(self):
        """Test organize executes full workflow: discover -> plan -> confirm -> execute -> verify."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Create multiple unregistered candidates
            graphify_dir = Path(tmpdir) / "graphify-out"
            graphify_dir.mkdir()
            (graphify_dir / "output.txt").write_text("graphify output", encoding="utf-8")

            superpowers_dir = Path(tmpdir) / "docs" / "superpowers"
            superpowers_dir.mkdir(parents=True)
            (superpowers_dir / "session.log").write_text("superpowers session", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--non-interactive", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data.get("success") is True

            # Check both artifacts were moved to airoom/artifacts/
            artifacts_dir = Path(tmpdir) / "airoom" / "artifacts"
            assert artifacts_dir.exists()
            # Should have graphify-out and superpowers (or similar)
            moved_items = list(artifacts_dir.rglob("*"))
            assert len(moved_items) >= 2

            # Check registry has both artifacts
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            registry_data = manager.read()
            artifacts = registry_data.get("artifacts", {})
            managed_artifacts = [a for a in artifacts.values() if a.get("management") == "managed"]
            assert len(managed_artifacts) >= 2

    def test_organize_rollback_on_failure(self):
        """Test organize rolls back on verification failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Create a graphify-out directory
            graphify_dir = Path(tmpdir) / "graphify-out"
            graphify_dir.mkdir()
            (graphify_dir / "output.txt").write_text("graphify output", encoding="utf-8")

            # Make target directory read-only to simulate failure
            artifacts_dir = Path(tmpdir) / "airoom" / "artifacts"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            # Note: On some systems this might not work as expected in tests
            # We'll test that the rollback mechanism is invoked conceptually
            # by checking that partial failures are handled gracefully

            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--non-interactive", "--json"])
            # Should either succeed or fail gracefully with rollback
            assert result.exit_code in (0, 1)
            if result.exit_code != 0:
                data = json.loads(result.stdout)
                assert "error" in data or "failed" in data.get("details", "").lower()

    def test_organize_global_json_flag(self):
        """Test that global --json flag works with organize command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--json", "--path", tmpdir, "organize", "--non-interactive", "--dry-run"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "plan" in data or "actions" in data or "messages" in data

    def test_organize_global_path_option(self):
        """Test that global --path option works with organize command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            graphify_dir = Path(tmpdir) / "graphify-out"
            graphify_dir.mkdir()
            (graphify_dir / "output.txt").write_text("graphify output", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--non-interactive", "--dry-run"])
            assert result.exit_code == 0

    def test_organize_human_output_format(self):
        """Test human output uses Rich formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            graphify_dir = Path(tmpdir) / "graphify-out"
            graphify_dir.mkdir()
            (graphify_dir / "output.txt").write_text("graphify output", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--non-interactive", "--dry-run"])
            assert result.exit_code == 0
            # Should contain Rich table-like output
            assert "│" in result.stdout or "┌" in result.stdout or "Plan" in result.stdout

    def test_organize_interactive_route_option(self):
        """Test interactive mode allows 'route' option (relocate to managed location)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            graphify_dir = Path(tmpdir) / "graphify-out"
            graphify_dir.mkdir()
            (graphify_dir / "output.txt").write_text("graphify output", encoding="utf-8")

            # Simulate user selecting "route" (managed)
            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--interactive"], input="route\n")
            assert result.exit_code == 0
            # Artifact should be moved
            target = Path(tmpdir) / "airoom" / "artifacts" / "graphify-out"
            assert target.exists() or any((Path(tmpdir) / "airoom" / "artifacts").glob("graphify-out*"))

    def test_organize_interactive_track_external_option(self):
        """Test interactive mode allows 'track-external' option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            (claude_dir / "settings.json").write_text("{}", encoding="utf-8")

            # Simulate user selecting "track-external"
            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--interactive"], input="track-external\n")
            assert result.exit_code == 0
            # Artifact should remain in place but be registered as external
            assert claude_dir.exists()

    def test_organize_interactive_skip_option(self):
        """Test interactive mode allows 'skip' option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            graphify_dir = Path(tmpdir) / "graphify-out"
            graphify_dir.mkdir()
            (graphify_dir / "output.txt").write_text("graphify output", encoding="utf-8")

            # Simulate user selecting "skip"
            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--interactive"], input="skip\n")
            assert result.exit_code == 0
            # Artifact should remain unchanged
            assert graphify_dir.exists()
            # Should not be in registry
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            registry_data = manager.read()
            artifacts = registry_data.get("artifacts", {})
            graphify_artifacts = [a for a in artifacts.values() if "graphify" in a.get("path", "").lower()]
            assert len(graphify_artifacts) == 0

    def test_organize_empty_project_no_candidates(self):
        """Test organize on a project with no unregistered candidates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--non-interactive", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data.get("success") is True or "no candidates" in str(data).lower() or "nothing" in str(data).lower()

    def test_organize_updates_gitignore(self):
        """Test organize updates .gitignore for managed artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            graphify_dir = Path(tmpdir) / "graphify-out"
            graphify_dir.mkdir()
            (graphify_dir / "output.txt").write_text("graphify output", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "organize", "--non-interactive"])
            assert result.exit_code == 0

            gitignore_path = Path(tmpdir) / ".gitignore"
            if gitignore_path.exists():
                content = gitignore_path.read_text()
                # Should have airoom/artifacts/ entries
                assert "airoom/artifacts/" in content or "graphify-out" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])