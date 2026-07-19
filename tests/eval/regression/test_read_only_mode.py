"""Read-only mode must remove write tools from the real FastMCP registry.

Regression source: VMware-AIops issue #31 (juanpf-ha). An operator driving the
family with a local Llama 3.3 70B had to hand-write the prompt instruction
"work exclusively in read-only mode and never modify segments, gateways, NAT
rules or routes", because read-only was only ever a documented intent. A weak
model can ignore a prompt; it cannot call a tool that is not in list_tools().

vmware_policy/tests/test_readonly.py pins the gate's *semantics* against a
stand-in registry. This file pins the other half: that the real FastMCP API the
gate reaches for still behaves as assumed, and that this skill's actual tool
inventory splits the way its docs claim.
"""

import asyncio
import importlib
import sys

import pytest

WRITE_TOOLS = {
    "configure_tier0_bgp",
    "create_ip_pool",
    "create_nat_rule",
    "create_segment",
    "create_static_route",
    "create_tier1_gateway",
    "delete_ip_pool",
    "delete_nat_rule",
    "delete_segment",
    "delete_static_route",
    "delete_tier1_gateway",
    "update_segment",
    "update_tier1_gateway",
}


def _load_server(monkeypatch, read_only: str | None):
    """Import vmware_nsx.mcp_server.server fresh under the given read-only env."""
    monkeypatch.delenv("VMWARE_READ_ONLY", raising=False)
    monkeypatch.delenv("VMWARE_NSX_READ_ONLY", raising=False)
    if read_only is not None:
        monkeypatch.setenv("VMWARE_READ_ONLY", read_only)

    for name in [m for m in sys.modules if m.startswith("vmware_nsx.mcp_server")]:
        del sys.modules[name]
    return importlib.import_module("vmware_nsx.mcp_server.server")


def _tool_names(server) -> set[str]:
    return {t.name for t in asyncio.run(server.mcp.list_tools())}


@pytest.fixture(autouse=True)
def _restore_modules():
    """Leave sys.modules as we found it so other test files import normally."""
    yield
    for name in [m for m in sys.modules if m.startswith("vmware_nsx.mcp_server")]:
        del sys.modules[name]


def test_default_mode_exposes_write_tools(monkeypatch):
    """Baseline: without the switch every tool is present."""
    server = _load_server(monkeypatch, None)
    names = _tool_names(server)
    assert WRITE_TOOLS <= names
    assert server.WITHHELD_WRITE_TOOLS == []


def test_read_only_removes_every_write_tool(monkeypatch):
    server = _load_server(monkeypatch, "true")
    names = _tool_names(server)
    assert not (WRITE_TOOLS & names), f"write tools survived: {WRITE_TOOLS & names}"


def test_read_only_keeps_read_tools(monkeypatch):
    """The gate must not be a blunt instrument — reads still work."""
    server = _load_server(monkeypatch, "true")
    names = _tool_names(server)
    for tool in ("list_segments", "get_segment", "list_nat_rules", "list_nsx_alarms"):
        assert tool in names


def test_withheld_list_is_reported(monkeypatch):
    """Startup must be able to tell the operator what was withheld."""
    server = _load_server(monkeypatch, "true")
    assert set(server.WITHHELD_WRITE_TOOLS) == WRITE_TOOLS


def test_every_surviving_tool_is_marked_read(monkeypatch):
    """End-to-end contract against the live registry."""
    server = _load_server(monkeypatch, "true")
    for tool in asyncio.run(server.mcp.list_tools()):
        assert (tool.description or "").lstrip().startswith("[READ]"), tool.name


def test_skill_env_var_also_works(monkeypatch):
    monkeypatch.delenv("VMWARE_READ_ONLY", raising=False)
    monkeypatch.setenv("VMWARE_NSX_READ_ONLY", "true")
    for name in [m for m in sys.modules if m.startswith("vmware_nsx.mcp_server")]:
        del sys.modules[name]
    server = importlib.import_module("vmware_nsx.mcp_server.server")
    assert not (WRITE_TOOLS & _tool_names(server))


def test_fastmcp_registry_api_still_present(monkeypatch):
    """The gate reaches into _tool_manager.list_tools(); pin that it exists.

    If an mcp upgrade moves this, we want a red test here rather than a gate
    that silently stops removing anything.
    """
    server = _load_server(monkeypatch, None)
    assert callable(getattr(server.mcp, "remove_tool", None))
    assert callable(getattr(server.mcp._tool_manager, "list_tools", None))
    assert server.mcp._tool_manager.list_tools()
