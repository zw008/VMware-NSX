# Security Policy

## Disclaimer

This is a community-maintained open-source project and is **not affiliated with, endorsed by, or sponsored by VMware, Inc. or Broadcom Inc.** "VMware" and "NSX" are trademarks of Broadcom Inc.

**Author**: Wei Zhou, VMware by Broadcom — wei-wz.zhou@broadcom.com

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it privately:

- **Email**: wei-wz.zhou@broadcom.com
- **GitHub**: Open a [private security advisory](https://github.com/zw008/VMware-NSX/security/advisories/new)

Do **not** open a public GitHub issue for security vulnerabilities.

## Security Design

### Credential Management

- Passwords are stored exclusively in `~/.vmware-nsx/.env` (never in `config.yaml`, never in code)
- `.env` file permissions are verified at startup (`chmod 600` required)
- No credentials are logged, echoed, or included in audit entries
- Each NSX Manager target uses a separate environment variable: `VMWARE_<TARGET_NAME_UPPER>_PASSWORD`
- Authentication is username/password via the NSX session-create API (form-body encoded, so
  passwords with special characters work correctly)

### Destructive Operation Safeguards

All write operations pass through multiple safety layers:

1. **`@vmware_tool` decorator** — mandatory on every MCP tool; provides pre-checks, audit logging, data sanitization, and timeout control
2. **Double confirmation** — CLI destructive commands (segment delete, gateway delete, NAT rule delete) require two separate "Are you sure?" prompts
3. **`--dry-run` mode** — all CLI write commands support preview without execution
4. **Dependency checks** — segment deletion verifies port count, gateway deletion checks for connected segments before proceeding
5. **Audit logging** — every operation (read and write) is logged to `~/.vmware/audit.db` (SQLite WAL) with timestamp, user, target, operation, parameters, and result
6. **Policy engine** — `~/.vmware/rules.yaml` can deny operations by pattern, enforce maintenance windows, and set risk-level thresholds

### SSL/TLS Verification

- TLS certificate verification is **enabled by default**
- `disableSslCertValidation: true` exists solely for NSX Manager instances using self-signed certificates in isolated lab/home environments
- In production, always use CA-signed certificates with full TLS verification

### Transitive Dependencies

- `vmware-policy` is the only transitive dependency auto-installed; it provides the `@vmware_tool` decorator and audit logging
- All other dependencies are standard Python packages (requests, Click, Rich, python-dotenv)
- No post-install scripts or background services are started during installation
- PyPI package name: `vmware-nsx-mgmt`

### Prompt Injection Protection

- All NSX-sourced content (segment names, rule descriptions, gateway configurations) is processed through `_sanitize()`
- Sanitization truncates to 500 characters and strips C0/C1 control characters
- Output is wrapped in boundary markers when consumed by LLM agents

## Static Analysis

This project is scanned with [Bandit](https://bandit.readthedocs.io/) before every release, targeting 0 Medium+ issues:

```bash
uvx bandit -r vmware_nsx/
```

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.5.x   | Yes       |
| < 1.5   | No        |
