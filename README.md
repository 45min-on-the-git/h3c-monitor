# H3C 网络设备监控

通过 SNMP/SSH 双通道采集并监控 H3C 交换机和防火墙的运行状态。

## 功能特性

- **双通道采集**：SNMP 优先，SSH 自动兜底
- **自动采集**：服务启动时立即采集一次，此后每 5 分钟自动采集
- **支持设备类型**：H3C 防火墙、H3C 交换机
- **采集指标**：CPU 使用率、内存使用率、温度、运行时间、会话数（防火墙）、接口状态与流量
- **告警引擎**：自定义阈值规则，自动触发/恢复，告警中心页面
- **设备台账**：序列号、采购日期、维保到期、供应商、机房机柜、资产编号
- **接口流量图**：接口级流量时序曲线（bps），带宽利用率
- **ACL 管理**：通过 SSH 读取/新建/编辑/删除设备 ACL 规则
- **侧边栏导航**：监控总览 / 设备台账 / 告警中心 / ACL 管理
- **暗色主题**：支持明/暗双主题切换
- **单元测试**：18 个用例覆盖 ACL 解析、告警引擎、数据库 CRUD

## 环境要求

- Python 3.10+
- 使用 uv 管理项目依赖

## 快速开始

```bash
git clone https://github.com/45min-on-the-git/h3c-monitor.git
cd h3c-monitor
uv sync
```

## 配置设备

编辑 `config.py` 中的 `DEVICE_LIST`：

```python
DEVICE_LIST = [
    {
        "device_type": "hp_comware",
        "ip": "192.168.42.130",
        "username": "admin",
        "password": "Admin@123456",
        "device_name": "FW-01",
        "device_category": "firewall",
        "snmp_community": "public",
        "snmp_version": 2,
    }
]
```

## 启动服务

```bash
uv run python app.py
# 或
uv run uvicorn app:app --host 0.0.0.0 --port 9001 --reload
```

启动后访问 `http://localhost:9001/`

## 运行测试

```bash
uv run pytest tests/ -v
```

## 采集的指标

| 指标 | 说明 | 适用设备 |
|------|------|---------|
| CPU 使用率 | H3C 私有 MIB / CLI 解析 | 全部 |
| 内存使用率 | 内存占用百分比 | 全部 |
| 温度 | 设备环境温度 | 全部 |
| 运行时间 | 设备持续运行时长 | 全部 |
| 会话数 | 当前 IPv4 会话数 | 防火墙 |
| 接口状态 | 接口 UP/DOWN | 全部 |
| 接口流量 | 入向/出向字节数 + 速率(bps) | 全部 |

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 监控总览 |
| GET | `/devices` | 设备台账 |
| GET | `/alarms` | 告警中心 |
| GET | `/acl` | ACL 管理 |
| GET | `/api/devices` | 设备列表 |
| POST/PUT | `/api/devices[/{id}]` | 设备台账 CRUD |
| GET | `/api/metrics` | 历史指标查询 |
| GET | `/api/metrics/latest/{id}` | 设备最新指标 |
| GET | `/api/interfaces/{id}` | 设备最新接口信息 |
| GET | `/api/interfaces/{id}/traffic` | 接口流量时序数据 |
| POST | `/api/collect/all` | 手动采集所有设备 |
| POST | `/api/collect/{ip}` | 手动采集单台设备 |
| GET/POST | `/api/alarm-rules` | 告警规则 CRUD |
| GET | `/api/alarms` | 告警记录列表 |
| POST | `/api/alarms/{id}/acknowledge` | 确认告警 |
| GET/POST/DELETE | `/api/acl/{device_id}...` | ACL 规则 CRUD |

## 项目架构

```
app.py              - FastAPI 应用、路由、APScheduler 调度
collector.py        - 采集器：SNMP 优先，SSH 兜底
alarm.py            - 告警引擎：规则管理 + 触发/恢复
driver/             - 设备驱动（抽象基类 + SNMP/SSH 实现）
database.py         - SQLite CRUD
config.py           - 设备列表、数据库路径、采集间隔
templates/          - Jinja2 模板（base.html 布局 + 4 页面）
static/             - CSS/JS（暗色主题、API 封装）
tests/              - 单元测试（18 用例）
```

## 数据库

- `devices` — 设备信息 + 台账扩展字段
- `device_metrics` — CPU/内存/温度/会话/运行时间
- `interface_stats` — 接口状态/流量历史
- `alarm_rules` — 告警规则
- `alarms` — 告警记录
