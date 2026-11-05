"""Tests for airoom upgrade command (Typer-based)."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from airoom.cli import app
from airoom.commands_typer.upgrade import (
    get_pipx_path,
    is_installed_via_pipx,
    parse_version,
    compare_versions,
    is_prerelease,
    fetch_latest_release,
    upgrade_via_pipx,
    verify_installation,
    Release,
)


class TestVersionParsing:
    """Tests for version parsing and comparison."""

    def test_parse_version_basic(self):
        """Test parsing basic semantic versions."""
        # Final releases: (major, minor, patch, 1)
        assert parse_version("0.1.0") == (0, 1, 0, 1)
        assert parse_version("1.0.0") == (1, 0, 0, 1)
        assert parse_version("10.20.30") == (10, 20, 30, 1)

    def test_parse_version_with_v_prefix(self):
        """Test parsing versions with 'v' prefix."""
        assert parse_version("v0.1.0") == (0, 1, 0, 1)
        assert parse_version("v1.0.0") == (1, 0, 0, 1)

    def test_parse_version_prerelease(self):
        """Test parsing prerelease versions."""
        # Prerelease identifiers are typed so numeric identifiers sort numerically.
        assert parse_version("0.2.0-alpha") == (0, 2, 0, 0, ((1, "alpha"),))
        assert parse_version("1.0.0-rc.1") == (1, 0, 0, 0, ((1, "rc"), (0, 1)))
        assert parse_version("v0.1.0-beta.2") == (0, 1, 0, 0, ((1, "beta"), (0, 2)))

    def test_compare_versions_equal(self):
        """Test comparing equal versions."""
        assert compare_versions("0.1.0", "0.1.0") == 0
        assert compare_versions("v1.0.0", "1.0.0") == 0

    def test_compare_versions_less(self):
        """Test comparing lesser versions."""
        assert compare_versions("0.1.0", "0.2.0") == -1
        assert compare_versions("0.1.0", "1.0.0") == -1
        assert compare_versions("1.0.0", "1.0.1") == -1

    def test_compare_versions_greater(self):
        """Test comparing greater versions."""
        assert compare_versions("0.2.0", "0.1.0") == 1
        assert compare_versions("1.0.0", "0.1.0") == 1
        assert compare_versions("1.0.1", "1.0.0") == 1

    def test_compare_versions_prerelease(self):
        """Test comparing prerelease vs final."""
        # Prereleases sort before final releases
        assert compare_versions("1.0.0-alpha", "1.0.0") == -1
        assert compare_versions("1.0.0-rc.1", "1.0.0") == -1
        assert compare_versions("1.0.0", "1.0.0-alpha") == 1

    def test_is_prerelease(self):
        """Test prerelease detection."""
        assert is_prerelease("0.1.0") is False
        assert is_prerelease("v1.0.0") is False
        assert is_prerelease("0.2.0-alpha") is True
        assert is_prerelease("1.0.0-rc.1") is True
        assert is_prerelease("v0.1.0-beta") is True


class TestPipxDetection:
    """Tests for pipx detection."""

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
        mock_run.return_value = MagicMock(returncode=0, stdout='{"venvs":{"other-package":{}}}')
        assert is_installed_via_pipx() is False


class TestFetchLatestRelease:
    """Tests for fetching latest release from GitHub API."""

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_success(self, mock_urlopen):
        """Test successful release fetch."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            [
                {
                    "tag_name": "v0.2.0",
                    "prerelease": False,
                    "draft": False,
                    "published_at": "2024-01-15T10:00:00Z",
                },
                {
                    "tag_name": "v0.1.0",
                    "prerelease": False,
                    "draft": False,
                    "published_at": "2024-01-01T10:00:00Z",
                },
            ]
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_response

        release = fetch_latest_release("zero-0o0o/airoom")
        assert release is not None
        assert release.tag_name == "v0.2.0"
        assert release.version == "0.2.0"
        assert release.prerelease is False

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_excludes_prerelease(self, mock_urlopen):
        """Test that prereleases are excluded by default."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            [
                {
                    "tag_name": "v0.2.0-alpha",
                    "prerelease": True,
                    "draft": False,
                    "published_at": "2024-01-15T10:00:00Z",
                },
                {
                    "tag_name": "v0.1.0",
                    "prerelease": False,
                    "draft": False,
                    "published_at": "2024-01-01T10:00:00Z",
                },
            ]
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_response

        release = fetch_latest_release("zero-0o0o/airoom", include_prereleases=False)
        assert release is not None
        assert release.version == "0.1.0"

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_includes_prerelease(self, mock_urlopen):
        """Test including prereleases when requested."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            [
                {
                    "tag_name": "v0.2.0-alpha",
                    "prerelease": True,
                    "draft": False,
                    "published_at": "2024-01-15T10:00:00Z",
                },
                {
                    "tag_name": "v0.1.0",
                    "prerelease": False,
                    "draft": False,
                    "published_at": "2024-01-01T10:00:00Z",
                },
            ]
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_response

        release = fetch_latest_release("zero-0o0o/airoom", include_prereleases=True)
        assert release is not None
        assert release.version == "0.2.0-alpha"

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_excludes_draft(self, mock_urlopen):
        """Test that draft releases are excluded."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            [
                {
                    "tag_name": "v0.2.0",
                    "prerelease": False,
                    "draft": True,
                    "published_at": "2024-01-15T10:00:00Z",
                },
                {
                    "tag_name": "v0.1.0",
                    "prerelease": False,
                    "draft": False,
                    "published_at": "2024-01-01T10:00:00Z",
                },
            ]
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_response

        release = fetch_latest_release("zero-0o0o/airoom")
        assert release is not None
        assert release.version == "0.1.0"

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_empty(self, mock_urlopen):
        """Test empty releases list."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([]).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_response

        release = fetch_latest_release("zero-0o0o/airoom")
        assert release is None

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_network_error(self, mock_urlopen):
        """Test network error handling."""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("Network error")

        with pytest.raises(RuntimeError, match="Failed to fetch releases"):
            fetch_latest_release("zero-0o0o/airoom")

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_invalid_json(self, mock_urlopen):
        """Test invalid JSON response."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"not valid json"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_response

        with pytest.raises(RuntimeError, match="Failed to parse GitHub API response"):
            fetch_latest_release("zero-0o0o/airoom")


class TestUpgradeViaPipx:
    """Tests for pipx upgrade."""

    @patch("subprocess.run")
    def test_upgrade_via_pipx_success(self, mock_run):
        """Test successful pipx upgrade."""
        mock_run.return_value = MagicMock(returncode=0, stdout="upgraded", stderr="")
        result = upgrade_via_pipx("v0.2.0")
        assert result is True

    @patch("subprocess.run")
    def test_upgrade_via_pipx_failure_does_not_force_reinstall(self, mock_run):
        """A failed upgrade leaves pipx's existing environment intact."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="upgrade failed")
        result = upgrade_via_pipx("v0.2.0")
        assert result is False
        assert mock_run.call_count == 1

    @patch("subprocess.run")
    def test_upgrade_via_pipx_failure(self, mock_run):
        """Test pipx upgrade failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result = upgrade_via_pipx("v0.2.0")
        assert result is False

    @patch("subprocess.run")
    def test_upgrade_via_pipx_timeout(self, mock_run):
        """Test pipx upgrade timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("pipx", 120)
        result = upgrade_via_pipx("v0.2.0")
        assert result is False


class TestVerifyInstallation:
    """Tests for installation verification."""

    @patch("subprocess.run")
    def test_verify_installation_success(self, mock_run):
        """Test successful verification."""
        mock_run.return_value = MagicMock(returncode=0, stdout="airoom 0.2.0", stderr="")
        version = verify_installation()
        assert version == "0.2.0"

    @patch("subprocess.run")
    def test_verify_installation_failure(self, mock_run):
        """Test verification failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        version = verify_installation()
        assert version is None


class TestTyperUpgradeCommand:
    """Integration tests for the Typer upgrade command."""

    def run_upgrade(self, args: list[str] | None = None, global_args: list[str] | None = None) -> tuple[int, str]:
        """Run upgrade command."""
        runner = CliRunner()
        cmd = []
        if global_args:
            cmd.extend(global_args)
        cmd.append("upgrade")
        if args:
            cmd.extend(args)
        result = runner.invoke(app, cmd)
        return result.exit_code, result.output

    @patch("airoom.commands_typer.upgrade.get_pipx_path")
    @patch("airoom.commands_typer.upgrade.is_installed_via_pipx")
    @patch("airoom.commands_typer.upgrade.fetch_latest_release")
    @patch("airoom.commands_typer.upgrade.upgrade_via_pipx")
    @patch("airoom.commands_typer.upgrade.verify_installation")
    def test_upgrade_already_latest(
        self, mock_verify, mock_upgrade, mock_fetch, mock_pipx_check, mock_pipx_path
    ):
        """Test upgrade when already at latest version."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.return_value = Release("v0.1.0", "0.1.0", False, "2024-01-01T10:00:00Z")

        exit_code, output = self.run_upgrade()
        assert exit_code == 2  # Already up to date
        mock_upgrade.assert_not_called()
        assert "Already at the latest version" in output

    @patch("airoom.commands_typer.upgrade.get_pipx_path")
    @patch("airoom.commands_typer.upgrade.is_installed_via_pipx")
    @patch("airoom.commands_typer.upgrade.fetch_latest_release")
    @patch("airoom.commands_typer.upgrade.upgrade_via_pipx")
    @patch("airoom.commands_typer.upgrade.verify_installation")
    def test_upgrade_success(
        self, mock_verify, mock_upgrade, mock_fetch, mock_pipx_check, mock_pipx_path
    ):
        """Test successful upgrade."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.return_value = Release("v0.2.0", "0.2.0", False, "2024-01-15T10:00:00Z")
        mock_upgrade.return_value = True
        mock_verify.return_value = "0.2.0"

        exit_code, output = self.run_upgrade()
        assert exit_code == 0
        mock_upgrade.assert_called_once_with("v0.2.0", "zero-0o0o/airoom")
        mock_verify.assert_called_once()
        assert "Successfully upgraded to version 0.2.0" in output

    @patch("airoom.commands_typer.upgrade.get_pipx_path")
    @patch("airoom.commands_typer.upgrade.is_installed_via_pipx")
    @patch("airoom.commands_typer.upgrade.fetch_latest_release")
    @patch("airoom.commands_typer.upgrade.upgrade_via_pipx")
    @patch("airoom.commands_typer.upgrade.verify_installation")
    @patch("urllib.request.urlopen")
    def test_upgrade_with_explicit_version(
        self, mock_urlopen, mock_verify, mock_upgrade, mock_fetch, mock_pipx_check, mock_pipx_path
    ):
        """Test upgrade with explicit version."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.return_value = Release("v0.2.0", "0.2.0", False, "2024-01-15T10:00:00Z")
        mock_upgrade.return_value = True
        mock_verify.return_value = "0.2.0"

        # Mock the version check for explicit version
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "tag_name": "v0.2.0",
                "prerelease": False,
                "draft": False,
            }
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_response

        exit_code, output = self.run_upgrade(["--version", "0.2.0"])
        assert exit_code == 0
        mock_upgrade.assert_called_once_with("v0.2.0", "zero-0o0o/airoom")
        assert "Successfully upgraded to version 0.2.0" in output

    @patch("airoom.commands_typer.upgrade.get_pipx_path")
    @patch("airoom.commands_typer.upgrade.is_installed_via_pipx")
    def test_upgrade_pipx_not_found(self, mock_pipx_check, mock_pipx_path):
        """Test upgrade when pipx not found."""
        mock_pipx_path.return_value = None

        exit_code, output = self.run_upgrade()
        assert exit_code == 1
        assert "pipx not found" in output

    @patch("airoom.commands_typer.upgrade.get_pipx_path")
    @patch("airoom.commands_typer.upgrade.is_installed_via_pipx")
    @patch("airoom.commands_typer.upgrade.fetch_latest_release")
    def test_upgrade_prerelease_blocked_by_default(
        self, mock_fetch, mock_pipx_check, mock_pipx_path
    ):
        """Test that prereleases are blocked by default."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.return_value = Release(
            "v0.2.0-alpha", "0.2.0-alpha", True, "2024-01-15T10:00:00Z"
        )

        exit_code, output = self.run_upgrade()
        assert exit_code == 2  # Already up to date (prerelease blocked)
        assert "prerelease" in output.lower()

    @patch("airoom.commands_typer.upgrade.get_pipx_path")
    @patch("airoom.commands_typer.upgrade.is_installed_via_pipx")
    @patch("airoom.commands_typer.upgrade.fetch_latest_release")
    @patch("airoom.commands_typer.upgrade.upgrade_via_pipx")
    @patch("airoom.commands_typer.upgrade.verify_installation")
    def test_upgrade_prerelease_allowed_with_flag(
        self, mock_verify, mock_upgrade, mock_fetch, mock_pipx_check, mock_pipx_path
    ):
        """Test that prereleases are allowed with --prerelease flag."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.return_value = Release(
            "v0.2.0-alpha", "0.2.0-alpha", True, "2024-01-15T10:00:00Z"
        )
        mock_upgrade.return_value = True
        mock_verify.return_value = "0.2.0-alpha"

        exit_code, output = self.run_upgrade(["--prerelease"])
        assert exit_code == 0
        assert "Successfully upgraded to version 0.2.0-alpha" in output

    @patch("airoom.commands_typer.upgrade.get_pipx_path")
    @patch("airoom.commands_typer.upgrade.is_installed_via_pipx")
    def test_upgrade_invalid_version_format(self, mock_pipx_check, mock_pipx_path):
        """Test upgrade with invalid version format."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True

        exit_code, output = self.run_upgrade(["--version", "invalid"])
        assert exit_code == 3  # Invalid version
        assert "Invalid version format" in output

    @patch("airoom.commands_typer.upgrade.get_pipx_path")
    @patch("airoom.commands_typer.upgrade.is_installed_via_pipx")
    @patch("airoom.commands_typer.upgrade.fetch_latest_release")
    @patch("urllib.request.urlopen")
    def test_upgrade_version_not_found(self, mock_urlopen, mock_fetch, mock_pipx_check, mock_pipx_path):
        """Test upgrade with non-existent version."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.return_value = Release("v0.2.0", "0.2.0", False, "2024-01-15T10:00:00Z")

        import urllib.error

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        error = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
        mock_urlopen.side_effect = error

        exit_code, output = self.run_upgrade(["--version", "99.99.99"])
        assert exit_code == 3  # Version not found
        assert "not found" in output.lower() or "404" in output.lower()

    @patch("airoom.commands_typer.upgrade.get_pipx_path")
    @patch("airoom.commands_typer.upgrade.is_installed_via_pipx")
    @patch("airoom.commands_typer.upgrade.fetch_latest_release")
    @patch("airoom.commands_typer.upgrade.upgrade_via_pipx")
    def test_upgrade_failure(self, mock_upgrade, mock_fetch, mock_pipx_check, mock_pipx_path):
        """Test upgrade failure."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.return_value = Release("v0.2.0", "0.2.0", False, "2024-01-15T10:00:00Z")
        mock_upgrade.return_value = False

        exit_code, output = self.run_upgrade()
        assert exit_code == 1  # Upgrade failed
        assert "Upgrade failed" in output

    @patch("airoom.commands_typer.upgrade.get_pipx_path")
    @patch("airoom.commands_typer.upgrade.is_installed_via_pipx")
    @patch("airoom.commands_typer.upgrade.fetch_latest_release")
    def test_upgrade_network_error(self, mock_fetch, mock_pipx_check, mock_pipx_path):
        """Test upgrade with network error."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.side_effect = RuntimeError("Network error")

        exit_code, output = self.run_upgrade()
        assert exit_code == 1  # Error
        assert "Network error" in output or "Failed to fetch" in output

    @patch("airoom.commands_typer.upgrade.get_pipx_path")
    @patch("airoom.commands_typer.upgrade.is_installed_via_pipx")
    def test_upgrade_not_installed_via_pipx(self, mock_pipx_check, mock_pipx_path):
        """Test upgrade when AIroom is not installed via pipx."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = False

        exit_code, output = self.run_upgrade()
        assert exit_code == 1
        assert "not verified as a pipx installation" in output

    def test_upgrade_dry_run(self):
        """Test upgrade with dry-run flag."""
        exit_code, output = self.run_upgrade([], global_args=["--dry-run"])
        assert exit_code == 0
        assert "dry run" in output.lower()

    def test_upgrade_json_output(self):
        """Test upgrade with JSON output."""
        with (
            patch("airoom.commands_typer.upgrade.get_pipx_path") as mock_pipx_path,
            patch("airoom.commands_typer.upgrade.is_installed_via_pipx") as mock_pipx_check,
            patch("airoom.commands_typer.upgrade.fetch_latest_release") as mock_fetch,
            patch("airoom.commands_typer.upgrade.upgrade_via_pipx") as mock_upgrade,
            patch("airoom.commands_typer.upgrade.verify_installation") as mock_verify,
        ):
            mock_pipx_path.return_value = "/usr/local/bin/pipx"
            mock_pipx_check.return_value = True
            mock_fetch.return_value = Release("v0.2.0", "0.2.0", False, "2024-01-15T10:00:00Z")
            mock_upgrade.return_value = True
            mock_verify.return_value = "0.2.0"

            exit_code, output = self.run_upgrade([], global_args=["--json"])
            assert exit_code == 0
            data = json.loads(output)
            assert "installed_version" in data
            assert "latest_version" in data
            assert "status" in data


class TestTyperUpgradeCliIntegration:
    """Tests for CLI integration."""

    def test_cli_import(self):
        """Test that CLI module can be imported."""
        from airoom.cli import main

        assert callable(main)

    def test_upgrade_command_in_help(self):
        """Test upgrade command appears in help."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "upgrade" in result.output
        assert "Upgrade the global CLI" in result.output

    def test_upgrade_help_shows_options(self):
        """Test upgrade --help shows version and prerelease options."""
        runner = CliRunner()
        result = runner.invoke(app, ["upgrade", "--help"])
        assert result.exit_code == 0
        assert "--version" in result.output
        assert "--prerelease" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])