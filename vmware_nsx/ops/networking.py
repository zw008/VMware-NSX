"""NSX networking: NAT rules, BGP neighbors, static routes, IP pools."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vmware_nsx.connection import NsxClient

_log = logging.getLogger("vmware-nsx.networking")

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _sanitize(text: str, max_len: int = 500) -> str:
    """Strip control characters and truncate to max_len."""
    if not text:
        return text
    return _CONTROL_CHAR_RE.sub("", text[:max_len])


# ---------------------------------------------------------------------------
# NAT Rules
# ---------------------------------------------------------------------------


def list_nat_rules(client: NsxClient, tier1_id: str) -> list[dict]:
    """List all user-defined NAT rules on a Tier-1 gateway.

    Args:
        client: Authenticated NSX API client.
        tier1_id: Tier-1 gateway identifier.

    Returns:
        List of NAT rule dicts with id, action, networks, and status.
    """
    path = (
        f"/policy/api/v1/infra/tier-1s/{tier1_id}"
        "/nat/USER/nat-rules"
    )
    items = client.get_all(path)
    return [
        {
            "id": _sanitize(r.get("id", "")),
            "display_name": _sanitize(r.get("display_name", "")),
            "action": r.get("action", ""),
            "source_network": _sanitize(r.get("source_network", "")),
            "destination_network": _sanitize(r.get("destination_network", "")),
            "translated_network": _sanitize(r.get("translated_network", "")),
            "translated_ports": _sanitize(r.get("translated_ports", "")),
            "enabled": r.get("enabled", True),
            "logging": r.get("logging", False),
            "firewall_match": r.get("firewall_match", ""),
            "sequence_number": r.get("sequence_number", 0),
        }
        for r in items
    ]


# ---------------------------------------------------------------------------
# BGP Neighbors
# ---------------------------------------------------------------------------


def get_bgp_neighbors(client: NsxClient, tier0_id: str) -> dict:
    """Get BGP neighbor status for a Tier-0 gateway.

    Uses the Policy API to discover locale-services, then queries the
    Management API for realized BGP neighbor status.

    Args:
        client: Authenticated NSX API client.
        tier0_id: Tier-0 gateway identifier.

    Returns:
        Dict with locale_service info and list of BGP neighbors.
    """
    # Step 1: Get locale-services for this Tier-0
    ls_path = f"/policy/api/v1/infra/tier-0s/{tier0_id}/locale-services"
    locale_services = client.get_all(ls_path)

    if not locale_services:
        return {
            "tier0_id": tier0_id,
            "locale_services": [],
            "bgp_neighbors": [],
            "hint": "No locale-services found on this Tier-0 gateway.",
        }

    first_ls = locale_services[0]
    ls_id = first_ls.get("id", "")

    # Step 2: Get BGP config from Policy API
    bgp_path = (
        f"/policy/api/v1/infra/tier-0s/{tier0_id}"
        f"/locale-services/{ls_id}/bgp"
    )
    try:
        bgp_config = client.get(bgp_path)
    except Exception:
        bgp_config = {}

    # Step 3: Get BGP neighbors from Policy API
    neighbors_path = (
        f"/policy/api/v1/infra/tier-0s/{tier0_id}"
        f"/locale-services/{ls_id}/bgp/neighbors"
    )
    try:
        neighbors = client.get_all(neighbors_path)
    except Exception:
        neighbors = []

    # Step 4: Try to get realized BGP neighbor status via Management API
    bgp_status: list[dict] = []
    try:
        # Get the realized logical router ID for this Tier-0
        status_path = (
            f"/policy/api/v1/infra/tier-0s/{tier0_id}"
            f"/locale-services/{ls_id}/bgp/neighbors/status"
        )
        status_data = client.get(status_path)
        bgp_status = status_data.get("results", [])
    except Exception:
        _log.debug(
            "Could not retrieve BGP neighbor status for tier0=%s",
            tier0_id,
        )

    return {
        "tier0_id": tier0_id,
        "locale_service_id": _sanitize(ls_id),
        "local_as_num": bgp_config.get("local_as_num", ""),
        "enabled": bgp_config.get("enabled", False),
        "graceful_restart": bgp_config.get("graceful_restart_config", {}),
        "neighbors": [
            {
                "id": _sanitize(n.get("id", "")),
                "display_name": _sanitize(n.get("display_name", "")),
                "neighbor_address": _sanitize(n.get("neighbor_address", "")),
                "remote_as_num": n.get("remote_as_num", ""),
                "source_addresses": n.get("source_addresses", []),
                "hold_down_timer": n.get("hold_down_timer", 180),
                "keep_alive_timer": n.get("keep_alive_timer", 60),
            }
            for n in neighbors
        ],
        "neighbor_status": [
            {
                "neighbor_address": _sanitize(
                    s.get("neighbor_address", "")
                ),
                "remote_as_num": s.get("remote_as_number", ""),
                "connection_state": s.get("connection_state", ""),
                "time_since_established": s.get(
                    "time_since_established", 0
                ),
                "messages_received": s.get("total_in_prefix_count", 0),
                "messages_sent": s.get("total_out_prefix_count", 0),
            }
            for s in bgp_status
        ],
    }


# ---------------------------------------------------------------------------
# Static Routes
# ---------------------------------------------------------------------------


def list_static_routes(
    client: NsxClient,
    gateway_id: str,
    gateway_type: str = "tier1",
) -> list[dict]:
    """List static routes on a gateway (Tier-0 or Tier-1).

    Args:
        client: Authenticated NSX API client.
        gateway_id: Gateway identifier.
        gateway_type: Either "tier0" or "tier1" (default "tier1").

    Returns:
        List of static route dicts.
    """
    gw_resource = "tier-0s" if gateway_type == "tier0" else "tier-1s"
    path = f"/policy/api/v1/infra/{gw_resource}/{gateway_id}/static-routes"
    items = client.get_all(path)
    return [
        {
            "id": _sanitize(r.get("id", "")),
            "display_name": _sanitize(r.get("display_name", "")),
            "network": _sanitize(r.get("network", "")),
            "next_hops": [
                {
                    "ip_address": _sanitize(
                        nh.get("ip_address", "")
                    ),
                    "admin_distance": nh.get("admin_distance", 1),
                }
                for nh in r.get("next_hops", [])
            ],
        }
        for r in items
    ]


# ---------------------------------------------------------------------------
# IP Pools
# ---------------------------------------------------------------------------


def list_ip_pools(client: NsxClient) -> list[dict]:
    """List all IP pools.

    Returns:
        List of IP pool dicts with id, display_name, and usage summary.
    """
    items = client.get_all("/policy/api/v1/infra/ip-pools")
    return [
        {
            "id": _sanitize(p.get("id", "")),
            "display_name": _sanitize(p.get("display_name", "")),
            "pool_usage": p.get("pool_usage", {}),
        }
        for p in items
    ]


def get_ip_pool_usage(client: NsxClient, pool_id: str) -> dict:
    """Get IP allocation details for a specific IP pool.

    Args:
        client: Authenticated NSX API client.
        pool_id: IP pool identifier.

    Returns:
        Dict with pool info and list of current allocations.
    """
    path = f"/policy/api/v1/infra/ip-pools/{pool_id}/ip-allocations"
    allocations = client.get_all(path)
    return {
        "pool_id": pool_id,
        "allocation_count": len(allocations),
        "allocations": [
            {
                "id": _sanitize(a.get("id", "")),
                "display_name": _sanitize(a.get("display_name", "")),
                "allocation_ip": _sanitize(a.get("allocation_ip", "")),
            }
            for a in allocations
        ],
    }
