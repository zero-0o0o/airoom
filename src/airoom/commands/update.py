"""AIroom update command implementation."""

import hashlib
import json
import sys
from pathlib import Path

from airoom import __version__
from airoom.commands.init import (
    AIROOM_END,
    AIROOM_START,
    get_resource_path,
    read_resource,
    update_agents_md,
    assert_safe_project_path,
    list_packaged_skills as list_packaged_skills,
    list_packaged_templates as list_packaged_templates,
)
from airoom.core.atomic import atomic_write, compute_file_hash
from airoom.core.version import read_version_file, write_version_file
from airoom.registry import RegistryError, dump_registry, parse_registry


def update_skill(
    skill_name: str,
    project_skills_dir: Path,
    verbose: bool = True,
    baseline_hash: str | None = None,
) -> dict:
    """Update a single skill directory.

    Returns a dict with keys: 'status' (updated|added|skipped|conflict), 'message'
    """
    src_skill = get_resource_path(f"skills/{skill_name}/SKILL.md")
    skill_dir = project_skills_dir / skill_name
    dst_skill = skill_dir / "SKILL.md"

    if not src_skill.exists():
        return {"status": "skipped", "message": f"Packaged skill not found: {skill_name}"}

    if not skill_dir.exists():
        # New skill - add it
        try:
            skill_dir.mkdir(parents=True, exist_ok=True)
            atomic_write(dst_skill, src_skill.read_text(encoding="utf-8"), expected_absent=True)
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
        try:
            if baseline_hash is not None:
                return {
                    "status": "conflict",
                    "message": f"Previously installed skill is missing: {skill_name}",
                }
            atomic_write(dst_skill, src_skill.read_text(encoding="utf-8"), expected_absent=True)
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
            return {"status": "skipped", "message": f"Skill already current: {skill_name}"}
        # Unchanged - update to latest
        try:
            atomic_write(
                dst_skill, src_skill.read_text(encoding="utf-8"), expected_text=existing_content
            )
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
        try:
            template_data = parse_registry(packaged_content)
            atomic_write(
                project_registry_path,
                dump_registry(template_data),
                expected_absent=True,
            )
            return {"status": "added", "message": "Created registry.yaml from template"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to create registry.yaml: {e}"}

    # Round-trip parse preserves comments/unknown keys; duplicate keys are rejected.
    try:
        original_text = project_registry_path.read_text(encoding="utf-8")
        existing_data = parse_registry(original_text)
    except RegistryError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Failed to read registry.yaml: {e}"}

    # Parse packaged template
    try:
        template_data = parse_registry(packaged_content)
    except RegistryError as e:
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
        return {"status": "skipped", "message": "Registry already up to date"}

    try:
        # dump_registry validates again before serialization.
        updated_text = dump_registry(existing_data)
        atomic_write(project_registry_path, updated_text, expected_text=original_text)
    except Exception as e:
        return {"status": "error", "message": f"Failed to update registry.yaml: {e}"}
    return {"status": "updated", "message": "Added missing registry schema fields"}


def update_agents_md_section(
    project_root: Path, verbose: bool = True, baseline_hash: str | None = None
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
    airoom_dir: Path, verbose: bool = True, baseline_hash: str | None = None
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
        try:
            if baseline_hash is not None:
                return {
                    "status": "conflict",
                    "message": "Previously installed AIROOM.md is missing",
                }
            atomic_write(airoom_md_path, airoom_md_template, expected_absent=True)
            if verbose:
                print(f"  Created file: {airoom_md_path}")
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
            return {"status": "skipped", "message": "AIROOM.md already current"}
        # Unchanged - update to latest
        try:
            atomic_write(airoom_md_path, packaged_content, expected_text=existing_content)
            if verbose:
                print(f"  Updated file: {airoom_md_path}")
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


def update_command(args) -> int:
    """Update AIroom project resources.

    Returns 0 on success, non-zero on failure.
    """
    # Determine project root
    project_root = Path(getattr(args, "path", None) or Path.cwd()).resolve()
    if not project_root.is_dir():
        print(
            f"Error: Project directory does not exist or is not a directory: {project_root}",
            file=sys.stderr,
        )
        return 1

    airoom_dir = project_root / "airoom"

    print(f"Updating AIroom resources in: {project_root}")

    # Check if AIroom is initialized
    if airoom_dir.is_symlink() or not airoom_dir.exists() or not airoom_dir.is_dir():
        print(
            "Error: AIroom not initialized in this project. Run 'airoom init' first.",
            file=sys.stderr,
        )
        return 1

    try:
        for target in (
            airoom_dir / "skills",
            airoom_dir / "AIROOM.md",
            airoom_dir / "registry.yaml",
            airoom_dir / ".airoom-version",
            airoom_dir / ".airoom-baseline.json",
            project_root / "AGENTS.md",
        ):
            assert_safe_project_path(project_root, target)
        for skill_name in list_packaged_skills():
            assert_safe_project_path(project_root, airoom_dir / "skills" / skill_name / "SKILL.md")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    version_path = airoom_dir / ".airoom-version"
    installed_version = read_version_file(version_path)
    current_version = __version__

    print(f"  Installed version: {installed_version or 'unknown'}")
    print(f"  Current version:   {current_version}")

    if installed_version == current_version:
        print("  Already at latest version.")
        # Still check for new resources that might have been added
        print("  Checking for new resources...")

    baseline_path = airoom_dir / ".airoom-baseline.json"
    baseline_text: str | None = None
    try:
        assert_safe_project_path(project_root, baseline_path)
        if baseline_path.exists():
            baseline_text = baseline_path.read_text(encoding="utf-8")
            baseline = json.loads(baseline_text)
        else:
            baseline = {}
        if not isinstance(baseline, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in baseline.items()
        ):
            raise ValueError("baseline must map resource paths to SHA-256 hashes")
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"Error: Cannot read AIroom resource baseline: {e}", file=sys.stderr)
        return 1

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
    print("\nUpdating skills...")
    project_skills_dir = airoom_dir / "skills"
    try:
        assert_safe_project_path(project_root, project_skills_dir)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if not project_skills_dir.exists():
        project_skills_dir.mkdir(parents=True, exist_ok=True)

    packaged_skills = list_packaged_skills()
    for skill_name in packaged_skills:
        relpath = f"skills/{skill_name}/SKILL.md"
        result = update_skill(
            skill_name, project_skills_dir, verbose=True, baseline_hash=baseline.get(relpath)
        )
        results["skills"].append((skill_name, result))
        if result["status"] in ("added", "updated", "skipped"):
            baseline[relpath] = compute_file_hash(project_skills_dir / skill_name / "SKILL.md")
        if result["status"] == "conflict":
            results["conflicts"].append(f"Skill: {skill_name}")
        elif result["status"] == "error":
            results["errors"].append(f"Skill {skill_name}: {result['message']}")

    # Check for skills that exist in project but not in package (user-created)
    if project_skills_dir.exists():
        for skill_dir in project_skills_dir.iterdir():
            if skill_dir.is_dir() and skill_dir.name not in packaged_skills:
                print(f"  Preserving user-created skill: {skill_dir.name}")

    # 2. Update registry.yaml
    print("\nUpdating registry...")
    registry_path = airoom_dir / "registry.yaml"
    try:
        assert_safe_project_path(project_root, registry_path)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    registry_result = update_registry(registry_path, verbose=True)
    results["registry"] = registry_result
    if registry_result["status"] == "error":
        results["errors"].append(f"Registry: {registry_result['message']}")

    # 3. Update AGENTS.md section
    print("\nUpdating AGENTS.md...")
    agents_result = update_agents_md_section(
        project_root, verbose=True, baseline_hash=baseline.get("AGENTS.md#airoom-section")
    )
    results["agents_md"] = agents_result
    if agents_result["status"] == "error":
        results["errors"].append(f"AGENTS.md: {agents_result['message']}")
    elif agents_result["status"] == "conflict":
        results["conflicts"].append("AGENTS.md AIroom section")
    if agents_result["status"] in ("updated", "skipped"):
        content = (project_root / "AGENTS.md").read_text(encoding="utf-8")
        start = content.find(AIROOM_START)
        end = content.find(AIROOM_END)
        if start != -1 and end > start:
            section = content[start : end + len(AIROOM_END)]
            baseline["AGENTS.md#airoom-section"] = hashlib.sha256(
                section.encode("utf-8")
            ).hexdigest()

    # 4. Update AIROOM.md
    print("\nUpdating AIROOM.md...")
    airoom_md_result = update_airoom_md(
        airoom_dir, verbose=True, baseline_hash=baseline.get("AIROOM.md")
    )
    results["airoom_md"] = airoom_md_result
    if airoom_md_result["status"] == "error":
        results["errors"].append(f"AIROOM.md: {airoom_md_result['message']}")
    elif airoom_md_result["status"] == "conflict":
        results["conflicts"].append("AIROOM.md")
    if airoom_md_result["status"] in ("added", "updated", "skipped"):
        baseline["AIROOM.md"] = compute_file_hash(airoom_dir / "AIROOM.md")

    # Print summary
    print("\n" + "=" * 50)
    print("Update Summary:")
    print("=" * 50)

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
        print(f"  Skill '{skill_name}': {status} - {result['message']}")

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
        print(f"  Registry: {status} - {results['registry']['message']}")

    if results["agents_md"]:
        status = results["agents_md"]["status"]
        if status == "updated":
            updated_count += 1
        elif status == "skipped":
            skipped_count += 1
        elif status == "error":
            error_count += 1
        print(f"  AGENTS.md: {status} - {results['agents_md']['message']}")

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
        print(f"  AIROOM.md: {status} - {results['airoom_md']['message']}")

    print(f"\n  Updated: {updated_count}")
    print(f"  Added:   {added_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Conflicts: {conflict_count}")
    print(f"  Errors:  {error_count}")

    # Determine exit code
    has_errors = error_count > 0 or bool(results["conflicts"])

    # Persist per-resource baselines for resources successfully written. This
    # makes a partial update safely repeatable while conflicted resources retain
    # their prior hashes. The version marker still advances only on full success.
    try:
        updated_baseline_text = json.dumps(baseline, indent=2, sort_keys=True) + "\n"
        if updated_baseline_text != baseline_text:
            atomic_write(
                baseline_path,
                updated_baseline_text,
                expected_text=baseline_text,
                expected_absent=baseline_text is None,
            )
    except Exception as e:
        print(f"\nError: Failed to update resource baseline: {e}", file=sys.stderr)
        has_errors = True

    if not has_errors:
        try:
            write_version_file(version_path, current_version)
            print(f"\nProject resource version: {current_version}")
        except Exception as e:
            print(f"\nWarning: Failed to update version file: {e}", file=sys.stderr)
            has_errors = True
    else:
        print("\nVersion NOT updated due to errors/conflicts.", file=sys.stderr)

    if results["conflicts"]:
        print("\nConflicts detected - user modifications preserved:")
        for conflict in results["conflicts"]:
            print(f"  - {conflict}")
        print("Review and merge manually if needed.")

    return 1 if has_errors else 0


def add_update_parser(subparsers):
    """Add the update subcommand parser."""
    parser = subparsers.add_parser("update", help="Update project resources")
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Project directory (default: current directory)",
    )
    parser.set_defaults(func=update_command)
