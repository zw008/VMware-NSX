"""READ-ONLY troubleshooting tools: logical port status, VM-to-segment mapping."""

from typing import Optional

from vmware_policy import vmware_tool

from mcp_server import server
from mcp_server._shared import _DOCTOR_HINT, _safe_error, mcp


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_logical_port_status(segment_id: str, target: Optional[str] = None) -> dict:
    """[READ] Check realized state of all ports on a segment (first 50 ports).

    For each port returns admin_state, attachment (type/id), and the
    realized state from the Policy API: attached (attachment present),
    realized_bindings_count, and transport_node_ids (nodes realizing the
    port). NSX does not expose a single UP/DOWN flag per segment port —
    an attached port with realized bindings on at least one transport
    node is healthy.

    Args:
        segment_id: The segment ID whose ports to inspect, as returned by
            list_segments.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.troubleshoot import get_logical_port_status as _get_port

        client = server._get_connection(target)
        return _get_port(client, segment_id)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_segment_port_for_vm(vm_display_name: str, target: Optional[str] = None) -> dict:
    """[READ] Find which segment(s) a VM is attached to via its VIF attachments.

    Looks up the VM in the NSX fabric inventory by display name, fetches its
    VIFs (/api/v1/fabric/vifs), and matches segment ports whose attachment id
    equals a VIF's lport_attachment_id. Returns VM info (external_id, host,
    power state) and matched_ports (segment id/name, port id/name).

    Args:
        vm_display_name: The VM display name as shown in vCenter/NSX inventory.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.troubleshoot import get_segment_port_for_vm as _get_vm_seg

        client = server._get_connection(target)
        return _get_vm_seg(client, vm_display_name)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}
