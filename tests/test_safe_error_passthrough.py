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

v1.8.5 narrowed the ``OSError`` half of that. Bare ``OSError`` passed through
*any* OS-level failure, and ``sanitize`` only strips control characters and
truncates — it redacts nothing — so ``socket.gaierror`` (the name that failed to
resolve) and ``requests``-style connection errors (the full
``scheme://host:port/path``) reached the agent verbatim. ``config.py`` now
raises ``ConfigError``, a narrow ``OSError`` subclass, and the allowlist names
that instead.
"""

from __future__ import annotations

import socket
import ssl

import pytest

from vmware_nsx.config import ConfigError
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
    """The single config error config.py raises — the whole point of it is the name."""
    out = _safe_error(ConfigError(MISSING_PASSWORD), "segment_list")
    assert ENV_KEY in out
    assert "operation failed" not in out


def test_config_error_is_what_config_py_actually_raises(monkeypatch):
    """A test that constructs its own exception proves nothing about the caller.

    ``ConfigError`` only earns its allowlist entry if the missing-password path
    raises it; a stray ``raise OSError`` there would be reduced to a class name
    and this file would still be green.
    """
    from vmware_nsx.config import TargetConfig

    monkeypatch.delenv(ENV_KEY, raising=False)
    target = TargetConfig(host="nsx.example", username="admin")
    with pytest.raises(ConfigError) as ei:
        target.get_password("prod")
    assert ENV_KEY in _safe_error(ei.value, "segment_list")


def test_tls_failure_does_not_leak_the_certificate_subject():
    """An allowlist cannot express "not this one", so this needs a pre-check.

    ``ssl.SSLCertVerificationError`` inherits from ``ValueError`` as well as
    ``OSError`` — so removing ``OSError`` from the allowlist did nothing for it,
    and it would have kept handing the agent the certificate subject and the
    hostname it was presented for. ``_safe_error`` reduces ``ssl.SSLError``
    before it consults the allowlist at all.
    """
    exc = ssl.SSLCertVerificationError(
        1,
        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self signed "
        "certificate (_ssl.c:1000), subject CN=nsx-mgmt.corp.internal",
    )
    out = _safe_error(exc, "t")
    assert out == "SSLCertVerificationError: operation failed."
    assert "nsx-mgmt.corp.internal" not in out
    assert "CERTIFICATE_VERIFY_FAILED" not in out


def test_the_tls_pre_check_is_why_that_works():
    """Pins the mechanism, not just the outcome.

    If someone ever "simplifies" the pre-check away on the grounds that
    ``OSError`` is gone, the test above is the only thing standing between the
    agent and the certificate subject — so state plainly that the allowlist
    alone would let it through.
    """
    from vmware_nsx.mcp_server._shared import _safe_error as fn

    assert issubclass(ssl.SSLCertVerificationError, ValueError), (
        "the whole reason for the pre-check: it is a ValueError too"
    )
    assert "ValueError" in fn.__doc__ and "SSLError" in fn.__doc__


def test_dns_failure_does_not_leak_the_hostname():
    """The reason bare ``OSError`` had to go.

    ``socket.gaierror`` is an ``OSError`` with no authored text — its message is
    the name that failed to resolve, which is exactly what this wrapper exists
    to withhold.
    """
    out = _safe_error(socket.gaierror(-2, "Name or service not known: nsx-mgmt.corp.internal"), "t")
    assert out == "gaierror: operation failed."
    assert "nsx-mgmt.corp.internal" not in out


def test_generic_oserror_is_reduced():
    """Any other OS-level failure is unplanned text and is withheld."""
    out = _safe_error(OSError("[Errno 113] No route to host: 10.20.30.40:443"), "t")
    assert out == "OSError: operation failed."
    assert "10.20.30.40" not in out


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


def test_httpx_tls_failure_reaches_the_agent_without_the_certificate_detail():
    """The path a real self-signed manager actually takes.

    httpx raises ``ConnectError`` — not an ``ssl.SSLError`` — so the pre-check
    above never sees it, and ``connection.py`` translates it into an
    ``NsxApiError`` that ``_safe_error`` passes through verbatim. The only thing
    keeping the certificate text out of agent context is that the translation no
    longer interpolates the raw exception. This drives the real connection layer
    rather than asserting on a hand-built message.
    """
    import httpx

    from vmware_nsx.config import TargetConfig
    from vmware_nsx.connection import NsxApiError, NsxClient

    raw = "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1000)"

    def refuse(self, url, **kwargs):
        raise httpx.ConnectError(raw)

    target = TargetConfig(host="nsx-mgmt.corp.internal", username="admin")
    original = httpx.Client.post
    httpx.Client.post = refuse
    try:
        with pytest.raises(NsxApiError) as ei:
            NsxClient(target, "pw", target_name="prod-nsx")
    finally:
        httpx.Client.post = original

    out = _safe_error(ei.value, "list_segments")
    assert "CERTIFICATE_VERIFY_FAILED" not in out
    assert "nsx-mgmt.corp.internal" not in out, "the configured host must not ride along either"
    # Still teaches the fix, and names the config entry to edit.
    assert "verify_ssl" in out and "prod-nsx" in out
