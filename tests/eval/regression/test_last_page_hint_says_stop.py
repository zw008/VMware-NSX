"""The hint on the last page must not prescribe a remedy that cannot work.

Real-hardware finding, 2026-08-30, second round. The previous round added
``next_offset`` and left a note in its own commit message: ``paginated`` takes
no ``offset``, so on the last page of a walk its ``hint`` still read "Raise
limit or narrow the query with a filter to see the rest". It also fires on a
page past the end, where ``returned`` is 0.

Two things were wrong with that page and only one of them is ``truncated``.

``truncated`` answers "is ``items`` the whole collection?" and on page four of
four the honest answer is still no — that page holds three rows out of twelve.
Flipping it to false there would buy a loop that stops at the price of the
failure the envelope exists to prevent (VMware-AIops issue #31: a partial page
read back as the complete answer). ``next_offset`` is the stop signal and
already says ``None``. So the semantics stay exactly as they are, and these
tests pin them so nobody "fixes" this the other way.

The **hint** is what was wrong. It is the one field written for a reader rather
than a machine, and it was telling that reader to raise a limit that cannot
produce another row and to narrow a query that is already exhausted. That is
advice, and it was false.

The previous round recorded this as needing a ``vmware_policy`` release. It
does not: ``paginated`` builds the envelope, and the ops layer — which is the
only layer that knows the ``offset`` — can state the sentence afterwards. That
is what ``page_envelope`` does, and it is one helper rather than ten copies so
the eleventh list op cannot get a different answer.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from vmware_nsx.ops._paginate import page_envelope

_REPO = pathlib.Path(__file__).resolve().parents[3]
OPS_DIR = _REPO / "vmware_nsx" / "ops"
assert OPS_DIR.is_dir(), f"ops package not found at {OPS_DIR} — the scan would find nothing"

#: Advice that is false once ``next_offset`` is ``None``. Substring match on the
#: lowercased hint.
DEAD_END_ADVICE = ("raise limit", "raise the limit", "narrow the query", "see the rest")


def _rows(n: int, start: int = 0) -> list[dict]:
    return [{"id": f"row-{i}"} for i in range(start, start + n)]


def _hint(env: dict) -> str:
    assert env["hint"] is not None, "a truncated page with no hint says nothing about why"
    return env["hint"].lower()


# ---------------------------------------------------------------------------
# The defect
# ---------------------------------------------------------------------------


def test_the_last_page_of_a_walk_does_not_advise_raising_the_limit():
    """Rows 9..11 of 12, read three at a time. There is no fourth page."""
    env = page_envelope(_rows(3, start=9), limit=3, offset=9, total=12)

    assert env["next_offset"] is None, "the walk has to be over for this hint to be tested at all"
    assert env["truncated"] is True, "truncated keeps its meaning: three rows is not twelve rows"

    hint = _hint(env)
    for advice in DEAD_END_ADVICE:
        assert advice not in hint, f"last-page hint still says {advice!r}: {env['hint']!r}"
    assert "no next page" in hint, f"last-page hint does not say the walk ended: {env['hint']!r}"


def test_a_page_past_the_end_says_so_rather_than_advising_a_bigger_limit():
    """Offset 12 of a 12-row collection. Nothing is there and nothing will be."""
    env = page_envelope([], limit=3, offset=12, total=12)

    assert env["next_offset"] is None
    assert env["truncated"] is True, "zero rows is not the whole collection either"

    hint = _hint(env)
    for advice in DEAD_END_ADVICE:
        assert advice not in hint, f"past-the-end hint still says {advice!r}: {env['hint']!r}"
    assert "past the end" in hint, f"past-the-end hint does not say why it is empty: {env['hint']!r}"
    assert "offset 0" in hint, f"past-the-end hint does not say where to start over: {env['hint']!r}"


def test_a_mid_walk_hint_names_the_offset_to_pass_back():
    """The remedy that does work is the one the hint should carry."""
    env = page_envelope(_rows(3), limit=3, offset=0, total=12)

    assert env["next_offset"] == 3
    assert env["truncated"] is True
    hint = _hint(env)
    assert "offset 3" in hint, f"mid-walk hint does not name the next offset: {env['hint']!r}"


def test_a_mid_walk_hint_without_a_total_still_names_the_next_offset():
    """An unknown total is why a full page is reported as having a successor."""
    env = page_envelope(_rows(3), limit=3, offset=0, total=None)

    assert env["next_offset"] == 3
    assert env["truncated"] is True
    hint = _hint(env)
    assert "offset 3" in hint
    assert "may be more" in hint, f"unknown-total hint states a certainty it does not have: {env['hint']!r}"


# ---------------------------------------------------------------------------
# Controls — what must NOT change
# ---------------------------------------------------------------------------


def test_a_collection_smaller_than_one_page_still_needs_no_second_call():
    env = page_envelope(_rows(2), limit=50, offset=0, total=2)
    assert env["next_offset"] is None
    assert env["truncated"] is False, "two rows out of two is the whole collection"
    assert env["hint"] is None, "a complete answer must not be given a hint to act on"


def test_a_partial_first_page_is_still_truncated_with_a_successor():
    """The control that fails if anyone makes ``truncated`` mean "no more pages"."""
    env = page_envelope(_rows(2), limit=3, offset=0, total=10)
    assert env["truncated"] is True
    assert env["next_offset"] == 2
    assert env["total"] == 10


def test_an_unknown_total_and_a_short_page_is_complete_and_silent():
    env = page_envelope(_rows(2), limit=3, offset=0, total=None)
    assert env["truncated"] is False
    assert env["next_offset"] is None
    assert env["hint"] is None


def test_the_envelope_keys_and_extras_are_unchanged():
    from vmware_policy import ENVELOPE_KEYS

    env = page_envelope(_rows(1), limit=3, offset=0, total=1, target="nsx-dc2")
    assert set(ENVELOPE_KEYS) <= set(env), "page_envelope dropped one of the six family keys"
    assert env["target"] == "nsx-dc2", "extras must still reach the envelope"
    assert env["items"] == _rows(1)


# ---------------------------------------------------------------------------
# Driven through a real tool, not just the helper
# ---------------------------------------------------------------------------


def test_a_real_list_tool_on_its_last_page_says_the_walk_ended():
    """The previous round shipped a wrapper that passed every op-level test and
    still dropped ``offset`` on the floor. Drive the tool."""
    from unittest.mock import MagicMock, patch

    from vmware_nsx.mcp_server import server as srv

    rows = [{"id": f"seg-{i}", "display_name": f"seg-{i}"} for i in range(12)]

    def get_all(path, params=None, max_items=None, *, page_size=None, limit=None, total_sink=None):
        if total_sink is not None:
            total_sink.value = len(rows)
        return list(rows) if limit is None else list(rows)[:limit]

    client = MagicMock()
    client.get_all.side_effect = get_all

    with patch.object(srv, "_get_connection", return_value=client):
        last = srv.list_segments(limit=3, offset=9)
        past = srv.list_segments(limit=3, offset=12)

    assert last["next_offset"] is None and last["returned"] == 3
    assert "no next page" in last["hint"].lower()
    assert "raise limit" not in last["hint"].lower()
    assert past["returned"] == 0
    assert "past the end" in past["hint"].lower()


# ---------------------------------------------------------------------------
# The gate: an eleventh list op cannot get a different answer
# ---------------------------------------------------------------------------


def _paged_ops() -> list[tuple[str, ast.FunctionDef]]:
    """Every ops function that takes an ``offset`` — i.e. every paged list op.

    Derived from the signature rather than from a list of names, so a new op
    joins this gate by being written. Functions with no ``offset`` are left
    alone on purpose: an embedded sample (``get_segment``'s ports) is not a
    paged walk and has no next offset to name.
    """
    found: list[tuple[str, ast.FunctionDef]] = []
    # ``_``-prefixed modules are the shared plumbing, not ops: ``_paginate``
    # itself defines ``validate_page_args``/``paginate``/``next_offset``/
    # ``page_envelope``, all of which take an ``offset`` and none of which is a
    # list op. Including them would make this gate demand that the helper call
    # itself.
    sources = sorted(p for p in OPS_DIR.glob("*.py") if not p.name.startswith("_"))
    assert sources, f"no ops modules under {OPS_DIR} — this gate would check nothing"
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and any(
                a.arg == "offset" for a in node.args.args + node.args.kwonlyargs
            ):
                found.append((path.name, node))
    assert found, "no paged ops found — the derivation is broken, not the code"
    return found


def _called_names(node: ast.FunctionDef) -> set[str]:
    return {
        c.func.id
        for c in ast.walk(node)
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
    }


@pytest.mark.parametrize("name,fn", [(f"{m}:{n.name}", n) for m, n in _paged_ops()])
def test_every_paged_op_builds_its_envelope_through_page_envelope(name, fn):
    """One place decides what a page says about itself.

    Ten hand-rolled ``paginated(...)`` calls is ten chances for the eleventh to
    be written without the hint — 形态 #6, a fact with no mechanical relation to
    the code that has to keep it true.
    """
    called = _called_names(fn)
    assert "page_envelope" in called, f"{name} does not build its envelope with page_envelope"
    assert "paginated" not in called, (
        f"{name} calls vmware_policy.paginated directly, so its hint bypasses the offset"
    )
