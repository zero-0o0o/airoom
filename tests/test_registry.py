"""Validation, duplicate-key, and atomic-write tests for registries."""

from pathlib import Path

import pytest

from airoom.core.registry import RegistryError, parse_registry
from airoom.core.atomic import atomic_write, AtomicWriteError


VALID = """version: 1
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


def test_valid_registry_allows_unknown_fields_and_empty_sections():
    registry = parse_registry(VALID)
    assert registry["artifacts"]["custom"]["future_field"] == "preserved"
    assert parse_registry("version: 1\nartifacts: {}\ntools: {}\n")["artifacts"] == {}


def test_duplicate_yaml_keys_are_rejected():
    with pytest.raises(RegistryError, match="duplicate key"):
        parse_registry("version: 1\nversion: 1\nartifacts: {}\ntools: {}\n")


@pytest.mark.parametrize(
    "path", ["../outside", "/tmp/outside", "airoom/artifacts/../../outside", "C:\\\\outside"]
)
def test_path_traversal_is_rejected(path):
    text = VALID.replace("airoom/artifacts/custom", path)
    with pytest.raises(RegistryError, match="project-relative|contain"):
        parse_registry(text)


def test_managed_artifact_must_live_in_artifacts():
    text = VALID.replace("airoom/artifacts/custom", "generated/custom")
    with pytest.raises(RegistryError, match="must be under airoom/artifacts"):
        parse_registry(text)


def test_duplicate_canonical_paths_are_rejected():
    text = """version: 1
artifacts:
  custom:
    owner: custom-tool
    path: airoom/artifacts/custom
    type: directory
    management: managed
    status: active
  other:
    owner: other
    path: airoom/artifacts/custom
    type: directory
    management: managed
    status: active
tools: {}
"""
    with pytest.raises(RegistryError, match="duplicate artifact path"):
        parse_registry(text)


def test_atomic_write_aborts_if_file_changed(tmp_path: Path):
    target = tmp_path / "registry.yaml"
    target.write_text("version: 1\nartifacts: {}\ntools: {}\n", encoding="utf-8")
    original = target.read_text(encoding="utf-8")
    target.write_text("concurrent update", encoding="utf-8")

    with pytest.raises(AtomicWriteError, match="concurrent modification"):
        atomic_write(target, "replacement", expected_text=original)
    assert target.read_text(encoding="utf-8") == "concurrent update"


def test_atomic_write_replaces_file_and_cleans_temp(tmp_path: Path):
    target = tmp_path / "registry.yaml"
    target.write_text("before", encoding="utf-8")
    atomic_write(target, "after", expected_text="before")
    assert target.read_text(encoding="utf-8") == "after"
    assert list(tmp_path.glob("*.tmp")) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])