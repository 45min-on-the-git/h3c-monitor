"""告警引擎测试"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import alarm
import config


def setup_module():
    """使用临时文件数据库，确保连接间共享"""
    config.DB_PATH = tempfile.mktemp(suffix=".db")  # alarm 也用 config.DB_PATH
    alarm.config.DB_PATH = config.DB_PATH

    # 建表
    conn = alarm.get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_type TEXT, ip TEXT, hostname TEXT, model TEXT, sw_version TEXT
    );
    CREATE TABLE IF NOT EXISTS alarm_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL, metric TEXT NOT NULL,
        operator TEXT DEFAULT '>', threshold REAL NOT NULL, enabled INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS alarms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL, rule_id INTEGER, metric TEXT NOT NULL,
        value REAL, threshold REAL, status TEXT DEFAULT 'active',
        triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP, resolved_at DATETIME
    );
    """)
    conn.execute("INSERT INTO devices (device_type, ip) VALUES ('switch', '10.0.0.1')")
    conn.commit()
    conn.close()


def teardown_module():
    try:
        os.unlink(config.DB_PATH)
    except OSError:
        pass


def test_create_rule():
    rid = alarm.create_rule(1, "cpu_usage", ">", 80.0)
    assert rid > 0

    rules = alarm.get_rules(1)
    assert len(rules) >= 1
    r = rules[-1]
    assert r["metric"] == "cpu_usage"
    assert r["threshold"] == 80.0


def test_trigger_on_cpu_high():
    rid = alarm.create_rule(1, "cpu_usage", ">", 80.0)
    alarm.check_and_trigger(1, {"cpu_usage": 95.0})
    alarms = alarm.get_alarms(status="active")
    assert len(alarms) >= 1
    a = alarms[0]
    assert a["metric"] == "cpu_usage"
    assert a["value"] == 95.0
    assert a["threshold"] == 80.0
    assert a["status"] == "active"


def test_no_duplicate_active():
    alarm.create_rule(1, "cpu_usage", ">", 80.0)
    alarm.check_and_trigger(1, {"cpu_usage": 90.0})
    count_before = len(alarm.get_alarms(status="active"))
    alarm.check_and_trigger(1, {"cpu_usage": 95.0})
    count_after = len(alarm.get_alarms(status="active"))
    assert count_after == count_before


def test_auto_resolve():
    alarm.create_rule(1, "cpu_usage", ">", 80.0)
    alarm.check_and_trigger(1, {"cpu_usage": 90.0})
    assert len(alarm.get_alarms(status="active")) >= 1

    alarm.check_and_trigger(1, {"cpu_usage": 50.0})
    assert len(alarm.get_alarms(status="active")) == 0
    assert len(alarm.get_alarms(status="resolved")) >= 1


def test_disabled_rule_not_checked():
    """禁用规则不触发告警（只检查本规则的告警数）"""
    rid = alarm.create_rule(1, "cpu_usage", ">", 80.0)
    alarm.update_rule(rid, enabled=0)

    # 统计此规则已有的 active 告警
    all_active = alarm.get_alarms(status="active")
    rule_active_before = len([a for a in all_active if a.get("rule_id") == rid])

    alarm.check_and_trigger(1, {"cpu_usage": 99.0})

    all_active_after = alarm.get_alarms(status="active")
    rule_active_after = len([a for a in all_active_after if a.get("rule_id") == rid])

    assert rule_active_after == rule_active_before


def test_acknowledge_alarm():
    alarm.create_rule(1, "cpu_usage", ">", 80.0)
    alarm.check_and_trigger(1, {"cpu_usage": 90.0})
    active_alarms = alarm.get_alarms(status="active")
    assert len(active_alarms) >= 1

    alarm.acknowledge_alarm(active_alarms[0]["id"])
    acked = alarm.get_alarms(status="acknowledged")
    assert len(acked) >= 1
