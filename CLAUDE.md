# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

H3C Monitor — 通过 SSH 采集 H3C 交换机和防火墙指标的网络设备监控系统。FastAPI + SQLite + Netmiko + APScheduler + Jinja2。

## 常用命令

```bash
uv sync                          # 安装依赖
uv run python app.py             # 启动服务 (localhost:9001)
uv run uvicorn app:app --host 0.0.0.0 --port 9001 --reload  # 开发模式
```

没有 lint、format、test 等配置 — 项目目前无测试框架。

## 架构

```
app.py          - FastAPI 应用、路由、APScheduler 自动采集调度
collector.py    - Netmiko SSH 采集 + 正则解析 H3C CLI 输出
database.py     - SQLite CRUD（devices / device_metrics / interface_stats）
config.py       - DEVICE_LIST、DB_PATH、COLLECT_INTERVAL
templates/      - Jinja2 HTML（Bootstrap 5 + Chart.js，全部走 CDN，无本地 static）
```

## 关键设计

### APScheduler 线程模型

`app.py` 使用 `BlockingScheduler`（设计上是阻塞的），但将它放入 daemon 线程启动。这意味着调度器在后台运行，主线程继续执行 uvicorn。daemon=True 保证进程退出时调度器随之终止。

### 采集流程

1. `collector.collect_device_data(device_config)` 通过 Netmiko (`hp_comware`) SSH 连接设备
2. 依次执行 H3C CLI 命令：`display version`、`display cpu-usage`、`display memory`、`display environment`、`display interface brief`、`display interface`、`display session statistics ipv4`（仅防火墙）、`display ip interface brief`
3. 每个命令的输出由对应的正则解析函数提取指标值
4. 结果通过 `database.get_or_create_device()` 写入/更新设备记录，指标和接口数据追加写入

### 接口采集的双路径

`collect_device_data()` 同时采集 `display interface brief`（快速获取接口名+状态）和 `display interface`（获取详细流量字节数）。两者结果通过 `extend` 合并，但接口命名规范不同（brief 用缩写如 `GE1/0`，detail 用全名如 `GigabitEthernet1/0/1`），可能产生同一物理接口的多条记录。

### get_latest_interfaces 子查询

`database.get_latest_interfaces()` 使用关联子查询，按 `(device_id, if_name)` 分组取每个接口最新一条记录，而非简单按时间取全部。

### 启动即采集

`app.py` 模块加载时（第 60 行）会同步执行一次 `auto_collect()`。在调度器启动前完成首次采集，确保 Web UI 立即可见数据。

## 已知问题

- **接口采集的双路径**：`collect_device_data()` 同时采集 `display interface brief`（快速获取接口名+状态）和 `display interface`（获取详细流量字节数）。两者结果通过 `extend` 合并，但接口命名规范不同（brief 用缩写如 `GE1/0`，detail 用全名如 `GigabitEthernet1/0/1`），可能产生同一物理接口的多条记录。
