"""MCP tool modules, grouped by NSX domain.

Importing each submodule registers its tools onto the shared ``mcp`` instance
(via the ``@mcp.tool`` decorator). ``mcp_server.server`` imports them all at
startup and re-exports the tool callables into its own namespace.
"""

from mcp_server.tools import (
    gateway,
    health,
    inventory,
    ip_pool,
    nat,
    networking,
    route,
    segment,
    troubleshoot,
)

__all__ = [
    "gateway",
    "health",
    "inventory",
    "ip_pool",
    "nat",
    "networking",
    "route",
    "segment",
    "troubleshoot",
]
