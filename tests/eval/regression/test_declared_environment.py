"""Targets declare their environment, and policy scopes by that declaration.

Policy scopes rules by environment ("irreversible work in production needs a
second person"), but ``env`` used to be derived from the *target's name* — so
the rule only fired if an operator happened to name a target the literal string
in the rule. Nobody names an NSX Manager ``production``; they name it
``nsx-prod``. The control was configured and inert.

Environment is now an explicit declaration in config.yaml. This pins the
skill's half of that contract end to end: ``TargetConfig`` parses the field,
``AppConfig.environment_for`` resolves it (including via ``default_target``),
and ``mcp_server.server`` registers that lookup with vmware-policy so the rules
can fire at all.

The rollout is two-step, and both steps are pinned here:

* **today (baseline)** — a state-changing tool against a target that declares
  no environment still runs, and logs a warning naming the fix;
* **next major release (enforcing)** — the same call is refused, with an error
  telling the operator which config key to add.

Read-only tools are unaffected under both. An operator who only inspects NSX
needs no config change whatsoever, now or later.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from vmware_policy.decorators import PolicyDenied
from vmware_policy.environment import set_environment_resolver
from vmware_policy.policy import reset_policy_engine

DECLARED = "nsx-lab"
UNDECLARED = "nsx-unlabelled"


def _write_config(tmp_path: Path) -> Path:
    """A config with one target that declares an environment and one that does not."""
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "targets": {
                    DECLARED: {
                        "host": "10.0.0.50",
                        "username": "admin",
                        "environment": "lab",
                    },
                    UNDECLARED: {"host": "10.0.0.51", "username": "admin"},
                },
                "default_target": DECLARED,
            }
        )
    )
    return path


def _server(tmp_path, monkeypatch, rules: str | None):
    """The real server, wired to the real config-backed environment resolver.

    ``rules`` is written to the harness home as the operator's rules.yaml, or
    omitted to fall back to vmware-policy's packaged baseline. Redirecting
    ``OPS_HOME`` also keeps audit/undo state out of the developer's ~/.vmware.
    """
    import mcp_server.server as srv

    ops_home = tmp_path / "ops"
    ops_home.mkdir()
    if rules is not None:
        (ops_home / "rules.yaml").write_text(rules)
    monkeypatch.setenv("OPS_HOME", str(ops_home))
    reset_policy_engine()

    monkeypatch.setenv("VMWARE_NSX_CONFIG", str(_write_config(tmp_path)))
    set_environment_resolver(srv._environment_for)
    return srv


@pytest.fixture(autouse=True)
def _reset_policy_singleton():
    yield
    reset_policy_engine()
    set_environment_resolver(None)


@pytest.fixture
def baseline(tmp_path, monkeypatch):
    """The shipped baseline — currently in its warn-only migration setting."""
    return _server(tmp_path, monkeypatch, rules=None)


@pytest.fixture
def enforcing(tmp_path, monkeypatch):
    """The same skill under the requirement as the next major release ships it.

    Flipping one word in the baseline is the whole of that release, so the
    enforcing behaviour is worth having under test from now.
    """
    return _server(tmp_path, monkeypatch, rules="require_declared_environment: true\n")


# ── the config layer parses and resolves the declaration ────────────────


def test_config_parses_the_declared_environment(tmp_path) -> None:
    from vmware_nsx.config import load_config

    config = load_config(_write_config(tmp_path))

    assert config.environment_for(DECLARED) == "lab"
    assert config.environment_for(UNDECLARED) == ""
    assert config.environment_for("no-such-target") == ""
    # An omitted --target resolves to default_target, not to "undeclared" —
    # otherwise every "use my default NSX Manager" write would be gated.
    assert config.environment_for(None) == "lab"


def test_server_registers_its_resolver_with_policy(tmp_path, monkeypatch) -> None:
    """Without this registration every target reads as undeclared, and the
    environment-scoped rules stay as inert as they were before the change."""
    from vmware_policy.environment import resolve_environment

    srv = _server(tmp_path, monkeypatch, rules=None)
    set_environment_resolver(srv._environment_for)

    assert resolve_environment(DECLARED) == "lab"
    assert resolve_environment(UNDECLARED) == ""


# ── writes: today they warn, next major release they are refused ────────


def test_write_against_undeclared_target_warns_but_runs(baseline, caplog) -> None:
    """Migration window: nothing breaks yet, but the operator is told."""
    import vmware_policy.policy as policy_mod

    policy_mod._warned_operations.clear()  # warned once per process otherwise

    with caplog.at_level("WARNING"), patch.object(
        baseline, "_get_connection", return_value=MagicMock()
    ), patch("vmware_nsx.ops.nat_route_mgmt.delete_ip_pool") as ops_delete:
        result = baseline.delete_ip_pool(pool_id="pool-1", target=UNDECLARED)

    ops_delete.assert_called_once()
    assert "deleted" in result
    assert "environment" in caplog.text
    assert "config.yaml" in caplog.text


def test_write_against_undeclared_target_is_denied_when_enforcing(enforcing) -> None:
    with patch.object(enforcing, "_get_connection", return_value=MagicMock()):
        with pytest.raises(PolicyDenied) as denied:
            enforcing.delete_ip_pool(pool_id="pool-1", target=UNDECLARED)

    reason = str(denied.value)
    # The operator must be able to fix this without reading the docs.
    assert "environment" in reason
    assert "config.yaml" in reason


@pytest.mark.parametrize("fixture", ["baseline", "enforcing"])
def test_write_against_declared_target_succeeds(request, fixture) -> None:
    server = request.getfixturevalue(fixture)

    with patch.object(server, "_get_connection", return_value=MagicMock()), patch(
        "vmware_nsx.ops.nat_route_mgmt.delete_ip_pool"
    ) as ops_delete:
        result = server.delete_ip_pool(pool_id="pool-1", target=DECLARED)

    ops_delete.assert_called_once()
    assert "deleted" in result


# ── reads are never gated, declared or not ──────────────────────────────


@pytest.mark.parametrize("fixture", ["baseline", "enforcing"])
@pytest.mark.parametrize("target", [DECLARED, UNDECLARED])
def test_reads_work_whether_or_not_the_target_declares(request, fixture, target) -> None:
    """Read-only work must keep working with no config changes at all."""
    server = request.getfixturevalue(fixture)
    segments = [{"id": "seg-1", "display_name": "web"}]

    with patch.object(server, "_get_connection", return_value=MagicMock()), patch(
        "vmware_nsx.ops.inventory.list_segments", return_value=segments
    ):
        assert server.list_segments(target=target) == segments
