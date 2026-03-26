"""NSX NAT & route management: create/delete NAT rules, static routes, IP pools."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vmware_nsx.connection import NsxClient

_log = logging.getLogger("vmware-nsx.nat-route-mgmt")

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _sanitize(text: str, max_len: int = 500) -> str:
    """Strip control characters and truncate to max_len."""
    if not text:
        return text
    return _CONTROL_CHAR_RE.sub("", text[:max_len])


def _validate_id(resource_id: str) -> str:
    """Validate resource ID contains only safe characters."""
    if not resource_id or not re.match(r"^[a-zA-Z0-9_-]+$", resource_id):
        raise ValueError(
            f"Invalid resource ID: '{resource_id}'. "
            "Only alphanumeric, hyphens, and underscores are allowed."
        )
    return resource_id


# ---------------------------------------------------------------------------
# NAT Rules
# ---------------------------------------------------------------------------


def create_nat_rule(
    client: NsxClient,
    tier1_id: str,
    rule_id: str,
    action: str,
    source_network: str | None = None,
    destination_network: str | None = None,
    translated_network: str | None = None,
) -> dict:
    """Create a NAT rule on a Tier-1 gateway via Policy API (PUT).

    Args:
        client: Authenticated NSX API client.
        tier1_id: Tier-1 gateway identifier.
        rule_id: Unique NAT rule identifier.
        action: NAT action type. One of: SNAT, DNAT, REFLEXIVE,
                NO_SNAT, NO_DNAT, NAT64.
        source_network: Source CIDR for matching (used in SNAT/NO_SNAT).
        destination_network: Destination CIDR for matching (used in DNAT/NO_DNAT).
        translated_network: Translated IP/CIDR (required for SNAT/DNAT).

    Returns:
        Created NAT rule dict from NSX API.
    """
    _validate_id(tier1_id)
    _validate_id(rule_id)

    valid_actions = {
        "SNAT",
        "DNAT",
        "REFLEXIVE",
        "NO_SNAT",
        "NO_DNAT",
        "NAT64",
    }
    if action not in valid_actions:
        raise ValueError(
            f"Invalid NAT action: '{action}'. "
            f"Must be one of: {', '.join(sorted(valid_actions))}"
        )

    body: dict[str, Any] = {
        "action": action,
        "enabled": True,
    }

    if source_network:
        body["source_network"] = source_network
    if destination_network:
        body["destination_network"] = destination_network
    if translated_network:
        body["translated_network"] = translated_network

    # Validate required fields based on action
    if action in ("SNAT", "DNAT") and not translated_network:
        raise ValueError(
            f"translated_network is required for {action} rules."
        )

    path = (
        f"/policy/api/v1/infra/tier-1s/{tier1_id}"
        f"/nat/USER/nat-rules/{rule_id}"
    )
    result = client.put(path, body)
    _log.info(
        "Created NAT rule %s (%s) on Tier-1 %s",
        rule_id,
        action,
        tier1_id,
    )
    return result


def delete_nat_rule(
    client: NsxClient,
    tier1_id: str,
    rule_id: str,
) -> dict:
    """Delete a NAT rule from a Tier-1 gateway.

    Args:
        client: Authenticated NSX API client.
        tier1_id: Tier-1 gateway identifier.
        rule_id: NAT rule identifier to delete.

    Returns:
        Dict with deletion status.
    """
    _validate_id(tier1_id)
    _validate_id(rule_id)

    path = (
        f"/policy/api/v1/infra/tier-1s/{tier1_id}"
        f"/nat/USER/nat-rules/{rule_id}"
    )
    client.delete(path)
    _log.info("Deleted NAT rule %s from Tier-1 %s", rule_id, tier1_id)
    return {"deleted": True, "tier1_id": tier1_id, "rule_id": rule_id}


# ---------------------------------------------------------------------------
# Static Routes
# ---------------------------------------------------------------------------


def create_static_route(
    client: NsxClient,
    gateway_id: str,
    route_id: str,
    network: str,
    next_hops: list[dict[str, Any]],
    gateway_type: str = "tier1",
) -> dict:
    """Create a static route on a gateway via Policy API (PUT).

    Args:
        client: Authenticated NSX API client.
        gateway_id: Gateway identifier (Tier-0 or Tier-1).
        route_id: Unique static route identifier.
        network: Destination CIDR (e.g., "10.0.0.0/8").
        next_hops: List of next-hop dicts, each containing:
            - ip_address (str): Next-hop IP address.
            - admin_distance (int, optional): Admin distance (default 1).
        gateway_type: Either "tier0" or "tier1" (default "tier1").

    Returns:
        Created static route dict from NSX API.
    """
    _validate_id(gateway_id)
    _validate_id(route_id)

    if not next_hops:
        raise ValueError("At least one next_hop is required.")

    gw_resource = "tier-0s" if gateway_type == "tier0" else "tier-1s"

    body: dict[str, Any] = {
        "network": network,
        "next_hops": [
            {
                "ip_address": nh["ip_address"],
                "admin_distance": nh.get("admin_distance", 1),
            }
            for nh in next_hops
        ],
    }

    path = (
        f"/policy/api/v1/infra/{gw_resource}/{gateway_id}"
        f"/static-routes/{route_id}"
    )
    result = client.put(path, body)
    _log.info(
        "Created static route %s (%s) on %s %s",
        route_id,
        network,
        gateway_type,
        gateway_id,
    )
    return result


def delete_static_route(
    client: NsxClient,
    gateway_id: str,
    route_id: str,
    gateway_type: str = "tier1",
) -> dict:
    """Delete a static route from a gateway.

    Args:
        client: Authenticated NSX API client.
        gateway_id: Gateway identifier.
        route_id: Static route identifier to delete.
        gateway_type: Either "tier0" or "tier1" (default "tier1").

    Returns:
        Dict with deletion status.
    """
    _validate_id(gateway_id)
    _validate_id(route_id)

    gw_resource = "tier-0s" if gateway_type == "tier0" else "tier-1s"
    path = (
        f"/policy/api/v1/infra/{gw_resource}/{gateway_id}"
        f"/static-routes/{route_id}"
    )
    client.delete(path)
    _log.info(
        "Deleted static route %s from %s %s",
        route_id,
        gateway_type,
        gateway_id,
    )
    return {
        "deleted": True,
        "gateway_id": gateway_id,
        "gateway_type": gateway_type,
        "route_id": route_id,
    }


# ---------------------------------------------------------------------------
# IP Pools
# ---------------------------------------------------------------------------


def create_ip_pool(
    client: NsxClient,
    pool_id: str,
    display_name: str,
    subnets: list[dict[str, Any]],
) -> dict:
    """Create an IP pool via Policy API (PUT).

    Args:
        client: Authenticated NSX API client.
        pool_id: Unique IP pool identifier.
        display_name: Human-readable name.
        subnets: List of subnet dicts, each containing:
            - allocation_ranges (list[dict]): Each with "start" and "end" IPs.
            - cidr (str): Subnet CIDR (e.g., "192.168.1.0/24").
            - gateway_ip (str, optional): Gateway IP for the subnet.

    Returns:
        Created IP pool dict from NSX API.
    """
    _validate_id(pool_id)

    if not subnets:
        raise ValueError("At least one subnet is required.")

    # Validate subnet structure
    for sub in subnets:
        if "allocation_ranges" not in sub or "cidr" not in sub:
            raise ValueError(
                "Each subnet must have 'allocation_ranges' and 'cidr'. "
                "allocation_ranges: [{start: ip, end: ip}], cidr: x.x.x.x/y"
            )

    body: dict[str, Any] = {
        "display_name": _sanitize(display_name),
    }

    path = f"/policy/api/v1/infra/ip-pools/{pool_id}"
    result = client.put(path, body)

    # Create IP subnets as sub-resources (IpAddressPoolStaticSubnet)
    for idx, sub in enumerate(subnets):
        subnet_id = f"{pool_id}-subnet-{idx}"
        subnet_body: dict[str, Any] = {
            "resource_type": "IpAddressPoolStaticSubnet",
            "display_name": f"{display_name} subnet {idx}",
            "cidr": sub["cidr"],
            "allocation_ranges": [
                {"start": r["start"], "end": r["end"]}
                for r in sub["allocation_ranges"]
            ],
        }
        if "gateway_ip" in sub:
            subnet_body["gateway_ip"] = sub["gateway_ip"]

        subnet_path = (
            f"/policy/api/v1/infra/ip-pools/{pool_id}"
            f"/ip-subnets/{subnet_id}"
        )
        client.put(subnet_path, subnet_body)

    _log.info(
        "Created IP pool %s (%s) with %d subnet(s)",
        pool_id,
        display_name,
        len(subnets),
    )
    return result
