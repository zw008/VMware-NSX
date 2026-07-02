"""NSX inventory: segments, gateways, transport zones/nodes, edge clusters."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vmware_policy import sanitize

if TYPE_CHECKING:
    from vmware_nsx.connection import NsxClient

_log = logging.getLogger("vmware-nsx.inventory")

# Default page/limit for list operations — matches the family list-tool
# convention (bounded results, agent narrows with a filter for more).
_DEFAULT_LIST_LIMIT = 50

# Ports embedded in a single-segment detail view are bounded to this many.
_SEGMENT_PORT_SAMPLE = 50


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------


def list_segments(client: NsxClient, limit: int = _DEFAULT_LIST_LIMIT) -> list[dict]:
    """List network segments (bounded to ``limit``, default 50)."""
    items = client.get_all(
        "/policy/api/v1/infra/segments", page_size=limit, limit=limit
    )
    return [
        {
            "id": sanitize(s.get("id", "")),
            "display_name": sanitize(s.get("display_name", "")),
            "type": s.get("type", "ROUTED"),
            "transport_zone_path": sanitize(s.get("transport_zone_path", "")),
            "vlan_ids": s.get("vlan_ids", []),
            "subnet": [
                {
                    "gateway": sub.get("gateway_address", ""),
                    "network": sub.get("network", ""),
                }
                for sub in s.get("subnets", [])
            ],
            "admin_state": s.get("admin_state", "UP"),
            "connectivity_path": sanitize(s.get("connectivity_path", "")),
        }
        for s in items
    ]


def get_segment(client: NsxClient, segment_id: str) -> dict:
    """Get segment details including ports."""
    seg = client.get(f"/policy/api/v1/infra/segments/{segment_id}")
    # Fetch only a bounded sample of ports rather than draining the whole
    # collection just to slice the first N; report the true total from
    # pagination metadata (fall back to what we fetched if it is absent).
    ports_path = f"/policy/api/v1/infra/segments/{segment_id}/ports"
    ports = client.get_all(
        ports_path, page_size=_SEGMENT_PORT_SAMPLE, limit=_SEGMENT_PORT_SAMPLE
    )
    total_port_count = client.get_count(ports_path)
    if total_port_count is None:
        total_port_count = len(ports)
    return {
        "id": sanitize(seg.get("id", "")),
        "display_name": sanitize(seg.get("display_name", "")),
        "type": seg.get("type", "ROUTED"),
        "admin_state": seg.get("admin_state", "UP"),
        "subnets": seg.get("subnets", []),
        "transport_zone_path": sanitize(seg.get("transport_zone_path", "")),
        "connectivity_path": sanitize(seg.get("connectivity_path", "")),
        "vlan_ids": seg.get("vlan_ids", []),
        "port_count": total_port_count,
        "ports": [
            {
                "id": sanitize(p.get("id", "")),
                "display_name": sanitize(p.get("display_name", "")),
                "attachment": p.get("attachment", {}),
            }
            for p in ports
        ],
    }


# ---------------------------------------------------------------------------
# Tier-0 Gateways
# ---------------------------------------------------------------------------


def list_tier0_gateways(
    client: NsxClient, limit: int = _DEFAULT_LIST_LIMIT
) -> list[dict]:
    """List Tier-0 gateways (bounded to ``limit``, default 50)."""
    items = client.get_all(
        "/policy/api/v1/infra/tier-0s", page_size=limit, limit=limit
    )
    return [
        {
            "id": sanitize(t.get("id", "")),
            "display_name": sanitize(t.get("display_name", "")),
            "ha_mode": t.get("ha_mode", ""),
            "failover_mode": t.get("failover_mode", ""),
            "transit_subnets": t.get("transit_subnets", []),
            "internal_transit_subnets": t.get("internal_transit_subnets", []),
        }
        for t in items
    ]


def get_tier0_gateway(client: NsxClient, tier0_id: str) -> dict:
    """Get Tier-0 gateway details."""
    t = client.get(f"/policy/api/v1/infra/tier-0s/{tier0_id}")
    return {
        "id": sanitize(t.get("id", "")),
        "display_name": sanitize(t.get("display_name", "")),
        "ha_mode": t.get("ha_mode", ""),
        "failover_mode": t.get("failover_mode", ""),
        "transit_subnets": t.get("transit_subnets", []),
        "internal_transit_subnets": t.get("internal_transit_subnets", []),
        "rd_admin_field": t.get("rd_admin_field", ""),
    }


# ---------------------------------------------------------------------------
# Tier-1 Gateways
# ---------------------------------------------------------------------------


def list_tier1_gateways(
    client: NsxClient, limit: int = _DEFAULT_LIST_LIMIT
) -> list[dict]:
    """List Tier-1 gateways (bounded to ``limit``, default 50)."""
    items = client.get_all(
        "/policy/api/v1/infra/tier-1s", page_size=limit, limit=limit
    )
    return [
        {
            "id": sanitize(t.get("id", "")),
            "display_name": sanitize(t.get("display_name", "")),
            "tier0_path": sanitize(t.get("tier0_path", "")),
            "failover_mode": t.get("failover_mode", ""),
            "route_advertisement_types": t.get("route_advertisement_types", []),
            "type": t.get("type", ""),
        }
        for t in items
    ]


def get_tier1_gateway(client: NsxClient, tier1_id: str) -> dict:
    """Get Tier-1 gateway details."""
    t = client.get(f"/policy/api/v1/infra/tier-1s/{tier1_id}")
    return {
        "id": sanitize(t.get("id", "")),
        "display_name": sanitize(t.get("display_name", "")),
        "tier0_path": sanitize(t.get("tier0_path", "")),
        "failover_mode": t.get("failover_mode", ""),
        "route_advertisement_types": t.get("route_advertisement_types", []),
        "type": t.get("type", ""),
    }


# ---------------------------------------------------------------------------
# Transport Zones
# ---------------------------------------------------------------------------


def list_transport_zones(
    client: NsxClient, limit: int = _DEFAULT_LIST_LIMIT
) -> list[dict]:
    """List transport zones (bounded to ``limit``, default 50)."""
    path = (
        "/policy/api/v1/infra/sites/default"
        "/enforcement-points/default/transport-zones"
    )
    items = client.get_all(path, page_size=limit, limit=limit)
    return [
        {
            "id": sanitize(tz.get("id", "")),
            "display_name": sanitize(tz.get("display_name", "")),
            # PolicyTransportZone has no host_switch_name field.
            "transport_type": tz.get("tz_type", ""),
        }
        for tz in items
    ]


# ---------------------------------------------------------------------------
# Transport Nodes
# ---------------------------------------------------------------------------


def list_transport_nodes(
    client: NsxClient, limit: int = _DEFAULT_LIST_LIMIT
) -> list[dict]:
    """List transport nodes (ESXi hosts, Edge nodes; bounded to ``limit``)."""
    items = client.get_all(
        "/api/v1/transport-nodes", page_size=limit, limit=limit
    )
    result: list[dict] = []
    for n in items:
        ip_addresses: list[str] = []
        host_switch_spec = n.get("host_switch_spec")
        if host_switch_spec:
            switches = host_switch_spec.get("host_switches", [])
            if switches:
                ip_spec = switches[0].get("ip_assignment_spec", {})
                ip_addresses = ip_spec.get("ip_list", [])

        result.append(
            {
                "id": sanitize(n.get("id", "")),
                "display_name": sanitize(n.get("display_name", "")),
                # Top-level resource_type is always "TransportNode";
                # the node kind lives in node_deployment_info.
                "node_type": (n.get("node_deployment_info") or {}).get(
                    "resource_type", ""
                ),
                "ip_addresses": ip_addresses,
                "maintenance_mode": n.get("maintenance_mode", "DISABLED"),
            }
        )
    return result


# ---------------------------------------------------------------------------
# Edge Clusters
# ---------------------------------------------------------------------------


def list_edge_clusters(
    client: NsxClient, limit: int = _DEFAULT_LIST_LIMIT
) -> list[dict]:
    """List edge clusters (bounded to ``limit``, default 50)."""
    items = client.get_all(
        "/api/v1/edge-clusters", page_size=limit, limit=limit
    )
    return [
        {
            "id": sanitize(ec.get("id", "")),
            "display_name": sanitize(ec.get("display_name", "")),
            "member_count": len(ec.get("members", [])),
            "deployment_type": ec.get("deployment_type", ""),
            "members": [
                {
                    "transport_node_id": sanitize(
                        m.get("transport_node_id", "")
                    ),
                }
                for m in ec.get("members", [])
            ],
        }
        for ec in items
    ]
