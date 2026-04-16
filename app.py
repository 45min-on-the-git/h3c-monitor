# FastAPI 后端应用
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import os
import uvicorn

import database
import collector

app = FastAPI(title="H3C Monitor API", version="1.0.0")

# 创建静态文件目录
os.makedirs("static", exist_ok=True)

# 创建模板目录
os.makedirs("templates", exist_ok=True)

# 模板路径
templates = Jinja2Templates(directory="templates")

# 初始化数据库
database.init_db()


@app.get("/")
async def root():
    """返回前端页面"""
    return HTMLResponse(content=open("templates/index.html").read())


@app.get("/api/devices")
async def get_devices():
    """获取设备列表"""
    devices = database.get_devices()
    
    # 添加设备配置信息
    device_map = {d['ip']: d for d in config.DEVICE_LIST}
    
    result = []
    for device in devices:
        config_info = device_map.get(device['ip'], {})
        result.append({
            'id': device['id'],
            'device_type': device['device_type'],
            'ip': device['ip'],
            'hostname': device['hostname'],
            'model': device['model'],
            'sw_version': device['sw_version'],
            'device_category': config_info.get('device_category', device['device_type']),
            'device_name': config_info.get('device_name', '')
        })
    
    return JSONResponse(content=result)


@app.get("/api/metrics")
async def get_metrics(
    device_id: Optional[int] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
):
    """获取指标历史"""
    metrics = database.get_metrics(device_id, start_time, end_time)
    return JSONResponse(content=metrics)


@app.get("/api/metrics/latest/{device_id}")
async def get_latest_metrics(device_id: int):
    """获取最新指标"""
    metrics = database.get_latest_metrics(device_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="No metrics found")
    return JSONResponse(content=metrics)


@app.post("/api/collect/{device_ip}")
async def collect_device(device_ip: str):
    """手动采集单台设备数据"""
    # 查找设备配置
    device_config = None
    for dev in config.DEVICE_LIST:
        if dev['ip'] == device_ip:
            device_config = dev
            break
    
    if not device_config:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # 采集数据
    result = collector.collect_device_data(device_config)
    
    if not result['success']:
        raise HTTPException(status_code=500, detail=result['error'])
    
    data = result['data']
    
    # 保存到数据库
    device_id = database.get_or_create_device(data)
    database.save_metrics(device_id, {
        'cpu_usage': data.get('cpu_usage'),
        'mem_usage': data.get('mem_usage'),
        'temperature': data.get('temperature'),
        'session_count': data.get('session_count'),
        'uptime': data.get('uptime')
    })
    
    # 保存接口信息
    database.save_interfaces(device_id, data.get('interfaces', []))
    
    return JSONResponse(content={'success': True, 'data': data})


@app.post("/api/collect/all")
async def collect_all():
    """采集所有设备数据"""
    results = collector.collect_all_devices()
    
    success_count = sum(1 for r in results if r['success'])
    
    return JSONResponse(content={
        'success': True,
        'total': len(results),
        'success_count': success_count,
        'failures': [r for r in results if not r['success']]
    })


# 启动时的设备列表
@app.get("/api/available-devices")
async def get_available_devices():
    """获取配置的设备列表（包含不在数据库中的）"""
    return JSONResponse(content=config.DEVICE_LIST)


# 配置端口
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9001)
