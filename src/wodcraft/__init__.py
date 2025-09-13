"""Unified WODCraft package (legacy + vNext).

This package provides a single CLI and thin wrappers that route to the
legacy DSL (wodc_merged) or the vNext language (wodc_vnext) depending
on file contents or explicit subcommands.
"""

from .cli import main  # noqa: F401

