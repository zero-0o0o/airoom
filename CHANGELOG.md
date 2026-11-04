# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Added SHA-256 baselines for packaged project text so updates distinguish upstream changes from local edits.
- Make update conflicts and failures return non-zero and prevent version/baseline advancement.
- Validate registry structure, paths, duplicate keys, and canonical-path uniqueness before writes; use round-trip serialization and atomic compare-before-replace.
- Reject symlinked AIroom resource paths and invalid project roots before writing.
- Verify pipx ownership from structured `pipx list --json` output and verify the requested version after CLI upgrades.
- Pin installer installs to a release tag instead of installing from the moving default branch.

### Changed
- Start new registries with empty artifact and tool maps instead of speculative Graphify/MemPalace records.
- Align packaged agent skills and AIROOM.md with the no-symlink, no-assumed-compatibility architecture.
- Replace the placeholder registry test with schema, duplicate-key, path-safety, and concurrent-write tests.
- Rewrite architecture and README guidance to describe implemented behavior and distribution limits.

### Changed
- **Removed symlink management**: AIroom no longer uses symbolic links for artifact management
- **Registry schema updated**: Replaced `symlink-compatible` management mode with `managed` and `external`
- **Registry field renamed**: `compatibility.original_path` → `original_path` (top-level field)
- **Skills removed**: `symlink-management` skill removed
- **Artifact discovery**: Updated to use `original_path` for provenance instead of symlink tracking
- **Registry management**: Updated to only support `managed` and `external` management modes
- **Safe management**: Updated to reflect removal of symlink operations

### Added
- `original_path` field in registry for artifact provenance tracking
- `external` management mode for artifacts that must remain at original location
- `managed` management mode as the standard for relocatable artifacts
- Relocation safety rules in safe-management skill
- Provenance tracking in artifact-discovery skill

### Updated
- Registry template: `management: managed`, `original_path` at top level
- Artifact discovery: Uses `original_path` for provenance, no symlink validation
- Registry management: Only `managed` and `external` modes, `original_path` at top level
- Safe management: Removed symlink operations, added relocation safety
- CLI init: Removed symlink-management skill from installation

## [0.1.0] - TBD

### Added
- Initial repository structure
- CLI foundation with init, update, upgrade commands
- Three AIroom skills: artifact-discovery, registry-management, safe-management
- Project templates: AGENTS.md, registry.yaml
- Installation script
- Test structure

### Changed
- Repository scaffolding
- Python package structure
- Resource distribution via setuptools
