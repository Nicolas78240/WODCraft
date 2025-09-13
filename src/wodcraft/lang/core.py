#!/usr/bin/env python3
# This file is moved from wodc_vnext/core.py to unified package structure.
# The full content was previously in wodc_vnext/core.py and is now the single source of truth.

from pathlib import Path
import json
from lark import Lark

# Re-export all from legacy path to keep imports working inside this module
# The actual implementation remains in the original file for this step.

from wodc_vnext.core import (  # type: ignore
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
    TeamRealizedAggregator,
    ProgrammingLinter,
)
