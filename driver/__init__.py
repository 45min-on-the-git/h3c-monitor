"""设备驱动工厂"""

from driver.base import DeviceDriver
from driver.h3c_ssh import H3CSSHDriver
from driver.h3c_snmp import H3CSNMPDriver


def get_driver(device_config: dict, prefer_snmp: bool = True) -> DeviceDriver:
    """
    返回合适的驱动实例。
    - prefer_snmp=True: 优先 SNMP，当前仅 H3C
    - prefer_snmp=False: 返回 SSH 驱动
    """
    device_type = device_config.get("device_type", "hp_comware")

    if device_type == "hp_comware":
        if prefer_snmp and device_config.get("snmp_community"):
            return H3CSNMPDriver(device_config)
        return H3CSSHDriver(device_config)

    raise ValueError(f"Unsupported device type: {device_type}")


def get_ssh_driver(device_config: dict) -> H3CSSHDriver:
    """获取 SSH 驱动（用于 fallback 和配置下发）"""
    return H3CSSHDriver(device_config)
