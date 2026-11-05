"""AIroom update command implementation (Typer-based)."""

import hashlib
import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from airoom import __version__
from airoom.core.atomic import atomic_write, compute_file_hash, AtomicWriteError
from airoom.core.baseline import BaselineManager
from airoom.core.project import Project, assert_safe_project_path, find_project_root
from airoom.core.registry import RegistryManager, parse_registry, dump_registry
from airoom.core.resources import ResourceManager
from airoom.core.version import read_version_file, write_version_file
from airoom.core.logging import get_logger

console = Console()
log = get_logger(__name__)

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


def update_skill(
    skill_name: str,
    project_skills_dir: Path,
    verbose: bool = True,
    baseline_hash: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Update a single skill directory.

    Returns a dict with keys: 'status' (updated|added|skipped|conflict|error), 'message', 'details'
    """
    src_skill = get_resource_path(f"skills/{skill_name}/SKILL.md")
    skill_dir = project_skills_dir / skill_name
    dst_skill = skill_dir / "SKILL.md"

    if not src_skill.exists():
        return {"status": "skipped", "message": f"Packaged skill not found: {skill_name}"}

    if not skill_dir.exists():
        # New skill - add it
        if dry_run:
            if verbose:
                console.print(f"  [yellow]Dry run:[/yellow] Would add new skill: {skill_name}")
            return {"status": "added", "message": f"Would add new skill: {skill_name}"}
        try:
            skill_dir.mkdir(parents=True, exist_ok=True)
            atomic_write(dst_skill, src_skill.read_text(encoding="utf-8"), expected_absent=True)
            if verbose:
                console.print(f"  Added skill: {skill_name}")
            return {"status": "added", "message": f"Added new skill: {skill_name}"}
        except PermissionError as e:
            return {
                "status": "error",
                "message": f"Permission error adding skill {skill_name}: {e}",
            }
        except Exception as e:
            return {"status": "error", "message": f"Error adding skill {skill_name}: {e}"}

    if not dst_skill.exists():
        # Skill directory exists but SKILL.md is missing - add it
        if dry_run:
            if verbose:
                console.print(f"  [yellow]Dry run:[/yellow] Would add missing SKILL.md for: {skill_name}")
            return {"status": "added", "message": f"Would add missing SKILL.md for: {skill_name}"}
        try:
            if baseline_hash is not None:
                return {
                    "status": "conflict",
                    "message": f"Previously installed skill is missing: {skill_name}",
                }
            atomic_write(dst_skill, src_skill.read_text(encoding="utf-8"), expected_absent=True)
            if verbose:
                console.print(f"  Added missing SKILL.md for: {skill_name}")
            return {"status": "added", "message": f"Added missing SKILL.md for: {skill_name}"}
        except Exception as e:
            return {"status": "error", "message": f"Error adding SKILL.md for {skill_name}: {e}"}

    # Skill exists - check if it was modified by user
    existing_content = dst_skill.read_text(encoding="utf-8")

    # Compare hashes to detect user modifications
    packaged_hash = compute_file_hash(src_skill)
    existing_hash = compute_file_hash(dst_skill)

    expected_hash = baseline_hash or packaged_hash
    if existing_hash == expected_hash:
        if existing_hash == packaged_hash:
            if verbose:
                console.print(f"  Skill already current: {skill_name}")
            return {"status": "skipped", "message": f"Skill already current: {skill_name}"}
        # Unchanged - update to latest
        if dry_run:
            if verbose:
                console.print(f"  [yellow]Dry run:[/yellow] Would update skill: {skill_name}")
            return {"status": "updated", "message": f"Would update skill: {skill_name}"}
        try:
            atomic_write(
                dst_skill, src_skill.read_text(encoding="utf-8"), expected_text=existing_content
            )
            if verbose:
                console.print(f"  Updated skill: {skill_name}")
            return {"status": "updated", "message": f"Updated skill: {skill_name}"}
        except Exception as e:
            return {"status": "error", "message": f"Error updating skill {skill_name}: {e}"}
    else:
        # Modified by user - conflict
        return {
            "status": "conflict",
            "message": f"Skill modified by user, not overwritten: {skill_name}",
            "details": "Run 'diff' to see differences",
        }


def update_registry(
    project_registry_path: Path,
    verbose: bool = True,
    dry_run: bool = False,
) -> dict:
    """Update registry.yaml with new defaults while preserving user data.

    Returns a dict with keys: 'status', 'message'
    """
    # Read and validate packaged template.
    try:
        packaged_content = read_resource("templates/registry.yaml")
    except Exception as e:
        return {"status": "error", "message": f"Failed to read packaged registry template: {e}"}

    if not project_registry_path.exists():
        # No existing registry - create from template
        if dry_run:
            if verbose:
                console.print("  [yellow]Dry run:[/yellow] Would create registry.yaml from template")
            return {"status": "added", "message": "Would create registry.yaml from template"}
        try:
            template_data = parse_registry(packaged_content)
            atomic_write(
                project_registry_path,
                dump_registry(template_data),
                expected_absent=True,
            )
            if verbose:
                console.print("  Created registry.yaml from template")
            return {"status": "added", "message": "Created registry.yaml from template"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to create registry.yaml: {e}"}

    # Round-trip parse preserves comments/unknown keys; duplicate keys are rejected.
    try:
        original_text = project_registry_path.read_text(encoding="utf-8")
        existing_data = parse_registry(original_text)
    except Exception as e:
        return {"status": "error", "message": f"Failed to read registry.yaml: {e}"}

    # Parse packaged template
    try:
        template_data = parse_registry(packaged_content)
    except Exception as e:
        return {"status": "error", "message": f"Invalid packaged registry template: {e}"}

    if existing_data is None:
        existing_data = {}

    if template_data is None:
        template_data = {}

    # Only merge schema containers/default metadata. The template intentionally has
    # no sample artifact entries, so updates never invent registrations.
    merged = False
    for key, value in template_data.items():
        if key not in existing_data:
            existing_data[key] = value
            merged = True
        elif isinstance(value, dict) and isinstance(existing_data[key], dict):
            continue

    if not merged:
        if verbose:
            console.print("  Registry already up to date")
        return {"status": "skipped", "message": "Registry already up to date"}

    if dry_run:
        if verbose:
            console.print("  [yellow]Dry run:[/yellow] Would add missing registry schema fields")
        return {"status": "updated", "message": "Would add missing registry schema fields"}

    try:
        # dump_registry validates again before serialization.
        updated_text = dump_registry(existing_data)
        atomic_write(project_registry_path, updated_text, expected_text=original_text)
        if verbose:
            console.print("  Added missing registry schema fields")
    except Exception as e:
        return {"status": "error", "message": f"Failed to update registry.yaml: {e}"}
    return {"status": "updated", "message": "Added missing registry schema fields"}


def update_agents_md(
    agents_path: Path,
    airoom_section: str,
    verbose: bool = True,
    replace_existing: bool = True,
    expected_content: str | None = None,
    dry_run: bool = False,
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
                if dry_run:
                    if verbose:
                        console.print("  [yellow]Dry run:[/yellow] Would update AIroom section in AGENTS.md")
                    return True
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
            if dry_run:
                if verbose:
                    console.print("  [yellow]Dry run:[/yellow] Would add AIroom section to AGENTS.md")
                return True
            atomic_write(agents_path, new_content, expected_text=original_content)
            if verbose:
                console.print(f"  Added AIroom section to: {agents_path}")
            return True
    else:
        # File doesn't exist - create it with just the AIroom section
        if dry_run:
            if verbose:
                console.print("  [yellow]Dry run:[/yellow] Would create AGENTS.md with AIroom section")
            return True
        atomic_write(agents_path, airoom_section + "\n", expected_absent=True)
        if verbose:
            console.print(f"  Created AGENTS.md with AIroom section: {agents_path}")
        return True


def update_agents_md_section(
    project_root: Path, verbose: bool = True, baseline_hash: str | None = None, dry_run: bool = False
) -> dict:
    """Update the AIroom section in root AGENTS.md.

    Returns a dict with keys: 'status', 'message'
    """
    agents_path = project_root / "AGENTS.md"
    try:
        airoom_section = read_resource("templates/AGENTS.md")
    except Exception as e:
        return {"status": "error", "message": f"Failed to read packaged AGENTS.md template: {e}"}

    try:
        current_content = None
        if agents_path.exists():
            content = agents_path.read_text(encoding="utf-8")
            current_content = content
            start = content.find(AIROOM_START)
            end = content.find(AIROOM_END)
            if start != -1 and end > start:
                section = content[start : end + len(AIROOM_END)]
                current_hash = hashlib.sha256(section.encode("utf-8")).hexdigest()
                packaged_hash = hashlib.sha256(airoom_section.strip().encode("utf-8")).hexdigest()
                if current_hash != (baseline_hash or packaged_hash):
                    return {
                        "status": "conflict",
                        "message": "AIroom section modified by user; preserved",
                    }
        modified = update_agents_md(
            agents_path,
            airoom_section,
            verbose=verbose,
            expected_content=current_content,
            dry_run=dry_run,
        )
        if modified:
            return {"status": "updated", "message": "Updated AIroom section in AGENTS.md"}
        else:
            return {
                "status": "skipped",
                "message": "AIroom section in AGENTS.md already up to date",
            }
    except Exception as e:
        return {"status": "error", "message": f"Failed to update AGENTS.md: {e}"}


def update_airoom_md(
    airoom_dir: Path, verbose: bool = True, baseline_hash: str | None = None, dry_run: bool = False
) -> dict:
    """Update AIROOM.md in the airoom directory.

    Returns a dict with keys: 'status', 'message'
    """
    airoom_md_path = airoom_dir / "AIROOM.md"
    try:
        airoom_md_template = read_resource("templates/AIROOM.md")
    except Exception as e:
        return {"status": "error", "message": f"Failed to read packaged AIROOM.md template: {e}"}

    if not airoom_md_path.exists():
        # File doesn't exist - create it
        if dry_run:
            if verbose:
                console.print(f"  [yellow]Dry run:[/yellow] Would create AIROOM.md from template")
            return {"status": "added", "message": "Would create AIROOM.md from template"}
        try:
            if baseline_hash is not None:
                return {
                    "status": "conflict",
                    "message": "Previously installed AIROOM.md is missing",
                }
            atomic_write(airoom_md_path, airoom_md_template, expected_absent=True)
            if verbose:
                console.print(f"  Created file: {airoom_md_path}")
            return {"status": "added", "message": "Created AIROOM.md from template"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to create AIROOM.md: {e}"}

    # File exists - check if it was modified by user
    packaged_content = airoom_md_template
    existing_content = airoom_md_path.read_text(encoding="utf-8")

    # Compare hashes to detect user modifications
    packaged_hash = compute_file_hash(get_resource_path("templates/AIROOM.md"))
    existing_hash = compute_file_hash(airoom_md_path)

    if existing_hash == (baseline_hash or packaged_hash):
        if existing_hash == packaged_hash:
            if verbose:
                console.print("  AIROOM.md already current")
            return {"status": "skipped", "message": "AIROOM.md already current"}
        # Unchanged - update to latest
        if dry_run:
            if verbose:
                console.print("  [yellow]Dry run:[/yellow] Would update AIROOM.md")
            return {"status": "updated", "message": "Would update AIROOM.md"}
        try:
            atomic_write(airoom_md_path, packaged_content, expected_text=existing_content)
            if verbose:
                console.print(f"  Updated file: {airoom_md_path}")
            return {"status": "updated", "message": "Updated AIROOM.md"}
        except Exception as e:
            return {"status": "error", "message": f"Error updating AIROOM.md: {e}"}
    else:
        # Modified by user - conflict
        return {
            "status": "conflict",
            "message": "AIROOM.md modified by user, not overwritten",
            "details": "Run 'diff' to see differences",
        }


def update(
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
    """Update AIroom project resources."""
    # Get global options from context
    global_opts = ctx.obj

    # Use global options if local not explicitly set
    project_path = path if path is not None else (global_opts.path if global_opts else None)
    verbose_level = verbose if verbose > 0 else (global_opts.verbose if global_opts else 0)
    json_output = json_output or (global_opts.json_output if global_opts else False)
    dry_run = dry_run or (global_opts.dry_run if global_opts else False)

    if dry_run:
        log.info("Dry run: skipping update")
        console.print("[yellow]Dry run:[/yellow] Would update project resources")
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
            project.version_path,
            project.baseline_path,
            project.airoom_md_path,
            project.agents_path,
        )
        for target in targets:
            project.assert_safe(target)

        # Also validate skill files
        packaged_skills = list_packaged_skills()
        for skill_name in packaged_skills:
            project.assert_safe(project.skills_dir / skill_name / "SKILL.md")

        if verbose_level > 0:
            console.print(f"Updating AIroom resources in: {project_root}")

    except (NotADirectoryError, ValueError) as e:
        if json_output:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Check if AIroom is initialized
    if project.airoom_dir.is_symlink() or not project.airoom_dir.exists() or not project.airoom_dir.is_dir():
        if json_output:
            print(json.dumps({"error": "AIroom not initialized in this project. Run 'airoom init' first."}, indent=2))
        else:
            console.print(
                "[red]Error:[/red] AIroom not initialized in this project. Run 'airoom init' first."
            )
        raise typer.Exit(1)

    installed_version = read_version_file(project.version_path)
    current_version = __version__

    if verbose_level > 0:
        console.print(f"  Installed version: {installed_version or 'unknown'}")
        console.print(f"  Current version:   {current_version}")

    if installed_version == current_version and verbose_level > 0:
        console.print("  Already at latest version.")
        console.print("  Checking for new resources...")

    # Read baseline
    baseline_manager = BaselineManager(project)
    try:
        baseline = baseline_manager.read()
    except (OSError, ValueError, json.JSONDecodeError) as e:
        if json_output:
            print(json.dumps({"error": f"Cannot read AIroom resource baseline: {e}"}, indent=2))
        else:
            console.print(f"[red]Error:[/red] Cannot read AIroom resource baseline: {e}")
        raise typer.Exit(1)

    # Read raw baseline text for concurrent modification detection
    if project.baseline_path.exists():
        baseline_text = project.baseline_path.read_text(encoding="utf-8")
    else:
        baseline_text = None

    # Track update results
    results = {
        "skills": [],
        "registry": None,
        "agents_md": None,
        "airoom_md": None,
        "errors": [],
        "conflicts": [],
    }

    # 1. Update skills
    if verbose_level > 0:
        console.print("\nUpdating skills...")

    if not project.skills_dir.exists():
        project.skills_dir.mkdir(parents=True, exist_ok=True)

    packaged_skills = list_packaged_skills()
    for skill_name in packaged_skills:
        relpath = f"skills/{skill_name}/SKILL.md"
        result = update_skill(
            skill_name,
            project.skills_dir,
            verbose=verbose_level > 0,
            baseline_hash=baseline.get(relpath),
            dry_run=dry_run,
        )
        results["skills"].append((skill_name, result))
        if result["status"] in ("added", "updated", "skipped") and not dry_run:
            skill_file = project.skills_dir / skill_name / "SKILL.md"
            if skill_file.exists():
                baseline[relpath] = compute_file_hash(skill_file)
        if result["status"] == "conflict":
            results["conflicts"].append(f"Skill: {skill_name}")
        elif result["status"] == "error":
            results["errors"].append(f"Skill {skill_name}: {result['message']}")

    # Check for skills that exist in project but not in package (user-created)
    if project.skills_dir.exists():
        for skill_dir in project.skills_dir.iterdir():
            if skill_dir.is_dir() and skill_dir.name not in packaged_skills:
                console.print(f"  Preserving user-created skill: {skill_dir.name}")

    # 2. Update registry.yaml
    if verbose_level > 0:
        console.print("\nUpdating registry...")
    registry_result = update_registry(project.registry_path, verbose=verbose_level > 0, dry_run=dry_run)
    results["registry"] = registry_result
    if registry_result["status"] == "error":
        results["errors"].append(f"Registry: {registry_result['message']}")

    # 3. Update AGENTS.md section
    if verbose_level > 0:
        console.print("\nUpdating AGENTS.md...")
    agents_result = update_agents_md_section(
        project.root, verbose=verbose_level > 0, baseline_hash=baseline.get("AGENTS.md#airoom-section"), dry_run=dry_run
    )
    results["agents_md"] = agents_result
    if agents_result["status"] == "error":
        results["errors"].append(f"AGENTS.md: {agents_result['message']}")
    elif agents_result["status"] == "conflict":
        results["conflicts"].append("AGENTS.md AIroom section")
    if agents_result["status"] in ("updated", "skipped") and not dry_run:
        content = project.agents_path.read_text(encoding="utf-8")
        start = content.find(AIROOM_START)
        end = content.find(AIROOM_END)
        if start != -1 and end > start:
            section = content[start : end + len(AIROOM_END)]
            baseline["AGENTS.md#airoom-section"] = hashlib.sha256(
                section.encode("utf-8")
            ).hexdigest()

    # 4. Update AIROOM.md
    if verbose_level > 0:
        console.print("\nUpdating AIROOM.md...")
    airoom_md_result = update_airoom_md(
        project.airoom_dir, verbose=verbose_level > 0, baseline_hash=baseline.get("AIROOM.md"), dry_run=dry_run
    )
    results["airoom_md"] = airoom_md_result
    if airoom_md_result["status"] == "error":
        results["errors"].append(f"AIROOM.md: {airoom_md_result['message']}")
    elif airoom_md_result["status"] == "conflict":
        results["conflicts"].append("AIROOM.md")
    if airoom_md_result["status"] in ("added", "updated", "skipped") and not dry_run:
        baseline["AIROOM.md"] = compute_file_hash(project.airoom_md_path)

    # Compute summary counts (needed for both JSON and human output, and exit code)
    updated_count = 0
    added_count = 0
    skipped_count = 0
    conflict_count = 0
    error_count = len(results["errors"])

    for skill_name, result in results["skills"]:
        status = result["status"]
        if status == "updated":
            updated_count += 1
        elif status == "added":
            added_count += 1
        elif status == "skipped":
            skipped_count += 1
        elif status == "conflict":
            conflict_count += 1

    if results["registry"]:
        status = results["registry"]["status"]
        if status == "updated":
            updated_count += 1
        elif status == "added":
            added_count += 1
        elif status == "skipped":
            skipped_count += 1
        elif status == "error":
            error_count += 1

    if results["agents_md"]:
        status = results["agents_md"]["status"]
        if status == "updated":
            updated_count += 1
        elif status == "skipped":
            skipped_count += 1
        elif status == "error":
            error_count += 1

    if results["airoom_md"]:
        status = results["airoom_md"]["status"]
        if status == "updated":
            updated_count += 1
        elif status == "added":
            added_count += 1
        elif status == "skipped":
            skipped_count += 1
        elif status == "conflict":
            conflict_count += 1
        elif status == "error":
            error_count += 1

    # Prepare output
    if json_output:
        # Convert skills list to dict format
        skills_dict = {}
        for skill_name, result in results["skills"]:
            skills_dict[skill_name] = result
        json_results = {
            "skills": skills_dict,
            "registry": results["registry"],
            "agents_md": results["agents_md"],
            "airoom_md": results["airoom_md"],
            "errors": results["errors"],
            "conflicts": results["conflicts"],
            "summary": {
                "updated": updated_count,
                "added": added_count,
                "skipped": skipped_count,
                "conflicts": conflict_count,
                "errors": error_count,
            },
        }
        print(json.dumps(json_results, indent=2))
    else:
        # Human-readable output (always show summary like legacy command)
        console.print("\n" + "=" * 50)
        console.print("Update Summary:")
        console.print("=" * 50)

        for skill_name, result in results["skills"]:
            status = result["status"]
            console.print(f"  Skill '{skill_name}': {status} - {result['message']}")

        if results["registry"]:
            status = results["registry"]["status"]
            console.print(f"  Registry: {status} - {results['registry']['message']}")

        if results["agents_md"]:
            status = results["agents_md"]["status"]
            console.print(f"  AGENTS.md: {status} - {results['agents_md']['message']}")

        if results["airoom_md"]:
            status = results["airoom_md"]["status"]
            console.print(f"  AIROOM.md: {status} - {results['airoom_md']['message']}")

        console.print(f"\n  Updated: {updated_count}")
        console.print(f"  Added:   {added_count}")
        console.print(f"  Skipped: {skipped_count}")
        console.print(f"  Conflicts: {conflict_count}")
        console.print(f"  Errors:  {error_count}")

    # Determine exit code
    has_errors = error_count > 0 or bool(results["conflicts"])

    # Persist per-resource baselines for resources successfully written. This
    # makes a partial update safely repeatable while conflicted resources retain
    # their prior hashes. The version marker still advances only on full success.
    if not dry_run:
        try:
            updated_baseline_text = json.dumps(baseline, indent=2, sort_keys=True) + "\n"
            if updated_baseline_text != baseline_text:
                atomic_write(
                    project.baseline_path,
                    updated_baseline_text,
                    expected_text=baseline_text,
                    expected_absent=baseline_text is None,
                )
        except Exception as e:
            if json_output:
                print(json.dumps({"error": f"Failed to update resource baseline: {e}"}, indent=2))
            else:
                console.print(f"\n[red]Error:[/red] Failed to update resource baseline: {e}")
            has_errors = True

        if not has_errors:
            try:
                write_version_file(project.version_path, current_version)
                if verbose_level > 0:
                    console.print(f"\nProject resource version: {current_version}")
            except Exception as e:
                if json_output:
                    print(json.dumps({"warning": f"Failed to update version file: {e}"}, indent=2))
                else:
                    console.print(f"\n[red]Warning:[/red] Failed to update version file: {e}")
                has_errors = True
        else:
            if verbose_level > 0:
                console.print("\nVersion NOT updated due to errors/conflicts.", style="red")

    if results["conflicts"]:
        console.print("\nConflicts detected - user modifications preserved:")
        for conflict in results["conflicts"]:
            console.print(f"  - {conflict}")
        console.print("Review and merge manually if needed.")

    raise typer.Exit(1 if has_errors else 0)


update_app = typer.Typer(name="update", help="Update project resources", invoke_without_command=True)
update_app.callback()(update)


__all__ = ["update", "update_skill", "update_registry", "update_agents_md_section", "update_airoom_md", "update_app"]