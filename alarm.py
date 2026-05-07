"""告警规则引擎"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Any
import config


def get_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ══════ 规则管理 ══════

def get_rules(device_id: int = None) -> List[Dict]:
    """获取告警规则"""
    conn = get_db()
    if device_id:
        rows = conn.execute(
            "SELECT * FROM alarm_rules WHERE device_id=? ORDER BY metric", (device_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM alarm_rules ORDER BY device_id, metric").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_rule(device_id: int, metric: str, operator: str, threshold: float) -> int:
    """创建告警规则"""
    conn = get_db()
    c = conn.execute(
        "INSERT INTO alarm_rules (device_id, metric, operator, threshold, enabled) VALUES (?, ?, ?, ?, 1)",
        (device_id, metric, operator, threshold),
    )
    conn.commit()
    rid = c.lastrowid
    conn.close()
    return rid


def update_rule(rule_id: int, **kwargs) -> bool:
    """更新告警规则"""
    conn = get_db()
    sets = [f"{k}=?" for k in kwargs]
    vals = list(kwargs.values()) + [rule_id]
    conn.execute(f"UPDATE alarm_rules SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return True


def delete_rule(rule_id: int) -> bool:
    conn = get_db()
    conn.execute("DELETE FROM alarm_rules WHERE id=?", (rule_id,))
    conn.execute("UPDATE alarms SET rule_id=NULL WHERE rule_id=?", (rule_id,))
    conn.commit()
    conn.close()
    return True


# ══════ 告警记录 ══════

def get_alarms(status: str = None, device_id: int = None, limit: int = 200) -> List[Dict]:
    conn = get_db()
    q = "SELECT * FROM alarms WHERE 1=1"
    params = []
    if status:
        q += " AND status=?"
        params.append(status)
    if device_id:
        q += " AND device_id=?"
        params.append(device_id)
    q += " ORDER BY triggered_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def acknowledge_alarm(alarm_id: int) -> bool:
    conn = get_db()
    conn.execute(
        "UPDATE alarms SET status='acknowledged' WHERE id=? AND status='active'",
        (alarm_id,),
    )
    conn.commit()
    conn.close()
    return True


def resolve_alarm(alarm_id: int) -> bool:
    conn = get_db()
    conn.execute(
        "UPDATE alarms SET status='resolved', resolved_at=? WHERE id=? AND status IN ('active','acknowledged')",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), alarm_id),
    )
    conn.commit()
    conn.close()
    return True


# ══════ 告警检查 ══════

def check_and_trigger(device_id: int, metrics: Dict[str, Any]):
    """采集完成后检查告警规则，触发告警并自动恢复"""
    rules = get_rules(device_id)

    for rule in rules:
        if not rule.get("enabled"):
            continue

        metric = rule["metric"]
        value = metrics.get(metric)
        if value is None:
            continue

        threshold = rule["threshold"]
        op = rule.get("operator", ">")

        triggered = False
        if op == ">" and value > threshold:
            triggered = True
        elif op == "<" and value < threshold:
            triggered = True
        elif op == ">=" and value >= threshold:
            triggered = True
        elif op == "<=" and value <= threshold:
            triggered = True
        elif op == "==" and value == threshold:
            triggered = True

        if triggered:
            _fire_alarm(device_id, rule["id"], metric, value, threshold)
        else:
            _auto_resolve(device_id, rule["id"])


def _fire_alarm(device_id: int, rule_id: int, metric: str, value: float, threshold: float):
    """触发告警（如果已有 active 则忽略）"""
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM alarms WHERE device_id=? AND rule_id=? AND metric=? AND status='active'",
        (device_id, rule_id, metric),
    ).fetchone()
    if existing:
        conn.close()
        return

    conn.execute(
        "INSERT INTO alarms (device_id, rule_id, metric, value, threshold, status) VALUES (?, ?, ?, ?, ?, 'active')",
        (device_id, rule_id, metric, value, threshold),
    )
    conn.commit()
    conn.close()


def _auto_resolve(device_id: int, rule_id: int):
    """指标恢复正常 → 自动 resolve"""
    conn = get_db()
    conn.execute(
        "UPDATE alarms SET status='resolved', resolved_at=? WHERE device_id=? AND rule_id=? AND status='active'",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), device_id, rule_id),
    )
    conn.commit()
    conn.close()
