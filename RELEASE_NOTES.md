## v1.5.22 (2026-05-08)

**Family alignment** — no source changes in this skill.

- **align:** Tracks v1.5.22 family bump driven by Smithery onboarding for vmware-avi / vmware-harden / vmware-pilot.

## v1.5.21 (2026-05-08)

**Family alignment** — no source changes in this skill.

- **deps:** Bumped `python-multipart` 0.0.26 → 0.0.27 (transitive, fixes GHSA HIGH DoS via unbounded multipart headers).
- **align:** Tracks v1.5.21 family bump driven by vmware-monitor folder_path feature (community PR #11).

## v1.5.20 (2026-05-08)

**Family alignment** — no source changes in this skill.

- **align:** Tracks v1.5.20 family bump driven by vmware-nsx-security and vmware-aria PyPI README `mcp-name:` ownership marker fix required by MCP Registry validation. Other 7 skills already had the marker; this release re-publishes them to keep the family version aligned per CLAUDE.md policy.
- **registry:** All 9 skills now registered on registry.modelcontextprotocol.io as `isLatest=true`.

## v1.5.19 (2026-05-06)

**Critical fix** — restores broken CLI subcommands for gateway / NAT / route / IP pool management.

- **fix(cli):** Corrected 9 broken imports in `vmware_nsx/cli.py`. Subcommands `gateway create-tier1 / update-tier1 / delete-tier1 / configure-tier0-bgp`, `nat create-rule / delete-rule`, `route create-static / delete-static`, and `ip-pool create` imported from non-existent modules `gateway_mgmt` / `nat_mgmt` / `route_mgmt` / `ip_pool_mgmt`. Actual functions live in `segment_mgmt.py` and `nat_route_mgmt.py`. Previously these commands raised `ModuleNotFoundError` at runtime (yjs review 2026-05-06; CLAUDE.md 踩坑 #27).
- **build:** Bumped `requires-python` from `>=3.10` to `>=3.11` (regression eval suite uses `tomllib` which is Py3.11+ builtin).
- **smoke:** Family `scripts/family_smoke.sh` now adds Check 3b — recursive `--help` on every Typer subcommand to trigger lazy imports. This is the harness change that would have caught this CLI bug before release.
- **align:** Family version bump to v1.5.19.

## v1.5.18 (2026-05-02)

**Family alignment + tooling normalization** — no source changes in this skill.

- **dev:** Added `[dependency-groups] dev` block (PEP 735) so `uv sync --group dev` works. Canonical set: `pytest>=8.0,<10.0`, `pytest-cov`, `ruff`.
- **test:** New `tests/eval/regression/test_release_blockers.py` (5 evals) catches the v1.5.x release blockers — missing `mcp_server` in wheel, AST-detected unimported runtime names (the v1.5.5 NSX `import re` incident is now caught at test time), Typer app load failure, module import errors. Run via `pytest tests/eval/regression/`.
- **note:** A separate cross-skill smoke check verifies that NSX and NSX-Security stay in sync on the form-body auth pattern (v1.4.9 special-character-password fix), so the v1.5.5 sync drift can't recur silently.
- **align:** Family version bump to v1.5.18.

## v1.5.17 (2026-05-01)

**Family alignment** — no source changes in this skill.

This release tracks vmware-pilot v1.5.17 (new `investigate_alert` template + `review_workflow` MCP tool + `parallel_group` step type) and vmware-policy v1.5.17 (L5 pattern matcher integrated into `@vmware_tool`). Both work with the existing skill MCP surface unchanged.

- **align:** Family version bump to v1.5.17.

## v1.5.16 (2026-04-30)

**Enterprise Harness Engineering alignment** — adapted from the Linkloud × addxai framework articles ([part 1](https://mp.weixin.qq.com/s/hz4W7ILHJ1yz_pG0Z1xP-A), [part 2](https://mp.weixin.qq.com/s/F3qYbyB3S8oIqx-Y4BrWNQ)).

- **docs:** "Automation Level Reference" section in `references/capabilities.md` — every tool tagged L1-L5 per the EHE framework.
- **docs:** Common Workflows in `SKILL.md` rewritten with pre-flight judgment (subnet conflict / edge cluster capacity / T0 uplink / NAT IP) and three-layer connectivity troubleshooting framework.
- **align:** Family version bump to v1.5.16.

## v1.5.15 (2026-04-29)

**UX improvements from real user feedback**

- **feat:** New top-level CLI subcommand `vmware-nsx mcp` starts the MCP server. Single command after `uv tool install vmware-nsx-mgmt` — no more `uvx --from`, no PyPI re-resolve, no TLS-proxy issues.
- **feat:** Default `verify_ssl: true` on new targets (was `false`). NSX Manager with default self-signed certs requires explicit `verify_ssl: false` in `config.yaml`.
- **docs:** README, SKILL.md, setup-guide.md, and `examples/mcp-configs/*.json` switched to `command: "vmware-nsx"`, `args: ["mcp"]`. uvx form to fallback with TLS-proxy troubleshooting note.
- **compat:** Legacy `vmware-nsx-mcp` console script kept — existing user configs continue to work.

## v1.5.14 (2026-04-21)

- Align with VMware skill family v1.5.14 (code review follow-up fixes by @yjs-2026)

## v1.5.13 (2026-04-21)

- Align with VMware skill family v1.5.13 (code review bug fixes)

## v1.5.12 (2026-04-17)

- Align with VMware skill family v1.5.12 (security & bug fixes from code review by @yjs-2026)

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