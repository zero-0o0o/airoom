"""AIroom init command implementation."""

import hashlib
import json
import sys
from pathlib import Path
from typing import Optional

from airoom import __version__
from airoom.core.resources import ResourceManager
from airoom.registry import RegistryError, atomic_write, parse_registry


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


def find_project_root(start_path: Optional[Path] = None) -> Path:
    """Find the project root directory.

    For init, we use the current working directory unless specified otherwise.
    """
    root = Path.cwd() if start_path is None else Path(start_path)
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise NotADirectoryError(f"Project directory does not exist or is not a directory: {root}")
    return root


def assert_safe_project_path(project_root: Path, path: Path) -> None:
    """Reject paths that escape the project or traverse existing symlinks."""
    root = project_root.resolve()
    try:
        relative = path.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"Path is outside the project: {path}") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Refusing to follow symlink in AIroom resource path: {current}")
    if not path.resolve(strict=False).is_relative_to(root):
        raise ValueError(f"Path resolves outside the project: {path}")


def create_directory(path: Path, verbose: bool = True) -> bool:
    """Create a directory if it doesn't exist.

    Returns True if created, False if already existed.
    """
    if path.exists():
        if path.is_dir():
            if verbose:
                print(f"  Directory already exists: {path}")
            return False
        else:
            raise FileExistsError(f"Path exists but is not a directory: {path}")
    try:
        path.mkdir(parents=True, exist_ok=False)
        if verbose:
            print(f"  Created directory: {path}")
        return True
    except PermissionError as e:
        raise PermissionError(f"Cannot create directory {path}: {e}") from e


def copy_file_if_missing(src: Path, dst: Path, verbose: bool = True) -> bool:
    """Copy a file if destination doesn't exist.

    Returns True if copied, False if already existed.
    """
    if dst.exists():
        if verbose:
            print(f"  File already exists (skipped): {dst}")
        return False
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(dst, src.read_text(encoding="utf-8"), expected_absent=True)
        if verbose:
            print(f"  Created file: {dst}")
        return True
    except PermissionError as e:
        raise PermissionError(f"Cannot create file {dst}: {e}") from e


def write_file_if_missing(path: Path, content: str, verbose: bool = True) -> bool:
    """Write a file if it doesn't exist.

    Returns True if written, False if already existed.
    """
    if path.exists():
        if verbose:
            print(f"  File already exists (skipped): {path}")
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, content, expected_absent=True)
        if verbose:
            print(f"  Created file: {path}")
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
            raise RegistryError(f"Concurrent modification detected: {agents_path}")

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
                    print("  Existing AIroom section preserved in AGENTS.md")
                return False
            # Section exists - check if content is different
            end_marker_end = end_idx + len(AIROOM_END)
            existing_section = content[start_idx:end_marker_end]

            if existing_section.strip() == airoom_section.strip():
                if verbose:
                    print("  AIroom section in AGENTS.md is up to date")
                return False
            else:
                # Replace the existing section
                new_content = content[:start_idx] + airoom_section + content[end_marker_end:]
                atomic_write(agents_path, new_content, expected_text=content)
                if verbose:
                    print(f"  Updated AIroom section in: {agents_path}")
                return True
        else:
            # No section exists - append to end of file
            original_content = content
            if content and not content.endswith("\n"):
                content += "\n"
            new_content = content + "\n" + airoom_section + "\n"
            atomic_write(agents_path, new_content, expected_text=original_content)
            if verbose:
                print(f"  Added AIroom section to: {agents_path}")
            return True
    else:
        # File doesn't exist - create it with just the AIroom section
        atomic_write(agents_path, airoom_section + "\n", expected_absent=True)
        if verbose:
            print(f"  Created AGENTS.md with AIroom section: {agents_path}")
        return True


def init_command(args) -> int:
    """Initialize AIroom in a project.

    Returns 0 on success, non-zero on failure.
    """
    # Determine project root
    try:
        project_root = find_project_root(getattr(args, "path", None))
        airoom_dir = project_root / "airoom"
        print(f"Initializing AIroom in: {project_root}")
        for target in (
            airoom_dir,
            airoom_dir / "skills",
            airoom_dir / "artifacts",
            airoom_dir / "registry.yaml",
            airoom_dir / "AIROOM.md",
            airoom_dir / ".airoom-version",
            airoom_dir / ".airoom-baseline.json",
            project_root / "AGENTS.md",
        ):
            assert_safe_project_path(project_root, target)
        packaged_skills = list_packaged_skills()
        for skill_name in packaged_skills:
            assert_safe_project_path(project_root, airoom_dir / "skills" / skill_name / "SKILL.md")

        # 1. Create airoom/ directory
        create_directory(airoom_dir)

        # 2. Create skills/ subdirectories and copy skill files
        skills_dir = airoom_dir / "skills"
        create_directory(skills_dir)

        for skill_name in packaged_skills:
            skill_dir = skills_dir / skill_name
            create_directory(skill_dir)

            # Copy SKILL.md from packaged resources
            src_skill = get_resource_path(f"skills/{skill_name}/SKILL.md")
            dst_skill = skill_dir / "SKILL.md"
            copy_file_if_missing(src_skill, dst_skill)

        # 3. Create artifacts/ directory
        artifacts_dir = airoom_dir / "artifacts"
        create_directory(artifacts_dir)

        # 4. Initialize registry.yaml from template (only if missing)
        registry_path = airoom_dir / "registry.yaml"
        registry_template = read_resource("templates/registry.yaml")
        if not registry_path.exists():
            parse_registry(registry_template)
            write_file_if_missing(registry_path, registry_template)
        # Existing registries are user data. Init leaves them untouched; update
        # validates them before any schema mutation.

        # 5. Create AIROOM.md from template (only if missing)
        airoom_md_path = airoom_dir / "AIROOM.md"
        airoom_md_template = read_resource("templates/AIROOM.md")
        write_file_if_missing(airoom_md_path, airoom_md_template)

        # 7. Update or create AGENTS.md with AIroom section
        agents_path = project_root / "AGENTS.md"
        airoom_section = read_resource("templates/AGENTS.md")
        update_agents_md(agents_path, airoom_section, replace_existing=False)

        # Baselines are only recorded for resources that exactly match what init installed.
        baseline: dict[str, str] = {}
        for skill_name in packaged_skills:
            relpath = f"skills/{skill_name}/SKILL.md"
            installed = airoom_dir / relpath
            bundled = get_resource_path(relpath)
            if installed.is_file() and installed.read_bytes() == bundled.read_bytes():
                baseline[relpath] = hashlib.sha256(installed.read_bytes()).hexdigest()
        for relpath in ("AIROOM.md",):
            installed = airoom_dir / relpath
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
        baseline_path = airoom_dir / ".airoom-baseline.json"
        if not baseline_path.exists():
            atomic_write(
                baseline_path,
                json.dumps(baseline, indent=2, sort_keys=True) + "\n",
                expected_absent=True,
            )

        # Version is written last: its presence indicates project resources initialized.
        version_path = airoom_dir / ".airoom-version"
        write_file_if_missing(version_path, __version__ + "\n")

        print("\nAIroom initialization complete!")
        print(f"  Project root: {project_root}")
        print(f"  AIroom directory: {airoom_dir}")
        print(f"  Version: {__version__}")

        return 0

    except FileExistsError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except PermissionError as e:
        print(f"Permission error: {e}", file=sys.stderr)
        return 1
    except (NotADirectoryError, ValueError, RegistryError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def add_init_parser(subparsers):
    """Add the init subcommand parser."""
    parser = subparsers.add_parser("init", help="Initialize AIroom in a project")
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Project directory (default: current directory)",
    )
    parser.set_defaults(func=init_command)
