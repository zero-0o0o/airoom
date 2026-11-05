"""Tests for airoom init command."""

import os
import tempfile
from pathlib import Path

import pytest

from airoom.commands.init import (
    init_command,
    find_project_root,
    create_directory,
    copy_file_if_missing,
    write_file_if_missing,
    update_agents_md,
    AIROOM_START,
    AIROOM_END,
)
from airoom.core.project import assert_safe_project_path
from airoom.core.safety import ensure_directory
from airoom.core.atomic import atomic_write
from airoom.core.resources import ResourceManager


class TestFindProjectRoot:
    """Tests for find_project_root function."""

    def test_current_directory(self):
        """Test finding project root from current directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                root = find_project_root()
                assert root == Path(tmpdir).resolve()
            finally:
                os.chdir(original_cwd)

    def test_explicit_path(self):
        """Test finding project root from explicit path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = find_project_root(Path(tmpdir))
            assert root == Path(tmpdir).resolve()


class TestCreateDirectory:
    """Tests for create_directory function."""

    def test_create_new_directory(self):
        """Test creating a new directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new_dir"
            result = create_directory(new_dir, verbose=False)
            assert result is True
            assert new_dir.exists()
            assert new_dir.is_dir()

    def test_existing_directory(self):
        """Test when directory already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_dir = Path(tmpdir) / "existing"
            existing_dir.mkdir()
            result = create_directory(existing_dir, verbose=False)
            assert result is False
            assert existing_dir.exists()

    def test_path_exists_as_file(self):
        """Test when path exists as a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "file.txt"
            file_path.write_text("content")
            with pytest.raises(FileExistsError):
                create_directory(file_path, verbose=False)


class TestCopyFileIfMissing:
    """Tests for copy_file_if_missing function."""

    def test_copy_new_file(self):
        """Test copying a file that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source.txt"
            src.write_text("source content")
            dst = Path(tmpdir) / "dest.txt"
            result = copy_file_if_missing(src, dst, verbose=False)
            assert result is True
            assert dst.read_text() == "source content"

    def test_skip_existing_file(self):
        """Test skipping when destination exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source.txt"
            src.write_text("source content")
            dst = Path(tmpdir) / "dest.txt"
            dst.write_text("existing content")
            result = copy_file_if_missing(src, dst, verbose=False)
            assert result is False
            assert dst.read_text() == "existing content"


class TestWriteFileIfMissing:
    """Tests for write_file_if_missing function."""

    def test_write_new_file(self):
        """Test writing a new file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "new.txt"
            result = write_file_if_missing(file_path, "content", verbose=False)
            assert result is True
            assert file_path.read_text() == "content"

    def test_skip_existing_file(self):
        """Test skipping when file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "existing.txt"
            file_path.write_text("existing")
            result = write_file_if_missing(file_path, "new content", verbose=False)
            assert result is False
            assert file_path.read_text() == "existing"


class TestUpdateAgentsMd:
    """Tests for update_agents_md function."""

    def test_create_new_agents_md(self):
        """Test creating AGENTS.md when it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_path = Path(tmpdir) / "AGENTS.md"
            section = f"{AIROOM_START}\n# Test\n{AIROOM_END}"
            result = update_agents_md(agents_path, section, verbose=False)
            assert result is True
            content = agents_path.read_text()
            assert AIROOM_START in content
            assert AIROOM_END in content

    def test_append_to_existing_agents_md(self):
        """Test appending AIroom section to existing AGENTS.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_path = Path(tmpdir) / "AGENTS.md"
            agents_path.write_text("# Project\n\nProject instructions.")
            section = f"{AIROOM_START}\n# AIroom\n{AIROOM_END}"
            result = update_agents_md(agents_path, section, verbose=False)
            assert result is True
            content = agents_path.read_text()
            assert "# Project" in content
            assert AIROOM_START in content
            assert AIROOM_END in content

    def test_replace_existing_section(self):
        """Test replacing existing AIroom section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_path = Path(tmpdir) / "AGENTS.md"
            old_section = f"{AIROOM_START}\n# Old AIroom\n{AIROOM_END}"
            agents_path.write_text(f"# Project\n\n{old_section}\n")
            new_section = f"{AIROOM_START}\n# New AIroom\n{AIROOM_END}"
            result = update_agents_md(agents_path, new_section, verbose=False)
            assert result is True
            content = agents_path.read_text()
            assert "# New AIroom" in content
            assert "# Old AIroom" not in content
            # Should only have one section
            assert content.count(AIROOM_START) == 1

    def test_skip_unchanged_section(self):
        """Test skipping when section is unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_path = Path(tmpdir) / "AGENTS.md"
            section = f"{AIROOM_START}\n# AIroom\n{AIROOM_END}"
            agents_path.write_text(f"# Project\n\n{section}\n")
            result = update_agents_md(agents_path, section, verbose=False)
            assert result is False
            content = agents_path.read_text()
            assert content.count(AIROOM_START) == 1


class TestInitCommand:
    """Integration tests for the init command."""

    def run_init(self, project_path: Path) -> int:
        """Run init command in a temporary directory."""

        # Create a mock args object
        class Args:
            def __init__(self, path=None):
                self.path = path

        args = Args(str(project_path))
        return init_command(args)

    def test_fresh_initialization(self):
        """Test initializing AIroom in a fresh project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            result = self.run_init(project_path)
            assert result == 0

            # Check all expected directories and files exist
            airoom_dir = project_path / "airoom"
            assert airoom_dir.exists()
            assert airoom_dir.is_dir()

            # Check .airoom-version
            version_file = airoom_dir / ".airoom-version"
            assert version_file.exists()
            assert version_file.read_text().strip() == "0.1.0"

            # Check registry.yaml
            registry = airoom_dir / "registry.yaml"
            assert registry.exists()
            content = registry.read_text()
            assert "version: 1" in content
            assert "artifacts: {}" in content
            assert "tools: {}" in content

            # Check skills
            skills_dir = airoom_dir / "skills"
            assert skills_dir.exists()
            expected_skills = [
                "artifact-discovery",
                "artifact-organization",
                "registry-management",
                "safe-management",
            ]
            for skill in expected_skills:
                skill_file = skills_dir / skill / "SKILL.md"
                assert skill_file.exists(), f"Missing skill: {skill}"
                assert len(skill_file.read_text()) > 0

            # Check AIROOM.md
            airoom_md = airoom_dir / "AIROOM.md"
            assert airoom_md.exists()
            content = airoom_md.read_text()
            assert "# AIROOM.md" in content
            assert "Choose a skill" in content

            # Check artifacts directory
            artifacts_dir = airoom_dir / "artifacts"
            assert artifacts_dir.exists()
            assert artifacts_dir.is_dir()

            # Check AGENTS.md
            agents_md = project_path / "AGENTS.md"
            assert agents_md.exists()
            content = agents_md.read_text()
            assert AIROOM_START in content
            assert AIROOM_END in content
            assert "airoom/AIROOM.md" in content

    def test_repeated_initialization(self):
        """Test running init twice doesn't duplicate content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            # First init
            result1 = self.run_init(project_path)
            assert result1 == 0

            # Second init
            result2 = self.run_init(project_path)
            assert result2 == 0

            # Verify AGENTS.md has only one AIroom section
            agents_md = project_path / "AGENTS.md"
            content = agents_md.read_text()
            assert content.count(AIROOM_START) == 1
            assert content.count(AIROOM_END) == 1

            # Verify AIROOM.md was not duplicated
            airoom_md = project_path / "airoom" / "AIROOM.md"
            assert airoom_md.exists()
            content = airoom_md.read_text()
            assert content.startswith("# AIROOM.md")

            # Verify registry wasn't overwritten
            registry = project_path / "airoom" / "registry.yaml"
            content = registry.read_text()
            assert "version: 1" in content

            # Verify skills weren't overwritten
            for skill in [
                "artifact-discovery",
                "artifact-organization",
                "registry-management",
                "safe-management",
            ]:
                skill_file = project_path / "airoom" / "skills" / skill / "SKILL.md"
                assert skill_file.exists()

    def test_preserve_existing_agents_md(self):
        """Test that existing AGENTS.md content is preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            agents_md = project_path / "AGENTS.md"
            original_content = "# My Project\n\n## Instructions\n\nDo this and that.\n"
            agents_md.write_text(original_content)

            result = self.run_init(project_path)
            assert result == 0

            content = agents_md.read_text()
            assert "# My Project" in content
            assert "Do this and that" in content
            assert AIROOM_START in content
            assert AIROOM_END in content

    def test_preserve_existing_registry(self):
        """Test that existing registry.yaml is preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            airoom_dir = project_path / "airoom"
            airoom_dir.mkdir(parents=True)
            registry = airoom_dir / "registry.yaml"
            custom_registry = "version: 1\nartifacts:\n  custom:\n    owner: custom-tool\n"
            registry.write_text(custom_registry)

            result = self.run_init(project_path)
            assert result == 0

            content = registry.read_text()
            assert "custom-tool" in content
            assert "custom:" in content

    def test_preserve_existing_skills(self):
        """Test that existing skill files are preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            airoom_dir = project_path / "airoom"
            skills_dir = airoom_dir / "skills"
            skill_dir = skills_dir / "artifact-discovery"
            skill_dir.mkdir(parents=True)
            skill_file = skill_dir / "SKILL.md"
            custom_skill = "# Custom Artifact Discovery\n\nMy custom skill."
            skill_file.write_text(custom_skill)

            result = self.run_init(project_path)
            assert result == 0

            content = skill_file.read_text()
            assert "Custom Artifact Discovery" in content
            assert "My custom skill" in content

    def test_invalid_project_path(self):
        """Test init with invalid/non-existent path."""

        class Args:
            def __init__(self, path):
                self.path = path

        args = Args("/nonexistent/path/that/does/not/exist")
        assert init_command(args) == 1

    def test_init_rejects_symlinked_airoom_directory(self):
        with (
            tempfile.TemporaryDirectory() as project_tmp,
            tempfile.TemporaryDirectory() as outside_tmp,
        ):
            project = Path(project_tmp)
            (project / "airoom").symlink_to(Path(outside_tmp), target_is_directory=True)

            class Args:
                path = str(project)

            assert init_command(Args()) == 1
            assert list(Path(outside_tmp).iterdir()) == []

    def test_init_preserves_malformed_airoom_markers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            agents = project / "AGENTS.md"
            original = "# instructions\n<!-- AIROOM:START -->\nmissing end marker\n"
            agents.write_text(original, encoding="utf-8")

            class Args:
                path = str(project)

            assert init_command(Args()) == 1
            assert agents.read_text(encoding="utf-8") == original

    def test_permission_error_handling(self):
        """Test handling of permission errors."""
        # This is difficult to test without root, skip for now
        pass

    def test_init_with_explicit_path(self):
        """Test init with explicit project path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "my-project"
            project_path.mkdir()

            class Args:
                def __init__(self, path):
                    self.path = path

            args = Args(str(project_path))
            result = init_command(args)
            assert result == 0

            airoom_dir = project_path / "airoom"
            assert airoom_dir.exists()


class TestCliIntegration:
    """Tests for CLI integration."""

    def test_cli_import(self):
        """Test that CLI module can be imported."""
        from airoom.cli import main

        assert callable(main)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])