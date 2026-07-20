"""NSX segment & gateway management: create, update, delete segments and Tier-1 gateways."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from vmware_policy import sanitize

if TYPE_CHECKING:
    from vmware_nsx.connection import NsxClient

_log = logging.getLogger("vmware-nsx.segment-mgmt")


def _validate_id(resource_id: str) -> str:
    """Validate resource ID contains only safe characters."""
    if not resource_id or not re.match(r"^[a-zA-Z0-9_-]+$", resource_id):
        raise ValueError(
            f"Invalid resource ID: '{resource_id}'. Only alphanumerics, hyphens and "
            "underscores are allowed — no spaces, slashes or dots, so a policy path "
            "like '/infra/segments/web' is not an ID. Copy an exact ID from "
            "list_segments, list_tier0_gateways or list_tier1_gateways."
        )
    return resource_id


def parse_vlan_ids(vlan_ids: str) -> list[int | str]:
    """Parse a comma-separated VLAN spec into NSX vlan_ids entries.

    Plain numbers become ints; tokens containing '-' (e.g. "100-200") pass
    through as range strings — the NSX Policy API natively accepts VLAN
    ranges. The old `.replace("-", ",")` parse silently turned the range
    '100-200' into the two discrete VLANs 100 and 200.
    """
    parsed: list[int | str] = []
    for token in vlan_ids.split(","):
        token = token.strip()
        if not token:
            continue
        parsed.append(token if "-" in token else int(token))
    return parsed


# ---------------------------------------------------------------------------
# Segment CRUD
# ---------------------------------------------------------------------------


def create_segment(
    client: NsxClient,
    segment_id: str,
    display_name: str,
    transport_zone_path: str,
    gateway_path: str | None = None,
    subnets: list[dict[str, Any]] | None = None,
    vlan_ids: list[int | str] | None = None,
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
        vlan_ids: List of VLAN IDs (for VLAN-backed segments); entries may
                  be ints or range strings like "100-200".

    Returns:
        Created segment dict from NSX API.
    """
    _validate_id(segment_id)

    body: dict[str, Any] = {
        "display_name": sanitize(display_name),
        "transport_zone_path": transport_zone_path,
    }

    if gateway_path:
        body["connectivity_path"] = gateway_path

    if subnets:
        body["subnets"] = []
        for sub in subnets:
            if "gateway_address" not in sub:
                continue
            entry: dict[str, Any] = {"gateway_address": sub["gateway_address"]}
            if sub.get("dhcp_ranges"):
                entry["dhcp_ranges"] = sub["dhcp_ranges"]
            body["subnets"].append(entry)

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
                f"Field '{key}' is not updatable on a segment. Allowed: "
                f"{', '.join(sorted(allowed_fields))}. Pass only those to "
                "update_segment; run get_segment to see the segment's current values."
            )
        body[key] = value

    if not body:
        raise ValueError(
            "update_segment was called with nothing to change. Pass at least one of: "
            f"{', '.join(sorted(allowed_fields))}. Run get_segment first to see the "
            "segment's current values."
        )

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

    # Safety check: verify no ports are attached. Probe with a single-item
    # page — one attached port is enough to block deletion, so there's no
    # need to drain the whole port collection.
    ports_path = f"/policy/api/v1/infra/segments/{segment_id}/ports"
    probe = client.get_all(ports_path, page_size=1, limit=1)
    if probe:
        # Non-empty: fetch the accurate total and a small id sample for the
        # error message (fall back to what we probed if metadata is absent).
        total = client.get_count(ports_path)
        sample = client.get_all(ports_path, page_size=10, limit=10)
        if total is None:
            total = len(sample)
        return {
            "deleted": False,
            "segment_id": segment_id,
            "error": (
                f"Segment has {total} active port(s). "
                "Detach all ports before deleting."
            ),
            "port_ids": [
                sanitize(p.get("id", "")) for p in sample[:10]
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
    edge_cluster_path: str | None = None,
) -> dict:
    """Create a new Tier-1 gateway via Policy API (PUT).

    Args:
        client: Authenticated NSX API client.
        tier1_id: Unique Tier-1 identifier.
        display_name: Human-readable name.
        tier0_path: Policy path to parent Tier-0 gateway.
        route_advertisement_types: List of route types to advertise
            (e.g., TIER1_CONNECTED, TIER1_STATIC_ROUTES, TIER1_NAT).
        edge_cluster_path: Edge cluster policy path. When given, a
            "default" locale-service is created on the gateway pointing
            at this edge cluster (required for stateful services like NAT).

    Returns:
        Created Tier-1 gateway dict from NSX API.
    """
    _validate_id(tier1_id)

    body: dict[str, Any] = {
        "display_name": sanitize(display_name),
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
                    f"Invalid route advertisement type: '{rt}'. Pass one or more of "
                    "these to create_tier1_gateway / update_tier1_gateway "
                    f"(--advertise on the CLI): {', '.join(sorted(valid_types))}."
                )
        body["route_advertisement_types"] = route_advertisement_types

    path = f"/policy/api/v1/infra/tier-1s/{tier1_id}"
    result = client.put(path, body)

    if edge_cluster_path:
        ls_path = f"{path}/locale-services/default"
        client.put(ls_path, {"edge_cluster_path": edge_cluster_path})

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
                f"Field '{key}' is not updatable on a Tier-1 gateway. Allowed: "
                f"{', '.join(sorted(allowed_fields))}. Pass only those to "
                "update_tier1_gateway; run get_tier1_gateway to see current values."
            )
        body[key] = value

    if not body:
        raise ValueError(
            "update_tier1_gateway was called with nothing to change. Pass at least "
            f"one of: {', '.join(sorted(allowed_fields))}. Run get_tier1_gateway "
            "first to see the gateway's current values."
        )

    path = f"/policy/api/v1/infra/tier-1s/{tier1_id}"
    result = client.patch(path, body)
    _log.info("Updated Tier-1 gateway %s: %s", tier1_id, list(body.keys()))
    return result


def delete_tier1_gateway(client: NsxClient, tier1_id: str) -> dict:
    """Delete a Tier-1 gateway (removing its default locale-service first).

    The Policy API refuses to delete a Tier-1 that still has children;
    create_tier1_gateway may have created a "default" locale-service for
    the edge cluster binding, so it is deleted first (404 ignored).

    Args:
        client: Authenticated NSX API client.
        tier1_id: Tier-1 gateway identifier to delete.

    Returns:
        Dict with deletion status.
    """
    from vmware_nsx.connection import NsxApiError

    _validate_id(tier1_id)

    path = f"/policy/api/v1/infra/tier-1s/{tier1_id}"
    try:
        client.delete(f"{path}/locale-services/default")
    except NsxApiError as exc:
        if exc.status_code != 404:
            raise
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
                f"BGP config key '{key}' is not allowed. Must be one of: "
                f"{', '.join(sorted(allowed_keys))}. Pass only those to "
                "configure_tier0_bgp; BGP neighbours are a separate object this "
                "skill does not create."
            )
        body[key] = value

    if not body:
        raise ValueError(
            "configure_tier0_bgp was called with an empty bgp_config. Pass at least "
            f"one of: {', '.join(sorted(allowed_keys))}. Run get_bgp_neighbors to see "
            "the Tier-0's current BGP state first."
        )

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
