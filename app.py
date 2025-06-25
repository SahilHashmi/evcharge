import asyncio
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import HTMLResponse
import httpx
import websockets
from ocpp.routing import on
from ocpp.v16 import ChargePoint as OcppChargePoint
from ocpp.v16.enums import RegistrationStatus
from ocpp.v16 import call_result
import threading

# -------------------- Logging --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ev-charger")

# -------------------- FastAPI Setup --------------------
app = FastAPI()

# -------------------- Charger Status Storage --------------------
charger_status = {
    "charger_id": "EV123",
    "status": "Available",
    "current_session": None,
    "last_meter_value": {},
    "transaction_id": None
}

# -------------------- WebSocket Clients --------------------
clients = []

# -------------------- OCPP ChargePoint --------------------
class ChargePoint(OcppChargePoint):
    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        logger.info(f"BootNotification from {self.id}: {charge_point_model}, {charge_point_vendor}")
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted
        )

    @on("Heartbeat")
    async def on_heartbeat(self):
        logger.info(f"Heartbeat received from {self.id}")
        return call_result.HeartbeatPayload(current_time=datetime.utcnow().isoformat())

    @on("StartTransaction")
    async def on_start_transaction(self, connector_id, id_tag, meter_start, timestamp, **kwargs):
        charger_status["status"] = "Charging"
        charger_status["current_session"] = {
            "charger_id": self.id,
            "start_time": timestamp,
            "connector_id": connector_id,
            "id_tag": id_tag,
            "meter_start": meter_start
        }
        charger_status["transaction_id"] = 1234
        logger.info(f"StartTransaction received: {connector_id}, {id_tag}")
        return call_result.StartTransactionPayload(
            transaction_id=1234,
            id_tag_info={"status": "Accepted"}
        )

    @on("MeterValues")
    async def on_meter_values(self, connector_id, meter_value, **kwargs):
        sampled_value = meter_value[0]['sampledValue'][0]
        value = float(sampled_value['value'])
        unit = sampled_value.get('unit', 'Wh')
        charger_status["last_meter_value"] = {
            "value": value,
            "unit": unit,
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.info(f"Received meter value: {value} {unit}")
        return call_result.MeterValuesPayload()

    @on("StopTransaction")
    async def on_stop_transaction(self, meter_stop, timestamp, transaction_id, **kwargs):
        charger_status["status"] = "Available"
        charger_status["last_meter_value"]["meter_stop"] = meter_stop
        charger_status["current_session"] = None
        logger.info(f"StopTransaction received: {transaction_id}")
        return call_result.StopTransactionPayload(id_tag_info={"status": "Accepted"})

# -------------------- OCPP WebSocket Server --------------------
async def ocpp_server(websocket, path):
    charge_point_id = path.strip("/")
    cp = ChargePoint(charge_point_id, websocket)
    await cp.start()

def start_ocpp_server():
    async def run():
        server = await websockets.serve(ocpp_server, "0.0.0.0", 9000, subprotocols=["ocpp1.6"])
        logger.info("OCPP Server running on ws://0.0.0.0:9000")
        await server.wait_closed()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run())

ocpp_thread = threading.Thread(target=start_ocpp_server, daemon=True)
ocpp_thread.start()

# -------------------- FastAPI REST Endpoints --------------------
@app.get("/")
def home():
    return {"message": "EV Charger Simulator Running"}

@app.get("/connect-charger")
def connect_charger(charger_id: str):
    return {
        "status": "True",
        "charger_id": charger_id,
        "message": "Charger connected successfully.",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/charging-ui-status")
def charging_ui_status():
    battery_raw = charger_status["last_meter_value"].get("value", 0)
    battery_percent = int(battery_raw)

    start_time_str = None
    if charger_status["current_session"]:
        start_time_str = charger_status["current_session"].get("start_time")

    if start_time_str:
        start_time = datetime.fromisoformat(start_time_str)
        duration_minutes = (datetime.utcnow() - start_time).total_seconds() // 60
        session_duration = f"Started {int(duration_minutes)} min ago"
    else:
        session_duration = "Not started"

    # Cost and estimated time (dummy logic)
    unit_rate = 0.10  # $/Wh
    units_used = battery_raw
    current_cost = f"${round(units_used * unit_rate, 2)}"

    if battery_percent < 80:
        percent_needed = 80 - battery_percent
        time_required = percent_needed * 1.5
        estimated_time = f"{int(time_required)} min approx to 80%"
    else:
        estimated_time = "Already above 80%"

    return {
        "charger_id": charger_status["charger_id"],
        "status": charger_status["status"],
        "battery_level_percent": battery_percent,
        "estimated_time_to_80_percent": estimated_time,
        "session_duration": session_duration,
        "current_cost": current_cost,
        "station_name": "EV Station A1",
        "map_location": {"lat": 28.6139, "lon": 77.209}
    }

@app.get("/status")
def get_status():
    return charger_status

@app.post("/discover-charger")
def discover_charger(scan_type: str, scanned_id: str):
    logger.info(f"Discovered charger via {scan_type}: {scanned_id}")
    return {
        "status": True,
        "charger_id": scanned_id,
        "scan_type": scan_type,
        "message": "Charger discovered and ready for connection."
    }

@app.get("/get-charger-third-party-data")
async def get_charger_metadata():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://jsonplaceholder.typicode.com/posts")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch third-party data")

# -------------------- WebSocket for Real-time App Updates --------------------
@app.websocket("/ws/charging/{charger_id}")
async def websocket_endpoint(websocket: WebSocket, charger_id: str):
    await websocket.accept()
    clients.append(websocket)
    try:
        while True:
            battery_raw = charger_status["last_meter_value"].get("value", 0)
            battery_percent = int(battery_raw)

            start_time_str = None
            if charger_status["current_session"]:
                start_time_str = charger_status["current_session"].get("start_time")

            if start_time_str:
                start_time = datetime.fromisoformat(start_time_str)
                duration_minutes = (datetime.utcnow() - start_time).total_seconds() // 60
                session_duration = f"Started {int(duration_minutes)} min ago"
            else:
                session_duration = "Not started"

            unit_rate = 0.10
            units_used = battery_raw
            current_cost = f"${round(units_used * unit_rate, 2)}"

            if battery_percent < 80:
                percent_needed = 80 - battery_percent
                time_required = percent_needed * 1.5
                estimated_time = f"{int(time_required)} min approx to 80%"
            else:
                estimated_time = "Already above 80%"

            await websocket.send_json({
                "charger_id": charger_id,
                "status": charger_status["status"],
                "battery_level_percent": battery_percent,
                "estimated_time_to_80_percent": estimated_time,
                "session_duration": session_duration,
                "current_cost": current_cost,
                "station_name": "EV Station A1",
                "map_location": {
                    "lat": 28.6139,
                    "lon": 77.209
                }
            })
            await asyncio.sleep(5)
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
        clients.remove(websocket)
