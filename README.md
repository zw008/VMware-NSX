<!-- mcp-name: io.github.zw008/vmware-nsx -->
# VMware NSX

[English](README.md) | [中文](README-CN.md)

VMware NSX networking management: segments, gateways, NAT, routing, IPAM — 31 MCP tools, domain-focused.

> NSX Policy API skill for NSX-T 3.0+ and NSX 4.x.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Companion Skills

| Skill | Scope | Tools | Install |
|-------|-------|:-----:|---------|
| **[vmware-nsx](https://github.com/zw008/VMware-NSX)** (this) | Segments, gateways, NAT, routing, IPAM | 31 | `uv tool install vmware-nsx-mgmt` |
| **[vmware-nsx-security](https://github.com/zw008/VMware-NSX-Security)** | DFW rules, security groups, IDS/IPS | - | `uv tool install vmware-nsx-mgmt-security` |
| **[vmware-monitor](https://github.com/zw008/VMware-Monitor)** (read-only) | Inventory, health, alarms, events | 8 | `uv tool install vmware-monitor` |
| **[vmware-aiops](https://github.com/zw008/VMware-AIops)** (full ops) | VM lifecycle, deployment, guest ops, plans | 33 | `uv tool install vmware-aiops` |
| **[vmware-storage](https://github.com/zw008/VMware-Storage)** | Datastores, iSCSI, vSAN | 11 | `uv tool install vmware-storage` |
| **[vmware-vks](https://github.com/zw008/VMware-VKS)** | Tanzu Namespaces, TKC cluster lifecycle | 20 | `uv tool install vmware-vks` |

## Quick Install

```bash
# Via PyPI
uv tool install vmware-nsx-mgmt

# Or pip
pip install vmware-nsx-mgmt
```

## Configuration

```bash
mkdir -p ~/.vmware-nsx
cp config.example.yaml ~/.vmware-nsx/config.yaml
# Edit with your NSX Manager credentials

echo "VMWARE_NSX_PROD_PASSWORD=your_password" > ~/.vmware-nsx/.env
chmod 600 ~/.vmware-nsx/.env

# Verify
vmware-nsx doctor
```

## What This Skill Does

| Category | Tools | Count |
|----------|-------|:-----:|
| **Segments** | list, get, create, update, delete, ports | 6 |
| **Tier-0 Gateways** | list, get, BGP neighbors, route table | 4 |
| **Tier-1 Gateways** | list, get, create, update, delete, route table | 6 |
| **NAT** | list, get, create, update, delete | 5 |
| **Static Routes** | list, create, delete | 3 |
| **IP Pools** | list, allocations, create, add subnet | 4 |
| **Health & Troubleshooting** | alarms, transport nodes, edge clusters, manager status, port status, VM-to-segment | 6 |

## Common Workflows

### Create an App Network (Segment + T1 Gateway + NAT)

1. Create gateway: `vmware-nsx gateway create-t1 app-t1 --edge-cluster edge-cluster-01 --tier0 tier0-gw`
2. Create segment: `vmware-nsx segment create app-web-seg --gateway app-t1 --subnet 10.10.1.1/24 --transport-zone tz-overlay`
3. Add SNAT: `vmware-nsx nat create app-t1 --action SNAT --source 10.10.1.0/24 --translated 172.16.0.10`
4. Verify: `vmware-nsx segment list` and `vmware-nsx nat list app-t1`

Use `--dry-run` to preview any write command first.

### Check Network Health

1. Manager status: `vmware-nsx health manager-status`
2. Transport nodes: `vmware-nsx health transport-nodes`
3. Edge clusters: `vmware-nsx health edge-clusters`
4. Alarms: `vmware-nsx health alarms`

### Troubleshoot VM Connectivity

1. Find VM's segment: `vmware-nsx troubleshoot vm-segment my-vm-01`
2. Check port status: `vmware-nsx troubleshoot port-status <port-id>`
3. Check routes: `vmware-nsx gateway routes-t1 app-t1`
4. Check BGP: `vmware-nsx gateway bgp-neighbors tier0-gw`

## MCP Tools (31)

| Category | Tools | Type |
|----------|-------|------|
| Segments | `list_segments`, `get_segment`, `create_segment`, `update_segment`, `delete_segment`, `list_segment_ports` | Read/Write |
| Tier-0 GW | `list_tier0_gateways`, `get_tier0_gateway`, `get_tier0_bgp_neighbors`, `get_tier0_route_table` | Read |
| Tier-1 GW | `list_tier1_gateways`, `get_tier1_gateway`, `create_tier1_gateway`, `update_tier1_gateway`, `delete_tier1_gateway`, `get_tier1_route_table` | Read/Write |
| NAT | `list_nat_rules`, `get_nat_rule`, `create_nat_rule`, `update_nat_rule`, `delete_nat_rule` | Read/Write |
| Static Routes | `list_static_routes`, `create_static_route`, `delete_static_route` | Read/Write |
| IP Pools | `list_ip_pools`, `get_ip_pool_allocations`, `create_ip_pool`, `create_ip_pool_subnet` | Read/Write |
| Health | `get_nsx_alarms`, `get_transport_node_status`, `get_edge_cluster_status`, `get_manager_cluster_status` | Read |
| Troubleshoot | `get_logical_port_status`, `find_vm_segment` | Read |

## CLI

```bash
# Segments
vmware-nsx segment list
vmware-nsx segment get app-web-seg
vmware-nsx segment create app-web-seg --gateway app-t1 --subnet 10.10.1.1/24 --transport-zone tz-overlay
vmware-nsx segment delete app-web-seg

# Gateways
vmware-nsx gateway list-t0
vmware-nsx gateway list-t1
vmware-nsx gateway create-t1 app-t1 --edge-cluster edge-cluster-01 --tier0 tier0-gw
vmware-nsx gateway bgp-neighbors tier0-gw
vmware-nsx gateway routes-t1 app-t1

# NAT
vmware-nsx nat list app-t1
vmware-nsx nat create app-t1 --action SNAT --source 10.10.1.0/24 --translated 172.16.0.10
vmware-nsx nat delete app-t1 rule-01

# Static Routes
vmware-nsx route list app-t1
vmware-nsx route create app-t1 --network 192.168.100.0/24 --next-hop 10.10.1.254

# IP Pools
vmware-nsx ippool list
vmware-nsx ippool create tep-pool
vmware-nsx ippool add-subnet tep-pool --start 192.168.100.10 --end 192.168.100.50 --cidr 192.168.100.0/24

# Health & Troubleshooting
vmware-nsx health alarms
vmware-nsx health transport-nodes
vmware-nsx health manager-status
vmware-nsx troubleshoot vm-segment my-vm-01

# Diagnostics
vmware-nsx doctor
```

## MCP Server

```bash
# Run directly
uvx --from vmware-nsx-mgmt vmware-nsx-mcp

# Or via Docker
docker compose up -d
```

### Agent Configuration

Add to your AI agent's MCP config:

```json
{
  "mcpServers": {
    "vmware-nsx": {
      "command": "vmware-nsx-mcp",
      "env": {
        "VMWARE_NSX_CONFIG": "~/.vmware-nsx/config.yaml"
      }
    }
  }
}
```

More agent config templates (Claude Code, Cursor, Goose, Continue, etc.) in [examples/mcp-configs/](examples/mcp-configs/).

## Version Compatibility

| NSX Version | Support | Notes |
|-------------|---------|-------|
| NSX 4.x | Full | Latest Policy API, all features |
| NSX-T 3.2 | Full | All features work |
| NSX-T 3.1 | Full | Minor route table format differences |
| NSX-T 3.0 | Compatible | IP pool subnet API introduced here |
| NSX-T 2.5 | Limited | Policy API incomplete; some tools may fail |
| NSX-V (6.x) | Not supported | Different API (SOAP-based) |

### VCF Compatibility

| VCF Version | Bundled NSX | Support |
|-------------|-------------|---------|
| VCF 5.x | NSX 4.x | Full |
| VCF 4.3-4.5 | NSX-T 3.1-3.2 | Full |

## Safety

| Feature | Description |
|---------|-------------|
| Read-heavy | 18/31 tools are read-only |
| Double confirmation | CLI write commands require two prompts |
| Dry-run mode | All write commands support `--dry-run` preview |
| Dependency checks | Delete operations validate no connected resources |
| Input validation | CIDR, IP, VLAN IDs, gateway existence validated |
| Audit logging | All operations logged to `~/.vmware-nsx/audit.log` |
| No firewall ops | Cannot create/modify DFW rules or security groups |
| Credential safety | Passwords only from environment variables |
| Prompt injection defense | NSX object names sanitized before output |

## Troubleshooting

| Problem | Cause & Fix |
|---------|-------------|
| "Segment not found" | Policy API uses segment `id`, not `display_name`. Run `segment list` to get the exact ID. |
| NAT creation fails "gateway not found" | NAT requires a Tier-1 (or Tier-0) gateway. Verify with `gateway list-t1`. Gateway must have an edge cluster. |
| BGP neighbor stuck in Connect/Active | Peer unreachable, ASN mismatch, TCP 179 blocked, or MD5 password mismatch. |
| Transport node "degraded" | TEP unreachable (check MTU >= 1600), NTP sync issues, or host switch config mismatch. |
| "Password not found" | Variable naming: `VMWARE_<TARGET_UPPER>_PASSWORD` (hyphens to underscores). Check `~/.vmware-nsx/.env`. |
| Connection timeout | Use `vmware-nsx doctor --skip-auth` to bypass auth checks on high-latency networks. |

## License

[MIT](LICENSE)
