"""AIroom doctor command implementation (Typer-based)."""

import json
import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from airoom import __version__
from airoom.commands_typer.init import AIROOM_START, AIROOM_END
from airoom.core.atomic import atomic_write, compute_file_hash, AtomicWriteError
from airoom.core.baseline import BaselineManager, compute_file_hash_from_bytes
from airoom.core.discovery import DiscoveryEngine
from airoom.core.project import Project
from airoom.core.registry import RegistryManager, parse_registry, dump_registry, RegistryError
from airoom.core.resources import ResourceManager
from airoom.core.version import get_installed_version, write_version_file

console = Console()

doctor_app = typer.Typer(name="doctor", help="Diagnose and repair common issues.")


def _get_project(ctx: typer.Context, path: Optional[Path] = None) -> Project:
    """Get project from context or path argument."""
    project_path = path
    if project_path is None:
        global_opts = ctx.obj
        if global_opts and global_opts.path:
            project_path = global_opts.path
    if project_path is None:
        project_path = Path.cwd()
    return Project(project_path)


def _check_version(project: Project, fix: bool = False, dry_run: bool = False) -> dict:
    """Check version consistency between installed and project."""
    installed_version = get_installed_version()
    version_path = project.version_path
    
    if not version_path.exists():
        if fix and not dry_run:
            try:
                write_version_file(version_path, installed_version)
                return {
                    "status": "ok",
                    "details": f"Recreated .airoom-version with version {installed_version}"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "details": f"Failed to recreate version file: {e}"
                }
        return {
            "status": "missing",
            "details": "Project version file (.airoom-version) not found. Run 'airoom init' or 'airoom doctor --fix' to recreate."
        }
    
    project_version = version_path.read_text(encoding="utf-8").strip()
    
    if installed_version == project_version:
        return {
            "status": "ok",
            "details": f"Version {installed_version} (match)"
        }
    else:
        return {
            "status": "mismatch",
            "details": f"Installed: {installed_version}, Project: {project_version}"
        }


def _check_baseline(project: Project, baseline_manager: BaselineManager, fix: bool = False, dry_run: bool = False) -> dict:
    """Verify baseline integrity - all tracked resources match their hashes."""
    # Check if baseline file exists
    if not project.baseline_path.exists():
        if fix and not dry_run:
            try:
                _recreate_baseline(project, baseline_manager)
                return {
                    "status": "ok",
                    "details": "Recreated missing .airoom-baseline.json from current resources"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "details": f"Failed to recreate baseline: {e}"
                }
        return {
            "status": "missing",
            "details": "Baseline file (.airoom-baseline.json) not found. Run 'airoom doctor --fix' to recreate."
        }
    
    try:
        baseline = baseline_manager.read()
    except Exception as e:
        return {
            "status": "error",
            "details": f"Failed to read baseline: {e}"
        }
    
    if not baseline:
        # Empty baseline - if fix, recreate from current state
        if fix and not dry_run:
            try:
                _recreate_baseline(project, baseline_manager)
                return {
                    "status": "ok",
                    "details": "Recreated empty baseline from current resources"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "details": f"Failed to recreate baseline: {e}"
                }
        return {
            "status": "ok",
            "details": "No baseline entries (empty baseline)"
        }
    
    mismatches = []
    missing_files = []
    
    for relpath, expected_hash in baseline.items():
        # Handle special AGENTS.md section entry
        if relpath == "AGENTS.md#airoom-section":
            agents_path = project.root / "AGENTS.md"
            if not agents_path.exists():
                missing_files.append(relpath)
                continue
            # Read the AIroom section
            content = agents_path.read_text(encoding="utf-8")
            start_idx = content.find(AIROOM_START)
            end_idx = content.find(AIROOM_END)
            if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
                missing_files.append(relpath)
                continue
            section = content[start_idx:end_idx + len(AIROOM_END)]
            actual_content = section.encode("utf-8")
        else:
            # Baseline paths are relative to the airoom directory
            file_path = project.airoom_dir / relpath
            if not file_path.exists() or not file_path.is_file():
                missing_files.append(relpath)
                continue
            actual_content = file_path.read_bytes()
        
        actual_hash = compute_file_hash_from_bytes(actual_content)
        if actual_hash != expected_hash:
            mismatches.append(relpath)
    
    if missing_files:
        # Missing files tracked in baseline
        if fix and not dry_run:
            try:
                _recreate_baseline(project, baseline_manager)
                return {
                    "status": "ok",
                    "details": f"Recreated baseline after {len(missing_files)} missing file(s)"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "details": f"Failed to recreate baseline: {e}"
                }
        details = f"Missing tracked files: {', '.join(missing_files)}"
        return {
            "status": "missing",
            "details": details
        }
    
    if mismatches:
        # User-modified files - DO NOT auto-fix
        details = f"Modified (user changes preserved): {', '.join(mismatches)}"
        return {
            "status": "mismatch",
            "details": details
        }
    
    return {
        "status": "ok",
        "details": f"All {len(baseline)} tracked resources verified"
    }


def _recreate_baseline(project: Project, baseline_manager: BaselineManager) -> None:
    """Recreate baseline from current state of installed resources."""
    baseline = {}
    resource_manager = ResourceManager()
    
    # Skills
    for skill_name in resource_manager.list_packaged_skills():
        relpath = f"skills/{skill_name}/SKILL.md"
        installed = project.airoom_dir / relpath
        bundled = resource_manager.get_resource_path(relpath)
        if installed.is_file() and installed.read_bytes() == bundled.read_bytes():
            baseline[relpath] = compute_file_hash_from_bytes(installed.read_bytes())
    
    # AIROOM.md
    for relpath in ("AIROOM.md",):
        installed = project.airoom_dir / relpath
        bundled = resource_manager.get_resource_path("templates/" + relpath)
        if installed.is_file() and installed.read_bytes() == bundled.read_bytes():
            baseline[relpath] = compute_file_hash_from_bytes(installed.read_bytes())
    
    # AGENTS.md section
    agents_path = project.root / "AGENTS.md"
    if agents_path.exists():
        content = agents_path.read_text(encoding="utf-8")
        start_idx = content.find(AIROOM_START)
        end_idx = content.find(AIROOM_END)
        if start_idx != -1 and end_idx > start_idx:
            section = content[start_idx:end_idx + len(AIROOM_END)]
            bundled_section = resource_manager.read_resource("templates/AGENTS.md").strip()
            if section.strip() == bundled_section:
                baseline["AGENTS.md#airoom-section"] = compute_file_hash_from_bytes(section.encode("utf-8"))
    
    baseline_manager.write(baseline)


def _check_registry(project: Project, registry_manager: RegistryManager, fix: bool = False, dry_run: bool = False) -> dict:
    """Validate registry schema and file existence."""
    try:
        is_valid, errors = registry_manager.validate()
    except Exception as e:
        return {
            "status": "error",
            "details": f"Registry validation failed: {e}"
        }
    
    if not is_valid:
        if fix and not dry_run:
            try:
                # Recreate registry from template
                resource_manager = ResourceManager()
                template = resource_manager.read_resource("templates/registry.yaml")
                template_data = parse_registry(template)
                registry_manager.write(template_data)
                return {
                    "status": "ok",
                    "details": "Recreated registry from template (invalid entries removed)"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "details": f"Failed to fix registry: {e}"
                }
        return {
            "status": "invalid",
            "details": "; ".join(errors)
        }
    
    return {
        "status": "ok",
        "details": "Registry schema valid"
    }


def _check_artifacts(project: Project, registry_manager: RegistryManager) -> dict:
    """Check that all artifacts in registry exist on disk."""
    try:
        registry = registry_manager.read()
    except Exception as e:
        return {
            "status": "error",
            "details": f"Failed to read registry: {e}"
        }
    
    artifacts = registry.get("artifacts", {})
    if not artifacts:
        return {
            "status": "ok",
            "details": "No artifacts registered"
        }
    
    missing = []
    for artifact_id, entry in artifacts.items():
        if entry.get("status") != "active":
            continue
        path = entry.get("path")
        if not path:
            missing.append(f"{artifact_id}: no path")
            continue
        
        full_path = project.root / path
        if not full_path.exists():
            missing.append(f"{artifact_id} ({path})")
    
    if missing:
        return {
            "status": "missing",
            "details": f"Missing artifacts: {', '.join(missing)}"
        }
    
    active_count = len([a for a in artifacts.values() if a.get("status") == "active"])
    return {
        "status": "ok",
        "details": f"All {active_count} active artifacts present"
    }


def _check_symlinks(project: Project) -> dict:
    """Check for symlinks in the airoom directory."""
    if not project.airoom_dir.exists():
        return {
            "status": "ok",
            "details": "AIroom directory does not exist"
        }
    
    symlinks = []
    
    def check_symlinks_recursive(path: Path):
        try:
            for entry in path.iterdir():
                if entry.is_symlink():
                    rel_path = entry.relative_to(project.airoom_dir)
                    symlinks.append(str(rel_path))
                elif entry.is_dir() and not entry.is_symlink():
                    check_symlinks_recursive(entry)
        except (PermissionError, OSError):
            pass
    
    check_symlinks_recursive(project.airoom_dir)
    
    if symlinks:
        return {
            "status": "found",
            "details": f"Symlinks found: {', '.join(symlinks)}"
        }
    
    return {
        "status": "ok",
        "details": "No symlinks in airoom/ directory"
    }


def _check_boundary(project: Project, registry_manager: RegistryManager) -> dict:
    """Check for path boundary violations in registry."""
    # Read raw registry without validation to catch boundary violations
    from ruamel.yaml import YAML
    def _yaml() -> YAML:
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.indent(mapping=2, sequence=4, offset=2)
        return yaml
    
    if not registry_manager.registry_path.exists():
        return {
            "status": "ok",
            "details": "No registry file"
        }
    
    try:
        text = registry_manager.registry_path.read_text(encoding="utf-8")
        registry = _yaml().load(text) or {"version": 1, "artifacts": {}, "tools": {}}
    except Exception as e:
        return {
            "status": "error",
            "details": f"Failed to read registry: {e}"
        }
    
    violations = []
    artifacts = registry.get("artifacts", {})
    
    for artifact_id, entry in artifacts.items():
        path = entry.get("path", "")
        if not path:
            continue
        
        # Check for absolute paths
        if path.startswith("/") or "\\" in path:
            violations.append(f"{artifact_id}: absolute or Windows-style path '{path}'")
            continue
        
        # Check for directory traversal
        if ".." in Path(path).parts:
            violations.append(f"{artifact_id}: path traversal in '{path}'")
            continue
        
        # Check that managed artifacts are under airoom/artifacts/
        if entry.get("management") == "managed" and not path.startswith("airoom/artifacts/"):
            violations.append(f"{artifact_id}: managed artifact not under airoom/artifacts/ ('{path}')")
    
    if violations:
        return {
            "status": "violation",
            "details": "; ".join(violations)
        }
    
    return {
        "status": "ok",
        "details": "All artifact paths respect project boundaries"
    }


def _check_orphaned_skills(project: Project) -> dict:
    """Check for skills in project but not in packaged resources."""
    if not project.skills_dir.exists():
        return {
            "status": "ok",
            "details": "No skills directory"
        }
    
    resource_manager = ResourceManager()
    packaged_skills = set(resource_manager.list_packaged_skills())
    
    orphaned = []
    try:
        for entry in project.skills_dir.iterdir():
            if entry.is_dir() and entry.name not in packaged_skills:
                skill_file = entry / "SKILL.md"
                if skill_file.exists():
                    orphaned.append(entry.name)
    except (PermissionError, OSError):
        pass
    
    if orphaned:
        return {
            "status": "found",
            "details": f"Orphaned skills (not packaged): {', '.join(orphaned)}"
        }
    
    return {
        "status": "ok",
        "details": "No orphaned skills"
    }


def _ensure_airoom_structure(project: Project) -> list[str]:
    """Ensure airoom directory structure exists. Returns list of created paths."""
    created = []
    for subdir in ("skills", "artifacts"):
        path = project.airoom_dir / subdir
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(str(path.relative_to(project.root)))
    return created


def _run_all_checks(project: Project, fix: bool = False, dry_run: bool = False) -> dict:
    """Run all health checks and return structured results."""
    baseline_manager = BaselineManager(project)
    registry_manager = RegistryManager(project)
    
    # Ensure directory structure if fixing
    if fix and not dry_run:
        _ensure_airoom_structure(project)
    
    return {
        "version": _check_version(project, fix, dry_run),
        "baseline": _check_baseline(project, baseline_manager, fix, dry_run),
        "registry": _check_registry(project, registry_manager, fix, dry_run),
        "artifacts": _check_artifacts(project, registry_manager),
        "symlinks": _check_symlinks(project),
        "boundary": _check_boundary(project, registry_manager),
        "orphaned_skills": _check_orphaned_skills(project),
    }


def _render_human(results: dict) -> None:
    """Render results as a Rich table."""
    table = Table(title="AIroom Doctor Diagnostics", show_header=True, header_style="bold")
    table.add_column("Check", style="cyan", width=20)
    table.add_column("Status", justify="center", width=12)
    table.add_column("Details", style="dim")
    
    status_icons = {
        "ok": "✓",
        "missing": "✗",
        "mismatch": "✗",
        "invalid": "✗",
        "error": "✗",
        "found": "⚠",
        "violation": "✗",
    }
    
    status_colors = {
        "ok": "green",
        "missing": "red",
        "mismatch": "red",
        "invalid": "red",
        "error": "red",
        "found": "yellow",
        "violation": "red",
    }
    
    for check_name, result in results.items():
        status = result["status"]
        icon = status_icons.get(status, "?")
        color = status_colors.get(status, "white")
        table.add_row(
            check_name.replace("_", " ").capitalize(),
            f"[{color}]{icon} {status}[/{color}]",
            result["details"]
        )
    
    console.print(table)


def _render_json(results: dict) -> None:
    """Render results as JSON."""
    print(json.dumps(results, indent=2))


@doctor_app.command()
def doctor(
    ctx: typer.Context,
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Attempt safe repairs (recreate missing files/dirs from baseline)"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
) -> None:
    """Diagnose and repair common issues."""
    # Use global --json flag if local --json not explicitly set
    global_opts = ctx.obj
    if global_opts and global_opts.json_output and not json_output:
        json_output = True
    
    # Get dry_run from global options
    dry_run = global_opts.dry_run if global_opts else False
    
    project = _get_project(ctx, path)
    
    # Verify project has been initialized
    if not project.airoom_dir.exists():
        if json_output:
            print(json.dumps({
                "error": "Project not initialized",
                "details": f"AIroom directory not found at {project.airoom_dir}. Run 'airoom init' first."
            }, indent=2))
        else:
            console.print(f"[red]Error:[/red] Project not initialized at {project.root}")
            console.print("Run 'airoom init' to initialize AIroom in this project.")
        raise typer.Exit(1)
    
    results = _run_all_checks(project, fix=fix, dry_run=dry_run)
    
    if json_output:
        _render_json(results)
    else:
        _render_human(results)
    
    # Exit 0 for diagnostics - status is in the output
    # Only exit non-zero for fatal errors (handled above)