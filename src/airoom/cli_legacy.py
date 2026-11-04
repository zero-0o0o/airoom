"""AIroom legacy CLI entry point (argparse-based).

This module preserves the original argparse CLI for compatibility during Phase 1-4.
It will be replaced by the Typer-based CLI in cli.py.
"""

import argparse
import sys

from airoom import __version__

from airoom.commands.init import add_init_parser
from airoom.commands.update import add_update_parser
from airoom.commands.upgrade import add_upgrade_parser
from airoom.commands.uninstall import add_uninstall_parser


def main():
    parser = argparse.ArgumentParser(
        prog="airoom", description="AIroom - Shared infrastructure for AI agents and tools"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init command
    add_init_parser(subparsers)

    # update command
    add_update_parser(subparsers)

    # upgrade command
    add_upgrade_parser(subparsers)

    # uninstall command
    add_uninstall_parser(subparsers)

    args = parser.parse_args()

    if hasattr(args, "func"):
        return args.func(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())