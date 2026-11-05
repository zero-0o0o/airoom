"""AIroom completion command implementation (Typer-based)."""

import typer
from click.shell_completion import BashComplete, FishComplete, ZshComplete

completion_app = typer.Typer(name="completion", help="Generate shell completion script.")


@completion_app.callback(invoke_without_command=True)
def completion(
    ctx: typer.Context,
    shell: str = typer.Argument(..., help="Shell type: bash|zsh|fish"),
) -> None:
    """Generate shell completion script for AIroom CLI."""
    valid_shells = ["bash", "zsh", "fish"]
    if shell not in valid_shells:
        print(f"Error: Invalid shell '{shell}'. Valid options: {', '.join(valid_shells)}")
        raise typer.Exit(1)

    # Get the root Click command from the context (parent = main app)
    root_ctx = ctx.parent
    if root_ctx is None:
        print("Error: Could not determine root command context")
        raise typer.Exit(1)

    click_command = root_ctx.command

    # Create the appropriate completion class and generate the script
    complete_var = f"_{click_command.name.upper().replace('-', '_')}_COMPLETE"

    if shell == "bash":
        completer = BashComplete(click_command, {}, click_command.name, complete_var)
    elif shell == "zsh":
        completer = ZshComplete(click_command, {}, click_command.name, complete_var)
    elif shell == "fish":
        completer = FishComplete(click_command, {}, click_command.name, complete_var)

    print(completer.source())
