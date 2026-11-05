"""Tests for airoom.core.resources module."""

import pytest

from airoom.core.resources import ResourceManager


class TestResourceManager:
    """Tests for ResourceManager class."""

    def test_get_resource_path(self):
        """Test getting path to a packaged resource."""
        manager = ResourceManager()
        path = manager.get_resource_path("skills/registry-management/SKILL.md")
        assert path.exists()
        assert path.name == "SKILL.md"
        assert "registry-management" in str(path)

    def test_get_resource_path_nonexistent(self):
        """Test getting path to nonexistent resource returns path that doesn't exist."""
        manager = ResourceManager()
        path = manager.get_resource_path("nonexistent/path.txt")
        assert not path.exists()

    def test_read_resource(self):
        """Test reading a packaged resource file."""
        manager = ResourceManager()
        content = manager.read_resource("skills/registry-management/SKILL.md")
        assert isinstance(content, str)
        assert len(content) > 0
        assert "registry" in content.lower()

    def test_read_resource_nonexistent(self):
        """Test reading nonexistent resource raises FileNotFoundError."""
        manager = ResourceManager()
        with pytest.raises(FileNotFoundError):
            manager.read_resource("nonexistent/path.txt")

    def test_list_packaged_skills(self):
        """Test listing all packaged skills."""
        manager = ResourceManager()
        skills = manager.list_packaged_skills()
        assert isinstance(skills, list)
        assert len(skills) > 0
        assert "registry-management" in skills
        assert "artifact-organization" in skills
        assert "safe-management" in skills
        assert "artifact-discovery" in skills
        # Should be sorted
        assert skills == sorted(skills)

    def test_list_packaged_templates(self):
        """Test listing all packaged templates."""
        manager = ResourceManager()
        templates = manager.list_packaged_templates()
        assert isinstance(templates, list)
        assert len(templates) > 0
        assert "AGENTS.md" in templates
        assert "registry.yaml" in templates
        assert "AIROOM.md" in templates
        # Should be sorted
        assert templates == sorted(templates)

    def test_resource_path_structure(self):
        """Test that resource paths follow expected structure."""
        manager = ResourceManager()
        skills_dir = manager.get_resource_path("skills")
        templates_dir = manager.get_resource_path("templates")

        assert skills_dir.exists()
        assert skills_dir.is_dir()
        assert templates_dir.exists()
        assert templates_dir.is_dir()

        # Check skills subdirectories
        skill_names = manager.list_packaged_skills()
        for skill_name in skill_names:
            skill_path = skills_dir / skill_name
            assert skill_path.exists()
            assert skill_path.is_dir()
            skill_file = skill_path / "SKILL.md"
            assert skill_file.exists()
            assert skill_file.is_file()

        # Check templates
        template_names = manager.list_packaged_templates()
        for template_name in template_names:
            template_path = templates_dir / template_name
            assert template_path.exists()
            assert template_path.is_file()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
