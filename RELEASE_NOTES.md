# Release Notes

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
