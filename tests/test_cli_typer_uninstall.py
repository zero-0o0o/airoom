"""Tests for airoom uninstall command (Typer-based)."""

import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from airoom.cli import app
from airoom.commands_typer.uninstall import (
    get_pipx_path,
    is_installed_via_pipx,
    uninstall_via_pipx,
    verify_uninstallation,
    is_interactive,
    prompt_confirmation,
)


class TestPipxDetection:
    """Tests for pipx detection functions."""

    @patch("shutil.which")
    def test_get_pipx_path_found(self, mock_which):
        """Test finding pipx path."""
        mock_which.return_value = "/usr/local/bin/pipx"
        path = get_pipx_path()
        assert path == "/usr/local/bin/pipx"

    @patch("shutil.which")
    def test_get_pipx_path_not_found(self, mock_which):
        """Test pipx not found."""
        mock_which.return_value = None
        path = get_pipx_path()
        assert path is None

    @patch("subprocess.run")
    def test_is_installed_via_pipx_true(self, mock_run):
        """Test detecting pipx installation."""
        mock_run.return_value = MagicMock(returncode=0, stdout='{"venvs":{"airoom":{}}}')
        assert is_installed_via_pipx() is True

    @patch("subprocess.run")
    def test_is_installed_via_pipx_false(self, mock_run):
        """Test detecting non-pipx installation."""
        mock_run.return_value = MagicMock(returncode=0, stdout='{"venvs":{"not-airoom":{}}}')
        assert is_installed_via_pipx() is False


class TestUninstallViaPipx:
    """Tests for pipx uninstall."""

    @patch("subprocess.run")
    def test_uninstall_via_pipx_success(self, mock_run):
        """Test successful pipx uninstall."""
        mock_run.return_value = MagicMock(returncode=0, stdout="uninstalled", stderr="")
        result = uninstall_via_pipx()
        assert result is True

    @patch("subprocess.run")
    def test_uninstall_via_pipx_failure(self, mock_run):
        """Test pipx uninstall failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result = uninstall_via_pipx()
        assert result is False

    @patch("subprocess.run")
    def test_uninstall_via_pipx_timeout(self, mock_run):
        """Test pipx uninstall timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("pipx", 60)
        result = uninstall_via_pipx()
        assert result is False


class TestVerifyUninstallation:
    """Tests for uninstallation verification."""

    @patch("subprocess.run")
    def test_verify_uninstallation_success(self, mock_run):
        """Test successful verification (airoom not found)."""
        mock_run.return_value = MagicMock(returncode=0, stdout='{"venvs":{}}')
        result = verify_uninstallation()
        assert result is True

    @patch("subprocess.run")
    def test_verify_uninstallation_still_installed(self, mock_run):
        """Test verification when airoom still installed."""
        mock_run.return_value = MagicMock(returncode=0, stdout='{"venvs":{"airoom":{}}}')
        result = verify_uninstallation()
        assert result is False


class TestInteractiveDetection:
    """Tests for interactive terminal detection."""

    @patch("sys.stdin.isatty", return_value=True)
    def test_is_interactive_true(self, mock_isatty):
        """Test interactive terminal."""
        assert is_interactive() is True

    @patch("sys.stdin.isatty", return_value=False)
    def test_is_interactive_false(self, mock_isatty):
        """Test non-interactive terminal."""
        assert is_interactive() is False


class TestPromptConfirmation:
    """Tests for confirmation prompt."""

    @patch("builtins.input", side_effect=["y"])
    def test_prompt_confirmation_yes(self, mock_input):
        """Test user confirms with 'y'."""
        assert prompt_confirmation() is True

    @patch("builtins.input", side_effect=["yes"])
    def test_prompt_confirmation_yes_full(self, mock_input):
        """Test user confirms with 'yes'."""
        assert prompt_confirmation() is True

    @patch("builtins.input", side_effect=["n"])
    def test_prompt_confirmation_no(self, mock_input):
        """Test user declines with 'n'."""
        assert prompt_confirmation() is False

    @patch("builtins.input", side_effect=["no"])
    def test_prompt_confirmation_no_full(self, mock_input):
        """Test user declines with 'no'."""
        assert prompt_confirmation() is False

    @patch("builtins.input", side_effect=[""])
    def test_prompt_confirmation_empty_defaults_no(self, mock_input):
        """Test empty input defaults to no."""
        assert prompt_confirmation() is False

    @patch("builtins.input", side_effect=["invalid", "y"])
    def test_prompt_confirmation_reprompts_on_invalid(self, mock_input):
        """Test reprompt on invalid input."""
        assert prompt_confirmation() is True

    @patch("builtins.input", side_effect=EOFError)
    def test_prompt_confirmation_eof(self, mock_input):
        """Test EOF (Ctrl+D) cancels."""
        assert prompt_confirmation() is False

    @patch("builtins.input", side_effect=KeyboardInterrupt)
    def test_prompt_confirmation_interrupt(self, mock_input):
        """Test Ctrl+C cancels."""
        assert prompt_confirmation() is False


class TestTyperUninstallCommand:
    """Integration tests for the Typer uninstall command."""

    def run_uninstall(self, args: list[str] | None = None, global_args: list[str] | None = None, input_data: str | None = None) -> tuple[int, str]:
        """Run uninstall command."""
        runner = CliRunner()
        cmd = []
        if global_args:
            cmd.extend(global_args)
        cmd.append("uninstall")
        if args:
            cmd.extend(args)
        result = runner.invoke(app, cmd, input=input_data)
        return result.exit_code, result.output

    @patch("airoom.commands_typer.uninstall.get_pipx_path")
    @patch("airoom.commands_typer.uninstall.is_installed_via_pipx")
    def test_uninstall_pipx_not_found(self, mock_pipx_check, mock_pipx_path):
        """Test uninstall when pipx not found."""
        mock_pipx_path.return_value = None

        exit_code, output = self.run_uninstall(["--yes"])
        assert exit_code == 3
        assert "pipx not found" in output

    @patch("airoom.commands_typer.uninstall.get_pipx_path")
    @patch("airoom.commands_typer.uninstall.is_installed_via_pipx")
    def test_uninstall_not_via_pipx(self, mock_pipx_check, mock_pipx_path):
        """Test uninstall when not installed via pipx."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = False

        exit_code, output = self.run_uninstall(["--yes"])
        assert exit_code == 3
        assert "installed via pipx" in output.lower()

    @patch("airoom.commands_typer.uninstall.get_pipx_path")
    @patch("airoom.commands_typer.uninstall.is_installed_via_pipx")
    @patch("airoom.commands_typer.uninstall.uninstall_via_pipx")
    @patch("airoom.commands_typer.uninstall.verify_uninstallation")
    def test_uninstall_success(
        self, mock_verify, mock_uninstall, mock_pipx_check, mock_pipx_path
    ):
        """Test successful uninstall with --yes."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_uninstall.return_value = True
        mock_verify.return_value = True

        exit_code, output = self.run_uninstall(["--yes"])
        assert exit_code == 0
        mock_uninstall.assert_called_once()
        mock_verify.assert_called_once()
        assert "successfully uninstalled" in output.lower() or "uninstalled" in output.lower()

    @patch("airoom.commands_typer.uninstall.get_pipx_path")
    @patch("airoom.commands_typer.uninstall.is_installed_via_pipx")
    @patch("airoom.commands_typer.uninstall.is_interactive")
    @patch("airoom.commands_typer.uninstall.prompt_confirmation")
    @patch("airoom.commands_typer.uninstall.uninstall_via_pipx")
    @patch("airoom.commands_typer.uninstall.verify_uninstallation")
    def test_uninstall_confirmation_accepted(
        self,
        mock_verify,
        mock_uninstall,
        mock_prompt,
        mock_interactive,
        mock_pipx_check,
        mock_pipx_path,
    ):
        """Test uninstall with interactive confirmation accepted."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_interactive.return_value = True
        mock_prompt.return_value = True
        mock_uninstall.return_value = True
        mock_verify.return_value = True

        exit_code, output = self.run_uninstall([])
        assert exit_code == 0
        mock_prompt.assert_called_once()

    @patch("airoom.commands_typer.uninstall.get_pipx_path")
    @patch("airoom.commands_typer.uninstall.is_installed_via_pipx")
    @patch("airoom.commands_typer.uninstall.is_interactive")
    @patch("airoom.commands_typer.uninstall.prompt_confirmation")
    def test_uninstall_confirmation_declined(
        self, mock_prompt, mock_interactive, mock_pipx_check, mock_pipx_path
    ):
        """Test uninstall with confirmation declined."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_interactive.return_value = True
        mock_prompt.return_value = False

        exit_code, output = self.run_uninstall([])
        assert exit_code == 2
        mock_prompt.assert_called_once()
        assert "cancelled" in output.lower()

    @patch("airoom.commands_typer.uninstall.get_pipx_path")
    @patch("airoom.commands_typer.uninstall.is_installed_via_pipx")
    @patch("airoom.commands_typer.uninstall.is_interactive")
    def test_uninstall_non_interactive_without_yes(
        self, mock_interactive, mock_pipx_check, mock_pipx_path
    ):
        """Test uninstall in non-interactive mode without --yes."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_interactive.return_value = False

        exit_code, output = self.run_uninstall([])
        assert exit_code == 2
        assert "non-interactive" in output.lower() or "--yes" in output

    @patch("airoom.commands_typer.uninstall.get_pipx_path")
    @patch("airoom.commands_typer.uninstall.is_installed_via_pipx")
    @patch("airoom.commands_typer.uninstall.is_interactive")
    @patch("airoom.commands_typer.uninstall.uninstall_via_pipx")
    def test_uninstall_failure(
        self, mock_uninstall, mock_interactive, mock_pipx_check, mock_pipx_path
    ):
        """Test uninstall failure."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_uninstall.return_value = False

        exit_code, output = self.run_uninstall(["--yes"])
        assert exit_code == 1
        assert "failed" in output.lower()

    @patch("airoom.commands_typer.uninstall.get_pipx_path")
    @patch("airoom.commands_typer.uninstall.is_installed_via_pipx")
    @patch("airoom.commands_typer.uninstall.is_interactive")
    @patch("airoom.commands_typer.uninstall.uninstall_via_pipx")
    @patch("airoom.commands_typer.uninstall.verify_uninstallation")
    def test_uninstall_verification_fails(
        self, mock_verify, mock_uninstall, mock_interactive, mock_pipx_check, mock_pipx_path
    ):
        """Test uninstall when verification fails."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_uninstall.return_value = True
        mock_verify.return_value = False

        exit_code, output = self.run_uninstall(["--yes"])
        assert exit_code == 1
        assert "warning" in output.lower() or "still be installed" in output.lower() or "verify" in output.lower()

    @patch("airoom.commands_typer.uninstall.get_pipx_path")
    @patch("airoom.commands_typer.uninstall.is_installed_via_pipx")
    @patch("airoom.commands_typer.uninstall.is_interactive")
    @patch("airoom.commands_typer.uninstall.uninstall_via_pipx")
    @patch("airoom.commands_typer.uninstall.verify_uninstallation")
    def test_uninstall_does_not_affect_project_files(
        self, mock_verify, mock_uninstall, mock_interactive, mock_pipx_check, mock_pipx_path
    ):
        """Test that uninstall only removes global CLI, not project files."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_uninstall.return_value = True
        mock_verify.return_value = True

        exit_code, output = self.run_uninstall(["--yes"])
        assert exit_code == 0
        # The command should only call pipx uninstall, not touch any project files
        mock_uninstall.assert_called_once_with("/usr/local/bin/pipx")

    def test_uninstall_dry_run(self):
        """Test uninstall with dry-run flag."""
        exit_code, output = self.run_uninstall(["--yes"], global_args=["--dry-run"])
        assert exit_code == 0
        assert "dry run" in output.lower()

    def test_uninstall_json_output(self):
        """Test uninstall with JSON output."""
        with (
            patch("airoom.commands_typer.uninstall.get_pipx_path") as mock_pipx_path,
            patch("airoom.commands_typer.uninstall.is_installed_via_pipx") as mock_pipx_check,
            patch("airoom.commands_typer.uninstall.uninstall_via_pipx") as mock_uninstall,
            patch("airoom.commands_typer.uninstall.verify_uninstallation") as mock_verify,
        ):
            mock_pipx_path.return_value = "/usr/local/bin/pipx"
            mock_pipx_check.return_value = True
            mock_uninstall.return_value = True
            mock_verify.return_value = True

            exit_code, output = self.run_uninstall(["--yes"], global_args=["--json"])
            assert exit_code == 0
            data = json.loads(output)
            assert "status" in data
            assert data["status"] == "success"

    def test_uninstall_short_yes_option(self):
        """Test uninstall with short -y option."""
        with (
            patch("airoom.commands_typer.uninstall.get_pipx_path") as mock_pipx_path,
            patch("airoom.commands_typer.uninstall.is_installed_via_pipx") as mock_pipx_check,
            patch("airoom.commands_typer.uninstall.uninstall_via_pipx") as mock_uninstall,
            patch("airoom.commands_typer.uninstall.verify_uninstallation") as mock_verify,
        ):
            mock_pipx_path.return_value = "/usr/local/bin/pipx"
            mock_pipx_check.return_value = True
            mock_uninstall.return_value = True
            mock_verify.return_value = True

            exit_code, output = self.run_uninstall(["-y"])
            assert exit_code == 0
            mock_uninstall.assert_called_once()


class TestTyperUninstallCliIntegration:
    """Tests for CLI integration."""

    def test_cli_import(self):
        """Test that CLI module can be imported."""
        from airoom.cli import main

        assert callable(main)

    def test_uninstall_command_in_help(self):
        """Test uninstall command appears in help."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "uninstall" in result.output
        assert "Uninstall the global CLI" in result.output

    def test_uninstall_help_shows_options(self):
        """Test uninstall --help shows yes option."""
        runner = CliRunner()
        result = runner.invoke(app, ["uninstall", "--help"])
        assert result.exit_code == 0
        assert "--yes" in result.output or "-y" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])