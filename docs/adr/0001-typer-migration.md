# ADR 0001: Migrate CLI from argparse to Typer

## Status

Accepted (Implemented)

## Context

AIroom's original CLI was built with Python's standard library `argparse`. As the command set grew to 11 commands with nested subcommands (registry, config, init, update), the argparse implementation became difficult to maintain:

- **Verbose boilerplate**: Each subcommand required manual parser setup, argument definitions, and help text
- **Inconsistent patterns**: Global options (`--path`, `--verbose`, `--json`, `--dry-run`, `--version`) were redefined per command
- **No rich output**: Limited to plain text; no colors, tables, or progress indicators
- **Manual completion**: Shell completion required custom implementation
- **Type safety**: No automatic type conversion or validation for arguments

The codebase already depended on `rich` for console output in core modules, making Typer a natural fit.

## Decision

Migrate the CLI from `argparse` to **Typer** (built on Click) with the following approach:

1. **Single Typer app** with global callback for shared options
2. **Subcommand modules** under `src/airoom/commands_typer/`
3. **Nested Typer apps** for `registry`, `config`, `init`, `update`, `upgrade`, `uninstall`, `completion`
4. **Rich markup mode** for formatted help output
5. **Global options via context object** (`GlobalOptions` dataclass)
6. **Preserve all existing behavior** exactly (exit codes, flags, output formats)

## Consequences

### Positive

- **Declarative syntax**: Commands defined with decorators and type hints
- **Automatic help**: Rich-formatted help with colors, tables, and groupings
- **Built-in completion**: `airoom completion bash|zsh|fish` works out of the box
- **Type safety**: Automatic validation and conversion via Python type hints
- **Global options once**: Defined in single callback, available to all commands
- **Rich integration**: Native support for `rich.Console` and markup
- **Less code**: ~40% reduction in CLI boilerplate
- **Maintainability**: Easier to add/modify commands and options

### Negative

- **New dependency**: `typer` (and transitive `click`) added to requirements
- **Learning curve**: Team must learn Typer patterns (mitigated by existing Click knowledge)
- **Migration effort**: One-time cost to rewrite all commands

### Neutral

- **Click dependency**: Typer uses Click internally; exposes Click context when needed
- **Python 3.10+**: Typer requires 3.7+; AIroom already requires 3.10+

## Alternatives Considered

### 1. Stay with argparse

**Pros**: No new dependencies, standard library
**Cons**: Growing maintenance burden, no rich output, manual completion, verbose

### 2. Click directly

**Pros**: Mature, powerful, Typer is built on it
**Cons**: More verbose than Typer, less modern ergonomics, no automatic type hints

### 3. Fire

**Pros**: Extremely simple, auto-generates CLI from functions
**Cons**: Less control, poor help formatting, no nested subcommands, limited customization

### 4. CliKit / Cleo

**Pros**: Used by Poetry, robust
**Cons**: Less community adoption, steeper learning curve, overkill for AIroom's needs

## Implementation Details

### Global Options Pattern

```python
# cli.py
def global_options_callback(
    ctx: typer.Context,
    path: Annotated[Optional[Path], typer.Option("--path", "-p")] = None,
    verbose: Annotated[int, typer.Option("--verbose", "-v", count=True)] = 0,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    version: Annotated[bool, typer.Option("--version", callback=version_callback)] = False,
) -> None:
    ctx.obj = GlobalOptions(path=path, verbose=verbose, json_output=json_output, dry_run=dry_run)

app.callback(invoke_without_command=True)(global_options_callback)
```

### Subcommand Registration

```python
# cli.py
app.command("status", help="Show project health summary")(status)
app.add_typer(registry_app, name="registry")
app.add_typer(config_app, name="config")
```

### Command Module Pattern

```python
# commands_typer/status.py
status_app = typer.Typer(name="status", help="Show project health summary")

@status_app.callback(invoke_without_command=True)
def status(
    ctx: typer.Context,
    path: Annotated[Optional[Path], typer.Option("--path", "-p")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    # Merge global + local options
    global_opts = ctx.obj
    # ... implementation
```

## Verification

All existing tests pass:

```bash
pytest tests/test_cli_typer_*.py -v
pytest tests/test_cli_dry_run.py -v
pytest tests/test_core_*.py -v
```

Behavioral parity confirmed for:
- Exit codes (0 success, 1 error/conflict)
- Global flags (`--path`, `--verbose`, `--json`, `--dry-run`, `--version`)
- Command-specific flags
- JSON output structure
- Dry-run semantics
- Help text (now enhanced with Rich)

## References

- [Typer Documentation](https://typer.tiangolo.com/)
- [Click Documentation](https://click.palletsprojects.com/)
- [Rich Documentation](https://rich.readthedocs.io/)
- Related: `src/airoom/cli.py`, `src/airoom/commands_typer/`, `tests/test_cli_typer_*.py`