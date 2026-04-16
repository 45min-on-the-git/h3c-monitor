# H3C Monitor 配置文件

# SQLite 数据库路径
DB_PATH = "h3c_monitor.db"

# 采集间隔（分钟）
COLLECT_INTERVAL = 5

# 设备列表
DEVICE_LIST = [
    {
        "device_type": "hp_comware",
        "ip": "192.168.42.130",
        "username": "admin",
        "password": "Admin@123456",
        "device_name": "FW-01",
        "device_category": "firewall"
    },
    {
        "device_type": "hp_comware",
        "ip": "192.168.42.131",
        "username": "admin",
        "password": "Admin@123456",
        "device_name": "FW-02",
        "device_category": "firewall"
    },
    {
        "device_type": "hp_comware",
        "ip": "192.168.42.150",
        "username": "admin",
        "password": "Admin@123456",
        "device_name": "SW-01",
        "device_category": "switch"
    },
    {
        "device_type": "hp_comware",
        "ip": "192.168.42.151",
        "username": "admin",
        "password": "Admin@123456",
        "device_name": "SW-02",
        "device_category": "switch"
    }
]
