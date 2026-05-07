"""设备驱动工厂"""

from driver.base import DeviceDriver
from driver.h3c_ssh import H3CSSHDriver
from driver.h3c_snmp import H3CSNMPDriver


def get_driver(device_config: dict, prefer_snmp: bool = True) -> DeviceDriver:
    """采集驱动：SNMP 优先，SSH 兜底"""
    device_type = device_config.get("device_type", "hp_comware")

    if device_type == "hp_comware":
        if prefer_snmp and device_config.get("snmp_community"):
            return H3CSNMPDriver(device_config)
        return H3CSSHDriver(device_config)

    raise ValueError(f"Unsupported device type: {device_type}")


def get_ssh_driver(device_config: dict) -> H3CSSHDriver:
    """获取 SSH 驱动（用于配置下发和 fallback）"""
    return H3CSSHDriver(device_config)


def get_config_driver(device_config: dict) -> DeviceDriver:
    """
    配置下发驱动：NETCONF 优先，SSH 兜底。
    先试 NETCONF 连接，失败自动退 SSH。
    """
    device_type = device_config.get("device_type", "hp_comware")
    if device_type != "hp_comware":
        return H3CSSHDriver(device_config)

    try:
        from driver.h3c_netconf import H3CNETCONFDriver
        driver = H3CNETCONFDriver(device_config)
        driver.connect()
        driver.disconnect()  # 仅测试连通性
        return H3CNETCONFDriver(device_config)
    except Exception:
        return H3CSSHDriver(device_config)
