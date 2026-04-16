## v1.5.11 (2026-04-17)

- Align with VMware skill family v1.5.11 (AVI 22.x fixes from @timwangbc)

## v1.5.10 (2026-04-16)

- Security: bump python-multipart 0.0.22→0.0.26 (DoS via large multipart preamble/epilogue)
- Align with VMware skill family v1.5.10

## v1.5.8 (2026-04-15)

- Fix: CRITICAL — 9 MCP tools imported non-existent ops modules (`gateway_mgmt`, `nat_mgmt`, `route_mgmt`, `ip_pool_mgmt`) causing `ModuleNotFoundError` at runtime. Corrected to `segment_mgmt` (gateway functions) and `nat_route_mgmt` (NAT/route/IP pool functions). Tools affected: create/update/delete_tier1_gateway, configure_tier0_bgp, create/delete_nat_rule, create/delete_static_route, create_ip_pool.
- Fix: `configure_tier0_bgp` signature mismatch — MCP layer passed individual BGP neighbor params but ops expects `(client, tier0_id, locale_service_id, bgp_config dict)`. Rewrote MCP signature to match ops contract (local_as_num, enabled, ecmp, inter_sr_ibgp, locale_service_id).
- Fix: SSL warning suppression scope — replaced process-global `warnings.filterwarnings()` with class-targeted `urllib3.disable_warnings(InsecureRequestWarning)`, which no longer accidentally suppresses SSL warnings from other libraries in the same process.
- Align with VMware skill family v1.5.8

## v1.5.7 (2026-04-15)

- Align with VMware skill family v1.5.7 (Pilot `__from_step_N__` fix + VKS SSL/timeout fix)

## v1.5.6 (2026-04-15)

- Align with VMware skill family v1.5.6 (AVI bugfixes + packaging hotfix)

## v1.5.5 (2026-04-15)

- Fix: CRITICAL — missing `import re` in `ops/segment_mgmt.py` and `ops/nat_route_mgmt.py` caused `NameError: name 're' is not defined` at runtime for all segment/NAT/route CRUD operations
- Align with VMware skill family v1.5.5

## v1.5.4 (2026-04-14)

- Fix: CLI `segment create` TypeError — `subnet` (string) was passed to `create_segment()` which expects `subnets` (list of dicts); also parse `vlan_ids` string to `list[int]`
- Fix: CLI `segment update` ValueError — same `subnet` vs `subnets` mismatch in `update_segment()`
- Fix: CLI `health alarms` ImportError — `list_nsx_alarms` renamed to `list_alarms` in ops layer
- Fix: CLI `health manager-status` ImportError — `get_nsx_manager_status` renamed to `get_manager_status` in ops layer
- Fix: MCP server had identical mismatches for all four above (segment create/update, alarms, manager-status)
- Ref: https://github.com/zw008/VMware-NSX/issues/3

## v1.5.0 (2026-04-12)

### Anthropic Best Practices Integration

- **[READ]/[WRITE] tool prefixes**: All MCP tool descriptions now start with [READ] or [WRITE] to clearly indicate operation type
- **Read/write split counts**: SKILL.md MCP Tools section header shows exact read vs write tool counts
- **Negative routing**: Description frontmatter includes "Do NOT use when..." clause to prevent misrouting
- **Broadcom author attestation**: README.md, README-CN.md, and pyproject.toml include VMware by Broadcom author identity (wei-wz.zhou@broadcom.com) to resolve Snyk E005 brand warnings

## v1.4.9 (2026-04-11)

- Fix: 403 auth failure for NSX passwords containing special chars (!, ), etc.)
  Switch /api/session/create from Basic Auth header to form-body credentials
  (j_username/j_password) matching curl behavior; preserve special chars
  unencoded using urllib.parse.quote safe-set to avoid NSX decoding issues.

## v1.4.8 (2026-04-09)

- Security: bump cryptography 46.0.6→46.0.7 (CVE-2026-39892, buffer overflow)
- Security: bump urllib3 2.3.0→2.6.3 (multiple CVEs) [VMware-VKS]
- Security: bump requests 2.32.5→2.33.0 (medium CVE) [VMware-VKS]

## v1.4.7 (2026-04-08)

- Fix: align openclaw metadata with actual runtime requirements
- Fix: standardize audit log path to ~/.vmware/audit.db across all docs
- Fix: update credential env var docs to correct VMWARE_<TARGET>_PASSWORD convention
- Fix: declare .env config and vmware-policy optional dependency in metadata

# Release Notes


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.4.5 — 2026-04-03

- **Security**: bump pygments 2.19.2 → 2.20.0 (fix ReDoS CVE in GUID matching regex)
- **Infrastructure**: add uv.lock for reproducible builds and Dependabot security tracking


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.4.0 — 2026-03-29

### Architecture: Unified Audit & Policy

- **vmware-policy integration**: All MCP tools now wrapped with `@vmware_tool` decorator
- **Unified audit logging**: Operations logged to `~/.vmware/audit.db` (SQLite WAL), replacing per-skill JSON Lines logs
- **Policy enforcement**: `check_allowed()` with rules.yaml, maintenance windows, risk-level gating
- **Sanitize consolidation**: Replaced local `_sanitize()` with shared `vmware_policy.sanitize()`
- **Risk classification**: Each tool tagged with risk_level (low/medium/high) for confirmation gating
- **Agent detection**: Audit logs identify calling agent (Claude/Codex/local)
- **New family members**: vmware-policy (audit/policy infrastructure) + vmware-pilot (workflow orchestration)


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.3.1 — 2026-03-27

### Family expansion: NSX-Security, Aria + hub entry point

- Added vmware-nsx-security and vmware-aria to companion skills routing table
- README updated with complete 7-skill family table
- vmware-aiops is now the family entry point (`vmware-aiops hub status`)


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.3.0 — 2026-03-26

### Initial release

- 31 MCP tools: 18 read-only + 13 write operations
- Network inventory: segments, Tier-0/Tier-1 gateways, transport zones/nodes, edge clusters
- Networking: NAT rules, BGP neighbors, static routes, IP pools
- Health: NSX alarms, transport node status, edge cluster status, manager status
- Troubleshooting: logical port status, VM-to-segment lookup
- Write operations: segment/gateway CRUD, NAT/route management, IP pool creation
- Safety: double confirmation + dry-run + audit logging on all write operations
- SKILL.md with progressive disclosure (Anthropic best practices)
- CLI (`vmware-nsx`) with typer — segment/gateway/nat/route/ippool/health/troubleshoot subcommands
- MCP server (31 tools) via stdio transport
- Docker one-command launch
- `vmware-nsx doctor` — 6-check environment diagnostics
- Audit logging (JSON Lines) for all operations
- references/: cli-reference.md, capabilities.md, setup-guide.md
- examples/mcp-configs/: 7 agent config templates (Claude Code, Cursor, Goose, Continue, LocalCowork, mcp-agent, VS Code Copilot)
- README.md and README-CN.md with Companion Skills, Workflows, Troubleshooting

**PyPI**: `uv tool install vmware-nsx-mgmt==1.3.0`
