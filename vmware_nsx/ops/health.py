"""NSX health: alarms, transport node status, edge cluster status, manager cluster."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vmware_policy import sanitize

if TYPE_CHECKING:
    from vmware_nsx.connection import NsxClient

_log = logging.getLogger("vmware-nsx.health")


# ---------------------------------------------------------------------------
# Alarms
# ---------------------------------------------------------------------------


def list_alarms(
    client: NsxClient,
    severity: str = "MEDIUM",
) -> list[dict]:
    """List alarms filtered by minimum severity.

    Severity levels (ascending): LOW, MEDIUM, HIGH, CRITICAL.
    The filter returns alarms at the specified severity and above.

    Args:
        client: Authenticated NSX API client.
        severity: Minimum severity filter (default "MEDIUM").

    Returns:
        List of alarm dicts with sanitized messages.
    """
    valid_severities = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    if severity.upper() not in valid_severities:
        raise ValueError(
            f"Invalid severity '{severity}'. "
            f"Must be one of: {', '.join(sorted(valid_severities))}"
        )

    # Management API endpoint for alarms
    data = client.get(
        "/api/v1/alarms",
        params={"severity": severity.upper()},
    )
    items = data.get("results", [])

    return [
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
        for a in items
    ]


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
    return {
        "node_id": node_id,
        "status": data.get("status", ""),
        "node_deployment_state": data.get("node_deployment_state", {}),
        "control_connection_status": sanitize(
            data.get("control_connection_status", {}).get("status", "")
        ),
        "mgmt_connection_status": sanitize(
            data.get("mgmt_connection_status", {}).get("status", "")
        ),
        "tunnel_status": {
            "status": data.get("host_node_deployment_status", {}).get(
                "lcp_connectivity_status", ""
            ),
            "bfd_status": data.get("host_node_deployment_status", {}).get(
                "lcp_connectivity_status_details", []
            ),
        },
        "pnic_status": data.get("pnic_bond_status", []),
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
                "transport_node_id": sanitize(
                    m.get("transport_node_id", "")
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
                "mgmt_cluster_listen_addr": sanitize(
                    n.get("mgmt_cluster_listen_addr", {}).get(
                        "ip_address", ""
                    )
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
