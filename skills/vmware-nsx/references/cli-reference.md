# CLI Reference

Complete command reference for `vmware-nsx` CLI.

## Global Options

All commands accept these options:

| Option | Description |
|--------|-------------|
| `--target <name>` | Target name from `~/.vmware-nsx/config.yaml` (defaults to first target) |
| `--config <path>` | Override config file path |
| `--help` | Show command help |

---

## Segment Commands

### `segment list`

List all segments with type, subnet, gateway, and transport zone.

```bash
vmware-nsx segment list
vmware-nsx segment list --target nsx-prod
```

Output columns: Name, ID, Type (OVERLAY/VLAN), Subnet, Gateway, Transport Zone, Admin State.

### `segment get`

Get detailed information about a specific segment.

```bash
vmware-nsx segment get app-web-seg
```

| Argument | Required | Description |
|----------|:--------:|-------------|
| `segment_id` | Yes | Segment ID (Policy API ID, not display name) |

Output: JSON with `id`, `display_name`, `type`, `subnets`, `connectivity_path` (linked gateway), `transport_zone_path`, `admin_state`, `tags`, `description`.

### `segment create`

Create a new overlay or VLAN segment.

```bash
vmware-nsx segment create app-web-seg \
  --gateway app-t1 \
  --subnet 10.10.1.1/24 \
  --transport-zone tz-overlay

vmware-nsx segment create vlan-seg-100 \
  --vlan-ids 100 \
  --transport-zone tz-vlan \
  --dry-run
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `name` | Yes | - | Segment ID and display name |
| `--gateway` | No | - | Tier-1 gateway to connect to |
| `--subnet` | No | - | Gateway CIDR (e.g., `10.10.1.1/24`) |
| `--transport-zone` | Yes | - | Transport zone name or path |
| `--vlan-ids` | No | - | VLAN ID(s) for VLAN-backed segments |
| `--description` | No | `""` | Description |
| `--tags` | No | `[]` | Tags in `key:value` format, comma-separated |
| `--dry-run` | No | `false` | Preview without executing |

**Safety**: Requires double confirmation. Transport zone and gateway (if specified) are validated before creation.

### `segment update`

Update segment properties.

```bash
vmware-nsx segment update app-web-seg --description "Production web tier"
vmware-nsx segment update app-web-seg --tags "env:prod,team:web" --dry-run
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `segment_id` | Yes | - | Segment ID |
| `--description` | No | - | New description |
| `--tags` | No | - | New tags (replaces existing) |
| `--dry-run` | No | `false` | Preview without executing |

**Safety**: Requires double confirmation. Fetches current segment state before updating.

### `segment delete`

Delete a segment.

```bash
vmware-nsx segment delete app-web-seg
vmware-nsx segment delete app-web-seg --dry-run
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `segment_id` | Yes | - | Segment ID |
| `--force` | No | `false` | Skip connected-port check |
| `--dry-run` | No | `false` | Preview without executing |

**Safety**: Requires double confirmation. Checks for connected logical ports before deletion — refuses to delete if ports exist unless `--force` is used.

### `segment ports`

List logical ports on a segment.

```bash
vmware-nsx segment ports app-web-seg
```

| Argument | Required | Description |
|----------|:--------:|-------------|
| `segment_id` | Yes | Segment ID |

Output: JSON array with `id`, `display_name`, `admin_state`, `attachment` (VM or router interface), `address_bindings`.

---

## Gateway Commands

### `gateway list-t0`

List all Tier-0 gateways.

```bash
vmware-nsx gateway list-t0
```

Output columns: Name, ID, HA Mode (ACTIVE_STANDBY/ACTIVE_ACTIVE), Edge Cluster, Failover Mode.

### `gateway get-t0`

Get Tier-0 gateway details.

```bash
vmware-nsx gateway get-t0 tier0-gw
```

| Argument | Required | Description |
|----------|:--------:|-------------|
| `gateway_id` | Yes | Tier-0 gateway ID |

Output: JSON with `id`, `display_name`, `ha_mode`, `failover_mode`, `edge_cluster_path`, `interfaces`, `bgp_config`, `route_redistribution`.

### `gateway bgp-neighbors`

List BGP neighbor sessions on a Tier-0 gateway.

```bash
vmware-nsx gateway bgp-neighbors tier0-gw
```

| Argument | Required | Description |
|----------|:--------:|-------------|
| `gateway_id` | Yes | Tier-0 gateway ID |

Output columns: Neighbor Address, Remote ASN, State (Established/Connect/Active/Idle), Prefixes Received, Uptime.

### `gateway routes-t0`

Get the Tier-0 routing table.

```bash
vmware-nsx gateway routes-t0 tier0-gw
vmware-nsx gateway routes-t0 tier0-gw --source BGP
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `gateway_id` | Yes | - | Tier-0 gateway ID |
| `--source` | No | all | Filter by route source: `CONNECTED`, `STATIC`, `BGP` |

Output: JSON array with `network`, `next_hop`, `source`, `admin_distance`, `interface`.

### `gateway list-t1`

List all Tier-1 gateways.

```bash
vmware-nsx gateway list-t1
```

Output columns: Name, ID, Linked Tier-0, Edge Cluster, Route Advertisement.

### `gateway get-t1`

Get Tier-1 gateway details.

```bash
vmware-nsx gateway get-t1 app-t1
```

| Argument | Required | Description |
|----------|:--------:|-------------|
| `gateway_id` | Yes | Tier-1 gateway ID |

Output: JSON with `id`, `display_name`, `tier0_path`, `edge_cluster_path`, `route_advertisement_types`, `interfaces`, `tags`.

### `gateway create-t1`

Create a new Tier-1 gateway.

```bash
vmware-nsx gateway create-t1 app-t1 \
  --edge-cluster edge-cluster-01 \
  --tier0 tier0-gw

vmware-nsx gateway create-t1 app-t1 \
  --edge-cluster edge-cluster-01 \
  --tier0 tier0-gw \
  --route-advertisement connected,nat \
  --dry-run
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `name` | Yes | - | Gateway ID and display name |
| `--edge-cluster` | No | - | Edge cluster name or path |
| `--tier0` | No | - | Tier-0 gateway to link to |
| `--route-advertisement` | No | - | Route types to advertise (comma-separated) |
| `--description` | No | `""` | Description |
| `--failover-mode` | No | `PREEMPTIVE` | Failover mode |
| `--dry-run` | No | `false` | Preview without executing |

**Safety**: Requires double confirmation. Edge cluster and Tier-0 gateway (if specified) are validated.

### `gateway update-t1`

Update Tier-1 gateway properties.

```bash
vmware-nsx gateway update-t1 app-t1 --route-advertisement connected,nat,static
vmware-nsx gateway update-t1 app-t1 --description "App tier gateway" --dry-run
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `gateway_id` | Yes | - | Tier-1 gateway ID |
| `--route-advertisement` | No | - | Updated route advertisement types |
| `--description` | No | - | New description |
| `--tags` | No | - | New tags |
| `--dry-run` | No | `false` | Preview without executing |

### `gateway delete-t1`

Delete a Tier-1 gateway.

```bash
vmware-nsx gateway delete-t1 app-t1
vmware-nsx gateway delete-t1 app-t1 --dry-run
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `gateway_id` | Yes | - | Tier-1 gateway ID |
| `--force` | No | `false` | Skip connected-segment check |
| `--dry-run` | No | `false` | Preview without executing |

**Safety**: Requires double confirmation. Checks for connected segments before deletion.

### `gateway routes-t1`

Get the Tier-1 routing table.

```bash
vmware-nsx gateway routes-t1 app-t1
```

| Argument | Required | Description |
|----------|:--------:|-------------|
| `gateway_id` | Yes | Tier-1 gateway ID |

---

## NAT Commands

### `nat list`

List NAT rules on a gateway.

```bash
vmware-nsx nat list app-t1
vmware-nsx nat list tier0-gw
```

| Argument | Required | Description |
|----------|:--------:|-------------|
| `gateway_id` | Yes | Gateway ID (Tier-0 or Tier-1) |

Output columns: Rule ID, Action (SNAT/DNAT/REFLEXIVE/NO_SNAT/NO_DNAT), Source Network, Destination Network, Translated Address, Enabled, Logging.

### `nat get`

Get NAT rule details.

```bash
vmware-nsx nat get app-t1 rule-01
```

| Argument | Required | Description |
|----------|:--------:|-------------|
| `gateway_id` | Yes | Gateway ID |
| `rule_id` | Yes | NAT rule ID |

### `nat create`

Create a NAT rule on a gateway.

```bash
# SNAT — all traffic from 10.10.1.0/24 appears as 172.16.0.10
vmware-nsx nat create app-t1 \
  --action SNAT \
  --source 10.10.1.0/24 \
  --translated 172.16.0.10

# DNAT — external 172.16.0.20:443 maps to internal 10.10.1.5:443
vmware-nsx nat create app-t1 \
  --action DNAT \
  --destination 172.16.0.20 \
  --translated 10.10.1.5 \
  --service TCP:443 \
  --dry-run
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `gateway_id` | Yes | - | Gateway ID |
| `--action` | Yes | - | `SNAT`, `DNAT`, `REFLEXIVE`, `NO_SNAT`, `NO_DNAT` |
| `--source` | No | - | Source network CIDR |
| `--destination` | No | - | Destination network CIDR |
| `--translated` | Yes | - | Translated IP address or CIDR |
| `--service` | No | - | Service (e.g., `TCP:443`, `UDP:53`) |
| `--rule-id` | No | auto | Custom rule ID |
| `--enabled` | No | `true` | Enable the rule |
| `--logging` | No | `false` | Enable logging |
| `--priority` | No | `100` | Rule priority (lower = higher priority) |
| `--dry-run` | No | `false` | Preview without executing |

**Safety**: Requires double confirmation. Gateway existence verified. CIDR and IP address formats validated.

### `nat update`

Update an existing NAT rule.

```bash
vmware-nsx nat update app-t1 rule-01 --translated 172.16.0.11
vmware-nsx nat update app-t1 rule-01 --enabled false --dry-run
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `gateway_id` | Yes | - | Gateway ID |
| `rule_id` | Yes | - | NAT rule ID |
| `--translated` | No | - | New translated address |
| `--enabled` | No | - | Enable or disable |
| `--logging` | No | - | Enable or disable logging |
| `--priority` | No | - | New priority |
| `--dry-run` | No | `false` | Preview without executing |

### `nat delete`

Delete a NAT rule.

```bash
vmware-nsx nat delete app-t1 rule-01
vmware-nsx nat delete app-t1 rule-01 --dry-run
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `gateway_id` | Yes | - | Gateway ID |
| `rule_id` | Yes | - | NAT rule ID |
| `--dry-run` | No | `false` | Preview without executing |

**Safety**: Requires double confirmation.

---

## Static Route Commands

### `route list`

List static routes on a gateway.

```bash
vmware-nsx route list app-t1
vmware-nsx route list tier0-gw
```

| Argument | Required | Description |
|----------|:--------:|-------------|
| `gateway_id` | Yes | Gateway ID (Tier-0 or Tier-1) |

Output columns: Route ID, Network, Next Hop(s), Admin Distance.

### `route create`

Add a static route.

```bash
vmware-nsx route create app-t1 \
  --network 192.168.100.0/24 \
  --next-hop 10.10.1.254

vmware-nsx route create app-t1 \
  --network 0.0.0.0/0 \
  --next-hop 10.10.1.1 \
  --admin-distance 10 \
  --dry-run
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `gateway_id` | Yes | - | Gateway ID |
| `--network` | Yes | - | Destination network CIDR |
| `--next-hop` | Yes | - | Next-hop IP address |
| `--admin-distance` | No | `1` | Administrative distance |
| `--route-id` | No | auto | Custom route ID |
| `--dry-run` | No | `false` | Preview without executing |

**Safety**: Requires double confirmation. CIDR and IP validated.

### `route delete`

Remove a static route.

```bash
vmware-nsx route delete app-t1 route-01
vmware-nsx route delete app-t1 route-01 --dry-run
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `gateway_id` | Yes | - | Gateway ID |
| `route_id` | Yes | - | Static route ID |
| `--dry-run` | No | `false` | Preview without executing |

---

## IP Pool Commands

### `ippool list`

List all IP address pools.

```bash
vmware-nsx ippool list
```

Output columns: Pool ID, Display Name, Subnets, Total IPs, Allocated, Free.

### `ippool allocations`

Show allocated IP addresses from a pool.

```bash
vmware-nsx ippool allocations pool-01
```

| Argument | Required | Description |
|----------|:--------:|-------------|
| `pool_id` | Yes | IP pool ID |

Output: JSON array with `allocation_id`, `ip_address`, `intent_path` (consumer).

### `ippool create`

Create a new IP address pool.

```bash
vmware-nsx ippool create tep-pool --description "TEP IP pool"
vmware-nsx ippool create tep-pool --dry-run
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `name` | Yes | - | Pool ID and display name |
| `--description` | No | `""` | Description |
| `--dry-run` | No | `false` | Preview without executing |

### `ippool add-subnet`

Add a subnet range to an IP pool.

```bash
vmware-nsx ippool add-subnet tep-pool \
  --start 192.168.100.10 \
  --end 192.168.100.50 \
  --cidr 192.168.100.0/24 \
  --gateway 192.168.100.1

vmware-nsx ippool add-subnet tep-pool \
  --start 192.168.100.10 \
  --end 192.168.100.50 \
  --cidr 192.168.100.0/24 \
  --dry-run
```

| Argument/Option | Required | Default | Description |
|-----------------|:--------:|---------|-------------|
| `pool_id` | Yes | - | IP pool ID |
| `--start` | Yes | - | Range start IP |
| `--end` | Yes | - | Range end IP |
| `--cidr` | Yes | - | Subnet CIDR |
| `--gateway` | No | - | Default gateway for the subnet |
| `--dry-run` | No | `false` | Preview without executing |

**Safety**: IP range validated (start < end, both within CIDR).

---

## Health Commands

### `health alarms`

List active NSX alarms.

```bash
vmware-nsx health alarms
vmware-nsx health alarms --severity CRITICAL
vmware-nsx health alarms --severity HIGH
```

| Option | Required | Default | Description |
|--------|:--------:|---------|-------------|
| `--severity` | No | all | Filter by severity: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` |

Output columns: Alarm ID, Severity, Feature, Entity, Description, Last Reported.

### `health transport-nodes`

Show transport node connectivity and configuration status.

```bash
vmware-nsx health transport-nodes
```

Output columns: Node Name, Node Type (HOST/EDGE), Status (UP/DOWN/DEGRADED), Control Connectivity, Management Connectivity, Tunnel Status.

### `health edge-clusters`

Show edge cluster member status.

```bash
vmware-nsx health edge-clusters
```

Output columns: Cluster Name, Member Count, Members (name + status), Allocation Profile, Failover Mode.

### `health manager-status`

Show NSX Manager cluster health.

```bash
vmware-nsx health manager-status
```

Output: JSON with `cluster_id`, `overall_status`, `nodes` (each with `fqdn`, `status`, `role` — MANAGER/POLICY/CONTROLLER), `mgmt_cluster_status`, `control_cluster_status`.

---

## Troubleshooting Commands

### `troubleshoot port-status`

Get logical port admin and operational status.

```bash
vmware-nsx troubleshoot port-status <port-id>
```

| Argument | Required | Description |
|----------|:--------:|-------------|
| `port_id` | Yes | Logical port ID (from `segment ports` output) |

Output: JSON with `admin_state`, `operational_status`, `link_state`, `attachment`, `address_bindings`, `realized_state`.

### `troubleshoot vm-segment`

Find which segment(s) a VM is connected to.

```bash
vmware-nsx troubleshoot vm-segment my-vm-01
vmware-nsx troubleshoot vm-segment "Web Server 01"
```

| Argument | Required | Description |
|----------|:--------:|-------------|
| `vm_name` | Yes | VM name (searched by display name, case-insensitive) |

Output: JSON array with `vm_name`, `vnic`, `segment_id`, `segment_name`, `ip_addresses`, `mac_address`, `port_id`.

---

## Diagnostics

### `doctor`

Run environment and connectivity diagnostics.

```bash
vmware-nsx doctor
vmware-nsx doctor --skip-auth
```

| Option | Description |
|--------|-------------|
| `--skip-auth` | Skip the NSX Manager authentication check (useful when NSX Manager is unreachable) |

Checks performed:
1. Config file exists (`~/.vmware-nsx/config.yaml`)
2. `.env` file exists with correct permissions (600)
3. Targets are configured in config
4. Network connectivity to all targets (TCP port check with 5s timeout)
5. NSX Manager authentication (actual login via REST API)
6. MCP server module loads successfully

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Operation failed or doctor check failed |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VMWARE_NSX_CONFIG` | Override config file path (used by MCP server) |
| `VMWARE_<TARGET>_PASSWORD` | Password for a target (e.g., `VMWARE_NSX_PROD_PASSWORD`) |
