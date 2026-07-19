## v1.8.0 (2026-07-18) — read-only mode, working policy defaults, declared environments

Family release driven by [VMware-AIops#31](https://github.com/zw008/VMware-AIops/issues/31),
where an operator running Llama 3.3 70B (Goose / OpenShift AI, on-prem H100) had to
hand-write 17 prompt guardrails to make tool calling reliable. A prompt is advisory — a
model can ignore it. Every guardrail that could move into the harness has.

### Added
- **Read-only mode.** Set `VMWARE_READ_ONLY=true` (or `VMWARE_<SKILL>_READ_ONLY`, or
  `read_only: true` in config.yaml) and every write tool is removed from the MCP registry
  at start-up. `list_tools()` never offers them, so the model cannot call what it cannot
  see. **Off by default** — nothing changes unless you turn it on. Fail-closed: if the
  mode is requested but cannot be guaranteed, the server refuses to start rather than
  running open.
- **`environment:` on each config target**, declaring which environment it is
  (production / staging / lab). Policy rules scope by this value.

### Added — list results now state whether they are complete

Every `[READ]` list tool returns the family envelope instead of a bare array:

    {"items": [...], "returned": 50, "limit": 50, "total": 213,
     "truncated": true, "hint": "Showing 50 of 213. Raise limit or narrow the query..."}

This closes the reported failure where long responses were summarised as "no data
returned": a bare list gives a model no way to tell a complete answer from page one, so
it guessed. `truncated: false` now positively states completeness — including when
`items` is empty, which means "checked, found none", not "the call failed".

- **10 tool(s) converted** across ops, MCP and CLI. All ten carry a real `total`, read from the ListResult `result_count` the client
  already fetched — no extra round trip. `list_nsx_alarms` reads complete except when
  the 1000-item client backstop cut the walk short, which is exactly when an agent must
  not treat it as the whole alarm picture.

### Changed — migration, read this
- **Approval tiers now actually run.** They shipped in v1.6.0 but the engine only ever
  read `~/.vmware/rules.yaml`, and a fresh install has no such file — so every deny rule,
  maintenance window and approval tier had been inert on every install that never
  hand-authored one. A packaged baseline now loads when you have written no rules of your
  own. Writes at medium risk and above are stamped with their tier in the audit log;
  irreversible work and guest execution against a target declared `production` require a
  named approver via `VMWARE_AUDIT_APPROVED_BY`.
- **`environment:` will become required for writes.** Today a state-changing operation
  against a target that declares none still runs and logs a warning. **The next major
  release refuses it.** Declare it now and that upgrade is a no-op:

      targets:
        prod-vc01:
          host: vc01.corp.local
          environment: production

  Read-only operations are never affected, in this release or the next. Check what applies
  to your targets before upgrading: `vmware-audit policy --operation vm_delete --env <env>`.

### Fixed
- **Policy glob patterns with a leading wildcard silently matched nothing.** A rule written
  `operations: ["*_delete"]` parsed fine, read correctly, and never fired — only a trailing
  `*` was honoured. Now full glob matching, for operations and environments alike.
- Config-path overrides (`VMWARE_<SKILL>_CONFIG`) are honoured when reading `read_only`
  and `environment`, so a setting in a custom config file is no longer silently ignored.

### Notes
- Requires `vmware-policy>=1.8.0`; publish that package first.
- `vmware-audit policy` reports which rules are in force and where they came from —
  including the case where your rules file exists but failed to parse, which previously
  looked identical to "policy is working".

## v1.7.5 (2026-07-13) — internal dead-code cleanup + family version alignment

### Internal
- Removed unused `import os` (doctor) and an unused assignment in the segment
  CLI. No behavior change; MCP tool surface unchanged (33).

## v1.7.4 (2026-07-13) — family version alignment

## v1.7.3 (2026-07-03) — family version alignment

## v1.7.2 (2026-07-02) — list pagination + port-status N+1

### Changed
- **List operations now default to at most 50 items** (previously drained up to
  1000 into agent context) and report the true total via a lightweight count
  probe. `get_all` gained optional `page_size` / `limit`; MCP/CLI signatures are
  unchanged (callers pick up the 50-item default).

### Fixed
- **Port-status & segment-scan round-trip storms.** `get_logical_port_status`
  issued a per-port `/state` GET (up to 51 round-trips per call); the segment-port
  fallback scanned every segment in the estate. Port status is now bounded to
  ≤50 ports, and the fallback is capped at 200 segments with a truncation warning
  (the Policy Search API path is preferred and unchanged).

## v1.7.1 (2026-07-02) — family version alignment

No code changes. Version bump to stay aligned with the v1.7.1 family release
(VMware-AIops + VMware-Monitor large-inventory scale fix — PropertyCollector
batching to stop per-object lazy SOAP round-trips, GitHub issue #31).

## v1.7.0 (2026-06-27) — guided onboarding + teaching auth errors

### Added
- **`vmware-nsx init` — interactive first-run setup wizard.** Prompts for host /
  username / password and writes `config.yaml` + `.env` for you. The password is
  stored grep-safe (`b64:`, never plaintext on disk) and `.env` is locked to
  0600, then the connection is verified. Replaces the manual "mkdir + cp
  config.example.yaml + edit YAML + chmod 600" dance.
- `.env.example` added documenting the per-target password var.

### Changed
- `doctor` now points to `vmware-nsx init` when config/credentials are missing
  (previously suggested a command that did not exist), keeping the manual steps
  as a fallback.
- Authentication and TLS failures now print a teaching message naming the exact
  file and env var to fix (`~/.vmware-nsx/.env` password var, `config.yaml`
  username) plus a `verify_ssl: false` hint for self-signed labs.
- Auth teaching reaffirms special-character passwords are sent via form-body.

## v1.6.1 (2026-06-24)

### Added
- **`.env` passwords are auto-obfuscated to a grep-safe `b64:` form** on first
  load and decoded transparently at runtime — plaintext no longer sits in
  `~/.<skill>/.env` for a casual `grep` to find. Values are read/written through
  python-dotenv's own parser, so the stored secret never drifts from the
  configured one (handles quotes, inline comments, trailing whitespace, and a
  password that literally starts with `b64:`). **Obfuscation, not encryption** —
  for real at-rest secrecy, inject the password from a secret manager instead of
  storing `.env`. New regression suite (10 cases) covers dotenv parity, the
  `b64:`-prefixed edge case, idempotency, and 0600 preservation.

## v1.6.0 (2026-06-22) — trust architecture: undo tokens

### Added
- **Undo-token recording** on create tools (vmware-policy 1.6.0): `create_segment`→`delete_segment`,
  `create_tier1_gateway`→`delete_tier1_gateway`, `create_nat_rule`→`delete_nat_rule`,
  `create_static_route`→`delete_static_route`, `create_ip_pool`→`delete_ip_pool`.
- Inherits harness budget guard, audit accountability fields, and graduated risk tiers.

### Changed
- Requires **vmware-policy >= 1.6.0**.

## v1.5.39 (2026-06-22) — family version alignment

No code changes. Version bump to stay aligned with the v1.5.39 family release
(AIops snapshot-delete async + honest-timeout token-burn fix; Storage datastore-browse timeout fix).

## v1.5.38 (2026-06-12) — backlog finish: cli/server split

### Changed
- Split the oversized `cli.py` (1334 lines) and `mcp_server/server.py` into `cli/*` and
  `mcp_server/tools/*` packages, all under the 800-line cap. Behavior-preserving — 33 tools and 38 CLI
  commands byte-for-byte identical; lazy-import `--help` speed (踩坑 #27) preserved. (#12)

## v1.5.37 (2026-06-12) — backlog: IP-pool lifecycle, tier-0 routes, faster VM lookup

### Fixed
- `create_ip_pool` reports partial state on a mid-loop subnet failure instead of leaving a silent
  half-built pool. (#8)
- VM→segment-port lookup uses the Policy search API instead of an O(segments×ports) full scan. (#11)

### Added
- `delete_ip_pool` (ops + CLI with `--dry-run`/confirm + audited MCP tool) — pools were uncreatable-then-
  unremovable despite the docstring. (#9)
- MCP static-route tools take a `gateway_type` param so Tier-0 routes work (ops already supported it). (#10)

Tool count 32 → 33 (20 read / 13 write).

## v1.5.36 (2026-06-12) — centralized HTTP error translation + SKILL.md accuracy

### Fixed
- **404/5xx no longer reach users as tracebacks (CLI) or opaque "operation failed" (MCP)** — a new
  `NsxApiError` + central `_request()` translates status codes to teaching hints, retries transient
  5xx once on GETs only, and re-auths once on 401 (a real 403 surfaces as a permission error, and
  writes are never blindly re-sent). Four delete tools no longer leak raw exception text.
- **VLAN range parsing fixed** — `segment create --vlan 100-200` created two discrete VLANs instead
  of the range; `dhcp_ranges` on a subnet are no longer silently dropped.
- **`is_alive` liveness probe uses a cheap any-role Policy-API GET** (`/policy/api/v1/infra`) instead
  of the privileged Manager-API path, so least-privilege accounts don't trigger reconnect churn.

### Changed
- SKILL.md / cli-reference regenerated from the live tool registry: **32 tools (20 read / 12 write)**,
  ~11 nonexistent tool names removed, and the false "all writes support dry-run" claim corrected
  (dry-run is CLI-only).

## v1.5.35 (2026-06-10) — security hardening: safe errors; doc accuracy

### Fixed
- **MCP tools route errors through `_safe_error()`** — full detail to the server log, a
  generic/sanitized message to the agent (no NSX response bodies / host:port leakage).
- **Silent `except: pass`** in troubleshoot now logs at debug.
- **Docs corrected**: removed the documented-but-unimplemented certificate-authentication
  section; authentication is username/password via the session-create API (form-body encoded).

This release aligns the whole family back to a single version (1.5.35); vmware-policy and vmware-pilot return to the shared number after sitting at 1.5.22.

## v1.5.32 (2026-06-08) — Response parsing fixed against official NSX 4.2 SDK + 2 CLI repairs

A family-wide spec audit found the status/troubleshooting read paths parsed
fields that don't exist on the official response models (silently returning
empty values), and two CLI commands that never worked.

### Fixed — response parsing (verified against nsx-policy/nsx SDK 4.2 models)
- Transport node status: `tunnel_status`/`pnic_status` StatusCount parsing;
  invented `node_deployment_state`/`pnic_bond_status`/`lcp_connectivity_status`
  removed; `mgmt_connection_status` is a plain string.
- Edge cluster member status via `transport_node.target_id`/`target_display_name`.
- Manager cluster: `mgmt_cluster_listen_ip_address` is a plain string.
- BGP: config fields `hold_down_time`/`keep_alive_time`; prefix counters now
  labeled `in_prefix_count`/`out_prefix_count` (were mislabeled as messages).
- Port status: SegmentPortState has no UP/DOWN field — output now reports
  attachment, realized-bindings count, and transport node IDs honestly.
- VM-to-segment lookup via `GET /api/v1/fabric/vifs?owner_vm_id=` matching
  `lport_attachment_id` (the previously read `virtual_interfaces` field
  doesn't exist — the tool always returned empty matches).
- Inventory: transport zone `host_switch_name` removed (not a Policy TZ field);
  node type from `node_deployment_info.resource_type` (HostNode/EdgeNode).
- Alarms: cursor pagination + exact-match `severity` filter exposed on CLI/MCP.

### Fixed — CLI commands that never worked
- `gateway configure-tier0-bgp` passed kwargs ops never accepted (TypeError on
  every run); reworked to the real BGP-settings capability
  (`--local-as/--enabled/--ecmp/--inter-sr-ibgp`; neighbor creation is a
  separate API and is not exposed).
- `network list-static-routes` crashed rendering next-hop dicts.

### Hardening
- REFLEXIVE NAT rules now require `translated_network`.
- `delete_tier1_gateway` removes the default locale-service first.

### Defense
- New spec-conformance regression: every API call AST-checked against 2530
  official path templates vendored from the NSX 4.2 SDKs
  (`tests/eval/spec/nsx_api_operations.json`).

## v1.5.30 (2026-06-07) — Fix 4 broken gateway/route/pool tools + tool description quality

### Fixed (critical)
Four tools were broken since their introduction — MCP wrappers and CLI commands passed
kwargs their ops functions don't accept, so every invocation failed with
TypeError/ValueError (swallowed into `{"error", "hint"}` payloads):
- `create_tier1_gateway`: passed `edge_cluster_path=`/`route_advertisement=`; now converts
  comma-separated advertisement types to `route_advertisement_types` list, and ops gained
  real `edge_cluster_path` support (creates the "default" locale-service on the gateway).
- `update_tier1_gateway`: passed `None` fields and a key rejected by ops `allowed_fields`
  (ValueError on every call); now sends only non-None fields under correct names.
- `create_static_route`: passed `next_hop=str`; now builds `next_hops=[{"ip_address": ...}]`.
- `create_ip_pool`: passed `start_ip/end_ip/cidr/gateway_ip`; now builds the
  `subnets=[{allocation_ranges, cidr, gateway_ip}]` structure ops expects.
- `get_bgp_neighbors` return annotation corrected `list[dict]` → `dict`.

Same fixes applied to the CLI commands (`gateway create-tier1`, `gateway update-tier1`,
`route create-static`, `ip-pool create`) — 踩坑 #19/#34 pattern.

### Tests
- New `tests/eval/regression/test_nsx_specific.py`: 8 tests exercising the real
  wrapper→ops path with a mocked NSX client; any future signature drift fails CI.

### Improved
- Rewrote 13 MCP tool descriptions (per-parameter formats, return fields, sibling-tool
  routing, PUT/PATCH semantics, audit disclosure) per Glama TDQS review.

## v1.5.29 (2026-05-29) — Family Version Alignment

No NSX-specific changes since v1.5.28. Bumped for family-wide v1.5.29 alignment.

## v1.5.28 (2026-05-20)

**Fix `subclass() arg 1 must be a class` in goose/old mcp environments** —
v1.5.25–1.5.27 replaced `X | None` with `Optional[X]` but kept
`from __future__ import annotations` at the top of `mcp_server/server.py`.
Under mcp 1.10–1.13 (which Goose and some sandboxes pin), `Tool.from_function`
calls `issubclass(param.annotation, Context)` without resolving forward refs,
so string annotations crash the entire server load. Removed
`from __future__ import annotations` from `mcp_server/server.py` so annotations
are real classes; verified all tools load under mcp 1.10 and 1.14.

Traceback location: `mcp/server/fastmcp/tools/base.py:67`. CLAUDE.md 踩坑 #33
updated. family_smoke.sh Check 4b now installs `mcp==1.10.0` to catch this
regression class.

## v1.5.27 (2026-05-20)

**Loosen Python requirement: now supports Python >= 3.10** — v1.5.25/26 fixed
the PEP 604 root cause in MCP tool signatures (Optional[X] instead of X | None),
but kept `requires-python = ">=3.11"` and a 3.11 hard guard in `mcp_cmd`. Both
relaxed to 3.10 so users on Python 3.10 (e.g. Goose default sandbox, Ubuntu
22.04 system python) can install and run directly without a Python upgrade.

- `pyproject.toml`: `requires-python = ">=3.10"` (was `>=3.11`; VMware-VKS
  was `>=3.12`, now also `>=3.10` for family alignment).
- `<pkg>/cli.py` `mcp_cmd()`: version guard now triggers on `< (3, 10)`.
- Behavior on Python 3.10 matches 3.11/3.12 — the Optional[X] fix from v1.5.25
  is what actually enables this; this release just stops blocking installs.

---

## v1.5.26

**Family-wide MCP server fix — Python 3.10 compatibility (踩坑 #33)** — `vmware-nsx mcp`
crashed at decorator time on Python 3.10 with `subclass() arg 1 must be a class`.
Root cause: `mcp_server/server.py` used PEP 604 `X | None` in tool signatures
plus `from __future__ import annotations`; on Python 3.10 + older mcp/pydantic
combos, `typing.get_type_hints()` evaluates `"str | None"` to a
`types.UnionType` instance, which FastMCP/Pydantic then feeds to `issubclass()`.
Reported by a goose user (qwen3.6:27, Python 3.10).

- `mcp_server/server.py`: all `X | None` → `Optional[X]`; ops layer untouched.
- `<pkg>/cli.py` `mcp_cmd()`: hard guard — exits with installation fix command
  if Python < 3.11 (defense in depth, our actual lower bound).
- `pyproject.toml`: `mcp[cli]>=1.10,<2.0` (was `>=1.0`) so uv doesn't pick
  an ancient version that has the same issubclass bug.

**Tooling — family smoke gains MCP schema-build check** — `scripts/family_smoke.sh`
new Check 4b runs `asyncio.run(mcp.list_tools())` per skill, forcing FastMCP to
build Pydantic models for every declared tool. Supports both module-level `mcp`
and `build_server()` factory patterns.

**Docs — CLAUDE.md gains 踩坑 #33 (PEP 604 / Python 3.10) and #34 (CLI/MCP exposure parity).**

---

## v1.5.24 (2026-05-19)

**Family version alignment** — no code changes in this skill. Bumped together
with VMware-AIops and VMware-VKS, which received a pyVmomi 8.x `ManagedObject`
setattr fix (踩坑 #32). `family_smoke.sh` now enforces the no-setattr rule
across all 9 skills.

## v1.5.23 (2026-05-19)

**NSX 9 / VCF 9.0 / 9.1 compatibility declared with caveats.**

- **docs:** README + `references/capabilities.md` version-compatibility tables now list NSX 9.0 / 9.1 and VCF 9.0 / 9.1 explicitly. The Policy API path used by this skill is fully supported in NSX 9.
- **docs:** Added NSX 9 caveats: (a) N-VDS removed — requires VDS 7.0+; (b) Bare-metal NSX agent removed, L2 overlay for physical servers no longer supported. Neither affects this skill's Segment/Gateway/NAT/Route/IPAM tools.
- **docs:** Added `Official Broadcom References` pointing to the [VMware NSX for Python SDK](https://developer.broadcom.com/sdks) as a future migration path (this skill currently uses raw REST requests against the Policy API — works fine in NSX 9 but may benefit from the official SDK later).
- **align:** Family v1.5.23 — all 9 skills tracking VCF 9.0 / 9.1 compatibility declaration.

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