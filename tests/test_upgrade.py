"""Tests for airoom upgrade command."""

import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from airoom.commands.upgrade import (
    upgrade_command,
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
from airoom.core.version import get_installed_version


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


class TestInstalledVersion:
    """Tests for getting installed version."""

    def test_get_installed_version(self):
        """Test getting installed version from package."""
        version = get_installed_version()
        assert version == "0.1.0"
        assert isinstance(version, str)


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


class TestUpgradeCommand:
    """Integration tests for upgrade command."""

    def create_args(self, version=None, prerelease=False):
        """Create mock args object."""

        class Args:
            def __init__(self, version=None, prerelease=False):
                self.version = version
                self.prerelease = prerelease

        return Args(version, prerelease)

    @patch("airoom.commands.upgrade.get_pipx_path")
    @patch("airoom.commands.upgrade.is_installed_via_pipx")
    @patch("airoom.commands.upgrade.fetch_latest_release")
    @patch("airoom.commands.upgrade.upgrade_via_pipx")
    @patch("airoom.commands.upgrade.verify_installation")
    def test_upgrade_already_latest(
        self, mock_verify, mock_upgrade, mock_fetch, mock_pipx_check, mock_pipx_path
    ):
        """Test upgrade when already at latest version."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.return_value = Release("v0.1.0", "0.1.0", False, "2024-01-01T10:00:00Z")

        result = upgrade_command(self.create_args())
        assert result == 2  # Already up to date
        mock_upgrade.assert_not_called()

    @patch("airoom.commands.upgrade.get_pipx_path")
    @patch("airoom.commands.upgrade.is_installed_via_pipx")
    @patch("airoom.commands.upgrade.fetch_latest_release")
    @patch("airoom.commands.upgrade.upgrade_via_pipx")
    @patch("airoom.commands.upgrade.verify_installation")
    def test_upgrade_success(
        self, mock_verify, mock_upgrade, mock_fetch, mock_pipx_check, mock_pipx_path
    ):
        """Test successful upgrade."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.return_value = Release("v0.2.0", "0.2.0", False, "2024-01-15T10:00:00Z")
        mock_upgrade.return_value = True
        mock_verify.return_value = "0.2.0"

        result = upgrade_command(self.create_args())
        assert result == 0
        mock_upgrade.assert_called_once_with("v0.2.0", "zero-0o0o/airoom")
        mock_verify.assert_called_once()

    @patch("airoom.commands.upgrade.get_pipx_path")
    @patch("airoom.commands.upgrade.is_installed_via_pipx")
    @patch("airoom.commands.upgrade.fetch_latest_release")
    @patch("airoom.commands.upgrade.upgrade_via_pipx")
    @patch("airoom.commands.upgrade.verify_installation")
    def test_upgrade_with_explicit_version(
        self, mock_verify, mock_upgrade, mock_fetch, mock_pipx_check, mock_pipx_path
    ):
        """Test upgrade with explicit version."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.return_value = Release("v0.2.0", "0.2.0", False, "2024-01-15T10:00:00Z")
        mock_upgrade.return_value = True
        mock_verify.return_value = "0.2.0"

        # Mock the version check for explicit version
        with patch("urllib.request.urlopen") as mock_urlopen:
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

            result = upgrade_command(self.create_args(version="0.2.0"))

        assert result == 0
        mock_upgrade.assert_called_once_with("v0.2.0", "zero-0o0o/airoom")

    @patch("airoom.commands.upgrade.get_pipx_path")
    @patch("airoom.commands.upgrade.is_installed_via_pipx")
    def test_upgrade_pipx_not_found(self, mock_pipx_check, mock_pipx_path):
        """Test upgrade when pipx not found."""
        mock_pipx_path.return_value = None

        result = upgrade_command(self.create_args())
        assert result == 1

    @patch("airoom.commands.upgrade.get_pipx_path")
    @patch("airoom.commands.upgrade.is_installed_via_pipx")
    @patch("airoom.commands.upgrade.fetch_latest_release")
    def test_upgrade_prerelease_blocked_by_default(
        self, mock_fetch, mock_pipx_check, mock_pipx_path
    ):
        """Test that prereleases are blocked by default."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.return_value = Release(
            "v0.2.0-alpha", "0.2.0-alpha", True, "2024-01-15T10:00:00Z"
        )

        result = upgrade_command(self.create_args(prerelease=False))
        assert result == 2  # Already up to date (prerelease blocked)

    @patch("airoom.commands.upgrade.get_pipx_path")
    @patch("airoom.commands.upgrade.is_installed_via_pipx")
    @patch("airoom.commands.upgrade.fetch_latest_release")
    def test_upgrade_prerelease_allowed_with_flag(
        self, mock_fetch, mock_pipx_check, mock_pipx_path
    ):
        """Test that prereleases are allowed with --prerelease flag."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.return_value = Release(
            "v0.2.0-alpha", "0.2.0-alpha", True, "2024-01-15T10:00:00Z"
        )

        with patch("airoom.commands.upgrade.upgrade_via_pipx") as mock_upgrade:
            mock_upgrade.return_value = True
            with patch("airoom.commands.upgrade.verify_installation") as mock_verify:
                mock_verify.return_value = "0.2.0-alpha"
                result = upgrade_command(self.create_args(prerelease=True))

        assert result == 0

    @patch("airoom.commands.upgrade.get_pipx_path")
    @patch("airoom.commands.upgrade.is_installed_via_pipx")
    def test_upgrade_invalid_version_format(self, mock_pipx_check, mock_pipx_path):
        """Test upgrade with invalid version format."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True

        result = upgrade_command(self.create_args(version="invalid"))
        assert result == 3  # Invalid version

    @patch("airoom.commands.upgrade.get_pipx_path")
    @patch("airoom.commands.upgrade.is_installed_via_pipx")
    @patch("airoom.commands.upgrade.fetch_latest_release")
    def test_upgrade_version_not_found(self, mock_fetch, mock_pipx_check, mock_pipx_path):
        """Test upgrade with non-existent version."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        # Mock fetch_latest_release to return a valid release (for comparison)
        mock_fetch.return_value = Release("v0.2.0", "0.2.0", False, "2024-01-15T10:00:00Z")

        # Now mock the specific version check
        with patch("urllib.request.urlopen") as mock_urlopen:
            import urllib.error

            mock_response = MagicMock()
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            error = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
            mock_urlopen.side_effect = error

            result = upgrade_command(self.create_args(version="99.99.99"))

        assert result == 3  # Version not found

    @patch("airoom.commands.upgrade.get_pipx_path")
    @patch("airoom.commands.upgrade.is_installed_via_pipx")
    @patch("airoom.commands.upgrade.fetch_latest_release")
    @patch("airoom.commands.upgrade.upgrade_via_pipx")
    def test_upgrade_failure(self, mock_upgrade, mock_fetch, mock_pipx_check, mock_pipx_path):
        """Test upgrade failure."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.return_value = Release("v0.2.0", "0.2.0", False, "2024-01-15T10:00:00Z")
        mock_upgrade.return_value = False

        result = upgrade_command(self.create_args())
        assert result == 1  # Upgrade failed

    @patch("airoom.commands.upgrade.get_pipx_path")
    @patch("airoom.commands.upgrade.is_installed_via_pipx")
    @patch("airoom.commands.upgrade.fetch_latest_release")
    def test_upgrade_network_error(self, mock_fetch, mock_pipx_check, mock_pipx_path):
        """Test upgrade with network error."""
        mock_pipx_path.return_value = "/usr/local/bin/pipx"
        mock_pipx_check.return_value = True
        mock_fetch.side_effect = RuntimeError("Network error")

        result = upgrade_command(self.create_args())
        assert result == 1  # Error


class TestCliIntegration:
    """Tests for CLI integration."""

    def test_cli_upgrade_help(self):
        """Test that upgrade command shows help."""
        result = subprocess.run(["airoom", "upgrade", "--help"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "Upgrade the global CLI" in result.stdout or "usage:" in result.stdout

    def test_cli_upgrade_version_option(self):
        """Test that upgrade command accepts --version option."""
        result = subprocess.run(
            ["airoom", "upgrade", "--version", "0.2.0", "--help"], capture_output=True, text=True
        )
        # Should parse without error (though it will fail due to no network)
        assert result.returncode == 0

    def test_cli_upgrade_prerelease_option(self):
        """Test that upgrade command accepts --prerelease option."""
        result = subprocess.run(
            ["airoom", "upgrade", "--prerelease", "--help"], capture_output=True, text=True
        )
        assert result.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])