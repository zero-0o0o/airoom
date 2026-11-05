# AIROOM.md

AIroom is the shared infrastructure and coordination layer for AI agents and tools. This file is the primary navigation entry point for AIroom resources in this project. AI-generated files and folders are organized and managed inside a separate `airoom/` directory to keep the project clean, well-structured, and easy for both developers and AI agents to understand and maintain.

## Project Structure

```text
project/
├── airoom/
│   ├── artifacts/           # Canonical location for managed AI tool outputs
│   │   ├── graphify-out/    # Example: Graphify knowledge graphs
│   │   ├── docs/superpowers/# Example: Superpowers specs and plans
│   │   └── .superpowers/    # Example: Superpowers brainstorm and SDD state
│   ├── skills/              # Installed agent skills for discovery and management
│   ├── .airoom-version      # Last project-resource version applied without conflicts
│   ├── .airoom-baseline.json# Integrity hashes for safe resource updates
│   ├── AIROOM.md            # Navigation and operational guidelines (this file)
│   └── registry.yaml        # Single registry of tracked artifacts and tools
└── ...                      # Project files (Rust, Flutter, Go, Python, Node, etc.)
```

> **Boundary Invariant**: AIroom strictly manages only its own directory (`airoom/`) and AI-generated tool artifacts. It must not create, modify, move, or interfere with any project files, build configurations, or source directories outside `airoom/` (except maintaining the delimited section in root `AGENTS.md`). Different projects use different stacks (e.g. Cargo, Flutter, Gradle, npm, pip) — user project files are entirely untouched by AIroom.

## Keep AI-Generated Artifacts Inside `airoom/artifacts/`

AI tools, plugins, and workflows often default to generating files directly in the project root. AIroom provides `airoom/artifacts/` as the canonical home for these outputs to keep the project root clean:

- **Graphify**: Set `GRAPHIFY_OUT=airoom/artifacts/graphify-out` before running Graphify commands.
- **Superpowers**: Direct design specs and plans to `airoom/artifacts/docs/superpowers/specs/` and `airoom/artifacts/docs/superpowers/plans/`; route brainstorm and SDD workspaces to `airoom/artifacts/.superpowers/`.
- **Other AI Tools**: Use tool configuration options, CLI output flags, or environment variables to target `airoom/artifacts/<tool-name>/`.
- **External Artifacts**: If a tool cannot be configured to use `airoom/artifacts/` or requires a hardcoded root path, track it as `management: external` at its existing path. Never move files if doing so would break the tool.

## Choose a skill

| Task | Read |
|---|---|
| Find candidate artifacts or registry discrepancies | `airoom/skills/artifact-discovery/SKILL.md` |
| Relocate, organize, or configure tool output paths | `airoom/skills/artifact-organization/SKILL.md` |
| Register or modify registry metadata | `airoom/skills/registry-management/SKILL.md` |
| Follow safety rules, boundary checks, and atomic writes | `airoom/skills/safe-management/SKILL.md` |

Read `safe-management` before any operation that alters project files or registry data. Discovery is strictly read-only.

## Safety and Compatibility

- Never delete user or tool artifacts automatically or silently overwrite existing files.
- Reject paths that escape the project root (`..` or absolute paths). AIroom does not use symlinks; treat existing symlinks as opaque.
- Do not relocate an artifact or label it `managed` until its owning tool is verified to support the canonical path.
- Project code, dependencies (`node_modules/`, `.venv/`), build outputs (`dist/`, `build/`), and version control (`.git/`) are never AIroom artifacts.
- `airoom init` and `airoom update` manage project resources. `airoom upgrade` and `airoom uninstall` manage only the global CLI.
- When an operation finishes, report what changed, what was preserved, checks performed, and any remaining unverified assumptions.
