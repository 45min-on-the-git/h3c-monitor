# FastAPI 后端应用
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
import threading
import os
import uvicorn
import config
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

import database
import collector
import alarm

app = FastAPI(title="H3C Monitor API", version="1.0.0")

# 目录
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 数据库
database.init_db()

# APScheduler
scheduler = BlockingScheduler()


def _save_and_alarm(data: dict) -> int:
    """保存采集数据到数据库并触发告警检查，返回 device_id"""
    device_id = database.get_or_create_device(data)
    database.save_metrics(device_id, {
        "cpu_usage": data.get("cpu_usage"),
        "mem_usage": data.get("mem_usage"),
        "temperature": data.get("temperature"),
        "session_count": data.get("session_count"),
        "uptime": data.get("uptime"),
    })
    database.save_interfaces(device_id, data.get("interfaces", []))
    # 告警检查
    alarm.check_and_trigger(device_id, {
        "cpu_usage": data.get("cpu_usage"),
        "mem_usage": data.get("mem_usage"),
        "temperature": data.get("temperature"),
        "interface_status": "UP",  # 基于最新接口状态
    })
    return device_id


def auto_collect():
    """自动采集所有设备数据"""
    print("Starting automatic data collection...")
    results = collector.collect_all_devices()

    success_count = 0
    for i, result in enumerate(results):
        if result["success"]:
            _save_and_alarm(result["data"])
            success_count += 1
        else:
            print(f"Failed to collect {config.DEVICE_LIST[i]['ip']}: {result['error']}")

    print(f"Auto collection complete: {success_count}/{len(results)} success")


# 启动时采集
auto_collect()

scheduler.add_job(
    auto_collect,
    trigger=IntervalTrigger(minutes=config.COLLECT_INTERVAL),
    id="auto_collect",
    replace_existing=True,
)
scheduler_thread = threading.Thread(target=scheduler.start, daemon=True)
scheduler_thread.start()


# ══════ 页面路由 ══════

@app.get("/", response_class=HTMLResponse)
async def page_dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")

@app.get("/devices", response_class=HTMLResponse)
async def page_devices(request: Request):
    return templates.TemplateResponse(request, "devices.html")

@app.get("/alarms", response_class=HTMLResponse)
async def page_alarms(request: Request):
    return templates.TemplateResponse(request, "alarms.html")

@app.get("/acl", response_class=HTMLResponse)
async def page_acl(request: Request):
    return templates.TemplateResponse(request, "acl.html")


# ══════ 设备 API ══════

@app.get("/api/devices")
async def get_devices():
    devices = database.get_devices()
    device_map = {d["ip"]: d for d in config.DEVICE_LIST}
    result = []
    for d in devices:
        ci = device_map.get(d["ip"], {})
        result.append({
            "id": d["id"], "device_type": d["device_type"], "ip": d["ip"],
            "hostname": d["hostname"], "model": d["model"], "sw_version": d["sw_version"],
            "create_time": d["create_time"],
            "device_category": ci.get("device_category", d["device_type"]),
            "device_name": ci.get("device_name", ""),
            "serial_number": d.get("serial_number"), "purchase_date": d.get("purchase_date"),
            "warranty_expiry": d.get("warranty_expiry"), "supplier": d.get("supplier"),
            "contract_no": d.get("contract_no"), "asset_no": d.get("asset_no"),
            "location": d.get("location"), "rack": d.get("rack"),
            "role": d.get("role"), "tags": d.get("tags"),
        })
    return JSONResponse(content=result)

@app.get("/api/devices/{device_id}")
async def get_device(device_id: int):
    devices = database.get_devices()
    for d in devices:
        if d["id"] == device_id:
            return JSONResponse(content=d)
    raise HTTPException(status_code=404, detail="Device not found")

@app.put("/api/devices/{device_id}")
async def update_device(device_id: int, body: dict = Body(...)):
    database.update_device_info(device_id, body)
    return JSONResponse(content={"success": True})

@app.post("/api/devices")
async def create_device(body: dict = Body(...)):
    try:
        device_id = database.create_device_manual(body)
        return JSONResponse(content={"success": True, "id": device_id})
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.get("/api/available-devices")
async def get_available_devices():
    return JSONResponse(content=config.DEVICE_LIST)


# ══════ 指标 API ══════

@app.get("/api/metrics")
async def get_metrics(
    device_id: Optional[int] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
):
    return JSONResponse(content=database.get_metrics(device_id, start_time, end_time))

@app.get("/api/metrics/latest/{device_id}")
async def get_latest_metrics(device_id: int):
    m = database.get_latest_metrics(device_id)
    if not m:
        raise HTTPException(status_code=404, detail="No metrics found")
    return JSONResponse(content=m)

@app.get("/api/interfaces/{device_id}")
async def get_interfaces(device_id: int):
    return JSONResponse(content=database.get_latest_interfaces(device_id))


@app.get("/api/interfaces/{device_id}/traffic")
async def get_interface_traffic(
    device_id: int,
    if_name: str,
    hours: int = 24,
):
    """获取接口流量时序数据（默认最近24h）"""
    limit = max(hours * 12, 10)  # 每5分钟采集一次，12条/小时
    data = database.get_interface_traffic(device_id, if_name, limit=limit)
    return JSONResponse(content=data)


# ══════ 采集 API ══════

@app.post("/api/collect/all")
async def collect_all():
    results = collector.collect_all_devices()
    success_count = 0
    for r in results:
        if r["success"]:
            _save_and_alarm(r["data"])
            success_count += 1
    return JSONResponse(content={
        "success": True, "total": len(results),
        "success_count": success_count,
        "failure_count": len(results) - success_count,
        "failures": [r for r in results if not r["success"]],
    })

@app.post("/api/collect/{device_ip}")
async def collect_device(device_ip: str):
    device_config = next((d for d in config.DEVICE_LIST if d["ip"] == device_ip), None)
    if not device_config:
        raise HTTPException(status_code=404, detail="Device not found")
    result = collector.collect_device_data(device_config)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    _save_and_alarm(result["data"])
    return JSONResponse(content={"success": True, "data": result["data"]})


# ══════ 告警 API ══════

@app.get("/api/alarms")
async def get_alarms(status: Optional[str] = None, device_id: Optional[int] = None):
    return JSONResponse(content=alarm.get_alarms(status=status, device_id=device_id))

@app.post("/api/alarms/{alarm_id}/acknowledge")
async def ack_alarm(alarm_id: int):
    alarm.acknowledge_alarm(alarm_id)
    return JSONResponse(content={"success": True})

@app.post("/api/alarms/{alarm_id}/resolve")
async def resolve_alarm(alarm_id: int):
    alarm.resolve_alarm(alarm_id)
    return JSONResponse(content={"success": True})


# ══════ 告警规则 API ══════

@app.get("/api/alarm-rules")
async def get_alarm_rules(device_id: Optional[int] = None):
    return JSONResponse(content=alarm.get_rules(device_id))

@app.post("/api/alarm-rules")
async def create_alarm_rule(body: dict = Body(...)):
    rid = alarm.create_rule(
        body["device_id"], body["metric"], body.get("operator", ">"), body["threshold"]
    )
    return JSONResponse(content={"success": True, "id": rid})

@app.put("/api/alarm-rules/{rule_id}")
async def update_alarm_rule(rule_id: int, body: dict = Body(...)):
    alarm.update_rule(rule_id, **body)
    return JSONResponse(content={"success": True})

@app.delete("/api/alarm-rules/{rule_id}")
async def delete_alarm_rule(rule_id: int):
    alarm.delete_rule(rule_id)
    return JSONResponse(content={"success": True})


# ══════ ACL API ══════

@app.get("/api/acl/{device_id}")
async def get_device_acls(device_id: int):
    """通过 SSH 读取设备 ACL 规则"""
    devices = database.get_devices()
    device_info = next((d for d in devices if d["id"] == device_id), None)
    if not device_info:
        raise HTTPException(status_code=404, detail="Device not found")

    # 从 config 获取 SSH 凭据
    device_config = next(
        (d for d in config.DEVICE_LIST if d["ip"] == device_info["ip"]), None
    )
    if not device_config:
        raise HTTPException(status_code=404, detail="Device config not found")

    try:
        from driver import get_ssh_driver
        driver = get_ssh_driver(device_config)
        driver.connect()
        acls = driver.get_acls()
        driver.disconnect()
        return JSONResponse(content=acls)
    except Exception as e:
        # SSH 不可达时返回空列表（不给用户报错）
        return JSONResponse(content=[])


@app.post("/api/acl/{device_id}")
async def create_acl_rule(device_id: int, body: dict = Body(...)):
    """创建 ACL 规则并下发到设备"""
    devices = database.get_devices()
    device_info = next((d for d in devices if d["id"] == device_id), None)
    if not device_info:
        raise HTTPException(status_code=404, detail="Device not found")

    device_config = next(
        (d for d in config.DEVICE_LIST if d["ip"] == device_info["ip"]), None
    )
    if not device_config:
        raise HTTPException(status_code=404, detail="Device config not found")

    try:
        from driver import get_ssh_driver
        driver = get_ssh_driver(device_config)
        driver.connect()
        driver.create_acl_rule(
            acl_number=body["acl_number"],
            rule_id=body["rule_id"],
            action=body["action"],
            protocol=body.get("protocol", "ip"),
            source=body.get("source", "any"),
            destination=body.get("destination", "any"),
            description=body.get("description", ""),
        )
        driver.disconnect()
        return JSONResponse(content={"success": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/acl/{device_id}/{acl_number}/{rule_id}")
async def update_acl_rule(device_id: int, acl_number: int, rule_id: int, body: dict = Body(...)):
    """更新 ACL 规则（先删后建）"""
    devices = database.get_devices()
    device_info = next((d for d in devices if d["id"] == device_id), None)
    if not device_info:
        raise HTTPException(status_code=404, detail="Device not found")

    device_config = next(
        (d for d in config.DEVICE_LIST if d["ip"] == device_info["ip"]), None
    )
    if not device_config:
        raise HTTPException(status_code=404, detail="Device config not found")

    try:
        from driver import get_ssh_driver
        driver = get_ssh_driver(device_config)
        driver.connect()
        driver.delete_acl_rule(acl_number, rule_id)
        driver.create_acl_rule(
            acl_number=body.get("acl_number", acl_number),
            rule_id=body.get("rule_id", rule_id),
            action=body["action"],
            protocol=body.get("protocol", "ip"),
            source=body.get("source", "any"),
            destination=body.get("destination", "any"),
        )
        driver.disconnect()
        return JSONResponse(content={"success": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/acl/{device_id}/{acl_number}/{rule_id}")
async def delete_acl_rule(device_id: int, acl_number: int, rule_id: int):
    """删除 ACL 规则"""
    devices = database.get_devices()
    device_info = next((d for d in devices if d["id"] == device_id), None)
    if not device_info:
        raise HTTPException(status_code=404, detail="Device not found")

    device_config = next(
        (d for d in config.DEVICE_LIST if d["ip"] == device_info["ip"]), None
    )
    if not device_config:
        raise HTTPException(status_code=404, detail="Device config not found")

    try:
        from driver import get_ssh_driver
        driver = get_ssh_driver(device_config)
        driver.connect()
        driver.delete_acl_rule(acl_number, rule_id)
        driver.disconnect()
        return JSONResponse(content={"success": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def main():
    uvicorn.run(app, host="0.0.0.0", port=9001)


if __name__ == "__main__":
    main()
