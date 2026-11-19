"""Agent ขายแทนเกษตรกร (ทำงานเหมือนกันทั้งตลาดจำลองและตลาดจริง)

กลยุทธ์ (ปรับได้):
  1. เริ่มเสนอที่ 103% ของราคาประเมิน แล้วลดรอบละ 2% ถ้ายังขายไม่ได้
  2. ไม่เสนอต่ำกว่าราคาต่ำสุด (80% ของราคาประเมิน) เด็ดขาด
  3. ส่งให้ผู้ซื้อเกรดพาณิชย์ก่อน (จ่ายดีกว่า) ครั้งละไม่เกิน 2 กระสอบ
  4. ครบ MARKET_MAX_ROUNDS แล้วยังเหลือ = ตลาดปิด ขายคืนที่ 80% (ตามกติกาตลาด)
"""
import asyncio
import logging

from .. import lots
from ..config import settings
from ..pricing import is_offer_allowed

log = logging.getLogger("agent")
START_MARKUP, STEP_DOWN, MAX_SACKS_PER_OFFER = 1.03, 0.98, 2


def eligible(rfq, lot):
    return (lot["inspection"]["defect_pct"] <= rfq.max_defect
            and lot["moisture"]["current"] <= rfq.max_moisture)


async def sell_lot(lot_id, market):
    lot = lots.to_dict(lots.get(lot_id), with_events=False)
    value, floor = lot["pricing"]["value"], lot["pricing"]["floor"]
    ask = round(value * START_MARKUP, 1)
    for _ in range(settings.market_max_rounds):
        remaining = lots.remaining_sacks(lot_id)
        if remaining <= 0:
            return
        rfqs = [r for r in market.open_round() if eligible(r, lot)]
        rfqs.sort(key=lambda r: (r.buyer_type != "commercial", -r.sacks_wanted))
        offers = []
        for r in rfqs:
            if remaining <= 0:
                break
            price = max(ask, floor)
            if not is_offer_allowed(price, floor):  # กันไว้อีกชั้น
                continue
            sacks = min(remaining, r.sacks_wanted, MAX_SACKS_PER_OFFER)
            o = market.submit(r, lot, sacks, price)
            lots.record_offer(lot_id, o.offer_id, sacks, price, r.buyer)
            offers.append(o)
            remaining -= sacks
        await asyncio.sleep(settings.market_round)
        sold_any = False
        for o in offers:
            n = market.close_round([o])[o.offer_id]
            if n > 0:
                sold_any = True
                lots.record_sale(lot_id, o.offer_id, n, o.price, o.rfq.buyer)
            else:
                lots.record_reject(lot_id, o.offer_id)
        if not sold_any:
            ask = round(max(floor, ask * STEP_DOWN), 1)
    left = lots.remaining_sacks(lot_id)
    if left > 0:
        lots.record_sale(lot_id, None, left, floor, "ตลาดรับซื้อตอนปิดรอบ (80%)")


class AgentManager:
    def __init__(self, market_factory):
        self.market_factory = market_factory
        self.tasks = {}

    def start(self, lot_id):
        t = self.tasks.get(lot_id)
        if t and not t.done():
            return
        loop = asyncio.get_running_loop()
        self.tasks[lot_id] = loop.create_task(self._run(lot_id))

    async def _run(self, lot_id):
        try:
            await sell_lot(lot_id, self.market_factory())
        except Exception:
            log.exception("Agent ขาย %s ล้มเหลว", lot_id)
