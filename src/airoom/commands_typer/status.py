"""AIroom status command implementation (Typer-based)."""

import json
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from airoom import __version__
from airoom.commands_typer.init import AIROOM_START, AIROOM_END
from airoom.core.baseline import BaselineManager
from airoom.core.project import Project
from airoom.core.registry import RegistryManager
from airoom.core.resources import ResourceManager
from airoom.core.version import get_installed_version, read_version_file

console = Console()

status_app = typer.Typer(name="status", help="Show project health summary.")


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


def _check_version(project: Project) -> dict:
    """Check version consistency between installed and project."""
    installed_version = get_installed_version()
    project_version = read_version_file(project.version_path)
    
    if not project_version:
        return {
            "status": "missing",
            "details": "Project version file (.airoom-version) not found. Run 'airoom init' to initialize."
        }
    
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


def _check_baseline(project: Project, baseline_manager: BaselineManager) -> dict:
    """Verify baseline integrity - all tracked resources match their hashes."""
    try:
        baseline = baseline_manager.read()
    except Exception as e:
        return {
            "status": "error",
            "details": f"Failed to read baseline: {e}"
        }
    
    if not baseline:
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
        
        import hashlib
        actual_hash = hashlib.sha256(actual_content).hexdigest()
        if actual_hash != expected_hash:
            mismatches.append(relpath)
    
    if mismatches or missing_files:
        details = []
        if mismatches:
            details.append(f"Modified: {', '.join(mismatches)}")
        if missing_files:
            details.append(f"Missing: {', '.join(missing_files)}")
        return {
            "status": "mismatch",
            "details": "; ".join(details)
        }
    
    return {
        "status": "ok",
        "details": f"All {len(baseline)} tracked resources verified"
    }


def _check_registry(project: Project, registry_manager: RegistryManager) -> dict:
    """Validate registry schema and file existence."""
    try:
        is_valid, errors = registry_manager.validate()
    except Exception as e:
        return {
            "status": "error",
            "details": f"Registry validation failed: {e}"
        }
    
    if not is_valid:
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
        management = entry.get("management")
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
    
    return {
        "status": "ok",
        "details": f"All {len([a for a in artifacts.values() if a.get('status') == 'active'])} active artifacts present"
    }


def _check_tools(project: Project, registry_manager: RegistryManager) -> dict:
    """Check tool configurations from registry."""
    try:
        registry = registry_manager.read()
    except Exception as e:
        return {
            "status": "error",
            "details": f"Failed to read registry: {e}"
        }
    
    tools = registry.get("tools", {})
    if not tools:
        return {
            "status": "ok",
            "details": "No tools registered"
        }
    
    active_tools = []
    for tool_id, entry in tools.items():
        if entry.get("status") != "active":
            continue
        name = entry.get("name", tool_id)
        config_path = entry.get("config_path")
        runtime_path = entry.get("runtime_path")
        details = [f"{tool_id}: {name}"]
        if config_path:
            details.append(f"config={config_path}")
        if runtime_path:
            details.append(f"runtime={runtime_path}")
        active_tools.append("; ".join(details))
    
    if not active_tools:
        return {
            "status": "ok",
            "details": "No active tools configured"
        }
    
    return {
        "status": "ok",
        "details": f"Active tools: {len(active_tools)}; " + "; ".join(active_tools)
    }


def _run_all_checks(project: Project) -> dict:
    """Run all health checks and return structured results."""
    baseline_manager = BaselineManager(project)
    registry_manager = RegistryManager(project)
    
    return {
        "version": _check_version(project),
        "baseline": _check_baseline(project, baseline_manager),
        "registry": _check_registry(project, registry_manager),
        "artifacts": _check_artifacts(project, registry_manager),
        "tools": _check_tools(project, registry_manager),
    }


def _render_human(results: dict) -> None:
    """Render results as a Rich table."""
    table = Table(title="AIroom Project Health Summary", show_header=True, header_style="bold")
    table.add_column("Check", style="cyan", width=20)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Details", style="dim")
    
    status_icons = {
        "ok": "✓",
        "missing": "✗",
        "mismatch": "✗",
        "invalid": "✗",
        "error": "✗",
    }
    
    status_colors = {
        "ok": "green",
        "missing": "red",
        "mismatch": "red",
        "invalid": "red",
        "error": "red",
    }
    
    for check_name, result in results.items():
        status = result["status"]
        icon = status_icons.get(status, "?")
        color = status_colors.get(status, "white")
        table.add_row(
            check_name.capitalize(),
            f"[{color}]{icon} {status}[/{color}]",
            result["details"]
        )
    
    console.print(table)


def _render_json(results: dict) -> None:
    """Render results as JSON."""
    import sys
    print(json.dumps(results, indent=2))


@status_app.command()
def status(
    ctx: typer.Context,
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
) -> None:
    """Show project health summary."""
    # Use global --json flag if local --json not explicitly set
    global_opts = ctx.obj
    if global_opts and global_opts.json_output and not json_output:
        json_output = True
    
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
    
    results = _run_all_checks(project)
    
    if json_output:
        _render_json(results)
    else:
        _render_human(results)
    
    # Always exit 0 for health checks - status is in the output
    # Only exit non-zero for fatal errors (handled above)