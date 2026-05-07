# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

H3C Monitor — 网络设备监控系统。FastAPI + SQLite + APScheduler + Jinja2，支持 SNMP/SSH 双通道采集，侧边栏多页面架构。

## 常用命令

```bash
uv sync                          # 安装依赖
uv run python app.py             # 启动服务 (localhost:9001)
uv run uvicorn app:app --host 0.0.0.0 --port 9001 --reload  # 开发模式
```

没有 lint、format、test 等配置。

## 架构

```
app.py              - FastAPI 应用、页面路由、API 路由、APScheduler 调度
collector.py        - 采集器：SNMP 优先，SSH 兜底
alarm.py            - 告警引擎：规则管理 + 告警检查 + 自动触发/恢复
driver/             - 设备驱动
  base.py           - DeviceDriver 抽象基类 + DeviceInfo/MetricsResult/InterfaceData
  h3c_snmp.py       - H3C SNMPv2c 驱动 (pysnmp 7.x)
  h3c_ssh.py        - H3C SSH 驱动 (Netmiko)
  __init__.py        - get_driver() / get_ssh_driver()
database.py         - SQLite CRUD (devices/device_metrics/interface_stats/alarms/alarm_rules)
config.py           - DEVICE_LIST (含 SNMP 配置)、DB_PATH、COLLECT_INTERVAL
templates/          - Jinja2 模板 (base.html 布局 + 各页面继承)
static/             - CSS/JS (暗色主题、API 封装)
```

## 关键设计

### 采集 + 告警联动

`auto_collect()` → `collector` 采集 → `_save_and_alarm()` 写库 → `alarm.check_and_trigger()` 逐规则检查：
- 指标超阈值 → 写 `alarms` (status=active)
- 指标恢复 → 自动 `resolved`
- 同一规则不重复触发 (已有 active 则跳过)

### APScheduler 线程模型

`BlockingScheduler` 放入 daemon 线程启动，调度器在后台运行，主线程执行 uvicorn。

### 前端：base.html 模板继承

所有页面继承 `templates/base.html`：侧边栏导航 + 顶栏（时钟、告警指示灯、主题切换）。静态文件：`static/css/app.css`（明/暗双主题）、`static/js/api.js`（fetch 封装 + 通用工具）。

### 已实现页面

| 路由 | 模板 | 功能 |
|------|------|------|
| `/` | dashboard.html | 监控总览（设备卡片、指标图表、接口表格） |
| `/devices` | devices.html | 设备台账（列表、筛选、编辑弹窗） |
| `/alarms` | alarms.html | 告警中心（列表、确认） |
| `/acl` | acl.html | ACL 管理（规则列表、新建/编辑/删除，通过 SSH 下发） |

### SNMP OID

H3C 私有 MIB：CPU `1.3.6.1.4.1.25506.2.6.1.1.1.1.6`、内存 `...1.8`、温度 `...1.12`。
标准 MIB：sysDescr/sysName/sysUpTime、IF-MIB (ifHCInOctets/ifHCOutOctets/ifHighSpeed)。

### 数据库表

- `devices` — 设备信息 + 台账扩展字段 (serial_number, warranty_expiry, location, rack, tags 等)
- `device_metrics` — CPU/内存/温度/会话/运行时间
- `interface_stats` — 接口状态/流量
- `alarms` / `alarm_rules` — 告警规则与记录（已实现）

## 已知问题

- **接口采集双路径**（SSH 驱动）：`display interface brief` 和 `display interface` 合并，命名规范不同可能产生重复。SNMP 驱动无此问题。
