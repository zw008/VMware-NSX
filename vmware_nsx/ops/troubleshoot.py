"""NSX troubleshooting: port status, VM-to-segment mapping."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vmware_policy import sanitize

if TYPE_CHECKING:
    from vmware_nsx.connection import NsxClient

_log = logging.getLogger("vmware-nsx.troubleshoot")


# ---------------------------------------------------------------------------
# Logical Port Status
# ---------------------------------------------------------------------------


def get_logical_port_status(client: NsxClient, segment_id: str) -> dict:
    """Get port status and realized state for all ports on a segment.

    Retrieves ports from the Policy API and their realized operational
    state from the Management API.

    Args:
        client: Authenticated NSX API client.
        segment_id: Segment identifier.

    Returns:
        Dict with segment info, port list, and per-port realized state.
    """
    # Get segment info
    seg = client.get(f"/policy/api/v1/infra/segments/{segment_id}")

    # Get ports on this segment
    ports = client.get_all(
        f"/policy/api/v1/infra/segments/{segment_id}/ports"
    )

    port_details: list[dict] = []
    for p in ports[:50]:  # Limit to 50 ports to avoid excessive API calls
        port_id = p.get("id", "")
        attachment = p.get("attachment", {})

        # Try to get realized state for this port
        realized_state: dict = {}
        try:
            realized_path = (
                f"/policy/api/v1/infra/segments/{segment_id}"
                f"/ports/{port_id}/state"
            )
            realized_state = client.get(realized_path)
        except Exception:
            _log.debug(
                "Could not get realized state for port %s on segment %s",
                port_id,
                segment_id,
            )

        port_details.append(
            {
                "id": sanitize(port_id),
                "display_name": sanitize(p.get("display_name", "")),
                "attachment_type": attachment.get(
                    "type", ""
                ),
                "attachment_id": sanitize(
                    attachment.get("id", "")
                ),
                "admin_state": p.get("admin_state", "UP"),
                # SegmentPortState (NSX 4.2) has no "state" field; report
                # what it actually carries: attachment presence, realized
                # bindings, and the transport nodes realizing the port.
                "realized_state": {
                    "attached": bool(realized_state.get("attachment")),
                    "realized_bindings_count": len(
                        realized_state.get("realized_bindings") or []
                    ),
                    "transport_node_ids": [
                        sanitize(str(t))
                        for t in (
                            realized_state.get("transport_node_ids") or []
                        )
                    ],
                },
            }
        )

    return {
        "segment_id": segment_id,
        "segment_name": sanitize(seg.get("display_name", "")),
        "admin_state": seg.get("admin_state", "UP"),
        "port_count": len(ports),
        "ports": port_details,
    }


# ---------------------------------------------------------------------------
# VM to Segment Port Mapping
# ---------------------------------------------------------------------------


def get_segment_port_for_vm(
    client: NsxClient,
    vm_display_name: str,
) -> dict:
    """Find the segment port(s) associated with a VM by display name.

    Queries the NSX fabric for VM info, then cross-references with
    segment ports to find connectivity.

    Args:
        client: Authenticated NSX API client.
        vm_display_name: VM display name to search for.

    Returns:
        Dict with VM info and associated segment ports.
    """
    sanitized_name = sanitize(vm_display_name, max_len=200)

    # Step 1: Find the VM in NSX fabric
    vm_data = client.get(
        "/api/v1/fabric/virtual-machines",
        params={"display_name": sanitized_name},
    )
    vms = vm_data.get("results", [])

    if not vms:
        return {
            "vm_display_name": sanitized_name,
            "found": False,
            "hint": (
                f"No VM found with display name '{sanitized_name}'. "
                "Verify the VM exists and NSX has discovered it."
            ),
        }

    vm = vms[0]
    vm_external_id = vm.get("external_id", "")

    # Step 2: Get VIFs for this VM — the fabric VirtualMachine object has
    # no virtual_interfaces field; VIFs come from the dedicated endpoint.
    vif_data = client.get(
        "/api/v1/fabric/vifs",
        params={"owner_vm_id": vm_external_id},
    )
    vifs = vif_data.get("results", [])
    vif_attachment_ids = [
        vif.get("lport_attachment_id", "")
        for vif in vifs
        if vif.get("lport_attachment_id")
    ]

    # Step 3: Search for segment ports whose attachment.id matches a VIF's
    # lport_attachment_id.
    segments = client.get_all("/policy/api/v1/infra/segments")

    matched_ports: list[dict] = []
    for seg in segments:
        seg_id = seg.get("id", "")
        try:
            ports = client.get_all(
                f"/policy/api/v1/infra/segments/{seg_id}/ports"
            )
        except Exception as exc:
            _log.debug("Skipping segment %s: port query failed: %s", seg_id, exc)
            continue

        for p in ports:
            attachment = p.get("attachment", {})
            attachment_id = attachment.get("id", "")

            if attachment_id and attachment_id in vif_attachment_ids:
                matched_ports.append(
                    {
                        "segment_id": sanitize(seg_id),
                        "segment_name": sanitize(
                            seg.get("display_name", "")
                        ),
                        "port_id": sanitize(p.get("id", "")),
                        "port_name": sanitize(
                            p.get("display_name", "")
                        ),
                        "attachment_id": sanitize(attachment_id),
                    }
                )

    return {
        "vm_display_name": sanitized_name,
        "found": True,
        "vm_external_id": sanitize(vm_external_id),
        "host_id": sanitize(vm.get("host_id", "")),
        "power_state": vm.get("power_state", ""),
        "matched_ports": matched_ports,
        "port_count": len(matched_ports),
    }
