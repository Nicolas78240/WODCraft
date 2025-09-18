"""Unified WODCraft package and CLI integrations.

This package exposes the WODCraft CLI (`wodc`) along with helper shims
used by the MCP server, SDK, and editor tooling while the language core
continues to be consolidated under ``src/wodcraft``.
"""

from .cli import main  # noqa: F401
