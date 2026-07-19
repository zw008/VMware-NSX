"""Every list tool must state its truncation instead of leaving it inferable.

Source: VMware-AIops issue #31 (juanpf-ha). Running the family against a local
Llama 3.3 70B, the operator reported that "with long tool responses, it may
omit existing information or incorrectly state that no data was returned."

A bare ``list[dict]`` gives a model no way to tell a complete answer from a
page-one answer, so it guesses — and the guess that reads "no data returned"
looks like a finding. Every read tool listed in SKILL.md now returns the
family envelope (``vmware_policy.paginated``), so ``returned``/``limit``/
``total``/``truncated`` are stated rather than inferred.

These tests pin, per tool:

* the six envelope keys are always present (a missing key invites invention);
* a page filled to the limit is flagged ``truncated`` when no total is known,
  because a full page cannot be told from a capped one;
* a short page is not flagged, and carries no hint;
* a full page matching the collection's real size is NOT flagged — the NSX
  Policy/Management APIs report ``result_count`` on every ListResult, and a
  known total removes the ambiguity a full page would otherwise create.

``result_count`` reaches the envelope through ``NsxClient.get_all``'s
``total_sink``, which reads the pages already fetched — no extra round trip,
and no count is invented when the API omits the field.
"""
from __future__ import annotations

from typing import Any

import pytest

ENVELOPE_KEYS = ("items", "returned", "limit", "total", "truncated", "hint")

# Every list tool declared in SKILL.md, with the ops call that backs it.
LIST_OPS: dict[str, tuple[str, str, tuple]] = {
    "list_segments": ("inventory", "list_segments", ()),
    "list_tier0_gateways": ("inventory", "list_tier0_gateways", ()),
    "list_tier1_gateways": ("inventory", "list_tier1_gateways", ()),
    "list_transport_zones": ("inventory", "list_transport_zones", ()),
    "list_transport_nodes": ("inventory", "list_transport_nodes", ()),
    "list_edge_clusters": ("inventory", "list_edge_clusters", ()),
    "list_nat_rules": ("networking", "list_nat_rules", ("t1",)),
    "list_static_routes": ("networking", "list_static_routes", ("gw",)),
    "list_ip_pools": ("networking", "list_ip_pools", ()),
    "list_nsx_alarms": ("health", "list_alarms", ()),
}


class _PagedClient:
    """Returns ``page`` rows and reports ``result_count`` as the true total.

    ``result_count`` is a real NSX ListResult field; ``None`` simulates the
    older APIs that omit it, where no total may be claimed.
    """

    def __init__(self, page: int, result_count: int | None) -> None:
        self.page = page
        self.result_count = result_count

    def get_all(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        max_items: int = 1000,
        *,
        page_size: int | None = None,
        limit: int | None = None,
        total_sink: Any = None,
    ) -> list[dict]:
        if total_sink is not None and self.result_count is not None:
            total_sink.value = self.result_count
        return [
            {
                "id": f"obj-{i}",
                "display_name": f"obj-{i}",
                "node_deployment_info": {"resource_type": "HostNode"},
            }
            for i in range(self.page)
        ]

    def get_count(self, path: str, params: dict[str, Any] | None = None) -> int | None:
        return self.result_count

    def get(self, path: str, params: dict[str, Any] | None = None, **_kw: Any) -> dict:
        return {}


def _call(tool: str, client: Any, **kwargs: Any) -> dict:
    import importlib

    module_name, func_name, args = LIST_OPS[tool]
    module = importlib.import_module(f"vmware_nsx.ops.{module_name}")
    return getattr(module, func_name)(client, *args, **kwargs)


# ---------------------------------------------------------------------------
# Shape: every list tool returns the envelope
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool", sorted(LIST_OPS))
def test_result_is_an_envelope_not_a_bare_list(tool: str) -> None:
    result = _call(tool, _PagedClient(page=3, result_count=3))
    assert isinstance(result, dict), f"{tool} still returns a bare list"
    assert isinstance(result["items"], list)


@pytest.mark.parametrize("tool", sorted(LIST_OPS))
def test_all_six_envelope_keys_are_always_present(tool: str) -> None:
    """Explicit nulls, never missing keys — a missing key invites invention."""
    result = _call(tool, _PagedClient(page=3, result_count=3))
    for key in ENVELOPE_KEYS:
        assert key in result, f"{tool} envelope is missing '{key}'"


@pytest.mark.parametrize("tool", sorted(LIST_OPS))
def test_returned_matches_the_row_count(tool: str) -> None:
    result = _call(tool, _PagedClient(page=3, result_count=3))
    assert result["returned"] == len(result["items"]) == 3


@pytest.mark.parametrize("tool", sorted(LIST_OPS))
def test_empty_result_is_complete_not_truncated(tool: str) -> None:
    """"Nothing configured" must read as an answer, not as a suppressed page."""
    result = _call(tool, _PagedClient(page=0, result_count=0))
    assert result["items"] == []
    assert result["returned"] == 0
    assert result["truncated"] is False
    assert result["hint"] is None


# ---------------------------------------------------------------------------
# Truncation, with and without a known total
# ---------------------------------------------------------------------------


# list_nsx_alarms takes no limit — it is covered separately below.
BOUNDED_TOOLS = sorted(set(LIST_OPS) - {"list_nsx_alarms"})


@pytest.mark.parametrize("tool", BOUNDED_TOOLS)
def test_short_page_is_complete_and_carries_no_hint(tool: str) -> None:
    result = _call(tool, _PagedClient(page=4, result_count=4), limit=50)
    assert result["returned"] == 4
    assert result["truncated"] is False
    assert result["hint"] is None


@pytest.mark.parametrize("tool", BOUNDED_TOOLS)
def test_full_page_with_no_reported_count_is_flagged_truncated(tool: str) -> None:
    """Conservative: with no result_count, a full page may hide more rows."""
    result = _call(tool, _PagedClient(page=50, result_count=None), limit=50)
    assert result["returned"] == 50
    assert result["total"] is None, "no count on the wire — do not invent one"
    assert result["truncated"] is True
    assert "limit" in result["hint"].lower()


@pytest.mark.parametrize("tool", BOUNDED_TOOLS)
def test_full_page_matching_the_real_total_is_not_truncated(tool: str) -> None:
    """result_count removes the ambiguity a full page would otherwise create."""
    result = _call(tool, _PagedClient(page=50, result_count=50), limit=50)
    assert result["returned"] == 50
    assert result["total"] == 50, "result_count is a real NSX ListResult field"
    assert result["truncated"] is False, (
        "a full page that matches the collection's result_count is complete — "
        "flagging it sends the agent back for a redundant query"
    )
    assert result["hint"] is None


@pytest.mark.parametrize("tool", BOUNDED_TOOLS)
def test_full_page_short_of_the_real_total_states_exact_numbers(tool: str) -> None:
    result = _call(tool, _PagedClient(page=50, result_count=412), limit=50)
    assert result["total"] == 412
    assert result["truncated"] is True
    assert "50" in result["hint"] and "412" in result["hint"]


def test_alarms_take_no_limit_and_report_the_full_severity_set() -> None:
    """Every alarm at the severity is fetched, so the result is complete."""
    result = _call("list_nsx_alarms", _PagedClient(page=7, result_count=7))
    assert result["returned"] == 7
    assert result["limit"] is None
    assert result["total"] == 7
    assert result["truncated"] is False
    assert result["hint"] is None


def test_alarms_cut_short_by_the_safety_backstop_are_flagged_truncated() -> None:
    """The backstop is the one case where alarms are not the whole picture."""
    result = _call("list_nsx_alarms", _PagedClient(page=1000, result_count=2500))
    assert result["returned"] == 1000
    assert result["total"] == 2500
    assert result["truncated"] is True


# ---------------------------------------------------------------------------
# The total reaches the envelope without a second round trip
# ---------------------------------------------------------------------------


def test_result_count_is_read_from_pages_already_fetched() -> None:
    """get_all fills the sink itself; get_count would cost an extra request."""
    from vmware_nsx.connection import CollectionTotal, NsxClient

    client = NsxClient.__new__(NsxClient)
    calls: list[dict] = []

    def get_stub(path: str, params: dict | None = None) -> dict:
        calls.append(dict(params or {}))
        return {
            "results": [{"id": f"x{i}"} for i in range(50)],
            "result_count": 137,
            "cursor": "next",
        }

    client.get = get_stub  # type: ignore[assignment]
    sink = CollectionTotal()
    out = client.get_all("/p", page_size=50, limit=50, total_sink=sink)

    assert len(out) == 50
    assert sink.value == 137
    assert len(calls) == 1, "the count came from the page already fetched"


def test_sink_stays_none_when_the_api_omits_result_count() -> None:
    from vmware_nsx.connection import CollectionTotal, NsxClient

    client = NsxClient.__new__(NsxClient)
    client.get = lambda path, params=None: {"results": []}  # type: ignore[assignment]
    sink = CollectionTotal()
    client.get_all("/p", page_size=50, limit=50, total_sink=sink)

    assert sink.value is None, "an absent count must not be fabricated"


# ---------------------------------------------------------------------------
# MCP surface
# ---------------------------------------------------------------------------


def test_mcp_list_tools_declare_object_results_not_arrays() -> None:
    """The annotation drives the schema an agent is handed."""
    import inspect

    # Import the server first: the tool packages resolve back through it, so
    # importing them directly trips a partially-initialised module.
    import vmware_nsx.mcp_server.server  # noqa: F401
    from vmware_nsx.mcp_server.tools import health, inventory, networking

    checked = []
    for module in (health, inventory, networking):
        for name in LIST_OPS:
            fn = getattr(module, name, None)
            if fn is None:
                continue
            # Unwrap the @mcp.tool / @vmware_tool decorators.
            annotation = inspect.signature(inspect.unwrap(fn)).return_annotation
            assert annotation is dict, (
                f"{module.__name__}.{name} must return the envelope dict, "
                f"got {annotation!r}"
            )
            checked.append(name)

    assert sorted(checked) == sorted(LIST_OPS), (
        "every list tool must be reachable on its module — a renamed or moved "
        "tool would otherwise pass this test vacuously"
    )
