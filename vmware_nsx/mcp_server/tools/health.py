"""READ-ONLY health tools: alarms, transport node / edge cluster / manager status."""

from typing import Optional

from vmware_policy import vmware_tool

from vmware_nsx.mcp_server import server
from vmware_nsx.mcp_server._shared import _DOCTOR_HINT, _safe_error, mcp


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_nsx_alarms(severity: str = "MEDIUM", target: Optional[str] = None) -> dict:
    """[READ] Get active NSX alarms at one severity, with feature, description, and entity.

    Note: the NSX severity filter is an EXACT match — "MEDIUM" returns only
    MEDIUM alarms, not MEDIUM-and-above. Query each severity separately to
    build a full picture. Results follow pagination cursors (all alarms at
    that severity are returned).

    Returns a result envelope: the rows under `items`, plus `returned`,
    `limit`, `total` (the collection's result_count, null when the API
    omits it), `truncated` and `hint`. Check `truncated` before describing
    this as the complete set — when it is true, more rows exist.

    Args:
        severity: Exact severity to filter on: LOW, MEDIUM, HIGH, or
            CRITICAL (default "MEDIUM").
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.health import list_alarms as _list_alarms

        client = server._get_connection(target)
        return _list_alarms(client, severity=severity)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_transport_node_status(node_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get realized runtime status of one transport node (ESXi host or Edge node).

    No side effects. Use after list_transport_nodes (which supplies node IDs)
    when a node looks degraded or overlay tunnels are suspect; for cluster-wide
    edge health use get_edge_cluster_status instead. Returns: node_id, status
    (e.g. UP, DEGRADED, DOWN, UNKNOWN), control_connection_status and
    mgmt_connection_status (controller/manager connectivity), tunnel_status
    (status plus up/down/degraded tunnel counts and BFD counters), and
    pnic_status (up/down/degraded pNIC counts). On failure returns
    {"error", "hint"} instead of raising.

    Args:
        node_id: Transport node UUID, as returned by list_transport_nodes.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.health import get_transport_node_status as _get_tn_status

        client = server._get_connection(target)
        return _get_tn_status(client, node_id)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


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

        client = server._get_connection(target)
        return _get_ec_status(client, cluster_id)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_nsx_manager_status(target: Optional[str] = None) -> dict:
    """[READ] Get NSX Manager cluster status (node health, cluster status, version).

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.health import get_manager_status as _get_mgr_status

        client = server._get_connection(target)
        return _get_mgr_status(client)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}
