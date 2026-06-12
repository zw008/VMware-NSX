"""Shared CLI plumbing: Typer sub-apps, option aliases, error decorator, helpers.

Command modules (``cli.inventory``, ``cli.segment``, …) register their commands
onto the sub-app instances defined here, and call the shared helpers via the
package namespace (``from vmware_nsx import cli`` then ``cli._get_connection``)
so that tests can ``patch("vmware_nsx.cli._get_connection")`` and have every
command pick up the patched callable.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Annotated, Any, Callable, TypeVar

import typer
from rich.console import Console

from vmware_nsx.notify.audit import AuditLogger

_audit = AuditLogger()
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
ip_pool_app = typer.Typer(help="IP pool management: create, delete.")
mcp_config_app = typer.Typer(help="Generate MCP server config for local AI agents.")

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

_F = TypeVar("_F", bound=Callable[..., Any])


def _cli_errors(fn: _F) -> _F:
    """Translate known operational errors into one red line + exit code 1.

    Without this, an NsxApiError (teaching error from the connection layer),
    a missing config file, or a bad config key surfaces as a raw Python
    traceback in the terminal. typer.Exit/typer.Abort pass through untouched.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        from vmware_nsx.connection import NsxApiError

        try:
            return fn(*args, **kwargs)
        except (NsxApiError, FileNotFoundError, KeyError, OSError) as exc:
            console.print(f"[red]Error: {exc}[/]")
            raise typer.Exit(1) from exc

    return wrapper  # type: ignore[return-value]


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
