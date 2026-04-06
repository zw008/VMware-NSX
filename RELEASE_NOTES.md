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
