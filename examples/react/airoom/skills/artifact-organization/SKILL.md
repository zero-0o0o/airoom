---
name: artifact-organization
description: Operational guide for routing, relocating, and organizing AI-generated files and folders under airoom/artifacts/ and updating the registry.
---

# Artifact Organization

Use this skill to organize AI-generated files and directories under `airoom/artifacts/`, keeping the project root clean while preserving access for AI tools and agents.

This skill bridges `artifact-discovery` (finding artifacts) and `registry-management` (updating metadata). Read `safe-management/SKILL.md` before performing any filesystem modifications.

## Core Principles

1. **Prefer Direct Output Routing**: Configure tools to generate directly into `airoom/artifacts/` from the start rather than relocating files after generation.
2. **Never Break Running Tools**: If a tool requires its files at the project root or lacks path configuration, do not move them. Track them as `external`.
3. **Zero Data Loss**: Always verify targets before moving, reject symlinks, prevent collisions, and test relocated artifacts with an immediate rollback plan.
4. **Strict Non-Interference with Project Files**: AIroom strictly manages only its own directory (`airoom/`) and AI-generated artifacts. Never move, modify, or interfere with any project source files, build manifests (e.g. Rust `Cargo.toml`, Flutter `pubspec.yaml`, Go `go.mod`, Python `pyproject.toml`, Node `package.json`), assets, or tests across any language or framework.

## Relocation Decision Matrix

Use this matrix to determine whether an artifact should be `managed` under `airoom/artifacts/` or tracked as `external` at its current location:

| Scenario | Management Mode | Action |
|---|---|---|
| Tool supports custom output path (env var, CLI option, or config) | `managed` | Configure tool (e.g. `GRAPHIFY_OUT=airoom/artifacts/...`) and write directly or move existing output. |
| Tool workflow is controlled by project skills or prompt instructions | `managed` | Direct skill/instructions to write under `airoom/artifacts/...` (e.g. Superpowers specs/plans). |
| Static documentation, report, or scratchpad with no fixed code dependency | `managed` | Relocate to `airoom/artifacts/...` with `original_path` recorded. |
| Tool hardcodes project-root paths and cannot be configured | `external` | Keep at project-root path. Record in `airoom/registry.yaml` with `management: external`. |
| Relocating would break compiler, build system, or tests | `external` | Keep at current path. Track metadata only. |
| Tool compatibility or path redirection is unverified | `external` | Keep at current path until verified by tests or authoritative documentation. |

## Well-Known Tool Configurations

- **Graphify**:
  - Default: `graphify-out/` at project root.
  - AIroom canonical: `airoom/artifacts/graphify-out`
  - Adaptation: Set `GRAPHIFY_OUT=airoom/artifacts/graphify-out` before running Graphify commands.
- **Superpowers**:
  - Default: `docs/superpowers/specs/`, `docs/superpowers/plans/`, `.superpowers/brainstorm/`, `.superpowers/sdd/`
  - AIroom canonical: `airoom/artifacts/docs/superpowers/` and `airoom/artifacts/.superpowers/`
  - Adaptation: Configure project-local skill instructions and helper scripts to resolve paths beneath `airoom/artifacts/`.
- **General AI Tools & Agents**:
  - Look for output flags (e.g. `--output-dir`, `-o`), configuration file keys, or environment variables.
  - If configurable, point them to `airoom/artifacts/<tool-name>/`.
  - If unconfigurable, leave them in place and register as `external`.

## Step-by-Step Organization & Relocation Workflow

### Step 1: Pre-flight Safety Checks

Before moving any existing artifact:
1. Verify source path exists and is inside the project root.
2. Confirm neither source nor any parent path is a symlink. Treat symlinks as opaque.
3. Verify target canonical path starts with `airoom/artifacts/` and is strictly project-relative (no `..` or absolute paths).
4. Verify the target path does NOT already exist. Never overwrite existing destination data.
5. Create parent directories under `airoom/artifacts/` safely if they do not exist.

### Step 2: Configure the Tool for Future Runs

Update tool invocation instructions, environment variables, or project skills so future operations target the canonical path automatically:
- Document the environment variable or flag in `airoom/registry.yaml` under `tools.<tool-id>`.
- Update any project-local agent instructions or skill files that invoke the tool.

### Step 3: Execute the Move

Move the artifact using a safe, non-destructive filesystem move:
1. For directories or files on the same filesystem: execute an atomic move/rename.
2. If cross-filesystem or copy-fallback is needed: copy all files, verify file counts and sizes match, and only then remove source files.
3. If an error occurs during the move, abort immediately and restore the source to its original state.

### Step 4: Register in `airoom/registry.yaml`

Follow `airoom/skills/registry-management/SKILL.md`:
1. Add or update the artifact entry:
   ```yaml
   artifacts:
     <artifact-id>:
       owner: <tool-id>
       path: airoom/artifacts/<relative-path>
       original_path: <original-path>
       type: directory # or file
       management: managed
       status: active
   ```
2. Add or update the tool entry under `tools`:
   ```yaml
   tools:
     <tool-id>:
       name: <Tool Name>
       status: active
       output_path: airoom/artifacts/<relative-path>
       output_env: <ENV_VAR>=airoom/artifacts/<relative-path> # if applicable
   ```

### Step 5: Post-Verification & Rollback

1. Run verification: test that the tool can read from or write to the new canonical location.
2. If verification fails:
   - Move the artifact back to its `original_path`.
   - Update `airoom/registry.yaml` to set `path: <original-path>` and `management: external`.
   - Report the issue and explanation clearly.

### Step 6: Git and Ignore Hygiene

- If the tool's root-level output was previously tracked in `.gitignore`, ensure the rule either covers the canonical path or root-level defaults remain ignored to prevent accidental root clutter.
- Do not commit sensitive local scratchpads, session keys, or unmanaged tool caches.

## Completion Report

When an organization or relocation task is complete, summarize:
1. Artifacts organized under `airoom/artifacts/` (`managed`).
2. Artifacts kept in their original locations (`external`) and why.
3. Tool configurations or environment variables applied.
4. Registry updates made in `airoom/registry.yaml`.
5. Verification tests performed and results.
