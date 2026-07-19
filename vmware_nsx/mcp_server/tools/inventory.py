"""READ-ONLY inventory tools: segments, gateways, transport zones/nodes, edge clusters."""

from typing import Optional

from vmware_policy import vmware_tool

from vmware_nsx.mcp_server import server
from vmware_nsx.mcp_server._shared import _DOCTOR_HINT, _safe_error, mcp


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_segments(target: Optional[str] = None) -> dict:
    """[READ] List all NSX network segments with type, subnet, admin state, and port count.

    Returns a result envelope: the rows under `items`, plus `returned`,
    `limit`, `total` (the collection's result_count, null when the API
    omits it), `truncated` and `hint`. Check `truncated` before describing
    this as the complete set — when it is true, more rows exist.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import list_segments as _list_segments

        client = server._get_connection(target)
        return _list_segments(client)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


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

        client = server._get_connection(target)
        return _get_segment(client, segment_id)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_tier0_gateways(target: Optional[str] = None) -> dict:
    """[READ] List all Tier-0 gateways with HA mode and transit subnets.

    Returns a result envelope: the rows under `items`, plus `returned`,
    `limit`, `total` (the collection's result_count, null when the API
    omits it), `truncated` and `hint`. Check `truncated` before describing
    this as the complete set — when it is true, more rows exist.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import list_tier0_gateways as _list_tier0s

        client = server._get_connection(target)
        return _list_tier0s(client)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


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

        client = server._get_connection(target)
        return _get_tier0(client, tier0_id)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_tier1_gateways(target: Optional[str] = None) -> dict:
    """[READ] List all Tier-1 gateways with linked Tier-0 path and route advertisement.

    Returns a result envelope: the rows under `items`, plus `returned`,
    `limit`, `total` (the collection's result_count, null when the API
    omits it), `truncated` and `hint`. Check `truncated` before describing
    this as the complete set — when it is true, more rows exist.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import list_tier1_gateways as _list_tier1s

        client = server._get_connection(target)
        return _list_tier1s(client)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


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

        client = server._get_connection(target)
        return _get_tier1(client, tier1_id)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_transport_zones(target: Optional[str] = None) -> dict:
    """[READ] List all NSX transport zones — the overlay/VLAN boundaries that segments attach to.

    No side effects. Primary use: discover the transport zone required by
    create_segment, whose transport_zone_path is
    "/infra/sites/default/enforcement-points/default/transport-zones/<id>"
    using the id returned here. Returns one dict per zone: id, display_name,
    transport_type (e.g. OVERLAY_STANDARD or VLAN_BACKED).
    All zones are returned (typically under 20; no pagination). On failure
    returns {"error", "hint"} instead of the envelope.

    Returns a result envelope: the rows under `items`, plus `returned`,
    `limit`, `total` (the collection's result_count, null when the API
    omits it), `truncated` and `hint`. Check `truncated` before describing
    this as the complete set — when it is true, more rows exist.

    Args:
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import list_transport_zones as _list_tzs

        client = server._get_connection(target)
        return _list_tzs(client)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_transport_nodes(target: Optional[str] = None) -> dict:
    """[READ] List all transport nodes with type and status.

    Returns a result envelope: the rows under `items`, plus `returned`,
    `limit`, `total` (the collection's result_count, null when the API
    omits it), `truncated` and `hint`. Check `truncated` before describing
    this as the complete set — when it is true, more rows exist.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import list_transport_nodes as _list_tns

        client = server._get_connection(target)
        return _list_tns(client)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_edge_clusters(target: Optional[str] = None) -> dict:
    """[READ] List all edge clusters with member count and deployment type.

    Returns a result envelope: the rows under `items`, plus `returned`,
    `limit`, `total` (the collection's result_count, null when the API
    omits it), `truncated` and `hint`. Check `truncated` before describing
    this as the complete set — when it is true, more rows exist.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.inventory import list_edge_clusters as _list_ecs

        client = server._get_connection(target)
        return _list_ecs(client)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}
