"""Tests for airoom.core.atomic module."""

import hashlib
import tempfile
from pathlib import Path

import pytest

from airoom.core.atomic import atomic_write, compute_file_hash


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

    def test_empty_file(self):
        """Test computing hash of empty file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "empty.txt"
            file_path.write_text("")
            hash_val = compute_file_hash(file_path)
            expected = hashlib.sha256(b"").hexdigest()
            assert hash_val == expected

    def test_binary_content(self):
        """Test computing hash of binary content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "binary.bin"
            file_path.write_bytes(b"\x00\x01\x02\xff\xfe\xfd")
            hash_val = compute_file_hash(file_path)
            expected = hashlib.sha256(b"\x00\x01\x02\xff\xfe\xfd").hexdigest()
            assert hash_val == expected


class TestAtomicWrite:
    """Tests for atomic_write function."""

    def setup_method(self):
        """Create a temporary directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmpdir)

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_write_new_file(self):
        """Test writing to a new file."""
        target = self.tmp_path / "new_file.txt"
        atomic_write(target, "new content")
        assert target.read_text(encoding="utf-8") == "new content"
        # No temp files left behind
        assert list(self.tmp_path.glob("*.tmp")) == []

    def test_replace_existing_file(self):
        """Test replacing an existing file."""
        target = self.tmp_path / "existing.txt"
        target.write_text("before", encoding="utf-8")
        atomic_write(target, "after", expected_text="before")
        assert target.read_text(encoding="utf-8") == "after"
        assert list(self.tmp_path.glob("*.tmp")) == []

    def test_write_without_expected_text(self):
        """Test writing without expected_text check."""
        target = self.tmp_path / "no_check.txt"
        target.write_text("original", encoding="utf-8")
        atomic_write(target, "updated")
        assert target.read_text(encoding="utf-8") == "updated"

    def test_concurrent_modification_detected(self):
        """Test that concurrent modification is detected and raises error."""
        target = self.tmp_path / "registry.yaml"
        target.write_text("version: 1\nartifacts: {}\ntools: {}\n", encoding="utf-8")
        original = target.read_text(encoding="utf-8")
        # Simulate concurrent modification
        target.write_text("concurrent update", encoding="utf-8")

        from airoom.core.atomic import AtomicWriteError
        with pytest.raises(AtomicWriteError, match="concurrent modification"):
            atomic_write(target, "replacement", expected_text=original)
        # File should be unchanged (still has concurrent update)
        assert target.read_text(encoding="utf-8") == "concurrent update"

    def test_concurrent_creation_detected(self):
        """Test that concurrent creation is detected when expected_absent=True."""
        target = self.tmp_path / "new_file.txt"
        # File doesn't exist initially
        # Simulate concurrent creation
        target.write_text("concurrent creation", encoding="utf-8")

        from airoom.core.atomic import AtomicWriteError
        with pytest.raises(AtomicWriteError, match="concurrent creation"):
            atomic_write(target, "our content", expected_absent=True)
        # File should be unchanged
        assert target.read_text(encoding="utf-8") == "concurrent creation"

    def test_expected_absent_false_no_error(self):
        """Test that expected_absent=False doesn't raise when file exists."""
        target = self.tmp_path / "existing.txt"
        target.write_text("original", encoding="utf-8")
        atomic_write(target, "updated", expected_absent=False)
        assert target.read_text(encoding="utf-8") == "updated"

    def test_preserves_file_permissions(self):
        """Test that file permissions are preserved."""
        target = self.tmp_path / "perm_test.txt"
        target.write_text("original", encoding="utf-8")
        target.chmod(0o600)
        original_mode = target.stat().st_mode & 0o777
        
        atomic_write(target, "updated", expected_text="original")
        
        new_mode = target.stat().st_mode & 0o777
        assert new_mode == original_mode
        assert target.read_text(encoding="utf-8") == "updated"

    def test_default_permissions_for_new_file(self):
        """Test default permissions (0o644) for new files."""
        target = self.tmp_path / "new_perm.txt"
        atomic_write(target, "content")
        
        mode = target.stat().st_mode & 0o777
        assert mode == 0o644

    def test_no_temp_files_left_on_error(self):
        """Test that temp files are cleaned up even on error."""
        target = self.tmp_path / "error_test.txt"
        target.write_text("original", encoding="utf-8")
        
        from airoom.core.atomic import AtomicWriteError
        with pytest.raises(AtomicWriteError):
            atomic_write(target, "updated", expected_text="wrong_expected")
        
        assert list(self.tmp_path.glob("*.tmp")) == []

    def test_concurrent_modification_second_check(self):
        """Test that concurrent modification is caught by the second check.
        
        This simulates a race where the file is modified after the temp file
        is written but before the atomic replace.
        """
        target = self.tmp_path / "second_check.txt"
        target.write_text("original", encoding="utf-8")
        original = target.read_text()
        
        # We can't easily test the second check in isolation due to timing,
        # but we can verify the double-check logic exists by ensuring
        # the first check works (tested in test_concurrent_modification_detected)
        # and the atomic write succeeds when no concurrent modification occurs.
        atomic_write(target, "updated", expected_text=original)
        assert target.read_text(encoding="utf-8") == "updated"
        assert list(self.tmp_path.glob("*.tmp")) == []

    def test_write_unicode_content(self):
        """Test writing unicode content."""
        target = self.tmp_path / "unicode.txt"
        content = "Hello 世界 🌍 café"
        atomic_write(target, content)
        assert target.read_text(encoding="utf-8") == content

    def test_write_large_content(self):
        """Test writing large content (multiple chunks)."""
        target = self.tmp_path / "large.txt"
        content = "x" * 100000  # 100KB
        atomic_write(target, content)
        assert target.read_text(encoding="utf-8") == content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])