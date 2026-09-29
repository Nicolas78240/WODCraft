"""Editor support for WODCraft: a language server (LSP) built on `pygls`.

``python -m wodcraft.lsp`` starts the server on stdio.
"""

from __future__ import annotations

__all__ = ["create_server", "main"]


def __getattr__(name: str):  # lazy, so importing the package never requires pygls
    if name in __all__:
        from wodcraft.lsp import server

        return getattr(server, name)
    raise AttributeError(name)
