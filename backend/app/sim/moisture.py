"""TRACK 1 (จำลอง): ส่งค่าความชื้นปลอมทุก MOISTURE_TICK_SECONDS วินาที

ใช้เส้นทางเดียวกับ ESP32 จริง คือ lots.apply_reading(lot_id, value, source)
"""
import asyncio
import logging
import random

from .. import db, lots
from ..config import settings

log = logging.getLogger("sim.moisture")
DRY_FLOOR = 11.0  # ตากต่อไปก็ไม่แห้งกว่านี้


def next_value(status, current):
    if status == "DRYING":
        v = current - random.uniform(0.25, 0.55) + random.uniform(-0.05, 0.05)
        return round(max(DRY_FLOOR, v), 2)
    # พร้อมขาย/ต้องดูแล: ค่าแกว่งเล็กน้อย แต่ไม่เกินเกณฑ์ (ไม่งั้นจะกลายเป็น ALERT เอง)
    hi = settings.moisture_target - 0.2
    v = current + random.uniform(-0.15, 0.15)
    return round(min(hi, max(hi - 1.1, v)), 2)


def tick_once():
    for row in db.lots_by_status("DRYING", "READY", "ALERT"):
        cur = lots.current_moisture(row)
        lots.apply_reading(row["lot_id"], next_value(row["status"], cur), "sim")


async def run_forever():
    log.info("Track 1 จำลอง: ส่งค่าทุก %s วิ", settings.moisture_tick)
    while True:
        await asyncio.sleep(settings.moisture_tick)  # อ่านค่าทุกรอบ ปรับความเร็วได้ระหว่างรัน
        try:
            tick_once()
        except Exception:
            log.exception("tick ล้มเหลว")
