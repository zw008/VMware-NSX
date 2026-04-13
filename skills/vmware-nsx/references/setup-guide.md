# Setup Guide

Complete setup and security guide for `vmware-nsx`.

## Prerequisites

- Python 3.10+
- NSX-T 3.0+ or NSX 4.x Manager
- Network access to NSX Manager on port 443 (HTTPS)
- NSX Manager credentials with appropriate role (minimum: `network_engineer` for read-only, `enterprise_admin` for write operations)

## Installation

### Via uv (recommended)

```bash
uv tool install vmware-nsx-mgmt
```

### Via pip

```bash
pip install vmware-nsx-mgmt
```

### From source

```bash
git clone https://github.com/zw008/VMware-NSX.git
cd VMware-NSX
pip install -e .
```

## Configuration

### 1. Create config directory

```bash
mkdir -p ~/.vmware-nsx
```

### 2. Create config.yaml

```bash
cp config.example.yaml ~/.vmware-nsx/config.yaml
```

Edit `~/.vmware-nsx/config.yaml`:

```yaml
targets:
  - name: nsx-prod              # Target identifier (used in CLI --target flag)
    host: nsx-mgr.example.com   # NSX Manager hostname or IP (or VIP for cluster)
    username: admin              # NSX Manager username
    port: 443
    verify_ssl: false            # Set true if using valid certs

  - name: nsx-lab
    host: 10.0.0.100
    username: admin
    port: 443
    verify_ssl: false

notify:
  webhook_url: ""                # Optional: webhook for notifications
```

The first target in the list is the default (used when `--target` is not specified).

**NSX Manager cluster**: Use the cluster VIP as the `host` value. The VIP automatically routes to the active manager node.

### 3. Create .env for credentials

Passwords are **never stored in config.yaml**. They must be set as environment variables via the `.env` file.

```bash
echo "VMWARE_NSX_PROD_PASSWORD=your_password" > ~/.vmware-nsx/.env
echo "VMWARE_NSX_LAB_PASSWORD=lab_password" >> ~/.vmware-nsx/.env
chmod 600 ~/.vmware-nsx/.env
```

**Naming convention**: `VMWARE_<TARGET_NAME_UPPER>_PASSWORD` where `<TARGET_NAME_UPPER>` is the target `name` from config.yaml, uppercased, with hyphens replaced by underscores.

Examples:
| Target name | Environment variable |
|-------------|---------------------|
| `nsx-prod` | `VMWARE_NSX_PROD_PASSWORD` |
| `nsx-lab` | `VMWARE_NSX_LAB_PASSWORD` |
| `nsx01` | `VMWARE_NSX01_PASSWORD` |

### 4. Verify setup

```bash
vmware-nsx doctor
```

This runs six checks: config file, .env file, targets, network connectivity, authentication, and MCP server module.

Use `--skip-auth` if NSX Manager is temporarily unreachable:

```bash
vmware-nsx doctor --skip-auth
```

## MCP Server Configuration

### Claude Code / Claude Desktop

Add to your MCP config (`~/.claude.json` or Claude Desktop settings):

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

### Cursor

Add to Cursor MCP settings:

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

### Goose

Add to `~/.config/goose/config.yaml`:

```yaml
extensions:
  vmware-nsx:
    type: stdio
    cmd: vmware-nsx-mcp
    env:
      VMWARE_NSX_CONFIG: "~/.vmware-nsx/config.yaml"
```

### VS Code Copilot

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "vmware-nsx": {
      "type": "stdio",
      "command": "vmware-nsx-mcp",
      "env": {
        "VMWARE_NSX_CONFIG": "~/.vmware-nsx/config.yaml"
      }
    }
  }
}
```

### Continue

Add to `~/.continue/config.yaml`:

```yaml
mcpServers:
  - name: vmware-nsx
    command: vmware-nsx-mcp
    env:
      VMWARE_NSX_CONFIG: ~/.vmware-nsx/config.yaml
```

### Docker

```bash
docker compose up -d
```

Or run manually:

```bash
docker run -d \
  -v ~/.vmware-nsx:/root/.vmware-nsx:ro \
  -e VMWARE_NSX_CONFIG=/root/.vmware-nsx/config.yaml \
  vmware-nsx
```

## Security Details

> **Disclaimer**: This is a community-maintained open-source project and is **not affiliated with, endorsed by, or sponsored by VMware, Inc. or Broadcom Inc.** "VMware" and "NSX" are trademarks of Broadcom.

### Credential Safety

- Passwords are **only loaded from environment variables** (via `.env` file), never from `config.yaml`
- The `.env` file permissions are checked at startup; a warning is logged if permissions are wider than `600` (owner read/write only)
- The `doctor` command verifies `.env` permissions and reports failures

### Certificate-Based Authentication

For environments using Principal Identity certificates instead of password authentication:

```yaml
targets:
  - name: nsx-prod
    host: nsx-mgr.example.com
    username: principal-identity-user
    cert_path: ~/.vmware-nsx/nsx-prod.pem
    key_path: ~/.vmware-nsx/nsx-prod.key
    port: 443
    verify_ssl: true
```

When `cert_path` and `key_path` are set, the password environment variable is not required for that target.

### Audit Logging

All operations are logged to `~/.vmware/audit.db` (SQLite WAL mode, via vmware-policy).

Each audit entry records:
- **timestamp**: UTC ISO 8601
- **target**: Which NSX Manager was acted on
- **operation**: What was done (e.g., `create_segment`, `delete_nat_rule`, `query`)
- **resource**: What resource was affected (segment ID, gateway ID, rule ID)
- **parameters**: Full parameter set passed to the operation
- **before_state / after_state**: State snapshots (when available)
- **result**: Operation outcome
- **user**: OS username who initiated the operation

Example audit entry:

```json
{
  "timestamp": "2026-03-26T10:30:00+00:00",
  "target": "nsx-prod",
  "operation": "create_segment",
  "resource": "app-web-seg",
  "parameters": {"name": "app-web-seg", "gateway": "app-t1", "subnet": "10.10.1.1/24", "transport_zone": "tz-overlay"},
  "before_state": null,
  "after_state": {"id": "app-web-seg", "type": "OVERLAY", "admin_state": "UP"},
  "result": "Segment 'app-web-seg' created successfully.",
  "user": "admin"
}
```

Read-only operations are also logged with `operation: "query"` for complete traceability.

### Double Confirmation on Write Operations

CLI write commands require two separate confirmation prompts before executing:

1. First prompt: "Are you sure?" (default: No)
2. Second prompt: "This modifies NSX network configuration. Confirm again?" (default: No)

Both must be answered `y` for the operation to proceed. This applies to all create, update, and delete operations.

### Dry-Run Mode

All write commands support `--dry-run` to preview what would happen without making changes:

```bash
vmware-nsx segment create app-web-seg --gateway app-t1 --subnet 10.10.1.1/24 --transport-zone tz-overlay --dry-run
# Output: [DRY-RUN] Would create segment 'app-web-seg' (overlay) on gateway 'app-t1' with subnet 10.10.1.1/24

vmware-nsx nat create app-t1 --action SNAT --source 10.10.1.0/24 --translated 172.16.0.10 --dry-run
# Output: [DRY-RUN] Would create SNAT rule on gateway 'app-t1': 10.10.1.0/24 → 172.16.0.10
```

### Dependency Checks

Write operations include dependency validation to prevent cascade failures:

- **Segment delete**: Checks for connected logical ports. If VMs or router interfaces are still connected, the operation is refused (unless `--force` is used)
- **Tier-1 gateway delete**: Checks for connected segments. If segments are still attached, the operation is refused
- **NAT/route operations**: Verifies that the target gateway exists before attempting the operation

### Prompt Injection Defense

NSX object names (segments, gateways, rules) returned from the NSX API are sanitized before output via the `_sanitize()` function:

- Strips C0/C1 control characters (U+0000-U+0008, U+000B, U+000C, U+000E-U+001F, U+007F-U+009F)
- Preserves newlines and tabs
- Truncates to 500 characters maximum

This prevents malicious object names from injecting prompts when the data flows to downstream LLM agents.

### Input Validation

- **CIDR networks**: Validated via Python's `ipaddress.ip_network()`
- **IP addresses**: Validated via Python's `ipaddress.ip_address()`
- **VLAN IDs**: Validated to be in range 0-4094
- **Port numbers**: Validated to be in range 1-65535
- **Segment/gateway/rule IDs**: Looked up via NSX API; returns a clear error if not found
- **NAT actions**: Validated against allowed enum values
- **IP pool ranges**: Start IP must be less than end IP, both must be within the specified CIDR

### Transport Security

- The MCP server uses **stdio transport** (local only) — no network listener is opened
- NSX Manager connections use HTTPS on port 443 by default
- SSL certificate verification can be enabled per-target via `verify_ssl: true` in config.yaml
- **Production recommendation**: Use `verify_ssl: true` with a valid CA certificate. Set `ca_cert_path` in config.yaml to specify a custom CA bundle

### What This Skill Cannot Do

This skill has **no firewall or security operations**. It cannot:
- Create, modify, or delete DFW (Distributed Firewall) rules
- Manage security groups or security policies
- Configure IDS/IPS
- Manage URL filtering rules
- Configure service insertion

For security operations, use `vmware-nsx-security`.

## Multi-Target Setup

You can configure multiple NSX Manager targets and switch between them:

```yaml
targets:
  - name: nsx-prod
    host: nsx-prod-vip.example.com
    username: svc-automation
    port: 443
    verify_ssl: true
    ca_cert_path: /etc/pki/tls/certs/nsx-prod-ca.pem

  - name: nsx-staging
    host: nsx-staging.example.com
    username: admin
    port: 443
    verify_ssl: false

  - name: nsx-lab
    host: 10.0.1.100
    username: admin
    port: 443
    verify_ssl: false
```

```bash
# Uses first target (nsx-prod) by default
vmware-nsx segment list

# Explicitly target staging
vmware-nsx segment list --target nsx-staging

# Target lab
vmware-nsx health alarms --target nsx-lab
```

## NSX Manager Roles

Recommended role assignments for the service account used by this skill:

| Use Case | NSX Role | Capabilities |
|----------|---------|-------------|
| Read-only monitoring | `network_engineer` (read-only) | List/get all objects, health, troubleshoot |
| Network automation | `network_engineer` | Create/modify segments, T1 gateways, NAT, routes, IP pools |
| Full operations | `enterprise_admin` | All operations including T0 modifications |

**Least privilege**: For monitoring-only deployments, use a read-only role. Write tools will return permission errors, but all read operations work.

## File Locations

| File | Purpose |
|------|---------|
| `~/.vmware-nsx/config.yaml` | Connection targets and settings |
| `~/.vmware-nsx/.env` | Passwords (chmod 600) |
| `~/.vmware/audit.db` | Operation audit trail (SQLite WAL, via vmware-policy) |

## Combining with Other VMware Skills

vmware-nsx can run alongside other VMware MCP skills simultaneously:

```json
{
  "mcpServers": {
    "vmware-nsx": {
      "command": "vmware-nsx-mcp",
      "env": { "VMWARE_NSX_CONFIG": "~/.vmware-nsx/config.yaml" }
    },
    "vmware-nsx-security": {
      "command": "vmware-nsx-security-mcp",
      "env": { "VMWARE_NSX_SECURITY_CONFIG": "~/.vmware-nsx-security/config.yaml" }
    },
    "vmware-monitor": {
      "command": "vmware-monitor-mcp",
      "env": { "VMWARE_MONITOR_CONFIG": "~/.vmware-monitor/config.yaml" }
    }
  }
}
```
