"""数据库操作测试"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import database


def setup_module():
    """使用临时文件数据库"""
    config.DB_PATH = tempfile.mktemp(suffix=".db")
    database.init_db()


def teardown_module():
    try:
        os.unlink(config.DB_PATH)
    except OSError:
        pass


def test_init_db():
    database.init_db()  # 重复调用不报错


def test_get_or_create_device():
    info = {
        "ip": "10.0.0.1",
        "device_category": "switch",
        "hostname": "test-sw",
        "model": "S5560",
        "sw_version": "7.1.070",
    }
    id1 = database.get_or_create_device(info)
    assert id1 > 0

    info["model"] = "S5590"
    id2 = database.get_or_create_device(info)
    assert id2 == id1

    devices = database.get_devices()
    assert len(devices) == 1
    assert devices[0]["model"] == "S5590"


def test_save_and_get_metrics():
    info = {"ip": "10.0.0.2", "device_category": "switch"}
    device_id = database.get_or_create_device(info)

    database.save_metrics(device_id, {
        "cpu_usage": 45.2, "mem_usage": 60.1, "temperature": 35.0,
        "session_count": None, "uptime": "1 days 3 hours",
    })

    latest = database.get_latest_metrics(device_id)
    assert latest is not None
    assert latest["cpu_usage"] == 45.2

    history = database.get_metrics(device_id=device_id)
    assert len(history) >= 1


def test_update_device_info():
    info = {"ip": "10.0.0.3", "device_category": "firewall"}
    device_id = database.get_or_create_device(info)

    database.update_device_info(device_id, {
        "device_name": "fw-core",
        "serial_number": "SN-12345",
        "location": "A1",
        "rack": "R03",
        "warranty_expiry": "2027-12-31",
        "supplier": "H3C",
    })

    devices = database.get_devices()
    d = next((x for x in devices if x["id"] == device_id), None)
    assert d is not None
    assert d["hostname"] == "fw-core"
    assert d["serial_number"] == "SN-12345"
    assert d["location"] == "A1"


def test_create_device_manual():
    device_id = database.create_device_manual({
        "ip": "10.0.0.4",
        "device_category": "switch",
        "device_name": "sw-edge",
        "model": "S5130",
        "location": "B2",
    })

    devices = database.get_devices()
    d = next((x for x in devices if x["id"] == device_id), None)
    assert d is not None
    assert d["ip"] == "10.0.0.4"
    assert d["hostname"] == "sw-edge"
