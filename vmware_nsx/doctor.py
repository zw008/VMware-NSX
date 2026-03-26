"""Pre-flight diagnostics for vmware-nsx."""

from __future__ import annotations

import logging
import os
import socket
import stat
from pathlib import Path

from rich.console import Console
from rich.table import Table

_log = logging.getLogger("vmware-nsx.doctor")
console = Console()


def run_doctor(
    config_path: Path | None = None,
    skip_auth: bool = False,
) -> bool:
    """Run all pre-flight checks. Returns True if all pass."""
    from vmware_nsx.config import CONFIG_FILE, ENV_FILE, load_config

    checks: list[tuple[str, bool, str]] = []

    # ── 1. Config file exists ────────────────────────────────────────────────
    path = config_path or CONFIG_FILE
    if path.exists():
        checks.append(("Config file", True, str(path)))
    else:
        checks.append((
            "Config file",
            False,
            f"Not found: {path}. Copy config.example.yaml to {CONFIG_FILE}",
        ))

    # ── 2. .env file permissions ─────────────────────────────────────────────
    if ENV_FILE.exists():
        try:
            mode = ENV_FILE.stat().st_mode
            perms = stat.S_IMODE(mode)
            if perms & (stat.S_IRWXG | stat.S_IRWXO):
                checks.append((
                    ".env permissions",
                    False,
                    f"Permissions {oct(perms)} too open. Run: chmod 600 {ENV_FILE}",
                ))
            else:
                checks.append((".env permissions", True, f"{oct(perms)} (owner-only)"))
        except OSError as e:
            checks.append((".env permissions", False, str(e)))
    else:
        checks.append((".env permissions", True, "No .env file (using shell env vars)"))

    # ── 3. Parse config / count targets ──────────────────────────────────────
    config = None
    try:
        config = load_config(path)
        target_count = len(config.targets)
        checks.append(("Config parse", True, f"{target_count} target(s) configured"))
    except Exception as e:
        checks.append(("Config parse", False, str(e)))

    if config is None:
        # Cannot proceed without config
        _print_table(checks)
        return False

    # ── 4. Password env vars set ─────────────────────────────────────────────
    for name, target_cfg in config.targets.items():
        try:
            _ = target_cfg.get_password(name)
            checks.append((f"Password ({name})", True, "Set"))
        except OSError as e:
            checks.append((f"Password ({name})", False, str(e)))

    # ── 5. Network connectivity (TCP to port 443) ────────────────────────────
    for name, target_cfg in config.targets.items():
        try:
            sock = socket.create_connection(
                (target_cfg.host, target_cfg.port), timeout=5,
            )
            sock.close()
            checks.append((
                f"Network ({name})",
                True,
                f"{target_cfg.host}:{target_cfg.port} reachable",
            ))
        except OSError as e:
            checks.append((
                f"Network ({name})",
                False,
                f"Cannot reach {target_cfg.host}:{target_cfg.port} - {e}",
            ))

    # ── 6 & 7. NSX authentication + version ─────────────────────────────────
    if not skip_auth:
        for name, target_cfg in config.targets.items():
            try:
                from vmware_nsx.connection import ConnectionManager

                mgr = ConnectionManager(config)
                client = mgr.connect(name)
                checks.append((f"NSX auth ({name})", True, "Session created"))

                # Get manager version
                try:
                    version_info = client.get("/api/v1/node/version")
                    version = version_info.get("product_version", "unknown")
                    checks.append((f"NSX version ({name})", True, f"v{version}"))
                except Exception as e:
                    checks.append((f"NSX version ({name})", False, str(e)))

                mgr.disconnect(name)
            except Exception as e:
                checks.append((f"NSX auth ({name})", False, str(e)))

    # ── 8. MCP server import check ───────────────────────────────────────────
    try:
        import mcp_server.server  # noqa: F401
        checks.append(("MCP server import", True, "mcp_server.server importable"))
    except ImportError as e:
        checks.append(("MCP server import", False, f"Import failed: {e}"))
    except Exception as e:
        checks.append(("MCP server import", False, str(e)))

    _print_table(checks)
    return all(passed for _, passed, _ in checks)


def _print_table(checks: list[tuple[str, bool, str]]) -> None:
    """Render the doctor results as a Rich table."""
    table = Table(title="vmware-nsx Doctor", show_header=True)
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail")

    for name, passed, detail in checks:
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        table.add_row(name, status, detail)

    console.print(table)
