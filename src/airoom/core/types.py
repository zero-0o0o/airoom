"""Shared type definitions for AIroom."""

from pathlib import Path
from typing import Optional


class GlobalOptions:
    """Container for global CLI options."""

    def __init__(
        self,
        path: Optional[Path] = None,
        verbose: int = 0,
        json_output: bool = False,
        dry_run: bool = False,
    ):
        self.path = path
        self.verbose = verbose
        self.json_output = json_output
        self.dry_run = dry_run
