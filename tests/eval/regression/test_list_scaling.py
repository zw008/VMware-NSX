"""Regression evals for REST list-scaling anti-patterns (2026-07 NSX pass).

Audit found list/detail ops that drained the collection (up to the 1000-item
``get_all`` safety cap) and N+1 per-port round trips. These evals pin the fix:

* ``get_all`` accepts ``page_size`` (server-side per-page) and ``limit`` (stop
  following cursors once ``limit`` items collected).
* Top-level list ops pass a bounded limit (default 50) to ``get_all``.
* ``get_logical_port_status`` fetches at most ~50 ports and makes at most one
  per-port state call each — no full-collection drain.
* ``get_segment`` / ``get_ip_pool_usage`` fetch a bounded page but still
  report the true total from pagination metadata.
* ``delete_segment`` probes emptiness with a single-item page.
* The ``_scan_segment_ports`` fallback is bounded, not an estate-wide scan.
"""
from __future__ import annotations

from typing import Any

import pytest

from vmware_nsx.ops import inventory, networking, segment_mgmt, troubleshoot


class FakeNsxClient:
    """Records the page_size/limit bounds each list call requests.

    ``get_all`` honours the requested ``limit`` against a large simulated
    backing store, so a caller that forgets to bound its query would visibly
    pull far more than the sample size.
    """

    def __init__(self, backing_count: int = 500) -> None:
        self.backing_count = backing_count
        # Each entry: {"path", "page_size", "limit", "returned"}.
        self.get_all_calls: list[dict[str, Any]] = []
        self.get_count_calls: list[str] = []
        self.get_paths: list[str] = []
        self.delete_paths: list[str] = []

    def _rows(self, n: int) -> list[dict]:
        return [{"id": f"item-{i}", "display_name": f"name-{i}"} for i in range(n)]

    def get_all(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        max_items: int = 1000,
        *,
        page_size: int | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        effective = min(
            self.backing_count,
            limit if limit is not None else max_items,
        )
        self.get_all_calls.append(
            {
                "path": path,
                "page_size": page_size,
                "limit": limit,
                "returned": effective,
            }
        )
        return self._rows(effective)

    def get_count(
        self, path: str, params: dict[str, Any] | None = None
    ) -> int | None:
        self.get_count_calls.append(path)
        return self.backing_count

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        retries: int = 1,
    ) -> dict:
        self.get_paths.append(path)
        return {}

    def delete(self, path: str) -> None:
        self.delete_paths.append(path)


# ── connection.get_all contract ─────────────────────────────────────────


def test_get_all_limit_stops_following_cursor() -> None:
    """A real get_all threads page_size and stops at ``limit`` even when the
    server keeps returning a cursor (would otherwise drain to the backstop)."""
    from vmware_nsx.connection import NsxClient

    client = NsxClient.__new__(NsxClient)
    calls: list[dict] = []

    def get_stub(path: str, params: dict | None = None) -> dict:
        calls.append(dict(params or {}))
        # Always hand back a full page plus a cursor — an unbounded caller
        # would keep paging forever (up to max_items).
        return {"results": [{"id": f"x{i}"} for i in range(50)], "cursor": "next"}

    client.get = get_stub  # type: ignore[assignment]
    out = client.get_all("/p", page_size=50, limit=50)
    assert len(out) == 50  # stopped at limit, did not keep following cursor
    assert len(calls) == 1  # one page fetched, not many
    assert calls[0].get("page_size") == 50


# ── list ops pass server-side bounds ────────────────────────────────────


def test_inventory_list_ops_pass_default_limit() -> None:
    client = FakeNsxClient()
    inventory.list_segments(client)
    inventory.list_tier0_gateways(client)
    inventory.list_tier1_gateways(client)
    inventory.list_transport_zones(client)
    inventory.list_transport_nodes(client)
    inventory.list_edge_clusters(client)

    assert len(client.get_all_calls) == 6
    for call in client.get_all_calls:
        assert call["limit"] == 50, call["path"]
        assert call["page_size"] == 50, call["path"]
        assert call["returned"] == 50


def test_networking_list_ops_pass_default_limit() -> None:
    client = FakeNsxClient()
    networking.list_nat_rules(client, "t1")
    networking.list_static_routes(client, "gw", "tier0")
    networking.list_ip_pools(client)

    for call in client.get_all_calls:
        assert call["limit"] == 50
        assert call["page_size"] == 50


def test_list_ops_respect_explicit_limit() -> None:
    client = FakeNsxClient()
    inventory.list_segments(client, limit=5)
    assert client.get_all_calls[0]["limit"] == 5
    assert client.get_all_calls[0]["returned"] == 5


# ── get_logical_port_status: no N+1 drain ───────────────────────────────


def test_get_logical_port_status_bounds_port_fetch() -> None:
    client = FakeNsxClient(backing_count=500)
    result = troubleshoot.get_logical_port_status(client, "seg-1")

    # Exactly one bounded port list, capped at 50.
    port_list_calls = [c for c in client.get_all_calls if c["path"].endswith("/ports")]
    assert len(port_list_calls) == 1
    assert port_list_calls[0]["limit"] == 50
    assert port_list_calls[0]["returned"] == 50

    # Per-port state calls bounded to the fetched sample (<= 50).
    state_gets = [p for p in client.get_paths if p.endswith("/state")]
    assert len(state_gets) <= 50

    # True total preserved, sample size reported alongside.
    assert result["port_count"] == 500
    assert result["ports_shown"] == 50
    assert len(result["ports"]) == 50


# ── get_segment: bounded fetch, honest total ────────────────────────────


def test_get_segment_bounds_ports_but_reports_true_total() -> None:
    client = FakeNsxClient(backing_count=500)
    result = inventory.get_segment(client, "seg-1")

    port_calls = [c for c in client.get_all_calls if c["path"].endswith("/ports")]
    assert port_calls[0]["limit"] == 50
    assert len(result["ports"]) == 50
    assert result["port_count"] == 500  # from get_count metadata
    assert client.get_count_calls  # count was queried, not derived from drain


# ── get_ip_pool_usage: bounded fetch, honest total ──────────────────────


def test_get_ip_pool_usage_bounds_allocations() -> None:
    client = FakeNsxClient(backing_count=300)
    result = networking.get_ip_pool_usage(client, "pool-1")

    alloc_call = client.get_all_calls[0]
    assert alloc_call["limit"] == 50
    assert len(result["allocations"]) == 50
    assert result["allocation_count"] == 300


# ── delete_segment: single-item emptiness probe ─────────────────────────


def test_delete_segment_probes_with_single_item_page() -> None:
    empty = FakeNsxClient(backing_count=0)
    out = segment_mgmt.delete_segment(empty, "seg-empty")
    probe = empty.get_all_calls[0]
    assert probe["limit"] == 1
    assert probe["page_size"] == 1
    assert out["deleted"] is True


def test_delete_segment_blocks_when_ports_present() -> None:
    busy = FakeNsxClient(backing_count=500)
    out = segment_mgmt.delete_segment(busy, "seg-busy")
    # Probe never drains the collection.
    assert busy.get_all_calls[0]["limit"] == 1
    assert out["deleted"] is False
    assert out["error"].startswith("Segment has 500 active port(s)")
    assert len(out["port_ids"]) <= 10


# ── _scan_segment_ports fallback is bounded ─────────────────────────────


def test_scan_segment_ports_bounds_segment_fanout() -> None:
    client = FakeNsxClient(backing_count=10_000)
    troubleshoot._scan_segment_ports(client, ["attach-1"])
    seg_call = next(
        c for c in client.get_all_calls if c["path"].endswith("/segments")
    )
    assert seg_call["limit"] == troubleshoot._MAX_SCAN_SEGMENTS
    assert seg_call["returned"] == troubleshoot._MAX_SCAN_SEGMENTS


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
