---
name: safe-management
description: Shared safety rules for filesystem operations, boundary enforcement, symlink handling, and atomic writes in AIroom.
---

# Safe Management

Apply these safety rules whenever an AIroom agent reads, moves, or changes project files or registry data. Command behaviors are implemented by the AIroom CLI and runtime helpers; this policy defines the boundary agents must strictly follow.

## Safety Invariants

### 1. Project Boundary Confinement & Non-Interference
- All operations must remain strictly inside the resolved project root directory.
- Reject any path that contains `..`, uses absolute filesystem roots, or resolves outside the project boundary.
- Reject backslashes in paths; use forward slashes for cross-platform consistency.
- **Strict Non-Interference**: AIroom strictly manages only the `airoom/` directory and AI-generated tool outputs. It must NEVER create, modify, move, or delete any project files, source trees, or build configurations outside `airoom/` (e.g., Rust `Cargo.toml`, Flutter/Dart `pubspec.yaml`, Go `go.mod`, Python `pyproject.toml`, Node `package.json`, or user application files). The only modification permitted outside `airoom/` is updating the delimited AIroom section in root `AGENTS.md`.

### 2. Symlink Safety
- AIroom does not use symlinks to manage artifacts or bridge relocated files.
- Treat existing symlinks as completely opaque: never follow a symlink to discover files or write data.
- Refuse to create symlinks inside `airoom/artifacts/` or `airoom/skills/`.
- If a symlink exists where an AIroom resource or artifact is expected, treat it as a conflict: report it and do not modify the symlink or its target.

### 3. Data Preservation & Collision Prevention
- **Never Overwrite User or Tool Artifacts**: Before moving or copying files to `airoom/artifacts/`, verify that the target path does not already exist. If it exists, abort and report the collision.
- **Never Delete User Files Automatically**: Routine cleanup must never delete artifacts or directories without explicit, verified operator confirmation.
- **Never Modify Artifact Content During AIroom Tasks**: Organization and registry management move or track files; they never alter the contents of AI-generated artifacts.

### 4. Baseline Integrity for Managed Resources
- Core templates (`AIROOM.md`, packaged skills, root `AGENTS.md` bounded section) are tracked in `.airoom-baseline.json`.
- If installed project resources differ from their recorded baseline hashes, treat them as user modifications. Never overwrite them during updates.
- Missing or malformed baselines are treated as conflicts, not permission to overwrite.

### 5. Atomic File Operations
- All writes to `airoom/registry.yaml`, `.airoom-version`, and `.airoom-baseline.json` must be atomic:
  - Write to a sibling temporary file (`.tmp`).
  - Flush and sync to disk.
  - Verify the target has not been concurrently modified since it was read.
  - Atomically replace the target using `os.replace`.

### 6. Relocation & Tool Compatibility
- Never move an artifact or change its mode to `managed` unless tool compatibility with the canonical path (`airoom/artifacts/...`) has been verified via:
  - Direct testing (e.g. running a dry-run or query at the canonical path).
  - Authoritative tool documentation (e.g. documented output environment variables or CLI flags).
- If compatibility is uncertain, retain the artifact at its current path and register it as `management: external`.

## When to Require User Confirmation

An agent must pause and request user confirmation in the following situations:
1. Ambiguous ownership of a file or directory.
2. Proposed relocation of an artifact whose tool compatibility cannot be verified.
3. Target path collisions in `airoom/artifacts/`.
4. Any operation that requires deleting or replacing existing files.
5. Detected conflicts during `airoom update`.

## Rollback Protocol

If a multi-step operation (such as moving an artifact and updating `registry.yaml`) encounters an error midway:
1. Stop execution immediately.
2. If files were moved, move them back to their original location.
3. If temporary files were created, remove them.
4. If `registry.yaml` was modified, restore it to its state prior to the operation.
5. Report the exact failure reason, what was rolled back, and the remaining state.
