# AIroom

**Shared infrastructure and coordination layer for AI agents and tools.**

AIroom gives agents a project-level instruction entry point, focused skills, and one registry for resources. The Python CLI installs and updates those project resources. It does not discover, move, or delete tool artifacts on its own.

See [`examples/rust/`](examples/rust/) and [`examples/react/`](examples/react/) for realistic applications where Graphify and Superpowers outputs are routed into `airoom/artifacts/` and registered as managed resources, keeping tool-generated folders out of the project root.

## Install

AIroom requires Python 3.10+ and pipx. The installer is intended to install a tagged release:

```bash
curl -fsSL https://raw.githubusercontent.com/zero-0o0o/airoom/main/scripts/install.sh | sh
```

## Use

```bash
cd your-project
airoom init
airoom update
airoom upgrade
airoom uninstall
```

- `init` installs missing project resources and a marked section in root `AGENTS.md`.
- `update` updates unchanged packaged resources using their recorded SHA-256 baseline. It preserves edits and exits non-zero on conflicts.
- `upgrade` changes only the globally installed CLI.
- `uninstall` removes only the verified pipx CLI; it requires confirmation or `--yes`.

## Project layout

```text
project/
├── AGENTS.md
└── airoom/
    ├── AIROOM.md
    ├── .airoom-version
    ├── .airoom-baseline.json
    ├── registry.yaml
    ├── artifacts/
    └── skills/
        ├── artifact-discovery/SKILL.md
        ├── artifact-organization/SKILL.md
        ├── registry-management/SKILL.md
        └── safe-management/SKILL.md
```

The registry starts empty; add only verified resources. `managed` artifacts live under `airoom/artifacts/` only when the owning tool supports that path. `external` resources remain at their current project-relative location. `original_path` is provenance metadata, not a symlink instruction. AIroom does not manage symlinks.

## Skills

- **artifact-discovery** — Read-only discovery and discrepancy reporting.
- **artifact-organization** — Routing, safe relocation, and organization of tool artifacts under `airoom/artifacts/`.
- **registry-management** — Safe registry validation and metadata changes.
- **safe-management** — Shared safety rules for project operations.

Start with `airoom/AIROOM.md`, then load the skill relevant to the task. Read `safe-management` before modifying project resources.

## Compatibility

Compatibility with Graphify, Superpowers, MemPalace, Claude Code, OpenCode, and Codex output paths is not verified by this project. Do not infer compatibility from a tool's name or output folder; test it or cite authoritative documentation before registering a resource as `managed`.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
ruff format --check .
python -m build
```

See [architecture.md](architecture.md) for boundaries, update behavior, registry schema, and known distribution limits. See [CHANGELOG.md](CHANGELOG.md) for changes.

## License

MIT License. See [LICENSE](LICENSE).
