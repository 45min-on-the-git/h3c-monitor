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
                r"\s*([HX]?GE\d+/\d+/\d+|GE\d+/\d+|MEth\d+/0/0|MGE\d+/\d+/\d+|InLoop\d+|NULL\d+|REG\d+)",
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
                r"(Ten-GigabitEthernet\d+/\d+/\d+|GigabitEthernet\d+/\d+/\d+|FortyGigE\d+/\d+/\d+|HundredGigE\d+/\d+/\d+|Ethernet\d+/\d+|Vlan-interface\d+|MEth\d+)",
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

        # 合并到 brief 列表：提取接口编号（如 1/0/1）精确匹配
        def _if_index(name: str) -> str:
            m = re.match(r"[A-Za-z-]+(.+)", name)
            return m.group(1) if m else name

        for iface in interfaces:
            idx = _if_index(iface.if_name)
            for dname, di in detail_ifaces.items():
                if idx == _if_index(dname):
                    iface.in_bytes = di.in_bytes
                    iface.out_bytes = di.out_bytes
                    # 尝试从 detail 补全 if_speed
                    if di.if_speed:
                        iface.if_speed = di.if_speed
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
        """创建 ACL 规则（通过 SSH 下发，Comware V7 语法）"""
        cmds = [
            f"acl number {acl_number}",
        ]
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
            f"acl number {acl_number}",
            f"undo rule {rule_id}",
        ])

    def apply_acl_to_interface(self, acl_number: int, if_name: str,
                               direction: str = "inbound") -> str:
        """将 ACL 应用到接口"""
        return self.execute_commands([
            f"interface {if_name}",
            f"packet-filter {acl_number} {direction}",
        ])

    # ── 端口操作 ──

    def port_shutdown(self, if_name: str) -> str:
        """shutdown 端口"""
        return self.execute_commands([f"interface {if_name}", "shutdown"])

    def port_undo_shutdown(self, if_name: str) -> str:
        """undo shutdown 端口"""
        return self.execute_commands([f"interface {if_name}", "undo shutdown"])

    def port_set_description(self, if_name: str, description: str) -> str:
        """设置端口描述"""
        desc = description if description else " "
        return self.execute_commands([f"interface {if_name}", f"description {desc}"])

    def port_set_vlan_access(self, if_name: str, vlan_id: int) -> str:
        """设置端口为 access 模式并绑定 PVID"""
        return self.execute_commands([
            f"interface {if_name}",
            "port link-type access",
            f"port access vlan {vlan_id}",
        ])

    def port_set_vlan_trunk(self, if_name: str, pvid: int, vlan_list: str) -> str:
        """设置端口为 trunk 模式"""
        cmds = [
            f"interface {if_name}",
            "port link-type trunk",
            f"port trunk pvid vlan {pvid}",
            f"port trunk permit vlan {vlan_list}",
        ]
        return self.execute_commands(cmds)

    # ── 静态路由 ──

    def route_list_static(self) -> List[Dict]:
        """获取静态路由列表"""
        output = self.execute_command("display ip routing-table protocol static", read_timeout=30)
        return self._parse_routes(output)

    def route_add_static(self, destination: str, mask: str, next_hop: str, preference: int = 60) -> str:
        """添加静态路由"""
        return self.execute_commands([
            f"ip route-static {destination} {mask} {next_hop} preference {preference}"
        ])

    def route_delete_static(self, destination: str, mask: str, next_hop: str) -> str:
        """删除静态路由"""
        return self.execute_commands([
            f"undo ip route-static {destination} {mask} {next_hop}"
        ])

    def _parse_routes(self, output: str) -> List[Dict]:
        """解析 display ip routing-table 输出"""
        routes = []
        for line in output.split("\n"):
            line = line.strip()
            m = re.match(
                r"(\d+\.\d+\.\d+\.\d+)/(\d+)\s+Static\s+(\d+)\s+\d+\s+(\d+\.\d+\.\d+\.\d+)",
                line,
            )
            if m:
                routes.append({
                    "destination": m.group(1),
                    "mask": m.group(2),
                    "preference": int(m.group(3)),
                    "next_hop": m.group(4),
                })
        return routes

    def _parse_acls(self, output: str) -> List[Dict]:
        """解析 display acl all 输出"""
        rules = []
        current_acl = None
        for line in output.split("\n"):
            line = line.strip()
            # 匹配 ACL 头：Advanced IPv4 ACL 3000, named xxx, 3 rules,
            # 或：Advanced ACL  3000,
            # 或：Basic ACL  2000,
            m = re.match(
                r"(?:Advanced|Basic)\s+(?:IPv4\s+)?ACL\s+(\d+)\s*,", line, re.IGNORECASE
            )
            if m:
                current_acl = int(m.group(1))
                continue
            # 跳过注释行
            if " comment " in line:
                continue
            # 匹配规则行：rule 5 permit ip source ... (5 times matched)
            # 或：rule 0 permit (无协议 = ip)
            if current_acl is not None:
                m = re.match(
                    r"rule\s+(\d+)\s+(permit|deny)\s*(\S+)?(.*?)(?:\s*\(\d+\s+times\s+matched\))?$",
                    line, re.IGNORECASE,
                )
                if m:
                    rule_id = int(m.group(1))
                    action = m.group(2).lower()
                    raw_proto = (m.group(3) or "").lower()
                    rest = m.group(4) or ""
                    # 处理 Basic ACL 格式: rule 5 permit source 1.1.1.1 0
                    # source 不是协议名，而是源地址关键字
                    if raw_proto == "source":
                        protocol = "ip"
                        rest = f" source{rest}"
                    else:
                        protocol = raw_proto or "ip"
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
