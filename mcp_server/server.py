"""MCP server wrapping VMware NSX networking operations.

This module is the thin entry point for the Model Context Protocol (MCP)
server (stdio transport). The tool implementations live under
``mcp_server.tools`` (one module per NSX domain) and register themselves onto
the shared ``mcp`` instance defined in ``mcp_server._shared``. Each tool
delegates to the corresponding function in the ``vmware_nsx`` package
(ops.inventory, ops.networking, ops.health, ops.troubleshoot,
ops.segment_mgmt, ops.nat_route_mgmt).

Tool categories
---------------
* **Read-only** (no side effects): list_segments, get_segment,
  list_tier0_gateways, get_tier0_gateway, list_tier1_gateways,
  get_tier1_gateway, list_transport_zones,
  list_transport_nodes, list_edge_clusters, list_nat_rules,
  get_bgp_neighbors, list_static_routes, list_ip_pools,
  get_ip_pool_usage, list_nsx_alarms, get_transport_node_status,
  get_edge_cluster_status, get_nsx_manager_status,
  get_logical_port_status, get_segment_port_for_vm

* **Write** (mutate state): create_segment, update_segment,
  delete_segment, create_tier1_gateway, update_tier1_gateway,
  delete_tier1_gateway, configure_tier0_bgp, create_nat_rule,
  delete_nat_rule, create_static_route, delete_static_route,
  create_ip_pool, delete_ip_pool — should be gated by the AI agent's
  confirmation flow.

Security considerations
-----------------------
* **Credential handling**: Credentials are loaded from environment
  variables / ``.env`` file — never passed via MCP messages.
* **Transport**: Uses stdio transport (local only); no network listener.
* **Destructive ops**: Write operations modify NSX networking config;
  confirmation is recommended before execution.

For DFW firewall/microsegmentation, use vmware-nsx-security.
For VM operations, use vmware-aiops.
For monitoring, use vmware-monitor.
"""


import logging
import os
from pathlib import Path
from typing import Any, Optional

from vmware_policy import apply_read_only_gate, mtime_cached_loader, set_environment_resolver

from vmware_nsx.config import CONFIG_FILE, load_config
from vmware_nsx.connection import ConnectionManager

# Re-exported so callers and tests can keep using ``mcp_server.server.<name>``.
from mcp_server._shared import _DOCTOR_HINT, _safe_error, mcp

__all__ = ["mcp", "main", "_get_connection", "_safe_error", "_DOCTOR_HINT"]

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

_conn_mgr: Optional[ConnectionManager] = None


def _get_connection(target: Optional[str] = None) -> Any:
    """Return an NsxClient, lazily initialising the connection manager.

    Tool modules call ``server._get_connection(...)`` (not a local import) so
    that tests can ``patch("mcp_server.server._get_connection")`` and have
    every tool pick up the patched callable.
    """
    global _conn_mgr  # noqa: PLW0603
    if _conn_mgr is None:
        config_path_str = os.environ.get("VMWARE_NSX_CONFIG")
        config_path = Path(config_path_str) if config_path_str else None
        config = load_config(config_path)
        _conn_mgr = ConnectionManager(config)
    return _conn_mgr.connect(target)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------
#
# Importing the tool package executes every ``@mcp.tool`` decorator, registering
# the tools on the shared ``mcp`` instance. This import must follow the
# ``_get_connection`` definition above: the tool modules import this module to
# resolve ``server._get_connection`` at *call* time, so a partially-initialised
# module is fine as long as the helper already exists.

from mcp_server import tools  # noqa: E402

# Re-export every tool callable into this module's namespace so existing
# imports (``from mcp_server.server import create_tier1_gateway``) and tests
# (``getattr(srv, "delete_segment")``) keep working after the split.
for _mod in (
    tools.inventory,
    tools.networking,
    tools.health,
    tools.troubleshoot,
    tools.segment,
    tools.gateway,
    tools.nat,
    tools.route,
    tools.ip_pool,
):
    for _name in vars(_mod):
        if not _name.startswith("_"):
            _obj = getattr(_mod, _name)
            if callable(_obj) and getattr(_obj, "__module__", "") == _mod.__name__:
                globals()[_name] = _obj
del _mod, _name, _obj


# ---------------------------------------------------------------------------
# Read-only gate
# ---------------------------------------------------------------------------


def _config_read_only() -> Optional[bool]:
    """Best-effort read of ``read_only`` from the config file.

    Runs at import time, when no config file need exist yet (tests, ``--help``,
    smoke checks), so every failure degrades to "not configured" and lets the
    env vars decide. None and False are equivalent here — config is the last
    link in the precedence chain — but None keeps 'not configured'
    distinguishable from 'configured off' in logs and debugging.
    """
    try:
        config_path_str = os.environ.get("VMWARE_NSX_CONFIG")
        config_path = Path(config_path_str) if config_path_str else None
        return load_config(config_path).read_only
    except Exception:  # noqa: BLE001 — absent/unreadable config is not an error here
        return None


# Applied once, after every tool module above has registered. In read-only mode
# the write tools are removed from the registry, so list_tools() never offers
# them — the guarantee is structural rather than a prompt instruction the model
# may ignore (VMware-AIops issue #31).
WITHHELD_WRITE_TOOLS: list[str] = apply_read_only_gate(
    mcp, "vmware-nsx", config_flag=_config_read_only()
)


# ---------------------------------------------------------------------------
# Environment declaration
# ---------------------------------------------------------------------------


_cached_config = mtime_cached_loader("VMWARE_NSX_CONFIG", CONFIG_FILE, load_config)


def _environment_for(target: Optional[str]) -> str:
    """Report the environment a target declares, for policy scoping.

    Policy rules scope by environment ("irreversible work in production needs a
    second person"), and vmware-policy cannot read this skill's config itself.
    Registering this lookup is what lets those rules fire at all. Reloaded on
    config.yaml mtime change so an edit takes effect without restarting the
    server. The config is cached via :func:`vmware_policy.mtime_cached_loader`,
    so repeated tool calls pay one ``os.stat`` instead of a full YAML parse.
    """
    try:
        return _cached_config().environment_for(target)
    except Exception:  # noqa: BLE001 — an unreadable config means "undeclared"
        return ""


set_environment_resolver(_environment_for)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")
