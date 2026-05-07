"""H3C Comware SSH 驱动"""

import re
from typing import Dict, List, Optional, Any

from netmiko import ConnectHandler
from driver.base import DeviceDriver, DeviceInfo, MetricsResult, InterfaceData


class H3CSSHDriver(DeviceDriver):
    """H3C Comware 设备 SSH 驱动"""

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._connection = None

    def connect(self) -> None:
        netconf = {
            "device_type": self.config.get("device_type", "hp_comware"),
            "host": self.config["ip"],
            "username": self.config["username"],
            "password": self.config["password"],
            "timeout": 10,
            "session_timeout": 10,
        }
        self._connection = ConnectHandler(**netconf)
        self._connection.enable()

    def disconnect(self) -> None:
        if self._connection:
            self._connection.disconnect()
            self._connection = None

    def execute_command(self, command: str, read_timeout: int = 30) -> str:
        if not self._connection:
            raise RuntimeError("Not connected")
        return self._connection.send_command(command, read_timeout=read_timeout)

    def execute_commands(self, commands: List[str]) -> str:
        if not self._connection:
            raise RuntimeError("Not connected")
        return self._connection.send_config_set(commands)

    # ── 采集 ──

    def collect_device_info(self) -> DeviceInfo:
        output = self.execute_command("display version", read_timeout=30)
        info = DeviceInfo(
            ip=self.ip,
            device_category=self.device_category,
            hostname=self.config.get("device_name", ""),
        )
        # 型号
        m = re.search(r"Model\s*:\s*(.+)", output, re.IGNORECASE)
        if not m:
            m = re.search(r"SoftWare Version\s*:\s*(.+)", output)
        if m:
            info.model = m.group(1).strip()
        # 版本
        m = re.search(r"SoftWare Version\s*:\s*(.+)", output)
        if not m:
            m = re.search(r"Version\s*:\s*(.+?)(?:\n|$)", output)
        if m:
            info.sw_version = m.group(1).strip()
        return info

    def collect_metrics(self) -> MetricsResult:
        result = MetricsResult()

        # 运行时间 (从 display version)
        ver = self.execute_command("display version", read_timeout=30)
        m = re.search(r"uptime is\s*([\d\w,\s]+)", ver, re.IGNORECASE)
        if m:
            result.uptime = m.group(1).strip()

        # CPU
        cpu = self.execute_command("display cpu-usage", read_timeout=30)
        result.cpu_usage = self._parse_cpu(cpu)

        # 内存
        mem = self.execute_command("display memory", read_timeout=30)
        result.mem_usage = self._parse_memory(mem)

        # 温度
        env = self.execute_command("display environment", read_timeout=30)
        result.temperature = self._parse_temperature(env)

        # 防火墙会话
        if self.device_category == "firewall":
            sess = self.execute_command("display session statistics ipv4", read_timeout=30)
            result.session_count = self._parse_sessions(sess)

        return result

    def collect_interfaces(self) -> List[InterfaceData]:
        result: List[InterfaceData] = []

        # display interface brief: 接口名 + 状态
        brief = self.execute_command("display interface brief", read_timeout=30)
        for line in brief.strip().split("\n"):
            m = re.match(
                r"\s*(GE\d+/\d+|H?GE\d+/\d+/\d+|MEth\d+/0/0|MGE\d+/\d+/\d+|InLoop\d+|NULL\d+|REG\d+)",
                line,
            )
            if m:
                parts = line.split()
                status = parts[1] if len(parts) > 1 else "DOWN"
                result.append(InterfaceData(
                    if_name=m.group(1),
                    status="UP" if status.upper() == "UP" else "DOWN",
                ))

        # display interface: 流量字节
        detail = self.execute_command("display interface", read_timeout=60)
        result = self._merge_interface_bytes(result, detail.strip().split("\n"))

        return result

    # ── 解析内部方法 ──

    def _parse_cpu(self, output: str) -> Optional[float]:
        for pat in [
            r"(\d+)%\s+in\s+last\s+5\s+seconds?",
            r"(\d+)%\s+in\s+last\s+5\s+secs?",
            r"last\s+5\s+seconds?.*?(\d+)%",
        ]:
            m = re.search(pat, output, re.IGNORECASE)
            if m:
                return float(m.group(1))
        return None

    def _parse_memory(self, output: str) -> Optional[float]:
        # FreeRatio
        m = re.search(r"FreeRatio\s*(\d+\.?\d*)%", output, re.IGNORECASE)
        if m:
            return round(100 - float(m.group(1)), 2)
        # Total / Used
        m = re.search(r"Mem:\s+(\d+)\s+(\d+)\s+(\d+)", output)
        if m:
            total, used = int(m.group(1)), int(m.group(2))
            if total > 0:
                return round((used / total) * 100, 2)
        # Usage: xx%
        m = re.search(r"Usage:\s*(\d+\.?\d*)%", output, re.IGNORECASE)
        if m:
            return float(m.group(1))
        return None

    def _parse_temperature(self, output: str) -> Optional[float]:
        m = re.search(r"Temperature\s*:\s*(\d+\.?\d*)\s*°?C", output, re.IGNORECASE)
        if m:
            return float(m.group(1))
        m = re.search(r"(\d+\.?\d*)\s*°?C", output)
        if m:
            return float(m.group(1))
        return None

    def _parse_sessions(self, output: str) -> Optional[int]:
        for pat in [r"Current\s+Sessions?:?\s*(\d+)", r"Number\s+of\s+sessions:\s*(\d+)"]:
            m = re.search(pat, output, re.IGNORECASE)
            if m:
                return int(m.group(1))
        return None

    def _merge_interface_bytes(
        self, interfaces: List[InterfaceData], lines: List[str]
    ) -> List[InterfaceData]:
        """从 display interface 详细输出合并流量字节到已有接口列表"""
        current_name = None
        in_bytes = 0
        out_bytes = 0

        detail_ifaces: Dict[str, InterfaceData] = {}

        for line in lines:
            line = line.strip()
            # 匹配详细接口名
            m = re.match(
                r"(Ten-GigabitEthernet\d+/\d+/\d+|GigabitEthernet\d+/\d+/\d+|Ethernet\d+/\d+|Vlan-interface\d+|MEth\d+)",
                line,
            )
            if m:
                if current_name and (in_bytes > 0 or out_bytes > 0):
                    detail_ifaces[current_name] = InterfaceData(
                        if_name=current_name, status="UP",
                        in_bytes=in_bytes, out_bytes=out_bytes,
                    )
                current_name = m.group(1)
                in_bytes = 0
                out_bytes = 0
                continue

            mi = re.search(r"Input:\s*(\d+)\s*Bytes", line)
            if mi:
                in_bytes = int(mi.group(1))
            mo = re.search(r"Output:\s*(\d+)\s*Bytes", line)
            if mo:
                out_bytes = int(mo.group(1))

        if current_name and (in_bytes > 0 or out_bytes > 0):
            detail_ifaces[current_name] = InterfaceData(
                if_name=current_name, status="UP",
                in_bytes=in_bytes, out_bytes=out_bytes,
            )

        # 合并到 brief 列表：按名称模糊匹配
        for iface in interfaces:
            for dname, di in detail_ifaces.items():
                if iface.if_name.replace("/", "") in dname.replace("/", ""):
                    iface.in_bytes = di.in_bytes
                    iface.out_bytes = di.out_bytes
                    break

        return interfaces

    # ── ACL 操作 ──

    def get_acls(self) -> List[Dict]:
        """读取设备 ACL 配置，解析为规则列表"""
        output = self.execute_command("display acl all", read_timeout=30)
        return self._parse_acls(output)

    def create_acl_rule(self, acl_number: int, rule_id: int, action: str,
                        protocol: str = "ip", source: str = "any",
                        destination: str = "any", description: str = "") -> str:
        """创建 ACL 规则（通过 SSH 下发）"""
        cmds = []
        # 如果 ACL 不存在，先创建
        cmds.append(f"acl advanced {acl_number}")
        src_clause = f" source {source}" if source and source != "any" else ""
        dst_clause = f" destination {destination}" if destination and destination != "any" else ""
        desc_clause = f" description {description}" if description else ""
        cmds.append(
            f"rule {rule_id} {action} {protocol}{src_clause}{dst_clause}{desc_clause}"
        )
        return self.execute_commands(cmds)

    def delete_acl_rule(self, acl_number: int, rule_id: int) -> str:
        """删除 ACL 规则"""
        return self.execute_commands([
            f"acl advanced {acl_number}",
            f"undo rule {rule_id}",
        ])

    def apply_acl_to_interface(self, acl_number: int, if_name: str,
                               direction: str = "inbound") -> str:
        """将 ACL 应用到接口"""
        return self.execute_commands([
            f"interface {if_name}",
            f"packet-filter {acl_number} {direction}",
        ])

    def _parse_acls(self, output: str) -> List[Dict]:
        """解析 display acl all 输出"""
        rules = []
        current_acl = None
        for line in output.split("\n"):
            line = line.strip()
            # 匹配 ACL 头部：Advanced ACL 3000
            m = re.match(r"Advanced\s+ACL\s+(\d+)", line, re.IGNORECASE)
            if m:
                current_acl = int(m.group(1))
                continue
            m = re.match(r"Basic\s+ACL\s+(\d+)", line, re.IGNORECASE)
            if m:
                current_acl = int(m.group(1))
                continue
            # 匹配规则：rule 5 permit tcp source 192.168.1.0 0.0.0.255 destination any
            if current_acl:
                m = re.match(
                    r"rule\s+(\d+)\s+(permit|deny)\s+(\S+)(.*)",
                    line, re.IGNORECASE,
                )
                if m:
                    rule_id = int(m.group(1))
                    action = m.group(2).lower()
                    protocol = m.group(3).lower()
                    rest = m.group(4)
                    source = "any"
                    destination = "any"
                    src_m = re.search(r"source\s+(\S+(?:\s+\S+)?)", rest)
                    if src_m:
                        source = src_m.group(1).strip()
                    dst_m = re.search(r"destination\s+(\S+(?:\s+\S+)?)", rest)
                    if dst_m:
                        destination = dst_m.group(1).strip()
                    rules.append({
                        "acl_number": current_acl,
                        "rule_id": rule_id,
                        "action": action,
                        "protocol": protocol,
                        "source": source,
                        "destination": destination,
                    })
        return rules
