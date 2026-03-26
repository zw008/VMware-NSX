"""CLI entry point for VMware NSX.

Provides read-only inventory/networking/health/troubleshooting queries and
write operations (segment, gateway, NAT, route, IP pool management) with
--dry-run preview and double confirmation for destructive actions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from vmware_nsx.config import CONFIG_DIR
from vmware_nsx.notify.audit import AuditLogger

_audit = AuditLogger()

app = typer.Typer(
    name="vmware-nsx",
    help="VMware NSX networking management and operations.",
    no_args_is_help=True,
)
console = Console()

# ─── Sub-command groups ──────────────────────────────────────────────────────

inventory_app = typer.Typer(help="NSX inventory: segments, gateways, transport zones/nodes, edge clusters.")
networking_app = typer.Typer(help="Networking: NAT rules, BGP, static routes, IP pools.")
health_app = typer.Typer(help="Health: alarms, transport node status, edge cluster status, manager status.")
troubleshoot_app = typer.Typer(help="Troubleshoot: port status, VM-to-segment mapping.")
segment_app = typer.Typer(help="Segment management: create, update, delete (write ops).")
gateway_app = typer.Typer(help="Gateway management: create/update/delete Tier-1, configure Tier-0 BGP.")
nat_app = typer.Typer(help="NAT rule management: create, delete.")
route_app = typer.Typer(help="Static route management: create, delete.")
ip_pool_app = typer.Typer(help="IP pool management: create.")

app.add_typer(inventory_app, name="inventory")
app.add_typer(networking_app, name="networking")
app.add_typer(health_app, name="health")
app.add_typer(troubleshoot_app, name="troubleshoot")
app.add_typer(segment_app, name="segment")
app.add_typer(gateway_app, name="gateway")
app.add_typer(nat_app, name="nat")
app.add_typer(route_app, name="route")
app.add_typer(ip_pool_app, name="ip-pool")

# ─── Type aliases ────────────────────────────────────────────────────────────

TargetOption = Annotated[
    str | None, typer.Option("--target", "-t", help="Target name from config")
]
ConfigOption = Annotated[
    Path | None, typer.Option("--config", "-c", help="Config file path")
]
DryRunOption = Annotated[
    bool, typer.Option("--dry-run", help="Print API calls without executing")
]


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _get_connection(target: str | None, config_path: Path | None = None):
    """Return (NsxClient, AppConfig)."""
    from vmware_nsx.config import load_config
    from vmware_nsx.connection import ConnectionManager

    cfg = load_config(config_path)
    mgr = ConnectionManager(cfg)
    name = target or cfg.default_target
    return mgr.connect(name), cfg


def _resolve_target(target: str | None) -> str:
    """Return display name for audit logs."""
    return target or "default"


def _dry_run_print(
    *,
    target: str,
    resource: str,
    operation: str,
    api_call: str,
    parameters: dict | None = None,
    before_state: dict | None = None,
    expected_after: dict | None = None,
    resource_label: str = "Resource",
) -> None:
    """Print a dry-run preview of the API call that would be made."""
    console.print("\n[bold magenta][DRY-RUN] No changes will be made.[/]")
    console.print(f"[magenta]  Target:      {target}[/]")
    console.print(f"[magenta]  {resource_label}:  {resource}[/]")
    console.print(f"[magenta]  Operation:   {operation}[/]")
    console.print(f"[magenta]  API Call:    {api_call}[/]")
    if parameters:
        for k, v in parameters.items():
            console.print(f"[magenta]  Param:       {k} = {v}[/]")
    if before_state:
        console.print(f"[magenta]  Current:     {before_state}[/]")
    if expected_after:
        console.print(f"[magenta]  Expected:    {expected_after}[/]")
    console.print("[magenta]  Run without --dry-run to execute.[/]\n")
    _audit.log(
        target=target,
        operation=operation,
        resource=resource,
        parameters={"dry_run": True, **(parameters or {})},
        result="dry-run",
    )


def _double_confirm(
    action: str,
    resource_name: str,
    target: str = "default",
    resource_type: str = "Resource",
) -> None:
    """Require two confirmations for destructive operations."""
    console.print(f"[bold yellow]WARNING: About to {action} {resource_type} '{resource_name}'[/]")
    try:
        typer.confirm(f"Confirm #1: {action} '{resource_name}'?", abort=True)
        typer.confirm(f"Confirm #2: This is irreversible. {action} '{resource_name}'?", abort=True)
    except typer.Abort:
        _audit.log(
            target=target,
            operation=action,
            resource=resource_name,
            parameters={},
            result="rejected",
        )
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# INVENTORY (read-only)
# ═══════════════════════════════════════════════════════════════════════════════


@inventory_app.command("list-segments")
def inventory_list_segments(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List all network segments."""
    from vmware_nsx.ops.inventory import list_segments

    client, _ = _get_connection(target, config)
    segments = list_segments(client)
    table = Table(title=f"Segments ({len(segments)})")
    table.add_column("ID", style="cyan")
    table.add_column("Display Name")
    table.add_column("VLAN / Overlay")
    table.add_column("Subnet")
    table.add_column("Admin State")
    table.add_column("Ports", justify="right")
    for s in segments:
        state_style = "green" if s["admin_state"] == "UP" else "red"
        table.add_row(
            s["id"],
            s["display_name"],
            s["type"],
            s.get("subnet", "-"),
            f"[{state_style}]{s['admin_state']}[/]",
            str(s.get("port_count", "-")),
        )
    console.print(table)


@inventory_app.command("get-segment")
def inventory_get_segment(
    segment_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Get detailed info for a specific segment."""
    from vmware_nsx.ops.inventory import get_segment

    client, _ = _get_connection(target, config)
    info = get_segment(client, segment_id)
    for k, v in info.items():
        console.print(f"  [cyan]{k}:[/] {v}")


@inventory_app.command("list-tier0s")
def inventory_list_tier0s(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List all Tier-0 gateways."""
    from vmware_nsx.ops.inventory import list_tier0_gateways

    client, _ = _get_connection(target, config)
    gateways = list_tier0_gateways(client)
    table = Table(title=f"Tier-0 Gateways ({len(gateways)})")
    table.add_column("ID", style="cyan")
    table.add_column("Display Name")
    table.add_column("HA Mode")
    table.add_column("Transit Subnets")
    for gw in gateways:
        table.add_row(gw["id"], gw["display_name"], gw.get("ha_mode", "-"), gw.get("transit_subnets", "-"))
    console.print(table)


@inventory_app.command("get-tier0")
def inventory_get_tier0(
    tier0_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Get detailed info for a Tier-0 gateway."""
    from vmware_nsx.ops.inventory import get_tier0_gateway

    client, _ = _get_connection(target, config)
    info = get_tier0_gateway(client, tier0_id)
    for k, v in info.items():
        console.print(f"  [cyan]{k}:[/] {v}")


@inventory_app.command("list-tier1s")
def inventory_list_tier1s(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List all Tier-1 gateways."""
    from vmware_nsx.ops.inventory import list_tier1_gateways

    client, _ = _get_connection(target, config)
    gateways = list_tier1_gateways(client)
    table = Table(title=f"Tier-1 Gateways ({len(gateways)})")
    table.add_column("ID", style="cyan")
    table.add_column("Display Name")
    table.add_column("Tier-0 Path")
    table.add_column("Route Advertisement")
    for gw in gateways:
        table.add_row(gw["id"], gw["display_name"], gw.get("tier0_path", "-"), gw.get("route_advertisement", "-"))
    console.print(table)


@inventory_app.command("get-tier1")
def inventory_get_tier1(
    tier1_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Get detailed info for a Tier-1 gateway."""
    from vmware_nsx.ops.inventory import get_tier1_gateway

    client, _ = _get_connection(target, config)
    info = get_tier1_gateway(client, tier1_id)
    for k, v in info.items():
        console.print(f"  [cyan]{k}:[/] {v}")


@inventory_app.command("list-transport-zones")
def inventory_list_transport_zones(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List all transport zones."""
    from vmware_nsx.ops.inventory import list_transport_zones

    client, _ = _get_connection(target, config)
    zones = list_transport_zones(client)
    table = Table(title=f"Transport Zones ({len(zones)})")
    table.add_column("ID", style="cyan")
    table.add_column("Display Name")
    table.add_column("Type")
    table.add_column("Host Switch")
    for z in zones:
        table.add_row(z["id"], z["display_name"], z["transport_type"], z.get("host_switch_name", "-"))
    console.print(table)


@inventory_app.command("list-transport-nodes")
def inventory_list_transport_nodes(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List all transport nodes."""
    from vmware_nsx.ops.inventory import list_transport_nodes

    client, _ = _get_connection(target, config)
    nodes = list_transport_nodes(client)
    table = Table(title=f"Transport Nodes ({len(nodes)})")
    table.add_column("ID", style="cyan")
    table.add_column("Display Name")
    table.add_column("Node Type")
    table.add_column("Status")
    for n in nodes:
        status = n.get("status", "UNKNOWN")
        style = "green" if status == "UP" else "red" if status == "DOWN" else "yellow"
        table.add_row(n["id"], n["display_name"], n.get("node_type", "-"), f"[{style}]{status}[/]")
    console.print(table)


@inventory_app.command("list-edge-clusters")
def inventory_list_edge_clusters(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List all edge clusters."""
    from vmware_nsx.ops.inventory import list_edge_clusters

    client, _ = _get_connection(target, config)
    clusters = list_edge_clusters(client)
    table = Table(title=f"Edge Clusters ({len(clusters)})")
    table.add_column("ID", style="cyan")
    table.add_column("Display Name")
    table.add_column("Members", justify="right")
    table.add_column("Deployment Type")
    for c in clusters:
        table.add_row(c["id"], c["display_name"], str(c.get("member_count", "-")), c.get("deployment_type", "-"))
    console.print(table)


# ═══════════════════════════════════════════════════════════════════════════════
# NETWORKING (read-only)
# ═══════════════════════════════════════════════════════════════════════════════


@networking_app.command("list-nat-rules")
def networking_list_nat_rules(
    tier1_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List NAT rules on a Tier-1 gateway."""
    from vmware_nsx.ops.networking import list_nat_rules

    client, _ = _get_connection(target, config)
    rules = list_nat_rules(client, tier1_id)
    table = Table(title=f"NAT Rules on '{tier1_id}' ({len(rules)})")
    table.add_column("ID", style="cyan")
    table.add_column("Action")
    table.add_column("Source")
    table.add_column("Destination")
    table.add_column("Translated")
    table.add_column("Enabled")
    for r in rules:
        enabled_style = "green" if r.get("enabled", True) else "red"
        table.add_row(
            r["id"],
            r["action"],
            r.get("source_network", "-"),
            r.get("destination_network", "-"),
            r.get("translated_network", "-"),
            f"[{enabled_style}]{'Yes' if r.get('enabled', True) else 'No'}[/]",
        )
    console.print(table)


@networking_app.command("bgp-neighbors")
def networking_bgp_neighbors(
    tier0_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Show BGP neighbors for a Tier-0 gateway."""
    from vmware_nsx.ops.networking import get_bgp_neighbors

    client, _ = _get_connection(target, config)
    neighbors = get_bgp_neighbors(client, tier0_id)
    if not neighbors:
        console.print("[yellow]No BGP neighbors found.[/]")
        return
    table = Table(title=f"BGP Neighbors on '{tier0_id}'")
    table.add_column("Neighbor Address", style="cyan")
    table.add_column("Remote ASN")
    table.add_column("State")
    table.add_column("Hold Time")
    table.add_column("Keep Alive")
    for n in neighbors:
        state = n.get("connection_state", "UNKNOWN")
        style = "green" if state == "ESTABLISHED" else "red"
        table.add_row(
            n["neighbor_address"],
            str(n.get("remote_as_num", "-")),
            f"[{style}]{state}[/]",
            str(n.get("hold_down_time", "-")),
            str(n.get("keep_alive_time", "-")),
        )
    console.print(table)


@networking_app.command("list-static-routes")
def networking_list_static_routes(
    tier1_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List static routes on a Tier-1 gateway."""
    from vmware_nsx.ops.networking import list_static_routes

    client, _ = _get_connection(target, config)
    routes = list_static_routes(client, tier1_id)
    table = Table(title=f"Static Routes on '{tier1_id}' ({len(routes)})")
    table.add_column("ID", style="cyan")
    table.add_column("Network")
    table.add_column("Next Hops")
    for r in routes:
        hops = ", ".join(r.get("next_hops", []))
        table.add_row(r["id"], r["network"], hops or "-")
    console.print(table)


@networking_app.command("list-ip-pools")
def networking_list_ip_pools(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List all IP address pools."""
    from vmware_nsx.ops.networking import list_ip_pools

    client, _ = _get_connection(target, config)
    pools = list_ip_pools(client)
    table = Table(title=f"IP Pools ({len(pools)})")
    table.add_column("ID", style="cyan")
    table.add_column("Display Name")
    table.add_column("Subnets")
    table.add_column("Usage", justify="right")
    for p in pools:
        table.add_row(p["id"], p["display_name"], p.get("subnets", "-"), p.get("usage_summary", "-"))
    console.print(table)


@networking_app.command("ip-pool-usage")
def networking_ip_pool_usage(
    pool_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Show IP pool allocation usage."""
    from vmware_nsx.ops.networking import get_ip_pool_usage

    client, _ = _get_connection(target, config)
    usage = get_ip_pool_usage(client, pool_id)
    console.print(f"\n[bold]IP Pool Usage: {pool_id}[/]")
    for k, v in usage.items():
        console.print(f"  [cyan]{k}:[/] {v}")


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH (read-only)
# ═══════════════════════════════════════════════════════════════════════════════


@health_app.command("alarms")
def health_alarms(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Show active NSX alarms."""
    from vmware_nsx.ops.health import list_nsx_alarms

    client, _ = _get_connection(target, config)
    alarms = list_nsx_alarms(client)
    if not alarms:
        console.print("[green]No active alarms.[/]")
        return
    table = Table(title=f"NSX Alarms ({len(alarms)})")
    table.add_column("Severity")
    table.add_column("Feature")
    table.add_column("Description")
    table.add_column("Entity")
    table.add_column("Time")
    for a in alarms:
        sev = a.get("severity", "UNKNOWN")
        sev_style = "red" if sev == "CRITICAL" else "yellow" if sev == "WARNING" else "white"
        table.add_row(
            f"[{sev_style}]{sev}[/]",
            a.get("feature_name", "-"),
            a.get("description", "-"),
            a.get("entity_id", "-"),
            a.get("last_reported_time", "-"),
        )
    console.print(table)


@health_app.command("transport-node-status")
def health_transport_node_status(
    node_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Check status of a specific transport node."""
    from vmware_nsx.ops.health import get_transport_node_status

    client, _ = _get_connection(target, config)
    status = get_transport_node_status(client, node_id)
    for k, v in status.items():
        console.print(f"  [cyan]{k}:[/] {v}")


@health_app.command("edge-cluster-status")
def health_edge_cluster_status(
    cluster_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Check status of an edge cluster."""
    from vmware_nsx.ops.health import get_edge_cluster_status

    client, _ = _get_connection(target, config)
    status = get_edge_cluster_status(client, cluster_id)
    for k, v in status.items():
        console.print(f"  [cyan]{k}:[/] {v}")


@health_app.command("manager-status")
def health_manager_status(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Show NSX Manager cluster status."""
    from vmware_nsx.ops.health import get_nsx_manager_status

    client, _ = _get_connection(target, config)
    status = get_nsx_manager_status(client)
    for k, v in status.items():
        console.print(f"  [cyan]{k}:[/] {v}")


# ═══════════════════════════════════════════════════════════════════════════════
# TROUBLESHOOT (read-only)
# ═══════════════════════════════════════════════════════════════════════════════


@troubleshoot_app.command("port-status")
def troubleshoot_port_status(
    port_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Check logical port operational status."""
    from vmware_nsx.ops.troubleshoot import get_logical_port_status

    client, _ = _get_connection(target, config)
    status = get_logical_port_status(client, port_id)
    for k, v in status.items():
        console.print(f"  [cyan]{k}:[/] {v}")


@troubleshoot_app.command("vm-segment")
def troubleshoot_vm_segment(
    vm_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Find which segment a VM is attached to."""
    from vmware_nsx.ops.troubleshoot import get_segment_port_for_vm

    client, _ = _get_connection(target, config)
    result = get_segment_port_for_vm(client, vm_id)
    if not result:
        console.print("[yellow]No segment port found for this VM.[/]")
        return
    for k, v in result.items():
        console.print(f"  [cyan]{k}:[/] {v}")


# ═══════════════════════════════════════════════════════════════════════════════
# SEGMENT MANAGEMENT (write ops)
# ═══════════════════════════════════════════════════════════════════════════════


@segment_app.command("create")
def segment_create(
    segment_id: str,
    display_name: Annotated[str, typer.Option("--name", help="Display name")],
    transport_zone: Annotated[str, typer.Option("--tz", help="Transport zone path")],
    vlan_ids: Annotated[str | None, typer.Option("--vlan", help="VLAN ID(s), e.g. '100' or '100-200'")] = None,
    subnet: Annotated[str | None, typer.Option("--subnet", help="Gateway CIDR, e.g. '192.168.1.1/24'")] = None,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Create a new network segment."""
    from vmware_nsx.ops.segment_mgmt import create_segment

    client, _ = _get_connection(target, config)
    params = {"display_name": display_name, "transport_zone": transport_zone, "vlan_ids": vlan_ids, "subnet": subnet}
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target),
            resource=segment_id,
            operation="create_segment",
            api_call=f"PUT /policy/api/v1/infra/segments/{segment_id}",
            parameters=params,
            resource_label="Segment",
        )
        return
    _double_confirm("create segment", segment_id, _resolve_target(target), resource_type="Segment")
    result = create_segment(client, segment_id, display_name=display_name, transport_zone_path=transport_zone, vlan_ids=vlan_ids, subnet=subnet)
    console.print(f"[green]Segment '{segment_id}' created.[/]")
    _audit.log(target=_resolve_target(target), operation="create_segment", resource=segment_id, parameters=params, result="ok")


@segment_app.command("update")
def segment_update(
    segment_id: str,
    display_name: Annotated[str | None, typer.Option("--name", help="New display name")] = None,
    subnet: Annotated[str | None, typer.Option("--subnet", help="New gateway CIDR")] = None,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Update an existing segment."""
    from vmware_nsx.ops.inventory import get_segment
    from vmware_nsx.ops.segment_mgmt import update_segment

    client, _ = _get_connection(target, config)
    before = get_segment(client, segment_id)
    params = {"display_name": display_name, "subnet": subnet}
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target),
            resource=segment_id,
            operation="update_segment",
            api_call=f"PATCH /policy/api/v1/infra/segments/{segment_id}",
            parameters={k: v for k, v in params.items() if v is not None},
            before_state={"display_name": before.get("display_name"), "subnet": before.get("subnet")},
            resource_label="Segment",
        )
        return
    _double_confirm("update segment", segment_id, _resolve_target(target), resource_type="Segment")
    update_segment(client, segment_id, display_name=display_name, subnet=subnet)
    console.print(f"[green]Segment '{segment_id}' updated.[/]")
    _audit.log(target=_resolve_target(target), operation="update_segment", resource=segment_id, parameters=params, result="ok")


@segment_app.command("delete")
def segment_delete(
    segment_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Delete a segment (destructive!)."""
    from vmware_nsx.ops.inventory import get_segment
    from vmware_nsx.ops.segment_mgmt import delete_segment

    client, _ = _get_connection(target, config)
    info = get_segment(client, segment_id)
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target),
            resource=segment_id,
            operation="delete_segment",
            api_call=f"DELETE /policy/api/v1/infra/segments/{segment_id}",
            before_state={"port_count": info.get("port_count"), "admin_state": info.get("admin_state")},
            resource_label="Segment",
        )
        return
    port_count = info.get("port_count", 0)
    if port_count and port_count > 0:
        console.print(f"[bold red]WARNING: Segment has {port_count} active ports![/]")
    _double_confirm("delete segment", segment_id, _resolve_target(target), resource_type="Segment")
    delete_segment(client, segment_id)
    console.print(f"[green]Segment '{segment_id}' deleted.[/]")
    _audit.log(target=_resolve_target(target), operation="delete_segment", resource=segment_id, parameters={}, result="ok")


# ═══════════════════════════════════════════════════════════════════════════════
# GATEWAY MANAGEMENT (write ops)
# ═══════════════════════════════════════════════════════════════════════════════


@gateway_app.command("create-tier1")
def gateway_create_tier1(
    tier1_id: str,
    display_name: Annotated[str, typer.Option("--name", help="Display name")],
    tier0_path: Annotated[str | None, typer.Option("--tier0", help="Tier-0 gateway path to link")] = None,
    edge_cluster_path: Annotated[str | None, typer.Option("--edge-cluster", help="Edge cluster path")] = None,
    route_advertisement: Annotated[str | None, typer.Option("--advertise", help="Route advertisement types, comma-separated")] = None,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Create a new Tier-1 gateway."""
    from vmware_nsx.ops.gateway_mgmt import create_tier1_gateway

    client, _ = _get_connection(target, config)
    params = {"display_name": display_name, "tier0_path": tier0_path, "edge_cluster_path": edge_cluster_path, "route_advertisement": route_advertisement}
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target),
            resource=tier1_id,
            operation="create_tier1_gateway",
            api_call=f"PUT /policy/api/v1/infra/tier-1s/{tier1_id}",
            parameters=params,
            resource_label="Tier-1 Gateway",
        )
        return
    _double_confirm("create Tier-1 gateway", tier1_id, _resolve_target(target), resource_type="Tier-1 Gateway")
    create_tier1_gateway(client, tier1_id, display_name=display_name, tier0_path=tier0_path, edge_cluster_path=edge_cluster_path, route_advertisement=route_advertisement)
    console.print(f"[green]Tier-1 gateway '{tier1_id}' created.[/]")
    _audit.log(target=_resolve_target(target), operation="create_tier1_gateway", resource=tier1_id, parameters=params, result="ok")


@gateway_app.command("update-tier1")
def gateway_update_tier1(
    tier1_id: str,
    display_name: Annotated[str | None, typer.Option("--name", help="New display name")] = None,
    tier0_path: Annotated[str | None, typer.Option("--tier0", help="New Tier-0 path")] = None,
    route_advertisement: Annotated[str | None, typer.Option("--advertise", help="Route advertisement types")] = None,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Update an existing Tier-1 gateway."""
    from vmware_nsx.ops.gateway_mgmt import update_tier1_gateway
    from vmware_nsx.ops.inventory import get_tier1_gateway

    client, _ = _get_connection(target, config)
    before = get_tier1_gateway(client, tier1_id)
    params = {"display_name": display_name, "tier0_path": tier0_path, "route_advertisement": route_advertisement}
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target),
            resource=tier1_id,
            operation="update_tier1_gateway",
            api_call=f"PATCH /policy/api/v1/infra/tier-1s/{tier1_id}",
            parameters={k: v for k, v in params.items() if v is not None},
            before_state={"display_name": before.get("display_name"), "tier0_path": before.get("tier0_path")},
            resource_label="Tier-1 Gateway",
        )
        return
    _double_confirm("update Tier-1 gateway", tier1_id, _resolve_target(target), resource_type="Tier-1 Gateway")
    update_tier1_gateway(client, tier1_id, display_name=display_name, tier0_path=tier0_path, route_advertisement=route_advertisement)
    console.print(f"[green]Tier-1 gateway '{tier1_id}' updated.[/]")
    _audit.log(target=_resolve_target(target), operation="update_tier1_gateway", resource=tier1_id, parameters=params, result="ok")


@gateway_app.command("delete-tier1")
def gateway_delete_tier1(
    tier1_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Delete a Tier-1 gateway (destructive!)."""
    from vmware_nsx.ops.gateway_mgmt import delete_tier1_gateway
    from vmware_nsx.ops.inventory import get_tier1_gateway

    client, _ = _get_connection(target, config)
    before = get_tier1_gateway(client, tier1_id)
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target),
            resource=tier1_id,
            operation="delete_tier1_gateway",
            api_call=f"DELETE /policy/api/v1/infra/tier-1s/{tier1_id}",
            before_state={"display_name": before.get("display_name"), "tier0_path": before.get("tier0_path")},
            resource_label="Tier-1 Gateway",
        )
        return
    _double_confirm("delete Tier-1 gateway", tier1_id, _resolve_target(target), resource_type="Tier-1 Gateway")
    delete_tier1_gateway(client, tier1_id)
    console.print(f"[green]Tier-1 gateway '{tier1_id}' deleted.[/]")
    _audit.log(target=_resolve_target(target), operation="delete_tier1_gateway", resource=tier1_id, parameters={}, result="ok")


@gateway_app.command("configure-tier0-bgp")
def gateway_configure_tier0_bgp(
    tier0_id: str,
    local_as: Annotated[int, typer.Option("--local-as", help="Local AS number")],
    neighbor_address: Annotated[str, typer.Option("--neighbor", help="BGP neighbor IP address")],
    remote_as: Annotated[int, typer.Option("--remote-as", help="Remote AS number")],
    hold_time: Annotated[int, typer.Option("--hold-time", help="Hold down time in seconds")] = 180,
    keep_alive: Annotated[int, typer.Option("--keep-alive", help="Keep alive time in seconds")] = 60,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Configure BGP on a Tier-0 gateway."""
    from vmware_nsx.ops.gateway_mgmt import configure_tier0_bgp

    client, _ = _get_connection(target, config)
    params = {"local_as": local_as, "neighbor_address": neighbor_address, "remote_as": remote_as, "hold_time": hold_time, "keep_alive": keep_alive}
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target),
            resource=tier0_id,
            operation="configure_tier0_bgp",
            api_call=f"PATCH /policy/api/v1/infra/tier-0s/{tier0_id}/locale-services/default/bgp",
            parameters=params,
            resource_label="Tier-0 BGP",
        )
        return
    _double_confirm("configure BGP on Tier-0", tier0_id, _resolve_target(target), resource_type="Tier-0 BGP")
    configure_tier0_bgp(client, tier0_id, local_as=local_as, neighbor_address=neighbor_address, remote_as=remote_as, hold_time=hold_time, keep_alive=keep_alive)
    console.print(f"[green]BGP configured on Tier-0 '{tier0_id}'.[/]")
    _audit.log(target=_resolve_target(target), operation="configure_tier0_bgp", resource=tier0_id, parameters=params, result="ok")


# ═══════════════════════════════════════════════════════════════════════════════
# NAT MANAGEMENT (write ops)
# ═══════════════════════════════════════════════════════════════════════════════


@nat_app.command("create-rule")
def nat_create_rule(
    tier1_id: Annotated[str, typer.Option("--tier1", help="Tier-1 gateway ID")],
    rule_id: Annotated[str, typer.Option("--rule-id", help="NAT rule ID")],
    action: Annotated[str, typer.Option("--action", help="NAT action: SNAT, DNAT, REFLEXIVE")] = "DNAT",
    source_network: Annotated[str | None, typer.Option("--source", help="Source network CIDR")] = None,
    destination_network: Annotated[str | None, typer.Option("--destination", help="Destination network CIDR")] = None,
    translated_network: Annotated[str, typer.Option("--translated", help="Translated network/IP")] = "",
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Create a NAT rule on a Tier-1 gateway."""
    from vmware_nsx.ops.nat_mgmt import create_nat_rule

    client, _ = _get_connection(target, config)
    params = {"action": action, "source_network": source_network, "destination_network": destination_network, "translated_network": translated_network}
    resource_name = f"{tier1_id}/{rule_id}"
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target),
            resource=resource_name,
            operation="create_nat_rule",
            api_call=f"PUT /policy/api/v1/infra/tier-1s/{tier1_id}/nat/USER/nat-rules/{rule_id}",
            parameters=params,
            resource_label="NAT Rule",
        )
        return
    _double_confirm("create NAT rule", resource_name, _resolve_target(target), resource_type="NAT Rule")
    create_nat_rule(client, tier1_id, rule_id, action=action, source_network=source_network, destination_network=destination_network, translated_network=translated_network)
    console.print(f"[green]NAT rule '{rule_id}' created on '{tier1_id}'.[/]")
    _audit.log(target=_resolve_target(target), operation="create_nat_rule", resource=resource_name, parameters=params, result="ok")


@nat_app.command("delete-rule")
def nat_delete_rule(
    tier1_id: Annotated[str, typer.Option("--tier1", help="Tier-1 gateway ID")],
    rule_id: Annotated[str, typer.Option("--rule-id", help="NAT rule ID to delete")],
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Delete a NAT rule (destructive!)."""
    from vmware_nsx.ops.nat_mgmt import delete_nat_rule

    client, _ = _get_connection(target, config)
    resource_name = f"{tier1_id}/{rule_id}"
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target),
            resource=resource_name,
            operation="delete_nat_rule",
            api_call=f"DELETE /policy/api/v1/infra/tier-1s/{tier1_id}/nat/USER/nat-rules/{rule_id}",
            resource_label="NAT Rule",
        )
        return
    _double_confirm("delete NAT rule", resource_name, _resolve_target(target), resource_type="NAT Rule")
    delete_nat_rule(client, tier1_id, rule_id)
    console.print(f"[green]NAT rule '{rule_id}' deleted from '{tier1_id}'.[/]")
    _audit.log(target=_resolve_target(target), operation="delete_nat_rule", resource=resource_name, parameters={}, result="ok")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE MANAGEMENT (write ops)
# ═══════════════════════════════════════════════════════════════════════════════


@route_app.command("create-static")
def route_create_static(
    tier1_id: Annotated[str, typer.Option("--tier1", help="Tier-1 gateway ID")],
    route_id: Annotated[str, typer.Option("--route-id", help="Static route ID")],
    network: Annotated[str, typer.Option("--network", help="Destination CIDR, e.g. '10.0.0.0/8'")],
    next_hop: Annotated[str, typer.Option("--next-hop", help="Next hop IP address")],
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Create a static route on a Tier-1 gateway."""
    from vmware_nsx.ops.route_mgmt import create_static_route

    client, _ = _get_connection(target, config)
    params = {"network": network, "next_hop": next_hop}
    resource_name = f"{tier1_id}/{route_id}"
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target),
            resource=resource_name,
            operation="create_static_route",
            api_call=f"PUT /policy/api/v1/infra/tier-1s/{tier1_id}/static-routes/{route_id}",
            parameters=params,
            resource_label="Static Route",
        )
        return
    _double_confirm("create static route", resource_name, _resolve_target(target), resource_type="Static Route")
    create_static_route(client, tier1_id, route_id, network=network, next_hop=next_hop)
    console.print(f"[green]Static route '{route_id}' created on '{tier1_id}'.[/]")
    _audit.log(target=_resolve_target(target), operation="create_static_route", resource=resource_name, parameters=params, result="ok")


@route_app.command("delete-static")
def route_delete_static(
    tier1_id: Annotated[str, typer.Option("--tier1", help="Tier-1 gateway ID")],
    route_id: Annotated[str, typer.Option("--route-id", help="Static route ID to delete")],
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Delete a static route (destructive!)."""
    from vmware_nsx.ops.route_mgmt import delete_static_route

    client, _ = _get_connection(target, config)
    resource_name = f"{tier1_id}/{route_id}"
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target),
            resource=resource_name,
            operation="delete_static_route",
            api_call=f"DELETE /policy/api/v1/infra/tier-1s/{tier1_id}/static-routes/{route_id}",
            resource_label="Static Route",
        )
        return
    _double_confirm("delete static route", resource_name, _resolve_target(target), resource_type="Static Route")
    delete_static_route(client, tier1_id, route_id)
    console.print(f"[green]Static route '{route_id}' deleted from '{tier1_id}'.[/]")
    _audit.log(target=_resolve_target(target), operation="delete_static_route", resource=resource_name, parameters={}, result="ok")


# ═══════════════════════════════════════════════════════════════════════════════
# IP POOL MANAGEMENT (write ops)
# ═══════════════════════════════════════════════════════════════════════════════


@ip_pool_app.command("create")
def ip_pool_create(
    pool_id: str,
    display_name: Annotated[str, typer.Option("--name", help="Display name")],
    start_ip: Annotated[str, typer.Option("--start", help="Start IP address")],
    end_ip: Annotated[str, typer.Option("--end", help="End IP address")],
    cidr: Annotated[str, typer.Option("--cidr", help="Subnet CIDR, e.g. '192.168.1.0/24'")],
    gateway_ip: Annotated[str | None, typer.Option("--gateway", help="Gateway IP")] = None,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Create a new IP address pool."""
    from vmware_nsx.ops.ip_pool_mgmt import create_ip_pool

    client, _ = _get_connection(target, config)
    params = {"display_name": display_name, "start_ip": start_ip, "end_ip": end_ip, "cidr": cidr, "gateway_ip": gateway_ip}
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target),
            resource=pool_id,
            operation="create_ip_pool",
            api_call=f"PUT /policy/api/v1/infra/ip-pools/{pool_id}",
            parameters=params,
            resource_label="IP Pool",
        )
        return
    _double_confirm("create IP pool", pool_id, _resolve_target(target), resource_type="IP Pool")
    create_ip_pool(client, pool_id, display_name=display_name, start_ip=start_ip, end_ip=end_ip, cidr=cidr, gateway_ip=gateway_ip)
    console.print(f"[green]IP pool '{pool_id}' created.[/]")
    _audit.log(target=_resolve_target(target), operation="create_ip_pool", resource=pool_id, parameters=params, result="ok")


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTOR
# ═══════════════════════════════════════════════════════════════════════════════


@app.command("doctor")
def doctor_cmd(
    skip_auth: Annotated[
        bool,
        typer.Option("--skip-auth", help="Skip NSX authentication check (faster)"),
    ] = False,
) -> None:
    """Check environment, config, connectivity, and NSX manager status."""
    from vmware_nsx.doctor import run_doctor

    exit_code = 0 if run_doctor(skip_auth=skip_auth) else 1
    raise typer.Exit(exit_code)


# ═══════════════════════════════════════════════════════════════════════════════
# MCP CONFIG GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

mcp_config_app = typer.Typer(help="Generate MCP server config for local AI agents.")
app.add_typer(mcp_config_app, name="mcp-config")

_AGENT_TEMPLATES = {
    "goose": "goose.json",
    "cursor": "cursor.json",
    "claude-code": "claude-code.json",
    "continue": "continue.yaml",
    "vscode-copilot": "vscode-copilot.json",
    "localcowork": "localcowork.json",
    "mcp-agent": "mcp-agent.yaml",
}

_TEMPLATES_DIR = Path(__file__).parent.parent / "examples" / "mcp-configs"

_AGENT_INSTALL_PATHS: dict[str, Path] = {
    "claude-code": Path.home() / ".claude" / "settings.json",
    "cursor": Path.home() / ".cursor" / "mcp.json",
    "goose": Path.home() / ".config" / "goose" / "config.yaml",
    "vscode-copilot": Path(".vscode") / "mcp.json",
    "continue": Path.home() / ".continue" / "config.json",
    "localcowork": Path.home() / ".localcowork" / "mcp.json",
    "mcp-agent": Path("mcp_agent.config.yaml"),
}


@mcp_config_app.command("generate")
def mcp_config_generate(
    agent: Annotated[
        str,
        typer.Option(
            "--agent", "-a",
            help="Target agent: goose, cursor, claude-code, continue, vscode-copilot, localcowork, mcp-agent",
        ),
    ],
    install_path: Annotated[
        str | None,
        typer.Option("--path", help="Absolute path to VMware-NSX install dir"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write config to this file path"),
    ] = None,
) -> None:
    """Generate MCP server config for a local AI agent.

    Example:
        vmware-nsx mcp-config generate --agent goose
    """
    agent_lower = agent.lower()
    if agent_lower not in _AGENT_TEMPLATES:
        available = ", ".join(sorted(_AGENT_TEMPLATES.keys()))
        console.print(f"[red]Unknown agent '{agent}'. Available: {available}[/]")
        raise typer.Exit(1)

    template_file = _TEMPLATES_DIR / _AGENT_TEMPLATES[agent_lower]
    if not template_file.exists():
        console.print(f"[red]Template file not found: {template_file}[/]")
        raise typer.Exit(1)

    content = template_file.read_text()

    if install_path:
        content = content.replace("/path/to/VMware-NSX", str(Path(install_path).resolve()))
    else:
        pkg_dir = Path(__file__).parent.parent.resolve()
        if (pkg_dir / "pyproject.toml").exists():
            content = content.replace("/path/to/VMware-NSX", str(pkg_dir))

    if output:
        output.write_text(content)
        console.print(f"[green]Config written to: {output}[/]")
    else:
        console.print(content)


@mcp_config_app.command("list")
def mcp_config_list() -> None:
    """List all supported agents."""
    table = Table(title="Supported Agents")
    table.add_column("Agent", style="cyan")
    table.add_column("Template File")
    for agent_name, template in sorted(_AGENT_TEMPLATES.items()):
        table.add_row(agent_name, template)
    console.print(table)


@mcp_config_app.command("install")
def mcp_config_install(
    agent: Annotated[
        str,
        typer.Option(
            "--agent", "-a",
            help="Target agent: goose, cursor, claude-code, continue, "
                 "vscode-copilot, localcowork, mcp-agent",
        ),
    ],
    install_path: Annotated[
        str | None,
        typer.Option("--path", help="Absolute path to VMware-NSX install dir"),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Install MCP config directly into a local AI agent's config file.

    Writes the vmware-nsx MCP server entry into the agent's config file.
    For agents with JSON configs, merges into the mcpServers section.
    Creates the config file if it doesn't exist.

    Example:
        vmware-nsx mcp-config install --agent cursor
        vmware-nsx mcp-config install --agent claude-code --yes
    """
    import json

    agent_lower = agent.lower()
    if agent_lower not in _AGENT_TEMPLATES:
        available = ", ".join(sorted(_AGENT_TEMPLATES.keys()))
        console.print(f"[red]Unknown agent '{agent}'. Available: {available}[/]")
        raise typer.Exit(1)

    template_file = _TEMPLATES_DIR / _AGENT_TEMPLATES[agent_lower]
    if not template_file.exists():
        console.print(f"[red]Template file not found: {template_file}[/]")
        raise typer.Exit(1)

    content = template_file.read_text()
    if install_path:
        abs_path = str(Path(install_path).resolve())
        content = content.replace("/path/to/VMware-NSX", abs_path)
    else:
        pkg_dir = Path(__file__).parent.parent.resolve()
        if (pkg_dir / "pyproject.toml").exists():
            content = content.replace("/path/to/VMware-NSX", str(pkg_dir))

    dest = _AGENT_INSTALL_PATHS.get(agent_lower)
    if dest is None:
        console.print(
            f"[yellow]No default install path for '{agent_lower}'. "
            f"Use 'generate' and install manually.[/]"
        )
        raise typer.Exit(1)

    console.print(f"[bold]Agent:[/] {agent_lower}")
    console.print(f"[bold]Install path:[/] {dest}")

    if not yes:
        confirmed = typer.confirm("Write config to this path?")
        if not confirmed:
            console.print("[yellow]Cancelled.[/]")
            raise typer.Exit(0)

    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.suffix == ".json" and dest.exists():
        try:
            existing = json.loads(dest.read_text())
            new_entry = json.loads(content)
            if "mcpServers" in new_entry:
                existing.setdefault("mcpServers", {}).update(new_entry["mcpServers"])
            else:
                existing.update(new_entry)
            dest.write_text(json.dumps(existing, indent=2) + "\n")
            console.print(f"[green]Merged vmware-nsx into: {dest}[/]")
        except (json.JSONDecodeError, Exception) as e:
            console.print(f"[red]Failed to merge into existing config: {e}[/]")
            console.print("[yellow]Writing new config (backup original first).[/]")
            dest.with_suffix(".bak").write_text(dest.read_text())
            dest.write_text(content)
            console.print(f"[green]Written: {dest} (backup: {dest.with_suffix('.bak')})[/]")
    else:
        dest.write_text(content)
        console.print(f"[green]Written: {dest}[/]")

    console.print("\n[dim]Run 'vmware-nsx doctor' to verify your setup.[/]")


if __name__ == "__main__":
    app()
