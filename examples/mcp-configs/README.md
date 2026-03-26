# MCP Configuration Templates

Copy the relevant config snippet into your AI agent's MCP configuration file.

## Prerequisites

```bash
# Install vmware-nsx
uv tool install vmware-nsx-mgmt
# or: pip install vmware-nsx-mgmt

# Configure credentials
mkdir -p ~/.vmware-nsx
cp config.example.yaml ~/.vmware-nsx/config.yaml
# Edit config.yaml with your NSX Manager host and username

echo "VMWARE_NSX_PROD_PASSWORD=your_password" > ~/.vmware-nsx/.env
chmod 600 ~/.vmware-nsx/.env

# Verify setup
vmware-nsx doctor
```

## Agent Configuration Files

| Agent | Config File | Template |
|-------|------------|----------|
| Claude Code | `~/.claude/settings.json` | [claude-code.json](claude-code.json) |
| Cursor | Cursor MCP settings | [cursor.json](cursor.json) |
| Goose | `goose configure` or UI | [goose.json](goose.json) |
| Continue | `~/.continue/config.yaml` | [continue.yaml](continue.yaml) |
| LocalCowork | MCP config panel | [localcowork.json](localcowork.json) |
| mcp-agent | `mcp_agent.config.yaml` | [mcp-agent.yaml](mcp-agent.yaml) |
| VS Code Copilot | `.vscode/mcp.json` | [vscode-copilot.json](vscode-copilot.json) |

## Using with Local Models (Ollama / LM Studio)

vmware-nsx has 31 tools — suitable for medium to large models with sufficient context windows. For smaller local models (7B-14B), consider using only the read-only tools or filtering by category.

```bash
# Example: Continue + Ollama + vmware-nsx MCP server
# 1. Configure Continue with your Ollama model
# 2. Add vmware-nsx MCP config from continue.yaml
# 3. Ask naturally: "list all segments" or "show NAT rules on app-t1"
```

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
    },
    "vmware-storage": {
      "command": "vmware-storage-mcp",
      "env": { "VMWARE_STORAGE_CONFIG": "~/.vmware-storage/config.yaml" }
    }
  }
}
```
