"""Tests for airoom.core.project module."""

import tempfile
from pathlib import Path

import pytest

from airoom.core.project import (
    Project,
    find_project_root,
    assert_safe_project_path,
)


class TestProjectInitialization:
    """Tests for Project class initialization and path properties."""

    def test_project_initialization_with_path(self):
        """Test Project initialization with a path sets all properties correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = Project(root)

            assert project.root == root.resolve()
            assert project.airoom_dir == project.root / "airoom"
            assert project.skills_dir == project.airoom_dir / "skills"
            assert project.artifacts_dir == project.airoom_dir / "artifacts"
            assert project.registry_path == project.airoom_dir / "registry.yaml"
            assert project.version_path == project.airoom_dir / ".airoom-version"
            assert project.baseline_path == project.airoom_dir / ".airoom-baseline.json"
            assert project.airoom_md_path == project.airoom_dir / "AIROOM.md"
            assert project.agents_path == project.root / "AGENTS.md"

    def test_project_initialization_resolves_path(self):
        """Test that Project initialization resolves the root path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Use a relative path that will be resolved
            project = Project(root)
            assert project.root.is_absolute()


class TestFindProjectRoot:
    """Tests for find_project_root function."""

    def test_current_directory(self):
        """Test finding project root from current directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                import os

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

    def test_explicit_path_string(self):
        """Test finding project root from explicit string path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = find_project_root(tmpdir)
            assert root == Path(tmpdir).resolve()

    def test_nonexistent_path_raises_error(self):
        """Test that nonexistent path raises NotADirectoryError."""
        with pytest.raises(NotADirectoryError):
            find_project_root(Path("/nonexistent/path/that/does/not/exist"))

    def test_file_path_raises_error(self):
        """Test that a file path raises NotADirectoryError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "file.txt"
            file_path.write_text("content")
            with pytest.raises(NotADirectoryError):
                find_project_root(file_path)


class TestAssertSafeProjectPath:
    """Tests for assert_safe_project_path function."""

    def setup_method(self):
        """Create a temporary project directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir).resolve()

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_safe_path_within_project(self):
        """Test that a path within the project passes."""
        target = self.project_root / "airoom" / "skills"
        assert_safe_project_path(self.project_root, target)

    def test_safe_path_at_project_root(self):
        """Test that the project root itself passes."""
        assert_safe_project_path(self.project_root, self.project_root)

    def test_safe_path_deeply_nested(self):
        """Test that a deeply nested path within project passes."""
        target = self.project_root / "airoom" / "skills" / "some-skill" / "SKILL.md"
        assert_safe_project_path(self.project_root, target)

    def test_path_outside_project_raises_error(self):
        """Test that a path outside the project raises ValueError."""
        outside = Path("/tmp/outside-project")
        with pytest.raises(ValueError, match="Path is outside the project"):
            assert_safe_project_path(self.project_root, outside)

    def test_path_traversal_raises_error(self):
        """Test that path traversal (../) raises ValueError."""
        target = self.project_root / "airoom" / ".." / ".." / "etc" / "passwd"
        with pytest.raises(ValueError, match="Path resolves outside the project"):
            assert_safe_project_path(self.project_root, target)

    def test_symlink_in_path_raises_error(self):
        """Test that a symlink in the path raises ValueError."""
        # Create a real directory outside the project
        outside_dir = Path("/tmp") / f"airoom-outside-{id(self)}"
        outside_dir.mkdir(exist_ok=True)

        # Create a symlink inside the project pointing outside
        link_path = self.project_root / "airoom" / "external-link"
        self.project_root.joinpath("airoom").mkdir(parents=True, exist_ok=True)
        link_path.symlink_to(outside_dir, target_is_directory=True)

        with pytest.raises(ValueError, match="Refusing to follow symlink"):
            assert_safe_project_path(self.project_root, link_path / "SKILL.md")

        # Cleanup
        link_path.unlink()
        outside_dir.rmdir()

    def test_symlink_target_outside_project_raises_error(self):
        """Test that a symlink whose resolved target is outside raises ValueError."""
        # Create a real directory outside the project
        outside_dir = Path("/tmp") / f"airoom-target-{id(self)}"
        outside_dir.mkdir(exist_ok=True)
        target_file = outside_dir / "target.txt"
        target_file.write_text("target")

        # Create a symlink inside the project pointing to the outside file
        self.project_root.joinpath("airoom").mkdir(parents=True, exist_ok=True)
        link_path = self.project_root / "airoom" / "link-to-outside.txt"
        link_path.symlink_to(target_file)

        # The symlink itself is detected first, so we get the symlink error
        with pytest.raises(ValueError, match="Refusing to follow symlink"):
            assert_safe_project_path(self.project_root, link_path)

        # Cleanup
        link_path.unlink()
        target_file.unlink()
        outside_dir.rmdir()

    def test_relative_path_resolution(self):
        """Test that relative paths are resolved correctly."""
        target = self.project_root / "airoom" / "skills" / ".." / "artifacts"
        assert_safe_project_path(self.project_root, target)


class TestProjectAssertSafe:
    """Tests for Project.assert_safe method."""

    def setup_method(self):
        """Create a temporary project directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir).resolve()
        self.project = Project(self.project_root)

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_assert_safe_delegates_to_standalone_function(self):
        """Test that Project.assert_safe delegates to assert_safe_project_path."""
        target = self.project_root / "airoom" / "skills"
        self.project.assert_safe(target)  # Should not raise

    def test_assert_safe_rejects_outside_path(self):
        """Test that Project.assert_safe rejects paths outside project."""
        outside = Path("/tmp/outside-project")
        with pytest.raises(ValueError, match="Path is outside the project"):
            self.project.assert_safe(outside)

    def test_assert_safe_rejects_symlink(self):
        """Test that Project.assert_safe rejects symlinks."""
        outside_dir = Path("/tmp") / f"airoom-outside-{id(self)}"
        outside_dir.mkdir(exist_ok=True)

        link_path = self.project_root / "airoom" / "external-link"
        self.project_root.joinpath("airoom").mkdir(parents=True, exist_ok=True)
        link_path.symlink_to(outside_dir, target_is_directory=True)

        with pytest.raises(ValueError, match="Refusing to follow symlink"):
            self.project.assert_safe(link_path / "SKILL.md")

        link_path.unlink()
        outside_dir.rmdir()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
