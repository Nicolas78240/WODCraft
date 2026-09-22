"""``python -m wodcraft.lsp`` — start the WODCraft language server on stdio."""

from __future__ import annotations

from wodcraft.lsp.server import main

if __name__ == "__main__":
    raise SystemExit(main())
