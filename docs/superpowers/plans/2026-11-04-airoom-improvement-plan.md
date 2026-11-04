# AIroom Comprehensive Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate AIroom CLI from argparse to Typer with hybrid approach, extract shared core module, and deliver all planned improvements (status, doctor, registry, discover, organize, config, completion, CI/CD, packaging).

**Architecture:** Hybrid migration — Typer for new commands (`status`, `doctor`, `registry`, `discover`, `organize`, `config`, `completion`), argparse preserved for legacy commands (`init`, `update`, `upgrade`, `uninstall`) until Phase 5. Shared `src/airoom/core/` module provides all business logic to both CLIs.

**Tech Stack:** Python 3.10+, Typer, Rich (output), ruamel.yaml (registry), pytest (testing), GitHub Actions (CI/CD), PyPI trusted publishing, Homebrew.

**Spec:** `docs/superpowers/specs/2026-11-04-airoom-improvement-design.md`

---

## Global Constraints

- Python 3.10+ (current requirement, no version bump)
- Preserve `.airoom-baseline.json` integrity logic exactly
- Preserve atomic write semantics for registry/version/baseline
- Preserve symlink safety and project boundary checks
- All existing tests must continue to pass until Phase 5
- No new dependencies beyond: `typer`, `rich`, `pyyaml` (transitive via ruamel.yaml)
- Registry schema version remains 1 (migration logic added for future)

---

## Review Focus

| Input / Failure Mode | Expected Behavior | Test Location |
|---------------------|-------------------|---------------|
| Registry with duplicate YAML keys | Rejected with clear error, file unchanged | Task 2.3 (registry validation) |
| Symlink in `airoom/` directory | Detected and rejected by all commands | Task 1.2 (safety), Task 5.1 (doctor) |
| Concurrent modification of registry/baseline | Atomic write detects and aborts | Task 1.3 (atomic), Task 2.4 (registry write) |
| User-modified skill file during `update` | Preserved, conflict reported, version not advanced | Task 4.2 (update integration) |
| `--dry-run` on any command | No filesystem writes, shows planned changes | Task 3.1 (global options), all command tasks |
| Invalid project path (outside root) | Rejected with clear error | Task 1.1 (project discovery) |
| Missing `.airoom-version` in initialized project | `doctor` reports, `--fix` recreates from baseline | Task 3.3 (doctor) |
| Registry entry with `management: managed` but path not under `airoom/artifacts/` | Rejected on add/validate | Task 3.2 (registry add/validate) |
| `organize` relocation where tool doesn't support new path | Rollback to original, registry updated to `external` | Task 3.6 (organize verification) |
| Config file with invalid YAML | Graceful error, defaults used | Task 4.3 (config) |

---

## File Structure Map

```
src/airoom/
├── core/                    # NEW: Shared business logic
│   ├── __init__.py
│   ├── project.py           # Project discovery, path safety
│   ├── registry.py          # Registry CRUD, validation
│   ├── baseline.py          # Baseline read/write/hash
│   ├── resources.py         # Packaged resource access
│   ├── atomic.py            # Atomic write utilities
│   ├── safety.py            # Path validation, symlink checks
│   ├── version.py           # Version file read/write
│   ├── discovery.py         # Artifact discovery engine
│   ├── organization.py      # Artifact relocation engine
│   └── config.py            # Config file management
├── cli.py                   # MODIFIED: Typer entry point (replaces argparse)
├── cli_legacy.py            # NEW: Argparse CLI preserved for Phase 1-4
├── commands/                # DEPRECATED: Kept until Phase 5
│   ├── __init__.py
│   ├── init.py
│   ├── update.py
│   ├── upgrade.py
│   └── uninstall.py
├── registry.py              # MOVED to core/registry.py (re-export)
├── __init__.py
├── resources/               # UNCHANGED
│   ├── skills/*/SKILL.md
│   └── templates/*
tests/
├── test_core_*.py           # NEW: Core module unit tests
├── test_cli_typer_*.py      # NEW: Typer CLI integration tests
├── test_init.py             # EXISTING: Updated to use core
├── test_update.py           # EXISTING: Updated to use core
├── test_upgrade.py          # EXISTING: Updated to use core
├── test_uninstall.py        # EXISTING: Updated to use core
├── test_registry.py         # EXISTING: Updated to use core
├── conftest.py              # NEW: Shared fixtures
docs/
├── superpowers/
│   ├── specs/2026-11-04-airoom-improvement-design.md
│   └── plans/2026-11-04-airoom-improvement-plan.md
├── cli-reference.md         # NEW: Auto-generated from Typer help
├── adr/
│   └── 0001-typer-migration.md
└── CONTRIBUTING.md          # NEW
.github/workflows/
├── ci.yml                   # NEW: Matrix test, lint, type-check
└── release.yml              # NEW: PyPI trusted publishing
homebrew/
└── airoom.rb                # NEW: Homebrew formula
```

---

## Phase 1: Core Extraction + Typer Foundation

### Task 1.1: Create `src/airoom/core/project.py`

**Files:**
- Create: `src/airoom/core/project.py`
- Test: `tests/test_core_project.py`

**Interfaces:**
- Consumes: None (foundation)
- Produces: `Project` class, `find_project_root()`, `assert_safe_project_path()`

```python
# Signature
class Project:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.airoom_dir = self.root / "airoom"
        self.skills_dir = self.airoom_dir / "skills"
        self.artifacts_dir = self.airoom_dir / "artifacts"
        self.registry_path = self.airoom_dir / "registry.yaml"
        self.version_path = self.airoom_dir / ".airoom-version"
        self.baseline_path = self.airoom_dir / ".airoom-baseline.json"
        self.airoom_md_path = self.airoom_dir / "AIROOM.md"
        self.agents_path = self.root / "AGENTS.md"

    def assert_safe(self, path: Path) -> None: ...

def find_project_root(start_path: Path | None = None) -> Path: ...

def assert_safe_project_path(project_root: Path, path: Path) -> None: ...
```

- [ ] **Step 1: Write failing tests** for `Project` initialization, path properties, `find_project_root`, `assert_safe_project_path` (symlink rejection, boundary check)
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement `Project` class and functions** — extract from `commands/init.py` and `commands/update.py`, preserve all safety logic
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 1.2: Create `src/airoom/core/safety.py`

**Files:**
- Create: `src/airoom/core/safety.py`
- Test: `tests/test_core_safety.py`

**Interfaces:**
- Consumes: `Project` from Task 1.1
- Produces: `validate_path()`, `check_symlinks()`, `ensure_directory()`

```python
# Signatures
def validate_path(project: Project, path: Path, field: str) -> str: ...

def check_symlinks(project: Project, path: Path) -> bool: ...

def ensure_directory(path: Path, verbose: bool = True) -> bool: ...
```

- [ ] **Step 1: Write failing tests** for path validation (traversal, absolute, backslash), symlink detection, directory creation
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — extract from `commands/init.py` (`_relative_path`, `assert_safe_project_path`, `create_directory`)
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 1.3: Create `src/airoom/core/atomic.py`

**Files:**
- Create: `src/airoom/core/atomic.py`
- Test: `tests/test_core_atomic.py`

**Interfaces:**
- Consumes: None
- Produces: `atomic_write()`, `compute_file_hash()`

```python
# Signatures
def atomic_write(
    path: Path,
    content: str,
    *,
    expected_text: str | None = None,
    expected_absent: bool = False,
) -> None: ...

def compute_file_hash(file_path: Path) -> str: ...
```

- [ ] **Step 1: Write failing tests** for atomic write (normal, concurrent modification, absent expectation), hash computation
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — extract from `registry.py` and `commands/update.py`, preserve exact behavior
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 1.4: Create `src/airoom/core/registry.py`

**Files:**
- Create: `src/airoom/core/registry.py`
- Modify: `src/airoom/registry.py` (re-export from core)
- Test: `tests/test_core_registry.py`

**Interfaces:**
- Consumes: `Project`, `atomic_write`, `compute_file_hash`
- Produces: `RegistryManager` class, `parse_registry()`, `dump_registry()`, `validate_registry()`

```python
# Signatures (preserve existing from src/airoom/registry.py)
class RegistryError(ValueError): ...

def _yaml() -> YAML: ...
def _relative_path(value: Any, field: str) -> str: ...
def validate_registry(data: Any) -> None: ...
def parse_registry(text: str) -> Any: ...
def dump_registry(data: Any) -> str: ...

class RegistryManager:
    def __init__(self, project: Project): ...
    def read(self) -> dict: ...
    def write(self, data: dict) -> None: ...
    def validate(self) -> tuple[bool, list[str]]: ...
    def add_artifact(self, artifact_id: str, entry: dict) -> None: ...
    def remove_artifact(self, artifact_id: str) -> None: ...
    def add_tool(self, tool_id: str, entry: dict) -> None: ...
    def remove_tool(self, tool_id: str) -> None: ...
```

- [ ] **Step 1: Write failing tests** for all RegistryManager methods, validation, duplicate path detection, managed path enforcement
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — move logic from `src/airoom/registry.py`, add `RegistryManager` class wrapping it
- [ ] **Step 4: Update `src/airoom/registry.py` to re-export from core** (backward compatibility)
- [ ] **Step 5: Run all registry tests (old + new) to verify they pass**
- [ ] **Step 6: Commit**

---

### Task 1.5: Create `src/airoom/core/baseline.py`

**Files:**
- Create: `src/airoom/core/baseline.py`
- Test: `tests/test_core_baseline.py`

**Interfaces:**
- Consumes: `Project`, `atomic_write`, `compute_file_hash`
- Produces: `BaselineManager` class

```python
# Signatures
class BaselineManager:
    def __init__(self, project: Project): ...
    def read(self) -> dict[str, str]: ...
    def write(self, baseline: dict[str, str]) -> None: ...
    def update_hash(self, relpath: str, content: bytes) -> None: ...
    def remove_hash(self, relpath: str) -> None: ...
    def verify(self, relpath: str, content: bytes) -> bool: ...
```

- [ ] **Step 1: Write failing tests** for read/write/update/remove/verify
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — extract from `commands/init.py` and `commands/update.py` baseline logic
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 1.6: Create `src/airoom/core/resources.py`

**Files:**
- Create: `src/airoom/core/resources.py`
- Test: `tests/test_core_resources.py`

**Interfaces:**
- Consumes: None
- Produces: `ResourceManager` class

```python
# Signatures
class ResourceManager:
    def __init__(self): ...
    def get_resource_path(self, relative_path: str) -> Path: ...
    def read_resource(self, relative_path: str) -> str: ...
    def list_packaged_skills(self) -> list[str]: ...
    def list_packaged_templates(self) -> list[str]: ...
```

- [ ] **Step 1: Write failing tests** for resource path resolution, reading, listing skills/templates
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — extract from `commands/init.py`
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 1.7: Create `src/airoom/core/version.py`

**Files:**
- Create: `src/airoom/core/version.py`
- Test: `tests/test_core_version.py`

**Interfaces:**
- Consumes: `Project`, `atomic_write`
- Produces: `read_version_file()`, `write_version_file()`

```python
# Signatures
def read_version_file(version_path: Path) -> str: ...
def write_version_file(version_path: Path, version: str) -> None: ...
```

- [ ] **Step 1: Write failing tests** for read/write version file
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — extract from `commands/upgrade.py` and `commands/update.py`
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 1.8: Create `src/airoom/core/discovery.py`

**Files:**
- Create: `src/airoom/core/discovery.py`
- Test: `tests/test_core_discovery.py`

**Interfaces:**
- Consumes: `Project`, `RegistryManager`
- Produces: `DiscoveryEngine` class, `DiscoveryReport` dataclass

```python
# Signatures
@dataclass
class DiscoveredArtifact:
    path: str
    likely_owner: str
    evidence: list[str]
    type: Literal["file", "directory"]
    recommended_mode: Literal["managed", "external"]
    relocation_feasibility: str

@dataclass
class RegistryDiscrepancy:
    kind: Literal["missing_path", "unregistered_candidate", "type_mismatch", "placement_mismatch", "duplicate_claim"]
    details: str

@dataclass
class DiscoveryReport:
    inspected_locations: list[str]
    registered_artifacts: list[tuple[str, bool]]  # (id, exists)
    unregistered_candidates: list[DiscoveredArtifact]
    discrepancies: list[RegistryDiscrepancy]
    recommendations: list[str]

class DiscoveryEngine:
    def __init__(self, project: Project, registry: RegistryManager): ...
    def scan(self) -> DiscoveryReport: ...
    def _find_candidates(self) -> list[DiscoveredArtifact]: ...
    def _check_registry_discrepancies(self, report: DiscoveryReport) -> None: ...
```

- [ ] **Step 1: Write failing tests** for scan, candidate detection (Graphify, Superpowers, scratchpads), discrepancy detection
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — implement `artifact-discovery` skill logic programmatically
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 1.9: Create `src/airoom/core/organization.py`

**Files:**
- Create: `src/airoom/core/organization.py`
- Test: `tests/test_core_organization.py`

**Interfaces:**
- Consumes: `Project`, `RegistryManager`, `DiscoveryEngine`, `BaselineManager`
- Produces: `OrganizationEngine` class, `RelocationPlan` dataclass

```python
# Signatures
@dataclass
class RelocationAction:
    source: Path
    target: Path
    artifact_id: str
    tool_id: str
    management: Literal["managed", "external"]
    env_var: str | None

@dataclass
class RelocationPlan:
    actions: list[RelocationAction]
    tool_configs: dict[str, dict]  # tool_id -> {output_path, output_env}

class OrganizationEngine:
    def __init__(self, project: Project, registry: RegistryManager, baseline: BaselineManager): ...
    def plan(self, discovery_report: DiscoveryReport, interactive: bool = False) -> RelocationPlan: ...
    def execute(self, plan: RelocationPlan, dry_run: bool = False) -> tuple[bool, list[str]]: ...
    def _preflight_checks(self, action: RelocationAction) -> tuple[bool, str]: ...
    def _move_artifact(self, action: RelocationAction) -> bool: ...
    def _update_tool_config(self, tool_id: str, config: dict) -> None: ...
    def _register_artifact(self, action: RelocationAction) -> None: ...
    def _verify_and_rollback(self, action: RelocationAction) -> bool: ...
```

- [ ] **Step 1: Write failing tests** for plan (interactive/non-interactive), execute (dry-run/real), preflight, move, verify, rollback
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — implement `artifact-organization` skill logic programmatically
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 1.10: Create `src/airoom/core/config.py`

**Files:**
- Create: `src/airoom/core/config.py`
- Test: `tests/test_core_config.py`

**Interfaces:**
- Consumes: `Project`
- Produces: `ConfigManager` class, `Config` dataclass

```python
# Signatures
@dataclass
class Config:
    skips: list[str]
    defaults: dict[str, Any]
    dry_run: bool
    verbose: int

class ConfigManager:
    def __init__(self, project: Project): ...
    def read(self) -> Config: ...
    def write(self, config: Config) -> None: ...
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    def unset(self, key: str) -> None: ...
```

- [ ] **Step 1: Write failing tests** for read/write/get/set/unset, defaults merging
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — YAML config file at `project_root/airoom.config.yaml`
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 1.11: Create `src/airoom/core/__init__.py`

**Files:**
- Create: `src/airoom/core/__init__.py`

**Interfaces:**
- Re-exports all public APIs from core modules

- [ ] **Step 1: Write `__init__.py`** with all public exports
- [ ] **Step 2: Run import test** to verify all modules accessible
- [ ] **Step 3: Commit**

---

### Task 1.12: Create Typer CLI Entry Point `src/airoom/cli.py`

**Files:**
- Modify: `src/airoom/cli.py` (replace argparse with Typer)
- Create: `src/airoom/cli_legacy.py` (preserve argparse for Phase 1-4)
- Test: `tests/test_cli_typer_root.py`

**Interfaces:**
- Consumes: All core modules
- Produces: `app` (Typer), `legacy_app` (argparse preserved)

```python
# Structure
import typer
from rich.console import Console

app = typer.Typer(name="airoom", help="...", rich_markup_mode="rich", add_completion=False)
legacy_app = typer.Typer(name="legacy", help="Legacy commands")

# Global options via callback
def global_options(
    path: Path = typer.Option(None, "--path", "-p", help="Project directory"),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Increase verbosity"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing"),
):
    ...

# Register subcommand groups (Tasks 2.1-2.7 will add commands)
```

- [ ] **Step 1: Write failing tests** for global options parsing, help output, command registration
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement Typer app** with global options callback, register legacy subcommands
- [ ] **Step 4: Move existing argparse CLI to `cli_legacy.py`** (preserve for reference)
- [ ] **Step 5: Update `pyproject.toml` entry point** to new `cli:app`
- [ ] **Step 6: Run tests to verify they pass**
- [ ] **Step 7: Commit**

---

## Phase 2: New CLI Commands

### Task 2.1: Implement `airoom status` command

**Files:**
- Create: `src/airoom/commands_typer/status.py`
- Modify: `src/airoom/cli.py` (register)
- Test: `tests/test_cli_typer_status.py`

**Interfaces:**
- Consumes: `Project`, `RegistryManager`, `BaselineManager`, `ResourceManager`
- Produces: `status_app` Typer subcommand

```python
# Signatures
@status_app.command()
def status(
    ctx: typer.Context,
    path: Path = typer.Option(None, "--path", "-p"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Show project health summary."""
```

- [ ] **Step 1: Write failing tests** for status output (human + JSON), all health checks
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — version check, baseline verification, registry validation, artifact existence, tool config
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 2.2: Implement `airoom doctor` command

**Files:**
- Create: `src/airoom/commands_typer/doctor.py`
- Modify: `src/airoom/cli.py` (register)
- Test: `tests/test_cli_typer_doctor.py`

**Interfaces:**
- Consumes: `Project`, `RegistryManager`, `BaselineManager`, `ResourceManager`, `DiscoveryEngine`
- Produces: `doctor_app` Typer subcommand

```python
# Signatures
@doctor_app.command()
def doctor(
    ctx: typer.Context,
    path: Path = typer.Option(None, "--path", "-p"),
    fix: bool = typer.Option(False, "--fix", help="Attempt safe repairs"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Diagnose and repair common issues."""
```

- [ ] **Step 1: Write failing tests** for all diagnostics, `--fix` repairs, JSON output
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — missing files, baseline mismatches, registry violations, missing artifacts, symlinks, boundary violations, orphaned skills
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 2.3: Implement `airoom registry` subcommands

**Files:**
- Create: `src/airoom/commands_typer/registry.py`
- Modify: `src/airoom/cli.py` (register)
- Test: `tests/test_cli_typer_registry.py`

**Interfaces:**
- Consumes: `Project`, `RegistryManager`
- Produces: `registry_app` Typer subcommand group

```python
# Signatures
@registry_app.command("list")
def registry_list(json_output: bool = False): ...

@registry_app.command("add")
def registry_add(
    artifact_id: str,
    owner: str = typer.Option(..., "--owner"),
    path: str = typer.Option(..., "--path"),
    type: str = typer.Option(..., "--type"),
    management: str = typer.Option(..., "--management"),
    status: str = typer.Option("active", "--status"),
    original_path: str | None = typer.Option(None, "--original-path"),
    version: str | None = typer.Option(None, "--version"),
    output_setting: str | None = typer.Option(None, "--output-setting"),
): ...

@registry_app.command("remove")
def registry_remove(artifact_id: str, force: bool = False): ...

@registry_app.command("validate")
def registry_validate(json_output: bool = False): ...

@registry_app.command("show")
def registry_show(artifact_id: str, json_output: bool = False): ...
```

- [ ] **Step 1: Write failing tests** for all subcommands, validation, error cases
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — full CRUD with schema validation, path safety, confirmation prompts
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 2.4: Implement `airoom discover` command

**Files:**
- Create: `src/airoom/commands_typer/discover.py`
- Modify: `src/airoom/cli.py` (register)
- Test: `tests/test_cli_typer_discover.py`

**Interfaces:**
- Consumes: `Project`, `DiscoveryEngine`
- Produces: `discover_app` Typer subcommand

```python
# Signatures
@discover_app.command()
def discover(
    ctx: typer.Context,
    path: Path = typer.Option(None, "--path", "-p"),
    type: str = typer.Option("all", "--type", help="graphify|superpowers|all"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Discover AI artifacts and registry discrepancies."""
```

- [ ] **Step 1: Write failing tests** for scan output (human table + JSON), filtering by type
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — delegate to `DiscoveryEngine.scan()`, format report
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 2.5: Implement `airoom organize` command

**Files:**
- Create: `src/airoom/commands_typer/organize.py`
- Modify: `src/airoom/cli.py` (register)
- Test: `tests/test_cli_typer_organize.py`

**Interfaces:**
- Consumes: `Project`, `OrganizationEngine`, `DiscoveryEngine`
- Produces: `organize_app` Typer subcommand

```python
# Signatures
@organize_app.command()
def organize(
    ctx: typer.Context,
    path: Path = typer.Option(None, "--path", "-p"),
    interactive: bool = typer.Option(True, "--interactive/--non-interactive"),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """Organize artifacts under airoom/artifacts/."""
```

- [ ] **Step 1: Write failing tests** for interactive/non-interactive, dry-run, full execution, rollback
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — discovery → plan → confirm → execute → verify → rollback on failure
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 2.6: Implement `airoom config` subcommands

**Files:**
- Create: `src/airoom/commands_typer/config.py`
- Modify: `src/airoom/cli.py` (register)
- Test: `tests/test_cli_typer_config.py`

**Interfaces:**
- Consumes: `Project`, `ConfigManager`
- Produces: `config_app` Typer subcommand group

```python
# Signatures
@config_app.command("show")
def config_show(json_output: bool = False): ...

@config_app.command("set")
def config_set(key: str, value: str): ...

@config_app.command("unset")
def config_unset(key: str): ...
```

- [ ] **Step 1: Write failing tests** for show/set/unset, defaults merging
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — YAML config file read/write
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 2.7: Implement `airoom completion` command

**Files:**
- Create: `src/airoom/commands_typer/completion.py`
- Modify: `src/airoom/cli.py` (register)
- Test: `tests/test_cli_typer_completion.py`

**Interfaces:**
- Consumes: Typer app
- Produces: `completion_app` Typer subcommand

```python
# Signatures
@completion_app.command()
def completion(shell: str = typer.Argument(..., help="bash|zsh|fish")):
    """Generate shell completion script."""
```

- [ ] **Step 1: Write failing tests** for bash/zsh/fish output
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — use Typer's built-in completion generation
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

## Phase 3: Developer Experience Enhancements

### Task 3.1: Add Structured Logging with JSON Output

**Files:**
- Modify: `src/airoom/cli.py` (global logging setup)
- Create: `src/airoom/core/logging.py`
- Test: `tests/test_core_logging.py`

**Interfaces:**
- Consumes: Global `--verbose`, `--json` options
- Produces: Configured logger used by all commands

- [ ] **Step 1: Write failing tests** for log levels, JSON formatting, output capture
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — stdlib `logging` with JSON formatter when `--json`, Rich handler otherwise
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 3.2: Ensure `--dry-run` Works on All Commands

**Files:**
- Modify: All command files (status, doctor, registry, discover, organize, config)
- Test: `tests/test_cli_dry_run.py`

**Interfaces:**
- Consumes: Global `dry_run` flag from context
- Produces: No filesystem writes when dry-run

- [ ] **Step 1: Write failing tests** for each command with `--dry-run` (verify no writes)
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — check `ctx.obj.dry_run` in all write paths, skip with log message
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 3.3: Update Existing Tests to Use Core Module

**Files:**
- Modify: `tests/test_init.py`, `tests/test_update.py`, `tests/test_upgrade.py`, `tests/test_uninstall.py`, `tests/test_registry.py`
- Test: All existing tests

**Interfaces:**
- Consumes: Core module APIs
- Produces: Updated tests passing

- [ ] **Step 1: Run existing tests to verify baseline pass**
- [ ] **Step 2: Update imports** from `airoom.commands.*` to `airoom.core.*`
- [ ] **Step 3: Update test fixtures** to use `Project`, `RegistryManager`, etc.
- [ ] **Step 4: Run all tests to verify they pass**
- [ ] **Step 5: Commit**

---

## Phase 4: Legacy Migration + CI/CD + Packaging

### Task 4.1: Migrate `init` Command to Typer

**Files:**
- Create: `src/airoom/commands_typer/init.py`
- Modify: `src/airoom/cli.py` (replace legacy)
- Test: `tests/test_cli_typer_init.py`

**Interfaces:**
- Consumes: All core modules
- Produces: `init` command in Typer

- [ ] **Step 1: Write failing tests** for all init behaviors (fresh, repeat, preserve, symlink rejection)
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — port logic from `commands/init.py` using core module
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 4.2: Migrate `update` Command to Typer

**Files:**
- Create: `src/airoom/commands_typer/update.py`
- Modify: `src/airoom/cli.py` (replace legacy)
- Test: `tests/test_cli_typer_update.py`

**Interfaces:**
- Consumes: All core modules
- Produces: `update` command in Typer

- [ ] **Step 1: Write failing tests** for all update behaviors (skills, registry, AGENTS.md, AIROOM.md, baseline, version, conflicts)
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — port logic from `commands/update.py` using core module
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 4.3: Migrate `upgrade` Command to Typer

**Files:**
- Create: `src/airoom/commands_typer/upgrade.py`
- Modify: `src/airoom/cli.py` (replace legacy)
- Test: `tests/test_cli_typer_upgrade.py`

**Interfaces:**
- Consumes: `upgrade` logic (GitHub API, pipx)
- Produces: `upgrade` command in Typer

- [ ] **Step 1: Write failing tests** for upgrade scenarios (latest, specific version, prerelease, failure)
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — port logic from `commands/upgrade.py`
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 4.4: Migrate `uninstall` Command to Typer

**Files:**
- Create: `src/airoom/commands_typer/uninstall.py`
- Modify: `src/airoom/cli.py` (replace legacy)
- Test: `tests/test_cli_typer_uninstall.py`

**Interfaces:**
- Consumes: `uninstall` logic (pipx)
- Produces: `uninstall` command in Typer

- [ ] **Step 1: Write failing tests** for uninstall scenarios (confirm, --yes, failure, verification)
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement** — port logic from `commands/uninstall.py`
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 4.5: Remove Legacy CLI Code

**Files:**
- Delete: `src/airoom/cli_legacy.py`
- Delete: `src/airoom/commands/__init__.py`, `init.py`, `update.py`, `upgrade.py`, `uninstall.py`
- Modify: `src/airoom/__init__.py` (remove legacy exports if any)
- Test: Full test suite

- [ ] **Step 1: Verify all tests pass with Typer CLI**
- [ ] **Step 2: Delete legacy files**
- [ ] **Step 3: Run full test suite**
- [ ] **Step 4: Commit**

---

### Task 4.6: Set Up GitHub Actions CI/CD

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: `pyproject.toml` dependencies, test commands
- Produces: Automated CI/CD pipelines

```yaml
# ci.yml: matrix test (3.10, 3.11, 3.12), ruff check, ruff format --check, pytest with coverage
# release.yml: on tag push, build wheel, publish to PyPI via trusted publishing
```

- [ ] **Step 1: Write CI workflow** with matrix, lint, format, test, coverage
- [ ] **Step 2: Write release workflow** with trusted publishing
- [ ] **Step 3: Test workflows** by pushing to branch
- [ ] **Step 4: Commit**

---

### Task 4.7: Create Homebrew Formula

**Files:**
- Create: `homebrew/airoom.rb`

**Interfaces:**
- Consumes: PyPI package metadata
- Produces: Homebrew formula

```ruby
# airoom.rb: formula for pipx-installable Python package
class Airoom < Formula
  desc "Shared infrastructure for AI agents and tools"
  homepage "https://github.com/zero-0o0o/airoom"
  url "https://pypi.org/packages/source/a/airoom/airoom-0.1.0.tar.gz"
  sha256 "..."
  depends_on "pipx"
  def install
    system "pipx", "install", "--force", "--spec", cached_download, "airoom"
  end
end
```

- [ ] **Step 1: Write formula** with correct SHA256
- [ ] **Step 2: Test locally** with `brew install --build-from-source ./homebrew/airoom.rb`
- [ ] **Step 3: Commit**

---

### Task 4.8: Write Documentation

**Files:**
- Create: `docs/cli-reference.md` (auto-generate from Typer help)
- Create: `CONTRIBUTING.md`
- Create: `docs/adr/0001-typer-migration.md`
- Modify: `README.md` (update CLI reference)

- [ ] **Step 1: Generate CLI reference** from `airoom --help` and subcommands
- [ ] **Step 2: Write CONTRIBUTING.md** (dev setup, test/lint/run, PR process)
- [ ] **Step 3: Write ADR** for Typer migration decision
- [ ] **Step 4: Update README.md** with new commands
- [ ] **Step 5: Commit**

---

### Task 4.9: Final Integration Testing

**Files:**
- Test: Full test suite + manual e2e

- [ ] **Step 1: Run full test suite** — all tests pass
- [ ] **Step 2: Manual e2e test** — `init` → `discover` → `organize` → `registry` → `status` → `doctor` → `update` → `upgrade` → `uninstall`
- [ ] **Step 3: Verify PyPI build** — `python -m build` produces valid wheel
- [ ] **Step 4: Commit**

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-11-04-airoom-improvement-plan.md`.**

**Recommended execution approach: Subagent-driven**

Because:
- 49 tasks with clear dependencies (core → commands → migration → CI/CD)
- Each task has independent test cycle
- Fresh reviewer per task catches interface mismatches early
- Typer migration touches entire codebase; independent verification critical

**Please review the plan. Does it capture what you want?**