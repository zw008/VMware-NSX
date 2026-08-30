"""Keep the suite out of the operator's own audit log.

``~/.vmware-nsx/audit.log`` is a real artefact on a real machine: it is what an
operator opens to see what changed on the NSX manager. A test run that appends
``delete_segment seg-x`` to it is writing a record of a deletion that never
happened into the file whose whole value is that its records are true.

The CLI sink has always leaked this way; the MCP sink began to when
``_write_audit`` gave the write tools the log they were missing. Both are
redirected here for the whole session, so a test that wants to read entries back
overrides only its own copy (``monkeypatch`` in a function fixture is applied
after this and restored before the next test).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _skill_audit_log_stays_in_tmp(tmp_path_factory):
    from vmware_nsx import cli
    from vmware_nsx.cli import _base
    from vmware_nsx.mcp_server import _write_audit
    from vmware_nsx.notify.audit import AuditLogger

    sink = AuditLogger(log_file=str(tmp_path_factory.mktemp("skill-audit") / "audit.log"))
    saved = (_write_audit._audit, _base._audit, cli._audit)
    _write_audit._audit = sink
    _base._audit = sink
    # ``cli`` re-exports ``_base._audit`` by value, and command bodies reach it
    # through the package namespace (``cli._audit.log``), so rebinding one name
    # leaves the other pointing at the real file.
    cli._audit = sink
    yield sink
    _write_audit._audit, _base._audit, cli._audit = saved
