"""Tests for airoom.core.version module."""

import tempfile
from pathlib import Path

import pytest

from airoom.core.version import read_version_file, write_version_file


class TestReadVersionFile:
    """Tests for read_version_file function."""

    def setup_method(self):
        """Create a temporary directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmpdir)

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_read_existing_version_file(self):
        """Test reading version from existing file."""
        version_path = self.tmp_path / ".airoom-version"
        version_path.write_text("1.2.3\n", encoding="utf-8")
        
        result = read_version_file(version_path)
        assert result == "1.2.3"

    def test_read_version_file_strips_whitespace(self):
        """Test that read_version_file strips whitespace."""
        version_path = self.tmp_path / ".airoom-version"
        version_path.write_text("  0.5.0-alpha  \n", encoding="utf-8")
        
        result = read_version_file(version_path)
        assert result == "0.5.0-alpha"

    def test_read_nonexistent_version_file(self):
        """Test reading version from nonexistent file returns empty string."""
        version_path = self.tmp_path / ".airoom-version"
        
        result = read_version_file(version_path)
        assert result == ""

    def test_read_empty_version_file(self):
        """Test reading version from empty file returns empty string."""
        version_path = self.tmp_path / ".airoom-version"
        version_path.write_text("", encoding="utf-8")
        
        result = read_version_file(version_path)
        assert result == ""

    def test_read_version_file_newlines_only(self):
        """Test reading version file with only newlines returns empty string."""
        version_path = self.tmp_path / ".airoom-version"
        version_path.write_text("\n\n", encoding="utf-8")
        
        result = read_version_file(version_path)
        assert result == ""


class TestWriteVersionFile:
    """Tests for write_version_file function."""

    def setup_method(self):
        """Create a temporary directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmpdir)

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_write_new_version_file(self):
        """Test writing version to new file."""
        version_path = self.tmp_path / ".airoom-version"
        
        write_version_file(version_path, "1.0.0")
        
        assert version_path.exists()
        assert version_path.read_text(encoding="utf-8") == "1.0.0\n"

    def test_write_version_file_replaces_existing(self):
        """Test writing version replaces existing file."""
        version_path = self.tmp_path / ".airoom-version"
        version_path.write_text("0.1.0\n", encoding="utf-8")
        
        write_version_file(version_path, "2.0.0")
        
        assert version_path.read_text(encoding="utf-8") == "2.0.0\n"

    def test_write_version_file_no_change_when_same(self):
        """Test writing same version doesn't rewrite file."""
        version_path = self.tmp_path / ".airoom-version"
        version_path.write_text("1.0.0\n", encoding="utf-8")
        original_mtime = version_path.stat().st_mtime
        
        write_version_file(version_path, "1.0.0")
        
        # mtime should not change (no write occurred)
        assert version_path.stat().st_mtime == original_mtime
        assert version_path.read_text(encoding="utf-8") == "1.0.0\n"

    def test_write_version_file_uses_atomic_write(self):
        """Test that write_version_file uses atomic_write (no temp files left)."""
        version_path = self.tmp_path / ".airoom-version"
        
        write_version_file(version_path, "1.0.0")
        
        # No temp files left behind
        assert list(self.tmp_path.glob("*.tmp")) == []

    def test_write_version_file_with_special_chars(self):
        """Test writing version with prerelease/build metadata."""
        version_path = self.tmp_path / ".airoom-version"
        
        write_version_file(version_path, "1.0.0-alpha.1+build.123")
        
        assert version_path.read_text(encoding="utf-8") == "1.0.0-alpha.1+build.123\n"

    def test_write_version_file_empty_string(self):
        """Test writing empty version string."""
        version_path = self.tmp_path / ".airoom-version"
        
        write_version_file(version_path, "")
        
        assert version_path.read_text(encoding="utf-8") == "\n"

    


class TestVersionFileIntegration:
    """Integration tests for read/write version file."""

    def setup_method(self):
        """Create a temporary directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmpdir)

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_read_write_roundtrip(self):
        """Test that write then read returns the same version."""
        version_path = self.tmp_path / ".airoom-version"
        
        write_version_file(version_path, "2.5.0-rc.1")
        result = read_version_file(version_path)
        
        assert result == "2.5.0-rc.1"

    def test_write_read_write_sequence(self):
        """Test multiple write/read cycles."""
        version_path = self.tmp_path / ".airoom-version"
        
        write_version_file(version_path, "1.0.0")
        assert read_version_file(version_path) == "1.0.0"
        
        write_version_file(version_path, "1.1.0")
        assert read_version_file(version_path) == "1.1.0"
        
        write_version_file(version_path, "2.0.0")
        assert read_version_file(version_path) == "2.0.0"

    def test_version_file_preserves_newline_format(self):
        """Test that version file always ends with exactly one newline."""
        version_path = self.tmp_path / ".airoom-version"
        
        write_version_file(version_path, "1.0.0")
        content = version_path.read_text(encoding="utf-8")
        assert content == "1.0.0\n"
        assert content.count("\n") == 1
        assert content.endswith("\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])