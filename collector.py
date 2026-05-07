# 采集器模块 — SNMP 优先，SSH 兜底
from typing import Dict, List, Any
import config
from driver import get_driver, get_ssh_driver


def collect_device_data(device_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    采集单台设备数据。
    SNMP 优先，失败时自动退回到 SSH。
    """
    errors = []

    # ── 第1次尝试：SNMP ──
    try:
        snmp_driver = get_driver(device_config, prefer_snmp=True)
        return _collect_via_driver(snmp_driver, device_config)
    except Exception as e:
        errors.append(f"SNMP: {e}")

    # ── 第2次尝试：SSH 兜底 ──
    try:
        ssh_driver = get_ssh_driver(device_config)
        return _collect_via_driver(ssh_driver, device_config)
    except Exception as e:
        errors.append(f"SSH: {e}")

    return {
        "success": False,
        "error": " | ".join(errors),
        "data": {},
    }


def _collect_via_driver(driver, device_config: Dict[str, Any]) -> Dict[str, Any]:
    """通过某个驱动完成整套采集"""
    try:
        driver.connect()

        info = driver.collect_device_info()
        metrics = driver.collect_metrics()
        interfaces = driver.collect_interfaces()

        driver.disconnect()

        return {
            "success": True,
            "data": {
                "device_category": device_config.get("device_category", "switch"),
                "hostname": info.hostname or device_config.get("device_name", ""),
                "ip": device_config["ip"],
                "model": info.model,
                "sw_version": info.sw_version,
                "uptime": metrics.uptime,
                "cpu_usage": metrics.cpu_usage,
                "mem_usage": metrics.mem_usage,
                "temperature": metrics.temperature,
                "session_count": metrics.session_count,
                "interfaces": [
                    {
                        "if_name": i.if_name,
                        "status": i.status,
                        "in_bytes": i.in_bytes,
                        "out_bytes": i.out_bytes,
                        "in_util": i.in_util,
                        "out_util": i.out_util,
                        "if_speed": getattr(i, "if_speed", 0),
                    }
                    for i in interfaces
                ],
            },
        }
    except Exception as e:
        driver.disconnect()
        raise


def collect_all_devices() -> List[Dict[str, Any]]:
    """采集所有设备"""
    results = []
    for device_config in config.DEVICE_LIST:
        print(f"Collecting data from {device_config['ip']}...")
        result = collect_device_data(device_config)
        results.append(result)
        if result["success"]:
            print(f"  OK {device_config['ip']}")
        else:
            print(f"  FAIL {device_config['ip']}: {result['error']}")
    return results
