"""NSX segment & gateway management: create, update, delete segments and Tier-1 gateways."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vmware_nsx.connection import NsxClient

_log = logging.getLogger("vmware-nsx.segment-mgmt")

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
# Segment CRUD
# ---------------------------------------------------------------------------


def create_segment(
    client: NsxClient,
    segment_id: str,
    display_name: str,
    transport_zone_path: str,
    gateway_path: str | None = None,
    subnets: list[dict[str, str]] | None = None,
    vlan_ids: list[int] | None = None,
) -> dict:
    """Create a new network segment via Policy API (PUT).

    Args:
        client: Authenticated NSX API client.
        segment_id: Unique segment identifier.
        display_name: Human-readable name.
        transport_zone_path: Policy path to the transport zone.
        gateway_path: Policy path to Tier-0/Tier-1 gateway (for routed segments).
        subnets: List of subnet dicts, each with "gateway_address" and
                 optionally "dhcp_ranges".
        vlan_ids: List of VLAN IDs (for VLAN-backed segments).

    Returns:
        Created segment dict from NSX API.
    """
    _validate_id(segment_id)

    body: dict[str, Any] = {
        "display_name": _sanitize(display_name),
        "transport_zone_path": transport_zone_path,
    }

    if gateway_path:
        body["connectivity_path"] = gateway_path

    if subnets:
        body["subnets"] = [
            {"gateway_address": sub["gateway_address"]}
            for sub in subnets
            if "gateway_address" in sub
        ]

    if vlan_ids:
        body["vlan_ids"] = vlan_ids

    path = f"/policy/api/v1/infra/segments/{segment_id}"
    result = client.put(path, body)
    _log.info("Created segment %s (%s)", segment_id, display_name)
    return result


def update_segment(client: NsxClient, segment_id: str, **kwargs: Any) -> dict:
    """Partial-update an existing segment via PATCH.

    Supported kwargs: display_name, admin_state, subnets, vlan_ids,
    connectivity_path, transport_zone_path.

    Args:
        client: Authenticated NSX API client.
        segment_id: Segment identifier to update.
        **kwargs: Fields to update.

    Returns:
        Updated segment dict from NSX API.
    """
    _validate_id(segment_id)

    allowed_fields = {
        "display_name",
        "admin_state",
        "subnets",
        "vlan_ids",
        "connectivity_path",
        "transport_zone_path",
    }
    body: dict[str, Any] = {}
    for key, value in kwargs.items():
        if key not in allowed_fields:
            raise ValueError(
                f"Field '{key}' is not updatable. "
                f"Allowed: {', '.join(sorted(allowed_fields))}"
            )
        body[key] = value

    if not body:
        raise ValueError("No update fields provided.")

    path = f"/policy/api/v1/infra/segments/{segment_id}"
    result = client.patch(path, body)
    _log.info("Updated segment %s: %s", segment_id, list(body.keys()))
    return result


def delete_segment(client: NsxClient, segment_id: str) -> dict:
    """Delete a segment after verifying no ports are attached.

    Checks for existing ports first to prevent orphaned resources.

    Args:
        client: Authenticated NSX API client.
        segment_id: Segment identifier to delete.

    Returns:
        Dict with deletion status.
    """
    _validate_id(segment_id)

    # Safety check: verify no ports are attached
    ports = client.get_all(
        f"/policy/api/v1/infra/segments/{segment_id}/ports"
    )
    if ports:
        return {
            "deleted": False,
            "segment_id": segment_id,
            "error": (
                f"Segment has {len(ports)} active port(s). "
                "Detach all ports before deleting."
            ),
            "port_ids": [
                _sanitize(p.get("id", "")) for p in ports[:10]
            ],
        }

    path = f"/policy/api/v1/infra/segments/{segment_id}"
    client.delete(path)
    _log.info("Deleted segment %s", segment_id)
    return {"deleted": True, "segment_id": segment_id}


# ---------------------------------------------------------------------------
# Tier-1 Gateway CRUD
# ---------------------------------------------------------------------------


def create_tier1_gateway(
    client: NsxClient,
    tier1_id: str,
    display_name: str,
    tier0_path: str | None = None,
    route_advertisement_types: list[str] | None = None,
) -> dict:
    """Create a new Tier-1 gateway via Policy API (PUT).

    Args:
        client: Authenticated NSX API client.
        tier1_id: Unique Tier-1 identifier.
        display_name: Human-readable name.
        tier0_path: Policy path to parent Tier-0 gateway.
        route_advertisement_types: List of route types to advertise
            (e.g., TIER1_CONNECTED, TIER1_STATIC_ROUTES, TIER1_NAT).

    Returns:
        Created Tier-1 gateway dict from NSX API.
    """
    _validate_id(tier1_id)

    body: dict[str, Any] = {
        "display_name": _sanitize(display_name),
    }

    if tier0_path:
        body["tier0_path"] = tier0_path

    if route_advertisement_types:
        valid_types = {
            "TIER1_CONNECTED",
            "TIER1_STATIC_ROUTES",
            "TIER1_NAT",
            "TIER1_LB_VIP",
            "TIER1_LB_SNAT",
            "TIER1_DNS_FORWARDER_IP",
            "TIER1_IPSEC_LOCAL_ENDPOINT",
        }
        for rt in route_advertisement_types:
            if rt not in valid_types:
                raise ValueError(
                    f"Invalid route advertisement type: '{rt}'. "
                    f"Valid types: {', '.join(sorted(valid_types))}"
                )
        body["route_advertisement_types"] = route_advertisement_types

    path = f"/policy/api/v1/infra/tier-1s/{tier1_id}"
    result = client.put(path, body)
    _log.info("Created Tier-1 gateway %s (%s)", tier1_id, display_name)
    return result


def update_tier1_gateway(
    client: NsxClient,
    tier1_id: str,
    **kwargs: Any,
) -> dict:
    """Partial-update an existing Tier-1 gateway via PATCH.

    Supported kwargs: display_name, tier0_path, route_advertisement_types,
    failover_mode.

    Args:
        client: Authenticated NSX API client.
        tier1_id: Tier-1 gateway identifier to update.
        **kwargs: Fields to update.

    Returns:
        Updated Tier-1 gateway dict from NSX API.
    """
    _validate_id(tier1_id)

    allowed_fields = {
        "display_name",
        "tier0_path",
        "route_advertisement_types",
        "failover_mode",
    }
    body: dict[str, Any] = {}
    for key, value in kwargs.items():
        if key not in allowed_fields:
            raise ValueError(
                f"Field '{key}' is not updatable. "
                f"Allowed: {', '.join(sorted(allowed_fields))}"
            )
        body[key] = value

    if not body:
        raise ValueError("No update fields provided.")

    path = f"/policy/api/v1/infra/tier-1s/{tier1_id}"
    result = client.patch(path, body)
    _log.info("Updated Tier-1 gateway %s: %s", tier1_id, list(body.keys()))
    return result


def delete_tier1_gateway(client: NsxClient, tier1_id: str) -> dict:
    """Delete a Tier-1 gateway.

    Args:
        client: Authenticated NSX API client.
        tier1_id: Tier-1 gateway identifier to delete.

    Returns:
        Dict with deletion status.
    """
    _validate_id(tier1_id)

    path = f"/policy/api/v1/infra/tier-1s/{tier1_id}"
    client.delete(path)
    _log.info("Deleted Tier-1 gateway %s", tier1_id)
    return {"deleted": True, "tier1_id": tier1_id}


# ---------------------------------------------------------------------------
# Tier-0 BGP Configuration
# ---------------------------------------------------------------------------


def configure_tier0_bgp(
    client: NsxClient,
    tier0_id: str,
    locale_service_id: str,
    bgp_config: dict[str, Any],
) -> dict:
    """Update BGP configuration on a Tier-0 gateway's locale-service.

    Args:
        client: Authenticated NSX API client.
        tier0_id: Tier-0 gateway identifier.
        locale_service_id: Locale-service identifier (typically "default").
        bgp_config: BGP configuration dict. Supported keys:
            - local_as_num (str): Local AS number.
            - enabled (bool): Enable/disable BGP.
            - inter_sr_ibgp (bool): Inter-SR iBGP.
            - ecmp (bool): ECMP enabled.
            - graceful_restart_config (dict): Graceful restart settings.

    Returns:
        Updated BGP config dict from NSX API.
    """
    _validate_id(tier0_id)
    _validate_id(locale_service_id)

    allowed_keys = {
        "local_as_num",
        "enabled",
        "inter_sr_ibgp",
        "ecmp",
        "graceful_restart_config",
    }
    body: dict[str, Any] = {}
    for key, value in bgp_config.items():
        if key not in allowed_keys:
            raise ValueError(
                f"BGP config key '{key}' is not allowed. "
                f"Allowed: {', '.join(sorted(allowed_keys))}"
            )
        body[key] = value

    if not body:
        raise ValueError("No BGP configuration fields provided.")

    path = (
        f"/policy/api/v1/infra/tier-0s/{tier0_id}"
        f"/locale-services/{locale_service_id}/bgp"
    )
    result = client.patch(path, body)
    _log.info(
        "Updated BGP config on Tier-0 %s / locale-service %s: %s",
        tier0_id,
        locale_service_id,
        list(body.keys()),
    )
    return result
