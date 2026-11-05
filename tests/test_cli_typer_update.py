"""Tests for airoom update command (Typer-based)."""

import hashlib
import json
import platform
import shutil
import tempfile
from pathlib import Path

import pytest
import ruamel.yaml
from typer.testing import CliRunner

from airoom.cli import app
from airoom.commands_typer.init import AIROOM_START, AIROOM_END
from airoom.core.project import Project
from airoom.core.baseline import BaselineManager, compute_file_hash_from_bytes
from airoom.core.version import read_version_file


class TestTyperUpdateCommand:
    """Integration tests for the Typer update command."""

    def run_update(self, project_path: Path, args: list[str] | None = None) -> tuple[int, str]:
        """Run update command in a temporary directory."""
        runner = CliRunner()
        cmd = ["update"]
        if args:
            cmd.extend(args)
        if project_path:
            cmd.extend(["--path", str(project_path)])
        result = runner.invoke(app, cmd)
        return result.exit_code, result.output

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

    def test_successful_update_fresh_project(self):
        """Test updating a freshly initialized project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            exit_code, _ = self.run_init(project_path)
            assert exit_code == 0

            exit_code, output = self.run_update(project_path)
            assert exit_code == 0
            assert "Update Summary" in output

            # Version should be updated to current
            version_file = project_path / "airoom" / ".airoom-version"
            assert version_file.read_text().strip() == "0.1.0"

    def test_update_adds_new_packaged_skill_when_missing(self):
        """Test that update installs newly added packaged skills into an existing project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            # Simulate legacy project that lacked artifact-organization
            new_skill_dir = project_path / "airoom" / "skills" / "artifact-organization"
            shutil.rmtree(new_skill_dir)
            baseline_file = project_path / "airoom" / ".airoom-baseline.json"
            baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
            baseline.pop("skills/artifact-organization/SKILL.md", None)
            baseline_file.write_text(json.dumps(baseline), encoding="utf-8")

            exit_code, output = self.run_update(project_path)
            assert exit_code == 0
            assert (new_skill_dir / "SKILL.md").exists()
            assert "artifact-organization" in output

            updated_baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
            assert "skills/artifact-organization/SKILL.md" in updated_baseline

    def test_update_preserves_user_modified_skill(self):
        """Test that user-modified skills are preserved as conflicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            # Modify a skill
            skill_file = project_path / "airoom" / "skills" / "artifact-discovery" / "SKILL.md"
            original = skill_file.read_text()
            skill_file.write_text(original + "\n\n# User customization")
            version = project_path / "airoom" / ".airoom-version"
            version.write_text("0.0.9\n")

            exit_code, output = self.run_update(project_path)
            assert exit_code == 1  # Conflicts are reported as a non-zero result

            # Skill should be unchanged
            assert skill_file.read_text() == original + "\n\n# User customization"
            assert version.read_text().strip() == "0.0.9"
            assert "Conflicts detected" in output
            assert "artifact-discovery" in output

            baseline = json.loads((project_path / "airoom" / ".airoom-baseline.json").read_text())
            assert (
                baseline["skills/artifact-discovery/SKILL.md"]
                == hashlib.sha256(original.encode("utf-8")).hexdigest()
            )

    def test_update_rejects_symlinked_resource_directory(self):
        """Test that update rejects symlinked resource directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            project_skills = project_path / "airoom" / "skills"
            moved = project_path / "skills-backup"
            project_skills.rename(moved)
            project_skills.symlink_to(moved, target_is_directory=True)

            exit_code, output = self.run_update(project_path)
            assert exit_code == 1
            assert "symlink" in output.lower()

    def test_update_preserves_user_created_files(self):
        """Test that user-created skills are preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            # Create a user skill
            user_skill_dir = project_path / "airoom" / "skills" / "user-skill"
            user_skill_dir.mkdir()
            (user_skill_dir / "SKILL.md").write_text("# User Skill\n\nCustom skill.")

            exit_code, output = self.run_update(project_path)
            assert exit_code == 0

            assert (user_skill_dir / "SKILL.md").exists()
            assert (user_skill_dir / "SKILL.md").read_text() == "# User Skill\n\nCustom skill."
            assert "Preserving user-created skill: user-skill" in output

    def test_update_preserves_registry_entries(self):
        """Test that existing registry entries are preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            # Add custom registry entry
            registry_path = project_path / "airoom" / "registry.yaml"
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

            exit_code, output = self.run_update(project_path)
            assert exit_code == 0

            # Verify custom entry preserved
            data = yaml.load(registry_path.read_text())
            assert "custom" in data["artifacts"]
            assert data["artifacts"]["custom"]["owner"] == "custom"
            assert data["artifacts"]["custom"]["management"] == "external"

    def test_update_does_not_seed_example_registry_entries(self):
        """Updating never invents example registrations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            registry_path = project_path / "airoom" / "registry.yaml"
            yaml = ruamel.yaml.YAML()

            exit_code, output = self.run_update(project_path)
            assert exit_code == 0

            data = yaml.load(registry_path.read_text())
            assert data["artifacts"] == {}

    def test_update_preserves_agents_md_content(self):
        """Test that existing AGENTS.md content is preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            agents_path = project_path / "AGENTS.md"
            original = agents_path.read_text()
            # Add user content
            agents_path.write_text(original + "\n\n# User Section\n\nUser content.")

            exit_code, output = self.run_update(project_path)
            assert exit_code == 0

            content = agents_path.read_text()
            assert "# User Section" in content
            assert "User content" in content
            assert AIROOM_START in content
            assert AIROOM_END in content

    def test_update_preserves_user_modified_agents_md_section(self):
        """Test that user-modified AIroom section in AGENTS.md is preserved as conflict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            agents_path = project_path / "AGENTS.md"
            content = agents_path.read_text()
            # Modify the AIroom section
            start = content.find(AIROOM_START)
            end = content.find(AIROOM_END)
            if start != -1 and end > start:
                modified_content = (
                    content[:start]
                    + content[start:end + len(AIROOM_END)].replace("AIroom", "Modified AIroom")
                    + content[end + len(AIROOM_END):]
                )
                agents_path.write_text(modified_content)

            exit_code, output = self.run_update(project_path)
            assert exit_code == 1  # Conflict
            assert "Conflicts detected" in output
            assert "AGENTS.md AIroom section" in output

            # Verify user modification preserved
            final_content = agents_path.read_text()
            assert "Modified AIroom" in final_content

    def test_update_preserves_user_modified_airoom_md(self):
        """Test that user-modified AIROOM.md is preserved as conflict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            airoom_md = project_path / "airoom" / "AIROOM.md"
            original = airoom_md.read_text()
            # Modify AIROOM.md
            airoom_md.write_text(original + "\n\n# User Addition\n\nCustom content.")

            exit_code, output = self.run_update(project_path)
            assert exit_code == 1  # Conflict
            assert "Conflicts detected" in output
            assert "AIROOM.md" in output

            # Verify user modification preserved
            final_content = airoom_md.read_text()
            assert "User Addition" in final_content
            assert "Custom content" in final_content

    def test_repeated_update_idempotent(self):
        """Test that repeated updates don't make unnecessary changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            exit_code1, _ = self.run_update(project_path)
            assert exit_code1 == 0

            exit_code2, _ = self.run_update(project_path)
            assert exit_code2 == 0

            # Version should remain the same
            version_file = project_path / "airoom" / ".airoom-version"
            assert version_file.read_text().strip() == "0.1.0"

    def test_update_without_initialization_fails(self):
        """Test that update fails when AIroom not initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            exit_code, output = self.run_update(project_path)
            assert exit_code == 1
            assert "not initialized" in output.lower()

    def test_update_with_invalid_path_fails(self):
        """Test that update fails with invalid path."""
        exit_code, output = self.run_update(Path("/nonexistent/path"))
        assert exit_code == 1
        assert "does not exist" in output or "not a directory" in output

    def test_update_version_not_updated_on_error(self):
        """Test that version is not updated when there are errors."""
        if platform.system() == "Darwin":
            pytest.skip("Permission test not reliable on macOS")
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            # Create a scenario that causes an error - make a directory read-only
            skills_dir = project_path / "airoom" / "skills"
            skills_dir.chmod(0o555)

            try:
                exit_code, output = self.run_update(project_path)
                assert exit_code == 1
            finally:
                skills_dir.chmod(0o755)

    def test_update_dry_run_mode(self):
        """Test dry run mode doesn't make changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            # Modify a skill to trigger an update
            skill_file = project_path / "airoom" / "skills" / "artifact-discovery" / "SKILL.md"
            original = skill_file.read_text()
            skill_file.write_text(original + "\n\n# User customization")
            version = project_path / "airoom" / ".airoom-version"
            version.write_text("0.0.9\n")

            exit_code, output = self.run_update(project_path, args=["--dry-run"])
            assert exit_code == 0
            assert "dry run" in output.lower()

            # Version should NOT be updated
            assert version.read_text().strip() == "0.0.9"

    def test_update_json_output(self):
        """Test JSON output format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)

            exit_code, output = self.run_update(project_path, args=["--json"])
            assert exit_code == 0

            # Output should be valid JSON
            result = json.loads(output)
            assert "skills" in result
            assert "registry" in result
            assert "agents_md" in result
            assert "airoom_md" in result
            assert "errors" in result
            assert "conflicts" in result

    def test_update_verbose_flag(self):
        """Test verbose flag increases output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)

            exit_code, output = self.run_update(project_path, args=["--verbose"])
            assert exit_code == 0
            # Verbose should produce more output
            assert len(output) > 0

    def test_update_global_path_option(self):
        """Test that global --path option works for update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)

            runner = CliRunner()
            result = runner.invoke(app, ["--path", str(project_path), "update"])
            assert result.exit_code == 0
            assert "Update Summary" in result.output

    def test_update_global_verbose_option(self):
        """Test that global --verbose option works for update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)

            runner = CliRunner()
            result = runner.invoke(app, ["--verbose", "--path", str(project_path), "update"])
            assert result.exit_code == 0

    def test_update_global_json_option(self):
        """Test that global --json option works for update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)

            runner = CliRunner()
            result = runner.invoke(app, ["--json", "--path", str(project_path), "update"])
            assert result.exit_code == 0
            parsed = json.loads(result.output)
            assert "skills" in parsed

    def test_update_global_dry_run_option(self):
        """Test that global --dry-run option works for update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)

            runner = CliRunner()
            result = runner.invoke(app, ["--dry-run", "--path", str(project_path), "update"])
            assert result.exit_code == 0
            assert "dry run" in result.output.lower()

    def test_baseline_updates_for_successful_writes(self):
        """Test that baseline is updated for successfully written resources."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            # Remove a skill to simulate it being newly added
            skill_dir = project_path / "airoom" / "skills" / "artifact-discovery"
            shutil.rmtree(skill_dir)

            exit_code, _ = self.run_update(project_path)
            assert exit_code == 0

            # Baseline should have the new skill hash
            baseline_path = project_path / "airoom" / ".airoom-baseline.json"
            baseline = json.loads(baseline_path.read_text())
            assert "skills/artifact-discovery/SKILL.md" in baseline
            # Hash should match the installed skill
            installed_content = (project_path / "airoom" / "skills" / "artifact-discovery" / "SKILL.md").read_bytes()
            expected_hash = compute_file_hash_from_bytes(installed_content)
            assert baseline["skills/artifact-discovery/SKILL.md"] == expected_hash

    def test_baseline_retains_old_hash_for_conflicts(self):
        """Test that baseline retains old hash for conflicted resources."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)
            # Modify a skill
            skill_file = project_path / "airoom" / "skills" / "artifact-discovery" / "SKILL.md"
            original = skill_file.read_text()
            skill_file.write_text(original + "\n\n# User customization")

            exit_code, _ = self.run_update(project_path)
            assert exit_code == 1  # Conflict

            # Baseline should still have the old hash (matching original)
            baseline_path = project_path / "airoom" / ".airoom-baseline.json"
            baseline = json.loads(baseline_path.read_text())
            assert "skills/artifact-discovery/SKILL.md" in baseline
            expected_hash = hashlib.sha256(original.encode("utf-8")).hexdigest()
            assert baseline["skills/artifact-discovery/SKILL.md"] == expected_hash

    def test_update_summary_counts(self):
        """Test that update summary shows correct counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            self.run_init(project_path)

            exit_code, output = self.run_update(project_path)
            assert exit_code == 0

            # All skills should be "skipped" (already current)
            assert "Skipped:" in output
            # Should show counts
            assert "Updated:" in output
            assert "Added:" in output
            assert "Conflicts:" in output
            assert "Errors:" in output


class TestTyperUpdateCliIntegration:
    """Tests for CLI integration."""

    def test_cli_import(self):
        """Test that CLI module can be imported."""
        from airoom.cli import main

        assert callable(main)

    def test_update_command_in_help(self):
        """Test update command appears in help."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "update" in result.output
        assert "Update project resources" in result.output

    def test_update_help(self):
        """Test update command shows help."""
        runner = CliRunner()
        result = runner.invoke(app, ["update", "--help"])
        assert result.exit_code == 0
        assert "Update project resources" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])