"""WRITE tools: NAT rule create / delete."""

from typing import Optional

from vmware_policy import vmware_tool

from vmware_nsx.mcp_server import server
from vmware_nsx.mcp_server._shared import _DOCTOR_HINT, _safe_error, mcp


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(
    risk_level="medium",
    undo=lambda params, result: {
        "tool": "delete_nat_rule",
        "params": {
            "tier1_id": params.get("tier1_id"),
            "rule_id": params.get("rule_id"),
            "target": params.get("target"),
        },
        "skill": "nsx",
        "note": "Inverse of create_nat_rule: delete the created NAT rule.",
    },
)
def create_nat_rule(
    tier1_id: str,
    rule_id: str,
    action: str = "DNAT",
    source_network: Optional[str] = None,
    destination_network: Optional[str] = None,
    translated_network: str = "",
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Create a NAT rule on a Tier-1 gateway's USER NAT section.

    Run list_tier1_gateways for tier1_id and list_nat_rules to avoid an id clash
    — the same rule_id overwrites. The gateway must have an edge cluster (see
    create_tier1_gateway) or NAT cannot be realized, and TIER1_NAT advertisement
    must be set via update_tier1_gateway for the translated address to be
    reachable from outside. Returns the created rule dict, else
    {"error", "hint"}. Then confirm with list_nat_rules; delete_nat_rule is the
    inverse.

    Args:
        tier1_id: Gateway ID, as returned by list_tier1_gateways.
        rule_id: Unique ID for the NAT rule.
        action: "SNAT", "DNAT" or "REFLEXIVE" (default "DNAT").
        source_network: Source CIDR (required for SNAT).
        destination_network: Destination CIDR (required for DNAT).
        translated_network: Translated network/IP (required for all three).
        target: NSX Manager target from config (default if omitted).
    """
    try:
        from vmware_nsx.ops.nat_route_mgmt import create_nat_rule as _create

        client = server._get_connection(target)
        return _create(
            client, tier1_id, rule_id,
            action=action,
            source_network=source_network,
            destination_network=destination_network,
            translated_network=translated_network,
        )
    except Exception as e:
        return {"error": _safe_error(e, "nsx"), "hint": _DOCTOR_HINT}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def delete_nat_rule(
    tier1_id: str,
    rule_id: str,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Permanently delete a NAT rule from a Tier-1 gateway's USER NAT section.

    Irreversible: traffic matched by the rule stops being translated
    immediately, which can break inbound (DNAT) or outbound (SNAT)
    connectivity. Run list_nat_rules on the same tier1_id first to confirm the
    rule_id and review its action and networks, and confirm with the user before
    deleting. Returns a confirmation string, or an "Error: ..." string — not a
    dict.

    Args:
        tier1_id: Gateway that owns the rule, as returned by list_tier1_gateways.
        rule_id: NAT rule ID to delete, as returned by list_nat_rules.
        target: NSX Manager target from config (default if omitted).
    """
    try:
        from vmware_nsx.ops.nat_route_mgmt import delete_nat_rule as _delete

        client = server._get_connection(target)
        _delete(client, tier1_id, rule_id)
        return f"NAT rule '{rule_id}' deleted from '{tier1_id}'."
    except Exception as e:
        return (
            f"Error: the rule was NOT deleted. {_safe_error(e, 'nsx')} "
            f"Run list_nat_rules on '{tier1_id}' to confirm the rule_id, or "
            f"'vmware-nsx doctor' to check connectivity."
        )
