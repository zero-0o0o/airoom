"""Tests for the `airoom config` Typer command."""

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from airoom.cli import app


class TestConfigCommand:
    """Tests for the config command group."""

    def setup_method(self):
        self.runner = CliRunner()

    def _init_project(self, tmpdir: str) -> Path:
        """Initialize an AIroom project in a temp directory."""
        result = self.runner.invoke(app, ["--path", tmpdir, "init"])
        assert result.exit_code == 0
        return Path(tmpdir)

    # =========================================================================
    # config show
    # =========================================================================

    def test_config_show_command_exists(self):
        """Test that the config show command is registered."""
        result = self.runner.invoke(app, ["config", "show", "--help"])
        assert result.exit_code == 0
        assert "show" in result.stdout.lower()

    def test_config_show_empty_config(self):
        """Test config show on a fresh project with no config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "show"])
            assert result.exit_code == 0
            # Should show default/empty config
            assert "skips" in result.stdout.lower() or "empty" in result.stdout.lower()

    def test_config_show_with_config(self):
        """Test config show displays existing config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Write a config file
            config_file = Path(tmpdir) / "airoom.config.yaml"
            config_file.write_text("""skips:
  - artifact-organization
defaults:
  registry_management: external
  dry_run: true
dry_run: true
verbose: 1
""", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "config", "show"])
            assert result.exit_code == 0
            assert "artifact-organization" in result.stdout
            assert "registry_management" in result.stdout
            assert "external" in result.stdout
            assert "dry_run" in result.stdout
            assert "verbose" in result.stdout

    def test_config_show_json_output(self):
        """Test config show with --json flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "show", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "skips" in data
            assert "defaults" in data
            assert "dry_run" in data
            assert "verbose" in data
            assert data["skips"] == []
            assert data["defaults"] == {}
            assert data["dry_run"] is False
            assert data["verbose"] == 0

    def test_config_show_json_output_with_config(self):
        """Test config show JSON output with existing config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            config_file = Path(tmpdir) / "airoom.config.yaml"
            config_file.write_text("""skips:
  - artifact-organization
defaults:
  registry_management: external
dry_run: true
verbose: 2
""", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "config", "show", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["skips"] == ["artifact-organization"]
            assert data["defaults"] == {"registry_management": "external"}
            assert data["dry_run"] is True
            assert data["verbose"] == 2

    def test_config_show_global_json_flag(self):
        """Test that global --json flag works with config show."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--json", "--path", tmpdir, "config", "show"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "skips" in data

    def test_config_show_global_path_option(self):
        """Test that global --path option works with config show."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "show"])
            assert result.exit_code == 0

    # =========================================================================
    # config set
    # =========================================================================

    def test_config_set_command_exists(self):
        """Test that the config set command is registered."""
        result = self.runner.invoke(app, ["config", "set", "--help"])
        assert result.exit_code == 0
        assert "set" in result.stdout.lower()

    def test_config_set_simple_key(self):
        """Test setting a simple top-level key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "set", "dry_run", "true"])
            assert result.exit_code == 0
            assert "dry_run" in result.stdout.lower() or "set" in result.stdout.lower()

            # Verify config was written
            config_file = Path(tmpdir) / "airoom.config.yaml"
            content = config_file.read_text(encoding="utf-8")
            assert "dry_run: true" in content

    def test_config_set_nested_key_dot_notation(self):
        """Test setting a nested key using dot notation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "set", "defaults.registry_management", "external"])
            assert result.exit_code == 0

            # Verify config was written
            config_file = Path(tmpdir) / "airoom.config.yaml"
            content = config_file.read_text(encoding="utf-8")
            assert "defaults:" in content
            assert "registry_management: external" in content

    def test_config_set_nested_key_auto_defaults(self):
        """Test setting a key not in TOP_LEVEL_KEYS goes under defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # "registry_management" is not a top-level key, should go under defaults
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "set", "registry_management", "external"])
            assert result.exit_code == 0

            config_file = Path(tmpdir) / "airoom.config.yaml"
            content = config_file.read_text(encoding="utf-8")
            assert "defaults:" in content
            assert "registry_management: external" in content

    def test_config_set_deep_nested_key(self):
        """Test setting a deep nested key creates intermediate dicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "set", "a.b.c", "value"])
            assert result.exit_code == 0

            config_file = Path(tmpdir) / "airoom.config.yaml"
            content = config_file.read_text(encoding="utf-8")
            # Should be under defaults since 'a' is not a top-level key
            assert "a:" in content
            assert "b:" in content
            assert "c: value" in content

    def test_config_set_overwrites_existing(self):
        """Test setting a key overwrites existing value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Pre-write config
            config_file = Path(tmpdir) / "airoom.config.yaml"
            config_file.write_text("""defaults:
  registry_management: managed
""", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "config", "set", "defaults.registry_management", "external"])
            assert result.exit_code == 0

            content = config_file.read_text(encoding="utf-8")
            assert "registry_management: external" in content
            assert "managed" not in content

    def test_config_set_json_output(self):
        """Test config set with --json flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "set", "dry_run", "true", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["status"] == "ok" or "dry_run" in str(data)

    def test_config_set_missing_key_fails(self):
        """Test that missing key argument fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "set"])
            assert result.exit_code != 0
            assert "Missing argument" in result.output or "required" in result.output.lower()

    def test_config_set_missing_value_fails(self):
        """Test that missing value argument fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "set", "dry_run"])
            assert result.exit_code != 0
            assert "Missing argument" in result.output or "required" in result.output.lower()

    # =========================================================================
    # config unset
    # =========================================================================

    def test_config_unset_command_exists(self):
        """Test that the config unset command is registered."""
        result = self.runner.invoke(app, ["config", "unset", "--help"])
        assert result.exit_code == 0
        assert "unset" in result.stdout.lower()

    def test_config_unset_simple_key(self):
        """Test unsetting a simple top-level key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            # Pre-write config
            config_file = Path(tmpdir) / "airoom.config.yaml"
            config_file.write_text("""dry_run: true
verbose: 2
""", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "config", "unset", "dry_run"])
            assert result.exit_code == 0

            # Verify config was removed (back to default)
            content = config_file.read_text(encoding="utf-8")
            # dry_run should not be in the file or be false
            # The key might be removed entirely or set to default
            # Just verify it doesn't say "true"
            assert "dry_run: true" not in content

    def test_config_unset_nested_key_dot_notation(self):
        """Test unsetting a nested key using dot notation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            config_file = Path(tmpdir) / "airoom.config.yaml"
            config_file.write_text("""defaults:
  registry_management: external
  dry_run: true
""", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "config", "unset", "defaults.registry_management"])
            assert result.exit_code == 0

            content = config_file.read_text(encoding="utf-8")
            assert "registry_management" not in content
            assert "dry_run: true" in content  # Other key preserved

    def test_config_unset_nested_key_auto_defaults(self):
        """Test unsetting a key not in TOP_LEVEL_KEYS goes under defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            config_file = Path(tmpdir) / "airoom.config.yaml"
            config_file.write_text("""defaults:
  registry_management: external
""", encoding="utf-8")

            # "registry_management" is not a top-level key
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "unset", "registry_management"])
            assert result.exit_code == 0

            content = config_file.read_text(encoding="utf-8")
            assert "registry_management" not in content

    def test_config_unset_removes_empty_parent_dicts(self):
        """Test unsetting a key removes empty parent dicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            config_file = Path(tmpdir) / "airoom.config.yaml"
            config_file.write_text("""defaults:
  a:
    b: value
""", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "config", "unset", "defaults.a.b"])
            assert result.exit_code == 0

            content = config_file.read_text(encoding="utf-8")
            # Both 'a' and 'b' should be gone
            assert "a:" not in content
            assert "b:" not in content

    def test_config_unset_nonexistent_key_no_error(self):
        """Test unsetting a nonexistent key doesn't raise error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "unset", "nonexistent"])
            assert result.exit_code == 0

            result = self.runner.invoke(app, ["--path", tmpdir, "config", "unset", "defaults.nonexistent"])
            assert result.exit_code == 0

    def test_config_unset_json_output(self):
        """Test config unset with --json flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            config_file = Path(tmpdir) / "airoom.config.yaml"
            config_file.write_text("dry_run: true\n", encoding="utf-8")

            result = self.runner.invoke(app, ["--path", tmpdir, "config", "unset", "dry_run", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["status"] == "ok" or "dry_run" in str(data)

    def test_config_unset_missing_key_fails(self):
        """Test that missing key argument fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "unset"])
            assert result.exit_code != 0
            assert "Missing argument" in result.output or "required" in result.output.lower()

    # =========================================================================
    # Not initialized project handling
    # =========================================================================

    def test_config_commands_fail_on_uninitialized_project(self):
        """Test all config commands fail gracefully on uninitialized project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for subcmd in ["show", "set test value", "unset test"]:
                cmd = ["--path", tmpdir, "config"] + subcmd.split()
                result = self.runner.invoke(app, cmd)
                assert result.exit_code != 0
                assert "not initialized" in result.stdout.lower() or "not found" in result.stdout.lower()

    # =========================================================================
    # Defaults merging / roundtrip
    # =========================================================================

    def test_config_roundtrip_preserves_all_fields(self):
        """Test set/unset/show roundtrip preserves all fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)

            # Set multiple values
            self.runner.invoke(app, ["--path", tmpdir, "config", "set", "skips", '["artifact-organization"]'])
            self.runner.invoke(app, ["--path", tmpdir, "config", "set", "defaults.registry_management", "external"])
            self.runner.invoke(app, ["--path", tmpdir, "config", "set", "dry_run", "true"])
            self.runner.invoke(app, ["--path", tmpdir, "config", "set", "verbose", "2"])

            # Show and verify
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "show", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["skips"] == ["artifact-organization"]
            assert data["defaults"]["registry_management"] == "external"
            assert data["dry_run"] is True
            assert data["verbose"] == 2

    def test_config_show_after_unset_restores_defaults(self):
        """Test that unsetting a key restores default value on show."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_project(tmpdir)

            # Set a value
            self.runner.invoke(app, ["--path", tmpdir, "config", "set", "dry_run", "true"])
            
            # Verify it's set
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "show", "--json"])
            data = json.loads(result.stdout)
            assert data["dry_run"] is True

            # Unset it
            self.runner.invoke(app, ["--path", tmpdir, "config", "unset", "dry_run"])

            # Verify it's back to default
            result = self.runner.invoke(app, ["--path", tmpdir, "config", "show", "--json"])
            data = json.loads(result.stdout)
            assert data["dry_run"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])