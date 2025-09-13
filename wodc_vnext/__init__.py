"""
wodc_vnext package shim exposing vNext symbols for imports in tests.

This re-exports the public API from wodc_vnext.core while allowing the
top-level CLI shim (wodc_vnext.py) to continue working unchanged.
"""

from .core import (
    GRAMMAR_VNEXT,
    UnitType,
    TypeSpec,
    Load,
    Distance,
    ModuleRef,
    ResolvedModule,
    ModuleResolver,
    InMemoryResolver,
    FileSystemResolver,
    SessionCompiler,
    ToASTvNext,
    parse_vnext,
    main,
    ProgrammingLinter,
    TeamRealizedAggregator,
)

__all__ = [
    "GRAMMAR_VNEXT",
    "UnitType",
    "TypeSpec",
    "Load",
    "Distance",
    "ModuleRef",
    "ResolvedModule",
    "ModuleResolver",
    "InMemoryResolver",
    "FileSystemResolver",
    "SessionCompiler",
    "ToASTvNext",
    "parse_vnext",
    "main",
    "ProgrammingLinter",
    "TeamRealizedAggregator",
]
