"""Tests for airoom init command (Typer-based)."""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from airoom.cli import app
from airoom.commands_typer.init import AIROOM_START, AIROOM_END


class TestTyperInitCommand:
    """Integration tests for the Typer init command."""

    def run_init(self, project_path: Path, args: list[str] | None = None) -> tuple[int, str]:
        """Run init command in a temporary directory."""
        runner = CliRunner()
        cmd = ["init"]
        if args:
            cmd.extend(args)
        if project_path:
            cmd.extend(["--path", str(project_path)])
        result = runner.invoke(app, cmd)
        return result.exit_code, result.output

    def test_fresh_initialization(self):
        """Test initializing AIroom in a fresh project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            exit_code, output = self.run_init(project_path)
            assert exit_code == 0

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
            exit_code1, _ = self.run_init(project_path)
            assert exit_code1 == 0

            # Second init
            exit_code2, _ = self.run_init(project_path)
            assert exit_code2 == 0

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

            exit_code, _ = self.run_init(project_path)
            assert exit_code == 0

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

            exit_code, _ = self.run_init(project_path)
            assert exit_code == 0

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

            exit_code, _ = self.run_init(project_path)
            assert exit_code == 0

            content = skill_file.read_text()
            assert "Custom Artifact Discovery" in content
            assert "My custom skill" in content

    def test_invalid_project_path(self):
        """Test init with invalid/non-existent path."""
        exit_code, output = self.run_init(Path("/nonexistent/path/that/does/not/exist"))
        assert exit_code != 0
        assert "does not exist" in output or "not a directory" in output

    def test_init_rejects_symlinked_airoom_directory(self):
        """Test init rejects symlinked airoom directory."""
        with (
            tempfile.TemporaryDirectory() as project_tmp,
            tempfile.TemporaryDirectory() as outside_tmp,
        ):
            project = Path(project_tmp)
            (project / "airoom").symlink_to(Path(outside_tmp), target_is_directory=True)

            exit_code, output = self.run_init(project)
            assert exit_code != 0
            assert "symlink" in output.lower()
            assert list(Path(outside_tmp).iterdir()) == []

    def test_init_preserves_malformed_airoom_markers(self):
        """Test init rejects malformed AIroom markers in AGENTS.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            agents = project / "AGENTS.md"
            original = "# instructions\n<!-- AIROOM:START -->\nmissing end marker\n"
            agents.write_text(original, encoding="utf-8")

            exit_code, output = self.run_init(project)
            assert exit_code != 0
            assert "incomplete" in output.lower() or "misordered" in output.lower()
            assert agents.read_text(encoding="utf-8") == original

    def test_init_with_explicit_path(self):
        """Test init with explicit project path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "my-project"
            project_path.mkdir()

            exit_code, output = self.run_init(project_path)
            assert exit_code == 0

            airoom_dir = project_path / "airoom"
            assert airoom_dir.exists()

    def test_dry_run_mode(self):
        """Test dry run mode doesn't create files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            exit_code, output = self.run_init(project_path, args=["--dry-run"])
            assert exit_code == 0
            assert "dry run" in output.lower()

            # Verify nothing was created
            assert not (project_path / "airoom").exists()
            assert not (project_path / "AGENTS.md").exists()

    def test_verbose_flag(self):
        """Test verbose flag increases output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            exit_code, output = self.run_init(project_path, args=["--verbose"])
            assert exit_code == 0
            # Verbose should produce more output
            assert len(output) > 0


class TestTyperInitCliIntegration:
    """Tests for CLI integration."""

    def test_cli_import(self):
        """Test that CLI module can be imported."""
        from airoom.cli import main

        assert callable(main)

    def test_init_command_in_help(self):
        """Test init command appears in help."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "init" in result.output
        assert "Initialize AIroom in a project" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
