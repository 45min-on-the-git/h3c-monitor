"""H3C Comware SNMPv2c 驱动 (pysnmp 7.x)"""

import re
from typing import Dict, List, Optional, Any, Tuple

from pysnmp.hlapi.v1arch import (
    CommunityData,
    ObjectIdentity,
    ObjectType,
    SnmpDispatcher,
    UdpTransportTarget,
    get_cmd,
    next_cmd,
)

# ── OID 映射 ──

OID = {
    # 系统
    "sysDescr": "1.3.6.1.2.1.1.1.0",
    "sysUpTime": "1.3.6.1.2.1.1.3.0",
    "sysName": "1.3.6.1.2.1.1.5.0",
    # H3C 私有 — CPU / 内存 / 温度
    "hh3cCpuUsage": "1.3.6.1.4.1.25506.2.6.1.1.1.1.6",
    "hh3cMemUsage": "1.3.6.1.4.1.25506.2.6.1.1.1.1.8",
    "hh3cTemperature": "1.3.6.1.4.1.25506.2.6.1.1.1.1.12",
    # IF-MIB
    "ifDescr": "1.3.6.1.2.1.2.2.1.2",
    "ifOperStatus": "1.3.6.1.2.1.2.2.1.8",
    "ifHCInOctets": "1.3.6.1.2.1.31.1.1.1.6",
    "ifHCOutOctets": "1.3.6.1.2.1.31.1.1.1.10",
    "ifSpeed": "1.3.6.1.2.1.2.2.1.5",
    "ifHighSpeed": "1.3.6.1.2.1.31.1.1.1.15",
    "hh3cSessions": "1.3.6.1.4.1.25506.2.4.1.1.1.0",
}


from driver.base import DeviceDriver, DeviceInfo, MetricsResult, InterfaceData


class H3CSNMPDriver(DeviceDriver):
    """H3C Comware SNMPv2c 驱动"""

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._community = device_config.get("snmp_community", "public")
        self._timeout = 3
        self._retries = 1
        self._engine = SnmpDispatcher()
        self._connected = False

    def connect(self) -> None:
        result = self._get(OID["sysDescr"])
        if result is None:
            raise RuntimeError(f"SNMP unreachable: {self.config['ip']}")
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def execute_command(self, command: str, **kwargs) -> str:
        raise NotImplementedError("SNMP driver: use SSH for CLI")

    def execute_commands(self, commands: List[str]) -> str:
        raise NotImplementedError("SNMP driver: use SSH for config")

    # ── 采集 ──

    def collect_device_info(self) -> DeviceInfo:
        info = DeviceInfo(
            ip=self.ip,
            device_category=self.device_category,
            hostname=self.config.get("device_name", ""),
        )
        desc = self._get(OID["sysDescr"])
        if desc:
            info.model = self._extract_model(str(desc))
            info.sw_version = self._extract_version(str(desc))
        name = self._get(OID["sysName"])
        if name:
            info.hostname = str(name)
        return info

    def collect_metrics(self) -> MetricsResult:
        result = MetricsResult()

        cpus = self._walk_float(OID["hh3cCpuUsage"])
        if cpus:
            result.cpu_usage = round(sum(cpus) / len(cpus), 1)

        mems = self._walk_float(OID["hh3cMemUsage"])
        if mems:
            result.mem_usage = round(sum(mems) / len(mems), 1)

        temps = self._walk_float(OID["hh3cTemperature"])
        if temps:
            result.temperature = round(sum(temps) / len(temps), 1)

        upt = self._get(OID["sysUpTime"])
        if upt is not None:
            result.uptime = self._ticks_str(upt)

        if self.device_category == "firewall":
            sess = self._get(OID["hh3cSessions"])
            if sess is not None:
                result.session_count = int(sess)

        return result

    def collect_interfaces(self) -> List[InterfaceData]:
        if_names = self._walk_table(OID["ifDescr"])
        if_statuses = self._walk_table(OID["ifOperStatus"])
        in_octets = self._walk_table(OID["ifHCInOctets"])
        out_octets = self._walk_table(OID["ifHCOutOctets"])
        speeds = self._walk_table(OID["ifHighSpeed"])
        if not speeds:
            speeds = self._walk_table(OID["ifSpeed"])

        interfaces = []
        for idx, name in if_names.items():
            iface = InterfaceData(
                if_name=str(name) if name else f"if{idx}",
                status="UP" if if_statuses.get(idx) == 1 else "DOWN",
                in_bytes=int(in_octets.get(idx, 0)),
                out_bytes=int(out_octets.get(idx, 0)),
            )
            s = speeds.get(idx, 0)
            if s:
                iface.if_speed = int(s) if s > 1000 else int(s) * 1000000
            interfaces.append(iface)

        return interfaces

    # ── SNMP 底层 ──

    def _target(self):
        return UdpTransportTarget(
            (self.config["ip"], 161),
            timeout=self._timeout,
            retries=self._retries,
        )

    def _auth(self):
        return CommunityData(self._community, mpModel=1)

    def _get(self, oid: str):
        """GET 单个 OID"""
        try:
            err_ind, err_st, err_idx, var_binds = get_cmd(
                self._engine,
                self._auth(),
                self._target(),
                ObjectType(ObjectIdentity(oid)),
            )
            if err_ind or err_st:
                return None
            if var_binds:
                val = var_binds[0][1]
                return val if val is not None else None
            return None
        except Exception:
            return None

    def _walk_float(self, oid: str) -> List[float]:
        """WALK OID 子树，返回 float 列表"""
        values = []
        try:
            for err_ind, err_st, err_idx, var_binds in next_cmd(
                self._engine,
                self._auth(),
                self._target(),
                ObjectType(ObjectIdentity(oid)),
            ):
                if err_ind or err_st:
                    break
                for vb in var_binds:
                    val = vb[1]
                    if val is not None:
                        try:
                            values.append(float(val))
                        except (ValueError, TypeError):
                            pass
        except Exception:
            pass
        return values

    def _walk_table(self, oid: str) -> Dict[int, Any]:
        """WALK 表，返回 {index: value}"""
        result = {}
        prefix = oid.rstrip(".0") + "."
        try:
            for err_ind, err_st, err_idx, var_binds in next_cmd(
                self._engine,
                self._auth(),
                self._target(),
                ObjectType(ObjectIdentity(oid)),
            ):
                if err_ind or err_st:
                    break
                for vb in var_binds:
                    oid_str = str(vb[0])
                    if oid_str.startswith(prefix):
                        try:
                            idx = int(oid_str[len(prefix):].rstrip("."))
                        except ValueError:
                            continue
                        result[idx] = vb[1]
        except Exception:
            pass
        return result

    # ── 解析 ──

    @staticmethod
    def _extract_model(desc: str) -> Optional[str]:
        m = re.search(r"(?:H3C\s+)?([A-Z]+-?\d+\S*)", desc)
        return m.group(1) if m else desc[:80]

    @staticmethod
    def _extract_version(desc: str) -> Optional[str]:
        m = re.search(r"Version\s+([\d.]+)", desc)
        return m.group(1) if m else None

    @staticmethod
    def _ticks_str(ticks) -> str:
        t = int(ticks) // 100
        d = t // 86400
        h = (t % 86400) // 3600
        m = (t % 3600) // 60
        parts = []
        if d:
            parts.append(f"{d}d")
        if h:
            parts.append(f"{h}h")
        if m:
            parts.append(f"{m}m")
        return " ".join(parts) if parts else f"{t}s"
