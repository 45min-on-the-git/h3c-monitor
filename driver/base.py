"""设备驱动抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class DeviceInfo:
    """设备基本信息"""
    hostname: str = ""
    model: str = ""
    sw_version: str = ""
    ip: str = ""
    device_category: str = "switch"


@dataclass
class MetricsResult:
    """采集指标结果"""
    cpu_usage: Optional[float] = None
    mem_usage: Optional[float] = None
    temperature: Optional[float] = None
    uptime: Optional[str] = None
    session_count: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InterfaceData:
    """接口数据"""
    if_name: str = ""
    status: str = "DOWN"
    in_bytes: int = 0
    out_bytes: int = 0
    in_util: float = 0.0
    out_util: float = 0.0
    if_speed: int = 0  # bps


class DeviceDriver(ABC):
    """设备驱动抽象基类"""

    def __init__(self, device_config: Dict[str, Any]):
        self.config = device_config
        self.ip = device_config.get("ip", "")
        self.device_category = device_config.get("device_category", "switch")

    @abstractmethod
    def connect(self) -> None:
        """建立设备连接"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """断开设备连接"""
        pass

    @abstractmethod
    def collect_device_info(self) -> DeviceInfo:
        """采集设备基本信息（型号、版本、主机名等）"""
        pass

    @abstractmethod
    def collect_metrics(self) -> MetricsResult:
        """采集设备运行指标（CPU、内存、温度等）"""
        pass

    @abstractmethod
    def collect_interfaces(self) -> List[InterfaceData]:
        """采集接口状态与流量"""
        pass

    @abstractmethod
    def execute_command(self, command: str) -> str:
        """执行 CLI 命令并返回输出"""
        pass

    @abstractmethod
    def execute_commands(self, commands: List[str]) -> str:
        """批量执行配置命令"""
        pass

    def collect_all(self) -> Dict[str, Any]:
        """一次性采集全部数据（兼容旧接口）"""
        try:
            self.connect()
            device_info = self.collect_device_info()
            metrics = self.collect_metrics()
            interfaces = self.collect_interfaces()
            self.disconnect()

            return {
                "success": True,
                "data": {
                    "device_category": self.device_category,
                    "hostname": device_info.hostname,
                    "ip": self.ip,
                    "model": device_info.model,
                    "sw_version": device_info.sw_version,
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
                        }
                        for i in interfaces
                    ],
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e), "data": {}}
