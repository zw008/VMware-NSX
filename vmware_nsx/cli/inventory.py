"""Inventory commands (read-only): segments, gateways, transport zones/nodes, edge clusters."""

from __future__ import annotations

from rich.table import Table

from vmware_nsx import cli
from vmware_nsx.cli._base import (
    ConfigOption,
    TargetOption,
    _cli_errors,
    console,
    inventory_app,
)


@inventory_app.command("list-segments")
@_cli_errors
def inventory_list_segments(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List all network segments."""
    from vmware_nsx.ops.inventory import list_segments

    client, _ = cli._get_connection(target, config)
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
@_cli_errors
def inventory_get_segment(
    segment_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Get detailed info for a specific segment."""
    from vmware_nsx.ops.inventory import get_segment

    client, _ = cli._get_connection(target, config)
    info = get_segment(client, segment_id)
    for k, v in info.items():
        console.print(f"  [cyan]{k}:[/] {v}")


@inventory_app.command("list-tier0s")
@_cli_errors
def inventory_list_tier0s(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List all Tier-0 gateways."""
    from vmware_nsx.ops.inventory import list_tier0_gateways

    client, _ = cli._get_connection(target, config)
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
@_cli_errors
def inventory_get_tier0(
    tier0_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Get detailed info for a Tier-0 gateway."""
    from vmware_nsx.ops.inventory import get_tier0_gateway

    client, _ = cli._get_connection(target, config)
    info = get_tier0_gateway(client, tier0_id)
    for k, v in info.items():
        console.print(f"  [cyan]{k}:[/] {v}")


@inventory_app.command("list-tier1s")
@_cli_errors
def inventory_list_tier1s(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List all Tier-1 gateways."""
    from vmware_nsx.ops.inventory import list_tier1_gateways

    client, _ = cli._get_connection(target, config)
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
@_cli_errors
def inventory_get_tier1(
    tier1_id: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Get detailed info for a Tier-1 gateway."""
    from vmware_nsx.ops.inventory import get_tier1_gateway

    client, _ = cli._get_connection(target, config)
    info = get_tier1_gateway(client, tier1_id)
    for k, v in info.items():
        console.print(f"  [cyan]{k}:[/] {v}")


@inventory_app.command("list-transport-zones")
@_cli_errors
def inventory_list_transport_zones(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List all transport zones."""
    from vmware_nsx.ops.inventory import list_transport_zones

    client, _ = cli._get_connection(target, config)
    zones = list_transport_zones(client)
    table = Table(title=f"Transport Zones ({len(zones)})")
    table.add_column("ID", style="cyan")
    table.add_column("Display Name")
    table.add_column("Type")
    for z in zones:
        table.add_row(z["id"], z["display_name"], z["transport_type"])
    console.print(table)


@inventory_app.command("list-transport-nodes")
@_cli_errors
def inventory_list_transport_nodes(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List all transport nodes."""
    from vmware_nsx.ops.inventory import list_transport_nodes

    client, _ = cli._get_connection(target, config)
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
@_cli_errors
def inventory_list_edge_clusters(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List all edge clusters."""
    from vmware_nsx.ops.inventory import list_edge_clusters

    client, _ = cli._get_connection(target, config)
    clusters = list_edge_clusters(client)
    table = Table(title=f"Edge Clusters ({len(clusters)})")
    table.add_column("ID", style="cyan")
    table.add_column("Display Name")
    table.add_column("Members", justify="right")
    table.add_column("Deployment Type")
    for c in clusters:
        table.add_row(c["id"], c["display_name"], str(c.get("member_count", "-")), c.get("deployment_type", "-"))
    console.print(table)
