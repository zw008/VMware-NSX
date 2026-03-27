<!-- mcp-name: io.github.zw008/vmware-nsx -->
# VMware NSX

[English](README.md) | [中文](README-CN.md)

VMware NSX 网络管理：Segment、网关、NAT、路由、IPAM — 31 个 MCP 工具，领域专注。

> 基于 NSX Policy API，支持 NSX-T 3.0+ 和 NSX 4.x。

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 伴生 Skills

| Skill | 范围 | 工具数 | 安装 |
|-------|------|:-----:|------|
| **[vmware-aiops](https://github.com/zw008/VMware-AIops)** ⭐ 入口 | VM 生命周期、部署、Guest Ops、集群 | 31 | `uv tool install vmware-aiops` |
| **[vmware-monitor](https://github.com/zw008/VMware-Monitor)** | 只读监控、告警、事件、VM 信息 | 8 | `uv tool install vmware-monitor` |
| **[vmware-storage](https://github.com/zw008/VMware-Storage)** | 数据存储、iSCSI、vSAN | 11 | `uv tool install vmware-storage` |
| **[vmware-vks](https://github.com/zw008/VMware-VKS)** | Tanzu 命名空间、TKC 集群生命周期 | 20 | `uv tool install vmware-vks` |
| **[vmware-nsx-security](https://github.com/zw008/VMware-NSX-Security)** | DFW 微分段、安全组、Traceflow | 20 | `uv tool install vmware-nsx-security` |
| **[vmware-aria](https://github.com/zw008/VMware-Aria)** | Aria Ops 指标、告警、容量规划 | 18 | `uv tool install vmware-aria` |

## 快速安装

```bash
# 通过 PyPI
uv tool install vmware-nsx-mgmt

# 或 pip
pip install vmware-nsx-mgmt
```

## 配置

```bash
mkdir -p ~/.vmware-nsx
cp config.example.yaml ~/.vmware-nsx/config.yaml
# 编辑 config.yaml，填入 NSX Manager 地址和用户名

echo "VMWARE_NSX_PROD_PASSWORD=your_password" > ~/.vmware-nsx/.env
chmod 600 ~/.vmware-nsx/.env

# 验证环境
vmware-nsx doctor
```

### config.yaml 示例

```yaml
default_target: nsx-prod
targets:
  nsx-prod:
    host: nsx-mgr.example.com    # NSX Manager IP 或集群 VIP
    user: admin
    password_env: VMWARE_NSX_PROD_PASSWORD
  nsx-lab:
    host: 10.0.0.100
    user: admin
    password_env: VMWARE_NSX_LAB_PASSWORD
```

## 功能概览

| 类别 | 工具 | 数量 |
|------|------|:----:|
| **Segment** | 列表、详情、创建、更新、删除、端口列表 | 6 |
| **Tier-0 网关** | 列表、详情、BGP 邻居、路由表 | 4 |
| **Tier-1 网关** | 列表、详情、创建、更新、删除、路由表 | 6 |
| **NAT** | 列表、详情、创建、更新、删除 | 5 |
| **静态路由** | 列表、创建、删除 | 3 |
| **IP 池** | 列表、分配详情、创建池、添加子网 | 4 |
| **健康与排障** | 告警、传输节点状态、Edge 集群状态、Manager 状态、逻辑端口状态、VM 所在 Segment | 6 |

## MCP 工具（31 个）

| 类别 | 工具 | 类型 |
|------|------|------|
| Segment | `list_segments`、`get_segment`、`create_segment`、`update_segment`、`delete_segment`、`list_segment_ports` | 读/写 |
| Tier-0 网关 | `list_tier0_gateways`、`get_tier0_gateway`、`get_tier0_bgp_neighbors`、`get_tier0_route_table` | 只读 |
| Tier-1 网关 | `list_tier1_gateways`、`get_tier1_gateway`、`create_tier1_gateway`、`update_tier1_gateway`、`delete_tier1_gateway`、`get_tier1_route_table` | 读/写 |
| NAT | `list_nat_rules`、`get_nat_rule`、`create_nat_rule`、`update_nat_rule`、`delete_nat_rule` | 读/写 |
| 静态路由 | `list_static_routes`、`create_static_route`、`delete_static_route` | 读/写 |
| IP 池 | `list_ip_pools`、`get_ip_pool_allocations`、`create_ip_pool`、`create_ip_pool_subnet` | 读/写 |
| 健康 | `get_nsx_alarms`、`get_transport_node_status`、`get_edge_cluster_status`、`get_manager_cluster_status` | 只读 |
| 排障 | `get_logical_port_status`、`find_vm_segment` | 只读 |

### 工具说明

**Segment**
- `list_segments` — 列出所有 Segment，含类型、子网、网关、传输区域
- `get_segment` — 获取 Segment 详情，含端口和子网配置
- `create_segment` — 创建 Overlay 或 VLAN Segment
- `update_segment` — 更新 Segment 属性（描述、标签、DHCP）
- `delete_segment` — 删除 Segment（检查已连接端口）
- `list_segment_ports` — 列出 Segment 上的逻辑端口及状态

**Tier-0 网关**
- `list_tier0_gateways` — 列出所有 Tier-0 网关，含 HA 模式和 Edge 集群
- `get_tier0_gateway` — 获取 Tier-0 详情：接口、路由配置、BGP
- `get_tier0_bgp_neighbors` — 列出 BGP 邻居会话及状态
- `get_tier0_route_table` — 获取 Tier-0 路由表

**Tier-1 网关**
- `list_tier1_gateways` — 列出所有 Tier-1 网关，含关联的 Tier-0
- `get_tier1_gateway` — 获取 Tier-1 详情：接口、路由通告
- `create_tier1_gateway` — 创建 Tier-1 网关并关联 Edge 集群和 Tier-0
- `update_tier1_gateway` — 更新 Tier-1 属性（路由通告、标签）
- `delete_tier1_gateway` — 删除 Tier-1 网关（检查已连接 Segment）
- `get_tier1_route_table` — 获取 Tier-1 路由表

**NAT**
- `list_nat_rules` — 列出网关上的 NAT 规则
- `get_nat_rule` — 获取 NAT 规则详情
- `create_nat_rule` — 创建 SNAT/DNAT/反射 NAT 规则
- `update_nat_rule` — 更新 NAT 规则属性
- `delete_nat_rule` — 删除 NAT 规则

**静态路由**
- `list_static_routes` — 列出网关上的静态路由
- `create_static_route` — 添加静态路由
- `delete_static_route` — 删除静态路由

**IP 池**
- `list_ip_pools` — 列出 IP 地址池及使用统计
- `get_ip_pool_allocations` — 查看已分配的 IP 地址
- `create_ip_pool` — 创建新的 IP 地址池
- `create_ip_pool_subnet` — 向 IP 池添加子网范围

**健康与排障**
- `get_nsx_alarms` — 列出活跃的 NSX 告警
- `get_transport_node_status` — 传输节点连接和配置状态
- `get_edge_cluster_status` — Edge 集群成员状态
- `get_manager_cluster_status` — NSX Manager 集群健康状态
- `get_logical_port_status` — 逻辑端口管理/运行状态
- `find_vm_segment` — 查找 VM 连接到哪个 Segment

## 常见工作流

### 创建应用网络（Segment + T1 网关 + NAT）

1. 创建网关：`vmware-nsx gateway create-t1 app-t1 --edge-cluster edge-cluster-01 --tier0 tier0-gw`
2. 创建 Segment：`vmware-nsx segment create app-web-seg --gateway app-t1 --subnet 10.10.1.1/24 --transport-zone tz-overlay`
3. 添加 SNAT：`vmware-nsx nat create app-t1 --action SNAT --source 10.10.1.0/24 --translated 172.16.0.10`
4. 验证：`vmware-nsx segment list` 和 `vmware-nsx nat list app-t1`

任何写操作前可加 `--dry-run` 预览。

### 检查网络健康

1. Manager 状态：`vmware-nsx health manager-status`
2. 传输节点：`vmware-nsx health transport-nodes`
3. Edge 集群：`vmware-nsx health edge-clusters`
4. 告警：`vmware-nsx health alarms`

### 排查 VM 连通性

1. 查找 VM 所在 Segment：`vmware-nsx troubleshoot vm-segment my-vm-01`
2. 检查端口状态：`vmware-nsx troubleshoot port-status <port-id>`
3. 检查路由：`vmware-nsx gateway routes-t1 app-t1`
4. 检查 BGP：`vmware-nsx gateway bgp-neighbors tier0-gw`

## CLI

```bash
# Segment
vmware-nsx segment list
vmware-nsx segment get app-web-seg
vmware-nsx segment create app-web-seg --gateway app-t1 --subnet 10.10.1.1/24 --transport-zone tz-overlay
vmware-nsx segment delete app-web-seg

# 网关
vmware-nsx gateway list-t0
vmware-nsx gateway list-t1
vmware-nsx gateway create-t1 app-t1 --edge-cluster edge-cluster-01 --tier0 tier0-gw
vmware-nsx gateway bgp-neighbors tier0-gw
vmware-nsx gateway routes-t1 app-t1

# NAT（写操作有双重确认 + --dry-run 预览）
vmware-nsx nat list app-t1
vmware-nsx nat create app-t1 --action SNAT --source 10.10.1.0/24 --translated 172.16.0.10
vmware-nsx nat delete app-t1 rule-01

# 静态路由
vmware-nsx route list app-t1
vmware-nsx route create app-t1 --network 192.168.100.0/24 --next-hop 10.10.1.254

# IP 池
vmware-nsx ippool list
vmware-nsx ippool create tep-pool
vmware-nsx ippool add-subnet tep-pool --start 192.168.100.10 --end 192.168.100.50 --cidr 192.168.100.0/24

# 健康与排障
vmware-nsx health alarms
vmware-nsx health transport-nodes
vmware-nsx health manager-status
vmware-nsx troubleshoot vm-segment my-vm-01

# 环境诊断
vmware-nsx doctor
```

## MCP Server

```bash
# 直接运行
uvx --from vmware-nsx-mgmt vmware-nsx-mcp

# 或通过 Docker
docker compose up -d
```

### Agent 配置

将以下内容添加到 AI Agent 的 MCP 配置文件：

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

更多 Agent 配置模板（Claude Code、Cursor、Goose、Continue 等）见 [examples/mcp-configs/](examples/mcp-configs/)。

## 版本兼容性

| NSX 版本 | 支持 | 说明 |
|----------|------|------|
| NSX 4.x | 完整 | 最新 Policy API，全部功能 |
| NSX-T 3.2 | 完整 | 所有功能可用 |
| NSX-T 3.1 | 完整 | 路由表格式略有差异 |
| NSX-T 3.0 | 兼容 | IP 池子网 API 在此版本引入 |
| NSX-T 2.5 | 有限 | Policy API 不完整，部分工具可能失败 |
| NSX-V (6.x) | 不支持 | 完全不同的 API（基于 SOAP） |

### VCF 兼容性

| VCF 版本 | 捆绑 NSX | 支持 |
|----------|----------|------|
| VCF 5.x | NSX 4.x | 完整 |
| VCF 4.3-4.5 | NSX-T 3.1-3.2 | 完整 |

## 安全

| 功能 | 说明 |
|------|------|
| 只读为主 | 31 个工具中 18 个只读 |
| 双重确认 | CLI 写操作需两次确认 |
| --dry-run | 所有写操作支持预览模式 |
| 依赖检查 | 删除操作验证无关联资源 |
| 输入验证 | CIDR、IP、VLAN ID、网关存在性验证 |
| 审计日志 | 所有操作记录到 `~/.vmware-nsx/audit.log`（JSON Lines） |
| 无防火墙操作 | 无法创建/修改 DFW 规则或安全组 |
| 凭据安全 | 密码只从环境变量读取，不存于配置文件 |
| Prompt 注入防护 | NSX 对象名称经过控制字符清理 |
| TLS 说明 | 默认对自签名证书禁用 TLS 验证；生产环境建议启用 |

## 常见问题排查

| 问题 | 原因与解决 |
|------|-----------|
| "Segment not found" | Policy API 使用 Segment `id` 而非 `display_name`。运行 `segment list` 获取准确 ID。 |
| NAT 创建报 "gateway not found" | NAT 需要 Tier-1（或 Tier-0）网关。用 `gateway list-t1` 确认，网关必须有 Edge 集群。 |
| BGP 邻居停在 Connect/Active | 对端不可达、ASN 不匹配、TCP 179 被阻止、或 MD5 密码不匹配。 |
| 传输节点 "degraded" | TEP 不可达（检查 MTU >= 1600）、NTP 同步问题、或主机交换机配置不匹配。 |
| "Password not found" 错误 | 变量名规则：`VMWARE_<目标名大写>_PASSWORD`（连字符→下划线）。检查 `~/.vmware-nsx/.env`。 |
| 连接 NSX Manager 超时 | 使用 `vmware-nsx doctor --skip-auth` 跳过高延迟网络的认证检查。 |

## 许可证

[MIT](LICENSE)
