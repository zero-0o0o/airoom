---
name: registry-management
description: Read, validate, register, or update entries in airoom/registry.yaml with round-trip schema safety.
---

# Registry Management

Use this skill to read, validate, register, or update entries in `airoom/registry.yaml`. This file is the single source of truth for AI-generated artifacts and tool integrations in the project.

Before any write operation, read `airoom/skills/safe-management/SKILL.md`.

## Registry Schema Reference

```yaml
version: 1

artifacts:
  # Example managed artifact (under airoom/artifacts/)
  graphify-output:
    owner: graphify
    path: airoom/artifacts/graphify-out
    type: directory                  # 'directory' or 'file'
    management: managed             # 'managed' or 'external'
    status: active                  # 'active' or 'inactive'
    original_path: graphify-out      # Optional: provenance location before relocation
    version: 0.9.101                 # Optional: tool or artifact version
    output_setting: GRAPHIFY_OUT=airoom/artifacts/graphify-out  # Optional: metadata

  # Example external artifact (remains in project root or subfolder)
  external-tool-cache:
    owner: unconfigurable-tool
    path: .unconfigurable-cache
    type: directory
    management: external
    status: active

tools:
  graphify:
    name: Graphify
    status: active                  # 'active' or 'inactive'
    version: 0.9.101                 # Optional
    output_path: airoom/artifacts/graphify-out  # Optional
    output_env: GRAPHIFY_OUT=airoom/artifacts/graphify-out  # Optional
    verification: Verified with graphify CLI output override  # Optional
```

## Schema Validation Invariants

Every entry must strictly satisfy these rules, which are validated by `src/airoom/registry.py`:

1. **Top-level Containers**:
   - `version`: must be integer `1`.
   - `artifacts`: mapping of unique artifact IDs to artifact dictionaries.
   - `tools`: mapping of unique tool IDs to tool dictionaries.
2. **Artifact IDs and Tool IDs**:
   - Must be non-empty strings without slashes (`/`).
3. **Artifact Required Fields**:
   - `owner`: non-empty string identifying the producing tool or component.
   - `path`: non-empty, project-relative path. Must NOT be absolute, must NOT contain `..`, and must NOT contain backslashes.
   - `type`: must be exactly `file` or `directory`.
   - `management`: must be exactly `managed` or `external`.
     - When `managed`, `path` **must** start with `airoom/artifacts/`.
   - `status`: must be exactly `active` or `inactive`.
4. **Artifact Optional Fields**:
   - `original_path`: project-relative path recording provenance prior to relocation. Must not contain `..` or leading slashes.
   - Arbitrary additional metadata fields are preserved during round-trip parsing.
5. **Uniqueness**:
   - Each `path` must be unique across all artifact entries.
   - Each `original_path` (when provided) must be unique.
6. **Tool Invariants**:
   - `name`: non-empty string.
   - `status`: `active` or `inactive`.
   - `config_path` and `runtime_path` (if present) must be valid project-relative paths.

## Safe Registry Update Procedure

When modifying `airoom/registry.yaml`:

1. **Read and Validate**:
   - Read the existing file content.
   - Validate that it is valid YAML without duplicate keys.
2. **Prepare Changes**:
   - If registering a newly relocated artifact, ensure `artifact-organization` steps were completed and files exist at `path`.
   - Set `status: active` for active artifacts; use `status: inactive` for deprecated or archived entries. Never delete entries as routine cleanup.
   - Ensure `owner` references a declared or identifiable tool.
3. **Preserve Content & Structure**:
   - Use round-trip parsing (`ruamel.yaml` in Python or equivalent structure-preserving parser) to preserve comments, formatting, and unknown fields.
   - Never reset `registry.yaml` from an empty template.
4. **Concurrency Check**:
   - Re-read the file immediately before writing. If the file changed on disk since it was first read, abort and report the concurrent modification conflict.
5. **Atomic Write**:
   - Write to a temporary file in the same directory (`airoom/`) with matching permissions, flush and sync to disk, then atomically replace `registry.yaml`.
6. **Post-Write Validation**:
   - Re-read and parse `registry.yaml` to confirm the file is valid and meets all schema invariants.

## Reporting

Summarize the operation:
- Modified entry IDs.
- Field changes (`path`, `management`, `status`, etc.).
- Verification confirmation.
