"""Configuration management for VMware NSX.

Loads targets and settings from YAML config file + environment variables.
Passwords are NEVER stored in config files — always via environment variables.
"""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

CONFIG_DIR = Path.home() / ".vmware-nsx"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
ENV_FILE = CONFIG_DIR / ".env"

_log = logging.getLogger("vmware-nsx.config")

# Load passwords from .env file (if exists) before any config access
load_dotenv(ENV_FILE)


def _check_env_permissions() -> None:
    """Warn if .env file has permissions wider than owner-only (600)."""
    if not ENV_FILE.exists():
        return
    try:
        mode = ENV_FILE.stat().st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            _log.warning(
                "Security warning: %s has permissions %s (should be 600). "
                "Run: chmod 600 %s",
                ENV_FILE,
                oct(stat.S_IMODE(mode)),
                ENV_FILE,
            )
    except OSError:
        pass


_check_env_permissions()


@dataclass(frozen=True)
class TargetConfig:
    """An NSX Manager connection target."""

    host: str
    username: str
    port: int = 443
    verify_ssl: bool = True

    def get_password(self, target_name: str) -> str:
        """Retrieve password from environment variable.

        Convention: VMWARE_NSX_<TARGET>_PASSWORD
        where <TARGET> is upper-cased with hyphens replaced by underscores.
        """
        env_key = f"VMWARE_NSX_{target_name.upper().replace('-', '_')}_PASSWORD"
        pw = os.environ.get(env_key, "")
        if not pw:
            raise OSError(
                f"Password not found. Set environment variable: {env_key}"
            )
        return pw


@dataclass(frozen=True)
class AppConfig:
    """Top-level application config."""

    targets: dict[str, TargetConfig] = ()  # type: ignore[assignment]
    default_target: str | None = None

    def get_target(self, name: str) -> TargetConfig | None:
        """Look up a target by name. Returns None if not found."""
        return self.targets.get(name)  # type: ignore[union-attr]

    def get_target_strict(self, name: str) -> TargetConfig:
        """Look up a target by name. Raises KeyError if not found."""
        cfg = self.get_target(name)
        if cfg is None:
            available = ", ".join(self.targets.keys())  # type: ignore[union-attr]
            raise KeyError(f"Target '{name}' not found. Available: {available}")
        return cfg


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load config from YAML file, with env var overrides for passwords."""
    env_override = os.environ.get("VMWARE_NSX_CONFIG")
    path = config_path or (Path(env_override) if env_override else CONFIG_FILE)

    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Copy config.example.yaml to {CONFIG_FILE} and edit it."
        )

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    targets: dict[str, TargetConfig] = {}
    for name, t in raw.get("targets", {}).items():
        targets[name] = TargetConfig(
            host=t["host"],
            username=t.get("username", "admin"),
            port=t.get("port", 443),
            verify_ssl=t.get("verify_ssl", True),
        )

    default = raw.get("default_target")
    if default and default not in targets:
        _log.warning("default_target '%s' not found in targets, ignoring", default)
        default = None

    return AppConfig(targets=targets, default_target=default)
