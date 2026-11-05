"""AIroom organize command implementation (Typer-based)."""

import json
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from airoom.core.discovery import DiscoveryEngine
from airoom.core.organization import OrganizationEngine
from airoom.core.project import Project
from airoom.core.registry import RegistryManager

console = Console()

organize_app = typer.Typer(name="organize", help="Organize artifacts under airoom/artifacts/.")


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


def _render_plan_human(plan, project: Project) -> None:
    """Render relocation plan as a Rich table."""
    table = Table(title="Relocation Plan", show_header=True, header_style="bold")
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Source", style="cyan")
    table.add_column("Target", style="green")
    table.add_column("Tool", style="yellow")
    table.add_column("Mgmt", justify="center", width=8)
    table.add_column("Env Var", style="dim")

    for i, action in enumerate(plan.actions, 1):
        source_rel = action.source.relative_to(project.root)
        target_rel = action.target.relative_to(project.root)
        mgmt = action.management
        env_var = action.env_var or "-"
        table.add_row(str(i), str(source_rel), str(target_rel), action.tool_id, mgmt, env_var)

    console.print(table)
    console.print()


def _build_plan_json(plan, project: Project) -> dict:
    """Build JSON representation of relocation plan."""
    return {
        "actions": [
            {
                "source": str(action.source.relative_to(project.root)),
                "target": str(action.target.relative_to(project.root)),
                "artifact_id": action.artifact_id,
                "tool_id": action.tool_id,
                "management": action.management,
                "env_var": action.env_var,
            }
            for action in plan.actions
        ],
        "tool_configs": plan.tool_configs,
    }


def _render_result_human(success: bool, messages: list[str]) -> None:
    """Render execution results as human-readable output."""
    if success:
        console.print("[green]✓ Organization completed successfully[/green]")
    else:
        console.print("[red]✗ Organization failed[/red]")

    for msg in messages:
        if msg.startswith("✓") or msg.startswith("[DRY RUN]"):
            console.print(f"  [green]{msg}[/green]")
        elif msg.startswith("✗"):
            console.print(f"  [red]{msg}[/red]")
        else:
            console.print(f"  {msg}")


def _build_result_json(success: bool, messages: list[str]) -> dict:
    """Build JSON representation of execution results."""
    return {
        "success": success,
        "messages": messages,
    }


def _prompt_for_action(candidate) -> str:
    """Prompt user for action on a candidate in interactive mode."""
    console.print(f"\n[bold]Candidate:[/bold] {candidate.path}")
    console.print(f"  Owner: [cyan]{candidate.likely_owner}[/cyan]")
    console.print(f"  Type: {candidate.type}")
    console.print(f"  Recommended: [green]{candidate.recommended_mode}[/green]")
    console.print(f"  Feasibility: [dim]{candidate.relocation_feasibility}[/dim]")

    choices = ["route", "track-external", "skip"]
    default = "route" if candidate.recommended_mode == "managed" else "track-external"

    action = Prompt.ask(
        "Action",
        choices=choices,
        default=default,
        show_choices=True,
    )
    return action


def _build_plan_from_interactive(
    project: Project, registry: RegistryManager, discovery_report, json_output: bool
) -> tuple:
    """Build a relocation plan interactively by prompting for each candidate."""
    from airoom.core.organization import RelocationAction, RelocationPlan

    actions: list[RelocationAction] = []
    tool_configs: dict[str, dict] = {}
    used_artifact_ids: set[str] = set()

    # Read existing artifact IDs from registry to avoid collisions
    registry_data = registry.read()
    for existing_id in registry_data.get("artifacts", {}).keys():
        used_artifact_ids.add(existing_id)

    for candidate in discovery_report.unregistered_candidates:
        if json_output:
            # In JSON mode, we can't prompt interactively, so use defaults
            action = "route" if candidate.recommended_mode == "managed" else "track-external"
        else:
            action = _prompt_for_action(candidate)

        if action == "skip":
            continue

        # Get tool config
        engine = OrganizationEngine(project, registry)
        tool_config = engine.TOOL_CONFIGS.get(candidate.likely_owner, {})
        canonical_path = tool_config.get("canonical_path")
        env_var = tool_config.get("env_var")

        # Determine artifact_id
        artifact_id = engine._sanitize_artifact_id(candidate.path, used_artifact_ids)
        used_artifact_ids.add(artifact_id)

        if action == "route" and canonical_path:
            # Managed relocation
            target_rel = canonical_path
            base_target = project.root / target_rel
            target = engine._get_unique_target(base_target, artifact_id)
            target_rel = target.relative_to(project.root).as_posix()

            rel_action = RelocationAction(
                source=project.root / candidate.path,
                target=target,
                artifact_id=artifact_id,
                tool_id=candidate.likely_owner,
                management="managed",
                env_var=env_var,
            )
            actions.append(rel_action)

            if candidate.likely_owner not in tool_configs:
                tool_configs[candidate.likely_owner] = {
                    "output_path": target_rel,
                    "output_env": env_var,
                }
        elif action == "track-external":
            # External tracking
            source = project.root / candidate.path
            rel_action = RelocationAction(
                source=source,
                target=source,
                artifact_id=artifact_id,
                tool_id=candidate.likely_owner,
                management="external",
                env_var=None,
            )
            actions.append(rel_action)

            if candidate.likely_owner not in tool_configs:
                tool_configs[candidate.likely_owner] = {
                    "output_path": candidate.path,
                    "output_env": None,
                }

    return RelocationPlan(actions=actions, tool_configs=tool_configs)


@organize_app.command()
def organize(
    ctx: typer.Context,
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive/--non-interactive",
            help="Prompt for each candidate (default: interactive)",
        ),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without executing"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
) -> None:
    """Organize artifacts under airoom/artifacts/."""
    # Use global --json flag if local --json not explicitly set
    global_opts = ctx.obj
    if global_opts and global_opts.json_output and not json_output:
        json_output = True

    # Use global --dry-run flag if local --dry-run not explicitly set
    if global_opts and global_opts.dry_run and not dry_run:
        dry_run = True

    project = _get_project(ctx, path)

    # Verify project has been initialized
    if not project.airoom_dir.exists():
        error_msg = f"AIroom directory not found at {project.airoom_dir}. Run 'airoom init' first."
        if json_output:
            print(json.dumps({"error": "Project not initialized", "details": error_msg}, indent=2))
        else:
            console.print(f"[red]Error:[/red] Project not initialized at {project.root}")
            console.print("Run 'airoom init' to initialize AIroom in this project.")
        raise typer.Exit(1)

    # Run discovery scan
    registry_manager = RegistryManager(project)
    discovery_engine = DiscoveryEngine(project, registry_manager)
    discovery_report = discovery_engine.scan()

    # Deduplicate candidates by source path (discovery may find same artifact from multiple scan roots)
    seen_paths = set()
    unique_candidates = []
    for candidate in discovery_report.unregistered_candidates:
        if candidate.path not in seen_paths:
            seen_paths.add(candidate.path)
            unique_candidates.append(candidate)
    discovery_report.unregistered_candidates = unique_candidates

    if not discovery_report.unregistered_candidates:
        if json_output:
            print(
                json.dumps(
                    {
                        "success": True,
                        "plan": {"actions": [], "tool_configs": {}},
                        "result": {
                            "success": True,
                            "messages": ["No unregistered candidates found. Nothing to organize."],
                        },
                    },
                    indent=2,
                )
            )
        else:
            console.print("[green]No unregistered candidates found. Nothing to organize.[/green]")
        return

    # Build relocation plan
    org_engine = OrganizationEngine(project, registry_manager)

    if interactive:
        # Interactive mode: prompt for each candidate
        plan = _build_plan_from_interactive(
            project, registry_manager, discovery_report, json_output
        )
    else:
        # Non-interactive mode: use defaults (managed if feasible, else external)
        plan = org_engine.plan(discovery_report)

    if not plan.actions:
        if json_output:
            print(
                json.dumps(
                    {
                        "success": True,
                        "plan": {"actions": [], "tool_configs": {}},
                        "result": {
                            "success": True,
                            "messages": ["No actions to perform after filtering."],
                        },
                    },
                    indent=2,
                )
            )
        else:
            console.print("[yellow]No actions to perform after filtering.[/yellow]")
        return

    # Build plan JSON for output
    plan_json = _build_plan_json(plan, project)

    # Show plan (human mode only - JSON mode combines plan and result)
    if not json_output:
        _render_plan_human(plan, project)

    # Execute plan (or dry-run)
    success, messages = org_engine.execute(plan, dry_run=dry_run)

    # Build result JSON
    result_json = _build_result_json(success, messages)

    # Render results
    if json_output:
        # Combined output: plan + result
        combined = {
            "success": success,
            "plan": plan_json,
            "result": result_json,
        }
        print(json.dumps(combined, indent=2))
    else:
        _render_result_human(success, messages)

    if not success:
        raise typer.Exit(1)
