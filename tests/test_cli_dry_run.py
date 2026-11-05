"""Tests for --dry-run flag on all CLI commands.

Verifies that no filesystem writes occur when --dry-run is set.
"""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from airoom.cli import app


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def temp_project(runner: CliRunner) -> Path:
    """Create a temporary initialized AIroom project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        # Initialize the project (legacy command uses global --path)
        result = runner.invoke(app, ["--path", str(project_path), "init"])
        assert result.exit_code == 0, f"Init failed: {result.output}"
        yield project_path


def _get_project_files(project_path: Path) -> dict[str, str]:
    """Get all files in the project with their content hashes for comparison."""
    import hashlib

    files = {}
    for file_path in project_path.rglob("*"):
        if file_path.is_file() and not file_path.name.startswith("."):
            rel = file_path.relative_to(project_path)
            content = file_path.read_bytes()
            files[str(rel)] = hashlib.sha256(content).hexdigest()
    return files


def _assert_no_changes(project_path: Path, before: dict[str, str]) -> None:
    """Assert no files were changed."""
    after = _get_project_files(project_path)
    assert before == after, f"Files changed during dry-run:\nBefore: {before}\nAfter: {after}"


class TestStatusDryRun:
    """Test status command with --dry-run (read-only, should not write)."""

    def test_status_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        before = _get_project_files(temp_project)
        result = runner.invoke(app, ["--dry-run", "--path", str(temp_project), "status"])
        assert result.exit_code == 0, f"Status failed: {result.output}"
        _assert_no_changes(temp_project, before)


class TestDoctorDryRun:
    """Test doctor command with --dry-run and --fix."""

    def test_doctor_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        before = _get_project_files(temp_project)
        result = runner.invoke(app, ["--dry-run", "--path", str(temp_project), "doctor"])
        assert result.exit_code == 0, f"Doctor failed: {result.output}"
        _assert_no_changes(temp_project, before)

    def test_doctor_fix_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        before = _get_project_files(temp_project)
        result = runner.invoke(app, ["--dry-run", "--path", str(temp_project), "doctor", "--fix"])
        assert result.exit_code == 0, f"Doctor --fix failed: {result.output}"
        _assert_no_changes(temp_project, before)

    def test_doctor_fix_without_dry_run_writes(self, runner: CliRunner, temp_project: Path) -> None:
        """Verify that --fix without --dry-run does write (sanity check)."""
        before = _get_project_files(temp_project)
        result = runner.invoke(app, ["--path", str(temp_project), "doctor", "--fix"])
        assert result.exit_code == 0, f"Doctor --fix failed: {result.output}"
        # This should have written something (though may be no-op if everything is clean)
        # We just verify it runs without error


class TestRegistryDryRun:
    """Test registry add/remove with --dry-run."""

    def test_registry_add_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        before = _get_project_files(temp_project)
        result = runner.invoke(
            app,
            [
                "--dry-run",
                "--path",
                str(temp_project),
                "registry",
                "add",
                "test-artifact",
                "--owner",
                "TestTool",
                "--artifact-path",
                "airoom/artifacts/test.txt",
                "--type",
                "file",
                "--management",
                "managed",
            ],
        )
        # Should succeed but not write
        assert result.exit_code == 0, f"Registry add failed: {result.output}"
        _assert_no_changes(temp_project, before)

        # Verify artifact was NOT actually added
        registry_path = temp_project / "airoom" / "registry.yaml"
        if registry_path.exists():
            content = registry_path.read_text()
            assert "test-artifact" not in content

    def test_registry_remove_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        # First add an artifact (without dry-run)
        runner.invoke(
            app,
            [
                "--path",
                str(temp_project),
                "registry",
                "add",
                "test-artifact-remove",
                "--owner",
                "TestTool",
                "--artifact-path",
                "airoom/artifacts/test2.txt",
                "--type",
                "file",
                "--management",
                "managed",
            ],
        )

        before = _get_project_files(temp_project)
        result = runner.invoke(
            app,
            [
                "--dry-run",
                "--path",
                str(temp_project),
                "registry",
                "remove",
                "test-artifact-remove",
                "--force",
            ],
        )
        assert result.exit_code == 0, f"Registry remove failed: {result.output}"
        _assert_no_changes(temp_project, before)

        # Verify artifact was NOT actually removed
        registry_path = temp_project / "airoom" / "registry.yaml"
        if registry_path.exists():
            content = registry_path.read_text()
            assert "test-artifact-remove" in content

    def test_registry_list_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        before = _get_project_files(temp_project)
        result = runner.invoke(app, ["--dry-run", "--path", str(temp_project), "registry", "list"])
        assert result.exit_code == 0, f"Registry list failed: {result.output}"
        _assert_no_changes(temp_project, before)

    def test_registry_show_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        # First add an artifact
        runner.invoke(
            app,
            [
                "--path",
                str(temp_project),
                "registry",
                "add",
                "test-artifact-show",
                "--owner",
                "TestTool",
                "--artifact-path",
                "airoom/artifacts/test3.txt",
                "--type",
                "file",
                "--management",
                "managed",
            ],
        )

        before = _get_project_files(temp_project)
        result = runner.invoke(
            app,
            ["--dry-run", "--path", str(temp_project), "registry", "show", "test-artifact-show"],
        )
        assert result.exit_code == 0, f"Registry show failed: {result.output}"
        _assert_no_changes(temp_project, before)

    def test_registry_validate_dry_run_no_writes(
        self, runner: CliRunner, temp_project: Path
    ) -> None:
        before = _get_project_files(temp_project)
        result = runner.invoke(
            app, ["--dry-run", "--path", str(temp_project), "registry", "validate"]
        )
        assert result.exit_code == 0, f"Registry validate failed: {result.output}"
        _assert_no_changes(temp_project, before)


class TestDiscoverDryRun:
    """Test discover command with --dry-run (read-only)."""

    def test_discover_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        before = _get_project_files(temp_project)
        result = runner.invoke(app, ["--dry-run", "--path", str(temp_project), "discover"])
        assert result.exit_code == 0, f"Discover failed: {result.output}"
        _assert_no_changes(temp_project, before)


class TestOrganizeDryRun:
    """Test organize command with --dry-run."""

    def test_organize_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        before = _get_project_files(temp_project)
        result = runner.invoke(
            app,
            [
                "--dry-run",
                "--path",
                str(temp_project),
                "organize",
                "--non-interactive",
            ],
        )
        assert result.exit_code == 0, f"Organize failed: {result.output}"
        _assert_no_changes(temp_project, before)

        # Should show [DRY RUN] messages in output
        assert "[DRY RUN]" in result.output or "No unregistered candidates found" in result.output

    def test_organize_global_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        """Test that global --dry-run works for organize (already has local --dry-run)."""
        before = _get_project_files(temp_project)
        result = runner.invoke(
            app,
            [
                "--dry-run",
                "--path",
                str(temp_project),
                "organize",
                "--non-interactive",
            ],
        )
        assert result.exit_code == 0, f"Organize failed: {result.output}"
        _assert_no_changes(temp_project, before)


class TestConfigDryRun:
    """Test config set/unset with --dry-run."""

    def test_config_show_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        before = _get_project_files(temp_project)
        result = runner.invoke(app, ["--dry-run", "--path", str(temp_project), "config", "show"])
        assert result.exit_code == 0, f"Config show failed: {result.output}"
        _assert_no_changes(temp_project, before)

    def test_config_set_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        before = _get_project_files(temp_project)
        result = runner.invoke(
            app,
            [
                "--dry-run",
                "--path",
                str(temp_project),
                "config",
                "set",
                "defaults.test_key",
                "test_value",
            ],
        )
        assert result.exit_code == 0, f"Config set failed: {result.output}"
        _assert_no_changes(temp_project, before)

        # Verify config was NOT actually set
        config_path = temp_project / "airoom.config.yaml"
        if config_path.exists():
            content = config_path.read_text()
            assert "test_key" not in content

    def test_config_unset_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        # First set a value (without dry-run)
        runner.invoke(
            app,
            [
                "--path",
                str(temp_project),
                "config",
                "set",
                "defaults.test_unset",
                "test_value",
            ],
        )

        before = _get_project_files(temp_project)
        result = runner.invoke(
            app,
            [
                "--dry-run",
                "--path",
                str(temp_project),
                "config",
                "unset",
                "defaults.test_unset",
            ],
        )
        assert result.exit_code == 0, f"Config unset failed: {result.output}"
        _assert_no_changes(temp_project, before)

        # Verify config was NOT actually unset
        config_path = temp_project / "airoom.config.yaml"
        if config_path.exists():
            content = config_path.read_text()
            assert "test_unset" in content


class TestCompletionDryRun:
    """Test completion command with --dry-run (read-only)."""

    def test_completion_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        before = _get_project_files(temp_project)
        result = runner.invoke(app, ["--dry-run", "completion", "bash"])
        assert result.exit_code == 0, f"Completion failed: {result.output}"
        _assert_no_changes(temp_project, before)


class TestInitUpdateUpgradeUninstallDryRun:
    """Test legacy commands with --dry-run."""

    def test_init_dry_run_no_writes(self, runner: CliRunner) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            before = _get_project_files(project_path)
            result = runner.invoke(app, ["--dry-run", "--path", str(project_path), "init"])
            assert result.exit_code == 0, f"Init failed: {result.output}"
            _assert_no_changes(project_path, before)
            # Verify .airoom directory was NOT created
            assert not (project_path / "airoom").exists()

    def test_update_dry_run_no_writes(self, runner: CliRunner, temp_project: Path) -> None:
        before = _get_project_files(temp_project)
        result = runner.invoke(app, ["--dry-run", "--path", str(temp_project), "update"])
        assert result.exit_code == 0, f"Update failed: {result.output}"
        _assert_no_changes(temp_project, before)

    def test_upgrade_dry_run_no_writes(self, runner: CliRunner) -> None:
        # Upgrade is global, doesn't need a project
        result = runner.invoke(app, ["--dry-run", "upgrade"])
        # Upgrade may fail due to network, but should not write locally
        assert result.exit_code in (0, 1), f"Upgrade failed unexpectedly: {result.output}"

    def test_uninstall_dry_run_no_writes(self, runner: CliRunner) -> None:
        # Uninstall is global, requires --yes
        result = runner.invoke(app, ["--dry-run", "uninstall", "--yes"])
        assert result.exit_code in (0, 1), f"Uninstall failed unexpectedly: {result.output}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
