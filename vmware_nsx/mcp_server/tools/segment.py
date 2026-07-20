"""WRITE tools: segment create / update / delete."""

from typing import Optional

from vmware_policy import vmware_tool

from vmware_nsx.mcp_server import server
from vmware_nsx.mcp_server._shared import _DOCTOR_HINT, _safe_error, mcp


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(
    risk_level="medium",
    undo=lambda params, result: {
        "tool": "delete_segment",
        "params": {"segment_id": params.get("segment_id"), "target": params.get("target")},
        "skill": "nsx",
        "note": "Inverse of create_segment: delete the created segment.",
    },
)
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

        client = server._get_connection(target)
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
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


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

        client = server._get_connection(target)
        update_kwargs: dict = {}
        if display_name is not None:
            update_kwargs["display_name"] = display_name
        if subnet is not None:
            update_kwargs["subnets"] = [{"gateway_address": subnet}]
        return _update(client, segment_id, **update_kwargs)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


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

        client = server._get_connection(target)
        _delete(client, segment_id)
        return f"Segment '{segment_id}' deleted."
    except Exception as e:
        return (
            f"Error: the segment was NOT deleted. {_safe_error(e, 'nsx')} "
            f"Run list_segments to confirm '{segment_id}' exists on this target, or "
            f"get_logical_port_status to see whether ports are still attached "
            f"(a segment with attached ports cannot be deleted)."
        )
