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

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

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

_conn_mgr: ConnectionManager | None = None


def _get_connection(target: str | None = None) -> Any:
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


@mcp.tool()
@vmware_tool(risk_level="low")
def list_segments(target: str | None = None) -> list[dict]:
    """List all NSX network segments with type, subnet, admin state, and port count.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.inventory import list_segments as _list_segments

    client = _get_connection(target)
    return _list_segments(client)


@mcp.tool()
@vmware_tool(risk_level="low")
def get_segment(segment_id: str, target: str | None = None) -> dict:
    """Get detailed info for a specific network segment.

    Args:
        segment_id: The segment ID (policy path name).
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.inventory import get_segment as _get_segment

    client = _get_connection(target)
    return _get_segment(client, segment_id)


@mcp.tool()
@vmware_tool(risk_level="low")
def list_tier0_gateways(target: str | None = None) -> list[dict]:
    """List all Tier-0 gateways with HA mode and transit subnets.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.inventory import list_tier0_gateways as _list_tier0s

    client = _get_connection(target)
    return _list_tier0s(client)


@mcp.tool()
@vmware_tool(risk_level="low")
def get_tier0_gateway(tier0_id: str, target: str | None = None) -> dict:
    """Get detailed info for a specific Tier-0 gateway.

    Args:
        tier0_id: The Tier-0 gateway ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.inventory import get_tier0_gateway as _get_tier0

    client = _get_connection(target)
    return _get_tier0(client, tier0_id)


@mcp.tool()
@vmware_tool(risk_level="low")
def list_tier1_gateways(target: str | None = None) -> list[dict]:
    """List all Tier-1 gateways with linked Tier-0 path and route advertisement.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.inventory import list_tier1_gateways as _list_tier1s

    client = _get_connection(target)
    return _list_tier1s(client)


@mcp.tool()
@vmware_tool(risk_level="low")
def get_tier1_gateway(tier1_id: str, target: str | None = None) -> dict:
    """Get detailed info for a specific Tier-1 gateway.

    Args:
        tier1_id: The Tier-1 gateway ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.inventory import get_tier1_gateway as _get_tier1

    client = _get_connection(target)
    return _get_tier1(client, tier1_id)


@mcp.tool()
@vmware_tool(risk_level="low")
def list_transport_zones(target: str | None = None) -> list[dict]:
    """List all transport zones with type and host switch name.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.inventory import list_transport_zones as _list_tzs

    client = _get_connection(target)
    return _list_tzs(client)


@mcp.tool()
@vmware_tool(risk_level="low")
def list_transport_nodes(target: str | None = None) -> list[dict]:
    """List all transport nodes with type and status.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.inventory import list_transport_nodes as _list_tns

    client = _get_connection(target)
    return _list_tns(client)


@mcp.tool()
@vmware_tool(risk_level="low")
def list_edge_clusters(target: str | None = None) -> list[dict]:
    """List all edge clusters with member count and deployment type.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.inventory import list_edge_clusters as _list_ecs

    client = _get_connection(target)
    return _list_ecs(client)


# ═══════════════════════════════════════════════════════════════════════════════
# READ-ONLY: Networking
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
@vmware_tool(risk_level="low")
def list_nat_rules(tier1_id: str, target: str | None = None) -> list[dict]:
    """List NAT rules on a Tier-1 gateway.

    Args:
        tier1_id: The Tier-1 gateway ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.networking import list_nat_rules as _list_nat

    client = _get_connection(target)
    return _list_nat(client, tier1_id)


@mcp.tool()
@vmware_tool(risk_level="low")
def get_bgp_neighbors(tier0_id: str, target: str | None = None) -> list[dict]:
    """Get BGP neighbors for a Tier-0 gateway with connection state and ASN.

    Args:
        tier0_id: The Tier-0 gateway ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.networking import get_bgp_neighbors as _get_bgp

    client = _get_connection(target)
    return _get_bgp(client, tier0_id)


@mcp.tool()
@vmware_tool(risk_level="low")
def list_static_routes(tier1_id: str, target: str | None = None) -> list[dict]:
    """List static routes on a Tier-1 gateway.

    Args:
        tier1_id: The Tier-1 gateway ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.networking import list_static_routes as _list_routes

    client = _get_connection(target)
    return _list_routes(client, tier1_id)


@mcp.tool()
@vmware_tool(risk_level="low")
def list_ip_pools(target: str | None = None) -> list[dict]:
    """List all IP address pools with subnets and usage summary.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.networking import list_ip_pools as _list_pools

    client = _get_connection(target)
    return _list_pools(client)


@mcp.tool()
@vmware_tool(risk_level="low")
def get_ip_pool_usage(pool_id: str, target: str | None = None) -> dict:
    """Get IP pool allocation usage details (total, allocated, free).

    Args:
        pool_id: The IP pool ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.networking import get_ip_pool_usage as _get_usage

    client = _get_connection(target)
    return _get_usage(client, pool_id)


# ═══════════════════════════════════════════════════════════════════════════════
# READ-ONLY: Health
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
@vmware_tool(risk_level="low")
def list_nsx_alarms(target: str | None = None) -> list[dict]:
    """Get all active NSX alarms with severity, feature, description, and entity.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.health import list_nsx_alarms as _list_alarms

    client = _get_connection(target)
    return _list_alarms(client)


@mcp.tool()
@vmware_tool(risk_level="low")
def get_transport_node_status(node_id: str, target: str | None = None) -> dict:
    """Check status of a specific transport node (connectivity, tunnel status).

    Args:
        node_id: The transport node ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.health import get_transport_node_status as _get_tn_status

    client = _get_connection(target)
    return _get_tn_status(client, node_id)


@mcp.tool()
@vmware_tool(risk_level="low")
def get_edge_cluster_status(cluster_id: str, target: str | None = None) -> dict:
    """Check status of an edge cluster (member health, overall status).

    Args:
        cluster_id: The edge cluster ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.health import get_edge_cluster_status as _get_ec_status

    client = _get_connection(target)
    return _get_ec_status(client, cluster_id)


@mcp.tool()
@vmware_tool(risk_level="low")
def get_nsx_manager_status(target: str | None = None) -> dict:
    """Get NSX Manager cluster status (node health, cluster status, version).

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.health import get_nsx_manager_status as _get_mgr_status

    client = _get_connection(target)
    return _get_mgr_status(client)


# ═══════════════════════════════════════════════════════════════════════════════
# READ-ONLY: Troubleshooting
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
@vmware_tool(risk_level="low")
def get_logical_port_status(port_id: str, target: str | None = None) -> dict:
    """Check logical port operational status (admin state, link state, attachment).

    Args:
        port_id: The logical port ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.troubleshoot import get_logical_port_status as _get_port

    client = _get_connection(target)
    return _get_port(client, port_id)


@mcp.tool()
@vmware_tool(risk_level="low")
def get_segment_port_for_vm(vm_id: str, target: str | None = None) -> dict:
    """Find which segment a VM is attached to via its VIF attachment.

    Args:
        vm_id: The VM external ID (BIOS UUID or instance UUID from vCenter).
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.troubleshoot import get_segment_port_for_vm as _get_vm_seg

    client = _get_connection(target)
    return _get_vm_seg(client, vm_id)


# ═══════════════════════════════════════════════════════════════════════════════
# WRITE: Segment management
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
@vmware_tool(risk_level="medium")
def create_segment(
    segment_id: str,
    display_name: str,
    transport_zone_path: str,
    vlan_ids: str | None = None,
    subnet: str | None = None,
    target: str | None = None,
) -> dict:
    """Create a new network segment.

    Args:
        segment_id: Unique ID for the segment (used in policy path).
        display_name: Human-readable name for the segment.
        transport_zone_path: Full policy path to the transport zone.
        vlan_ids: VLAN ID(s) for VLAN-backed segments (e.g. "100" or "100-200").
        subnet: Gateway CIDR for the segment (e.g. "192.168.1.1/24").
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.segment_mgmt import create_segment as _create

    client = _get_connection(target)
    return _create(
        client, segment_id,
        display_name=display_name,
        transport_zone_path=transport_zone_path,
        vlan_ids=vlan_ids,
        subnet=subnet,
    )


@mcp.tool()
@vmware_tool(risk_level="medium")
def update_segment(
    segment_id: str,
    display_name: str | None = None,
    subnet: str | None = None,
    target: str | None = None,
) -> dict:
    """Update an existing network segment (partial update via PATCH).

    Args:
        segment_id: The segment ID to update.
        display_name: New display name (optional).
        subnet: New gateway CIDR (optional).
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.segment_mgmt import update_segment as _update

    client = _get_connection(target)
    return _update(client, segment_id, display_name=display_name, subnet=subnet)


@mcp.tool()
@vmware_tool(risk_level="high")
def delete_segment(segment_id: str, target: str | None = None) -> str:
    """Delete a network segment. WARNING: This will disconnect all attached VMs.

    Args:
        segment_id: The segment ID to delete.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.segment_mgmt import delete_segment as _delete

    client = _get_connection(target)
    _delete(client, segment_id)
    return f"Segment '{segment_id}' deleted."


# ═══════════════════════════════════════════════════════════════════════════════
# WRITE: Gateway management
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
@vmware_tool(risk_level="medium")
def create_tier1_gateway(
    tier1_id: str,
    display_name: str,
    tier0_path: str | None = None,
    edge_cluster_path: str | None = None,
    route_advertisement: str | None = None,
    target: str | None = None,
) -> dict:
    """Create a new Tier-1 gateway.

    Args:
        tier1_id: Unique ID for the Tier-1 gateway.
        display_name: Human-readable name.
        tier0_path: Policy path to link to a Tier-0 gateway (optional).
        edge_cluster_path: Policy path to an edge cluster for services (optional).
        route_advertisement: Comma-separated route advertisement types (optional).
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.gateway_mgmt import create_tier1_gateway as _create

    client = _get_connection(target)
    return _create(
        client, tier1_id,
        display_name=display_name,
        tier0_path=tier0_path,
        edge_cluster_path=edge_cluster_path,
        route_advertisement=route_advertisement,
    )


@mcp.tool()
@vmware_tool(risk_level="medium")
def update_tier1_gateway(
    tier1_id: str,
    display_name: str | None = None,
    tier0_path: str | None = None,
    route_advertisement: str | None = None,
    target: str | None = None,
) -> dict:
    """Update an existing Tier-1 gateway (partial update via PATCH).

    Args:
        tier1_id: The Tier-1 gateway ID to update.
        display_name: New display name (optional).
        tier0_path: New Tier-0 path to link (optional).
        route_advertisement: New route advertisement types (optional).
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.gateway_mgmt import update_tier1_gateway as _update

    client = _get_connection(target)
    return _update(
        client, tier1_id,
        display_name=display_name,
        tier0_path=tier0_path,
        route_advertisement=route_advertisement,
    )


@mcp.tool()
@vmware_tool(risk_level="high")
def delete_tier1_gateway(tier1_id: str, target: str | None = None) -> str:
    """Delete a Tier-1 gateway. WARNING: This removes all attached segments and NAT rules.

    Args:
        tier1_id: The Tier-1 gateway ID to delete.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.gateway_mgmt import delete_tier1_gateway as _delete

    client = _get_connection(target)
    _delete(client, tier1_id)
    return f"Tier-1 gateway '{tier1_id}' deleted."


@mcp.tool()
@vmware_tool(risk_level="medium")
def configure_tier0_bgp(
    tier0_id: str,
    local_as: int,
    neighbor_address: str,
    remote_as: int,
    hold_time: int = 180,
    keep_alive: int = 60,
    target: str | None = None,
) -> dict:
    """Configure BGP on a Tier-0 gateway (add/update a BGP neighbor).

    Args:
        tier0_id: The Tier-0 gateway ID.
        local_as: Local AS number.
        neighbor_address: BGP neighbor IP address.
        remote_as: Remote AS number.
        hold_time: Hold down time in seconds (default 180).
        keep_alive: Keep alive time in seconds (default 60).
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.gateway_mgmt import configure_tier0_bgp as _configure

    client = _get_connection(target)
    return _configure(
        client, tier0_id,
        local_as=local_as,
        neighbor_address=neighbor_address,
        remote_as=remote_as,
        hold_time=hold_time,
        keep_alive=keep_alive,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# WRITE: NAT management
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
@vmware_tool(risk_level="medium")
def create_nat_rule(
    tier1_id: str,
    rule_id: str,
    action: str = "DNAT",
    source_network: str | None = None,
    destination_network: str | None = None,
    translated_network: str = "",
    target: str | None = None,
) -> dict:
    """Create a NAT rule on a Tier-1 gateway.

    Args:
        tier1_id: The Tier-1 gateway ID.
        rule_id: Unique ID for the NAT rule.
        action: NAT action: "SNAT", "DNAT", or "REFLEXIVE" (default "DNAT").
        source_network: Source network CIDR (required for SNAT).
        destination_network: Destination network CIDR (required for DNAT).
        translated_network: Translated network/IP address.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.nat_mgmt import create_nat_rule as _create

    client = _get_connection(target)
    return _create(
        client, tier1_id, rule_id,
        action=action,
        source_network=source_network,
        destination_network=destination_network,
        translated_network=translated_network,
    )


@mcp.tool()
@vmware_tool(risk_level="high")
def delete_nat_rule(
    tier1_id: str,
    rule_id: str,
    target: str | None = None,
) -> str:
    """Delete a NAT rule from a Tier-1 gateway.

    Args:
        tier1_id: The Tier-1 gateway ID.
        rule_id: The NAT rule ID to delete.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.nat_mgmt import delete_nat_rule as _delete

    client = _get_connection(target)
    _delete(client, tier1_id, rule_id)
    return f"NAT rule '{rule_id}' deleted from '{tier1_id}'."


# ═══════════════════════════════════════════════════════════════════════════════
# WRITE: Route management
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
@vmware_tool(risk_level="medium")
def create_static_route(
    tier1_id: str,
    route_id: str,
    network: str,
    next_hop: str,
    target: str | None = None,
) -> dict:
    """Create a static route on a Tier-1 gateway.

    Args:
        tier1_id: The Tier-1 gateway ID.
        route_id: Unique ID for the static route.
        network: Destination CIDR (e.g. "10.0.0.0/8").
        next_hop: Next hop IP address.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.route_mgmt import create_static_route as _create

    client = _get_connection(target)
    return _create(client, tier1_id, route_id, network=network, next_hop=next_hop)


@mcp.tool()
@vmware_tool(risk_level="high")
def delete_static_route(
    tier1_id: str,
    route_id: str,
    target: str | None = None,
) -> str:
    """Delete a static route from a Tier-1 gateway.

    Args:
        tier1_id: The Tier-1 gateway ID.
        route_id: The static route ID to delete.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.route_mgmt import delete_static_route as _delete

    client = _get_connection(target)
    _delete(client, tier1_id, route_id)
    return f"Static route '{route_id}' deleted from '{tier1_id}'."


# ═══════════════════════════════════════════════════════════════════════════════
# WRITE: IP Pool management
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
@vmware_tool(risk_level="medium")
def create_ip_pool(
    pool_id: str,
    display_name: str,
    start_ip: str,
    end_ip: str,
    cidr: str,
    gateway_ip: str | None = None,
    target: str | None = None,
) -> dict:
    """Create a new IP address pool with a static subnet allocation range.

    Args:
        pool_id: Unique ID for the IP pool.
        display_name: Human-readable name.
        start_ip: Start IP address of the allocation range.
        end_ip: End IP address of the allocation range.
        cidr: Subnet CIDR (e.g. "192.168.1.0/24").
        gateway_ip: Gateway IP for the subnet (optional).
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    from vmware_nsx.ops.ip_pool_mgmt import create_ip_pool as _create

    client = _get_connection(target)
    return _create(
        client, pool_id,
        display_name=display_name,
        start_ip=start_ip,
        end_ip=end_ip,
        cidr=cidr,
        gateway_ip=gateway_ip,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")
