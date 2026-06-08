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

CLI_PATH = Path(__file__).resolve().parent.parent / "vmware_nsx" / "cli.py"

# CLI command functions for destructive operations that MUST call
# double_confirm before executing the dangerous operation.
DESTRUCTIVE_CLI_COMMANDS: list[str] = [
    "segment_delete",
    "gateway_delete_tier1",
    "nat_delete_rule",
    "route_delete_static",
]


def _has_double_confirm(file_path: Path, func_name: str) -> bool:
    """Return True if *func_name* in *file_path* references ``double_confirm``."""
    tree = ast.parse(file_path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            source = ast.dump(node)
            return "double_confirm" in source
    return False


@pytest.mark.unit
class TestDestructiveOpsSafety:
    """Every destructive CLI command must include a double_confirm safety guard."""

    @pytest.mark.parametrize("func_name", DESTRUCTIVE_CLI_COMMANDS)
    def test_has_double_confirm(self, func_name: str) -> None:
        assert CLI_PATH.exists(), f"{CLI_PATH} not found"
        assert _has_double_confirm(CLI_PATH, func_name), (
            f"{func_name} in cli.py lacks a double_confirm safety guard"
        )
