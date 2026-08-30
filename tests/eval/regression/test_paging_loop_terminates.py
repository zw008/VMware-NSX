"""Every list tool can be asked for a page, and a paging loop over it ends.

Real-hardware finding, 2026-08-30. All ten list tools on this skill's MCP
surface took exactly one argument — ``target``. The ops layer underneath them
already had a ``limit`` and defaulted it to 50, so an agent got the first fifty
rows of every collection and had no way to ask for the fifty-first: no limit,
no offset, no cursor, nothing in the response pointing onwards. On an estate
with more than fifty segments the rest were unreachable through the tool.

Adding ``limit`` alone would not have been enough. A page size with no way to
move the window is a smaller ceiling, not paging, and the family's envelope
cannot express where the next page starts: its six keys all describe the page
in hand. So the ops take an ``offset`` and the envelope carries a
``next_offset`` extra — the value to pass back, or ``None`` when this page ends
the collection.

``truncated`` is deliberately not that signal. It answers "is ``items`` the
whole collection?", so on the last page of a paged walk it is still true, and a
loop driven by it never stops (that is the defect these tests were written
against in VMware-NSX-Security on the same day).

Collection sizes here are not multiples of the page size. The partial last page
is where the arithmetic goes wrong.
"""

from __future__ import annotations

import asyncio
import importlib

import pytest
from unittest.mock import MagicMock

from vmware_nsx.ops._paginate import MAX_LIMIT, paginate

#: (module, function, positional args before limit/offset). Every list op in
#: the skill — derived from nothing, so a new one has to be added here by hand;
#: the surface test below is what catches an op that never arrives.
LIST_OPS = [
    ("vmware_nsx.ops.inventory", "list_segments", ()),
    ("vmware_nsx.ops.inventory", "list_tier0_gateways", ()),
    ("vmware_nsx.ops.inventory", "list_tier1_gateways", ()),
    ("vmware_nsx.ops.inventory", "list_transport_zones", ()),
    ("vmware_nsx.ops.inventory", "list_transport_nodes", ()),
    ("vmware_nsx.ops.inventory", "list_edge_clusters", ()),
    ("vmware_nsx.ops.health", "list_alarms", ()),
    ("vmware_nsx.ops.networking", "list_nat_rules", ("tier1-01",)),
    ("vmware_nsx.ops.networking", "list_static_routes", ("tier1-01",)),
    ("vmware_nsx.ops.networking", "list_ip_pools", ()),
]

IDS = [f"{m.rsplit('.', 1)[-1]}.{f}" for m, f, _ in LIST_OPS]

#: The MCP tools that wrap them. Same order, same collections.
LIST_TOOLS = [
    "list_segments",
    "list_tier0_gateways",
    "list_tier1_gateways",
    "list_transport_zones",
    "list_transport_nodes",
    "list_edge_clusters",
    "list_nsx_alarms",
    "list_nat_rules",
    "list_static_routes",
    "list_ip_pools",
]


def _op(import_path: str, fn_name: str):
    return getattr(importlib.import_module(import_path), fn_name)


def _rows(n: int) -> list[dict]:
    """Rows carrying every id field the ten ops read, so one shape serves all."""
    return [
        {
            "id": f"item-{i}",
            "display_name": f"item-{i}",
            "severity": "MEDIUM",
            "node_id": f"item-{i}",
        }
        for i in range(n)
    ]


def _client(rows: list[dict], *, report_total: bool = True) -> MagicMock:
    """A client whose ``get_all`` honours ``limit`` and fills ``total_sink``.

    Both matter. An op that forgets to widen its fetch to ``offset + limit``
    looks correct against a mock that returns everything regardless, because
    the slice afterwards tidies up behind it; and ``total`` is what makes
    ``next_offset`` exact rather than conservative.
    """

    def get_all(path, params=None, max_items=None, *, page_size=None, limit=None, total_sink=None):
        if total_sink is not None and report_total:
            total_sink.value = len(rows)
        return list(rows) if limit is None else list(rows)[:limit]

    client = MagicMock()
    client.get.return_value = {}
    client.get_all.side_effect = get_all
    client.get_count.return_value = len(rows)
    return client


def _walk(fn, args, client, page_size: int, label: str, max_calls: int = 20):
    """Follow the op's own ``next_offset`` until it stops. Returns ids + calls."""
    seen: list[str] = []
    offset = 0
    calls = 0
    while True:
        calls += 1
        assert calls <= max_calls, (
            f"{label} paging did not terminate within {max_calls} calls "
            f"(page_size={page_size}, last offset={offset})"
        )
        page = fn(client, *args, limit=page_size, offset=offset)
        assert "next_offset" in page, (
            f"{label} returned no next_offset — an agent has nothing to page by"
        )
        seen.extend(row["id"] for row in page["items"])
        nxt = page["next_offset"]
        if nxt is None:
            return seen, calls
        assert isinstance(nxt, int) and nxt > offset, (
            f"{label} next_offset {nxt!r} does not advance past {offset}"
        )
        offset = nxt


# ---------------------------------------------------------------------------
# The load-bearing test: the loop stops, and sees every row exactly once
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("import_path", "fn_name", "args"), LIST_OPS, ids=IDS)
def test_paging_loop_terminates_and_sees_every_row_once(import_path, fn_name, args) -> None:
    fn = _op(import_path, fn_name)
    rows = _rows(10)  # 10 is not a multiple of 3 — the last page is partial
    label = f"{fn_name}"
    seen, calls = _walk(fn, args, _client(rows), page_size=3, label=label)

    assert seen == [r["id"] for r in rows], (
        f"{label} paging lost, duplicated or reordered rows: {seen}"
    )
    assert calls == 4, f"{label} took {calls} calls to read 10 rows in pages of 3"


@pytest.mark.parametrize(("import_path", "fn_name", "args"), LIST_OPS, ids=IDS)
def test_paging_terminates_without_a_server_total(import_path, fn_name, args) -> None:
    """A manager that omits ``result_count`` must still give a walk that ends.

    Ten rows in pages of three ends on a short page, and a short page is
    self-evidently the last one whether or not a total was reported — so this
    costs nothing. The case that does cost is below.
    """
    fn = _op(import_path, fn_name)
    rows = _rows(10)
    seen, calls = _walk(
        fn, args, _client(rows, report_total=False), page_size=3, label=fn_name
    )
    assert seen == [r["id"] for r in rows]
    assert calls == 4, f"{fn_name} took {calls} calls (expected 4)"


@pytest.mark.parametrize(("import_path", "fn_name", "args"), LIST_OPS, ids=IDS)
def test_a_full_last_page_ends_the_walk(import_path, fn_name, args) -> None:
    """Nine rows in pages of three: the last page is full, and must still end.

    This is where a known total earns its keep. With one, the walk stops after
    three calls because the arithmetic proves nothing remains. Without one, a
    full page cannot be told apart from a truncated one, so a fourth call goes
    out and comes back empty — the honest cost of not knowing, paid once, and
    it has to be the last call rather than the start of a cycle.
    """
    fn = _op(import_path, fn_name)
    rows = _rows(9)

    seen, calls = _walk(fn, args, _client(rows), page_size=3, label=fn_name)
    assert seen == [r["id"] for r in rows]
    assert calls == 3, f"{fn_name} took {calls} calls with a known total"

    seen, calls = _walk(
        fn, args, _client(rows, report_total=False), page_size=3, label=fn_name
    )
    assert seen == [r["id"] for r in rows]
    assert calls == 4, f"{fn_name} took {calls} calls (expected 3 pages + 1 empty)"


@pytest.mark.parametrize(("import_path", "fn_name", "args"), LIST_OPS, ids=IDS)
def test_the_fetch_widens_to_cover_the_offset(import_path, fn_name, args) -> None:
    """Page two must not be page one sliced away to nothing.

    The ops bound their fetch server-side. If that bound stays at ``limit``
    while the slice starts at ``offset``, every page after the first is empty
    — and empty reads as "the collection ended here" (形态 #1).
    """
    fn = _op(import_path, fn_name)
    page = fn(_client(_rows(10)), *args, limit=3, offset=6)
    assert [r["id"] for r in page["items"]] == ["item-6", "item-7", "item-8"]


# ---------------------------------------------------------------------------
# Controls — a tool that always says "stop" would pass everything above
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("import_path", "fn_name", "args"), LIST_OPS, ids=IDS)
def test_a_short_collection_needs_no_second_call(import_path, fn_name, args) -> None:
    fn = _op(import_path, fn_name)
    page = fn(_client(_rows(2)), *args, limit=50, offset=0)
    assert page["returned"] == 2
    assert page["truncated"] is False
    assert page["next_offset"] is None


@pytest.mark.parametrize(("import_path", "fn_name", "args"), LIST_OPS, ids=IDS)
def test_a_partial_first_page_still_reports_truncated(import_path, fn_name, args) -> None:
    """The control against "always report truncated: false and stop".

    That passes every termination test above while telling an agent three rows
    are all ten.
    """
    fn = _op(import_path, fn_name)
    page = fn(_client(_rows(10)), *args, limit=3, offset=0)
    assert page["truncated"] is True
    assert page["total"] == 10
    assert page["next_offset"] == 3


@pytest.mark.parametrize(("import_path", "fn_name", "args"), LIST_OPS, ids=IDS)
def test_truncated_stays_true_on_the_last_page(import_path, fn_name, args) -> None:
    """Pinning the decision: the stop signal is next_offset, not truncated."""
    fn = _op(import_path, fn_name)
    page = fn(_client(_rows(10)), *args, limit=3, offset=9)
    assert page["returned"] == 1
    assert page["truncated"] is True
    assert page["next_offset"] is None


# ---------------------------------------------------------------------------
# limit=0 and negative limit — rejected, never silently reinterpreted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("import_path", "fn_name", "args"), LIST_OPS, ids=IDS)
@pytest.mark.parametrize("bad_limit", [0, -1, -50, MAX_LIMIT + 1])
def test_out_of_range_limit_is_rejected(import_path, fn_name, args, bad_limit) -> None:
    fn = _op(import_path, fn_name)
    with pytest.raises(ValueError, match="limit"):
        fn(_client(_rows(10)), *args, limit=bad_limit, offset=0)


@pytest.mark.parametrize(("import_path", "fn_name", "args"), LIST_OPS, ids=IDS)
def test_negative_offset_is_rejected(import_path, fn_name, args) -> None:
    fn = _op(import_path, fn_name)
    with pytest.raises(ValueError, match="offset"):
        fn(_client(_rows(10)), *args, limit=3, offset=-5)


def test_paginate_itself_never_reaches_python_negative_slicing() -> None:
    """The helper's own guard, tested where it can still fail.

    Validation rejects a negative limit before ``paginate`` sees one, so no
    test that goes through an op can tell whether this guard survives. It is
    the last thing between ``items[0:-1]`` and a page quietly missing its final
    row, which is the shape the family-wide audit found at 26 call sites.
    """
    rows = _rows(10)
    for bad_limit in (-1, -3, -9):
        window = paginate(rows, bad_limit, 0)
        assert window != rows[0:bad_limit], (
            f"limit={bad_limit} fell through to Python negative slicing"
        )
        assert window == [], f"limit={bad_limit} produced a page: {window}"
    assert paginate(rows, 0, 0) == []


def test_the_rejection_says_what_to_pass_instead() -> None:
    """Teaching error, not just a refusal (family error-message rule)."""
    fn = _op("vmware_nsx.ops.inventory", "list_segments")
    with pytest.raises(ValueError) as exc:
        fn(_client(_rows(10)), limit=0)
    message = str(exc.value)
    assert "1" in message and str(MAX_LIMIT) in message
    assert "offset" in message, "tell the caller how to reach the rest"


# ---------------------------------------------------------------------------
# The MCP surface — the schema is the only contract an agent sees
# ---------------------------------------------------------------------------


def _tools() -> dict:
    """The live FastMCP registry — the same view an MCP client gets."""
    from vmware_nsx.mcp_server.server import mcp

    return {t.name: t for t in asyncio.run(mcp.list_tools())}


@pytest.mark.parametrize("tool_name", LIST_TOOLS)
def test_every_list_tool_exposes_limit_and_offset(tool_name) -> None:
    """An ops-layer limit an agent cannot pass is not a paging story.

    This is what the estate hit: `limit=50` was hardcoded one call below a
    tool whose entire signature was `target`.
    """
    props = _tools()[tool_name].inputSchema.get("properties", {})
    assert "limit" in props, f"{tool_name} cannot be asked for a page size"
    assert "offset" in props, f"{tool_name} cannot be asked for the next page"


@pytest.mark.parametrize(
    ("tool_name", "import_path", "fn_name"),
    [(t, m, f) for t, (m, f, _) in zip(LIST_TOOLS, LIST_OPS)],
    ids=LIST_TOOLS,
)
def test_the_tool_default_page_size_matches_the_op(tool_name, import_path, fn_name) -> None:
    """A wrapper default that disagrees with the op re-caps it in silence.

    Caught in the writing of this change: the ops keep ``list_alarms`` at the
    full 1000 on purpose, because a health sweep showing the first fifty alarms
    and calling it a picture is the failure the envelope exists to prevent —
    and the tool wrapper had been given a flat 50 along with the other nine. It
    would have shipped as "alarms now default to 50", stated nowhere, from a
    change whose whole subject is paging honesty.
    """
    import inspect

    op_default = inspect.signature(_op(import_path, fn_name)).parameters["limit"].default
    tool_default = _tools()[tool_name].inputSchema["properties"]["limit"].get("default")
    assert tool_default == op_default, (
        f"{tool_name} advertises limit={tool_default} while {fn_name} defaults "
        f"to {op_default} — the tool silently re-caps its own op"
    )


@pytest.mark.parametrize("tool_name", LIST_TOOLS)
def test_every_list_tool_documents_how_to_stop(tool_name) -> None:
    """The docstring is the only place an agent learns the loop's exit."""
    description = _tools()[tool_name].description or ""
    assert "next_offset" in description, (
        f"{tool_name} never names the key a paging loop stops on"
    )


@pytest.mark.parametrize("tool_name", LIST_TOOLS)
def test_every_list_tool_actually_forwards_the_offset(tool_name) -> None:
    """Advertising ``offset`` and dropping it is worse than not having it.

    The schema test above passes on a wrapper that accepts ``offset`` and never
    passes it down: the tool then returns page one for every offset an agent
    tries, and an agent that trusts the schema walks in a circle collecting
    duplicates. Mutation-testing found exactly that hole — removing
    ``offset=offset`` from one wrapper's call left the whole suite green.

    So this drives the tool itself, not the op, and checks the rows that came
    back are the window that was asked for.
    """
    from unittest.mock import patch

    import vmware_nsx.mcp_server.server as srv

    required = {
        "list_nat_rules": {"tier1_id": "tier1-01"},
        "list_static_routes": {"tier1_id": "tier1-01"},
    }.get(tool_name, {})

    with patch.object(srv, "_get_connection", return_value=_client(_rows(10))):
        result = getattr(srv, tool_name)(limit=3, offset=6, **required)

    assert "error" not in result, result
    assert [row["id"] for row in result["items"]] == ["item-6", "item-7", "item-8"], (
        f"{tool_name} did not forward limit/offset to its ops function"
    )
    # 6 skipped + 3 returned = 9, and row ten is still behind it.
    assert result["next_offset"] == 9


# ---------------------------------------------------------------------------
# The CLI has the same reader, and had the same problem
# ---------------------------------------------------------------------------


def test_the_cli_says_where_the_next_page_starts(capsys) -> None:
    """A table headed "Segments (50)" reads as "there are 50 segments".

    The CLI took ``["items"]`` and dropped the rest of the envelope, so a
    human saw a bounded page with nothing marking it as one — the same defect
    as the MCP surface, on the surface nobody was looking at.
    """
    from vmware_nsx.cli._base import print_next_page

    print_next_page({"next_offset": 50, "total": 213})
    out = capsys.readouterr().out
    assert "--offset 50" in out, "the follow-on command has to be printable"
    assert "213" in out


def test_the_cli_stays_quiet_on_the_last_page(capsys) -> None:
    """The control: a message on every page is a message on none of them."""
    from vmware_nsx.cli._base import print_next_page

    print_next_page({"next_offset": None, "total": 213})
    assert capsys.readouterr().out == ""
