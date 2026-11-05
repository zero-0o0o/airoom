# AIroom CLI Reference

Auto-generated from `airoom --help` and all subcommand help output.

## Global Options

These options are available for all commands:

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Project directory (default: current directory) |
| `--verbose` | `-v` | Increase verbosity (can be repeated) |
| `--json` | | Output JSON instead of human-readable text |
| `--dry-run` | | Preview changes without writing |
| `--version` | | Show version and exit |
| `--help` | | Show help message and exit |

---

## Commands Overview

| Command | Description |
|---------|-------------|
| `status` | Show project health summary |
| `doctor` | Diagnose and repair common issues |
| `discover` | Discover AI artifacts and registry discrepancies |
| `organize` | Organize artifacts under `airoom/artifacts/` |
| `registry` | Manage artifact registry |
| `config` | Manage project configuration |
| `completion` | Generate shell completion script |
| `init` | Initialize AIroom in a project |
| `update` | Update project resources |
| `upgrade` | Upgrade the global CLI |
| `uninstall` | Uninstall the global CLI |

---

## `airoom status`

Show project health summary.

```bash
airoom status [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Project directory |
| `--json` | | Output JSON |
| `--help` | | Show help message and exit |

### Example

```bash
airoom status
airoom status --json
```

---

## `airoom doctor`

Diagnose and repair common issues.

```bash
airoom doctor [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Project directory |
| `--fix` | | Attempt safe repairs (recreate missing files/dirs from baseline) |
| `--json` | | Output JSON |
| `--help` | | Show help message and exit |

### Example

```bash
airoom doctor
airoom doctor --fix
airoom doctor --json
```

---

## `airoom discover`

Discover AI artifacts and registry discrepancies.

```bash
airoom discover [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Project directory |
| `--type` | | Filter candidates: `graphify`, `superpowers`, or `all` (default: `all`) |
| `--json` | | Output JSON |
| `--help` | | Show help message and exit |

### Example

```bash
airoom discover
airoom discover --type graphify
airoom discover --json
```

---

## `airoom organize`

Organize artifacts under `airoom/artifacts/`.

```bash
airoom organize [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Project directory |
| `--interactive` / `--non-interactive` | | Prompt for each candidate (default: interactive) |
| `--dry-run` | | Preview changes without executing |
| `--json` | | Output JSON |
| `--help` | | Show help message and exit |

### Example

```bash
airoom organize
airoom organize --non-interactive
airoom organize --dry-run
```

---

## `airoom registry`

Manage artifact registry.

```bash
airoom registry [OPTIONS] COMMAND [ARGS]...
```

### Subcommands

| Command | Description |
|---------|-------------|
| `list` | List all artifacts in the registry |
| `add` | Add an artifact to the registry |
| `remove` | Remove an artifact from the registry |
| `validate` | Validate the registry schema and structure |
| `show` | Show details of a specific artifact |

### `airoom registry list`

List all artifacts in the registry.

```bash
airoom registry list [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Project directory |
| `--json` | | Output JSON |
| `--help` | | Show help message and exit |

### `airoom registry add`

Add an artifact to the registry.

```bash
airoom registry add [OPTIONS] ARTIFACT_ID
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `ARTIFACT_ID` | Unique artifact identifier (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--owner` | | Owner/tool name (required) |
| `--artifact-path` | | Project-relative artifact path (required) |
| `--type` | | Artifact type: `file` or `directory` (required) |
| `--management` | | Management mode: `managed` or `external` (required) |
| `--status` | | Status: `active` or `inactive` (default: `active`) |
| `--original-path` | | Original source path |
| `--version` | | Artifact version |
| `--output-setting` | | Output setting |
| `--path` | `-p` | Project directory |
| `--json` | | Output JSON |
| `--help` | | Show help message and exit |

### `airoom registry remove`

Remove an artifact from the registry.

```bash
airoom registry remove [OPTIONS] ARTIFACT_ID
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `ARTIFACT_ID` | Artifact identifier to remove (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--force` | `-f` | Skip confirmation prompt |
| `--yes` | `-y` | Alias for `--force`, for scripted use |
| `--path` | `-p` | Project directory |
| `--json` | | Output JSON |
| `--help` | | Show help message and exit |

### `airoom registry validate`

Validate the registry schema and structure.

```bash
airoom registry validate [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Project directory |
| `--json` | | Output JSON |
| `--help` | | Show help message and exit |

### `airoom registry show`

Show details of a specific artifact.

```bash
airoom registry show [OPTIONS] ARTIFACT_ID
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `ARTIFACT_ID` | Artifact identifier to show (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Project directory |
| `--json` | | Output JSON |
| `--help` | | Show help message and exit |

---

## `airoom config`

Manage project configuration.

```bash
airoom config [OPTIONS] COMMAND [ARGS]...
```

### Subcommands

| Command | Description |
|---------|-------------|
| `show` | Show current configuration |
| `set` | Set a configuration value using dot notation |
| `unset` | Unset a configuration value using dot notation |

### `airoom config show`

Show current configuration.

```bash
airoom config show [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Project directory |
| `--json` | | Output JSON |
| `--help` | | Show help message and exit |

### `airoom config set`

Set a configuration value using dot notation.

```bash
airoom config set [OPTIONS] KEY VALUE
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `KEY` | Configuration key (dot notation) (required) |
| `VALUE` | Value to set (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Project directory |
| `--json` | | Output JSON |
| `--help` | | Show help message and exit |

### `airoom config unset`

Unset a configuration value using dot notation.

```bash
airoom config unset [OPTIONS] KEY
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `KEY` | Configuration key (dot notation) (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Project directory |
| `--json` | | Output JSON |
| `--help` | | Show help message and exit |

---

## `airoom completion`

Generate shell completion script.

```bash
airoom completion [OPTIONS] SHELL [COMMAND] [ARGS]...
```

### Arguments

| Argument | Description |
|----------|-------------|
| `SHELL` | Shell type: `bash`, `zsh`, or `fish` (required) |

### Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message and exit |

### Example

```bash
airoom completion bash
airoom completion zsh
airoom completion fish
```

---

## `airoom init`

Initialize AIroom in a project.

```bash
airoom init [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Project directory (default: current directory) |
| `--verbose` | `-v` | Increase verbosity (default: 0) |
| `--json` | | Output JSON |
| `--dry-run` | | Preview changes without writing |
| `--help` | | Show help message and exit |

### Example

```bash
airoom init
airoom init --path /path/to/project
airoom init --dry-run
```

---

## `airoom update`

Update project resources.

```bash
airoom update [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Project directory (default: current directory) |
| `--verbose` | `-v` | Increase verbosity (default: 0) |
| `--json` | | Output JSON |
| `--dry-run` | | Preview changes without writing |
| `--help` | | Show help message and exit |

### Example

```bash
airoom update
airoom update --dry-run
airoom update --json
```

---

## `airoom upgrade`

Upgrade the global CLI.

```bash
airoom upgrade [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--version` | Specific version to upgrade to (e.g., `0.2.0`) |
| `--prerelease` | Allow upgrading to prerelease versions |
| `--help` | Show help message and exit |

### Example

```bash
airoom upgrade
airoom upgrade --version 0.2.0
airoom upgrade --prerelease
```

---

## `airoom uninstall`

Uninstall the global CLI.

```bash
airoom uninstall [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--yes` | `-y` | Skip confirmation prompt |
| `--help` | | Show help message and exit |

### Example

```bash
airoom uninstall
airoom uninstall --yes
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (conflicts, failures, or invalid usage) |

## JSON Output

All commands support `--json` for machine-readable output. The structure varies by command but generally includes:

- **Success**: Command-specific result data
- **Error**: `{"error": "message"}`
- **Update/Init/Doctor**: Summary with counts (`updated`, `added`, `skipped`, `conflicts`, `errors`)

## See Also

- [README.md](../README.md) - Project overview and quick start
- [architecture.md](../architecture.md) - Architecture and design decisions
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Development setup and contribution guidelines