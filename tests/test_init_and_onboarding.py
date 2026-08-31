"""Regression tests for onboarding: the ``vmware-nsx init`` wizard, the doctor
init reference (no false promise — 踩坑 #2), and teaching REST auth/TLS errors
from the form-body session-create path (踩坑 #10/#21, do not regress).
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from vmware_nsx import init_wizard


# ── init wizard ──────────────────────────────────────────────────────────────


@pytest.fixture
def _wizard_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg_dir = tmp_path / ".vmware-nsx"
    monkeypatch.setattr(init_wizard, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(init_wizard, "CONFIG_FILE", cfg_dir / "config.yaml")
    monkeypatch.setattr(init_wizard, "ENV_FILE", cfg_dir / ".env")
    return cfg_dir


def _feed(monkeypatch: pytest.MonkeyPatch, answers: list[object], confirms: list[bool]) -> None:
    a = iter(answers)
    c = iter(confirms)
    monkeypatch.setattr(init_wizard.typer, "prompt", lambda *args, **kwargs: next(a))
    monkeypatch.setattr(init_wizard.typer, "confirm", lambda *args, **kwargs: next(c))


def test_init_writes_grep_safe_env(_wizard_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from vmware_nsx.config import _decode_secret

    _feed(
        monkeypatch,
        # target name, host, username, port, password
        answers=["nsx-lab", "10.1.2.3", "admin", 443, "S3cr3t!pw)"],
        confirms=[True],  # verify_ssl
    )
    assert init_wizard.run_init(skip_test=True) == 0

    env_path = _wizard_env / ".env"
    env_text = env_path.read_text(encoding="utf-8")
    assert "VMWARE_NSX_NSX_LAB_PASSWORD=b64:" in env_text
    assert "S3cr3t!pw)" not in env_text  # never plaintext on disk
    assert env_path.stat().st_mode & 0o777 == 0o600
    line = next(ln for ln in env_text.splitlines() if ln.startswith("VMWARE_NSX_NSX_LAB_PASSWORD="))
    # Round-trip: the stored b64 decodes back to the literal special-char pw.
    assert _decode_secret(line.split("=", 1)[1]) == "S3cr3t!pw)"


def test_init_writes_nsx_config_shape(_wizard_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import yaml

    from vmware_nsx.config import load_config

    _feed(
        monkeypatch,
        answers=["nsx-prod", "nsx.example.com", "svc-nsx", 443, "pw"],
        confirms=[False],  # verify_ssl False → self-signed lab
    )
    assert init_wizard.run_init(skip_test=True) == 0

    raw = yaml.safe_load((_wizard_env / "config.yaml").read_text(encoding="utf-8"))
    # targets is a dict keyed by name (NSX load_config shape), with default_target
    assert raw["default_target"] == "nsx-prod"
    assert raw["targets"]["nsx-prod"]["host"] == "nsx.example.com"
    assert raw["targets"]["nsx-prod"]["username"] == "svc-nsx"
    assert raw["targets"]["nsx-prod"]["verify_ssl"] is False

    # And it parses cleanly through the real loader.
    cfg = load_config(_wizard_env / "config.yaml")
    tgt = cfg.get_target_strict("nsx-prod")
    assert tgt.host == "nsx.example.com"
    assert tgt.verify_ssl is False


def test_env_key_matches_loader(_wizard_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The wizard's env-var name must equal what get_password() reads."""
    from vmware_nsx.config import TargetConfig

    _feed(
        monkeypatch,
        answers=["nsx-edge1", "10.0.0.9", "admin", 443, "topsecret"],
        confirms=[True],
    )
    assert init_wizard.run_init(skip_test=True) == 0

    tgt = TargetConfig(host="10.0.0.9", username="admin")
    # get_password reads the env var the wizard set this session.
    assert tgt.get_password("nsx-edge1") == "topsecret"


# ── doctor references a real init command (no false promise) ──────────────────


def _init_registered() -> bool:
    from vmware_nsx.cli import app

    return any(c.name == "init" for c in app.registered_commands)


def test_doctor_init_reference_is_backed_by_real_command():
    from vmware_nsx import doctor

    src = Path(doctor.__file__).read_text(encoding="utf-8")
    if "vmware-nsx init" in src:
        assert _init_registered(), "doctor recommends init but no such command is registered"


def test_init_command_is_registered():
    assert _init_registered(), "vmware-nsx init must be registered on the CLI app"


# ── REST form-body auth/TLS errors teach where to fix the problem ────────────


def _client_with_response(monkeypatch, *, status_code=None, raise_exc=None):
    """Build an NsxClient whose session-create POST returns a canned response.

    Bypasses the real network: patches httpx.Client.post on the instance so we
    can drive the auth / TLS error branches of _create_session deterministically.
    """
    from vmware_nsx.config import TargetConfig
    from vmware_nsx.connection import NsxClient

    target = TargetConfig(host="nsx.example.com", username="admin", verify_ssl=True)

    def fake_post(self, url, **kwargs):
        if raise_exc is not None:
            raise raise_exc
        request = httpx.Request("POST", "https://nsx.example.com/api/session/create")
        return httpx.Response(status_code, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    return NsxClient, target


def test_auth_failure_is_teaching(monkeypatch):
    from vmware_nsx.connection import NsxApiError

    NsxClient, target = _client_with_response(monkeypatch, status_code=403)
    with pytest.raises(NsxApiError) as ei:
        NsxClient(target, "S3cr3t!pw)")
    msg = str(ei.value)
    assert ".vmware-nsx/.env" in msg
    assert "VMWARE_NSX_<TARGET_NAME_UPPER>_PASSWORD" in msg
    assert "config.yaml" in msg  # names where the username lives
    assert "form-body" in msg  # special-char passwords handled (#10/#21)


def test_tls_failure_is_teaching(monkeypatch):
    import ssl

    from vmware_nsx.connection import NsxApiError

    tls_exc = httpx.ConnectError("certificate verify failed")
    tls_exc.__cause__ = ssl.SSLCertVerificationError("self signed certificate")
    NsxClient, target = _client_with_response(monkeypatch, raise_exc=tls_exc)
    with pytest.raises(NsxApiError) as ei:
        NsxClient(target, "pw")
    msg = str(ei.value)
    assert "verify_ssl" in msg
    assert "self-signed" in msg.lower()
