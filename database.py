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

    # 台账扩展字段 — ALTER TABLE 迁移 (SQLite 不支持 IF NOT EXISTS for column)
    _migrate_devices_columns(cursor)

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
        if_speed INTEGER DEFAULT 0,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    )
    ''')

    # 告警规则表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS alarm_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        metric TEXT NOT NULL,
        operator TEXT NOT NULL DEFAULT '>',
        threshold REAL NOT NULL,
        enabled INTEGER DEFAULT 1,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    )
    ''')

    # 告警记录表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS alarms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        rule_id INTEGER,
        metric TEXT NOT NULL,
        value REAL,
        threshold REAL,
        status TEXT DEFAULT 'active' CHECK (status IN ('active','acknowledged','resolved')),
        triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        resolved_at DATETIME,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    )
    ''')

    # 配置模板表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS config_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        template_text TEXT NOT NULL,
        variables TEXT DEFAULT '{}'
    )
    ''')

    # 端口分配台账
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS port_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        if_name TEXT NOT NULL,
        connected_device TEXT,
        connected_port TEXT,
        description TEXT,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    )
    ''')

    # 变更审计
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        action TEXT NOT NULL,
        detail TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # VLAN 台账
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vlan_registry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        vlan_id INTEGER NOT NULL,
        name TEXT,
        subnet_id INTEGER,
        purpose TEXT,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    )
    ''')

    # migrate devices status column
    existing_dev = {row[1] for row in cursor.execute("PRAGMA table_info(devices)")}
    if "status" not in existing_dev:
        cursor.execute("ALTER TABLE devices ADD COLUMN status TEXT DEFAULT 'online'")

    # 配置备份表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS config_backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        config_text TEXT NOT NULL,
        config_hash TEXT,
        backup_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    )
    ''')

    # IPAM 子网表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ip_subnets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        network TEXT NOT NULL,
        cidr INTEGER NOT NULL DEFAULT 24,
        gateway TEXT,
        vlan_id INTEGER,
        description TEXT
    )
    ''')

    # IP 分配表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ip_allocations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subnet_id INTEGER NOT NULL,
        ip_address TEXT NOT NULL,
        device_name TEXT,
        interface_name TEXT,
        status TEXT DEFAULT 'free' CHECK (status IN ('free','used','reserved')),
        description TEXT,
        FOREIGN KEY (subnet_id) REFERENCES ip_subnets(id)
    )
    ''')

    # 迁移：加 if_speed 列
    existing_if = {row[1] for row in cursor.execute("PRAGMA table_info(interface_stats)")}
    if "if_speed" not in existing_if:
        cursor.execute("ALTER TABLE interface_stats ADD COLUMN if_speed INTEGER DEFAULT 0")

    # 索引
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


def _migrate_devices_columns(cursor):
    """安全添加台账扩展字段"""
    new_cols = [
        "serial_number TEXT",
        "purchase_date TEXT",
        "warranty_expiry TEXT",
        "supplier TEXT",
        "contract_no TEXT",
        "asset_no TEXT",
        "location TEXT",
        "rack TEXT",
        "role TEXT",
        "tags TEXT",
    ]
    existing = {row[1] for row in cursor.execute("PRAGMA table_info(devices)")}
    for col_def in new_cols:
        col_name = col_def.split()[0]
        if col_name not in existing:
            cursor.execute(f"ALTER TABLE devices ADD COLUMN {col_def}")


# ══════ 设备操作 ══════

def get_or_create_device(device_info: Dict[str, Any]) -> int:
    """获取或创建设备记录，并更新采集到的动态信息"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM devices WHERE ip = ?", (device_info["ip"],))
    row = cursor.fetchone()

    if row:
        device_id = row["id"]
        cursor.execute(
            "UPDATE devices SET device_type=?, hostname=?, model=?, sw_version=? WHERE id=?",
            (
                device_info.get("device_category", "switch"),
                device_info.get("hostname", ""),
                device_info.get("model", ""),
                device_info.get("sw_version", ""),
                device_id,
            ),
        )
    else:
        cursor.execute(
            "INSERT INTO devices (device_type, ip, hostname, model, sw_version) VALUES (?, ?, ?, ?, ?)",
            (
                device_info.get("device_category", "switch"),
                device_info["ip"],
                device_info.get("hostname", ""),
                device_info.get("model", ""),
                device_info.get("sw_version", ""),
            ),
        )
        device_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return device_id


def create_device_manual(info: Dict[str, Any]) -> int:
    """手动创建设备记录（含台账字段）"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM devices WHERE ip = ?", (info.get("ip", ""),))
    if cursor.fetchone():
        conn.close()
        raise ValueError(f"设备 IP {info['ip']} 已存在")

    cursor.execute(
        """INSERT INTO devices (device_type, ip, hostname, model, serial_number,
           purchase_date, warranty_expiry, supplier, contract_no, asset_no,
           location, rack, role, tags)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            info.get("device_category", "switch"),
            info.get("ip", ""),
            info.get("device_name", ""),
            info.get("model", ""),
            info.get("serial_number", ""),
            info.get("purchase_date", ""),
            info.get("warranty_expiry", ""),
            info.get("supplier", ""),
            info.get("contract_no", ""),
            info.get("asset_no", ""),
            info.get("location", ""),
            info.get("rack", ""),
            info.get("role", ""),
            info.get("tags", ""),
        ),
    )
    device_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return device_id


def update_device_info(device_id: int, info: Dict[str, Any]):
    """更新设备台账信息"""
    conn = get_db_connection()
    cursor = conn.cursor()

    fields = [
        "hostname", "model", "serial_number", "purchase_date", "warranty_expiry",
        "supplier", "contract_no", "asset_no", "location", "rack", "role", "tags",
    ]
    device_name = info.get("device_name", "")
    if device_name:
        info["hostname"] = device_name

    sets = [f"{f}=?" for f in fields if f in info]
    vals = [info[f] for f in fields if f in info]

    if sets:
        cursor.execute(
            f"UPDATE devices SET {', '.join(sets)} WHERE id=?",
            vals + [device_id],
        )

    conn.commit()
    conn.close()


def get_devices() -> List[Dict[str, Any]]:
    """获取所有设备列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM devices ORDER BY id")
    rows = cursor.fetchall()

    devices = []
    for row in rows:
        d = dict(row)
        devices.append({
            "id": d["id"],
            "device_type": d["device_type"],
            "ip": d["ip"],
            "hostname": d.get("hostname"),
            "model": d.get("model"),
            "sw_version": d.get("sw_version"),
            "create_time": d.get("create_time"),
            "serial_number": d.get("serial_number"),
            "purchase_date": d.get("purchase_date"),
            "warranty_expiry": d.get("warranty_expiry"),
            "supplier": d.get("supplier"),
            "contract_no": d.get("contract_no"),
            "asset_no": d.get("asset_no"),
            "location": d.get("location"),
            "rack": d.get("rack"),
            "role": d.get("role"),
            "tags": d.get("tags"),
            "status": d.get("status", "online"),
        })

    conn.close()
    return devices


# ══════ 指标操作 ══════

def save_metrics(device_id: int, metrics: Dict[str, Any]):
    """保存设备指标"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO device_metrics (device_id, collect_time, cpu_usage, mem_usage, temperature, session_count, uptime) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            device_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            metrics.get("cpu_usage"),
            metrics.get("mem_usage"),
            metrics.get("temperature"),
            metrics.get("session_count"),
            metrics.get("uptime"),
        ),
    )
    conn.commit()
    conn.close()


def save_interfaces(device_id: int, interfaces: List[Dict[str, Any]]):
    """保存接口信息"""
    conn = get_db_connection()
    cursor = conn.cursor()
    for iface in interfaces:
        cursor.execute(
            "INSERT INTO interface_stats (device_id, collect_time, if_name, status, in_bytes, out_bytes, in_util, out_util, if_speed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                device_id,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                iface.get("if_name"),
                iface.get("status"),
                iface.get("in_bytes"),
                iface.get("out_bytes"),
                iface.get("in_util"),
                iface.get("out_util"),
                iface.get("if_speed", 0),
            ),
        )
    conn.commit()
    conn.close()


def get_metrics(
    device_id: Optional[int] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """获取指标历史"""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM device_metrics WHERE 1=1"
    params = []

    if device_id:
        query += " AND device_id = ?"
        params.append(device_id)
    if start_time:
        query += " AND collect_time >= ?"
        params.append(start_time)
    if end_time:
        query += " AND collect_time <= ?"
        params.append(end_time)

    query += " ORDER BY collect_time DESC LIMIT 100"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    metrics = []
    for row in rows:
        metrics.append({
            "id": row["id"],
            "device_id": row["device_id"],
            "collect_time": row["collect_time"],
            "cpu_usage": row["cpu_usage"],
            "mem_usage": row["mem_usage"],
            "temperature": row["temperature"],
            "session_count": row["session_count"],
            "uptime": row["uptime"],
        })

    conn.close()
    return metrics


def get_latest_metrics(device_id: int) -> Optional[Dict[str, Any]]:
    """获取设备最新指标"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM device_metrics WHERE device_id = ? ORDER BY collect_time DESC LIMIT 1",
        (device_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "device_id": row["device_id"],
            "collect_time": row["collect_time"],
            "cpu_usage": row["cpu_usage"],
            "mem_usage": row["mem_usage"],
            "temperature": row["temperature"],
            "session_count": row["session_count"],
            "uptime": row["uptime"],
        }
    return None


def get_latest_interfaces(device_id: int) -> List[Dict[str, Any]]:
    """获取设备最新接口信息（每个接口取最新一条）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT * FROM interface_stats i1
           WHERE device_id = ?
           AND collect_time = (
               SELECT MAX(collect_time) FROM interface_stats i2
               WHERE i2.device_id = i1.device_id AND i2.if_name = i1.if_name
           )
           ORDER BY if_name""",
        (device_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "if_name": row["if_name"],
            "status": row["status"],
            "in_bytes": row["in_bytes"],
            "out_bytes": row["out_bytes"],
            "in_util": row["in_util"],
            "out_util": row["out_util"],
            "if_speed": row["if_speed"],
            "collect_time": row["collect_time"],
        }
        for row in rows
    ]


def get_interface_traffic(
    device_id: int, if_name: str, limit: int = 100
) -> List[Dict[str, Any]]:
    """获取单个接口的流量时序数据"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT collect_time, in_bytes, out_bytes, in_util, out_util, status
           FROM interface_stats
           WHERE device_id=? AND if_name=?
           ORDER BY collect_time ASC
           LIMIT ?""",
        (device_id, if_name, limit),
    )
    rows = cursor.fetchall()
    conn.close()

    data = []
    prev_in = None
    prev_out = None
    for row in rows:
        in_bytes = row["in_bytes"]
        out_bytes = row["out_bytes"]
        # 计算速率 (bps)：两次采集之间的 delta / 时间差
        in_bps = 0
        out_bps = 0
        if prev_in is not None and in_bytes >= prev_in and out_bytes >= prev_out:
            # 采集间隔约 5 分钟 = 300 秒
            delta_in = in_bytes - prev_in
            delta_out = out_bytes - prev_out
            in_bps = round(delta_in * 8 / 300, 0)
            out_bps = round(delta_out * 8 / 300, 0)
        prev_in = in_bytes
        prev_out = out_bytes
        data.append({
            "collect_time": row["collect_time"],
            "in_bytes": in_bytes,
            "out_bytes": out_bytes,
            "in_bps": in_bps,
            "out_bps": out_bps,
            "in_util": row["in_util"],
            "out_util": row["out_util"],
            "status": row["status"],
        })
    return data


# ══════ IPAM ══════

def ipam_get_subnets() -> List[Dict]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM ip_subnets ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ipam_create_subnet(name: str, network: str, cidr: int, gateway: str = "", vlan_id: int = None, description: str = "") -> int:
    conn = get_db_connection()
    c = conn.execute(
        "INSERT INTO ip_subnets (name, network, cidr, gateway, vlan_id, description) VALUES (?,?,?,?,?,?)",
        (name, network, cidr, gateway, vlan_id, description),
    )
    conn.commit()
    sid = c.lastrowid
    conn.close()
    return sid


def ipam_delete_subnet(subnet_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM ip_allocations WHERE subnet_id=?", (subnet_id,))
    conn.execute("DELETE FROM ip_subnets WHERE id=?", (subnet_id,))
    conn.commit()
    conn.close()


def ipam_get_allocations(subnet_id: int) -> List[Dict]:
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM ip_allocations WHERE subnet_id=? ORDER BY ip_address", (subnet_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ipam_set_allocation(subnet_id: int, ip_address: str, status: str, device_name: str = "", interface_name: str = "", description: str = ""):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT id FROM ip_allocations WHERE subnet_id=? AND ip_address=?", (subnet_id, ip_address)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE ip_allocations SET status=?, device_name=?, interface_name=?, description=? WHERE id=?",
            (status, device_name, interface_name, description, row["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO ip_allocations (subnet_id, ip_address, status, device_name, interface_name, description) VALUES (?,?,?,?,?,?)",
            (subnet_id, ip_address, status, device_name, interface_name, description),
        )
    conn.commit()
    conn.close()


def ipam_get_subnet_usage(subnet_id: int) -> Dict:
    """返回子网利用率"""
    conn = get_db_connection()
    subnet = conn.execute("SELECT * FROM ip_subnets WHERE id=?", (subnet_id,)).fetchone()
    if not subnet:
        conn.close()
        return {}
    total_ips = max(2 ** (32 - subnet["cidr"]) - 2, 1)  # 去掉网络地址和广播地址
    used = conn.execute(
        "SELECT COUNT(*) as n FROM ip_allocations WHERE subnet_id=? AND status IN ('used','reserved')",
        (subnet_id,),
    ).fetchone()["n"]
    conn.close()
    return {
        "subnet": dict(subnet),
        "total": total_ips,
        "used": used,
        "free": total_ips - used,
        "utilization": round(used / total_ips * 100, 1) if total_ips > 0 else 0,
    }


# ══════ 配置备份 ══════

import hashlib

def config_backup_save(device_id: int, config_text: str) -> int:
    conn = get_db_connection()
    h = hashlib.sha256(config_text.encode()).hexdigest()[:16]
    c = conn.execute(
        "INSERT INTO config_backups (device_id, config_text, config_hash) VALUES (?,?,?)",
        (device_id, config_text, h),
    )
    conn.commit()
    bid = c.lastrowid
    conn.close()
    return bid


def config_backup_list(device_id: int, limit: int = 20) -> List[Dict]:
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, device_id, config_hash, backup_time FROM config_backups WHERE device_id=? ORDER BY backup_time DESC LIMIT ?",
        (device_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def config_backup_get(backup_id: int) -> Optional[Dict]:
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM config_backups WHERE id=?", (backup_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ══════ 配置模板 ══════

def template_list() -> List[Dict]:
    conn = get_db_connection()
    rows = conn.execute("SELECT id, name, description, variables FROM config_templates ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def template_get(template_id: int) -> Optional[Dict]:
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM config_templates WHERE id=?", (template_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def template_create(name: str, description: str, template_text: str, variables: str = "{}") -> int:
    conn = get_db_connection()
    c = conn.execute(
        "INSERT INTO config_templates (name, description, template_text, variables) VALUES (?,?,?,?)",
        (name, description, template_text, variables),
    )
    conn.commit()
    tid = c.lastrowid
    conn.close()
    return tid

def template_update(template_id: int, **kwargs):
    conn = get_db_connection()
    sets = [f"{k}=?" for k in kwargs]
    vals = list(kwargs.values()) + [template_id]
    conn.execute(f"UPDATE config_templates SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    conn.close()

def template_delete(template_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM config_templates WHERE id=?", (template_id,))
    conn.commit()
    conn.close()


# ══════ 端口分配台账 ══════

def port_assignment_list(device_id: int = None) -> List[Dict]:
    conn = get_db_connection()
    if device_id:
        rows = conn.execute("SELECT * FROM port_assignments WHERE device_id=? ORDER BY if_name", (device_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM port_assignments ORDER BY device_id, if_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def port_assignment_set(device_id: int, if_name: str, connected_device: str, connected_port: str, description: str = ""):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT id FROM port_assignments WHERE device_id=? AND if_name=?", (device_id, if_name)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE port_assignments SET connected_device=?, connected_port=?, description=? WHERE id=?",
            (connected_device, connected_port, description, row["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO port_assignments (device_id, if_name, connected_device, connected_port, description) VALUES (?,?,?,?,?)",
            (device_id, if_name, connected_device, connected_port, description),
        )
    conn.commit()
    conn.close()


# ══════ 变更审计 ══════

def audit_log(action: str, device_id: int = None, detail: str = ""):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO audit_logs (device_id, action, detail) VALUES (?,?,?)",
        (device_id, action, detail),
    )
    conn.commit()
    conn.close()

def audit_list(limit: int = 100) -> List[Dict]:
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ══════ VLAN 台账 ══════

def vlan_registry_list(device_id: int = None) -> List[Dict]:
    conn = get_db_connection()
    if device_id:
        rows = conn.execute("SELECT * FROM vlan_registry WHERE device_id=? ORDER BY vlan_id", (device_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM vlan_registry ORDER BY device_id, vlan_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def vlan_registry_sync(device_id: int, vlans: List[Dict]):
    """同步设备 VLAN 到台账（增新不删旧）"""
    conn = get_db_connection()
    existing = {r["vlan_id"] for r in conn.execute(
        "SELECT vlan_id FROM vlan_registry WHERE device_id=?", (device_id,)
    ).fetchall()}
    for v in vlans:
        vid = int(v.get("vlan_id", 0))
        name = v.get("name", "")
        if vid in existing:
            conn.execute(
                "UPDATE vlan_registry SET name=? WHERE device_id=? AND vlan_id=?",
                (name, device_id, vid),
            )
        else:
            conn.execute(
                "INSERT INTO vlan_registry (device_id, vlan_id, name) VALUES (?,?,?)",
                (device_id, vid, name),
            )
    conn.commit()
    conn.close()

def vlan_registry_update(vlan_reg_id: int, **kwargs):
    conn = get_db_connection()
    sets = [f"{k}=?" for k in kwargs]
    vals = list(kwargs.values()) + [vlan_reg_id]
    conn.execute(f"UPDATE vlan_registry SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    conn.close()


# ══════ 设备状态 ══════

def set_device_status(device_id: int, status: str):
    conn = get_db_connection()
    conn.execute("UPDATE devices SET status=? WHERE id=?", (status, device_id))
    conn.commit()
    conn.close()
