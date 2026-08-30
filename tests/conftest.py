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

import atexit as _atexit
import os as _os
import shutil as _shutil
import tempfile as _tempfile
from pathlib import Path as _Path

from vmware_policy.audit import reset_engine as _reset_engine

# ── shared-audit sandbox, installed at import time ───────────────────────────
#
# A session-scoped autouse fixture is too late for this one: vmware_policy's
# audit engine is a lazily built singleton keyed to the path it first resolved,
# and per-skill loggers bind Path.home() when their module is imported —
# collection has already imported every test module before any fixture runs.
#
# OPS_HOME moves vmware_policy's shared ~/.vmware/audit.db. Without it this
# suite appended 78 rows per run to the operator's real audit trail, which
# held over 30,000 — most of them tool names nobody had ever invoked. An audit
# trail containing test fiction cannot answer the question it is kept for.
_REAL_HOME = _Path(_os.path.expanduser("~"))
_SANDBOX_HOME = _Path(_tempfile.mkdtemp(prefix="vmware-nsx-tests-"))
_os.environ["HOME"] = str(_SANDBOX_HOME)
_os.environ["OPS_HOME"] = str(_SANDBOX_HOME / ".vmware")
_os.environ["USERPROFILE"] = str(_SANDBOX_HOME)
_reset_engine()
_atexit.register(_shutil.rmtree, _SANDBOX_HOME, True)

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
