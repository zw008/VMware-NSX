"""NSX health: alarms, transport node status, edge cluster status, manager cluster."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vmware_policy import sanitize

from vmware_nsx.connection import CollectionTotal
from vmware_nsx.ops._paginate import (
    MAX_LIMIT,
    page_envelope,
    paginate,
    validate_page_args,
)

if TYPE_CHECKING:
    from vmware_nsx.connection import NsxClient

_log = logging.getLogger("vmware-nsx.health")


# ---------------------------------------------------------------------------
# Alarms
# ---------------------------------------------------------------------------


def list_alarms(
    client: NsxClient,
    severity: str = "MEDIUM",
    limit: int = MAX_LIMIT,
    offset: int = 0,
) -> dict:
    """List alarms filtered by severity (exact match).

    Severity levels: LOW, MEDIUM, HIGH, CRITICAL.
    The NSX API severity filter is an exact match — it returns only
    alarms at the specified severity, not higher severities.

    Args:
        client: Authenticated NSX API client.
        severity: Severity filter, exact match (default "MEDIUM").
        limit: Page size, 1..1000. Defaults to 1000 — the connection layer's
            own backstop, so the default fetch is exactly what it was before
            this argument existed: every alarm at the severity, which is what
            makes a health check complete. Pass a smaller value to page. 0 and
            negatives are rejected; there is no "unlimited".
        offset: Alarms to skip. Pass the previous response's ``next_offset``.

    Returns:
        Result envelope with alarm dicts under ``items``, messages sanitized.
        ``total`` is the ListResult ``result_count`` — the number of alarms at
        this severity, which is what says whether the page in hand is all of
        them.

        The envelope carries ``next_offset``: pass it back as ``offset`` for
        the next page and stop when it is ``None``. Do not loop on
        ``truncated`` — that says this page is not the whole set, which stays
        true on the last page of a walk.

        Before 2026-08-30 there was no ``limit`` or ``offset`` here at all.
        The default fetch is unchanged, but an estate with more alarms than
        the 1000-item backstop had the remainder simply unreachable: the
        envelope said ``truncated: true`` and there was no argument that could
        get at what sat behind it.
    """
    valid_severities = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    if severity.upper() not in valid_severities:
        raise ValueError(
            f"Invalid severity '{severity}'. Must be one of: "
            f"{', '.join(sorted(valid_severities))}. Pass one of those to "
            "list_nsx_alarms (CLI: vmware-nsx health alarms --severity HIGH). "
            "The filter is an exact match, not a floor."
        )

    # Management API endpoint for alarms (paginated)
    validate_page_args(limit, offset)
    total = CollectionTotal()
    items = client.get_all(
        "/api/v1/alarms",
        params={"severity": severity.upper()},
        page_size=limit,
        limit=offset + limit,
        total_sink=total,
    )

    rows = [
        {
            "id": sanitize(a.get("id", "")),
            "severity": a.get("severity", ""),
            "status": a.get("status", ""),
            "feature_name": sanitize(a.get("feature_name", "")),
            "event_type": sanitize(a.get("event_type", "")),
            "description": sanitize(a.get("description", ""), max_len=1000),
            "recommended_action": sanitize(
                a.get("recommended_action", ""), max_len=1000
            ),
            "entity_id": sanitize(a.get("entity_id", "")),
            "last_reported_time": a.get("last_reported_time", 0),
            "node_display_name": sanitize(
                a.get("node_display_name", "")
            ),
        }
        for a in paginate(items, limit, offset)
    ]
    return page_envelope(rows, limit=limit, offset=offset, total=total.value)


# ---------------------------------------------------------------------------
# Transport Node Status
# ---------------------------------------------------------------------------


def get_transport_node_status(client: NsxClient, node_id: str) -> dict:
    """Get status of a specific transport node.

    Args:
        client: Authenticated NSX API client.
        node_id: Transport node UUID.

    Returns:
        Dict with node connectivity, tunnel, and pNIC status.
    """
    data = client.get(f"/api/v1/transport-nodes/{node_id}/status")
    # TransportNodeStatus (NSX 4.2): mgmt_connection_status is a plain
    # string; tunnel_status is a TunnelStatusCount; pnic_status and
    # control_connection_status are StatusCount structs.
    tunnel = data.get("tunnel_status") or {}
    pnic = data.get("pnic_status") or {}
    return {
        "node_id": node_id,
        "status": data.get("status", ""),
        "control_connection_status": sanitize(
            (data.get("control_connection_status") or {}).get("status", "")
        ),
        "mgmt_connection_status": sanitize(
            data.get("mgmt_connection_status", "")
        ),
        "tunnel_status": {
            "status": tunnel.get("status", ""),
            "up_count": tunnel.get("up_count", 0),
            "down_count": tunnel.get("down_count", 0),
            "degraded_count": tunnel.get("degraded_count", 0),
            "bfd_status": tunnel.get("bfd_status", {}),
        },
        "pnic_status": {
            "status": pnic.get("status", ""),
            "up_count": pnic.get("up_count", 0),
            "down_count": pnic.get("down_count", 0),
            "degraded_count": pnic.get("degraded_count", 0),
        },
    }


# ---------------------------------------------------------------------------
# Edge Cluster Status
# ---------------------------------------------------------------------------


def get_edge_cluster_status(client: NsxClient, cluster_id: str) -> dict:
    """Get status of an edge cluster and its member nodes.

    Args:
        client: Authenticated NSX API client.
        cluster_id: Edge cluster UUID.

    Returns:
        Dict with overall cluster status and per-member status.
    """
    data = client.get(f"/api/v1/edge-clusters/{cluster_id}/status")
    members = data.get("member_status", [])
    return {
        "cluster_id": cluster_id,
        "edge_cluster_status": data.get("edge_cluster_status", ""),
        "member_count": len(members),
        "members": [
            {
                # EdgeClusterMemberStatus.transport_node is a
                # ResourceReference (target_id / target_display_name).
                "transport_node_id": sanitize(
                    (m.get("transport_node") or {}).get("target_id", "")
                ),
                "transport_node_name": sanitize(
                    (m.get("transport_node") or {}).get(
                        "target_display_name", ""
                    )
                ),
                "status": m.get("status", ""),
            }
            for m in members
        ],
    }


# ---------------------------------------------------------------------------
# Manager Cluster Status
# ---------------------------------------------------------------------------


def get_manager_status(client: NsxClient) -> dict:
    """Get NSX Manager cluster status.

    Returns:
        Dict with cluster health, control/mgmt plane status, and node info.
    """
    data = client.get("/api/v1/cluster/status")
    nodes = data.get("mgmt_cluster_status", {}).get("online_nodes", [])
    return {
        "cluster_id": sanitize(data.get("cluster_id", "")),
        "overall_status": data.get("detailed_cluster_status", {}).get(
            "overall_status", ""
        ),
        "control_cluster_status": data.get(
            "control_cluster_status", {}
        ).get("status", ""),
        "mgmt_cluster_status": data.get(
            "mgmt_cluster_status", {}
        ).get("status", ""),
        "online_node_count": len(nodes),
        "nodes": [
            {
                "uuid": sanitize(n.get("uuid", "")),
                # ManagementPlaneBaseNodeInfo.mgmt_cluster_listen_ip_address
                # is a plain string in NSX 4.2.
                "mgmt_cluster_listen_ip_address": sanitize(
                    n.get("mgmt_cluster_listen_ip_address", "")
                ),
            }
            for n in nodes
        ],
        "groups": [
            {
                "group_id": sanitize(g.get("group_id", "")),
                "group_status": g.get("group_status", ""),
                "group_type": g.get("group_type", ""),
            }
            for g in data.get("detailed_cluster_status", {}).get(
                "groups", []
            )
        ],
    }
