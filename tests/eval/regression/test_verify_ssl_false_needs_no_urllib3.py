"""``verify_ssl: false`` must not require a package this skill never declared.

Real-hardware finding, 2026-08-30: on a clean install from PyPI, authenticating
against a target with ``verify_ssl: false`` — the VCF default, and the reason
that setting exists — died with ``No module named 'urllib3'``. Four skills in
the family were affected.

The import sat behind ``if not target.verify_ssl:``, so it never ran in this
repo's own tests: none of the four development environments has urllib3
installed either, which is exactly why nobody noticed. Every test that touches
this constructor uses a target with verification on.

The code it guarded was already inert. This client is **httpx**, which does not
use urllib3 and does not raise ``InsecureRequestWarning`` — verified directly:
an httpx request with ``verify=False`` emits no warnings and never loads
urllib3. So the call suppressed a warning that is never issued, at the cost of
making the family's default TLS posture depend on an undeclared dependency.

The fix is removal, not declaring the dependency. Declaring it would have made
the clean install work while keeping a line that does nothing.
"""

from __future__ import annotations

import builtins
import sys
from types import SimpleNamespace

import pytest

from vmware_nsx import connection as conn


@pytest.fixture
def no_urllib3(monkeypatch):
    """Make ``import urllib3`` fail, the way a clean install does.

    Not relying on it merely being absent from this venv: it is absent today,
    so the test would pass for the wrong reason the moment some future
    dependency pulls it in, and the guard would rot silently (形态 #1).
    """
    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "urllib3" or name.startswith("urllib3."):
            raise ModuleNotFoundError("No module named 'urllib3'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    monkeypatch.delitem(sys.modules, "urllib3", raising=False)
    return blocked


def _target(verify_ssl: bool):
    return SimpleNamespace(
        host="host.example",
        port=443,
        username="admin",
        verify_ssl=verify_ssl,
        domain="CORP",
        provider="Local",
    )


@pytest.mark.unit
def test_the_blocker_really_blocks(no_urllib3):
    """Positive control. A fixture that silently failed to block would make
    every assertion below vacuous — the shape this whole round keeps finding."""
    with pytest.raises(ModuleNotFoundError):
        __import__("urllib3")


@pytest.mark.unit
def test_a_client_can_be_built_against_a_self_signed_target(no_urllib3, monkeypatch):
    """The reported failure: this is the VCF default configuration."""
    monkeypatch.setattr(conn.NsxClient, "_create_session", lambda self: None)

    client = conn.NsxClient(_target(verify_ssl=False), "secret")

    assert client._client is not None


@pytest.mark.unit
def test_a_verifying_target_is_unaffected(no_urllib3, monkeypatch):
    """The control. The path that always worked must keep working."""
    monkeypatch.setattr(conn.NsxClient, "_create_session", lambda self: None)

    client = conn.NsxClient(_target(verify_ssl=True), "secret")

    assert client._client is not None


@pytest.mark.unit
def test_nothing_in_the_connection_layer_reaches_for_urllib3():
    """Source-level, deliberately, and load-bearing rather than decorative: the
    import is inside a branch, so a behavioural test only covers the branches it
    happens to take. This covers the ones it does not."""
    import inspect

    assert "urllib3" not in inspect.getsource(conn), (
        "an undeclared dependency is referenced again in the connection layer; "
        "if it is genuinely needed now, declare it in pyproject.toml first"
    )
