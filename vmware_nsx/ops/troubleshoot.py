"""NSX troubleshooting: port status, VM-to-segment mapping."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vmware_policy import sanitize

if TYPE_CHECKING:
    from vmware_nsx.connection import NsxClient

_log = logging.getLogger("vmware-nsx.troubleshoot")

# Cap the per-port realized-state round trips: at most this many ports are
# fetched and probed (one GET .../state each), so a busy segment can't turn a
# single call into hundreds of round trips.
_PORT_SAMPLE_LIMIT = 50

# Cap the fallback full-inventory scan (only reached when the Policy search
# API returns nothing). Scanning the whole estate is O(#segments) port lists;
# bound it and warn rather than hammer every segment.
_MAX_SCAN_SEGMENTS = 200


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

    # Fetch only a bounded sample of ports — we make one per-port state call
    # below, so draining the whole collection would be O(#ports) round trips.
    ports_path = f"/policy/api/v1/infra/segments/{segment_id}/ports"
    ports = client.get_all(
        ports_path,
        page_size=_PORT_SAMPLE_LIMIT,
        limit=_PORT_SAMPLE_LIMIT,
    )
    # Report the true total (don't silently drop the count) from pagination
    # metadata; fall back to what we fetched if the API omits result_count.
    total_port_count = client.get_count(ports_path)
    if total_port_count is None:
        total_port_count = len(ports)

    port_details: list[dict] = []
    for p in ports:
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
        "port_count": total_port_count,
        "ports_shown": len(port_details),
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

    # Step 3: Find segment ports whose attachment.id matches a VIF's
    # lport_attachment_id. The Policy search API resolves this directly per
    # VIF instead of an O(segments×ports) full inventory scan; fall back to
    # the scan only if search returns nothing/errors (keeps correctness).
    matched_ports = _search_segment_ports(client, vif_attachment_ids)
    if not matched_ports:
        matched_ports = _scan_segment_ports(client, vif_attachment_ids)

    return {
        "vm_display_name": sanitized_name,
        "found": True,
        "vm_external_id": sanitize(vm_external_id),
        "host_id": sanitize(vm.get("host_id", "")),
        "power_state": vm.get("power_state", ""),
        "matched_ports": matched_ports,
        "port_count": len(matched_ports),
    }


def _format_matched_port(seg_id: str, seg_name: str, port: dict) -> dict:
    """Shape a SegmentPort dict into the matched-port summary."""
    attachment = port.get("attachment", {})
    return {
        "segment_id": sanitize(seg_id),
        "segment_name": sanitize(seg_name),
        "port_id": sanitize(port.get("id", "")),
        "port_name": sanitize(port.get("display_name", "")),
        "attachment_id": sanitize(attachment.get("id", "")),
    }


def _segment_id_from_path(port_path: str) -> str:
    """Extract the segment id from a SegmentPort policy path.

    Path shape: /infra/segments/<seg-id>/ports/<port-id>.
    """
    parts = port_path.split("/")
    if "segments" in parts:
        idx = parts.index("segments")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def _search_segment_ports(
    client: NsxClient,
    vif_attachment_ids: list[str],
) -> list[dict]:
    """Resolve matching segment ports via the Policy search API.

    Issues one search query per VIF attachment id, avoiding a full
    inventory scan. Returns an empty list on any error so the caller can
    fall back to the scan (keeps correctness).
    """
    matched_ports: list[dict] = []
    for attachment_id in vif_attachment_ids:
        query = (
            f"resource_type:SegmentPort AND attachment.id:{attachment_id}"
        )
        try:
            data = client.get(
                "/policy/api/v1/search/query",
                params={"query": query},
            )
        except Exception as exc:
            _log.debug(
                "Segment port search failed for attachment %s: %s",
                attachment_id,
                exc,
            )
            return []

        for port in data.get("results", []):
            seg_id = _segment_id_from_path(port.get("path", ""))
            matched_ports.append(
                _format_matched_port(
                    seg_id, port.get("parent_display_name", ""), port
                )
            )
    return matched_ports


def _scan_segment_ports(
    client: NsxClient,
    vif_attachment_ids: list[str],
) -> list[dict]:
    """Full inventory scan fallback: enumerate every segment's ports.

    Used only when the search API returns nothing/errors. The scan is
    bounded to ``_MAX_SCAN_SEGMENTS`` segments so it cannot fan out across
    the whole estate; if that cap is hit the result may be incomplete and a
    warning is logged advising the caller to narrow the query.
    """
    segments = client.get_all(
        "/policy/api/v1/infra/segments",
        page_size=_MAX_SCAN_SEGMENTS,
        limit=_MAX_SCAN_SEGMENTS,
    )
    if len(segments) >= _MAX_SCAN_SEGMENTS:
        _log.warning(
            "Segment-port fallback scan hit the %d-segment cap; results may "
            "be incomplete. The Policy search API is the reliable path — "
            "narrow the query or check search availability.",
            _MAX_SCAN_SEGMENTS,
        )

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
            attachment_id = p.get("attachment", {}).get("id", "")
            if attachment_id and attachment_id in vif_attachment_ids:
                matched_ports.append(
                    _format_matched_port(seg_id, seg.get("display_name", ""), p)
                )

    return matched_ports
