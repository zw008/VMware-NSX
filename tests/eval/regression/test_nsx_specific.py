"""NSX-specific regression evals.

踩坑 #19/#34 family — MCP and CLI wrappers passed kwargs their ops
functions don't accept, so four tools failed with TypeError/ValueError on
EVERY invocation (errors swallowed into {"error", "hint"} payloads):

* create_tier1_gateway passed edge_cluster_path= / route_advertisement=
  (ops wants route_advertisement_types: list[str]; edge_cluster_path was
  unsupported until 2026-06-07)
* update_tier1_gateway passed route_advertisement= unconditionally —
  rejected by ops allowed_fields → ValueError on every call
* create_static_route passed next_hop=str (ops wants next_hops: list[dict])
* create_ip_pool passed start_ip/end_ip/cidr/gateway_ip (ops wants
  subnets: list[dict])

Found 2026-06-07 during the Glama TDQS description rewrite. These tests
invoke the real wrapper → real ops path with a mocked NSX client, so any
future signature drift between wrapper and ops fails here, not in prod.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _mock_client() -> MagicMock:
    client = MagicMock(name="NsxClient")
    client.put.return_value = {"id": "created"}
    client.patch.return_value = {"id": "patched"}
    return client


# ── MCP wrapper → ops signature compatibility ──────────────────────────


def test_mcp_create_tier1_gateway_kwargs_match_ops() -> None:
    client = _mock_client()
    with patch("mcp_server.server._get_connection", return_value=client):
        from mcp_server.server import create_tier1_gateway

        result = create_tier1_gateway(
            tier1_id="t1-regress",
            display_name="Regression GW",
            tier0_path="/infra/tier-0s/t0",
            edge_cluster_path="/infra/sites/default/enforcement-points/default/edge-clusters/ec1",
            route_advertisement="TIER1_CONNECTED, TIER1_NAT",
        )
    assert "error" not in result, f"wrapper→ops call failed: {result}"
    # gateway PUT + locale-service PUT for edge_cluster_path
    assert client.put.call_count == 2
    gw_body = client.put.call_args_list[0].args[1]
    assert gw_body["route_advertisement_types"] == ["TIER1_CONNECTED", "TIER1_NAT"]
    ls_path, ls_body = client.put.call_args_list[1].args
    assert ls_path.endswith("/locale-services/default")
    assert ls_body == {"edge_cluster_path": "/infra/sites/default/enforcement-points/default/edge-clusters/ec1"}


def test_mcp_update_tier1_gateway_filters_none_and_maps_ra() -> None:
    client = _mock_client()
    with patch("mcp_server.server._get_connection", return_value=client):
        from mcp_server.server import update_tier1_gateway

        result = update_tier1_gateway(
            tier1_id="t1-regress",
            route_advertisement="TIER1_STATIC_ROUTES",
        )
    assert "error" not in result, f"wrapper→ops call failed: {result}"
    body = client.patch.call_args.args[1]
    # None fields must NOT be PATCHed; key must be the ops-level name
    assert body == {"route_advertisement_types": ["TIER1_STATIC_ROUTES"]}


def test_mcp_create_static_route_builds_next_hops() -> None:
    client = _mock_client()
    with patch("mcp_server.server._get_connection", return_value=client):
        from mcp_server.server import create_static_route

        result = create_static_route(
            tier1_id="t1-regress",
            route_id="r1",
            network="10.0.0.0/8",
            next_hop="192.168.1.254",
        )
    assert "error" not in result, f"wrapper→ops call failed: {result}"
    body = client.put.call_args.args[1]
    assert body["next_hops"] == [{"ip_address": "192.168.1.254", "admin_distance": 1}]


def test_mcp_create_ip_pool_builds_subnets() -> None:
    client = _mock_client()
    with patch("mcp_server.server._get_connection", return_value=client):
        from mcp_server.server import create_ip_pool

        result = create_ip_pool(
            pool_id="pool-regress",
            display_name="Regression Pool",
            start_ip="192.168.1.10",
            end_ip="192.168.1.100",
            cidr="192.168.1.0/24",
            gateway_ip="192.168.1.1",
        )
    assert "error" not in result, f"wrapper→ops call failed: {result}"
    # pool PUT + one subnet PUT
    assert client.put.call_count == 2
    subnet_body = client.put.call_args_list[1].args[1]
    assert subnet_body["cidr"] == "192.168.1.0/24"
    assert subnet_body["allocation_ranges"] == [{"start": "192.168.1.10", "end": "192.168.1.100"}]
    assert subnet_body["gateway_ip"] == "192.168.1.1"


# ── CLI command → ops signature compatibility (same bug, same fix) ─────


@pytest.fixture()
def cli_env():
    client = _mock_client()
    import vmware_nsx.cli as cli

    with (
        patch.object(cli, "_get_connection", return_value=(client, None)),
        patch.object(cli, "_resolve_target", return_value="test-target"),
        patch.object(cli, "_double_confirm"),
        patch.object(cli, "_audit"),
    ):
        yield cli, client


def test_cli_gateway_create_tier1_kwargs_match_ops(cli_env) -> None:
    cli, client = cli_env
    cli.gateway_create_tier1(
        tier1_id="t1-cli",
        display_name="CLI GW",
        tier0_path="/infra/tier-0s/t0",
        edge_cluster_path=None,
        route_advertisement="TIER1_CONNECTED",
        target=None,
        config=None,
        dry_run=False,
    )
    body = client.put.call_args.args[1]
    assert body["route_advertisement_types"] == ["TIER1_CONNECTED"]


def test_cli_gateway_update_tier1_kwargs_match_ops(cli_env) -> None:
    cli, client = cli_env
    cli.gateway_update_tier1(
        tier1_id="t1-cli",
        display_name="Renamed",
        tier0_path=None,
        route_advertisement=None,
        target=None,
        config=None,
        dry_run=False,
    )
    body = client.patch.call_args.args[1]
    assert body == {"display_name": "Renamed"}


def test_cli_route_create_static_kwargs_match_ops(cli_env) -> None:
    cli, client = cli_env
    cli.route_create_static(
        tier1_id="t1-cli",
        route_id="r1",
        network="10.0.0.0/8",
        next_hop="192.168.1.254",
        target=None,
        config=None,
        dry_run=False,
    )
    body = client.put.call_args.args[1]
    assert body["next_hops"] == [{"ip_address": "192.168.1.254", "admin_distance": 1}]


def test_cli_ip_pool_create_kwargs_match_ops(cli_env) -> None:
    cli, client = cli_env
    cli.ip_pool_create(
        pool_id="pool-cli",
        display_name="CLI Pool",
        start_ip="10.0.0.10",
        end_ip="10.0.0.20",
        cidr="10.0.0.0/24",
        gateway_ip=None,
        target=None,
        config=None,
        dry_run=False,
    )
    subnet_body = client.put.call_args_list[1].args[1]
    assert subnet_body["allocation_ranges"] == [{"start": "10.0.0.10", "end": "10.0.0.20"}]
    assert "gateway_ip" not in subnet_body
