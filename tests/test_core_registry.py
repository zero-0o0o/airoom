"""Tests for airoom.core.registry module."""

import tempfile
from pathlib import Path

import pytest

from airoom.core.project import Project
from airoom.core.registry import (
    RegistryError,
    _yaml,
    _relative_path,
    validate_registry,
    parse_registry,
    dump_registry,
    RegistryManager,
)


VALID_REGISTRY = """version: 1
artifacts:
  custom:
    owner: custom-tool
    path: airoom/artifacts/custom
    type: directory
    management: managed
    status: active
    future_field: preserved
tools: {}
"""


class TestYAMLHelper:
    """Tests for _yaml helper function."""

    def test_yaml_preserves_quotes_and_indent(self):
        """Test that _yaml returns configured YAML instance."""
        yaml = _yaml()
        assert yaml.preserve_quotes is True
        # Test dump produces expected format
        from io import StringIO

        output = StringIO()
        yaml.dump({"key": "value"}, output)
        result = output.getvalue()
        assert "key: value" in result


class TestRelativePath:
    """Tests for _relative_path function."""

    def test_valid_relative_path(self):
        """Test that a valid relative path is returned stripped."""
        result = _relative_path("airoom/artifacts/test", "test.field")
        assert result == "airoom/artifacts/test"

    def test_valid_path_with_trailing_slash(self):
        """Test that trailing slash is stripped."""
        result = _relative_path("airoom/artifacts/test/", "test.field")
        assert result == "airoom/artifacts/test"

    def test_absolute_path_raises_error(self):
        """Test that absolute path raises RegistryError."""
        with pytest.raises(RegistryError, match="must not be absolute or contain"):
            _relative_path("/absolute/path", "test.field")

    def test_path_with_double_dot_raises_error(self):
        """Test that path with .. raises RegistryError."""
        with pytest.raises(RegistryError, match="must not be absolute or contain"):
            _relative_path("airoom/../outside", "test.field")

    def test_path_with_backslash_raises_error(self):
        """Test that path with backslash raises RegistryError."""
        with pytest.raises(RegistryError, match="must not be absolute or contain"):
            _relative_path("airoom\\artifacts", "test.field")

    def test_empty_path_raises_error(self):
        """Test that empty path raises RegistryError."""
        with pytest.raises(RegistryError, match="must be a non-empty project-relative path"):
            _relative_path("", "test.field")

    def test_whitespace_only_path_raises_error(self):
        """Test that whitespace-only path raises RegistryError."""
        with pytest.raises(RegistryError, match="must be a non-empty project-relative path"):
            _relative_path("   ", "test.field")

    def test_non_string_path_raises_error(self):
        """Test that non-string path raises RegistryError."""
        with pytest.raises(RegistryError, match="must be a non-empty project-relative path"):
            _relative_path(123, "test.field")

    def test_path_with_empty_component_normalized(self):
        """Test that path with empty component (//) is normalized (original behavior).

        Note: PurePosixPath normalizes '//' away, so this test verifies
        the current behavior (which doesn't catch it at the parts level).
        The backslash check catches it on the raw string instead.
        """
        # This is the original behavior - it gets normalized and passes
        result = _relative_path("airoom//artifacts", "test.field")
        assert result == "airoom//artifacts"  # Raw string preserved in return

    def test_path_with_dot_component_normalized(self):
        """Test that path with . component is normalized (original behavior).

        Note: PurePosixPath normalizes './' away, so this test verifies
        the current behavior (which doesn't catch it at the parts level).
        """
        # This is the original behavior - it gets normalized and passes
        result = _relative_path("airoom/./artifacts", "test.field")
        assert result == "airoom/./artifacts"  # Raw string preserved in return


class TestValidateRegistry:
    """Tests for validate_registry function."""

    def test_valid_registry_passes(self):
        """Test that a valid registry passes validation."""
        data = parse_registry(VALID_REGISTRY)
        validate_registry(data)  # Should not raise

    def test_valid_registry_allows_unknown_fields(self):
        """Test that unknown fields are preserved and allowed."""
        data = parse_registry(VALID_REGISTRY)
        assert data["artifacts"]["custom"]["future_field"] == "preserved"

    def test_empty_artifacts_and_tools_passes(self):
        """Test that empty artifacts and tools sections pass."""
        data = parse_registry("version: 1\nartifacts: {}\ntools: {}\n")
        assert data["artifacts"] == {}
        assert data["tools"] == {}

    def test_non_dict_registry_raises_error(self):
        """Test that non-dict registry raises RegistryError."""
        with pytest.raises(RegistryError, match="registry must be a YAML mapping"):
            validate_registry("not a dict")

    def test_version_must_be_integer_1(self):
        """Test that version must be integer 1."""
        with pytest.raises(RegistryError, match="registry.version must be integer 1"):
            validate_registry({"version": "1", "artifacts": {}, "tools": {}})
        with pytest.raises(RegistryError, match="registry.version must be integer 1"):
            validate_registry({"version": 2, "artifacts": {}, "tools": {}})
        with pytest.raises(RegistryError, match="registry.version must be integer 1"):
            validate_registry({"version": True, "artifacts": {}, "tools": {}})

    def test_missing_version_raises_error(self):
        """Test that missing version raises RegistryError."""
        with pytest.raises(RegistryError, match="registry.version must be integer 1"):
            validate_registry({"artifacts": {}, "tools": {}})

    def test_artifacts_must_be_mapping(self):
        """Test that artifacts must be a mapping."""
        with pytest.raises(
            RegistryError, match="registry.artifacts and registry.tools must be mappings"
        ):
            validate_registry({"version": 1, "artifacts": [], "tools": {}})

    def test_tools_must_be_mapping(self):
        """Test that tools must be a mapping."""
        with pytest.raises(
            RegistryError, match="registry.artifacts and registry.tools must be mappings"
        ):
            validate_registry({"version": 1, "artifacts": {}, "tools": []})

    def test_artifact_id_format_validation(self):
        """Test artifact ID format validation."""
        # Empty and whitespace-only are rejected
        for invalid_id in ["", "  "]:
            data = {
                "version": 1,
                "artifacts": {
                    invalid_id: {
                        "owner": "tool",
                        "path": "airoom/artifacts/test",
                        "type": "file",
                        "management": "managed",
                        "status": "active",
                    }
                },
                "tools": {},
            }
            with pytest.raises(RegistryError, match="invalid artifact id"):
                validate_registry(data)
        # Forward slash is rejected
        data = {
            "version": 1,
            "artifacts": {
                "invalid/id": {
                    "owner": "tool",
                    "path": "airoom/artifacts/test",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                }
            },
            "tools": {},
        }
        with pytest.raises(RegistryError, match="invalid artifact id"):
            validate_registry(data)
        # Backslash is NOT rejected (original behavior only checks for forward slash)
        data = {
            "version": 1,
            "artifacts": {
                "another\\\\id": {
                    "owner": "tool",
                    "path": "airoom/artifacts/test",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                }
            },
            "tools": {},
        }
        validate_registry(data)  # Should not raise

    def test_artifact_entry_must_be_mapping(self):
        """Test that artifact entry must be a mapping."""
        data = {"version": 1, "artifacts": {"test": "not a mapping"}, "tools": {}}
        with pytest.raises(RegistryError, match="artifacts.test must be a mapping"):
            validate_registry(data)

    def test_artifact_required_fields(self):
        """Test that all required artifact fields are validated."""
        required_fields = ["owner", "path", "type", "management", "status"]
        for field in required_fields:
            data = {
                "version": 1,
                "artifacts": {"test": {f: "value" for f in required_fields if f != field}},
                "tools": {},
            }
            with pytest.raises(RegistryError, match=f"artifacts.test.{field} is required"):
                validate_registry(data)

    def test_artifact_owner_must_be_non_empty_string(self):
        """Test that artifact owner must be non-empty string."""
        data = {
            "version": 1,
            "artifacts": {
                "test": {
                    "owner": "",
                    "path": "airoom/artifacts/test",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                }
            },
            "tools": {},
        }
        with pytest.raises(RegistryError, match="artifacts.test.owner must be a non-empty string"):
            validate_registry(data)

    def test_artifact_path_validation(self):
        """Test artifact path validation."""
        # Absolute path
        data = {
            "version": 1,
            "artifacts": {
                "test": {
                    "owner": "t",
                    "path": "/abs",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                }
            },
            "tools": {},
        }
        with pytest.raises(RegistryError, match="must not be absolute or contain"):
            validate_registry(data)

    def test_managed_artifact_must_be_under_airoom_artifacts(self):
        """Test that managed artifact path must be under airoom/artifacts/."""
        data = {
            "version": 1,
            "artifacts": {
                "test": {
                    "owner": "t",
                    "path": "generated/test",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                }
            },
            "tools": {},
        }
        with pytest.raises(
            RegistryError, match="managed artifact path must be under airoom/artifacts/"
        ):
            validate_registry(data)

    def test_external_artifact_can_be_anywhere(self):
        """Test that external artifact can have any valid path."""
        data = {
            "version": 1,
            "artifacts": {
                "test": {
                    "owner": "t",
                    "path": "external/test",
                    "type": "file",
                    "management": "external",
                    "status": "active",
                }
            },
            "tools": {},
        }
        validate_registry(data)  # Should not raise

    def test_artifact_type_validation(self):
        """Test artifact type must be file or directory."""
        data = {
            "version": 1,
            "artifacts": {
                "test": {
                    "owner": "t",
                    "path": "airoom/artifacts/test",
                    "type": "invalid",
                    "management": "managed",
                    "status": "active",
                }
            },
            "tools": {},
        }
        with pytest.raises(RegistryError, match="artifacts.test.type must be file or directory"):
            validate_registry(data)

    def test_artifact_status_validation(self):
        """Test artifact status must be active or inactive."""
        data = {
            "version": 1,
            "artifacts": {
                "test": {
                    "owner": "t",
                    "path": "airoom/artifacts/test",
                    "type": "file",
                    "management": "managed",
                    "status": "invalid",
                }
            },
            "tools": {},
        }
        with pytest.raises(RegistryError, match="artifacts.test.status must be active or inactive"):
            validate_registry(data)

    def test_duplicate_artifact_paths_rejected(self):
        """Test that duplicate artifact paths are rejected."""
        data = {
            "version": 1,
            "artifacts": {
                "a": {
                    "owner": "t",
                    "path": "airoom/artifacts/same",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                },
                "b": {
                    "owner": "t",
                    "path": "airoom/artifacts/same",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                },
            },
            "tools": {},
        }
        with pytest.raises(RegistryError, match="duplicate artifact path"):
            validate_registry(data)

    def test_duplicate_original_paths_rejected(self):
        """Test that duplicate original_path values are rejected."""
        data = {
            "version": 1,
            "artifacts": {
                "a": {
                    "owner": "t",
                    "path": "airoom/artifacts/a",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                    "original_path": "orig/path",
                },
                "b": {
                    "owner": "t",
                    "path": "airoom/artifacts/b",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                    "original_path": "orig/path",
                },
            },
            "tools": {},
        }
        with pytest.raises(RegistryError, match="duplicate original_path"):
            validate_registry(data)

    def test_tool_id_format_validation(self):
        """Test tool ID format validation."""
        # Empty and whitespace-only are rejected
        for invalid_id in ["", "  "]:
            data = {
                "version": 1,
                "artifacts": {},
                "tools": {invalid_id: {"name": "Test Tool", "status": "active"}},
            }
            with pytest.raises(RegistryError, match="invalid tool id"):
                validate_registry(data)
        # Forward slash is rejected
        data = {
            "version": 1,
            "artifacts": {},
            "tools": {"invalid/id": {"name": "Test Tool", "status": "active"}},
        }
        with pytest.raises(RegistryError, match="invalid tool id"):
            validate_registry(data)
        # Backslash is NOT rejected (original behavior only checks for forward slash)
        data = {
            "version": 1,
            "artifacts": {},
            "tools": {"another\\\\id": {"name": "Test Tool", "status": "active"}},
        }
        validate_registry(data)  # Should not raise

    def test_tool_entry_must_be_mapping(self):
        """Test that tool entry must be a mapping."""
        data = {"version": 1, "artifacts": {}, "tools": {"test": "not a mapping"}}
        with pytest.raises(RegistryError, match="tools.test must be a mapping"):
            validate_registry(data)

    def test_tool_name_required_and_non_empty(self):
        """Test that tool name is required and non-empty."""
        data = {"version": 1, "artifacts": {}, "tools": {"test": {"status": "active"}}}
        with pytest.raises(RegistryError, match="tools.test.name must be a non-empty string"):
            validate_registry(data)
        data = {"version": 1, "artifacts": {}, "tools": {"test": {"name": "", "status": "active"}}}
        with pytest.raises(RegistryError, match="tools.test.name must be a non-empty string"):
            validate_registry(data)

    def test_tool_status_validation(self):
        """Test tool status must be active or inactive."""
        data = {
            "version": 1,
            "artifacts": {},
            "tools": {"test": {"name": "Test", "status": "invalid"}},
        }
        with pytest.raises(RegistryError, match="tools.test.status must be active or inactive"):
            validate_registry(data)

    def test_tool_config_path_validation(self):
        """Test tool config_path validation."""
        data = {
            "version": 1,
            "artifacts": {},
            "tools": {"test": {"name": "Test", "status": "active", "config_path": "/abs"}},
        }
        with pytest.raises(RegistryError, match="must not be absolute or contain"):
            validate_registry(data)

    def test_tool_runtime_path_validation(self):
        """Test tool runtime_path validation."""
        data = {
            "version": 1,
            "artifacts": {},
            "tools": {"test": {"name": "Test", "status": "active", "runtime_path": "bad\\path"}},
        }
        with pytest.raises(RegistryError, match="must not be absolute or contain"):
            validate_registry(data)


class TestParseRegistry:
    """Tests for parse_registry function."""

    def test_valid_registry_parses(self):
        """Test that valid registry parses correctly."""
        data = parse_registry(VALID_REGISTRY)
        assert data["version"] == 1
        assert "custom" in data["artifacts"]
        assert data["artifacts"]["custom"]["future_field"] == "preserved"

    def test_duplicate_yaml_keys_rejected(self):
        """Test that duplicate YAML keys are rejected."""
        with pytest.raises(RegistryError, match="duplicate key"):
            parse_registry("version: 1\nversion: 1\nartifacts: {}\ntools: {}\n")

    def test_invalid_yaml_raises_error(self):
        """Test that invalid YAML raises RegistryError."""
        with pytest.raises(RegistryError, match="invalid registry YAML"):
            parse_registry("version: 1\n  artifacts: not valid yaml")


class TestDumpRegistry:
    """Tests for dump_registry function."""

    def test_dump_valid_registry(self):
        """Test dumping a valid registry."""
        data = parse_registry(VALID_REGISTRY)
        output = dump_registry(data)
        assert "version: 1" in output
        assert "custom:" in output
        assert "future_field: preserved" in output

    def test_dump_validates_before_dump(self):
        """Test that dump_registry validates before dumping."""
        data = {
            "version": 1,
            "artifacts": {
                "test": {
                    "owner": "t",
                    "path": "/abs",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                }
            },
            "tools": {},
        }
        with pytest.raises(RegistryError, match="must not be absolute or contain"):
            dump_registry(data)


class TestRegistryManager:
    """Tests for RegistryManager class."""

    def setup_method(self):
        """Create a temporary project directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir).resolve()
        self.project = Project(self.project_root)
        # Create the airoom directory structure
        self.project.airoom_dir.mkdir(parents=True, exist_ok=True)
        self.manager = RegistryManager(self.project)

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_with_project(self):
        """Test RegistryManager initialization with Project."""
        assert self.manager.project == self.project
        assert self.manager.registry_path == self.project.registry_path

    def test_read_nonexistent_registry_returns_default(self):
        """Test reading a nonexistent registry returns default structure."""
        data = self.manager.read()
        assert data == {"version": 1, "artifacts": {}, "tools": {}}

    def test_read_existing_registry(self):
        """Test reading an existing registry."""
        # Write a registry first
        content = VALID_REGISTRY
        self.project.registry_path.write_text(content, encoding="utf-8")

        data = self.manager.read()
        assert data["version"] == 1
        assert "custom" in data["artifacts"]
        assert data["artifacts"]["custom"]["future_field"] == "preserved"

    def test_read_invalid_registry_raises_error(self):
        """Test reading invalid registry raises RegistryError."""
        self.project.registry_path.write_text(
            "version: 1\nversion: 1\nartifacts: {}\ntools: {}\n", encoding="utf-8"
        )
        with pytest.raises(RegistryError, match="duplicate key"):
            self.manager.read()

    def test_write_registry(self):
        """Test writing a registry."""
        data = {"version": 1, "artifacts": {}, "tools": {}}
        self.manager.write(data)

        content = self.project.registry_path.read_text(encoding="utf-8")
        assert "version: 1" in content
        assert "artifacts: {}" in content
        assert "tools: {}" in content

    def test_write_invalid_registry_raises_error(self):
        """Test writing invalid registry raises RegistryError."""
        data = {
            "version": 1,
            "artifacts": {
                "test": {
                    "owner": "t",
                    "path": "/abs",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                }
            },
            "tools": {},
        }
        with pytest.raises(RegistryError, match="must not be absolute or contain"):
            self.manager.write(data)
        # File should not be created
        assert not self.project.registry_path.exists()

    def test_write_uses_atomic_write(self):
        """Test that write uses atomic write (creates no temp files on success)."""
        data = {"version": 1, "artifacts": {}, "tools": {}}
        self.manager.write(data)
        tmp_files = list(self.project.airoom_dir.glob("*.tmp"))
        assert tmp_files == []

    def test_validate_valid_registry(self):
        """Test validate on valid registry."""
        self.manager.write({"version": 1, "artifacts": {}, "tools": {}})
        is_valid, errors = self.manager.validate()
        assert is_valid is True
        assert errors == []

    def test_validate_invalid_registry(self):
        """Test validate on invalid registry."""
        self.project.registry_path.write_text(
            "version: 1\nversion: 1\nartifacts: {}\ntools: {}\n", encoding="utf-8"
        )
        is_valid, errors = self.manager.validate()
        assert is_valid is False
        assert len(errors) > 0
        assert any("duplicate key" in e for e in errors)

    def test_validate_nonexistent_registry(self):
        """Test validate on nonexistent registry (should be valid default)."""
        is_valid, errors = self.manager.validate()
        assert is_valid is True
        assert errors == []

    def test_add_artifact(self):
        """Test adding an artifact."""
        self.manager.add_artifact(
            "my-artifact",
            {
                "owner": "my-tool",
                "path": "airoom/artifacts/my-artifact",
                "type": "file",
                "management": "managed",
                "status": "active",
            },
        )

        data = self.manager.read()
        assert "my-artifact" in data["artifacts"]
        assert data["artifacts"]["my-artifact"]["owner"] == "my-tool"

    def test_add_artifact_validates_entry(self):
        """Test that add_artifact validates the entry."""
        with pytest.raises(RegistryError, match="must not be absolute or contain"):
            self.manager.add_artifact(
                "bad",
                {
                    "owner": "t",
                    "path": "/abs",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                },
            )

    def test_add_artifact_duplicate_id_raises_error(self):
        """Test that adding duplicate artifact ID raises error."""
        self.manager.add_artifact(
            "my-artifact",
            {
                "owner": "my-tool",
                "path": "airoom/artifacts/my-artifact",
                "type": "file",
                "management": "managed",
                "status": "active",
            },
        )
        with pytest.raises(RegistryError, match="already exists"):
            self.manager.add_artifact(
                "my-artifact",
                {
                    "owner": "other-tool",
                    "path": "airoom/artifacts/other",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                },
            )

    def test_add_artifact_duplicate_path_raises_error(self):
        """Test that adding artifact with duplicate path raises error."""
        self.manager.add_artifact(
            "artifact1",
            {
                "owner": "tool1",
                "path": "airoom/artifacts/shared",
                "type": "file",
                "management": "managed",
                "status": "active",
            },
        )
        with pytest.raises(RegistryError, match="duplicate artifact path"):
            self.manager.add_artifact(
                "artifact2",
                {
                    "owner": "tool2",
                    "path": "airoom/artifacts/shared",
                    "type": "file",
                    "management": "managed",
                    "status": "active",
                },
            )

    def test_remove_artifact(self):
        """Test removing an artifact."""
        self.manager.add_artifact(
            "my-artifact",
            {
                "owner": "my-tool",
                "path": "airoom/artifacts/my-artifact",
                "type": "file",
                "management": "managed",
                "status": "active",
            },
        )
        self.manager.remove_artifact("my-artifact")

        data = self.manager.read()
        assert "my-artifact" not in data["artifacts"]

    def test_remove_nonexistent_artifact_raises_error(self):
        """Test removing nonexistent artifact raises error."""
        with pytest.raises(RegistryError, match="not found"):
            self.manager.remove_artifact("nonexistent")

    def test_add_tool(self):
        """Test adding a tool."""
        self.manager.add_tool(
            "my-tool", {"name": "My Tool", "status": "active", "config_path": "airoom/config.yaml"}
        )

        data = self.manager.read()
        assert "my-tool" in data["tools"]
        assert data["tools"]["my-tool"]["name"] == "My Tool"

    def test_add_tool_validates_entry(self):
        """Test that add_tool validates the entry."""
        with pytest.raises(RegistryError, match="must be a non-empty string"):
            self.manager.add_tool("bad", {"name": "", "status": "active"})

    def test_add_tool_duplicate_id_raises_error(self):
        """Test that adding duplicate tool ID raises error."""
        self.manager.add_tool("my-tool", {"name": "My Tool", "status": "active"})
        with pytest.raises(RegistryError, match="already exists"):
            self.manager.add_tool("my-tool", {"name": "Other Tool", "status": "active"})

    def test_remove_tool(self):
        """Test removing a tool."""
        self.manager.add_tool("my-tool", {"name": "My Tool", "status": "active"})
        self.manager.remove_tool("my-tool")

        data = self.manager.read()
        assert "my-tool" not in data["tools"]

    def test_remove_nonexistent_tool_raises_error(self):
        """Test removing nonexistent tool raises error."""
        with pytest.raises(RegistryError, match="not found"):
            self.manager.remove_tool("nonexistent")

    def test_write_preserves_existing_permissions(self):
        """Test that write preserves existing file permissions."""
        # Create registry with specific permissions
        self.project.registry_path.write_text(VALID_REGISTRY, encoding="utf-8")
        self.project.registry_path.chmod(0o600)
        original_mode = self.project.registry_path.stat().st_mode & 0o777

        self.manager.write({"version": 1, "artifacts": {}, "tools": {}})

        new_mode = self.project.registry_path.stat().st_mode & 0o777
        assert new_mode == original_mode


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
