# Capabilities

Detailed capability reference for `vmware-nsx`.

## API Coverage

vmware-nsx uses the **NSX Policy API** (not the Management API) for all operations. The Policy API provides a declarative, intent-based interface that is the recommended path for NSX-T 3.x and NSX 4.x.

### Policy API vs Management API

| Aspect | Policy API (used by this skill) | Management API (not used) |
|--------|--------------------------------|--------------------------|
| Endpoint prefix | `/policy/api/v1/` | `/api/v1/` |
| Model | Declarative, intent-based | Imperative, realized-state |
| Object IDs | User-defined string IDs | System-generated UUIDs |
| Hierarchy | Infra → Tier-0 → Tier-1 → Segment | Flat namespace |
| Transaction support | Hierarchical API (PATCH entire tree) | Individual API calls |
| Recommended by VMware | Yes (primary API since NSX-T 3.0) | Deprecated for new development |

**Why Policy API?** The Policy API allows setting desired state declaratively. NSX Manager reconciles realized state automatically. This is safer for automation — you describe what you want, NSX figures out how to get there.

## Tool Capabilities by Category

### Segments (6 tools)

| Capability | Tool | API Endpoint | Method |
|------------|------|-------------|--------|
| List all segments | `list_segments` | `/policy/api/v1/infra/segments` | GET |
| Get segment details | `get_segment` | `/policy/api/v1/infra/segments/{id}` | GET |
| Create segment | `create_segment` | `/policy/api/v1/infra/segments/{id}` | PUT |
| Update segment | `update_segment` | `/policy/api/v1/infra/segments/{id}` | PATCH |
| Delete segment | `delete_segment` | `/policy/api/v1/infra/segments/{id}` | DELETE |
| List segment ports | `list_segment_ports` | `/policy/api/v1/infra/segments/{id}/ports` | GET |

**Segment types supported**:
- Overlay segments (Geneve encapsulation, requires overlay transport zone)
- VLAN-backed segments (requires VLAN transport zone + VLAN ID)

**Segment features**:
- Subnet configuration (gateway CIDR)
- DHCP configuration (static bindings, relay)
- Connectivity to Tier-1 gateways
- Tags and metadata
- Admin state management

### Tier-0 Gateways (4 tools)

| Capability | Tool | API Endpoint | Method |
|------------|------|-------------|--------|
| List Tier-0 gateways | `list_tier0_gateways` | `/policy/api/v1/infra/tier-0s` | GET |
| Get Tier-0 details | `get_tier0_gateway` | `/policy/api/v1/infra/tier-0s/{id}` | GET |
| BGP neighbors | `get_tier0_bgp_neighbors` | `/policy/api/v1/infra/tier-0s/{id}/locale-services/{ls}/bgp/neighbors/status` | GET |
| Route table | `get_tier0_route_table` | `/policy/api/v1/infra/tier-0s/{id}/routing-table` | GET |

**Note**: This skill provides read-only access to Tier-0 gateways. Tier-0 creation/modification is a high-impact infrastructure operation typically done during initial NSX deployment.

### Tier-1 Gateways (6 tools)

| Capability | Tool | API Endpoint | Method |
|------------|------|-------------|--------|
| List Tier-1 gateways | `list_tier1_gateways` | `/policy/api/v1/infra/tier-1s` | GET |
| Get Tier-1 details | `get_tier1_gateway` | `/policy/api/v1/infra/tier-1s/{id}` | GET |
| Create Tier-1 | `create_tier1_gateway` | `/policy/api/v1/infra/tier-1s/{id}` | PUT |
| Update Tier-1 | `update_tier1_gateway` | `/policy/api/v1/infra/tier-1s/{id}` | PATCH |
| Delete Tier-1 | `delete_tier1_gateway` | `/policy/api/v1/infra/tier-1s/{id}` | DELETE |
| Route table | `get_tier1_route_table` | `/policy/api/v1/infra/tier-1s/{id}/routing-table` | GET |

**Route advertisement types**:
- `TIER1_CONNECTED` — Connected subnets
- `TIER1_NAT` — NAT IP addresses
- `TIER1_STATIC_ROUTES` — Static routes
- `TIER1_LB_VIP` — Load balancer VIPs
- `TIER1_LB_SNAT` — Load balancer SNAT IPs
- `TIER1_DNS_FORWARDER_IP` — DNS forwarder IPs
- `TIER1_IPSEC_LOCAL_ENDPOINT` — IPSec local endpoints

### NAT (5 tools)

| Capability | Tool | API Endpoint | Method |
|------------|------|-------------|--------|
| List NAT rules | `list_nat_rules` | `/policy/api/v1/infra/tier-1s/{id}/nat/USER/nat-rules` | GET |
| Get NAT rule | `get_nat_rule` | `/policy/api/v1/infra/tier-1s/{id}/nat/USER/nat-rules/{rule}` | GET |
| Create NAT rule | `create_nat_rule` | `/policy/api/v1/infra/tier-1s/{id}/nat/USER/nat-rules/{rule}` | PUT |
| Update NAT rule | `update_nat_rule` | `/policy/api/v1/infra/tier-1s/{id}/nat/USER/nat-rules/{rule}` | PATCH |
| Delete NAT rule | `delete_nat_rule` | `/policy/api/v1/infra/tier-1s/{id}/nat/USER/nat-rules/{rule}` | DELETE |

**NAT action types**:
- `SNAT` — Source NAT (outbound traffic)
- `DNAT` — Destination NAT (inbound traffic)
- `REFLEXIVE` — Stateless bidirectional NAT
- `NO_SNAT` — Exempt from SNAT
- `NO_DNAT` — Exempt from DNAT

**NAT also works on Tier-0**: Replace `tier-1s` with `tier-0s` in the API path. The CLI and MCP tools detect gateway type automatically.

### Static Routes (3 tools)

| Capability | Tool | API Endpoint | Method |
|------------|------|-------------|--------|
| List static routes | `list_static_routes` | `/policy/api/v1/infra/tier-{0,1}s/{id}/static-routes` | GET |
| Create static route | `create_static_route` | `/policy/api/v1/infra/tier-{0,1}s/{id}/static-routes/{route}` | PUT |
| Delete static route | `delete_static_route` | `/policy/api/v1/infra/tier-{0,1}s/{id}/static-routes/{route}` | DELETE |

### IP Pools (4 tools)

| Capability | Tool | API Endpoint | Method |
|------------|------|-------------|--------|
| List pools | `list_ip_pools` | `/policy/api/v1/infra/ip-pools` | GET |
| Get allocations | `get_ip_pool_allocations` | `/policy/api/v1/infra/ip-pools/{id}/ip-allocations` | GET |
| Create pool | `create_ip_pool` | `/policy/api/v1/infra/ip-pools/{id}` | PUT |
| Create subnet | `create_ip_pool_subnet` | `/policy/api/v1/infra/ip-pools/{id}/ip-subnets/{subnet}` | PUT |

**IP pool use cases**:
- TEP (Tunnel Endpoint) IP assignment
- SNAT IP pool for gateways
- Load balancer VIP pools
- Custom automation IP management

### Health & Troubleshooting (6 tools)

| Capability | Tool | API Endpoint | Method |
|------------|------|-------------|--------|
| NSX alarms | `get_nsx_alarms` | `/api/v1/alarms` | GET |
| Transport node status | `get_transport_node_status` | `/api/v1/transport-nodes/status` | GET |
| Edge cluster status | `get_edge_cluster_status` | `/api/v1/edge-clusters/status` | GET |
| Manager cluster status | `get_manager_cluster_status` | `/api/v1/cluster/status` | GET |
| Logical port status | `get_logical_port_status` | `/api/v1/logical-ports/{id}/status` | GET |
| VM-to-segment lookup | `find_vm_segment` | `/policy/api/v1/infra/realized-state/virtual-machines` + `/policy/api/v1/infra/segments` | GET |

**Note**: Health and troubleshooting tools use a mix of Policy API and Management API endpoints. The Management API is used where the Policy API does not yet expose equivalent realized-state or status information (alarms, transport node status, logical port status).

## NSX Version Compatibility

| NSX Version | Support Level | Notes |
|-------------|--------------|-------|
| NSX 4.2.x | Full | Latest, all features supported |
| NSX 4.1.x | Full | All features supported |
| NSX 4.0.x | Full | Policy API v1 fully available |
| NSX-T 3.2.x | Full | Policy API mature, all features work |
| NSX-T 3.1.x | Full | Minor differences in route table API response format |
| NSX-T 3.0.x | Compatible | IP pool subnet API introduced here; older formats handled |
| NSX-T 2.5.x | Limited | Policy API available but incomplete; some tools may fail |
| NSX-V (6.x) | Not supported | Completely different API (SOAP-based). Use legacy tools |

### VCF (VMware Cloud Foundation) Compatibility

| VCF Version | Bundled NSX | Support |
|-------------|-------------|---------|
| VCF 5.2 | NSX 4.2.x | Full |
| VCF 5.1 | NSX 4.1.x | Full |
| VCF 5.0 | NSX 4.0.x | Full |
| VCF 4.5 | NSX-T 3.2.x | Full |
| VCF 4.4 | NSX-T 3.2.x | Full |
| VCF 4.3 | NSX-T 3.1.x | Full |

## Scope Boundaries

### What This Skill Does

- Network infrastructure: segments, gateways, routing, NAT, IPAM
- Network health: alarms, transport nodes, edge clusters, manager status
- Network troubleshooting: port status, VM-to-segment mapping

### What This Skill Does NOT Do

| Capability | Responsible Skill |
|------------|-------------------|
| Distributed Firewall (DFW) rules | `vmware-nsx-security` |
| Security groups and policies | `vmware-nsx-security` |
| IDS/IPS configuration | `vmware-nsx-security` |
| URL filtering | `vmware-nsx-security` |
| Service insertion / east-west security | `vmware-nsx-security` |
| VM lifecycle (power, deploy, guest ops) | `vmware-aiops` |
| vSphere inventory and health | `vmware-monitor` |
| Storage (datastores, iSCSI, vSAN) | `vmware-storage` |
| Tanzu Kubernetes | `vmware-vks` |
| Load balancing | Future skill or NSX ALB |
| VPN (IPSec / L2VPN) | Future skill |
| NSX Intelligence / Network Detection and Response | Future skill |

## Rate Limiting and Pagination

- NSX Policy API supports pagination via `cursor` and `page_size` parameters
- Default page size: 1000 objects (configurable)
- List operations automatically paginate through all results
- NSX Manager has built-in rate limiting; the skill respects `429 Too Many Requests` responses with automatic backoff
- Recommendation: for environments with >500 segments or >200 gateways, use targeted `get` operations instead of `list`

## Authentication

The skill authenticates to NSX Manager using HTTP Basic Authentication over HTTPS. This is the standard authentication method for the NSX Policy API.

**Supported authentication methods**:
- Local NSX Manager credentials (admin user)
- vIDM-backed credentials (when NSX Manager is integrated with Identity Manager)
- Principal Identity certificates (configure `cert_path` and `key_path` in config.yaml instead of password)

**Session management**: Each API call creates an independent HTTPS request with Basic Auth headers. No persistent sessions are maintained, which simplifies connection pooling and avoids session timeout issues.
