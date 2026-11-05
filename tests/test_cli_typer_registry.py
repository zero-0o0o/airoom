"""Tests for the `airoom registry` Typer command."""

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from airoom.cli import app


class TestRegistryCommand:
    """Tests for the registry command group."""

    def setup_method(self):
        self.runner = CliRunner()

    def _init_project(self, tmpdir: str) -> Path:
        """Initialize an AIroom project in a temp directory."""
        result = self.runner.invoke(app, ["--path", tmpdir, "init"])
        assert result.exit_code == 0
        return Path(tmpdir)

    # =========================================================================
    # registry list
    # =========================================================================

    def test_registry_list_command_exists(self):
        """Test that the registry list command is registered."""
        result = self.runner.invoke(app, ["registry", "list", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout.lower()

    def test_registry_list_empty(self):
        """Test registry list on a fresh project (no artifacts)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "registry", "list"])
            assert result.exit_code == 0
            assert "No artifacts" in result.stdout or "empty" in result.stdout.lower()

    def test_registry_list_with_artifacts(self):
        """Test registry list shows artifacts in human format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Add an artifact via registry manager
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            manager.add_artifact("test-artifact", {
                "owner": "test-tool",
                "path": "airoom/artifacts/test-artifact",
                "type": "file",
                "management": "managed",
                "status": "active"
            })
            
            result = self.runner.invoke(app, ["--path", tmpdir, "registry", "list"])
            assert result.exit_code == 0
            assert "test-artifact" in result.stdout
            assert "test-tool" in result.stdout
            assert "managed" in result.stdout
            assert "active" in result.stdout

    def test_registry_list_json_output(self):
        """Test registry list with --json flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "registry", "list", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "artifacts" in data
            assert isinstance(data["artifacts"], list)
            assert len(data["artifacts"]) == 0

    def test_registry_list_json_output_with_artifacts(self):
        """Test registry list JSON output with artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            manager.add_artifact("test-artifact", {
                "owner": "test-tool",
                "path": "airoom/artifacts/test-artifact",
                "type": "file",
                "management": "managed",
                "status": "active"
            })
            
            result = self.runner.invoke(app, ["--path", tmpdir, "registry", "list", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert len(data["artifacts"]) == 1
            artifact = data["artifacts"][0]
            assert artifact["id"] == "test-artifact"
            assert artifact["owner"] == "test-tool"
            assert artifact["path"] == "airoom/artifacts/test-artifact"
            assert artifact["type"] == "file"
            assert artifact["management"] == "managed"
            assert artifact["status"] == "active"

    def test_registry_list_global_json_flag(self):
        """Test that global --json flag works with registry list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--json", "--path", tmpdir, "registry", "list"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "artifacts" in data

    def test_registry_list_global_path_option(self):
        """Test that global --path option works with registry list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "registry", "list"])
            assert result.exit_code == 0

    # =========================================================================
    # registry add
    # =========================================================================

    def test_registry_add_command_exists(self):
        """Test that the registry add command is registered."""
        result = self.runner.invoke(app, ["registry", "add", "--help"])
        assert result.exit_code == 0
        assert "add" in result.stdout.lower()
        assert "--owner" in result.stdout
        assert "--artifact-path" in result.stdout
        assert "--type" in result.stdout
        assert "--management" in result.stdout
        assert "--status" in result.stdout

    def test_registry_add_minimal_valid(self):
        """Test adding a minimal valid artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "my-artifact",
                "--owner", "my-tool",
                "--artifact-path", "airoom/artifacts/my-artifact",
                "--type", "file",
                "--management", "managed"
            ])
            assert result.exit_code == 0
            assert "Added artifact" in result.stdout or "added" in result.stdout.lower()
            
            # Verify it was added
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            data = manager.read()
            assert "my-artifact" in data["artifacts"]
            assert data["artifacts"]["my-artifact"]["owner"] == "my-tool"

    def test_registry_add_with_all_options(self):
        """Test adding artifact with all optional fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "my-artifact",
                "--owner", "my-tool",
                "--artifact-path", "airoom/artifacts/my-artifact",
                "--type", "directory",
                "--management", "managed",
                "--status", "inactive",
                "--original-path", "external/original",
                "--version", "1.0.0",
                "--output-setting", "custom"
            ])
            assert result.exit_code == 0
            
            # Verify all fields
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            data = manager.read()
            artifact = data["artifacts"]["my-artifact"]
            assert artifact["owner"] == "my-tool"
            assert artifact["path"] == "airoom/artifacts/my-artifact"
            assert artifact["type"] == "directory"
            assert artifact["management"] == "managed"
            assert artifact["status"] == "inactive"
            assert artifact["original_path"] == "external/original"
            assert artifact["version"] == "1.0.0"
            assert artifact["output_setting"] == "custom"

    def test_registry_add_external_artifact(self):
        """Test adding an external artifact (not under airoom/artifacts/)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "external-artifact",
                "--owner", "my-tool",
                "--artifact-path", "external/data/file.txt",
                "--type", "file",
                "--management", "external"
            ])
            assert result.exit_code == 0
            
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            data = manager.read()
            assert data["artifacts"]["external-artifact"]["management"] == "external"
            assert data["artifacts"]["external-artifact"]["path"] == "external/data/file.txt"

    def test_registry_add_managed_artifact_not_under_airoom_artifacts_fails(self):
        """Test that managed artifact must be under airoom/artifacts/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "bad-artifact",
                "--owner", "my-tool",
                "--artifact-path", "generated/output.txt",
                "--type", "file",
                "--management", "managed"
            ])
            assert result.exit_code != 0
            assert "must be under airoom/artifacts" in result.stdout or "managed artifact path" in result.stdout

    def test_registry_add_invalid_type_fails(self):
        """Test that invalid type is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "bad-artifact",
                "--owner", "my-tool",
                "--artifact-path", "airoom/artifacts/bad",
                "--type", "invalid",
                "--management", "managed"
            ])
            assert result.exit_code != 0
            assert "type must be file or directory" in result.stdout or "invalid" in result.stdout.lower()

    def test_registry_add_invalid_management_fails(self):
        """Test that invalid management is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "bad-artifact",
                "--owner", "my-tool",
                "--artifact-path", "airoom/artifacts/bad",
                "--type", "file",
                "--management", "invalid"
            ])
            assert result.exit_code != 0
            assert "management must be managed or external" in result.stdout or "invalid" in result.stdout.lower()

    def test_registry_add_invalid_status_fails(self):
        """Test that invalid status is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "bad-artifact",
                "--owner", "my-tool",
                "--artifact-path", "airoom/artifacts/bad",
                "--type", "file",
                "--management", "managed",
                "--status", "invalid"
            ])
            assert result.exit_code != 0
            assert "status must be active or inactive" in result.stdout or "invalid" in result.stdout.lower()

    def test_registry_add_missing_required_field_fails(self):
        """Test that missing required fields are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Missing --owner
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "bad-artifact",
                "--artifact-path", "airoom/artifacts/bad",
                "--type", "file",
                "--management", "managed"
            ])
            assert result.exit_code != 0
            assert "Missing option" in result.output or "required" in result.output.lower()

    def test_registry_add_duplicate_id_fails(self):
        """Test that duplicate artifact ID is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            manager.add_artifact("existing", {
                "owner": "tool", "path": "airoom/artifacts/existing",
                "type": "file", "management": "managed", "status": "active"
            })
            
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "existing",
                "--owner", "other-tool",
                "--artifact-path", "airoom/artifacts/other",
                "--type", "file",
                "--management", "managed"
            ])
            assert result.exit_code != 0
            assert "already exists" in result.stdout

    def test_registry_add_duplicate_path_fails(self):
        """Test that duplicate artifact path is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            manager.add_artifact("artifact1", {
                "owner": "tool1", "path": "airoom/artifacts/shared",
                "type": "file", "management": "managed", "status": "active"
            })
            
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "artifact2",
                "--owner", "tool2",
                "--artifact-path", "airoom/artifacts/shared",
                "--type", "file",
                "--management", "managed"
            ])
            assert result.exit_code != 0
            assert "duplicate artifact path" in result.stdout

    def test_registry_add_duplicate_external_path_fails(self):
        """Test that duplicate external artifact path is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            manager.add_artifact("artifact1", {
                "owner": "tool1", "path": "external/shared.txt",
                "type": "file", "management": "external", "status": "active"
            })
            
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "artifact2",
                "--owner", "tool2",
                "--artifact-path", "external/shared.txt",
                "--type", "file",
                "--management", "external"
            ])
            assert result.exit_code != 0
            assert "duplicate artifact path" in result.stdout

    def test_registry_add_invalid_artifact_id_fails(self):
        """Test that invalid artifact ID (with slash) is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "invalid/id",
                "--owner", "my-tool",
                "--artifact-path", "airoom/artifacts/bad",
                "--type", "file",
                "--management", "managed"
            ])
            assert result.exit_code != 0
            assert "invalid artifact id" in result.stdout

    def test_registry_add_invalid_path_fails(self):
        """Test that invalid paths are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Absolute path
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "bad-artifact",
                "--owner", "my-tool",
                "--artifact-path", "/absolute/path",
                "--type", "file",
                "--management", "external"
            ])
            assert result.exit_code != 0
            assert "must not be absolute" in result.stdout or "absolute" in result.stdout.lower()

    def test_registry_add_path_with_double_dot_fails(self):
        """Test that path with .. is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "bad-artifact",
                "--owner", "my-tool",
                "--artifact-path", "airoom/../outside",
                "--type", "file",
                "--management", "external"
            ])
            assert result.exit_code != 0
            assert "must not be absolute or contain" in result.stdout or ".." in result.stdout

    def test_registry_add_path_with_backslash_fails(self):
        """Test that path with backslash is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "bad-artifact",
                "--owner", "my-tool",
                "--artifact-path", "airoom\\artifacts\\bad",
                "--type", "file",
                "--management", "external"
            ])
            assert result.exit_code != 0
            assert "must not be absolute or contain" in result.stdout or "backslash" in result.stdout.lower()

    def test_registry_add_empty_owner_fails(self):
        """Test that empty owner is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "bad-artifact",
                "--owner", "",
                "--artifact-path", "airoom/artifacts/bad",
                "--type", "file",
                "--management", "managed"
            ])
            assert result.exit_code != 0

    def test_registry_add_json_output(self):
        """Test registry add with --json flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "add", "my-artifact",
                "--owner", "my-tool",
                "--artifact-path", "airoom/artifacts/my-artifact",
                "--type", "file",
                "--management", "managed",
                "--json"
            ])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["status"] == "ok" or data.get("added") == "my-artifact"
            assert "my-artifact" in str(data)

    # =========================================================================
    # registry remove
    # =========================================================================

    def test_registry_remove_command_exists(self):
        """Test that the registry remove command is registered."""
        result = self.runner.invoke(app, ["registry", "remove", "--help"])
        assert result.exit_code == 0
        assert "remove" in result.stdout.lower()
        assert "--force" in result.stdout

    def test_registry_remove_existing_artifact(self):
        """Test removing an existing artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            manager.add_artifact("to-remove", {
                "owner": "tool", "path": "airoom/artifacts/to-remove",
                "type": "file", "management": "managed", "status": "active"
            })
            
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "remove", "to-remove", "--force"
            ])
            assert result.exit_code == 0
            assert "Removed artifact" in result.stdout or "removed" in result.stdout.lower()
            
            data = manager.read()
            assert "to-remove" not in data["artifacts"]

    def test_registry_remove_nonexistent_fails(self):
        """Test removing nonexistent artifact fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "remove", "nonexistent", "--force"
            ])
            assert result.exit_code != 0
            assert "not found" in result.stdout

    def test_registry_remove_without_force_prompts(self):
        """Test that remove without --force prompts for confirmation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            manager.add_artifact("to-remove", {
                "owner": "tool", "path": "airoom/artifacts/to-remove",
                "type": "file", "management": "managed", "status": "active"
            })
            
            # Simulate user saying 'n' (no)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "remove", "to-remove"
            ], input="n\n")
            assert result.exit_code != 0
            assert "cancelled" in result.stdout.lower() or "abort" in result.stdout.lower()
            
            # Artifact should still exist
            data = manager.read()
            assert "to-remove" in data["artifacts"]

    def test_registry_remove_without_force_confirms_yes(self):
        """Test that remove without --force proceeds when user says 'y'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            manager.add_artifact("to-remove", {
                "owner": "tool", "path": "airoom/artifacts/to-remove",
                "type": "file", "management": "managed", "status": "active"
            })
            
            # Simulate user saying 'y' (yes)
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "remove", "to-remove"
            ], input="y\n")
            assert result.exit_code == 0
            assert "Removed artifact" in result.stdout or "removed" in result.stdout.lower()
            
            data = manager.read()
            assert "to-remove" not in data["artifacts"]

    def test_registry_remove_json_output(self):
        """Test registry remove with --json flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            manager.add_artifact("to-remove", {
                "owner": "tool", "path": "airoom/artifacts/to-remove",
                "type": "file", "management": "managed", "status": "active"
            })
            
            result = self.runner.invoke(app, [
                "--path", tmpdir, "registry", "remove", "to-remove", "--force", "--json"
            ])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["status"] == "ok" or data.get("removed") == "to-remove"

    # =========================================================================
    # registry validate
    # =========================================================================

    def test_registry_validate_command_exists(self):
        """Test that the registry validate command is registered."""
        result = self.runner.invoke(app, ["registry", "validate", "--help"])
        assert result.exit_code == 0
        assert "validate" in result.stdout.lower()

    def test_registry_validate_valid_registry(self):
        """Test validate on a valid registry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "registry", "validate"])
            assert result.exit_code == 0
            assert "valid" in result.stdout.lower() or "ok" in result.stdout.lower()

    def test_registry_validate_json_output(self):
        """Test registry validate with --json flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "registry", "validate", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["valid"] is True
            assert data["errors"] == []

    def test_registry_validate_invalid_registry(self):
        """Test validate detects invalid registry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Corrupt the registry
            registry_file = Path(tmpdir) / "airoom" / "registry.yaml"
            registry_file.write_text("version: 2\nartifacts: {}\ntools: {}\n", encoding="utf-8")
            
            result = self.runner.invoke(app, ["--path", tmpdir, "registry", "validate"])
            assert result.exit_code != 0
            assert "invalid" in result.stdout.lower() or "error" in result.stdout.lower()

    def test_registry_validate_invalid_registry_json(self):
        """Test validate invalid registry with --json flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            registry_file = Path(tmpdir) / "airoom" / "registry.yaml"
            registry_file.write_text("version: 2\nartifacts: {}\ntools: {}\n", encoding="utf-8")
            
            result = self.runner.invoke(app, ["--path", tmpdir, "registry", "validate", "--json"])
            assert result.exit_code != 0
            data = json.loads(result.stdout)
            assert data["valid"] is False
            assert len(data["errors"]) > 0

    # =========================================================================
    # registry show
    # =========================================================================

    def test_registry_show_command_exists(self):
        """Test that the registry show command is registered."""
        result = self.runner.invoke(app, ["registry", "show", "--help"])
        assert result.exit_code == 0
        assert "show" in result.stdout.lower()

    def test_registry_show_existing_artifact(self):
        """Test showing an existing artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            manager.add_artifact("my-artifact", {
                "owner": "my-tool",
                "path": "airoom/artifacts/my-artifact",
                "type": "file",
                "management": "managed",
                "status": "active",
                "original_path": "external/original",
                "version": "1.0.0"
            })
            
            result = self.runner.invoke(app, ["--path", tmpdir, "registry", "show", "my-artifact"])
            assert result.exit_code == 0
            assert "my-artifact" in result.stdout
            assert "my-tool" in result.stdout
            assert "airoom/artifacts/my-artifact" in result.stdout
            assert "managed" in result.stdout
            assert "active" in result.stdout
            assert "external/original" in result.stdout
            assert "1.0.0" in result.stdout

    def test_registry_show_nonexistent_fails(self):
        """Test showing nonexistent artifact fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "registry", "show", "nonexistent"])
            assert result.exit_code != 0
            assert "not found" in result.stdout

    def test_registry_show_json_output(self):
        """Test registry show with --json flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            manager.add_artifact("my-artifact", {
                "owner": "my-tool",
                "path": "airoom/artifacts/my-artifact",
                "type": "file",
                "management": "managed",
                "status": "active"
            })
            
            result = self.runner.invoke(app, ["--path", tmpdir, "registry", "show", "my-artifact", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["id"] == "my-artifact"
            assert data["owner"] == "my-tool"
            assert data["path"] == "airoom/artifacts/my-artifact"
            assert data["type"] == "file"
            assert data["management"] == "managed"
            assert data["status"] == "active"

    def test_registry_show_external_artifact(self):
        """Test showing an external artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            from airoom.core.project import Project
            from airoom.core.registry import RegistryManager
            project = Project(Path(tmpdir))
            manager = RegistryManager(project)
            manager.add_artifact("external-artifact", {
                "owner": "my-tool",
                "path": "external/data.txt",
                "type": "file",
                "management": "external",
                "status": "inactive"
            })
            
            result = self.runner.invoke(app, ["--path", tmpdir, "registry", "show", "external-artifact"])
            assert result.exit_code == 0
            assert "external-artifact" in result.stdout
            assert "external" in result.stdout
            assert "inactive" in result.stdout

    # =========================================================================
    # Not initialized project handling
    # =========================================================================

    def test_registry_commands_fail_on_uninitialized_project(self):
        """Test all registry commands fail gracefully on uninitialized project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for subcmd in ["list", "add test --owner t --artifact-path p --type file --management managed",
                          "remove test --force", "validate", "show test"]:
                cmd = ["--path", tmpdir, "registry"] + subcmd.split()
                result = self.runner.invoke(app, cmd)
                assert result.exit_code != 0
                assert "not initialized" in result.stdout.lower() or "not found" in result.stdout.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])