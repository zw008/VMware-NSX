"""Safety boundary tests -- verify destructive ops have double_confirm guards.

Uses Python AST parsing to verify that every destructive CLI command in
cli.py contains a call to ``double_confirm`` (or ``_double_confirm``).

The guard lives in the CLI command layer (which owns the interactive
confirmation flow), not in ops/ — ops functions are also invoked by the
MCP server, where confirmation is the agent's responsibility and a
blocking prompt would hang the stdio transport.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_CLI_BASE = Path(__file__).resolve().parent.parent / "vmware_nsx" / "cli"
# The CLI is a package (vmware_nsx/cli/) split by command group; fall back to
# the legacy single-module layout (vmware_nsx/cli.py) if present.
CLI_SOURCES: list[Path] = (
    sorted(_CLI_BASE.glob("*.py"))
    if _CLI_BASE.is_dir()
    else [_CLI_BASE.with_suffix(".py")]
)

# CLI command functions for destructive operations that MUST call
# double_confirm before executing the dangerous operation.
DESTRUCTIVE_CLI_COMMANDS: list[str] = [
    "segment_delete",
    "gateway_delete_tier1",
    "nat_delete_rule",
    "route_delete_static",
]


def _has_double_confirm(sources: list[Path], func_name: str) -> bool:
    """Return True if *func_name* in any of *sources* references ``double_confirm``."""
    for file_path in sources:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                return "double_confirm" in ast.dump(node)
    return False


@pytest.mark.unit
class TestDestructiveOpsSafety:
    """Every destructive CLI command must include a double_confirm safety guard."""

    @pytest.mark.parametrize("func_name", DESTRUCTIVE_CLI_COMMANDS)
    def test_has_double_confirm(self, func_name: str) -> None:
        assert CLI_SOURCES, "no CLI source files found"
        assert _has_double_confirm(CLI_SOURCES, func_name), (
            f"{func_name} in the CLI package lacks a double_confirm safety guard"
        )
