"""Tests for airoom uninstall command."""

from unittest.mock import patch, MagicMock

import pytest

from airoom.commands.uninstall import (
    uninstall_command,
    get_pipx_path,
    is_installed_via_pipx,
    get_installed_version,
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


class TestInstalledVersion:
    """Tests for getting installed version."""

    def test_get_installed_version(self):
        """Test getting installed version from package."""
        version = get_installed_version()
        assert version == "0.1.0"
        assert isinstance(version, str)


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
        import subprocess

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


class TestUninstallCommand:
    """Integration tests for uninstall command."""

    def create_args(self, yes=False):
        """Create mock args object."""

        class Args:
            def __init__(self, yes=False):
                self.yes = yes

        return Args(yes)

    @patch("airoom.commands.uninstall.get_pipx_path")
    @patch("airoom.commands.uninstall.is_installed_via_pipx")
    @patch("airoom.commands.uninstall.is_interactive")
    def test_uninstall_pipx_not_found(self, mock_interactive, mock_pipx_check, mock_pipx_path):
        """Test uninstall when pipx not found."""
        mock_pipx_path.return_value = None

        result = uninstall_command(self.create_args(yes=True))
        assert result == 3

    @patch("airoom.commands.uninstall.get_pipx_path")
    @patch("airoom.commands.uninstall.is_installed_via_pipx")
    @patch("airoom.commands.uninstall.is_interactive")
    def test_uninstall_not_via_pipx(self, mock_interactive, mock_pipx_check, mock_pipx_path):
        """Test uninstall when not installed via pipx."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = False

        result = uninstall_command(self.create_args(yes=True))
        assert result == 3

    @patch("airoom.commands.uninstall.get_pipx_path")
    @patch("airoom.commands.uninstall.is_installed_via_pipx")
    @patch("airoom.commands.uninstall.is_interactive")
    @patch("airoom.commands.uninstall.uninstall_via_pipx")
    @patch("airoom.commands.uninstall.verify_uninstallation")
    def test_uninstall_success(
        self, mock_verify, mock_uninstall, mock_interactive, mock_pipx_check, mock_pipx_path
    ):
        """Test successful uninstall with --yes."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_uninstall.return_value = True
        mock_verify.return_value = True

        result = uninstall_command(self.create_args(yes=True))
        assert result == 0
        mock_uninstall.assert_called_once()

    @patch("airoom.commands.uninstall.get_pipx_path")
    @patch("airoom.commands.uninstall.is_installed_via_pipx")
    @patch("airoom.commands.uninstall.is_interactive")
    @patch("airoom.commands.uninstall.prompt_confirmation")
    @patch("airoom.commands.uninstall.uninstall_via_pipx")
    @patch("airoom.commands.uninstall.verify_uninstallation")
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

        result = uninstall_command(self.create_args(yes=False))
        assert result == 0
        mock_prompt.assert_called_once()

    @patch("airoom.commands.uninstall.get_pipx_path")
    @patch("airoom.commands.uninstall.is_installed_via_pipx")
    @patch("airoom.commands.uninstall.is_interactive")
    @patch("airoom.commands.uninstall.prompt_confirmation")
    def test_uninstall_confirmation_declined(
        self, mock_prompt, mock_interactive, mock_pipx_check, mock_pipx_path
    ):
        """Test uninstall with confirmation declined."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_interactive.return_value = True
        mock_prompt.return_value = False

        result = uninstall_command(self.create_args(yes=False))
        assert result == 2
        mock_prompt.assert_called_once()

    @patch("airoom.commands.uninstall.get_pipx_path")
    @patch("airoom.commands.uninstall.is_installed_via_pipx")
    @patch("airoom.commands.uninstall.is_interactive")
    def test_uninstall_non_interactive_without_yes(
        self, mock_interactive, mock_pipx_check, mock_pipx_path
    ):
        """Test uninstall in non-interactive mode without --yes."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_interactive.return_value = False

        result = uninstall_command(self.create_args(yes=False))
        assert result == 2

    @patch("airoom.commands.uninstall.get_pipx_path")
    @patch("airoom.commands.uninstall.is_installed_via_pipx")
    @patch("airoom.commands.uninstall.is_interactive")
    @patch("airoom.commands.uninstall.uninstall_via_pipx")
    def test_uninstall_failure(
        self, mock_uninstall, mock_interactive, mock_pipx_check, mock_pipx_path
    ):
        """Test uninstall failure."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_uninstall.return_value = False

        result = uninstall_command(self.create_args(yes=True))
        assert result == 1

    @patch("airoom.commands.uninstall.get_pipx_path")
    @patch("airoom.commands.uninstall.is_installed_via_pipx")
    @patch("airoom.commands.uninstall.is_interactive")
    @patch("airoom.commands.uninstall.uninstall_via_pipx")
    @patch("airoom.commands.uninstall.verify_uninstallation")
    def test_uninstall_verification_fails(
        self, mock_verify, mock_uninstall, mock_interactive, mock_pipx_check, mock_pipx_path
    ):
        """Test uninstall when verification fails."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_uninstall.return_value = True
        mock_verify.return_value = False

        result = uninstall_command(self.create_args(yes=True))
        assert result == 1

    @patch("airoom.commands.uninstall.get_pipx_path")
    @patch("airoom.commands.uninstall.is_installed_via_pipx")
    @patch("airoom.commands.uninstall.is_interactive")
    @patch("airoom.commands.uninstall.uninstall_via_pipx")
    @patch("airoom.commands.uninstall.verify_uninstallation")
    def test_uninstall_does_not_affect_project_files(
        self, mock_verify, mock_uninstall, mock_interactive, mock_pipx_check, mock_pipx_path
    ):
        """Test that uninstall only removes global CLI, not project files."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_uninstall.return_value = True
        mock_verify.return_value = True

        result = uninstall_command(self.create_args(yes=True))
        assert result == 0
        # The command should only call pipx uninstall, not touch any project files
        mock_uninstall.assert_called_once_with("/usr/local/bin/pipx")


class TestCliIntegration:
    """Tests for CLI integration."""

    def test_cli_uninstall_help(self):
        """Test that uninstall command shows help."""
        import subprocess

        result = subprocess.run(["airoom", "uninstall", "--help"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "Uninstall the global CLI" in result.stdout or "usage:" in result.stdout

    def test_cli_uninstall_yes_option(self):
        """Test that uninstall command accepts --yes option."""
        import subprocess

        result = subprocess.run(
            ["airoom", "uninstall", "--yes", "--help"], capture_output=True, text=True
        )
        assert result.returncode == 0

    def test_cli_uninstall_short_yes_option(self):
        """Test that uninstall command accepts -y option."""
        import subprocess

        result = subprocess.run(
            ["airoom", "uninstall", "-y", "--help"], capture_output=True, text=True
        )
        assert result.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
