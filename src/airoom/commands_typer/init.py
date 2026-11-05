"""AIroom init command implementation (Typer-based)."""

import hashlib
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from airoom import __version__
from airoom.core.atomic import atomic_write
from airoom.core.baseline import BaselineManager
from airoom.core.project import Project, find_project_root
from airoom.core.registry import RegistryManager
from airoom.core.resources import ResourceManager
from airoom.core.version import write_version_file

console = Console()

# Markers for the AIroom section in AGENTS.md
AIROOM_START = "<!-- AIROOM:START -->"
AIROOM_END = "<!-- AIROOM:END -->"

_resource_manager = ResourceManager()


def get_resource_path(relative_path: str) -> Path:
    """Get the path to a packaged resource (delegates to ResourceManager)."""
    return _resource_manager.get_resource_path(relative_path)


def read_resource(relative_path: str) -> str:
    """Read a packaged resource file (delegates to ResourceManager)."""
    return _resource_manager.read_resource(relative_path)


def list_packaged_skills() -> list[str]:
    """List all skill names packaged with AIroom (delegates to ResourceManager)."""
    return _resource_manager.list_packaged_skills()


def list_packaged_templates() -> list[str]:
    """List all template names packaged with AIroom (delegates to ResourceManager)."""
    return _resource_manager.list_packaged_templates()


def create_directory(path: Path, verbose: bool = True) -> bool:
    """Create a directory if it doesn't exist.

    Returns True if created, False if already existed.
    """
    if path.exists():
        if path.is_dir():
            if verbose:
                console.print(f"  Directory already exists: {path}")
            return False
        else:
            raise FileExistsError(f"Path exists but is not a directory: {path}")
    try:
        path.mkdir(parents=True, exist_ok=False)
        if verbose:
            console.print(f"  Created directory: {path}")
        return True
    except PermissionError as e:
        raise PermissionError(f"Cannot create directory {path}: {e}") from e


def copy_file_if_missing(src: Path, dst: Path, verbose: bool = True) -> bool:
    """Copy a file if destination doesn't exist.

    Returns True if copied, False if already existed.
    """
    if dst.exists():
        if verbose:
            console.print(f"  File already exists (skipped): {dst}")
        return False
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(dst, src.read_text(encoding="utf-8"), expected_absent=True)
        if verbose:
            console.print(f"  Created file: {dst}")
        return True
    except PermissionError as e:
        raise PermissionError(f"Cannot create file {dst}: {e}") from e


def write_file_if_missing(path: Path, content: str, verbose: bool = True) -> bool:
    """Write a file if it doesn't exist.

    Returns True if written, False if already existed.
    """
    if path.exists():
        if verbose:
            console.print(f"  File already exists (skipped): {path}")
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, content, expected_absent=True)
        if verbose:
            console.print(f"  Created file: {path}")
        return True
    except PermissionError as e:
        raise PermissionError(f"Cannot write file {path}: {e}") from e


def update_agents_md(
    agents_path: Path,
    airoom_section: str,
    verbose: bool = True,
    replace_existing: bool = True,
    expected_content: str | None = None,
) -> bool:
    """Update or insert the AIroom section in AGENTS.md.

    Returns True if modified, False if unchanged.
    """
    if agents_path.exists():
        content = agents_path.read_text(encoding="utf-8")
        if expected_content is not None and content != expected_content:
            raise ValueError(f"Concurrent modification detected: {agents_path}")

        # Check if AIroom section already exists
        if content.count(AIROOM_START) > 1 or content.count(AIROOM_END) > 1:
            raise ValueError("AGENTS.md contains duplicate AIroom markers; refusing to edit it")
        start_idx = content.find(AIROOM_START)
        end_idx = content.find(AIROOM_END)
        if (start_idx == -1) != (end_idx == -1) or (end_idx != -1 and end_idx < start_idx):
            raise ValueError("AGENTS.md contains incomplete or misordered AIroom markers")

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            if not replace_existing:
                if verbose:
                    console.print("  Existing AIroom section preserved in AGENTS.md")
                return False
            # Section exists - check if content is different
            end_marker_end = end_idx + len(AIROOM_END)
            existing_section = content[start_idx:end_marker_end]

            if existing_section.strip() == airoom_section.strip():
                if verbose:
                    console.print("  AIroom section in AGENTS.md is up to date")
                return False
            else:
                # Replace the existing section
                new_content = content[:start_idx] + airoom_section + content[end_marker_end:]
                atomic_write(agents_path, new_content, expected_text=content)
                if verbose:
                    console.print(f"  Updated AIroom section in: {agents_path}")
                return True
        else:
            # No section exists - append to end of file
            original_content = content
            if content and not content.endswith("\n"):
                content += "\n"
            new_content = content + "\n" + airoom_section + "\n"
            atomic_write(agents_path, new_content, expected_text=original_content)
            if verbose:
                console.print(f"  Added AIroom section to: {agents_path}")
            return True
    else:
        # File doesn't exist - create it with just the AIroom section
        atomic_write(agents_path, airoom_section + "\n", expected_absent=True)
        if verbose:
            console.print(f"  Created AGENTS.md with AIroom section: {agents_path}")
        return True


init_app = typer.Typer(name="init", help="Initialize AIroom in a project")


@init_app.callback(invoke_without_command=True)
def init(
    ctx: typer.Context,
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory (default: current directory)"),
    ] = None,
    verbose: Annotated[
        int,
        typer.Option("--verbose", "-v", count=True, help="Increase verbosity"),
    ] = 0,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing"),
    ] = False,
) -> None:
    """Initialize AIroom in a project."""
    # Get global options from context
    global_opts = ctx.obj

    # Use global options if local not explicitly set
    project_path = path if path is not None else (global_opts.path if global_opts else None)
    verbose = verbose if verbose > 0 else (global_opts.verbose if global_opts else 0)
    json_output = json_output or (global_opts.json_output if global_opts else False)
    dry_run = dry_run or (global_opts.dry_run if global_opts else False)

    if dry_run:
        from airoom.core.logging import get_logger

        log = get_logger(__name__)
        log.info("Dry run: skipping init")
        console.print("[yellow]Dry run:[/yellow] Would initialize AIroom in project")
        raise typer.Exit(0)

    # Determine project root
    try:
        project_root = find_project_root(project_path)
        project = Project(project_root)

        # Validate all target paths are safe
        targets = (
            project.airoom_dir,
            project.skills_dir,
            project.artifacts_dir,
            project.registry_path,
            project.airoom_md_path,
            project.version_path,
            project.baseline_path,
            project.agents_path,
        )
        for target in targets:
            project.assert_safe(target)

        # Also validate skill files
        packaged_skills = list_packaged_skills()
        for skill_name in packaged_skills:
            project.assert_safe(project.skills_dir / skill_name / "SKILL.md")

        if verbose:
            console.print(f"Initializing AIroom in: {project_root}")

        # 1. Create airoom/ directory
        create_directory(project.airoom_dir, verbose=verbose)

        # 2. Create skills/ subdirectories and copy skill files
        create_directory(project.skills_dir, verbose=verbose)

        for skill_name in packaged_skills:
            skill_dir = project.skills_dir / skill_name
            create_directory(skill_dir, verbose=verbose)

            # Copy SKILL.md from packaged resources
            src_skill = get_resource_path(f"skills/{skill_name}/SKILL.md")
            dst_skill = skill_dir / "SKILL.md"
            copy_file_if_missing(src_skill, dst_skill, verbose=verbose)

        # 3. Create artifacts/ directory
        create_directory(project.artifacts_dir, verbose=verbose)

        # 4. Initialize registry.yaml from template (only if missing)
        registry_template = read_resource("templates/registry.yaml")
        if not project.registry_path.exists():
            # Validate template
            RegistryManager(project).write({"version": 1, "artifacts": {}, "tools": {}})
            write_file_if_missing(project.registry_path, registry_template, verbose=verbose)
        # Existing registries are user data. Init leaves them untouched; update
        # validates them before any schema mutation.

        # 5. Create AIROOM.md from template (only if missing)
        airoom_md_template = read_resource("templates/AIROOM.md")
        write_file_if_missing(project.airoom_md_path, airoom_md_template, verbose=verbose)

        # 6. Update or create AGENTS.md with AIroom section
        agents_path = project.agents_path
        airoom_section = read_resource("templates/AGENTS.md")
        update_agents_md(agents_path, airoom_section, verbose=verbose, replace_existing=False)

        # 7. Create baseline for resources that exactly match what init installed
        baseline: dict[str, str] = {}
        for skill_name in packaged_skills:
            relpath = f"skills/{skill_name}/SKILL.md"
            installed = project.airoom_dir / relpath
            bundled = get_resource_path(relpath)
            if installed.is_file() and installed.read_bytes() == bundled.read_bytes():
                baseline[relpath] = hashlib.sha256(installed.read_bytes()).hexdigest()
        for relpath in ("AIROOM.md",):
            installed = project.airoom_dir / relpath
            bundled = get_resource_path("templates/" + relpath)
            if installed.is_file() and installed.read_bytes() == bundled.read_bytes():
                baseline[relpath] = hashlib.sha256(installed.read_bytes()).hexdigest()
        agents_content = agents_path.read_text(encoding="utf-8")
        start_idx = agents_content.find(AIROOM_START)
        end_idx = agents_content.find(AIROOM_END)
        if start_idx != -1 and end_idx > start_idx:
            section = agents_content[start_idx : end_idx + len(AIROOM_END)]
            bundled_section = read_resource("templates/AGENTS.md").strip()
            if section.strip() == bundled_section:
                baseline["AGENTS.md#airoom-section"] = hashlib.sha256(
                    section.encode("utf-8")
                ).hexdigest()
        if not project.baseline_path.exists() and baseline:
            baseline_manager = BaselineManager(project)
            baseline_manager.write(baseline)

        # 8. Version is written last: its presence indicates project resources initialized
        write_version_file(project.version_path, __version__)

        if verbose:
            console.print("\n[green]AIroom initialization complete![/green]")
            console.print(f"  Project root: {project_root}")
            console.print(f"  AIroom directory: {project.airoom_dir}")
            console.print(f"  Version: {__version__}")

    except FileExistsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except PermissionError as e:
        console.print(f"[red]Permission error:[/red] {e}")
        raise typer.Exit(1)
    except (NotADirectoryError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(1)


__all__ = ["init", "AIROOM_START", "AIROOM_END", "init_app"]
