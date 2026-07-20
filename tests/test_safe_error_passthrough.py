"""A teaching message the agent never sees is not a teaching message.

``_safe_error`` reduces unrecognised exceptions to ``"<Class>: operation
failed."`` so raw NSX Manager text cannot leak. The allowlist it checks against
was an enumeration, and an enumeration drifts: two exceptions this skill raises
deliberately were missing from it, so their messages were replaced by their
class names on the way to the agent.

``OSError`` is the one that mattered most. ``config.py`` raises exactly one —
the missing-password error, this family's most common first-run failure — and
its entire remedy is the env var name it names (``VMWARE_NSX_<TARGET>_PASSWORD``,
whose ``NSX_`` segment is easy to omit). ``ConnectionError`` was the second:
``connection.py`` raises it when session creation succeeds but returns no
X-XSRF-TOKEN, and that message names the proxy-stripping cause and the config
keys to check. Both arrived as ``<Class>: operation failed.``

The defect was invisible from the CLI, which prints these messages in full, and
invisible to the error-quality eval, which reads the message at the raise site
rather than what survives the wrapper.

So the rule is the inverse of an enumeration: every exception this skill raises
on purpose passes through, and only genuinely unplanned ones are reduced.
"""

from __future__ import annotations

import pytest

from vmware_nsx.connection import NsxApiError
from vmware_nsx.mcp_server._shared import _safe_error

TEACHING = "Segment 'web-seg' not found. Run segment_list to see available segments."

ENV_KEY = "VMWARE_NSX_PROD_PASSWORD"
MISSING_PASSWORD = (
    f"NSX password not found for target 'prod'. Set {ENV_KEY} "
    "in ~/.vmware-nsx/.env (chmod 600) or export it, then retry. "
    "'vmware-nsx init' writes that file for you."
)


def test_missing_password_keeps_the_env_var_name():
    """The single OSError config.py raises — and the whole point of it is the name."""
    out = _safe_error(OSError(MISSING_PASSWORD), "segment_list")
    assert ENV_KEY in out
    assert "operation failed" not in out


def test_missing_xsrf_token_keeps_its_hint():
    """connection.py raises ConnectionError with the proxy-stripping explanation."""
    msg = (
        "NSX session creation on nsx.internal:443 succeeded but returned no "
        "X-XSRF-TOKEN header. Check that host and port in ~/.vmware-nsx/config.yaml "
        "point at the NSX Manager itself — a proxy in front of it can strip the "
        "header. Then run 'vmware-nsx doctor'."
    )
    out = _safe_error(ConnectionError(msg), "segment_list")
    assert "X-XSRF-TOKEN" in out
    assert "operation failed" not in out


def test_nsx_api_error_keeps_its_message():
    """The connection layer's teaching errors are the ones agents act on."""
    assert _safe_error(NsxApiError(TEACHING, status_code=404), "segment_get") == TEACHING


@pytest.mark.parametrize("exc_type", [ValueError, FileNotFoundError, KeyError, PermissionError])
def test_validation_errors_still_pass_through(exc_type):
    assert "web-seg" in _safe_error(exc_type(TEACHING), "t")


def test_unplanned_exceptions_are_still_reduced():
    """The redaction this allowlist exists for has to keep working."""
    out = _safe_error(RuntimeError("https://admin:hunter2@nsx.internal/api/v1/segments"), "t")
    assert out == "RuntimeError: operation failed."
    assert "hunter2" not in out


def test_message_is_still_truncated():
    """Length capping is the other half of the guard."""
    assert len(_safe_error(NsxApiError("x" * 900), "t")) <= 300
