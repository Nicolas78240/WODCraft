"""The WODCraft MCP server: the compiler, exposed over the Model Context Protocol.

``python -m wodcraft.mcp.server`` starts it over stdio; ``--http`` serves streamable HTTP.
The server object and its tools live in :mod:`wodcraft.mcp.server`, which is imported
explicitly so that importing this package never requires the ``mcp`` SDK.

See ``docs/mcp.md``.
"""
