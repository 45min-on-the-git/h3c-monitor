# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本代码库中工作时提供指导。

## 项目概述

H3C Monitor 是一个网络设备监控系统，通过 SSH 采集并存储 H3C 交换机和防火墙的指标数据。使用 FastAPI 构建 Web API，SQLite 存储数据，Netmiko 实现 SSH 连接，APScheduler 负责定期采集。

## 运行应用

```bash
python app.py
# 或
uvicorn app:app --host 0.0.0.0 --port 9001
```

Web UI 访问地址：`http://localhost:9001/`

## 架构

```
app.py          - FastAPI 应用、路由、自动采集调度器
collector.py    - 通过 Netmiko SSH 采集，解析 H3C CLI 输出
database.py     - SQLite 数据库操作（devices, metrics, interface_stats）
config.py       - 设备列表、数据库路径、采集间隔配置
templates/      - Jinja2 HTML 模板
static/         - 静态资源（目前未使用）
```

## 关键模式

- **设备采集**：`collector.collect_device_data()` 通过 SSH 连接设备，执行 H3C CLI 命令（`display version`、`display cpu-usage`、`display memory`、`display environment`、`display interface brief` 等），使用正则表达式解析输出
- **自动采集**：APScheduler 每 5 分钟执行一次 `auto_collect()`（可通过 `config.COLLECT_INTERVAL` 配置）
- **数据库**：设备通过 `get_or_create_device()` 创建或更新，指标和接口数据按时间戳追加存储
- **设备类型**：H3C 设备使用 `hp_comware` 作为 Netmiko 设备类型；`device_category` 区分 `firewall` 和 `switch`

## API 端点

- `GET /` - Web UI 页面
- `GET /api/devices` - 获取所有设备列表
- `GET /api/metrics?device_id=&start_time=&end_time=` - 查询指标历史
- `GET /api/metrics/latest/{device_id}` - 获取设备最新指标
- `GET /api/available-devices` - 获取配置的设备列表
- `POST /api/collect/all` - 立即采集所有设备
- `GET/POST /api/collect/{device_ip}` - 立即采集单台设备
