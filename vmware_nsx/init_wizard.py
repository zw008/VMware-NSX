"""Interactive first-run setup wizard — ``vmware-nsx init``.

Replaces the hand-rolled "mkdir + cp config.example.yaml + edit YAML + remember
chmod 600" dance with guided prompts. Writes config.yaml + .env, sets the
correct per-target password env-var name (``VMWARE_NSX_<TARGET>_PASSWORD``),
obfuscates the password to grep-safe ``b64:`` form immediately (never left
plaintext on disk), locks .env to 0600, and offers to verify the connection.

Only touches local config files — no NSX mutation. NSX Manager authenticates
via form-body POST so special-character passwords are handled safely
(踩坑 #10/#21); the stored password is the literal value typed here.
"""

from __future__ import annotations

import os
from typing import Any

import typer
import yaml
from rich.console import Console

from vmware_nsx.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    ENV_FILE,
    _autoencode_env_file,
)

console = Console()


def _env_key_for(name: str) -> str:
    """The password env-var name the loader expects for a target.

    Mirrors ``TargetConfig.get_password`` exactly: NSX uses a ``VMWARE_NSX_``
    prefix (so target ``nsx-prod`` → ``VMWARE_NSX_NSX_PROD_PASSWORD``).
    """
    return f"VMWARE_NSX_{name.upper().replace('-', '_')}_PASSWORD"


def _prompt_target() -> dict[str, Any]:
    """Collect one NSX Manager target's fields interactively."""
    name = typer.prompt("Target name (short id, e.g. nsx-prod)", default="nsx-prod")
    host = typer.prompt("NSX Manager host (FQDN or IP)")
    username = typer.prompt("Username", default="admin")
    port = typer.prompt("Port", default=443, type=int)
    verify_ssl = typer.confirm(
        "Verify the TLS certificate? (answer No for default self-signed NSX Managers)",
        default=True,
    )
    return {
        "name": name,
        "host": host,
        "username": username,
        "port": port,
        "verify_ssl": verify_ssl,
    }


def _write_env(name: str, password: str) -> str:
    """Write the password to .env (grep-safe b64), 0600, and the live env."""
    from dotenv import set_key

    env_key = _env_key_for(name)
    ENV_FILE.touch(mode=0o600, exist_ok=True)
    os.chmod(ENV_FILE, 0o600)
    set_key(str(ENV_FILE), env_key, password, quote_mode="never")
    # Obfuscate to b64: immediately so the secret is never left plaintext on
    # disk, even before the next load (honours the .env-no-plaintext rule).
    _autoencode_env_file(ENV_FILE)
    os.chmod(ENV_FILE, 0o600)
    # Make it visible to an in-process connection test this session.
    os.environ[env_key] = password
    return env_key


def run_init(force: bool = False, skip_test: bool = False) -> int:
    """Run the interactive setup wizard. Returns a process exit code."""
    console.print("[bold cyan]vmware-nsx init[/] — guided setup\n")

    if CONFIG_FILE.exists() and not force:
        console.print(f"[yellow]Config already exists:[/] {CONFIG_FILE}")
        if not typer.confirm("Overwrite it?", default=False):
            console.print("Kept existing config. Edit it by hand or re-run with --force.")
            return 0

    target = _prompt_target()
    password = typer.prompt("Password", hide_input=True)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    name = target["name"]
    config = {
        "targets": {
            name: {
                "host": target["host"],
                "username": target["username"],
                "port": target["port"],
                "verify_ssl": target["verify_ssl"],
            }
        },
        "default_target": name,
    }
    CONFIG_FILE.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    env_key = _write_env(name, password)

    console.print()
    console.print(f"[green]✓[/] Wrote {CONFIG_FILE}")
    console.print(f"[green]✓[/] Wrote {ENV_FILE} (0600, password stored grep-safe as {env_key})")
    if not target["verify_ssl"]:
        console.print("[yellow]ℹ TLS verification disabled — expected for default self-signed NSX Managers.[/]")

    if skip_test:
        console.print("\nNext: [cyan]vmware-nsx doctor[/] to verify the connection.")
        return 0

    if not typer.confirm("\nTest the connection now?", default=True):
        console.print("Next: [cyan]vmware-nsx doctor[/] to verify the connection.")
        return 0

    from vmware_nsx.doctor import run_doctor

    console.print()
    return 0 if run_doctor() else 1
