"""NSX inventory: segments, gateways, transport zones/nodes, edge clusters."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vmware_policy import sanitize

if TYPE_CHECKING:
    from vmware_nsx.connection import NsxClient

_log = logging.getLogger("vmware-nsx.inventory")


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------


def list_segments(client: NsxClient) -> list[dict]:
    """List all network segments."""
    items = client.get_all("/policy/api/v1/infra/segments")
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
    # Get ports on this segment
    ports = client.get_all(
        f"/policy/api/v1/infra/segments/{segment_id}/ports"
    )
    return {
        "id": sanitize(seg.get("id", "")),
        "display_name": sanitize(seg.get("display_name", "")),
        "type": seg.get("type", "ROUTED"),
        "admin_state": seg.get("admin_state", "UP"),
        "subnets": seg.get("subnets", []),
        "transport_zone_path": sanitize(seg.get("transport_zone_path", "")),
        "connectivity_path": sanitize(seg.get("connectivity_path", "")),
        "vlan_ids": seg.get("vlan_ids", []),
        "port_count": len(ports),
        "ports": [
            {
                "id": sanitize(p.get("id", "")),
                "display_name": sanitize(p.get("display_name", "")),
                "attachment": p.get("attachment", {}),
            }
            for p in ports[:50]  # Limit to 50 ports
        ],
    }


# ---------------------------------------------------------------------------
# Tier-0 Gateways
# ---------------------------------------------------------------------------


def list_tier0_gateways(client: NsxClient) -> list[dict]:
    """List all Tier-0 gateways."""
    items = client.get_all("/policy/api/v1/infra/tier-0s")
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


def list_tier1_gateways(client: NsxClient) -> list[dict]:
    """List all Tier-1 gateways."""
    items = client.get_all("/policy/api/v1/infra/tier-1s")
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


def list_transport_zones(client: NsxClient) -> list[dict]:
    """List all transport zones."""
    path = (
        "/policy/api/v1/infra/sites/default"
        "/enforcement-points/default/transport-zones"
    )
    items = client.get_all(path)
    return [
        {
            "id": sanitize(tz.get("id", "")),
            "display_name": sanitize(tz.get("display_name", "")),
            "transport_type": tz.get("tz_type", ""),
            "host_switch_name": sanitize(tz.get("host_switch_name", "")),
        }
        for tz in items
    ]


# ---------------------------------------------------------------------------
# Transport Nodes
# ---------------------------------------------------------------------------


def list_transport_nodes(client: NsxClient) -> list[dict]:
    """List all transport nodes (ESXi hosts, Edge nodes)."""
    items = client.get_all("/api/v1/transport-nodes")
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
                "node_type": n.get("resource_type", ""),
                "ip_addresses": ip_addresses,
                "maintenance_mode": n.get("maintenance_mode", "DISABLED"),
            }
        )
    return result


# ---------------------------------------------------------------------------
# Edge Clusters
# ---------------------------------------------------------------------------


def list_edge_clusters(client: NsxClient) -> list[dict]:
    """List all edge clusters."""
    items = client.get_all("/api/v1/edge-clusters")
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
