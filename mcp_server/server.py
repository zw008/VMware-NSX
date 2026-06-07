"""MCP server wrapping VMware NSX networking operations.

This module exposes VMware NSX network management tools via the Model
Context Protocol (MCP) using stdio transport.  Each ``@mcp.tool()``
function delegates to the corresponding function in the ``vmware_nsx``
package (ops.inventory, ops.networking, ops.health, ops.troubleshoot,
ops.segment_mgmt, ops.gateway_mgmt, ops.nat_mgmt, ops.route_mgmt,
ops.ip_pool_mgmt).

Tool categories
---------------
* **Read-only** (no side effects): list_segments, get_segment,
  list_tier0_gateways, list_tier1_gateways, list_transport_zones,
  list_transport_nodes, list_edge_clusters, list_nat_rules,
  get_bgp_neighbors, list_static_routes, list_ip_pools,
  get_ip_pool_usage, list_nsx_alarms, get_transport_node_status,
  get_edge_cluster_status, get_nsx_manager_status,
  get_logical_port_status, get_segment_port_for_vm

* **Write** (mutate state): create_segment, update_segment,
  delete_segment, create_tier1_gateway, update_tier1_gateway,
  delete_tier1_gateway, configure_tier0_bgp, create_nat_rule,
  delete_nat_rule, create_static_route, delete_static_route,
  create_ip_pool — should be gated by the AI agent's confirmation flow.

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

from mcp.server.fastmcp import FastMCP
from vmware_policy import vmware_tool

from vmware_nsx.config import load_config
from vmware_nsx.connection import ConnectionManager

logger = logging.getLogger(__name__)

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

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

_conn_mgr: Optional[ConnectionManager] = None


def _get_connection(target: Optional[str] = None) -> Any:
    """Return an NsxClient, lazily initialising the connection manager."""
    global _conn_mgr  # noqa: PLW0603
    if _conn_mgr is None:
        config_path_str = os.environ.get("VMWARE_NSX_CONFIG")
        config_path = Path(config_path_str) if config_path_str else None
        config = load_config(config_path)
        _conn_mgr = ConnectionManager(config)
    return _conn_mgr.connect(target)


# ═══════════════════════════════════════════════════════════════════════════════
# READ-ONLY: Inventory
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_segments(target: Optional[str] = None) -> list[dict]:
    """[READ] List all NSX network segments with type, subnet, admin state, and port count.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import list_segments as _list_segments

        client = _get_connection(target)
        return _list_segments(client)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_segment(segment_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get full details for one network segment, including its attached ports.

    No side effects. Use after list_segments to inspect a single segment — e.g.
    check port_count before delete_segment (segments with attached ports refuse
    deletion). Returns: id, display_name, type, admin_state, subnets,
    transport_zone_path, connectivity_path (linked gateway), vlan_ids,
    port_count, and the first 50 ports (id, display_name, attachment).
    On failure returns {"error", "hint"} instead of raising.

    Args:
        segment_id: Segment ID — the final component of the policy path
            /infra/segments/<id>, as returned by list_segments.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import get_segment as _get_segment

        client = _get_connection(target)
        return _get_segment(client, segment_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_tier0_gateways(target: Optional[str] = None) -> list[dict]:
    """[READ] List all Tier-0 gateways with HA mode and transit subnets.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import list_tier0_gateways as _list_tier0s

        client = _get_connection(target)
        return _list_tier0s(client)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_tier0_gateway(tier0_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get configuration details for one Tier-0 gateway (north-south edge router).

    No side effects. Use after list_tier0_gateways to inspect HA configuration,
    or to build the tier0_path ("/infra/tier-0s/<id>") that create_tier1_gateway
    needs. For BGP peering state use get_bgp_neighbors instead. Returns: id,
    display_name, ha_mode (ACTIVE_ACTIVE or ACTIVE_STANDBY), failover_mode
    (PREEMPTIVE or NON_PREEMPTIVE), transit_subnets, internal_transit_subnets,
    rd_admin_field. On failure returns {"error", "hint"} instead of raising.

    Args:
        tier0_id: Tier-0 gateway ID, as returned by list_tier0_gateways.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import get_tier0_gateway as _get_tier0

        client = _get_connection(target)
        return _get_tier0(client, tier0_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_tier1_gateways(target: Optional[str] = None) -> list[dict]:
    """[READ] List all Tier-1 gateways with linked Tier-0 path and route advertisement.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import list_tier1_gateways as _list_tier1s

        client = _get_connection(target)
        return _list_tier1s(client)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_tier1_gateway(tier1_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get detailed info for a specific Tier-1 gateway.

    Args:
        tier1_id: The Tier-1 gateway ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import get_tier1_gateway as _get_tier1

        client = _get_connection(target)
        return _get_tier1(client, tier1_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_transport_zones(target: Optional[str] = None) -> list[dict]:
    """[READ] List all NSX transport zones — the overlay/VLAN boundaries that segments attach to.

    No side effects. Primary use: discover the transport zone required by
    create_segment, whose transport_zone_path is
    "/infra/sites/default/enforcement-points/default/transport-zones/<id>"
    using the id returned here. Returns one dict per zone: id, display_name,
    transport_type (e.g. OVERLAY_STANDARD or VLAN_BACKED), host_switch_name.
    All zones are returned (typically under 20; no pagination). On failure
    returns a single-element list containing {"error", "hint"}.

    Args:
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import list_transport_zones as _list_tzs

        client = _get_connection(target)
        return _list_tzs(client)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_transport_nodes(target: Optional[str] = None) -> list[dict]:
    """[READ] List all transport nodes with type and status.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import list_transport_nodes as _list_tns

        client = _get_connection(target)
        return _list_tns(client)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_edge_clusters(target: Optional[str] = None) -> list[dict]:
    """[READ] List all edge clusters with member count and deployment type.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import list_edge_clusters as _list_ecs

        client = _get_connection(target)
        return _list_ecs(client)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}]


# ═══════════════════════════════════════════════════════════════════════════════
# READ-ONLY: Networking
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_nat_rules(tier1_id: str, target: Optional[str] = None) -> list[dict]:
    """[READ] List NAT rules on a Tier-1 gateway.

    Args:
        tier1_id: The Tier-1 gateway ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.networking import list_nat_rules as _list_nat

        client = _get_connection(target)
        return _list_nat(client, tier1_id)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_bgp_neighbors(tier0_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get BGP configuration and neighbor status for a Tier-0 gateway.

    No side effects. Use to verify dynamic routing after configure_tier0_bgp or
    when troubleshooting north-south connectivity. Reads the gateway's first
    locale-service, its BGP config and configured neighbors (Policy API), plus
    realized neighbor session state (Management API) where available. Returns
    tier0_id, locale-service info, BGP config (local AS, enabled, ECMP),
    neighbors (peer IP, remote ASN), and session status; includes a hint when
    the gateway has no locale-services. On failure returns {"error", "hint"}.

    Args:
        tier0_id: Tier-0 gateway ID, as returned by list_tier0_gateways.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.networking import get_bgp_neighbors as _get_bgp

        client = _get_connection(target)
        return _get_bgp(client, tier0_id)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_static_routes(tier1_id: str, target: Optional[str] = None) -> list[dict]:
    """[READ] List static routes on a Tier-1 gateway.

    Args:
        tier1_id: The Tier-1 gateway ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.networking import list_static_routes as _list_routes

        client = _get_connection(target)
        return _list_routes(client, tier1_id)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_ip_pools(target: Optional[str] = None) -> list[dict]:
    """[READ] List all IP address pools with subnets and usage summary.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.networking import list_ip_pools as _list_pools

        client = _get_connection(target)
        return _list_pools(client)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_ip_pool_usage(pool_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get current IP allocations for one IP address pool.

    No side effects. Use after list_ip_pools to see how much of a pool is
    consumed — e.g. when diagnosing TEP address exhaustion or before retiring
    a pool. Returns: pool_id, allocation_count, and allocations — one entry per
    allocated IP with id, display_name, allocation_ip (all allocations
    returned, no pagination). An empty allocations list means the pool is
    unused. On failure returns {"error", "hint"} instead of raising.

    Args:
        pool_id: IP pool ID, as returned by list_ip_pools.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.networking import get_ip_pool_usage as _get_usage

        client = _get_connection(target)
        return _get_usage(client, pool_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


# ═══════════════════════════════════════════════════════════════════════════════
# READ-ONLY: Health
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_nsx_alarms(target: Optional[str] = None) -> list[dict]:
    """[READ] Get all active NSX alarms with severity, feature, description, and entity.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.health import list_alarms as _list_alarms

        client = _get_connection(target)
        return _list_alarms(client)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_transport_node_status(node_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get realized runtime status of one transport node (ESXi host or Edge node).

    No side effects. Use after list_transport_nodes (which supplies node IDs)
    when a node looks degraded or overlay tunnels are suspect; for cluster-wide
    edge health use get_edge_cluster_status instead. Returns: node_id, status
    (e.g. UP, DEGRADED, DOWN, UNKNOWN), node_deployment_state,
    control_connection_status and mgmt_connection_status (controller/manager
    connectivity), tunnel_status (LCP connectivity plus BFD details), and
    pnic_status. On failure returns {"error", "hint"} instead of raising.

    Args:
        node_id: Transport node UUID, as returned by list_transport_nodes.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.health import get_transport_node_status as _get_tn_status

        client = _get_connection(target)
        return _get_tn_status(client, node_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_edge_cluster_status(cluster_id: str, target: Optional[str] = None) -> dict:
    """[READ] Check status of an edge cluster (member health, overall status).

    Args:
        cluster_id: The edge cluster ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.health import get_edge_cluster_status as _get_ec_status

        client = _get_connection(target)
        return _get_ec_status(client, cluster_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_nsx_manager_status(target: Optional[str] = None) -> dict:
    """[READ] Get NSX Manager cluster status (node health, cluster status, version).

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.health import get_manager_status as _get_mgr_status

        client = _get_connection(target)
        return _get_mgr_status(client)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


# ═══════════════════════════════════════════════════════════════════════════════
# READ-ONLY: Troubleshooting
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_logical_port_status(port_id: str, target: Optional[str] = None) -> dict:
    """[READ] Check logical port operational status (admin state, link state, attachment).

    Args:
        port_id: The logical port ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.troubleshoot import get_logical_port_status as _get_port

        client = _get_connection(target)
        return _get_port(client, port_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_segment_port_for_vm(vm_id: str, target: Optional[str] = None) -> dict:
    """[READ] Find which segment a VM is attached to via its VIF attachment.

    Args:
        vm_id: The VM external ID (BIOS UUID or instance UUID from vCenter).
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.troubleshoot import get_segment_port_for_vm as _get_vm_seg

        client = _get_connection(target)
        return _get_vm_seg(client, vm_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


# ═══════════════════════════════════════════════════════════════════════════════
# WRITE: Segment management
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def create_segment(
    segment_id: str,
    display_name: str,
    transport_zone_path: str,
    vlan_ids: Optional[str] = None,
    subnet: Optional[str] = None,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Create a new NSX network segment (overlay or VLAN-backed) via the Policy API.

    Prerequisite: get the transport zone from list_transport_zones first. Pass
    subnet for overlay routed segments, or vlan_ids for VLAN-backed transport
    zones. Re-running with the same segment_id overwrites that segment (PUT
    semantics). Returns the created segment dict (id, display_name, subnets,
    transport_zone_path); on failure returns {"error", "hint"}. The operation
    is recorded in the audit log (~/.vmware/audit.db).

    Args:
        segment_id: Unique segment identifier (alphanumerics, hyphens,
            underscores only); becomes policy path /infra/segments/<segment_id>.
        display_name: Human-readable name shown in the NSX UI.
        transport_zone_path: Full transport zone policy path, e.g.
            "/infra/sites/default/enforcement-points/default/transport-zones/<tz-id>".
        vlan_ids: VLAN ID(s) for VLAN-backed segments, comma- or
            hyphen-separated individual IDs (e.g. "100" or "100,200"). Omit for overlay.
        subnet: Gateway IP in CIDR notation, e.g. "192.168.1.1/24" (the
            gateway address, not the network address). Omit for VLAN-backed segments.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.segment_mgmt import create_segment as _create

        client = _get_connection(target)
        parsed_vlan_ids: Optional[list[int]] = None
        if vlan_ids is not None:
            parsed_vlan_ids = [int(v.strip()) for v in vlan_ids.replace("-", ",").split(",") if v.strip()]
        parsed_subnets: Optional[list[dict[str, str]]] = None
        if subnet is not None:
            parsed_subnets = [{"gateway_address": subnet}]
        return _create(
            client, segment_id,
            display_name=display_name,
            transport_zone_path=transport_zone_path,
            vlan_ids=parsed_vlan_ids,
            subnets=parsed_subnets,
        )
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def update_segment(
    segment_id: str,
    display_name: Optional[str] = None,
    subnet: Optional[str] = None,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Update an existing network segment (partial update via PATCH).

    Args:
        segment_id: The segment ID to update.
        display_name: New display name (optional).
        subnet: New gateway CIDR (optional).
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.segment_mgmt import update_segment as _update

        client = _get_connection(target)
        update_kwargs: dict = {}
        if display_name is not None:
            update_kwargs["display_name"] = display_name
        if subnet is not None:
            update_kwargs["subnets"] = [{"gateway_address": subnet}]
        return _update(client, segment_id, **update_kwargs)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def delete_segment(segment_id: str, target: Optional[str] = None) -> str:
    """[WRITE] Delete a network segment. WARNING: This will disconnect all attached VMs.

    Args:
        segment_id: The segment ID to delete.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.segment_mgmt import delete_segment as _delete

        client = _get_connection(target)
        _delete(client, segment_id)
        return f"Segment '{segment_id}' deleted."
    except Exception as e:
        return f"Error: {e}. Run 'vmware-nsx doctor' to verify connectivity."


# ═══════════════════════════════════════════════════════════════════════════════
# WRITE: Gateway management
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def create_tier1_gateway(
    tier1_id: str,
    display_name: str,
    tier0_path: Optional[str] = None,
    edge_cluster_path: Optional[str] = None,
    route_advertisement: Optional[str] = None,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Create a Tier-1 gateway for routing segments, with optional Tier-0 uplink.

    For north-south reachability, link it to a Tier-0 (get the path from
    list_tier0_gateways). Side effect to note: if route_advertisement is
    omitted, nothing is advertised to the Tier-0, so connected subnets stay
    unreachable from outside until advertisement types are set (here or via
    update_tier1_gateway). Re-running with the same tier1_id overwrites it
    (PUT semantics). Returns the created gateway dict; on failure returns
    {"error", "hint"}. Recorded in the audit log (~/.vmware/audit.db).

    Args:
        tier1_id: Unique gateway identifier (alphanumerics, hyphens,
            underscores only); becomes policy path /infra/tier-1s/<tier1_id>.
        display_name: Human-readable name shown in the NSX UI.
        tier0_path: Parent Tier-0 policy path, e.g. "/infra/tier-0s/<t0-id>".
            Omit to create a standalone (unlinked) gateway.
        edge_cluster_path: Edge cluster policy path for stateful services
            such as NAT, e.g. "/infra/sites/default/enforcement-points/default/
            edge-clusters/<uuid>". Optional.
        route_advertisement: Comma-separated advertisement types. Valid values:
            TIER1_CONNECTED, TIER1_STATIC_ROUTES, TIER1_NAT, TIER1_LB_VIP,
            TIER1_LB_SNAT, TIER1_DNS_FORWARDER_IP, TIER1_IPSEC_LOCAL_ENDPOINT.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.segment_mgmt import create_tier1_gateway as _create

        client = _get_connection(target)
        ra_types = (
            [t.strip() for t in route_advertisement.split(",") if t.strip()]
            if route_advertisement
            else None
        )
        return _create(
            client, tier1_id,
            display_name=display_name,
            tier0_path=tier0_path,
            route_advertisement_types=ra_types,
            edge_cluster_path=edge_cluster_path,
        )
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def update_tier1_gateway(
    tier1_id: str,
    display_name: Optional[str] = None,
    tier0_path: Optional[str] = None,
    route_advertisement: Optional[str] = None,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Partially update an existing Tier-1 gateway via PATCH.

    Only the fields you pass change; omitted fields keep their current values.
    Use get_tier1_gateway first to inspect current config. Typical uses:
    relink the gateway to a different Tier-0, or enable route advertisement on
    a gateway created without it. Re-applying identical values is harmless.
    Returns the updated gateway dict; on failure returns {"error", "hint"}.
    Recorded in the audit log (~/.vmware/audit.db).

    Args:
        tier1_id: Tier-1 gateway ID to update, as returned by list_tier1_gateways.
        display_name: New display name. Optional.
        tier0_path: New parent Tier-0 policy path, e.g. "/infra/tier-0s/<t0-id>". Optional.
        route_advertisement: Comma-separated advertisement types. Valid values:
            TIER1_CONNECTED, TIER1_STATIC_ROUTES, TIER1_NAT, TIER1_LB_VIP,
            TIER1_LB_SNAT, TIER1_DNS_FORWARDER_IP, TIER1_IPSEC_LOCAL_ENDPOINT.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.segment_mgmt import update_tier1_gateway as _update

        client = _get_connection(target)
        updates: dict = {}
        if display_name is not None:
            updates["display_name"] = display_name
        if tier0_path is not None:
            updates["tier0_path"] = tier0_path
        if route_advertisement is not None:
            updates["route_advertisement_types"] = [
                t.strip() for t in route_advertisement.split(",") if t.strip()
            ]
        return _update(client, tier1_id, **updates)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def delete_tier1_gateway(tier1_id: str, target: Optional[str] = None) -> str:
    """[WRITE] Delete a Tier-1 gateway. WARNING: This removes all attached segments and NAT rules.

    Args:
        tier1_id: The Tier-1 gateway ID to delete.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.segment_mgmt import delete_tier1_gateway as _delete

        client = _get_connection(target)
        _delete(client, tier1_id)
        return f"Tier-1 gateway '{tier1_id}' deleted."
    except Exception as e:
        return f"Error: {e}. Run 'vmware-nsx doctor' to verify connectivity."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def configure_tier0_bgp(
    tier0_id: str,
    local_as_num: str,
    enabled: bool = True,
    ecmp: bool = True,
    inter_sr_ibgp: bool = True,
    locale_service_id: str = "default",
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Configure BGP settings on a Tier-0 gateway's locale-service.

    Note: This configures BGP *settings* (local AS, ECMP, graceful restart).
    BGP neighbor creation is a separate Policy API object and not exposed here.

    Args:
        tier0_id: The Tier-0 gateway ID.
        local_as_num: Local AS number as a string (e.g. "65001").
        enabled: Enable or disable BGP on the locale-service (default True).
        ecmp: Enable ECMP for BGP routes (default True).
        inter_sr_ibgp: Enable inter-SR iBGP (default True).
        locale_service_id: Locale-service identifier (default "default").
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.segment_mgmt import configure_tier0_bgp as _configure

        client = _get_connection(target)
        bgp_config = {
            "local_as_num": local_as_num,
            "enabled": enabled,
            "ecmp": ecmp,
            "inter_sr_ibgp": inter_sr_ibgp,
        }
        return _configure(client, tier0_id, locale_service_id, bgp_config)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


# ═══════════════════════════════════════════════════════════════════════════════
# WRITE: NAT management
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def create_nat_rule(
    tier1_id: str,
    rule_id: str,
    action: str = "DNAT",
    source_network: Optional[str] = None,
    destination_network: Optional[str] = None,
    translated_network: str = "",
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Create a NAT rule on a Tier-1 gateway.

    Args:
        tier1_id: The Tier-1 gateway ID.
        rule_id: Unique ID for the NAT rule.
        action: NAT action: "SNAT", "DNAT", or "REFLEXIVE" (default "DNAT").
        source_network: Source network CIDR (required for SNAT).
        destination_network: Destination network CIDR (required for DNAT).
        translated_network: Translated network/IP address.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.nat_route_mgmt import create_nat_rule as _create

        client = _get_connection(target)
        return _create(
            client, tier1_id, rule_id,
            action=action,
            source_network=source_network,
            destination_network=destination_network,
            translated_network=translated_network,
        )
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def delete_nat_rule(
    tier1_id: str,
    rule_id: str,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Permanently delete a NAT rule from a Tier-1 gateway's USER NAT section.

    Irreversible: traffic matched by the rule stops being translated
    immediately, which can break inbound (DNAT) or outbound (SNAT)
    connectivity. Run list_nat_rules on the same tier1_id first to confirm the
    rule_id and review its action and networks, and confirm with the user
    before deleting. Returns a confirmation string on success, or an
    "Error: ..." string (rule or gateway not found, connectivity failure).
    Recorded in the audit log (~/.vmware/audit.db).

    Args:
        tier1_id: Tier-1 gateway that owns the rule, as returned by list_tier1_gateways.
        rule_id: NAT rule ID to delete, as returned by list_nat_rules.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.nat_route_mgmt import delete_nat_rule as _delete

        client = _get_connection(target)
        _delete(client, tier1_id, rule_id)
        return f"NAT rule '{rule_id}' deleted from '{tier1_id}'."
    except Exception as e:
        return f"Error: {e}. Run 'vmware-nsx doctor' to verify connectivity."


# ═══════════════════════════════════════════════════════════════════════════════
# WRITE: Route management
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def create_static_route(
    tier1_id: str,
    route_id: str,
    network: str,
    next_hop: str,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Create a static route on a Tier-1 gateway via the Policy API.

    Use for destinations not covered by connected or advertised routes (e.g.
    reaching a VPN or external subnet). Note: for the Tier-0 to advertise this
    route upstream, the gateway needs TIER1_STATIC_ROUTES route advertisement
    (set via update_tier1_gateway). Re-running with the same route_id
    overwrites it (PUT semantics). Returns the created route dict; on failure
    returns {"error", "hint"}. Recorded in the audit log (~/.vmware/audit.db).

    Args:
        tier1_id: Tier-1 gateway ID, as returned by list_tier1_gateways.
        route_id: Unique route identifier (alphanumerics, hyphens, underscores only).
        network: Destination network in CIDR notation, e.g. "10.0.0.0/8".
        next_hop: Next-hop IPv4 address, e.g. "192.168.1.254".
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.nat_route_mgmt import create_static_route as _create

        client = _get_connection(target)
        return _create(
            client, tier1_id, route_id,
            network=network,
            next_hops=[{"ip_address": next_hop}],
        )
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def delete_static_route(
    tier1_id: str,
    route_id: str,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Permanently delete a static route from a Tier-1 gateway.

    Irreversible: traffic to the route's destination CIDR immediately falls
    back to remaining routes or is dropped. Run list_static_routes on the same
    tier1_id first to confirm the route_id, destination network, and next
    hops, and confirm with the user before deleting. Returns a confirmation
    string on success, or an "Error: ..." string (route or gateway not found,
    connectivity failure). Recorded in the audit log (~/.vmware/audit.db).

    Args:
        tier1_id: Tier-1 gateway that owns the route, as returned by list_tier1_gateways.
        route_id: Static route ID to delete, as returned by list_static_routes.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.nat_route_mgmt import delete_static_route as _delete

        client = _get_connection(target)
        _delete(client, tier1_id, route_id)
        return f"Static route '{route_id}' deleted from '{tier1_id}'."
    except Exception as e:
        return f"Error: {e}. Run 'vmware-nsx doctor' to verify connectivity."


# ═══════════════════════════════════════════════════════════════════════════════
# WRITE: IP Pool management
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def create_ip_pool(
    pool_id: str,
    display_name: str,
    start_ip: str,
    end_ip: str,
    cidr: str,
    gateway_ip: Optional[str] = None,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Create an IP address pool with one static subnet and allocation range.

    IP pools supply addresses to NSX consumers such as tunnel endpoints
    (TEPs). Check list_ip_pools first to avoid overlapping ranges; start_ip
    and end_ip must both fall inside cidr. Re-running with the same pool_id
    overwrites it (PUT semantics). Returns the created pool dict; verify
    consumption later with get_ip_pool_usage. On failure returns
    {"error", "hint"}. Recorded in the audit log (~/.vmware/audit.db).

    Args:
        pool_id: Unique pool identifier (alphanumerics, hyphens, underscores
            only); becomes policy path /infra/ip-pools/<pool_id>.
        display_name: Human-readable name shown in the NSX UI.
        start_ip: First allocatable IPv4 address, e.g. "192.168.1.10".
        end_ip: Last allocatable IPv4 address, e.g. "192.168.1.100".
        cidr: Subnet containing the range, in CIDR notation, e.g. "192.168.1.0/24".
        gateway_ip: Default gateway IP for the subnet, e.g. "192.168.1.1". Optional.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.nat_route_mgmt import create_ip_pool as _create

        client = _get_connection(target)
        subnet: dict = {
            "allocation_ranges": [{"start": start_ip, "end": end_ip}],
            "cidr": cidr,
        }
        if gateway_ip:
            subnet["gateway_ip"] = gateway_ip
        return _create(
            client, pool_id,
            display_name=display_name,
            subnets=[subnet],
        )
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-nsx doctor' to verify connectivity."}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")
