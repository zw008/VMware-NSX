"""The doctor must diagnose the config file the tools will actually load.

Real-hardware finding, 2026-08-30, first hit on the sibling Aria skill and
reproduced here: with ``VMWARE_NSX_CONFIG`` set, ``vmware-nsx doctor`` reported
"Config file PASS" and "Config parse PASS — 1 target(s) configured" against
``~/.vmware-nsx/config.yaml`` while ``load_config()`` — the call every tool
makes — raised ``FileNotFoundError`` on the path in the variable.

``load_config`` resolves ``config_path or $VMWARE_NSX_CONFIG or CONFIG_FILE``.
``run_doctor`` resolved ``config_path or CONFIG_FILE``, skipping the env var,
and then passed that path *explicitly* to ``load_config`` — which suppressed the
env var there too. So the doctor did not merely check a different file, it made
itself consistent with the wrong one, and produced a green report for a
configuration nothing else would ever read.

A diagnostic that green-lights a file the tools do not open is worse than no
diagnostic: it converts "my tools fail" into "my tools fail and the checker says
they should not", which is where the operator stops trusting the checker.

The precedence now lives in exactly one function, ``resolve_config_path``, that
both callers use — two copies of a rule do not disagree loudly, they disagree
slowly, which is how this one drifted (CLAUDE.md 形态 #6).
"""

from __future__ import annotations

import inspect

import pytest

from vmware_nsx import config as cfg
from vmware_nsx import doctor as doc

# Deliberately different target counts: the count printed by the report is what
# tells us which of the two files the doctor actually opened.
_ONE_TARGET = """
targets:
  only-in-the-default:
    host: 127.0.0.1
    port: 1
    username: admin
"""

_THREE_TARGETS = """
targets:
  a:
    host: 127.0.0.1
    port: 1
    username: admin
  b:
    host: 127.0.0.1
    port: 1
    username: admin
  c:
    host: 127.0.0.1
    port: 1
    username: admin
"""


def _flat(text: str) -> str:
    """The report with whitespace and table drawing removed.

    Rich wraps a long path across cells; comparing the flattened text keeps the
    assertions about *which file* independent of the table layout.
    """
    return "".join(ch for ch in text if not ch.isspace() and ch not in "│┃")


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """A default config that exists and is valid, so the only way the doctor can
    report on the env var's file is by resolving it."""
    default = tmp_path / "default.yaml"
    default.write_text(_ONE_TARGET)
    monkeypatch.setattr(cfg, "CONFIG_FILE", default)
    monkeypatch.setattr(cfg, "ENV_FILE", tmp_path / "no-such.env")
    monkeypatch.delenv("VMWARE_NSX_CONFIG", raising=False)
    # Rich elides long details at 80 columns, so an assertion about a tmp_path
    # would be measuring the terminal rather than the doctor.
    monkeypatch.setenv("COLUMNS", "300")
    return default


def test_the_env_var_decides_which_file_is_resolved(sandbox, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere.yaml"
    elsewhere.write_text(_THREE_TARGETS)
    monkeypatch.setenv("VMWARE_NSX_CONFIG", str(elsewhere))

    assert cfg.resolve_config_path() == elsewhere


def test_an_explicit_path_still_beats_the_env_var(sandbox, tmp_path, monkeypatch):
    """The control on precedence: ``--config`` is the operator saying which file
    they mean, and it has to keep winning."""
    explicit = tmp_path / "explicit.yaml"
    explicit.write_text(_ONE_TARGET)
    monkeypatch.setenv("VMWARE_NSX_CONFIG", str(tmp_path / "ignored.yaml"))

    assert cfg.resolve_config_path(explicit) == explicit
    assert len(cfg.load_config(explicit).targets) == 1


def test_with_neither_it_is_the_default(sandbox):
    assert cfg.resolve_config_path() == cfg.CONFIG_FILE


def test_doctor_reads_the_env_vars_file_not_the_default(
    sandbox, tmp_path, monkeypatch, capsys
):
    """The positive half: pointed at a real file elsewhere, the doctor reports
    on that one — three targets, not the default's one."""
    elsewhere = tmp_path / "elsewhere.yaml"
    elsewhere.write_text(_THREE_TARGETS)
    monkeypatch.setenv("VMWARE_NSX_CONFIG", str(elsewhere))

    doc.run_doctor(skip_auth=True)
    out = _flat(capsys.readouterr().out)

    assert str(elsewhere) in out, "the report must name the file it looked at"
    assert "3target(s)configured" in out, (
        "the doctor counted the default file's targets, so it parsed the file "
        "the tools will never open"
    )


def test_doctor_fails_when_the_env_var_points_at_a_missing_file(
    sandbox, tmp_path, monkeypatch, capsys
):
    """The reported failure. The default config here exists and is perfectly
    valid; it is simply not the file the tools will open."""
    missing = tmp_path / "not-there.yaml"
    monkeypatch.setenv("VMWARE_NSX_CONFIG", str(missing))

    ok = doc.run_doctor(skip_auth=True)
    out = _flat(capsys.readouterr().out)

    assert ok is False
    assert str(missing) in out, (
        "the report must name the file it looked at — a verdict about an "
        "unnamed file is what made this take real hardware to find"
    )
    assert "1target(s)configured" not in out, (
        "doctor parsed the default config and called it green while every tool "
        "call raises FileNotFoundError on the path in $VMWARE_NSX_CONFIG"
    )


def test_load_config_and_the_doctor_cannot_disagree():
    """Structural, not behavioural: both go through the one resolver, so a
    future edit to either cannot silently desynchronise them again."""
    for fn in (cfg.load_config, doc.run_doctor):
        source = inspect.getsource(fn)
        assert "resolve_config_path" in source, (
            f"{fn.__qualname__} resolves the config path by itself again; that "
            f"is the duplication this test exists to prevent"
        )


def test_the_mcp_server_does_not_keep_its_own_copy_of_the_precedence():
    """The third copy. The MCP server read $VMWARE_NSX_CONFIG itself and passed
    the result down explicitly — the same duplication, and the reason a change
    to the rule would have had to be made in three places to take effect."""
    from vmware_nsx.mcp_server import server

    source = inspect.getsource(server._get_connection)
    assert "os.environ" not in source, (
        "_get_connection resolves the config path itself; let load_config do it"
    )
