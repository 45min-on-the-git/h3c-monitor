"""H3C Comware NETCONF 驱动 (ncclient)"""

import re
from typing import Dict, List, Optional, Any
from lxml import etree

from ncclient import manager
from driver.base import DeviceDriver, DeviceInfo, MetricsResult, InterfaceData


H3C_CONFIG_NS = "http://www.h3c.com/netconf/config:1.0"
H3C_DATA_NS = "http://www.h3c.com/netconf/data:1.0"
NETCONF_BASE = "urn:ietf:params:xml:ns:netconf:base:1.0"

# XML 模板
RPC_HEADER = f'<rpc message-id="101" xmlns="{NETCONF_BASE}">'
RPC_FOOTER = "</rpc>"

def _edit_config_xml(xml_content: str) -> str:
    return f"""{RPC_HEADER}
<edit-config>
  <target><running/></target>
  <config>
    <top xmlns="{H3C_CONFIG_NS}" xmlns:xc="{NETCONF_BASE}" xc:operation="merge">
{xml_content}
    </top>
  </config>
</edit-config>
{RPC_FOOTER}"""


class H3CNETCONFDriver(DeviceDriver):
    """H3C Comware NETCONF 驱动 — 配置下发优先使用"""

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._mgr = None
        self._if_index_cache: Dict[str, str] = {}

    def connect(self) -> None:
        try:
            self._mgr = manager.connect(
                host=self.config["ip"],
                port=830,
                username=self.config["username"],
                password=self.config["password"],
                hostkey_verify=False,
                device_params={"name": "h3c"},
                timeout=10,
            )
        except Exception:
            raise RuntimeError(f"NETCONF connect failed: {self.config['ip']}")

    def disconnect(self) -> None:
        if self._mgr:
            self._mgr.close_session()
            self._mgr = None

    def execute_command(self, command: str, **kwargs) -> str:
        raise NotImplementedError("NETCONF: use SSH for CLI commands")

    def execute_commands(self, commands: List[str]) -> str:
        raise NotImplementedError("NETCONF: use specific methods for config")

    # ── 采集（基本，透传 SSH 已有数据即可）──

    def collect_device_info(self) -> DeviceInfo:
        """从 NETCONF 获取设备信息（有限，主要靠 SSH/SNMP）"""
        return DeviceInfo(
            ip=self.ip, device_category=self.device_category,
            hostname=self.config.get("device_name", ""),
        )

    def collect_metrics(self) -> MetricsResult:
        return MetricsResult()

    def collect_interfaces(self) -> List[InterfaceData]:
        return []

    # ── VLAN 操作 ──

    def vlan_create(self, vlan_id: int, name: str = "", description: str = "") -> str:
        """创建 VLAN"""
        name_xml = f"<Name>{name}</Name>" if name else ""
        desc_xml = f"<Description>{description}</Description>" if description else ""
        xml = _edit_config_xml(f"""<VLAN>
  <VLANs>
    <VLANID>
      <ID>{vlan_id}</ID>
      {name_xml}
      {desc_xml}
    </VLANID>
  </VLANs>
</VLAN>""")
        return self._rpc(xml)

    def vlan_delete(self, vlan_id: int) -> str:
        """删除 VLAN"""
        xml = f"""{RPC_HEADER}
<edit-config>
  <target><running/></target>
  <config>
    <top xmlns="{H3C_CONFIG_NS}" xmlns:xc="{NETCONF_BASE}" xc:operation="delete">
      <VLAN>
        <VLANs>
          <VLANID>
            <ID>{vlan_id}</ID>
          </VLANID>
        </VLANs>
      </VLAN>
    </top>
  </config>
</edit-config>
{RPC_FOOTER}"""
        return self._rpc(xml)

    def vlan_list(self) -> List[Dict]:
        """获取 VLAN 列表"""
        xml = f"""{RPC_HEADER}
<get>
  <filter type="subtree">
    <top xmlns="{H3C_DATA_NS}">
      <VLAN>
        <VLANs>
          <VLANID>
            <ID/>
            <Name/>
            <Description/>
          </VLANID>
        </VLANs>
      </VLAN>
    </top>
  </filter>
</get>
{RPC_FOOTER}"""
        reply = self._rpc(xml)
        return self._parse_vlans(reply)

    # ── 接口操作 ──

    def _get_if_index(self, if_name: str) -> str:
        """接口名 → IfIndex 映射（带缓存）"""
        if if_name in self._if_index_cache:
            return self._if_index_cache[if_name]
        xml = f"""{RPC_HEADER}
<get>
  <filter type="subtree">
    <top xmlns="{H3C_DATA_NS}">
      <Ifmgr>
        <Interfaces>
          <Interface>
            <IfIndex/>
            <Name>{if_name}</Name>
          </Interface>
        </Interfaces>
      </Ifmgr>
    </top>
  </filter>
</get>
{RPC_FOOTER}"""
        reply = self._rpc(xml)
        root = etree.fromstring(reply.encode())
        ns = {"d": H3C_DATA_NS}
        idx = root.xpath("//d:IfIndex/text()", namespaces=ns)
        if idx:
            self._if_index_cache[if_name] = idx[0]
            return idx[0]
        raise ValueError(f"Interface {if_name} not found via NETCONF")

    def port_shutdown(self, if_name: str) -> str:
        """NETCONF shutdown 端口"""
        idx = self._get_if_index(if_name)
        xml = _edit_config_xml(f"""<Ifmgr>
  <Interfaces>
    <Interface>
      <IfIndex>{idx}</IfIndex>
      <AdminStatus>DOWN</AdminStatus>
    </Interface>
  </Interfaces>
</Ifmgr>""")
        return self._rpc(xml)

    def port_undo_shutdown(self, if_name: str) -> str:
        """NETCONF undo shutdown 端口"""
        idx = self._get_if_index(if_name)
        xml = _edit_config_xml(f"""<Ifmgr>
  <Interfaces>
    <Interface>
      <IfIndex>{idx}</IfIndex>
      <AdminStatus>UP</AdminStatus>
    </Interface>
  </Interfaces>
</Ifmgr>""")
        return self._rpc(xml)

    def port_set_description(self, if_name: str, description: str) -> str:
        """NETCONF 设置端口描述"""
        idx = self._get_if_index(if_name)
        xml = _edit_config_xml(f"""<Ifmgr>
  <Interfaces>
    <Interface>
      <IfIndex>{idx}</IfIndex>
      <Description>{description}</Description>
    </Interface>
  </Interfaces>
</Ifmgr>""")
        return self._rpc(xml)

    def port_set_vlan_access(self, if_name: str, vlan_id: int) -> str:
        """NETCONF 设置 access 端口 VLAN"""
        idx = self._get_if_index(if_name)
        xml = _edit_config_xml(f"""<Ifmgr>
  <Interfaces>
    <Interface>
      <IfIndex>{idx}</IfIndex>
      <LinkType>access</LinkType>
      <PVID>{vlan_id}</PVID>
    </Interface>
  </Interfaces>
</Ifmgr>""")
        return self._rpc(xml)

    def port_set_vlan_trunk(self, if_name: str, pvid: int, vlan_list: str) -> str:
        """NETCONF 设置 trunk 端口 VLAN"""
        idx = self._get_if_index(if_name)
        xml = _edit_config_xml(f"""<Ifmgr>
  <Interfaces>
    <Interface>
      <IfIndex>{idx}</IfIndex>
      <LinkType>trunk</LinkType>
      <PVID>{pvid}</PVID>
      <PermitVlanList>{vlan_list}</PermitVlanList>
    </Interface>
  </Interfaces>
</Ifmgr>""")
        return self._rpc(xml)

    def port_set_ip(self, if_name: str, ip: str, mask: str) -> str:
        """NETCONF 设置三层接口 IP"""
        idx = self._get_if_index(if_name)
        xml = _edit_config_xml(f"""<Ifmgr>
  <Interfaces>
    <Interface>
      <IfIndex>{idx}</IfIndex>
      <IpAddress>
        <IP>{ip}</IP>
        <Mask>{mask}</Mask>
      </IpAddress>
    </Interface>
  </Interfaces>
</Ifmgr>""")
        return self._rpc(xml)

    # ── 底层 RPC ──

    def _rpc(self, xml: str) -> str:
        if not self._mgr:
            raise RuntimeError("NETCONF not connected")
        reply = self._mgr.dispatch(etree.fromstring(xml.encode()))
        if reply is None:
            raise RuntimeError("NETCONF empty reply")
        # 检查错误
        errs = reply.findall(".//{urn:ietf:params:xml:ns:netconf:base:1.0}rpc-error")
        if errs:
            msgs = [e.findtext("{urn:ietf:params:xml:ns:netconf:base:1.0}error-message", "unknown") for e in errs]
            raise RuntimeError("NETCONF error: " + "; ".join(msgs))
        return etree.tostring(reply, encoding="unicode")

    def _parse_vlans(self, xml_str: str) -> List[Dict]:
        root = etree.fromstring(xml_str.encode())
        ns = {"d": H3C_DATA_NS}
        vlans = []
        for v in root.xpath("//d:VLANID", namespaces=ns):
            vlan_id = v.findtext("d:ID", namespaces=ns)
            name = v.findtext("d:Name", namespaces=ns)
            desc = v.findtext("d:Description", namespaces=ns)
            vlans.append({"vlan_id": vlan_id, "name": name or "", "description": desc or ""})
        return vlans
