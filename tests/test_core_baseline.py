"""Tests for airoom.core.baseline module."""

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from airoom.core.atomic import compute_file_hash
from airoom.core.baseline import BaselineManager
from airoom.core.project import Project


class TestBaselineManager:
    """Tests for BaselineManager class."""

    def setup_method(self):
        """Create a temporary directory and project."""
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir)
        self.project = Project(self.project_root)
        self.baseline_manager = BaselineManager(self.project)
        # Create airoom directory structure
        self.project.airoom_dir.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_read_empty_baseline(self):
        """Test reading baseline when file doesn't exist returns empty dict."""
        baseline = self.baseline_manager.read()
        assert baseline == {}

    def test_read_existing_baseline(self):
        """Test reading baseline from existing file."""
        baseline_data = {"skills/test/SKILL.md": "abc123", "AIROOM.md": "def456"}
        self.project.baseline_path.write_text(
            json.dumps(baseline_data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        baseline = self.baseline_manager.read()
        assert baseline == baseline_data

    def test_read_invalid_json(self):
        """Test reading baseline with invalid JSON raises error."""
        self.project.baseline_path.write_text("not valid json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            self.baseline_manager.read()

    def test_read_non_dict_json(self):
        """Test reading baseline with non-dict JSON raises error."""
        self.project.baseline_path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
        with pytest.raises(ValueError, match="baseline must be a dictionary"):
            self.baseline_manager.read()

    def test_read_invalid_key_value_types(self):
        """Test reading baseline with non-string keys/values raises error."""
        # JSON parser converts int keys to strings, so test with non-string value
        self.project.baseline_path.write_text(json.dumps({"key": 123}), encoding="utf-8")
        with pytest.raises(ValueError, match="baseline must map resource paths to SHA-256 hashes"):
            self.baseline_manager.read()

    def test_write_baseline(self):
        """Test writing baseline atomically."""
        baseline_data = {"skills/test/SKILL.md": "abc123", "AIROOM.md": "def456"}
        self.baseline_manager.write(baseline_data)
        assert self.project.baseline_path.exists()
        content = self.project.baseline_path.read_text(encoding="utf-8")
        expected = json.dumps(baseline_data, indent=2, sort_keys=True) + "\n"
        assert content == expected

    def test_write_empty_baseline(self):
        """Test writing empty baseline."""
        self.baseline_manager.write({})
        assert self.project.baseline_path.exists()
        content = self.project.baseline_path.read_text(encoding="utf-8")
        assert content == "{}\n"

    def test_write_atomic_behavior(self):
        """Test that write uses atomic_write (creates temp file, fsyncs, replaces atomically)."""
        from airoom.core.atomic import AtomicWriteError

        baseline_data = {"test": "hash"}
        self.baseline_manager.write(baseline_data)
        
        # Verify file exists and has correct content
        assert self.project.baseline_path.exists()
        content = self.project.baseline_path.read_text(encoding="utf-8")
        expected = json.dumps(baseline_data, indent=2, sort_keys=True) + "\n"
        assert content == expected
        
        # No temp files left behind
        assert list(self.project.airoom_dir.glob("*.tmp")) == []

    def test_write_atomic_with_expected_text(self):
        """Test that atomic write detects concurrent modification when expected_text provided."""
        from airoom.core.atomic import AtomicWriteError, atomic_write

        baseline_data = {"test": "hash"}
        self.baseline_manager.write(baseline_data)
        original = self.project.baseline_path.read_text(encoding="utf-8")

        # Simulate concurrent modification
        self.project.baseline_path.write_text("concurrent", encoding="utf-8")

        # Use atomic_write directly with expected_text (as update.py does)
        with pytest.raises(AtomicWriteError):
            atomic_write(self.project.baseline_path, json.dumps({"other": "hash"}) + "\n", expected_text=original)

    def test_update_hash(self):
        """Test updating hash for a resource."""
        content = b"test content"
        relpath = "skills/test/SKILL.md"
        expected_hash = hashlib.sha256(content).hexdigest()

        self.baseline_manager.update_hash(relpath, content)

        baseline = self.baseline_manager.read()
        assert baseline[relpath] == expected_hash

    def test_update_hash_overwrites_existing(self):
        """Test updating hash overwrites existing entry."""
        content1 = b"content 1"
        content2 = b"content 2"
        relpath = "skills/test/SKILL.md"

        self.baseline_manager.update_hash(relpath, content1)
        self.baseline_manager.update_hash(relpath, content2)

        baseline = self.baseline_manager.read()
        assert baseline[relpath] == hashlib.sha256(content2).hexdigest()

    def test_update_hash_preserves_other_entries(self):
        """Test updating one hash preserves other entries."""
        content1 = b"content 1"
        content2 = b"content 2"
        relpath1 = "skills/test1/SKILL.md"
        relpath2 = "skills/test2/SKILL.md"

        self.baseline_manager.update_hash(relpath1, content1)
        self.baseline_manager.update_hash(relpath2, content2)

        baseline = self.baseline_manager.read()
        assert baseline[relpath1] == hashlib.sha256(content1).hexdigest()
        assert baseline[relpath2] == hashlib.sha256(content2).hexdigest()

    def test_remove_hash(self):
        """Test removing a hash from baseline."""
        content = b"test content"
        relpath = "skills/test/SKILL.md"

        self.baseline_manager.update_hash(relpath, content)
        assert relpath in self.baseline_manager.read()

        self.baseline_manager.remove_hash(relpath)
        assert relpath not in self.baseline_manager.read()

    def test_remove_nonexistent_hash(self):
        """Test removing non-existent hash doesn't raise."""
        self.baseline_manager.remove_hash("nonexistent/path")
        # Should not raise
        baseline = self.baseline_manager.read()
        assert baseline == {}

    def test_verify_matching_hash(self):
        """Test verify returns True when content matches baseline."""
        content = b"test content"
        relpath = "skills/test/SKILL.md"

        self.baseline_manager.update_hash(relpath, content)
        result = self.baseline_manager.verify(relpath, content)

        assert result is True

    def test_verify_mismatched_hash(self):
        """Test verify returns False when content doesn't match baseline."""
        content1 = b"content 1"
        content2 = b"content 2"
        relpath = "skills/test/SKILL.md"

        self.baseline_manager.update_hash(relpath, content1)
        result = self.baseline_manager.verify(relpath, content2)

        assert result is False

    def test_verify_nonexistent_resource(self):
        """Test verify returns False when resource not in baseline."""
        content = b"test content"
        relpath = "skills/test/SKILL.md"

        result = self.baseline_manager.verify(relpath, content)

        assert result is False

    def test_verify_empty_content(self):
        """Test verify with empty content."""
        content = b""
        relpath = "skills/test/SKILL.md"

        self.baseline_manager.update_hash(relpath, content)
        result = self.baseline_manager.verify(relpath, content)

        assert result is True

    def test_baseline_json_format(self):
        """Test baseline is written with indent=2 and sort_keys=True."""
        # Write in reverse alphabetical order
        self.baseline_manager.update_hash("z_last", b"content")
        self.baseline_manager.update_hash("a_first", b"content")

        content = self.project.baseline_path.read_text(encoding="utf-8")
        # Should be sorted alphabetically
        assert content.index("a_first") < content.index("z_last")
        # Should have indent=2 (check for spaces)
        assert "  \"a_first\"" in content

    def test_baseline_integration_with_project_paths(self):
        """Test baseline works with actual project resource paths."""
        # Create some test resource files
        skill_path = self.project.skills_dir / "test_skill" / "SKILL.md"
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_content = b"# Test Skill\n\nContent here"
        skill_path.write_bytes(skill_content)

        # Update baseline with the skill
        relpath = "skills/test_skill/SKILL.md"
        self.baseline_manager.update_hash(relpath, skill_content)

        # Verify the baseline
        assert self.baseline_manager.verify(relpath, skill_content)

        # Read the file and verify
        file_content = skill_path.read_bytes()
        assert self.baseline_manager.verify(relpath, file_content)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])