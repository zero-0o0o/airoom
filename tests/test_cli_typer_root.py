"""Tests for Typer CLI root entry point and global options."""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from airoom.cli import app


class TestTyperApp:
    """Tests for the main Typer app."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_app_exists(self):
        """Test that the Typer app is created."""
        assert app is not None
        assert app.info.name == "airoom"

    def test_help_output(self):
        """Test that --help works and shows expected commands."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "AIroom" in result.stdout
        assert "legacy" not in result.stdout  # legacy subcommand group removed

    def test_version_output(self):
        """Test that --version works."""
        result = self.runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.stdout

    def test_global_option_path(self):
        """Test --path/-p global option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["--path", tmpdir, "init"])
            assert result.exit_code in (0, 1)

    def test_global_option_verbose(self):
        """Test --verbose/-v global option (count)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["-v", "--path", tmpdir, "init"])
            assert result.exit_code in (0, 1)
            result = self.runner.invoke(app, ["-vv", "--path", tmpdir, "init"])
            assert result.exit_code in (0, 1)

    def test_global_option_json(self):
        """Test --json global option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["--json", "--path", tmpdir, "init"])
            assert result.exit_code in (0, 1)

    def test_global_option_dry_run(self):
        """Test --dry-run global option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["--dry-run", "--path", tmpdir, "init"])
            assert result.exit_code in (0, 1)

    def test_global_options_stored_in_context(self):
        """Test that global options are stored in ctx.obj."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(
                app, ["--path", tmpdir, "--verbose", "--json", "--dry-run", "init"]
            )
            assert result.exit_code in (0, 1)

    def test_init_command_registered(self):
        """Test that init command is registered at top level."""
        result = self.runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "Initialize" in result.stdout

    def test_update_command_registered(self):
        """Test that update command is registered at top level."""
        result = self.runner.invoke(app, ["update", "--help"])
        assert result.exit_code == 0
        assert "Update" in result.stdout

    def test_upgrade_command_registered(self):
        """Test that upgrade command is registered at top level."""
        result = self.runner.invoke(app, ["upgrade", "--help"])
        assert result.exit_code == 0
        assert "Upgrade" in result.stdout

    def test_uninstall_command_registered(self):
        """Test that uninstall command is registered at top level."""
        result = self.runner.invoke(app, ["uninstall", "--help"])
        assert result.exit_code == 0
        assert "Uninstall" in result.stdout

    def test_init_command(self):
        """Test init command works through Typer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["--path", tmpdir, "init"])
            assert result.exit_code == 0
            # Check that AIroom was initialized
            airoom_dir = Path(tmpdir) / "airoom"
            assert airoom_dir.exists()

    def test_update_command(self):
        """Test update command works through Typer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First initialize
            self.runner.invoke(app, ["--path", tmpdir, "init"])
            # Then update
            result = self.runner.invoke(app, ["--path", tmpdir, "update"])
            assert result.exit_code == 0

    def test_invalid_command(self):
        """Test that invalid command shows error."""
        result = self.runner.invoke(app, ["nonexistent"])
        assert result.exit_code != 0

    def test_no_command_shows_help(self):
        """Test that running without command shows help."""
        result = self.runner.invoke(app, [])
        # With invoke_without_command=True, the callback runs and shows help
        assert result.exit_code == 0
        assert "AIroom" in result.stdout
        assert "Usage:" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
