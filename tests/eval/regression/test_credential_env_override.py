"""Regression: per-target username is overridable from the environment.

Reported against the family via VMware-AIops#33: the password could be injected
from a secret store but the username could only come from config.yaml, so a
deployment that externalises credentials could only externalise half the pair —
a config username silently paired with another account's env password
authenticates as nobody.

The pin that matters is *late binding*. ``get_username`` must be a method that
reads the environment on every call, exactly like ``get_password``. If either
half is resolved once at load time, a rotation moves one half and strands the
other, which is precisely the failure this override exists to prevent.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from vmware_nsx.config import AppConfig, TargetConfig
from vmware_nsx.connection import ConnectionManager

# Target "nsx-prod" -> VMWARE_NSX_NSX_PROD_{USERNAME,PASSWORD}
_USER_KEY = "VMWARE_NSX_NSX_PROD_USERNAME"
_PW_KEY = "VMWARE_NSX_NSX_PROD_PASSWORD"


def _target() -> TargetConfig:
    return TargetConfig(host="nsx.example.com", username="config-admin")


def test_username_env_overrides_config(monkeypatch):
    monkeypatch.setenv(_USER_KEY, "vault-admin")
    assert _target().get_username("nsx-prod") == "vault-admin"


def test_username_falls_back_to_config_when_env_unset(monkeypatch):
    monkeypatch.delenv(_USER_KEY, raising=False)
    assert _target().get_username("nsx-prod") == "config-admin"


def test_empty_env_username_falls_back_to_config(monkeypatch):
    """An empty override must not blank the username — it is never a valid
    account, and silently sending "" would surface as a confusing 403."""
    monkeypatch.setenv(_USER_KEY, "")
    assert _target().get_username("nsx-prod") == "config-admin"


def test_hyphenated_target_maps_to_underscored_key(monkeypatch):
    """Same name mangling as get_password, or the pair reads two different
    targets' variables."""
    monkeypatch.setenv("VMWARE_NSX_NSX_LAB_USERNAME", "lab-admin")
    assert _target().get_username("nsx-lab") == "lab-admin"


def test_username_and_password_resolve_together_across_rotation(monkeypatch):
    """THE pin: rotate both env vars and both halves must follow.

    A username cached at load time would keep returning the pre-rotation value
    while the password moved on — the split-credential bug this guards.
    """
    target = _target()

    monkeypatch.setenv(_USER_KEY, "svc-account-v1")
    monkeypatch.setenv(_PW_KEY, "pw-v1")
    assert (target.get_username("nsx-prod"), target.get_password("nsx-prod")) == (
        "svc-account-v1",
        "pw-v1",
    )

    # Secret store rotates the credential pair under a long-lived process.
    monkeypatch.setenv(_USER_KEY, "svc-account-v2")
    monkeypatch.setenv(_PW_KEY, "pw-v2")
    assert (target.get_username("nsx-prod"), target.get_password("nsx-prod")) == (
        "svc-account-v2",
        "pw-v2",
    )


def test_connection_manager_authenticates_with_env_username(monkeypatch):
    """The override is worthless unless the connection layer actually uses it."""
    captured: dict = {}

    def _fake_client(target, password, username=None, *, target_name=""):
        captured["username"] = username
        captured["password"] = password
        captured["target_name"] = target_name
        return MagicMock()

    monkeypatch.setattr("vmware_nsx.connection.NsxClient", _fake_client)
    monkeypatch.setenv(_USER_KEY, "vault-admin")
    monkeypatch.setenv(_PW_KEY, "vault-pw")

    cfg = AppConfig(targets={"nsx-prod": _target()}, default_target="nsx-prod")
    ConnectionManager(cfg).connect("nsx-prod")

    # target_name is what connection errors name instead of the resolved
    # host:port, so it has to actually reach the client.
    assert captured == {
        "username": "vault-admin",
        "password": "vault-pw",
        "target_name": "nsx-prod",
    }


def test_connection_manager_falls_back_to_config_username(monkeypatch):
    """With no override set, the connection layer must still send the
    configured username — the override is additive, not a new requirement."""
    captured: dict = {}

    def _fake_client(target, password, username=None, *, target_name=""):
        captured["username"] = username
        return MagicMock()

    monkeypatch.setattr("vmware_nsx.connection.NsxClient", _fake_client)
    monkeypatch.delenv(_USER_KEY, raising=False)
    monkeypatch.setenv(_PW_KEY, "vault-pw")

    cfg = AppConfig(targets={"nsx-prod": _target()}, default_target="nsx-prod")
    ConnectionManager(cfg).connect("nsx-prod")

    assert captured["username"] == "config-admin"
