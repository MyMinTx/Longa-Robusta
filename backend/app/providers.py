"""สวิตช์ แหล่งข้อมูลแต่ละ Track (อ่านจาก .env) — ที่เดียวที่ต้องแก้เมื่อของจริงพร้อม

แต่ละ Track มี 3 แบบ:
  sim       ตัวจำลองในเครื่องนี้ (ค่าเริ่มต้น)
  external  ระบบอื่นส่งค่าเข้ามาเองที่ /ingest/* (เช่น ทีม Track 1/2/3 ยิง HTTP มา)
  serial / camera / real   โค้ดของจริงที่รันในเครื่องนี้ (ต้องเติมให้ครบก่อน)
"""
import asyncio
from functools import lru_cache

from .config import settings


@lru_cache
def inspector():
    """Track 2 · คืน None = external (รอ /ingest/defect)"""
    if settings.inspector == "external":
        return None
    if settings.inspector == "camera":
        from .real.camera_inspector import CameraInspector
        return CameraInspector()
    from .sim.inspector import SimInspector
    return SimInspector()


def market():
    if settings.market == "real":
        from .market.real_market import RealMarket
        return RealMarket()
    from .market.sim_market import SimMarket
    return SimMarket()


@lru_cache
def agent_manager():
    """Track 3 · คืน None = external (รอ /ingest/sale)"""
    if settings.market == "external":
        return None
    from .market.agent import AgentManager
    return AgentManager(market)


async def _idle():
    while True:
        await asyncio.sleep(3600)


def moisture_runner():
    """Track 1 · external = ไม่รันอะไร รอ /ingest/moisture"""
    if settings.moisture_source == "external":
        return _idle
    if settings.moisture_source == "serial":
        from .real.serial_moisture import run_forever
    else:
        from .sim.moisture import run_forever
    return run_forever
