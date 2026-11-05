# Contributing to AIroom

Thank you for your interest in contributing to AIroom! This document provides guidelines for development setup, testing, linting, and the contribution process.

## Development Setup

### Prerequisites

- **Python 3.10+** (required)
- **pipx** (for global CLI installation)
- **Git** (for version control)

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/zero-0o0o/airoom.git
cd airoom

# Install in development mode with dev dependencies
python -m pip install -e '.[dev]'

# Verify installation
airoom --help
pytest --version
ruff --version
```

### Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Run tests and linters (see below)
4. Commit with clear messages
5. Push and open a Pull Request

## Running Tests

### All Tests

```bash
pytest
```

### Specific Test Modules

```bash
# Core functionality tests
pytest tests/test_core_*.py

# CLI Typer tests
pytest tests/test_cli_typer_*.py

# Registry tests
pytest tests/test_registry.py
```

### Test with Coverage

```bash
pytest --cov=airoom --cov-report=term-missing
```

### Continuous Testing

```bash
# Watch for changes (requires pytest-watch)
ptw
```

## Linting and Formatting

### Check Code Style

```bash
# Lint with Ruff
ruff check .

# Check formatting
ruff format --check .
```

### Auto-fix Issues

```bash
# Auto-fix linting issues
ruff check . --fix

# Auto-format code
ruff format .
```

### Combined Check

```bash
# Run all checks (lint + format check)
ruff check . && ruff format --check .
```

## Type Checking

```bash
# If mypy is configured (optional)
mypy src/airoom
```

## Building

### Build Package

```bash
python -m build
```

### Verify Build

```bash
# Check the built package
twine check dist/*
```

## Pull Request Process

### Before Submitting

1. **All tests pass**: `pytest`
2. **No linting errors**: `ruff check .`
3. **Code formatted**: `ruff format --check .`
4. **Documentation updated** (if applicable): Update `README.md`, `docs/cli-reference.md`, or `docs/adr/` as needed
5. **Changelog updated**: Add entry to `CHANGELOG.md` under "Unreleased"

### PR Requirements

- **Clear title**: Summarize the change in one line
- **Description**: Explain what changed and why
- **Linked issues**: Reference related issues (e.g., `Fixes #123`)
- **Small scope**: One logical change per PR
- **Tests included**: New functionality requires tests

### Review Process

1. Automated checks must pass (CI)
2. At least one maintainer review
3. All conversations resolved
4. Squash and merge (preferred) or rebase merge

## Coding Standards

### Python Style

- **PEP 8** compliance (enforced by Ruff)
- **Type hints** for all public functions and methods
- **Docstrings** for all public modules, classes, and functions (Google style)
- **Line length**: 100 characters (Ruff default)

### Architecture Principles

Follow the boundaries defined in [architecture.md](../architecture.md):

| Layer | Responsibility |
|-------|----------------|
| `core/` | Pure business logic, no I/O side effects |
| `commands_typer/` | CLI interface only, delegates to core |
| `resources/` | Packaged templates and skills (source of truth) |

### Key Invariants (Never Break These)

1. **Atomic writes**: All file modifications use `atomic_write()`
2. **Baseline integrity**: `.airoom-baseline.json` logic preserved exactly
3. **Symlink safety**: Reject symlinked destinations, treat links as opaque
4. **Project boundary**: All paths validated with `project.assert_safe()`
5. **Registry schema version**: Remains `1`
6. **No user data deletion**: Never delete user files or artifacts

### Dependencies

Only these dependencies are allowed (no additions without approval):

- `typer` - CLI framework
- `rich` - Terminal formatting
- `ruamel.yaml` (via `pyyaml` transitive) - YAML round-trip parsing

### Commit Messages

Follow conventional commits:

```
type(scope): brief description

Longer explanation if needed.

Fixes #issue-number
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`

Examples:
```
feat(cli): add --json flag to status command
fix(registry): handle missing version field in parse_registry
docs: update CLI reference with new organize options
test(core): add baseline conflict detection tests
```

## Adding New Commands

1. Create `src/airoom/commands_typer/<command>.py`
2. Follow existing patterns (see `status.py`, `doctor.py`)
3. Register in `src/airoom/cli.py`
4. Add tests in `tests/test_cli_typer_<command>.py`
5. Update `docs/cli-reference.md` (auto-generate or manual)
6. Update `README.md` command list

## Adding New Skills

1. Create `src/airoom/resources/skills/<skill-name>/SKILL.md`
2. Follow [safe-management/SKILL.md](../src/airoom/resources/skills/safe-management/SKILL.md)
3. Register in `ResourceManager.list_packaged_skills()`
4. Test with `airoom init` and `airoom update`

## Updating Packaged Resources

Resources in `src/airoom/resources/templates/` and `src/airoom/resources/skills/` are the source of truth. Changes here affect:

- `airoom init` (new projects)
- `airoom update` (existing projects, baseline-aware)

Test with a fresh project:

```bash
mkdir /tmp/test-project && cd /tmp/test-project
airoom init
airoom update
```

## Debugging

### Verbose Output

```bash
airoom -vvv <command>  # Maximum verbosity
```

### Dry Run

```bash
airoom <command> --dry-run  # Preview without writing
```

### JSON Output

```bash
airoom <command> --json  # Machine-readable output
```

## Getting Help

- Check existing issues and PRs
- Read [architecture.md](../architecture.md) for design context
- Ask in discussions or open a new issue

## License

By contributing, you agree that your contributions will be licensed under the MIT License (see [LICENSE](../LICENSE)).