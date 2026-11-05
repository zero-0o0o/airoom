"""Tests for airoom.core.config module."""

import tempfile
from pathlib import Path

import pytest

from airoom.core.project import Project
from airoom.core.config import Config, ConfigManager, _default_config


DEFAULT_CONFIG = _default_config()


class TestConfigDataclass:
    """Tests for Config dataclass."""

    def test_config_defaults(self):
        """Test Config can be created with default values."""
        config = Config(skips=[], defaults={}, dry_run=False, verbose=0)
        assert config.skips == []
        assert config.defaults == {}
        assert config.dry_run is False
        assert config.verbose == 0

    def test_config_with_values(self):
        """Test Config can be created with custom values."""
        config = Config(
            skips=["artifact-organization"],
            defaults={"registry_management": "external", "dry_run": True},
            dry_run=True,
            verbose=2,
        )
        assert config.skips == ["artifact-organization"]
        assert config.defaults == {"registry_management": "external", "dry_run": True}
        assert config.dry_run is True
        assert config.verbose == 2


class TestConfigManager:
    """Tests for ConfigManager class."""

    def setup_method(self):
        """Create a temporary project directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir).resolve()
        self.project = Project(self.project_root)
        # Create the airoom directory structure
        self.project.airoom_dir.mkdir(parents=True, exist_ok=True)
        self.manager = ConfigManager(self.project)
        self.config_path = self.project_root / "airoom.config.yaml"

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_with_project(self):
        """Test ConfigManager initialization with Project."""
        assert self.manager.project == self.project
        assert self.manager.config_path == self.config_path

    def test_read_nonexistent_config_returns_default(self):
        """Test reading a nonexistent config returns default Config."""
        config = self.manager.read()
        assert config == DEFAULT_CONFIG

    def test_read_existing_config(self):
        """Test reading an existing config file."""
        config_yaml = """skips:
  - artifact-organization
defaults:
  registry_management: external
  dry_run: true
dry_run: true
verbose: 1
"""
        self.config_path.write_text(config_yaml, encoding="utf-8")

        config = self.manager.read()
        assert config.skips == ["artifact-organization"]
        assert config.defaults == {"registry_management": "external", "dry_run": True}
        assert config.dry_run is True
        assert config.verbose == 1

    def test_read_empty_config_returns_default(self):
        """Test reading empty config file returns default."""
        self.config_path.write_text("", encoding="utf-8")
        config = self.manager.read()
        assert config == DEFAULT_CONFIG

    def test_read_config_with_partial_keys(self):
        """Test reading config with only some keys returns defaults for missing."""
        config_yaml = """skips:
  - artifact-organization
"""
        self.config_path.write_text(config_yaml, encoding="utf-8")

        config = self.manager.read()
        assert config.skips == ["artifact-organization"]
        assert config.defaults == {}
        assert config.dry_run is False
        assert config.verbose == 0

    def test_write_config(self):
        """Test writing a config."""
        config = Config(
            skips=["artifact-organization"],
            defaults={"registry_management": "external"},
            dry_run=True,
            verbose=2,
        )
        self.manager.write(config)

        content = self.config_path.read_text(encoding="utf-8")
        assert "skips:" in content
        assert "artifact-organization" in content
        assert "defaults:" in content
        assert "registry_management: external" in content
        assert "dry_run: true" in content
        assert "verbose: 2" in content

    def test_write_uses_atomic_write(self):
        """Test that write uses atomic write (creates no temp files on success)."""
        config = Config(skips=[], defaults={}, dry_run=False, verbose=0)
        self.manager.write(config)
        tmp_files = list(self.project.airoom_dir.glob("*.tmp"))
        assert tmp_files == []

    def test_get_simple_key(self):
        """Test getting a simple key."""
        config_yaml = """dry_run: true
verbose: 2
"""
        self.config_path.write_text(config_yaml, encoding="utf-8")

        assert self.manager.get("dry_run") is True
        assert self.manager.get("verbose") == 2

    def test_get_nested_key_dot_notation(self):
        """Test getting a nested key using dot notation."""
        config_yaml = """defaults:
  registry_management: external
  dry_run: true
"""
        self.config_path.write_text(config_yaml, encoding="utf-8")

        assert self.manager.get("defaults.registry_management") == "external"
        assert self.manager.get("defaults.dry_run") is True

    def test_get_nonexistent_key_returns_default(self):
        """Test getting a nonexistent key returns the provided default."""
        assert self.manager.get("nonexistent") is None
        assert self.manager.get("nonexistent", "default") == "default"
        assert self.manager.get("defaults.nonexistent", "default") == "default"

    def test_get_empty_config_returns_default(self):
        """Test getting keys from empty config returns defaults."""
        assert self.manager.get("dry_run") is None
        assert self.manager.get("dry_run", False) is False

    def test_set_simple_key(self):
        """Test setting a simple key."""
        self.manager.set("dry_run", True)
        config = self.manager.read()
        assert config.dry_run is True

    def test_set_nested_key_dot_notation(self):
        """Test setting a nested key using dot notation."""
        self.manager.set("defaults.registry_management", "external")
        config = self.manager.read()
        assert config.defaults == {"registry_management": "external"}

    def test_set_nested_key_creates_intermediate_dicts(self):
        """Test setting a deep nested key creates intermediate dicts."""
        self.manager.set("a.b.c", "value")
        config = self.manager.read()
        assert config.defaults == {"a": {"b": {"c": "value"}}}

    def test_set_overwrites_existing(self):
        """Test setting a key overwrites existing value."""
        config_yaml = """defaults:
  registry_management: managed
"""
        self.config_path.write_text(config_yaml, encoding="utf-8")

        self.manager.set("defaults.registry_management", "external")
        config = self.manager.read()
        assert config.defaults == {"registry_management": "external"}

    def test_unset_simple_key(self):
        """Test unsetting a simple key."""
        config_yaml = """dry_run: true
verbose: 2
"""
        self.config_path.write_text(config_yaml, encoding="utf-8")

        self.manager.unset("dry_run")
        config = self.manager.read()
        assert config.dry_run is False  # Back to default

    def test_unset_nested_key_dot_notation(self):
        """Test unsetting a nested key using dot notation."""
        config_yaml = """defaults:
  registry_management: external
  dry_run: true
"""
        self.config_path.write_text(config_yaml, encoding="utf-8")

        self.manager.unset("defaults.registry_management")
        config = self.manager.read()
        assert config.defaults == {"dry_run": True}

    def test_unset_nonexistent_key_no_error(self):
        """Test unsetting a nonexistent key doesn't raise error."""
        self.manager.unset("nonexistent")  # Should not raise
        self.manager.unset("defaults.nonexistent")  # Should not raise

    def test_unset_removes_empty_parent_dicts(self):
        """Test unsetting a key removes empty parent dicts."""
        config_yaml = """defaults:
  a:
    b: value
"""
        self.config_path.write_text(config_yaml, encoding="utf-8")

        self.manager.unset("defaults.a.b")
        config = self.manager.read()
        assert config.defaults == {}

    def test_roundtrip_preserves_all_fields(self):
        """Test read/write roundtrip preserves all fields."""
        original = Config(
            skips=["artifact-organization", "registry-management"],
            defaults={"registry_management": "external", "dry_run": True, "verbose": 1},
            dry_run=True,
            verbose=2,
        )
        self.manager.write(original)
        read_back = self.manager.read()
        assert read_back == original

    def test_config_file_at_project_root(self):
        """Test config file is at project root, not in airoom/."""
        config = Config(skips=[], defaults={}, dry_run=False, verbose=0)
        self.manager.write(config)
        assert self.config_path.exists()
        assert self.config_path == self.project_root / "airoom.config.yaml"
        assert not (self.project.airoom_dir / "airoom.config.yaml").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
