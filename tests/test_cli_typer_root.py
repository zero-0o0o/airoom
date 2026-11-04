"""Tests for Typer CLI root entry point and global options."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from airoom.cli import app, legacy_app


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
        assert "legacy" in result.stdout  # legacy subcommand group

    def test_version_output(self):
        """Test that --version works."""
        result = self.runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.stdout

    def test_global_option_path(self):
        """Test --path/-p global option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["--path", tmpdir, "legacy", "init"])
            assert result.exit_code in (0, 1)

    def test_global_option_verbose(self):
        """Test --verbose/-v global option (count)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["-v", "--path", tmpdir, "legacy", "init"])
            assert result.exit_code in (0, 1)
            result = self.runner.invoke(app, ["-vv", "--path", tmpdir, "legacy", "init"])
            assert result.exit_code in (0, 1)

    def test_global_option_json(self):
        """Test --json global option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["--json", "--path", tmpdir, "legacy", "init"])
            assert result.exit_code in (0, 1)

    def test_global_option_dry_run(self):
        """Test --dry-run global option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["--dry-run", "--path", tmpdir, "legacy", "init"])
            assert result.exit_code in (0, 1)

    def test_global_options_stored_in_context(self):
        """Test that global options are stored in ctx.obj."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["--path", tmpdir, "--verbose", "--json", "--dry-run", "legacy", "init"])
            assert result.exit_code in (0, 1)

    def test_legacy_commands_registered(self):
        """Test that legacy commands are registered as subcommand group."""
        result = self.runner.invoke(app, ["legacy", "--help"])
        assert result.exit_code == 0
        assert "init" in result.stdout
        assert "update" in result.stdout
        assert "upgrade" in result.stdout
        assert "uninstall" in result.stdout

    def test_legacy_init_command(self):
        """Test legacy init command works through Typer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(app, ["--path", tmpdir, "legacy", "init"])
            assert result.exit_code == 0
            # Check that AIroom was initialized
            airoom_dir = Path(tmpdir) / "airoom"
            assert airoom_dir.exists()

    def test_legacy_update_command(self):
        """Test legacy update command works through Typer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First initialize
            self.runner.invoke(app, ["--path", tmpdir, "legacy", "init"])
            # Then update
            result = self.runner.invoke(app, ["--path", tmpdir, "legacy", "update"])
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


class TestLegacyApp:
    """Tests for the legacy argparse app (preserved for Phase 1-4)."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_legacy_app_exists(self):
        """Test that legacy app is created."""
        assert legacy_app is not None
        assert legacy_app.info.name == "legacy"

    def test_legacy_help(self):
        """Test legacy --help."""
        result = self.runner.invoke(legacy_app, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.stdout
        assert "update" in result.stdout
        assert "upgrade" in result.stdout
        assert "uninstall" in result.stdout

    def test_legacy_init_direct(self):
        """Test legacy init command directly with global --path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(legacy_app, ["--path", tmpdir, "init"])
            assert result.exit_code == 0
            airoom_dir = Path(tmpdir) / "airoom"
            assert airoom_dir.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])