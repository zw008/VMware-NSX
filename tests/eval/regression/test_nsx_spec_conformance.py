"""Spec-conformance regression eval — every API path must exist in the NSX SDK.

2026-06-08 SDK audit: several read paths parsed response fields that do not
exist on the official NSX 4.2 models, and get_segment_port_for_vm read an
invented ``virtual_interfaces`` field instead of calling the real
``/api/v1/fabric/vifs`` endpoint.  Root cause: the API layer was written
from memory and never validated against the official specification.

This test AST-parses every ``client.<get|get_all|post|put|patch|delete>``
call in vmware_nsx/ whose path is a string literal, an f-string, or a
local variable assigned from one (single-assignment resolution within the
enclosing function), and asserts the path matches a url_template from the
official NSX 4.2 Python SDKs (nsx-policy-python-sdk + nsx-python-sdk),
vendored as a path-only index at tests/eval/spec/nsx_api_operations.json
(the SDK url_template metadata carries no HTTP method — path-only matching
still catches invented paths).

Matching is segment-wise template unification: a candidate segment that
came from an interpolated variable matches any spec segment; a spec
``{param}`` segment matches any candidate segment; literal segments must
match exactly.  Path lengths must match, so invented sub-resources
(e.g. ``/transport-nodes/{id}/fake-status``) are still rejected.  To stay
strict, a single spec-path match may not combine BOTH crossing kinds
(candidate-wildcard↔spec-literal and candidate-literal↔spec-wildcard) —
that combination let invented literals slide past unrelated templates.

Any future invented endpoint fails here instead of 404-ing in production.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC_PATH = REPO_ROOT / "tests" / "eval" / "spec" / "nsx_api_operations.json"
SCAN_DIRS = [REPO_ROOT / "vmware_nsx"]

_HTTP_METHODS = {"get", "get_all", "post", "put", "patch", "delete"}

# Endpoints intentionally outside the SDK url_template index.
_ALLOWLIST = {
    # Session-cookie auth endpoint (NSX REST API authentication, not part of
    # the SDK operation metadata).
    "/api/session/create",
}


def _spec_segment_lists() -> list[list[str]]:
    """Spec paths split into segments; '{...}' segments act as wildcards."""
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    return [op["path"].split("/") for op in spec["operations"]]


def _resolve_path(node: ast.AST, env: dict[str, str]) -> str | None:
    """Resolve a str constant, f-string, or known local Name to a template.

    Unknown interpolations become '{param}' placeholders; Names assigned
    earlier in the same function resolve to their (template) value.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(str(v.value))
            elif (
                isinstance(v, ast.FormattedValue)
                and isinstance(v.value, ast.Name)
                and v.value.id in env
            ):
                parts.append(env[v.value.id])
            else:
                parts.append("{param}")
        return "".join(parts)
    if isinstance(node, ast.Name):
        return env.get(node.id)
    return None


class _ApiCallScanner(ast.NodeVisitor):
    """Collect (location, path-template) for HTTP calls, resolving locals."""

    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self.env: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        saved, self.env = self.env, {}
        self.generic_visit(node)
        self.env = saved

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value = _resolve_path(node.value, self.env)
            if value is not None:
                self.env[node.targets[0].id] = value
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in _HTTP_METHODS
            and node.args
        ):
            path = _resolve_path(node.args[0], self.env)
            if path is not None and path.startswith("/"):
                self.calls.append((f"{self.rel_path}:{node.lineno}", path))
        self.generic_visit(node)


def _collect_api_calls() -> list[tuple[str, str]]:
    """All (location, path) HTTP calls under vmware_nsx/."""
    calls: list[tuple[str, str]] = []
    for scan_dir in SCAN_DIRS:
        for py in sorted(scan_dir.rglob("*.py")):
            scanner = _ApiCallScanner(str(py.relative_to(REPO_ROOT)))
            scanner.visit(ast.parse(py.read_text(encoding="utf-8")))
            calls.extend(scanner.calls)
    return calls


def _matches_spec(path: str, spec_paths: list[list[str]]) -> bool:
    if path in _ALLOWLIST:
        return True
    candidate = path.split("/")
    for spec in spec_paths:
        if len(spec) != len(candidate):
            continue
        cand_wild_vs_spec_literal = False
        cand_literal_vs_spec_wild = False
        for spec_seg, cand_seg in zip(spec, candidate):
            spec_wild = bool(re.fullmatch(r"\{[^}]+\}", spec_seg))
            cand_wild = "{param}" in cand_seg
            if not (spec_wild or cand_wild or spec_seg == cand_seg):
                break
            if cand_wild and not spec_wild:
                cand_wild_vs_spec_literal = True
            elif spec_wild and not cand_wild:
                cand_literal_vs_spec_wild = True
        else:
            # Both crossing kinds in one match = too loose; keep looking.
            if not (cand_wild_vs_spec_literal and cand_literal_vs_spec_wild):
                return True
    return False


def test_spec_index_is_loaded() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["operation_count"] >= 2000, "spec index missing or truncated"
    assert spec["operation_count"] == len(spec["operations"])


def test_known_invented_path_is_rejected() -> None:
    """Self-check: the matcher must reject paths absent from the SDK."""
    spec_paths = _spec_segment_lists()
    invented = [
        "/api/v1/fabric/virtual-machines/{param}/virtual-interfaces",
        "/api/v1/totally/made/up",
        "/policy/api/v1/infra/segments/{param}/imaginary-status",
        # would match the node-proxy catch-all /{target-node-id}/{target-uri}
        # if those templates weren't excluded from the index
        "/api/v1/transport-nodes/{param}/fake-status",
        # literal sub-resource invented under a real collection
        "/policy/api/v1/infra/tier-1s/{param}/locale-services/default/bogus",
    ]
    for path in invented:
        assert not _matches_spec(path, spec_paths), f"matcher accepted invented path {path}"


def test_real_endpoints_are_accepted() -> None:
    """Self-check: known-good endpoints used by the ops layer must match."""
    spec_paths = _spec_segment_lists()
    real = [
        "/api/v1/alarms",
        "/api/v1/fabric/vifs",
        "/api/v1/transport-nodes/{param}/status",
        "/policy/api/v1/infra/segments/{param}/ports/{param}/state",
        "/policy/api/v1/infra/tier-1s/{param}/nat/USER/nat-rules/{param}",
        # literal "default" id satisfies the spec's {locale-services-id}
        "/policy/api/v1/infra/tier-1s/{param}/locale-services/default",
        # interpolated gateway-type segment ({param}) unifies with the
        # spec literal "tier-0s"/"tier-1s"
        "/policy/api/v1/infra/{param}/{param}/static-routes/{param}",
    ]
    for path in real:
        assert _matches_spec(path, spec_paths), f"matcher rejected real path {path}"


def test_every_api_call_exists_in_nsx_sdk_spec() -> None:
    spec_paths = _spec_segment_lists()
    calls = _collect_api_calls()
    assert len(calls) >= 40, (
        f"only {len(calls)} API calls collected — AST scan regressed?"
    )

    violations = [
        f"{loc}: {path}"
        for loc, path in calls
        if not _matches_spec(path, spec_paths)
    ]

    assert not violations, (
        "API paths not present in the NSX 4.2 SDK url_template index "
        "(invented endpoints WILL 404 in production):\n  " + "\n  ".join(violations)
    )
