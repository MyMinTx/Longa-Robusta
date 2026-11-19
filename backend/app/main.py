"""TGR-49 LINE Mini App — backend (FastAPI)

รัน:  uvicorn app.main:app --host 0.0.0.0 --port 8000
เอกสาร API อัตโนมัติ: http://localhost:8000/docs
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, lots
from .auth import current_user
from .config import settings
from .providers import agent_manager, moisture_runner
from .timeutil import iso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
settings.static_dir.joinpath("vis").mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app):
    db.conn()
    task = asyncio.create_task(moisture_runner()())
    for row in db.lots_by_status("SELLING"):  # รีสตาร์ตแล้วขายต่อ
        agent_manager().start(row["lot_id"])
    yield
    task.cancel()


app = FastAPI(title="TGR-49 Coffee Lot API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                   allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")


@app.exception_handler(lots.LotError)
async def lot_error(_, e: lots.LotError):
    return JSONResponse(status_code=e.code, content={"detail": e.message})


def _own(lot_id, user):
    row = lots.get(lot_id)
    if row["owner"] != user:
        raise HTTPException(403, "ล็อตนี้ไม่ใช่ของคุณ")
    return row


# ------------------------------------------------------------------ สำหรับแอป
@app.get("/health")
async def health():
    return {"ok": True, "time": iso(), "moisture": settings.moisture_source,
            "inspector": settings.inspector, "market": settings.market}


@app.get("/lots/latest")
async def latest(user: str = Depends(current_user)):
    row = db.latest_lot_row(user) or lots.create(user)
    return lots.to_dict(row)


@app.post("/lots")
async def new_lot(user: str = Depends(current_user)):
    """เริ่มล็อตใหม่ (หลังขายล็อตเก่าเสร็จ)"""
    return lots.to_dict(lots.create(user))


@app.get("/lots/{lot_id}")
async def get_lot(lot_id: str, user: str = Depends(current_user)):
    return lots.to_dict(_own(lot_id, user))


@app.get("/lots/{lot_id}/events")
async def get_events(lot_id: str, since_id: int = 0, user: str = Depends(current_user)):
    _own(lot_id, user)
    return [lots._event_out(e) for e in db.events(lot_id, since_id)]


@app.post("/lots/{lot_id}/sell")
async def sell(lot_id: str, user: str = Depends(current_user)):
    return lots.to_dict(lots.start_selling(lot_id, user))


@app.post("/lots/{lot_id}/inspect")
async def inspect(lot_id: str, improved: bool = False, user: str = Depends(current_user)):
    """ปุ่ม 'ขอตรวจใหม่' · improved=true จำลองว่าคัดเมล็ดเสียออกแล้ว (เฉพาะ INSPECTOR=sim)"""
    _own(lot_id, user)
    lots.request_inspection(lot_id, improved=improved)
    return lots.to_dict(lots.get(lot_id))


# ------------------------------------------------------------------ รับ 3 พารามิเตอร์จาก Track 1–3
def ingest_key(x_ingest_key: str = Header(default="")):
    if x_ingest_key != settings.ingest_key:
        raise HTTPException(403, "ต้องใส่ X-Ingest-Key")


class MoistureIn(BaseModel):
    moisture: float                 # Track 1: ความชื้น (%)
    lot_id: str | None = None


class DefectIn(BaseModel):
    defect_pct: float               # Track 2: % เมล็ดเสีย
    image_url: str | None = None    # ไม่บังคับ: ภาพประกอบ (HTTPS)
    lot_id: str | None = None


class SaleIn(BaseModel):
    price: float                    # Track 3: ราคาที่ขายออก (บาท/กก.)
    sacks: int | None = None        # ไม่บังคับ: ไม่ใส่ = ขายทุกกระสอบที่เหลือ
    buyer: str | None = None        # ไม่บังคับ
    lot_id: str | None = None


@app.get("/ingest/lots", dependencies=[Depends(ingest_key)])
async def ingest_lots():
    """ให้ทีม Track 1–3 ดู lot_id ที่ส่งค่าเข้าได้ (ใหม่สุดก่อน)"""
    rows = db.q("SELECT * FROM lots WHERE status IN ('DRYING','READY','ALERT','SELLING') "
                "ORDER BY created_at DESC, rowid DESC LIMIT 20")
    return [{"lot_id": r["lot_id"], "status": r["status"], "updated_at": r["updated_at"],
             "moisture": round(lots.current_moisture(r), 2)} for r in rows]


@app.post("/ingest/moisture", dependencies=[Depends(ingest_key)])
async def ingest_moisture(body: MoistureIn):
    row = lots.active_lot(("DRYING", "READY", "ALERT"), body.lot_id)
    lots.apply_reading(row["lot_id"], body.moisture, "ingest")
    return lots.to_dict(lots.get(row["lot_id"]), with_events=False)


@app.post("/ingest/defect", dependencies=[Depends(ingest_key)])
async def ingest_defect(body: DefectIn):
    row = lots.active_lot(("DRYING", "READY", "ALERT"), body.lot_id)
    lots.apply_inspection(row["lot_id"], {"defect_pct": body.defect_pct, "image_url": body.image_url})
    return lots.to_dict(lots.get(row["lot_id"]), with_events=False)


@app.post("/ingest/sale", dependencies=[Depends(ingest_key)])
async def ingest_sale(body: SaleIn):
    row = lots.active_lot(("SELLING",), body.lot_id)
    lots.record_sale(row["lot_id"], None, body.sacks, body.price, body.buyer)
    return lots.to_dict(lots.get(row["lot_id"]), with_events=False)


# ------------------------------------------------------------------ เดโม/ดีบัก
def demo_key(x_demo_key: str = Header(default="")):
    if x_demo_key != settings.demo_key:
        raise HTTPException(403, "ต้องใส่ X-Demo-Key")


class Speed(BaseModel):
    moisture_tick_seconds: float | None = None
    market_round_seconds: float | None = None


class Reading(BaseModel):
    value: float


@app.post("/demo/reset", dependencies=[Depends(demo_key)])
async def demo_reset(user: str = Depends(current_user)):
    """ลบล็อตทั้งหมดของผู้ใช้นี้ แล้วเริ่มล็อตใหม่ที่ความชื้น ~18%"""
    for row in db.q("SELECT lot_id FROM lots WHERE owner=?", (user,)):
        db.delete_lot(row["lot_id"])
    return lots.to_dict(lots.create(user, moisture_start=18.0))


@app.post("/demo/speed", dependencies=[Depends(demo_key)])
async def demo_speed(s: Speed):
    """เร่งเวลา เช่น {"moisture_tick_seconds": 2, "market_round_seconds": 2}"""
    if s.moisture_tick_seconds:
        settings.moisture_tick = s.moisture_tick_seconds
    if s.market_round_seconds:
        settings.market_round = s.market_round_seconds
    return {"moisture_tick_seconds": settings.moisture_tick, "market_round_seconds": settings.market_round}


@app.post("/demo/lots/{lot_id}/reading", dependencies=[Depends(demo_key)])
async def demo_reading(lot_id: str, r: Reading):
    """ใส่ค่าความชื้นเองหนึ่งค่า (ทดสอบ / แทน ESP32)"""
    lots.apply_reading(lot_id, r.value, "manual")
    return lots.to_dict(lots.get(lot_id))


@app.get("/debug/state", dependencies=[Depends(demo_key)])
async def debug_state():
    return [lots.to_dict(r, with_events=False) for r in db.q("SELECT * FROM lots ORDER BY created_at DESC")]


@app.get("/debug/pushes", dependencies=[Depends(demo_key)])
async def debug_pushes():
    return db.pushes()
