"""WRITE tools: Tier-1 gateway create / update / delete, Tier-0 BGP config."""

from typing import Optional

from vmware_policy import vmware_tool

from mcp_server import server
from mcp_server._shared import _DOCTOR_HINT, _safe_error, mcp


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def create_tier1_gateway(
    tier1_id: str,
    display_name: str,
    tier0_path: Optional[str] = None,
    edge_cluster_path: Optional[str] = None,
    route_advertisement: Optional[str] = None,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Create a Tier-1 gateway for routing segments, with optional Tier-0 uplink.

    For north-south reachability, link it to a Tier-0 (get the path from
    list_tier0_gateways). Side effect to note: if route_advertisement is
    omitted, nothing is advertised to the Tier-0, so connected subnets stay
    unreachable from outside until advertisement types are set (here or via
    update_tier1_gateway). Re-running with the same tier1_id overwrites it
    (PUT semantics). Returns the created gateway dict; on failure returns
    {"error", "hint"}. Recorded in the audit log (~/.vmware/audit.db).

    Args:
        tier1_id: Unique gateway identifier (alphanumerics, hyphens,
            underscores only); becomes policy path /infra/tier-1s/<tier1_id>.
        display_name: Human-readable name shown in the NSX UI.
        tier0_path: Parent Tier-0 policy path, e.g. "/infra/tier-0s/<t0-id>".
            Omit to create a standalone (unlinked) gateway.
        edge_cluster_path: Edge cluster policy path for stateful services
            such as NAT, e.g. "/infra/sites/default/enforcement-points/default/
            edge-clusters/<uuid>". Optional.
        route_advertisement: Comma-separated advertisement types. Valid values:
            TIER1_CONNECTED, TIER1_STATIC_ROUTES, TIER1_NAT, TIER1_LB_VIP,
            TIER1_LB_SNAT, TIER1_DNS_FORWARDER_IP, TIER1_IPSEC_LOCAL_ENDPOINT.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.segment_mgmt import create_tier1_gateway as _create

        client = server._get_connection(target)
        ra_types = (
            [t.strip() for t in route_advertisement.split(",") if t.strip()]
            if route_advertisement
            else None
        )
        return _create(
            client, tier1_id,
            display_name=display_name,
            tier0_path=tier0_path,
            route_advertisement_types=ra_types,
            edge_cluster_path=edge_cluster_path,
        )
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def update_tier1_gateway(
    tier1_id: str,
    display_name: Optional[str] = None,
    tier0_path: Optional[str] = None,
    route_advertisement: Optional[str] = None,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Partially update an existing Tier-1 gateway via PATCH.

    Only the fields you pass change; omitted fields keep their current values.
    Use get_tier1_gateway first to inspect current config. Typical uses:
    relink the gateway to a different Tier-0, or enable route advertisement on
    a gateway created without it. Re-applying identical values is harmless.
    Returns the updated gateway dict; on failure returns {"error", "hint"}.
    Recorded in the audit log (~/.vmware/audit.db).

    Args:
        tier1_id: Tier-1 gateway ID to update, as returned by list_tier1_gateways.
        display_name: New display name. Optional.
        tier0_path: New parent Tier-0 policy path, e.g. "/infra/tier-0s/<t0-id>". Optional.
        route_advertisement: Comma-separated advertisement types. Valid values:
            TIER1_CONNECTED, TIER1_STATIC_ROUTES, TIER1_NAT, TIER1_LB_VIP,
            TIER1_LB_SNAT, TIER1_DNS_FORWARDER_IP, TIER1_IPSEC_LOCAL_ENDPOINT.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.segment_mgmt import update_tier1_gateway as _update

        client = server._get_connection(target)
        updates: dict = {}
        if display_name is not None:
            updates["display_name"] = display_name
        if tier0_path is not None:
            updates["tier0_path"] = tier0_path
        if route_advertisement is not None:
            updates["route_advertisement_types"] = [
                t.strip() for t in route_advertisement.split(",") if t.strip()
            ]
        return _update(client, tier1_id, **updates)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def delete_tier1_gateway(tier1_id: str, target: Optional[str] = None) -> str:
    """[WRITE] Delete a Tier-1 gateway. WARNING: This removes all attached segments and NAT rules.

    Also removes the gateway's "default" locale-service first (the Policy
    API refuses to delete a Tier-1 that still has children); a missing
    locale-service is ignored.

    Args:
        tier1_id: The Tier-1 gateway ID to delete.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.segment_mgmt import delete_tier1_gateway as _delete

        client = server._get_connection(target)
        _delete(client, tier1_id)
        return f"Tier-1 gateway '{tier1_id}' deleted."
    except Exception as e:
        return f"Error: {_safe_error(e, 'nsx')} {_DOCTOR_HINT}"


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def configure_tier0_bgp(
    tier0_id: str,
    local_as_num: str,
    enabled: bool = True,
    ecmp: bool = True,
    inter_sr_ibgp: bool = True,
    locale_service_id: str = "default",
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Configure BGP settings on a Tier-0 gateway's locale-service.

    Note: This configures BGP *settings* (local AS, ECMP, graceful restart).
    BGP neighbor creation is a separate Policy API object and not exposed here.

    Args:
        tier0_id: The Tier-0 gateway ID.
        local_as_num: Local AS number as a string (e.g. "65001").
        enabled: Enable or disable BGP on the locale-service (default True).
        ecmp: Enable ECMP for BGP routes (default True).
        inter_sr_ibgp: Enable inter-SR iBGP (default True).
        locale_service_id: Locale-service identifier (default "default").
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.segment_mgmt import configure_tier0_bgp as _configure

        client = server._get_connection(target)
        bgp_config = {
            "local_as_num": local_as_num,
            "enabled": enabled,
            "ecmp": ecmp,
            "inter_sr_ibgp": inter_sr_ibgp,
        }
        return _configure(client, tier0_id, locale_service_id, bgp_config)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}
