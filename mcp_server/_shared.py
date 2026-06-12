"""Shared MCP primitives: the FastMCP instance and the error sanitizer.

Tool modules under ``mcp_server.tools`` import ``mcp`` (to register tools),
``_safe_error`` (agent-safe error formatting), and ``_DOCTOR_HINT`` from here.
The connection helper lives in ``mcp_server.server`` instead, so that tests can
``patch("mcp_server.server._get_connection")`` and have every tool pick it up;
tool modules therefore call ``server._get_connection(...)`` at runtime.
"""

import logging

from mcp.server.fastmcp import FastMCP
from vmware_policy import sanitize

from vmware_nsx.connection import NsxApiError

logger = logging.getLogger("mcp_server")

_DOCTOR_HINT = "Run 'vmware-nsx doctor' to verify connectivity."


def _safe_error(exc: Exception, tool: str) -> str:
    """Return an agent-safe error string; log full detail server-side only.

    Raw NSX exception text can carry response bodies, internal paths, or
    host:port pairs. Full traceback goes to stderr (operator-visible); the agent
    sees only a control-char-stripped, length-capped message. Intentional
    validation errors (ValueError/FileNotFoundError/KeyError) and the
    connection layer's teaching errors (NsxApiError) pass through.
    """
    logger.error("Tool %s failed", tool, exc_info=True)
    if isinstance(exc, (ValueError, FileNotFoundError, KeyError, NsxApiError)):
        return sanitize(str(exc), 300)
    return f"{type(exc).__name__}: operation failed."


mcp = FastMCP(
    "vmware-nsx",
    instructions=(
        "VMware NSX networking management. "
        "Query and configure network segments, Tier-0/Tier-1 gateways, "
        "NAT rules, static routes, IP pools, transport zones/nodes, "
        "and edge clusters. Check NSX health, alarms, and troubleshoot "
        "connectivity. For DFW firewall/microsegmentation, use vmware-nsx-security. "
        "For VM operations, use vmware-aiops. For monitoring, use vmware-monitor."
    ),
)
