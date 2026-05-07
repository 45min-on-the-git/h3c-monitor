"""测试共享 fixture"""

import sys
import os
import sqlite3
import pytest

# 确保项目根目录在 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_db():
    """内存 SQLite，自动建表，测试后清理"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 建表（与 database.init_db 一致）
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_type TEXT NOT NULL,
        ip TEXT UNIQUE NOT NULL,
        hostname TEXT, model TEXT, sw_version TEXT, username TEXT,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        serial_number TEXT, purchase_date TEXT, warranty_expiry TEXT,
        supplier TEXT, contract_no TEXT, asset_no TEXT,
        location TEXT, rack TEXT, role TEXT, tags TEXT
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS device_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        collect_time DATETIME NOT NULL,
        cpu_usage REAL, mem_usage REAL, temperature REAL,
        session_count INTEGER, uptime TEXT,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interface_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        collect_time DATETIME NOT NULL,
        if_name TEXT, status TEXT,
        in_bytes INTEGER, out_bytes INTEGER,
        in_util REAL, out_util REAL,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alarm_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        metric TEXT NOT NULL,
        operator TEXT NOT NULL DEFAULT '>',
        threshold REAL NOT NULL,
        enabled INTEGER DEFAULT 1,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alarms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        rule_id INTEGER, metric TEXT NOT NULL,
        value REAL, threshold REAL,
        status TEXT DEFAULT 'active',
        triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        resolved_at DATETIME,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    )""")
    conn.commit()

    # 插入测试设备
    cursor.execute(
        "INSERT INTO devices (device_type, ip, hostname) VALUES ('switch', '10.0.0.1', 'test-sw')"
    )
    conn.commit()

    yield conn
    conn.close()


@pytest.fixture
def sample_device():
    """标准测试设备配置"""
    return {
        "device_type": "hp_comware",
        "ip": "10.0.0.1",
        "username": "admin",
        "password": "test",
        "device_name": "test-sw",
        "device_category": "switch",
        "snmp_community": "public",
        "snmp_version": 2,
    }
