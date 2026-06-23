"""Configuration management for VMware NSX.

Loads targets and settings from YAML config file + environment variables.
Passwords are NEVER stored in config files — always via environment variables.
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import dotenv_values, load_dotenv, set_key

CONFIG_DIR = Path.home() / ".vmware-nsx"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
ENV_FILE = CONFIG_DIR / ".env"

_log = logging.getLogger("vmware-nsx.config")

_PW_KEY_RE = re.compile(r"[A-Z][A-Z0-9_]*_PASSWORD")


def _is_b64_token(value: str) -> tuple[bool, str]:
    """Return ``(True, decoded)`` if ``value`` is a valid ``b64:`` token, else ``(False, "")``.

    Recognises already-encoded values (for idempotency) and decodes on read. A
    value that merely *starts with* ``b64:`` but is not valid base64 (e.g. a real
    password ``b64:hunter2``) is NOT a token — it is treated as plaintext, so such
    a password still round-trips correctly instead of being corrupted.
    """
    if not value.startswith("b64:"):
        return (False, "")
    try:
        return (True, base64.b64decode(value[4:], validate=True).decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return (False, "")


def _decode_secret(value: str) -> str:
    """Decode a ``b64:`` token; any other value passes through unchanged.

    Obfuscation to defeat casual grep — NOT encryption.
    """
    ok, decoded = _is_b64_token(value)
    return decoded if ok else value


def _autoencode_env_file(env_file: Path) -> None:
    """Rewrite plaintext ``*_PASSWORD`` values in .env to grep-safe ``b64:`` form.

    Values are read and written through python-dotenv's own parser/serializer
    (``dotenv_values`` + ``set_key``), so the stored value is exactly what
    ``load_dotenv`` would return — quoting, inline comments, and trailing
    whitespace are handled identically and the secret never drifts from the
    configured one. Idempotent (already-``b64:`` tokens are skipped); only
    ``*_PASSWORD`` keys are touched. Obfuscation, not encryption.
    """
    if not env_file.exists():
        return
    try:
        parsed = dotenv_values(env_file)
    except OSError:
        return

    changed = False
    for key, value in parsed.items():
        if not value or not _PW_KEY_RE.fullmatch(key) or _is_b64_token(value)[0]:
            continue
        encoded = "b64:" + base64.b64encode(value.encode("utf-8")).decode("ascii")
        try:
            set_key(str(env_file), key, encoded, quote_mode="never")
            changed = True
        except OSError as exc:
            _log.warning("Could not auto-encode %s in %s: %s", key, env_file, exc)

    if not changed:
        return
    try:
        os.chmod(env_file, 0o600)
    except OSError:
        pass
    _log.warning(
        "Auto-encoded plaintext password(s) in %s to b64: (grep-safe; "
        "obfuscation, not encryption).",
        env_file,
    )


# Auto-encode any plaintext passwords in .env, then load it into the environment
_autoencode_env_file(ENV_FILE)
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
        return _decode_secret(pw)


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
