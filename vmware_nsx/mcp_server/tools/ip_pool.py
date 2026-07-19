"""WRITE tools: IP address pool create / delete."""

from typing import Optional

from vmware_policy import vmware_tool

from vmware_nsx.mcp_server import server
from vmware_nsx.mcp_server._shared import _DOCTOR_HINT, _safe_error, mcp


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(
    risk_level="medium",
    undo=lambda params, result: {
        "tool": "delete_ip_pool",
        "params": {"pool_id": params.get("pool_id"), "target": params.get("target")},
        "skill": "nsx",
        "note": "Inverse of create_ip_pool: delete the created IP pool.",
    },
)
def create_ip_pool(
    pool_id: str,
    display_name: str,
    start_ip: str,
    end_ip: str,
    cidr: str,
    gateway_ip: Optional[str] = None,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Create an IP address pool with one static subnet and allocation range.

    IP pools supply addresses to NSX consumers such as tunnel endpoints
    (TEPs). Check list_ip_pools first to avoid overlapping ranges; start_ip
    and end_ip must both fall inside cidr. Re-running with the same pool_id
    overwrites it (PUT semantics). Returns the created pool dict; verify
    consumption later with get_ip_pool_usage. On failure returns
    {"error", "hint"}. Recorded in the audit log (~/.vmware/audit.db).

    Args:
        pool_id: Unique pool identifier (alphanumerics, hyphens, underscores
            only); becomes policy path /infra/ip-pools/<pool_id>.
        display_name: Human-readable name shown in the NSX UI.
        start_ip: First allocatable IPv4 address, e.g. "192.168.1.10".
        end_ip: Last allocatable IPv4 address, e.g. "192.168.1.100".
        cidr: Subnet containing the range, in CIDR notation, e.g. "192.168.1.0/24".
        gateway_ip: Default gateway IP for the subnet, e.g. "192.168.1.1". Optional.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.nat_route_mgmt import create_ip_pool as _create

        client = server._get_connection(target)
        subnet: dict = {
            "allocation_ranges": [{"start": start_ip, "end": end_ip}],
            "cidr": cidr,
        }
        if gateway_ip:
            subnet["gateway_ip"] = gateway_ip
        return _create(
            client, pool_id,
            display_name=display_name,
            subnets=[subnet],
        )
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def delete_ip_pool(
    pool_id: str,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Permanently delete an IP address pool.

    Irreversible: consumers (e.g. transport endpoints) that draw addresses
    from this pool can no longer allocate, and NSX rejects the delete if the
    pool still has active allocations. Run list_ip_pools and get_ip_pool_usage
    on the same pool_id first to confirm the pool is unused, and confirm with
    the user before deleting. Returns a confirmation string on success, or an
    "Error: ..." string (pool not found, still in use, connectivity failure).
    Recorded in the audit log (~/.vmware/audit.db).

    Args:
        pool_id: IP pool ID to delete, as returned by list_ip_pools.
        target: NSX Manager name from config.yaml. Uses the default target if omitted.
    """
    try:
        from vmware_nsx.ops.nat_route_mgmt import delete_ip_pool as _delete

        client = server._get_connection(target)
        _delete(client, pool_id)
        return f"IP pool '{pool_id}' deleted."
    except Exception as e:
        return f"Error: {_safe_error(e, 'nsx')} {_DOCTOR_HINT}"
