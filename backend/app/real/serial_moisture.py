"""TRACK 1 (ของจริง): อ่าน ESP32 ผ่าน USB Serial แล้วส่งเข้าล็อตที่กำลังตาก

ตั้ง MOISTURE_SOURCE=serial ใน .env · เฟิร์มแวร์แข่งส่งค่าเมื่อกดปุ่มเท่านั้น
"""
import asyncio
import logging
import threading

from .. import lots
from ..config import settings
from ..serial_reader import read_forever

log = logging.getLogger("serial")


def _on_value(v):
    # ESP32 เลือกล็อตเองไม่ได้ → ใช้กฎเดียวกับ /ingest แต่ถ้ามีหลายล็อตให้เข้าล็อตใหม่ล่าสุด
    try:
        row = lots.active_lot(("DRYING", "READY", "ALERT"), strict=False)
    except lots.LotError:
        log.warning("ได้ค่า %.2f แต่ไม่มีล็อตที่กำลังตาก", v)
        return
    lots.apply_reading(row["lot_id"], v, "esp32")


async def run_forever():
    threading.Thread(target=read_forever, args=(settings.serial_port, _on_value), daemon=True).start()
    while True:
        await asyncio.sleep(3600)
