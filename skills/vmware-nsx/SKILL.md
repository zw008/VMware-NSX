---
name: vmware-nsx
description: >
  Use this skill whenever the user needs to manage VMware NSX networking — segments, gateways, NAT, routing, and IP pools.
  Directly handles: create/manage network segments, configure Tier-0/Tier-1 gateways, set up NAT rules, manage static routes, configure IP pools, check transport node and edge cluster health.
  Always use this skill for "create segment", "set up gateway", "create NAT rule", "check network health", "troubleshoot connectivity", or any NSX/networking/segment task.
  Do NOT use for DFW firewall rules or security groups (use vmware-nsx-security), VM lifecycle (use vmware-aiops), or AVI/ALB load balancing (use vmware-avi).
  For multi-step workflows use vmware-pilot.
installer:
  kind: uv
  package: vmware-nsx-mgmt
allowed-tools:
  - Bash
metadata: {"openclaw":{"requires":{"env":["VMWARE_NSX_CONFIG"],"bins":["vmware-nsx"],"config":["~/.vmware-nsx/config.yaml","~/.vmware-nsx/.env"]},"optional":{"env":["VMWARE_<TARGET>_PASSWORD"],"bins":["vmware-policy"]},"primaryEnv":"VMWARE_NSX_CONFIG","homepage":"https://github.com/zw008/VMware-NSX","emoji":"🌐","os":["macos","linux"]}}
compatibility: >
  vmware-policy auto-installed as Python dependency (provides @vmware_tool decorator and audit logging). All write operations audited to ~/.vmware/audit.db.
  Credentials: Each NSX Manager target requires a per-target password env var in ~/.vmware-nsx/.env following the pattern VMWARE_<TARGET_NAME_UPPER>_PASSWORD. Also supports certificate-based auth. Passwords are never logged or echoed.
  Destructive operations: Segment/gateway/NAT delete require double confirmation + --dry-run. Segment delete checks for connected ports, gateway delete checks for connected segments.
  No webhooks, no outbound network calls, no guest operations. Local only: stdio MCP + NSX Policy API (HTTPS 443).
  SSL bypass: verify_ssl is on by default; false option for self-signed certs in lab environments only.
  Transitive dependencies: Only vmware-policy (audit/policy). No post-install scripts or background services.
---

# VMware NSX

> **Disclaimer**: This is a community-maintained open-source project and is **not affiliated with, endorsed by, or sponsored by VMware, Inc. or Broadcom Inc.** "VMware" and "NSX" are trademarks of Broadcom. Source code is publicly auditable at [github.com/zw008/VMware-NSX](https://github.com/zw008/VMware-NSX) under the MIT license.

VMware NSX networking management — 31 MCP tools for segments, gateways, NAT, routing, and IPAM.

> Domain-focused networking skill for NSX-T / NSX 4.x Policy API.
> **Companion skills**: [vmware-nsx-security](https://github.com/zw008/VMware-NSX-Security) (DFW/firewall), [vmware-aiops](https://github.com/zw008/VMware-AIops) (VM lifecycle), [vmware-monitor](https://github.com/zw008/VMware-Monitor) (read-only monitoring), [vmware-storage](https://github.com/zw008/VMware-Storage) (iSCSI/vSAN), [vmware-vks](https://github.com/zw008/VMware-VKS) (Tanzu Kubernetes), [vmware-aria](https://github.com/zw008/VMware-Aria) (metrics/alerts/capacity), [vmware-avi](https://github.com/zw008/VMware-AVI) (AVI/ALB/AKO).
> | [vmware-pilot](../vmware-pilot/SKILL.md) (workflow orchestration) | [vmware-policy](../vmware-policy/SKILL.md) (audit/policy)

## What This Skill Does

| Category | Tools | Count |
|----------|-------|:-----:|
| **Segments** | list, get details, create, update, delete, list ports | 6 |
| **Tier-0 Gateways** | list, get details, BGP neighbors, route table | 4 |
| **Tier-1 Gateways** | list, get details, create, update, delete, route table | 6 |
| **NAT** | list rules, get rule details, create rule, update rule, delete rule | 5 |
| **Static Routes** | list, create, delete | 3 |
| **IP Pools** | list, get allocations, create pool, create subnet | 4 |
| **Health & Troubleshooting** | NSX alarms, transport node status, edge cluster status, manager cluster status, logical port status, VM-to-segment lookup | 6 |

**Total**: 31 tools (18 read-only + 13 write)

## Quick Install

```bash
uv tool install vmware-nsx-mgmt
vmware-nsx doctor
```

## When to Use This Skill

- List, create, or modify NSX segments (overlay / VLAN-backed)
- Create or manage Tier-0 / Tier-1 gateways
- Configure NAT rules (SNAT, DNAT, reflexive)
- View or add static routes, check BGP neighbors
- Manage IP pools and subnet allocations
- Check NSX alarms, transport node health, edge cluster status
- Find which segment a VM is connected to
- Troubleshoot logical port status

**Use companion skills for**:
- Distributed firewall, security groups, DFW rules, IDS/IPS → `vmware-nsx-security`
- VM lifecycle, deployment, guest ops → `vmware-aiops`
- vSphere inventory, health, alarms, events → `vmware-monitor`
- Storage: iSCSI, vSAN, datastores → `vmware-storage`
- Tanzu Kubernetes → `vmware-vks`
- Load balancing, AVI/ALB, AKO, Ingress → `vmware-avi`

## Related Skills — Skill Routing

| User Intent | Recommended Skill |
|-------------|-------------------|
| NSX networking: segments, gateways, NAT, routing, IPAM | **vmware-nsx** ← this skill |
| NSX security: DFW rules, security groups, IDS/IPS | **vmware-nsx-security** |
| Read-only vSphere monitoring, alarms, events | **vmware-monitor** |
| VM lifecycle, deployment, guest ops | **vmware-aiops** |
| Storage: iSCSI, vSAN, datastores | **vmware-storage** |
| Tanzu Kubernetes (vSphere 8.x+) | **vmware-vks** |
| Aria Ops: metrics, alerts, capacity planning | **vmware-aria** |
| Multi-step workflows with approval | **vmware-pilot** |
| Load balancer, AVI, ALB, AKO, Ingress | **vmware-avi** (`uv tool install vmware-avi`) |
| Audit log query | **vmware-policy** (`vmware-audit` CLI) |

## Common Workflows

### Create an App Network (Segment + T1 Gateway + NAT)

1. Create a Tier-1 gateway → `vmware-nsx gateway create-t1 app-t1 --edge-cluster edge-cluster-01 --tier0 tier0-gw`
2. Create a segment → `vmware-nsx segment create app-web-seg --gateway app-t1 --subnet <subnet-cidr> --transport-zone tz-overlay`
3. Add SNAT rule → `vmware-nsx nat create app-t1 --action SNAT --source <private-cidr> --translated <public-ip>`
4. Verify → `vmware-nsx segment list` and `vmware-nsx nat list app-t1`

**Dry-run first**: Append `--dry-run` to any write command to preview without executing:
```bash
vmware-nsx segment create app-web-seg --gateway app-t1 --subnet <subnet-cidr> --transport-zone tz-overlay --dry-run
```

### Check Network Health

1. NSX manager cluster status → `vmware-nsx health manager-status`
2. Transport node status → `vmware-nsx health transport-nodes`
3. Edge cluster status → `vmware-nsx health edge-clusters`
4. Active alarms → `vmware-nsx health alarms`
5. If issues found, investigate with `vmware-monitor` for vSphere-side events

### Troubleshoot VM Connectivity

1. Find the VM's segment → `vmware-nsx troubleshoot vm-segment my-vm-01`
2. Check logical port status → `vmware-nsx troubleshoot port-status <port-id>`
3. Check the gateway route table → `vmware-nsx gateway routes-t1 app-t1`
4. Check BGP neighbors on T0 → `vmware-nsx gateway bgp-neighbors tier0-gw`
5. Review NAT rules → `vmware-nsx nat list app-t1`

### Multi-Target Operations

All commands accept `--target <name>` to operate against a specific NSX Manager from your config:

```bash
# Default target (first in config.yaml)
vmware-nsx segment list

# Specific target
vmware-nsx segment list --target nsx-prod
vmware-nsx health alarms --target nsx-lab
```

## Usage Mode

| Scenario | Recommended | Why |
|----------|:-----------:|-----|
| Local/small models (Ollama, Qwen) | **CLI** | ~2K tokens vs ~8K for MCP |
| Cloud models (Claude, GPT-4o) | Either | MCP gives structured JSON I/O |
| Automated pipelines | **MCP** | Type-safe parameters, structured output |

## MCP Tools (31 — 18 read, 13 write)

All MCP tools accept an optional `target` parameter to select which NSX Manager to connect to.

| Category | Tool | Type | Description |
|----------|------|:----:|-------------|
| Segment | `list_segments` | Read | List all segments with type, subnet, gateway, transport zone |
| | `get_segment` | Read | Get segment details including ports and subnet config |
| | `create_segment` | Write | Create overlay or VLAN segment with subnet and gateway |
| | `update_segment` | Write | Update segment properties (description, tags, DHCP) |
| | `delete_segment` | Write | Delete a segment (checks for connected ports first) |
| | `list_segment_ports` | Read | List logical ports on a segment with status |
| Tier-0 GW | `list_tier0_gateways` | Read | List Tier-0 gateways with HA mode and edge cluster |
| | `get_tier0_gateway` | Read | Get Tier-0 details: interfaces, routing config, BGP |
| | `get_tier0_bgp_neighbors` | Read | List BGP neighbor sessions with state, ASN, routes |
| | `get_tier0_route_table` | Read | Get Tier-0 routing table (connected, static, BGP) |
| Tier-1 GW | `list_tier1_gateways` | Read | List Tier-1 gateways with linked Tier-0 and edge cluster |
| | `get_tier1_gateway` | Read | Get Tier-1 details: interfaces, route advertisement |
| | `create_tier1_gateway` | Write | Create Tier-1 gateway with edge cluster and Tier-0 link |
| | `update_tier1_gateway` | Write | Update Tier-1 properties (route advertisement, tags) |
| | `delete_tier1_gateway` | Write | Delete a Tier-1 gateway (checks for connected segments) |
| | `get_tier1_route_table` | Read | Get Tier-1 routing table |
| NAT | `list_nat_rules` | Read | List NAT rules on a Tier-1 gateway |
| | `get_nat_rule` | Read | Get NAT rule details (action, source, destination, translated) |
| | `create_nat_rule` | Write | Create SNAT/DNAT/reflexive NAT rule on a gateway |
| | `update_nat_rule` | Write | Update NAT rule properties |
| | `delete_nat_rule` | Write | Delete a NAT rule |
| Static Routes | `list_static_routes` | Read | List static routes on a Tier-0 or Tier-1 gateway |
| | `create_static_route` | Write | Add a static route with network and next-hop |
| | `delete_static_route` | Write | Remove a static route |
| IP Pools | `list_ip_pools` | Read | List IP pools with usage statistics |
| | `get_ip_pool_allocations` | Read | Show allocated IPs from a pool |
| | `create_ip_pool` | Write | Create a new IP address pool |
| | `create_ip_pool_subnet` | Write | Add a subnet/range to an IP pool |
| Health | `get_nsx_alarms` | Read | List active NSX alarms with severity and entity |
| | `get_transport_node_status` | Read | Transport node connectivity and config status |
| | `get_edge_cluster_status` | Read | Edge cluster member status and failover config |
| | `get_manager_cluster_status` | Read | NSX Manager cluster health and node roles |
| Troubleshoot | `get_logical_port_status` | Read | Logical port admin/operational status and link state |
| | `find_vm_segment` | Read | Find which segment(s) a VM is connected to by name |

**Read/write split**: 18 tools are read-only, 13 modify state. Write tools require explicit parameters and are audit-logged. All write operations support dry-run mode.

## CLI Quick Reference

```bash
# Segments
vmware-nsx segment list [--target <name>]
vmware-nsx segment get <segment-name>
vmware-nsx segment create <name> --gateway <t1> --subnet <cidr> --transport-zone <tz> [--dry-run]
vmware-nsx segment update <name> --description "new desc" [--dry-run]
vmware-nsx segment delete <name> [--dry-run]
vmware-nsx segment ports <segment-name>

# Tier-0 Gateways
vmware-nsx gateway list-t0
vmware-nsx gateway get-t0 <name>
vmware-nsx gateway bgp-neighbors <t0-name>
vmware-nsx gateway routes-t0 <t0-name>

# Tier-1 Gateways
vmware-nsx gateway list-t1
vmware-nsx gateway get-t1 <name>
vmware-nsx gateway create-t1 <name> --edge-cluster <ec> --tier0 <t0> [--dry-run]
vmware-nsx gateway update-t1 <name> --route-advertisement connected,nat [--dry-run]
vmware-nsx gateway delete-t1 <name> [--dry-run]
vmware-nsx gateway routes-t1 <t1-name>

# NAT
vmware-nsx nat list <gateway-name>
vmware-nsx nat get <gateway-name> <rule-id>
vmware-nsx nat create <gateway-name> --action SNAT --source <cidr> --translated <ip> [--dry-run]
vmware-nsx nat update <gateway-name> <rule-id> --translated <new-ip> [--dry-run]
vmware-nsx nat delete <gateway-name> <rule-id> [--dry-run]

# Static Routes
vmware-nsx route list <gateway-name>
vmware-nsx route create <gateway-name> --network <cidr> --next-hop <ip> [--dry-run]
vmware-nsx route delete <gateway-name> <route-id> [--dry-run]

# IP Pools
vmware-nsx ippool list
vmware-nsx ippool allocations <pool-id>
vmware-nsx ippool create <name> [--dry-run]
vmware-nsx ippool add-subnet <pool-id> --start <ip> --end <ip> --cidr <cidr> [--dry-run]

# Health & Troubleshooting
vmware-nsx health alarms [--severity CRITICAL]
vmware-nsx health transport-nodes
vmware-nsx health edge-clusters
vmware-nsx health manager-status
vmware-nsx troubleshoot port-status <port-id>
vmware-nsx troubleshoot vm-segment <vm-name>

# Diagnostics
vmware-nsx doctor [--skip-auth]
```

> Full CLI reference with all options and output formats: see `references/cli-reference.md`

## Troubleshooting

### "Segment not found" when querying

Segment display names and Policy API IDs can differ. Use `vmware-nsx segment list` to get the exact ID. The Policy API uses the segment `id` field, not `display_name`. Common mistakes: using the display name with spaces instead of the hyphenated ID.

### NAT rule creation fails with "gateway not found"

NAT rules are created on Tier-1 gateways (or Tier-0 for some topologies). Verify the gateway name with `vmware-nsx gateway list-t1`. The gateway must have an edge cluster assigned for NAT to function.

### BGP neighbor shows "Connect" or "Active" state

The BGP session is not established. Common causes:
1. Peer IP unreachable from the edge node — check physical uplinks and VLAN config
2. ASN mismatch — compare local and remote ASN in `bgp-neighbors` output
3. Firewall blocking TCP 179 — check edge node firewall rules (not NSX DFW)
4. MD5 password mismatch — verify authentication settings on both sides

### Transport node status "degraded"

A transport node in degraded state has partial connectivity. Steps:
1. Check `vmware-nsx health transport-nodes` for the specific failure reason
2. Common cause: tunnel endpoint (TEP) unreachable — verify underlay MTU (minimum 1600 for Geneve)
3. Check NTP sync between NSX Manager and transport nodes
4. If recently upgraded, verify the host switch config matches NSX Manager expectations

### "Password not found" error

The password environment variable is missing. Variable names follow the pattern `VMWARE_<TARGET_NAME_UPPER>_PASSWORD` where hyphens become underscores. Example: target `nsx-prod` needs `VMWARE_NSX_PROD_PASSWORD`. Check your `~/.vmware-nsx/.env` file.

## Safety

- **Read-heavy**: 18 of 31 tools are read-only (list, get, status, health, troubleshoot)
- **Audit logging**: All operations logged to `~/.vmware/audit.db` (SQLite WAL, via vmware-policy) with timestamp, user, target, operation, parameters, and result
- **Double confirmation**: CLI write commands require two separate confirmation prompts before executing
- **Dry-run mode**: All write commands support `--dry-run` to preview API calls without executing
- **Dependency checks**: Segment delete checks for connected ports; gateway delete checks for connected segments; prevents accidental cascade failures
- **Input validation**: CIDR networks validated, IP addresses checked, gateway existence verified before NAT/route operations
- **Prompt injection defense**: NSX object names returned from the API are sanitized via `_sanitize()` — strips control characters, truncates to 500 chars
- **Credential safety**: Passwords loaded only from environment variables (`.env` file), never from `config.yaml`
- **No firewall operations**: Cannot create, modify, or delete DFW rules, security groups, or IDS/IPS policies — that scope belongs to `vmware-nsx-security`

## Setup

```bash
uv tool install vmware-nsx-mgmt
mkdir -p ~/.vmware-nsx
cp config.example.yaml ~/.vmware-nsx/config.yaml
# Edit config.yaml with your NSX Manager targets

# Add to ~/.vmware-nsx/.env (create if missing, chmod 600):
# VMWARE_NSX_PROD_PASSWORD=<your-password>
chmod 600 ~/.vmware-nsx/.env

vmware-nsx doctor
```

> All tools are automatically audited via vmware-policy. Audit logs: `vmware-audit log --last 20`

> Full setup guide with multi-target config, MCP server setup, and Docker: see `references/setup-guide.md`

## Architecture

```
User (natural language)
  |
AI Agent (Claude Code / Goose / Cursor)
  | reads SKILL.md
vmware-nsx CLI or MCP server (stdio transport)
  | NSX Policy API (REST/JSON over HTTPS)
NSX Manager
  |
Segments / Gateways / NAT / Routes / IP Pools / Transport Nodes
```

The MCP server uses stdio transport (local only, no network listener). Connections to NSX Manager use HTTPS on port 443.

## Audit & Safety

All operations are automatically audited via vmware-policy (`@vmware_tool` decorator):
- Every tool call logged to `~/.vmware/audit.db` (SQLite, framework-agnostic)
- Policy rules enforced via `~/.vmware/rules.yaml` (deny rules, maintenance windows, risk levels)
- Risk classification: each tool tagged as low/medium/high/critical
- View recent operations: `vmware-audit log --last 20`
- View denied operations: `vmware-audit log --status denied`

vmware-policy is automatically installed as a dependency — no manual setup needed.

## License

MIT — [github.com/zw008/VMware-NSX](https://github.com/zw008/VMware-NSX)
