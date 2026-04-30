# 数据库操作模块
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any
import config


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 设备信息表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_type TEXT NOT NULL CHECK (device_type IN ('switch', 'firewall')),
        ip TEXT UNIQUE NOT NULL,
        hostname TEXT,
        model TEXT,
        sw_version TEXT,
        username TEXT,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 指标历史表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS device_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        collect_time DATETIME NOT NULL,
        cpu_usage REAL,
        mem_usage REAL,
        temperature REAL,
        session_count INTEGER,
        uptime TEXT,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    )
    ''')
    
    # 端口信息表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS interface_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        collect_time DATETIME NOT NULL,
        if_name TEXT,
        status TEXT,
        in_bytes INTEGER,
        out_bytes INTEGER,
        in_util REAL,
        out_util REAL,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    )
    ''')
    
    # 创建索引
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_device_metrics_device_time
    ON device_metrics(device_id, collect_time)
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_interface_stats_device_time
    ON interface_stats(device_id, collect_time)
    ''')
    
    conn.commit()
    conn.close()


def get_or_create_device(device_info: Dict[str, Any]) -> int:
    """获取或创建设备记录"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id FROM devices WHERE ip = ?
    ''', (device_info['ip'],))
    
    row = cursor.fetchone()
    if row:
        device_id = row['id']
    else:
        cursor.execute('''
            INSERT INTO devices (device_type, ip, hostname, model, sw_version, username)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            device_info.get('device_category', 'switch'),
            device_info['ip'],
            device_info.get('hostname', ''),
            device_info.get('model', ''),
            device_info.get('sw_version', ''),
            device_info.get('username', '')
        ))
        device_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return device_id


def save_metrics(device_id: int, metrics: Dict[str, Any]):
    """保存设备指标"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO device_metrics (device_id, collect_time, cpu_usage, mem_usage, temperature, session_count, uptime)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        device_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        metrics.get('cpu_usage'),
        metrics.get('mem_usage'),
        metrics.get('temperature'),
        metrics.get('session_count'),
        metrics.get('uptime')
    ))
    
    conn.commit()
    conn.close()


def save_interfaces(device_id: int, interfaces: List[Dict[str, Any]]):
    """保存接口信息"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for iface in interfaces:
        cursor.execute('''
            INSERT INTO interface_stats (device_id, collect_time, if_name, status, in_bytes, out_bytes, in_util, out_util)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            device_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            iface.get('if_name'),
            iface.get('status'),
            iface.get('in_bytes'),
            iface.get('out_bytes'),
            iface.get('in_util'),
            iface.get('out_util')
        ))
    
    conn.commit()
    conn.close()


def get_devices() -> List[Dict[str, Any]]:
    """获取所有设备列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM devices ORDER BY id')
    rows = cursor.fetchall()
    
    devices = []
    for row in rows:
        devices.append({
            'id': row['id'],
            'device_type': row['device_type'],
            'ip': row['ip'],
            'hostname': row['hostname'],
            'model': row['model'],
            'sw_version': row['sw_version'],
            'create_time': row['create_time']
        })
    
    conn.close()
    return devices


def get_metrics(device_id: Optional[int] = None, 
                start_time: Optional[str] = None,
                end_time: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取指标历史"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM device_metrics WHERE 1=1'
    params = []
    
    if device_id:
        query += ' AND device_id = ?'
        params.append(device_id)
    
    if start_time:
        query += ' AND collect_time >= ?'
        params.append(start_time)
    
    if end_time:
        query += ' AND collect_time <= ?'
        params.append(end_time)
    
    query += ' ORDER BY collect_time DESC LIMIT 100'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    metrics = []
    for row in rows:
        metrics.append({
            'id': row['id'],
            'device_id': row['device_id'],
            'collect_time': row['collect_time'],
            'cpu_usage': row['cpu_usage'],
            'mem_usage': row['mem_usage'],
            'temperature': row['temperature'],
            'session_count': row['session_count'],
            'uptime': row['uptime']
        })
    
    conn.close()
    return metrics


def get_latest_metrics(device_id: int) -> Optional[Dict[str, Any]]:
    """获取设备最新指标"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM device_metrics
        WHERE device_id = ?
        ORDER BY collect_time DESC
        LIMIT 1
    ''', (device_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'id': row['id'],
            'device_id': row['device_id'],
            'collect_time': row['collect_time'],
            'cpu_usage': row['cpu_usage'],
            'mem_usage': row['mem_usage'],
            'temperature': row['temperature'],
            'session_count': row['session_count'],
            'uptime': row['uptime']
        }
    return None


def get_latest_interfaces(device_id: int) -> List[Dict[str, Any]]:
    """获取设备最新接口信息（每个接口取最新一条）"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 每个接口取最新时间的记录
    cursor.execute('''
        SELECT * FROM interface_stats i1
        WHERE device_id = ?
        AND collect_time = (
            SELECT MAX(collect_time) FROM interface_stats i2
            WHERE i2.device_id = i1.device_id AND i2.if_name = i1.if_name
        )
        ORDER BY if_name
    ''', (device_id,))

    rows = cursor.fetchall()
    conn.close()

    interfaces = []
    for row in rows:
        interfaces.append({
            'if_name': row['if_name'],
            'status': row['status'],
            'in_bytes': row['in_bytes'],
            'out_bytes': row['out_bytes'],
            'in_util': row['in_util'],
            'out_util': row['out_util'],
            'collect_time': row['collect_time']
        })

    return interfaces
