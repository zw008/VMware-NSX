"""READ-ONLY networking tools: NAT rules, BGP neighbors, static routes, IP pools."""

from typing import Optional

from vmware_policy import vmware_tool

from mcp_server import server
from mcp_server._shared import _DOCTOR_HINT, _safe_error, mcp


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_nat_rules(tier1_id: str, target: Optional[str] = None) -> list[dict]:
    """[READ] List NAT rules on a Tier-1 gateway.

    Args:
        tier1_id: The Tier-1 gateway ID.
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.networking import list_nat_rules as _list_nat

        client = server._get_connection(target)
        return _list_nat(client, tier1_id)
    except Exception as e:
        return [{"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_bgp_neighbors(tier0_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get BGP configuration and neighbor status for a Tier-0 gateway.

    No side effects. Use to verify dynamic routing after configure_tier0_bgp or
    when troubleshooting north-south connectivity. Reads the gateway's first
    locale-service, its BGP config and configured neighbors (Policy API), plus
    realized neighbor session state (Management API) where available. Returns
    tier0_id, locale-service info, BGP config (local AS, enabled, ECMP),
    neighbors (peer IP, remote ASN, hold_down_time, keep_alive_time), and
    session status (connection_state, in/out prefix counts); includes a hint
    when the gateway has no locale-services. On failure returns
    {"error", "hint"}.

    Args:
        tier0_id: Tier-0 gateway ID, as returned by list_tier0_gateways.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.networking import get_bgp_neighbors as _get_bgp

        client = server._get_connection(target)
        return _get_bgp(client, tier0_id)
    except Exception as e:
        return [{"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_static_routes(
    tier1_id: str,
    gateway_type: str = "tier1",
    target: Optional[str] = None,
) -> list[dict]:
    """[READ] List static routes on a Tier-0 or Tier-1 gateway.

    Args:
        tier1_id: The gateway ID (Tier-0 or Tier-1, per gateway_type).
        gateway_type: Either "tier0" or "tier1" (default "tier1").
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.networking import list_static_routes as _list_routes

        client = server._get_connection(target)
        return _list_routes(client, tier1_id, gateway_type=gateway_type)
    except Exception as e:
        return [{"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_ip_pools(target: Optional[str] = None) -> list[dict]:
    """[READ] List all IP address pools with subnets and usage summary.

    Args:
        target: Optional NSX Manager target name from config. Uses default if omitted.
    """
    try:
        from vmware_nsx.ops.networking import list_ip_pools as _list_pools

        client = server._get_connection(target)
        return _list_pools(client)
    except Exception as e:
        return [{"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_ip_pool_usage(pool_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get current IP allocations for one IP address pool.

    No side effects. Use after list_ip_pools to see how much of a pool is
    consumed — e.g. when diagnosing TEP address exhaustion or before retiring
    a pool. Returns: pool_id, allocation_count, and allocations — one entry per
    allocated IP with id, display_name, allocation_ip (all allocations
    returned, no pagination). An empty allocations list means the pool is
    unused. On failure returns {"error", "hint"} instead of raising.

    Args:
        pool_id: IP pool ID, as returned by list_ip_pools.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.networking import get_ip_pool_usage as _get_usage

        client = server._get_connection(target)
        return _get_usage(client, pool_id)
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}
