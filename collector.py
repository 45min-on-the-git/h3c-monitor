# 采集器模块 - Netmiko + TextFSM
from netmiko import ConnectHandler
from textfsm import TextFSM
from typing import Dict, List, Optional, Any
import config  # noqa: F401
import re


def collect_device_data(device_config: Dict[str, Any]) -> Dict[str, Any]:
    """采集单台设备的数据"""
    result = {
        'success': False,
        'error': None,
        'data': {}
    }
    
    try:
        # 建立 SSH 连接
        netconf = {
            'device_type': device_config['device_type'],
            'host': device_config['ip'],
            'username': device_config['username'],
            'password': device_config['password'],
            'timeout': 10,
            'session_timeout': 10
        }
        
        net_connect = ConnectHandler(**netconf)
        
        # 切换特权模式（H3C 设备）
        net_connect.enable()
        
        device_data = {
            'device_category': device_config.get('device_category', 'switch'),
            'hostname': device_config.get('device_name', ''),
            'ip': device_config['ip'],
            'uptime': None,
            'cpu_usage': None,
            'mem_usage': None,
            'temperature': None,
            'model': None,
            'sw_version': None,
            'session_count': None,
            'interfaces': []
        }
        
        # 1. 获取设备基本信息
        version_output = net_connect.send_command('display version', read_timeout=30)
        device_data.update(parse_version(version_output, device_config['device_type']))
        
        # 2. 获取运行时间
        uptime_output = net_connect.send_command('display version', read_timeout=30)
        device_data['uptime'] = extract_uptime(uptime_output)
        
        # 3. 获取 CPU 使用率
        cpu_output = net_connect.send_command('display cpu-usage', read_timeout=30)
        device_data['cpu_usage'] = extract_cpu_usage(cpu_output)
        
        # 4. 获取内存使用率
        mem_output = net_connect.send_command('display memory', read_timeout=30)
        device_data['mem_usage'] = extract_mem_usage(mem_output)
        
        # 5. 获取温度
        temp_output = net_connect.send_command('display environment', read_timeout=30)
        device_data['temperature'] = extract_temperature(temp_output)
        
        # 6. 获取接口信息
        if_stats_output = net_connect.send_command('display interface brief', read_timeout=30)
        device_data['interfaces'] = parse_interfaces(if_stats_output, device_config['device_type'])
        
        # 7. 获取接口流量（如果需要）
        interface_output = net_connect.send_command('display interface', read_timeout=60)
        device_data['interfaces'].extend(parse_interface_stats(interface_output, device_config['device_type']))
        
        # 8. 如果是防火墙，获取会话信息
        if device_config.get('device_category') == 'firewall':
            session_output = net_connect.send_command('display session statistics ipv4', read_timeout=30)
            device_data['session_count'] = extract_session_count(session_output)
        
        # 9. 获取管理 IP
        ip_output = net_connect.send_command('display ip interface brief', read_timeout=30)
        device_data['management_ip'] = extract_management_ip(ip_output)
        
        net_connect.disconnect()
        result['success'] = True
        result['data'] = device_data
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


def parse_version(version_output: str, device_type: str) -> Dict[str, Any]:
    """解析版本信息"""
    result = {'model': None, 'sw_version': None}
    
    # 解析型号
    model_match = re.search(r'Model\s*:\s*(.+)', version_output, re.IGNORECASE)
    if not model_match:
        model_match = re.search(r'SoftWare Version\s*:\s*(.+)', version_output)
    if model_match:
        result['model'] = model_match.group(1).strip()
    
    # 解析版本
    sw_match = re.search(r'SoftWare Version\s*:\s*(.+)', version_output)
    if not sw_match:
        sw_match = re.search(r'Version\s*:\s*(.+?)(?:\n|$)', version_output)
    if sw_match:
        result['sw_version'] = sw_match.group(1).strip()
    
    return result


def extract_uptime(version_output: str) -> Optional[str]:
    """提取运行时间"""
    # H3C Comware 输出格式：uptime is 0 weeks, 3 days, 7 hours, 19 minutes
    match = re.search(r'uptime is\s*([\d\w,\s]+)', version_output, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return None


def extract_cpu_usage(cpu_output: str) -> Optional[float]:
    """提取 CPU 使用率"""
    # H3C display cpu-usage 输出示例：
    # Unit CPU usage:
    #        1% in last 5 seconds
    #        2% in last 1 minute
    #        1% in last 5 minutes
    
    # 优先获取 5 秒的 CPU 使用率
    match = re.search(r'(\d+)%\s+in\s+last\s+5\s+seconds?', cpu_output, re.IGNORECASE)
    if match:
        return float(match.group(1))
    
    match = re.search(r'(\d+)%\s+in\s+last\s+5\s+secs?', cpu_output, re.IGNORECASE)
    if match:
        return float(match.group(1))
    
    # 尝试其他格式
    match = re.search(r'last\s+5\s+seconds?.*?(\d+)%', cpu_output, re.IGNORECASE)
    if match:
        return float(match.group(1))
    
    return None


def extract_mem_usage(mem_output: str) -> Optional[float]:
    """提取内存使用率"""
    # H3C display memory 输出示例：
    # Mem:       1978716    981468    997248         0     10316    326212       51.4%
    # 最后一列是 FreeRatio，所以使用率 = 100 - FreeRatio
    
    # 尝试提取 FreeRatio
    match = re.search(r'FreeRatio\s*(\d+\.?\d*)%', mem_output, re.IGNORECASE)
    if match:
        free_ratio = float(match.group(1))
        usage = 100 - free_ratio
        return round(usage, 2)
    
    # 或者直接从 Mem:行提取 Total 和 Used
    mem_line_match = re.search(r'Mem:\s+(\d+)\s+(\d+)\s+(\d+)', mem_output)
    if mem_line_match:
        total = int(mem_line_match.group(1))
        used = int(mem_line_match.group(2))
        if total > 0:
            return round((used / total) * 100, 2)
    
    # 尝试旧格式
    match = re.search(r'Usage:\s*(\d+\.?\d*)%', mem_output, re.IGNORECASE)
    if match:
        return float(match.group(1))
    
    # 总使用量和总容量
    total_match = re.search(r'Total:\s*(\d+)', mem_output)
    used_match = re.search(r'Used:\s*(\d+)', mem_output)
    
    if total_match and used_match:
        total = int(total_match.group(1))
        used = int(used_match.group(1))
        if total > 0:
            return round((used / total) * 100, 2)
    
    return None


def extract_temperature(env_output: str) -> Optional[float]:
    """提取温度"""
    # 尝试提取温度值
    temp_match = re.search(r'Temperature\s*:\s*(\d+\.?\d*)\s*°?C', env_output, re.IGNORECASE)
    if temp_match:
        return float(temp_match.group(1))
    
    temp_match = re.search(r'(\d+\.?\d*)\s*°?C', env_output)
    if temp_match:
        return float(temp_match.group(1))
    
    return None


def parse_interfaces(if_output: str, device_type: str) -> List[Dict[str, Any]]:
    """解析接口基本信息"""
    interfaces = []
    
    # 解析 display interface brief 输出
    # 防火墙格式示例：
    # Interface            Link Protocol Primary IP      Description                
    # GE1/0                UP   UP       192.168.42.130  
    # GE2/0                UP   UP       --              
    
    # 交换机格式示例：
    # Interface            Link Protocol Primary IP        Description              
    # HGE1/0/1             UP   UP       --                
    # MGE0/0/0             UP   UP       192.168.42.150    
    
    lines = if_output.strip().split('\n')
    for line in lines:
        # 匹配接口名称（支持 2 位和 3 位格式）
        # GE1/0, GE2/0, HGE1/0/1, MGE0/0/0, MEth0/0/0, InLoop0 等
        iface_match = re.match(r'\s*(GE\d+/\d+|H?GE\d+/\d+/\d+|MEth\d+/0/0|MGE\d+/\d+/\d+|InLoop\d+|NULL\d+|REG\d+)', line)
        if iface_match:
            if_name = iface_match.group(1)
            parts = line.split()
            status = parts[1] if len(parts) > 1 else 'DOWN'
            
            interfaces.append({
                'if_name': if_name,
                'status': 'UP' if status.upper() == 'UP' else 'DOWN',
                'in_bytes': 0,
                'out_bytes': 0,
                'in_util': 0,
                'out_util': 0
            })
    
    return interfaces


def parse_interface_stats(if_output: str, device_type: str) -> List[Dict[str, Any]]:
    """解析接口流量统计"""
    interfaces = []
    current_iface = None
    in_bytes = 0
    out_bytes = 0
    
    lines = if_output.strip().split('\n')
    for line in lines:
        line = line.strip()
        
        # 匹配接口名称（例如：Ten-GigabitEthernet1/0/1）
        iface_match = re.match(r'(Ten-GigabitEthernet\d+/\d+/\d+|GigabitEthernet\d+/\d+/\d+|Ethernet\d+/\d+|Vlan-interface\d+|MEth\d+)', line)
        if iface_match:
            # 保存前一个接口
            if current_iface and (in_bytes > 0 or out_bytes > 0):
                interfaces.append({
                    'if_name': current_iface,
                    'status': 'UP',
                    'in_bytes': in_bytes,
                    'out_bytes': out_bytes,
                    'in_util': 0,
                    'out_util': 0
                })
            
            current_iface = iface_match.group(1)
            in_bytes = 0
            out_bytes = 0
            continue
        
        # 匹配 I/O 统计
        in_match = re.search(r'Input:\s*(\d+)\s*Bytes', line)
        if in_match:
            in_bytes = int(in_match.group(1))
            continue
        
        out_match = re.search(r'Output:\s*(\d+)\s*Bytes', line)
        if out_match:
            out_bytes = int(out_match.group(1))
            continue
    
    # 保存最后一个接口
    if current_iface and (in_bytes > 0 or out_bytes > 0):
        interfaces.append({
            'if_name': current_iface,
            'status': 'UP',
            'in_bytes': in_bytes,
            'out_bytes': out_bytes,
            'in_util': 0,
            'out_util': 0
        })
    
    return interfaces


def extract_session_count(session_output: str) -> Optional[int]:
    """提取会话数（防火墙）"""
    # 尝试多种格式
    match = re.search(r'Current\s+Sessions?:?\s*(\d+)', session_output, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    match = re.search(r'Number\s+of\s+sessions:\s*(\d+)', session_output, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    return None


def extract_management_ip(ip_output: str) -> Optional[str]:
    """提取管理 IP"""
    lines = ip_output.strip().split('\n')
    for line in lines:
        # 匹配带有 IP 地址的接口
        ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
        if ip_match:
            # 优先匹配 VLAN 接口
            if 'Vlan' in line or 'vlan' in line:
                return ip_match.group(1)
    
    return None


def collect_all_devices() -> List[Dict[str, Any]]:
    """采集所有设备的数据"""
    import config  # noqa: F401
    
    results = []
    
    for device_config in config.DEVICE_LIST:
        print(f"Collecting data from {device_config['ip']}...")
        result = collect_device_data(device_config)
        results.append(result)
        
        if result['success']:
            print(f"✓ {device_config['ip']} - Success")
        else:
            print(f"✗ {device_config['ip']} - Error: {result['error']}")
    
    return results
