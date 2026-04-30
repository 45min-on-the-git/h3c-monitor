# H3C 网络设备监控

通过 SSH 采集并监控 H3C 交换机和防火墙的运行状态。

## 功能特性

- **自动采集**：服务启动时立即采集一次，此后每 5 分钟自动采集
- **支持设备类型**：H3C 防火墙、H3C 交换机
- **采集指标**：CPU 使用率、内存使用率、温度、运行时间、会话数（防火墙）、接口状态与流量
- **Web 界面**：设备卡片总览、历史指标表格、接口状态表格
- **手动采集**：支持前台手动触发单台或全部设备采集

## 环境要求

- Python 3.10+
- 使用 uv 管理项目依赖

## 安装依赖

```bash
uv sync
```

## 运行

## 配置设备

编辑 `config.py` 中的 `DEVICE_LIST`，添加要监控的设备：

```python
DEVICE_LIST = [
    {
        "device_type": "hp_comware",      # 固定为 hp_comware
        "ip": "192.168.42.130",
        "username": "admin",
        "password": "Admin@123456",
        "device_name": "FW-01",           # 自定义显示名称
        "device_category": "firewall"      # firewall 或 switch
    }
]
```

## 启动服务

```bash
uv run python app.py
```

或使用 uvicorn：

```bash
uv run uvicorn app:app --host 0.0.0.0 --port 9001
```

启动后访问 `http://localhost:9001/`

## 采集的指标

| 指标 | 说明 | 适用设备 |
|------|------|---------|
| CPU 使用率 | 5 秒内 CPU 占用 | 全部 |
| 内存使用率 | 内存占用百分比 | 全部 |
| 温度 | 设备环境温度 | 全部 |
| 运行时间 | 设备持续运行时长 | 全部 |
| 会话数 | 当前 IPv4 会话数 | 防火墙 |
| 接口状态 | 接口 UP/DOWN | 全部 |
| 接口流量 | 入向/出向字节数 | 全部 |

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | Web 管理界面 |
| GET | `/api/devices` | 设备列表 |
| GET | `/api/metrics` | 历史指标查询 |
| GET | `/api/metrics/latest/{device_id}` | 设备最新指标 |
| GET | `/api/interfaces/{device_id}` | 设备最新接口信息 |
| POST | `/api/collect/all` | 手动采集所有设备 |
| POST | `/api/collect/{device_ip}` | 手动采集单台设备 |

## 数据库

数据存储在 `h3c_monitor.db`（SQLite），包含以下表：

- `devices` — 设备基本信息
- `device_metrics` — 指标历史
- `interface_stats` — 接口统计历史
