# AIroom Comprehensive Improvement Design

**Date**: 2026-11-04
**Status**: Approved
**Approach**: Hybrid (C) — Typer for new commands, argparse for legacy, shared core module

---

## Intent and Why

AIroom v0.1.0 provides solid project resource management (`init`, `update`, `upgrade`, `uninstall`) but lacks:
- Project health visibility (`status`, `doctor`)
- Registry management from CLI (`registry add/list/remove/validate/show`)
- Artifact discovery/organization workflows (`discover`, `organize`)
- Developer experience (tab completion, config, structured logging, `--dry-run`)
- Release automation (PyPI, Homebrew, CI/CD)

This design covers migrating to Typer for new commands while preserving stable argparse commands, extracting a shared core module, and delivering all planned improvements in phases.

---

## Goals

1. **Typer-based CLI** for all new commands with nested subcommands, rich help, auto-completion
2. **Shared core module** (`src/airoom/core/`) used by both CLI implementations
3. **Project health commands**: `status`, `doctor`
4. **Registry CLI**: full CRUD + validation
5. **Discovery/Organization CLI**: read-only scan + guided relocation
6. **Developer experience**: `--dry-run`, `--verbose`, `--json`, tab completion, config file
7. **CI/CD**: GitHub Actions matrix testing, PyPI trusted publishing, Homebrew formula
8. **Documentation**: CONTRIBUTING.md, architecture decision records, CLI reference

## Non-Goals

- Changing `init`/`update`/`upgrade`/`uninstall` behavior (preserved in argparse until Phase 4)
- Modifying agent-facing skills (kept separate per user decision)
- Remote registry sync, plugin system, LSP integration (future work)

## Anti-Goals

- Breaking existing `airoom init`/`update` workflows
- Adding dependencies beyond `typer`, `rich` (for output), `pyyaml` (already via ruamel.yaml)
- Duplicating business logic between argparse and Typer implementations

---

## Constraints

- Python 3.10+ (current requirement)
- Must preserve `.airoom-baseline.json` integrity logic
- Must preserve atomic write semantics for registry/version/baseline
- Must preserve symlink safety and project boundary checks
- Existing tests must continue to pass

---

## Approaches Considered

| Approach | Description | Verdict |
|----------|-------------|---------|
| **A: Phased Migration** | Rewrite all to Typer first, then add features | Rejected — high risk, delays features |
| **B: Incremental on Argparse** | Add all features to argparse, migrate last | Rejected — argparse limits nested commands, poor completion |
| **C: Hybrid (Selected)** | Typer for new commands, argparse for legacy, shared core | **Approved** — best balance of risk, velocity, UX |

---

## Design

### 1. Shared Core Module (`src/airoom/core/`)

Extract all business logic from `commands/` into a clean, testable core:

```
src/airoom/core/
├── __init__.py
├── project.py          # Project root discovery, path safety
├── registry.py         # Registry CRUD, validation (wraps existing)
├── baseline.py         # Baseline read/write/hash computation
├── resources.py        # Packaged resource access (skills, templates)
├── atomic.py           # Atomic write utilities (wraps existing)
├── safety.py           # Path validation, symlink checks
├── version.py          # Version file read/write
├── discovery.py        # Artifact discovery logic (from skill)
├── organization.py     # Artifact relocation logic (from skill)
└── config.py           # Config file read/write (new)
```

**Key classes**:
- `Project(root: Path)` — project context, safe paths
- `RegistryManager(project)` — registry operations
- `BaselineManager(project)` — baseline operations
- `ResourceManager()` — packaged resource access
- `DiscoveryEngine(project)` — read-only artifact scanning
- `OrganizationEngine(project)` — relocation with verification
- `ConfigManager(project)` — config file operations

Both argparse and Typer CLIs import from `airoom.core`.

---

### 2. Typer CLI Structure (`src/airoom/cli_typer.py`)

```python
import typer
from rich.console import Console
from rich.table import Table
from rich.json import JSON

app = typer.Typer(
    name="airoom",
    help="AIroom - Shared infrastructure for AI agents and tools",
    add_completion=False,  # We'll add custom completion command
    rich_markup_mode="rich",
)

console = Console()

# Legacy commands (ported from argparse in Phase 4)
legacy_app = typer.Typer(name="legacy", help="Legacy commands (to be migrated)")
app.add_typer(legacy_app, name="")

# New commands
status_app = typer.Typer(name="status", help="Show project health")
app.add_typer(status_app)

doctor_app = typer.Typer(name="doctor", help="Diagnose and repair issues")
app.add_typer(doctor_app)

registry_app = typer.Typer(name="registry", help="Registry management")
app.add_typer(registry_app)

discover_app = typer.Typer(name="discover", help="Discover AI artifacts")
app.add_typer(discover_app)

organize_app = typer.Typer(name="organize", help="Organize artifacts under airoom/artifacts/")
app.add_typer(organize_app)

config_app = typer.Typer(name="config", help="Configuration management")
app.add_typer(config_app)

completion_app = typer.Typer(name="completion", help="Shell completion")
app.add_typer(completion_app)
```

**Global options** (via callback):
- `--path/-p`: Project directory (default: cwd)
- `--verbose/-v`: Increase verbosity (repeatable)
- `--json`: Output JSON instead of human-readable
- `--dry-run`: Preview changes without writing

---

### 3. Command Specifications

#### 3.1 `airoom status [PATH] [--json]`

Shows project health summary:
- AIroom version (installed vs project)
- Baseline integrity (all tracked resources match hash)
- Registry validity (schema + path existence)
- Artifact verification (managed paths exist, external paths exist)
- Tool configuration status

**Output (human)**:
```
AIroom Status: /path/to/project
═══════════════════════════════
Version:        0.1.0 (installed) / 0.1.0 (project) ✓
Baseline:       6/6 resources verified ✓
Registry:       Valid schema, 4 artifacts, 2 tools ✓
Artifacts:
  graphify-output      managed  airoom/artifacts/graphify-out      ✓ exists
  superpowers-specs    managed  airoom/artifacts/docs/superpowers/specs  ✓ exists
  superpowers-plans    managed  airoom/artifacts/docs/superpowers/plans  ✓ exists
  superpowers-brainstorm managed airoom/artifacts/.superpowers/brainstorm ✓ exists
Tools:
  graphify             active  GRAPHIFY_OUT=airoom/artifacts/graphify-out
  superpowers          active  v7.0.1
```

#### 3.2 `airoom doctor [PATH] [--fix] [--json]`

Diagnoses common issues:
- Missing `.airoom-version` or `.airoom-baseline.json`
- Baseline mismatches (user-modified resources)
- Registry schema violations
- Missing artifact paths (registered but not on disk)
- Symlinks in `airoom/` directory
- Path boundary violations
- Orphaned skills (in project but not packaged)

With `--fix`: attempts safe repairs (recreate missing dirs, restore missing baseline entries from packaged resources, remove invalid registry entries with confirmation).

#### 3.3 `airoom registry` subcommands

| Command | Description |
|---------|-------------|
| `list [--json]` | List all artifacts and tools in table/JSON |
| `add <id> --owner --path --type --management --status [--original-path] [--version] [--output-setting]` | Register new artifact |
| `remove <id>` | Remove artifact entry (with confirmation) |
| `validate` | Validate registry schema and path existence |
| `show <id>` | Show full entry details |

**Validation**: All `add` operations run full schema validation + path safety checks before writing.

#### 3.4 `airoom discover [PATH] [--type graphify|superpowers|all] [--json]`

Read-only scan implementing `artifact-discovery` skill logic:
- Scans project root for known AI tool signatures
- Checks `airoom/artifacts/` for managed artifacts
- Reports unregistered candidates with owner evidence
- Reports registry discrepancies (missing, type mismatch, placement mismatch)
- Outputs structured report (human table or JSON)

#### 3.5 `airoom organize [PATH] [--interactive] [--dry-run]`

Guided relocation implementing `artifact-organization` skill:
1. Runs discovery to find candidates
2. For each candidate, shows relocation feasibility matrix
3. In `--interactive`: prompts for each (route/relocate/track-external/skip)
4. In non-interactive: applies defaults (managed if feasible, else external)
5. Executes moves with pre-flight checks, tool config updates, registry registration
6. Runs post-verification (tool can read/write new location)
7. Rollback on failure

#### 3.6 `airoom config` subcommands

| Command | Description |
|---------|-------------|
| `show [--json]` | Show effective config (defaults + project + user) |
| `set <key> <value>` | Set project config value |
| `unset <key>` | Remove project config value |

**Config file**: `airoom.config.yaml` in project root (optional)
```yaml
# Example
skips:
  - artifact-organization  # Don't install this skill by default
defaults:
  registry_management: external  # Default for new artifacts
  dry_run: false
  verbose: 0
```

#### 3.7 `airoom completion [bash|zsh|fish]`

Generates shell completion script using Typer's built-in support.

---

### 4. Migration Plan (Phases)

#### Phase 1: Core Extraction + Typer Foundation (Week 1)
- Create `src/airoom/core/` with all extracted logic
- Write `cli_typer.py` with app structure, global options
- Implement `status`, `doctor` commands using core
- Add `--dry-run`, `--verbose`, `--json` global options
- Update `pyproject.toml` entry point to new Typer CLI
- Keep argparse CLI as `cli_legacy.py` for reference

#### Phase 2: Registry CLI (Week 2)
- Implement `registry` subcommands (list, add, remove, validate, show)
- Add registry schema migration logic (future-proofing)
- Add artifact integrity verification (optional hash field)

#### Phase 3: Discovery & Organization CLI (Week 3)
- Implement `discover` command (read-only, from skill logic)
- Implement `organize` command (guided relocation, from skill logic)
- Add tool compatibility verification step

#### Phase 4: Developer Experience (Week 4)
- Implement `config` subcommands
- Add tab completion generation
- Add structured logging with JSON output option
- Add config file support

#### Phase 5: Legacy Migration + CI/CD + Packaging (Week 5)
- Port `init`, `update`, `upgrade`, `uninstall` to Typer (using core)
- Remove argparse CLI code
- Set up GitHub Actions CI (matrix 3.10/3.11/3.12, lint, type-check, test)
- Configure PyPI trusted publishing
- Create Homebrew formula
- Write CONTRIBUTING.md, ADR template

---

### 5. Testing Strategy

- **Unit tests**: Core module functions (project, registry, baseline, discovery, organization, config)
- **Integration tests**: Typer CLI commands via `typer.testing.CliRunner`
- **Legacy compatibility**: Existing argparse tests continue to pass until Phase 5
- **Property-based**: Hypothesis tests for registry validation edge cases
- **E2E**: Full workflow test (init → discover → organize → registry → status)

---

### 6. Documentation Updates

- `README.md`: Update CLI reference with new commands
- `docs/cli-reference.md`: Full command documentation (auto-generated from Typer help)
- `CONTRIBUTING.md`: Development setup, test/run/lint commands, PR process
- `docs/adr/`: Architecture decision records for major choices
- `CHANGELOG.md`: Track all changes

---

## What's Left to the Builder

- Exact Typer option naming (kebab-case vs snake_case)
- Rich table formatting details for `status`/`doctor`/`registry list`
- Interactive prompt wording in `organize`
- Config file schema defaults
- CI/CD workflow YAML specifics
- Homebrew formula template

---

## Approval

**Approved by user**: 2026-11-04
**Approach**: Hybrid (C) — Typer for new commands, argparse for legacy, shared core module
**Next step**: Invoke `writing-plans` skill for implementation plan