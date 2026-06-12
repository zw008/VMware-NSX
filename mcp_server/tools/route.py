"""WRITE tools: static route create / delete."""

from typing import Optional

from vmware_policy import vmware_tool

from mcp_server import server
from mcp_server._shared import _DOCTOR_HINT, _safe_error, mcp


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def create_static_route(
    tier1_id: str,
    route_id: str,
    network: str,
    next_hop: str,
    gateway_type: str = "tier1",
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Create a static route on a Tier-0 or Tier-1 gateway via the Policy API.

    Use for destinations not covered by connected or advertised routes (e.g.
    reaching a VPN or external subnet). Note: for the Tier-0 to advertise this
    route upstream, the gateway needs TIER1_STATIC_ROUTES route advertisement
    (set via update_tier1_gateway). Re-running with the same route_id
    overwrites it (PUT semantics). Returns the created route dict; on failure
    returns {"error", "hint"}. Recorded in the audit log (~/.vmware/audit.db).

    Args:
        tier1_id: Gateway ID (Tier-0 or Tier-1, per gateway_type), as returned
            by list_tier0_gateways / list_tier1_gateways.
        route_id: Unique route identifier (alphanumerics, hyphens, underscores only).
        network: Destination network in CIDR notation, e.g. "10.0.0.0/8".
        next_hop: Next-hop IPv4 address, e.g. "192.168.1.254".
        gateway_type: Either "tier0" or "tier1" (default "tier1").
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.nat_route_mgmt import create_static_route as _create

        client = server._get_connection(target)
        return _create(
            client, tier1_id, route_id,
            network=network,
            next_hops=[{"ip_address": next_hop}],
            gateway_type=gateway_type,
        )
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def delete_static_route(
    tier1_id: str,
    route_id: str,
    gateway_type: str = "tier1",
    target: Optional[str] = None,
) -> str:
    """[WRITE] Permanently delete a static route from a Tier-0 or Tier-1 gateway.

    Irreversible: traffic to the route's destination CIDR immediately falls
    back to remaining routes or is dropped. Run list_static_routes on the same
    tier1_id first to confirm the route_id, destination network, and next
    hops, and confirm with the user before deleting. Returns a confirmation
    string on success, or an "Error: ..." string (route or gateway not found,
    connectivity failure). Recorded in the audit log (~/.vmware/audit.db).

    Args:
        tier1_id: Gateway that owns the route (Tier-0 or Tier-1, per gateway_type),
            as returned by list_tier0_gateways / list_tier1_gateways.
        route_id: Static route ID to delete, as returned by list_static_routes.
        gateway_type: Either "tier0" or "tier1" (default "tier1").
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.nat_route_mgmt import delete_static_route as _delete

        client = server._get_connection(target)
        _delete(client, tier1_id, route_id, gateway_type=gateway_type)
        return f"Static route '{route_id}' deleted from '{tier1_id}'."
    except Exception as e:
        return f"Error: {_safe_error(e, 'nsx')} {_DOCTOR_HINT}"
