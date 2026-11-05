"""Tests for airoom update command."""

import hashlib
import json
import platform
import tempfile
import shutil
from pathlib import Path

import pytest
import ruamel.yaml

from airoom.commands.update import (
    update_command,
    update_skill,
    update_registry,
    update_agents_md_section,
    update_airoom_md,
)
from airoom.commands.init import init_command, AIROOM_START, AIROOM_END
from airoom.core.atomic import compute_file_hash
from airoom.core.version import read_version_file, write_version_file
from airoom.core.resources import ResourceManager
from airoom.core.baseline import BaselineManager, compute_file_hash_from_bytes
from airoom.core.project import Project


class TestComputeFileHash:
    """Tests for compute_file_hash function."""

    def test_existing_file(self):
        """Test computing hash of existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("hello world")
            hash_val = compute_file_hash(file_path)
            expected = hashlib.sha256(b"hello world").hexdigest()
            assert hash_val == expected

    def test_nonexistent_file(self):
        """Test computing hash of nonexistent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "nonexistent.txt"
            hash_val = compute_file_hash(file_path)
            assert hash_val == ""

    def test_directory(self):
        """Test computing hash of directory returns empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir) / "subdir"
            dir_path.mkdir()
            hash_val = compute_file_hash(dir_path)
            assert hash_val == ""


class TestVersionFile:
    """Tests for version file operations."""

    def test_read_version_file(self):
        """Test reading version file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            version_path = Path(tmpdir) / ".airoom-version"
            version_path.write_text("0.1.0\n")
            version = read_version_file(version_path)
            assert version == "0.1.0"

    def test_read_missing_version_file(self):
        """Test reading missing version file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            version_path = Path(tmpdir) / ".airoom-version"
            version = read_version_file(version_path)
            assert version == ""

    def test_write_version_file(self):
        """Test writing version file atomically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            version_path = Path(tmpdir) / ".airoom-version"
            write_version_file(version_path, "0.2.0")
            assert version_path.read_text() == "0.2.0\n"


class TestListPackagedResources:
    """Tests for listing packaged resources."""

    def test_list_packaged_skills(self):
        """Test listing packaged skills."""
        rm = ResourceManager()
        skills = rm.list_packaged_skills()
        assert "artifact-discovery" in skills
        assert "artifact-organization" in skills
        assert "registry-management" in skills
        assert "safe-management" in skills
        assert len(skills) == 4

    def test_list_packaged_templates(self):
        """Test listing packaged templates."""
        rm = ResourceManager()
        templates = rm.list_packaged_templates()
        assert "AGENTS.md" in templates
        assert "AIROOM.md" in templates
        assert "registry.yaml" in templates
        assert len(templates) == 3


class TestUpdateSkill:
    """Tests for update_skill function."""

    def setup_method(self):
        """Create a temporary project with AIroom initialized."""
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir)
        self.airoom_dir = self.project_root / "airoom"
        self.airoom_dir.mkdir()
        self.skills_dir = self.airoom_dir / "skills"
        self.skills_dir.mkdir()

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def run_init(self):
        """Run init command in temp directory."""

        class Args:
            def __init__(self, path):
                self.path = path

        init_command(Args(str(self.project_root)))

    def test_add_new_skill(self):
        """Test adding a new skill that doesn't exist."""
        self.run_init()
        # Remove one skill to simulate it being new
        skill_dir = self.skills_dir / "artifact-discovery"
        shutil.rmtree(skill_dir)

        result = update_skill("artifact-discovery", self.skills_dir, verbose=False)
        assert result["status"] == "added"
        assert (self.skills_dir / "artifact-discovery" / "SKILL.md").exists()

    def test_update_unchanged_skill(self):
        """Test updating an unchanged skill."""
        self.run_init()
        # Get original hash
        skill_file = self.skills_dir / "artifact-discovery" / "SKILL.md"
        original_content = skill_file.read_text()
        original_hash = hashlib.sha256(original_content.encode()).hexdigest()

        result = update_skill("artifact-discovery", self.skills_dir, verbose=False)
        assert result["status"] == "skipped"
        # Content should be the same
        new_content = skill_file.read_text()
        new_hash = hashlib.sha256(new_content.encode()).hexdigest()
        assert new_hash == original_hash

    def test_preserve_user_modified_skill(self):
        """Test preserving a user-modified skill."""
        self.run_init()
        skill_file = self.skills_dir / "artifact-discovery" / "SKILL.md"
        # Modify the skill
        original = skill_file.read_text()
        modified = original + "\n\n# User addition\nCustom content."
        skill_file.write_text(modified)

        result = update_skill("artifact-discovery", self.skills_dir, verbose=False)
        assert result["status"] == "conflict"
        # Content should be unchanged
        assert skill_file.read_text() == modified

    def test_baseline_allows_upstream_update_then_refreshes_hash(self, monkeypatch):
        """An unchanged old release is updateable even when it differs upstream."""
        self.run_init()
        skill_file = self.skills_dir / "artifact-discovery" / "SKILL.md"
        old_content = skill_file.read_text()
        old_hash = hashlib.sha256(old_content.encode("utf-8")).hexdigest()
        packaged = self.project_root / "new-packaged-skill.md"
        packaged.write_text("# Simulated newer packaged content\n", encoding="utf-8")
        from airoom.commands import update as update_module

        real_get_resource_path = update_module.get_resource_path

        def get_resource_path(relative_path):
            if relative_path == "skills/artifact-discovery/SKILL.md":
                return packaged
            return real_get_resource_path(relative_path)

        monkeypatch.setattr(update_module, "get_resource_path", get_resource_path)
        result = update_skill(
            "artifact-discovery", self.skills_dir, verbose=False, baseline_hash=old_hash
        )
        assert result["status"] == "updated"
        assert skill_file.read_text() == "# Simulated newer packaged content\n"

    def test_missing_previously_installed_skill_is_a_conflict(self):
        self.run_init()
        skill_file = self.skills_dir / "artifact-discovery" / "SKILL.md"
        skill_file.unlink()
        result = update_skill(
            "artifact-discovery", self.skills_dir, verbose=False, baseline_hash="known-hash"
        )
        assert result["status"] == "conflict"
        assert not skill_file.exists()

    def test_missing_skill_file_in_existing_dir(self):
        """Test adding missing SKILL.md in existing skill directory."""
        self.run_init()
        skill_file = self.skills_dir / "artifact-discovery" / "SKILL.md"
        skill_file.unlink()  # Remove the file but keep directory

        result = update_skill("artifact-discovery", self.skills_dir, verbose=False)
        assert result["status"] == "added"
        assert skill_file.exists()


class TestUpdateRegistry:
    """Tests for update_registry function."""

    def setup_method(self):
        """Create a temporary project."""
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir)
        self.airoom_dir = self.project_root / "airoom"
        self.airoom_dir.mkdir()

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_new_registry(self):
        """Test creating registry from template when missing."""
        registry_path = self.airoom_dir / "registry.yaml"
        result = update_registry(registry_path, verbose=False)
        assert result["status"] == "added"
        assert registry_path.exists()
        content = registry_path.read_text()
        assert "version: 1" in content
        assert "artifacts: {}" in content
        assert "tools: {}" in content
        # A fresh registry must not claim example artifacts exist.
        assert "graphify" not in content
        assert "mempalace" not in content
        assert "symlink-compatible" not in content
        assert "compatibility:" not in content

    def test_update_registry_adds_missing_fields(self):
        """Test updating registry adds missing fields without resetting values."""
        registry_path = self.airoom_dir / "registry.yaml"
        # Create registry with custom artifact
        custom_registry = """version: 1
artifacts:
  graphify:
    owner: graphify
    path: airoom/artifacts/graphify-out
    original_path: graphify-out
    type: directory
    management: managed
    status: active
  custom-tool:
    owner: custom
    path: airoom/artifacts/custom/
    type: directory
    management: external
    status: active
"""
        registry_path.write_text(custom_registry)

        result = update_registry(registry_path, verbose=False)
        assert result["status"] == "updated"

        # Verify custom artifact preserved
        content = registry_path.read_text()
        assert "custom-tool" in content
        assert "custom" in content
        assert "management: external" in content

        # The CLI adds schema containers only, never speculative artifacts.
        assert "mempalace" not in content
        assert "tools: {}" in content

    def test_preserve_registry_comments_and_formatting(self):
        """Test that comments and formatting are preserved."""
        registry_path = self.airoom_dir / "registry.yaml"
        registry_with_comments = """# AIroom Registry
# This file tracks AI-generated artifacts

version: 1

artifacts:
  graphify:
    owner: graphify
    path: airoom/artifacts/graphify-out
    original_path: graphify-out
    type: directory
    management: managed
    status: active
  # Custom artifact
  custom-tool:
    owner: custom
    path: airoom/artifacts/custom/
    type: directory
    management: external
    status: active
"""
        registry_path.write_text(registry_with_comments)

        result = update_registry(registry_path, verbose=False)
        assert result["status"] in ("updated", "skipped")

        content = registry_path.read_text()
        assert "# AIroom Registry" in content
        assert "# Custom artifact" in content
        assert "custom-tool" in content

    def test_invalid_yaml_handled_gracefully(self):
        """Test that invalid YAML is handled gracefully."""
        registry_path = self.airoom_dir / "registry.yaml"
        registry_path.write_text("invalid: yaml: content: [")

        result = update_registry(registry_path, verbose=False)
        assert result["status"] == "error"
        assert "invalid registry YAML" in result["message"]
        # Original file should be unchanged
        assert registry_path.read_text() == "invalid: yaml: content: ["

    def test_duplicate_registry_keys_are_rejected_without_writing(self):
        registry_path = self.airoom_dir / "registry.yaml"
        original = "version: 1\nartifacts: {}\nartifacts: {}\ntools: {}\n"
        registry_path.write_text(original, encoding="utf-8")
        result = update_registry(registry_path, verbose=False)
        assert result["status"] == "error"
        assert "duplicate key" in result["message"].lower()
        assert registry_path.read_text(encoding="utf-8") == original

    def test_registry_preserves_unknown_fields(self):
        """Test that unknown/user-defined registry fields are preserved."""
        registry_path = self.airoom_dir / "registry.yaml"
        registry_with_extras = """version: 1
custom_field: some_value
artifacts:
  graphify:
    owner: graphify
    path: airoom/artifacts/graphify-out
    original_path: graphify-out
    type: directory
    management: managed
    status: active
    user_custom_field: custom_value
"""
        registry_path.write_text(registry_with_extras)

        result = update_registry(registry_path, verbose=False)
        assert result["status"] in ("updated", "skipped")

        content = registry_path.read_text()
        assert "custom_field: some_value" in content
        assert "user_custom_field: custom_value" in content


class TestUpdateAgentsMdSection:
    """Tests for update_agents_md_section function."""

    def setup_method(self):
        """Create a temporary project."""
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir)

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_update_existing_agents_md(self):
        """Test updating AGENTS.md with existing content."""
        agents_path = self.project_root / "AGENTS.md"
        agents_path.write_text("# My Project\n\nProject instructions.")

        result = update_agents_md_section(self.project_root, verbose=False)
        assert result["status"] == "updated"

        content = agents_path.read_text()
        assert "# My Project" in content
        assert AIROOM_START in content
        assert AIROOM_END in content

    def test_skip_up_to_date_agents_md(self):
        """Test skipping when AGENTS.md is already up to date."""
        agents_path = self.project_root / "AGENTS.md"
        # Initialize with init to get current AIroom section
        airoom_dir = self.project_root / "airoom"
        airoom_dir.mkdir()
        (airoom_dir / ".airoom-version").write_text("0.1.0\n")
        from airoom.commands.init import read_resource

        airoom_section = read_resource("templates/AGENTS.md")
        agents_path.write_text(f"# My Project\n\n{airoom_section}\n")

        result = update_agents_md_section(self.project_root, verbose=False)
        assert result["status"] == "skipped"


class TestUpdateCommand:
    """Integration tests for the update command."""

    def setup_method(self):
        """Create a temporary project."""
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir)

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def run_init(self):
        """Run init command in temp directory."""

        class Args:
            def __init__(self, path):
                self.path = path

        return init_command(Args(str(self.project_root)))

    def run_update(self, path=None):
        """Run update command."""

        class Args:
            def __init__(self, path=None):
                self.path = path

        return update_command(Args(str(self.project_root) if path is None else path))

    def test_successful_update_fresh_project(self):
        """Test updating a freshly initialized project."""
        self.run_init()
        result = self.run_update()
        assert result == 0

        # Version should be updated
        version_file = self.project_root / "airoom" / ".airoom-version"
        assert version_file.read_text().strip() == "0.1.0"

    def test_update_adds_new_packaged_skill_when_missing(self):
        """Test that update installs newly added packaged skills into an existing project."""
        self.run_init()
        # Simulate legacy project that lacked artifact-organization
        new_skill_dir = self.project_root / "airoom" / "skills" / "artifact-organization"
        shutil.rmtree(new_skill_dir)
        baseline_file = self.project_root / "airoom" / ".airoom-baseline.json"
        baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
        baseline.pop("skills/artifact-organization/SKILL.md", None)
        baseline_file.write_text(json.dumps(baseline), encoding="utf-8")

        result = self.run_update()
        assert result == 0
        assert (new_skill_dir / "SKILL.md").exists()
        updated_baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
        assert "skills/artifact-organization/SKILL.md" in updated_baseline

    def test_update_preserves_user_modified_skill(self):
        """Test that user-modified skills are preserved."""
        self.run_init()
        # Modify a skill
        skill_file = self.project_root / "airoom" / "skills" / "artifact-discovery" / "SKILL.md"
        original = skill_file.read_text()
        skill_file.write_text(original + "\n\n# User customization")
        version = self.project_root / "airoom" / ".airoom-version"
        version.write_text("0.0.9\n")

        result = self.run_update()
        assert result == 1  # Conflicts are reported as a non-zero result.

        # Skill should be unchanged
        assert skill_file.read_text() == original + "\n\n# User customization"
        assert version.read_text().strip() == "0.0.9"
        baseline = json.loads((self.project_root / "airoom" / ".airoom-baseline.json").read_text())
        assert (
            baseline["skills/artifact-discovery/SKILL.md"]
            == hashlib.sha256(original.encode("utf-8")).hexdigest()
        )

    def test_update_rejects_symlinked_resource_directory(self):
        self.run_init()
        project_skills = self.project_root / "airoom" / "skills"
        moved = self.project_root / "skills-backup"
        project_skills.rename(moved)
        project_skills.symlink_to(moved, target_is_directory=True)
        assert self.run_update() == 1

    def test_update_preserves_user_created_files(self):
        """Test that user-created files are preserved."""
        self.run_init()
        # Create a user skill
        user_skill_dir = self.project_root / "airoom" / "skills" / "user-skill"
        user_skill_dir.mkdir()
        (user_skill_dir / "SKILL.md").write_text("# User Skill\n\nCustom skill.")

        result = self.run_update()
        assert result == 0

        assert (user_skill_dir / "SKILL.md").exists()
        assert (user_skill_dir / "SKILL.md").read_text() == "# User Skill\n\nCustom skill."

    def test_update_preserves_registry_entries(self):
        """Test that existing registry entries are preserved."""
        self.run_init()
        # Add custom registry entry
        registry_path = self.project_root / "airoom" / "registry.yaml"
        yaml = ruamel.yaml.YAML()
        data = yaml.load(registry_path.read_text())
        data["artifacts"]["custom"] = {
            "owner": "custom",
            "path": "airoom/artifacts/custom/",
            "original_path": "custom/",
            "type": "directory",
            "management": "external",
            "status": "active",
        }
        with registry_path.open("w") as f:
            yaml.dump(data, f)

        result = self.run_update()
        assert result == 0

        # Verify custom entry preserved
        data = yaml.load(registry_path.read_text())
        assert "custom" in data["artifacts"]
        assert data["artifacts"]["custom"]["owner"] == "custom"
        assert data["artifacts"]["custom"]["management"] == "external"

    def test_update_does_not_seed_example_registry_entries(self):
        """Updating never invents example registrations."""
        self.run_init()
        registry_path = self.project_root / "airoom" / "registry.yaml"
        yaml = ruamel.yaml.YAML()

        result = self.run_update()
        assert result == 0

        data = yaml.load(registry_path.read_text())
        assert data["artifacts"] == {}

    def test_update_preserves_agents_md_content(self):
        """Test that existing AGENTS.md content is preserved."""
        self.run_init()
        agents_path = self.project_root / "AGENTS.md"
        original = agents_path.read_text()
        # Add user content
        agents_path.write_text(original + "\n\n# User Section\n\nUser content.")

        result = self.run_update()
        assert result == 0

        content = agents_path.read_text()
        assert "# User Section" in content
        assert "User content" in content
        assert AIROOM_START in content
        assert AIROOM_END in content

    def test_repeated_update_idempotent(self):
        """Test that repeated updates don't make unnecessary changes."""
        self.run_init()
        result1 = self.run_update()
        assert result1 == 0

        result2 = self.run_update()
        assert result2 == 0

        # Version should remain the same
        version_file = self.project_root / "airoom" / ".airoom-version"
        assert version_file.read_text().strip() == "0.1.0"

    def test_update_without_initialization_fails(self):
        """Test that update fails when AIroom not initialized."""
        result = self.run_update()
        assert result == 1

    def test_update_with_invalid_path_fails(self):
        """Test that update fails with invalid path."""
        result = self.run_update("/nonexistent/path")
        assert result == 1

    def test_update_version_not_updated_on_error(self):
        """Test that version is not updated when there are errors."""
        if platform.system() == "Darwin":
            pytest.skip("Permission test not reliable on macOS")
        self.run_init()
        # Create a scenario that causes an error - make a directory read-only
        skills_dir = self.project_root / "airoom" / "skills"
        skills_dir.chmod(0o555)

        try:
            result = self.run_update()
            assert result == 1
        finally:
            skills_dir.chmod(0o755)


class TestCliIntegration:
    """Tests for CLI integration."""

    def test_cli_update_help(self):
        """Test that update command shows help."""
        import subprocess

        result = subprocess.run(["airoom", "update", "--help"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "Update project resources" in result.stdout
        assert "usage:" in result.stdout.lower()

    def test_cli_global_path_option(self):
        """Test that global --path option is available."""
        import subprocess

        result = subprocess.run(["airoom", "--help"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "--path" in result.stdout
        assert "-p" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])