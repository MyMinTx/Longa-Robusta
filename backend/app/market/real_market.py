"""TRACK 3 (ตลาดจริง) — บิว/มิ้นเติมตาม docs/market-api.md แล้วตั้ง MARKET=real

แปลง API ตลาดจริงให้เป็นเมธอด 3 ตัวเหมือน SimMarket
Agent (agent.py) ไม่ต้องแก้เลย
"""
from .base import Market


class RealMarket(Market):
    def __init__(self, base_url: str = "", token: str = ""):
        self.base_url, self.token = base_url, token

    def open_round(self):
        # TODO: GET คำขอซื้อ (RFQ) รอบปัจจุบัน → list[RFQ]
        raise NotImplementedError("ยังไม่ได้ต่อตลาดจริง ใช้ MARKET=sim ไปก่อน")

    def submit(self, rfq, lot, sacks, price):
        # TODO: POST ข้อเสนอ (lot ของทีม, กระสอบ, ราคา) → Offer
        raise NotImplementedError

    def close_round(self, offers):
        # TODO: รอผลรอบ → {offer_id: กระสอบที่ขายได้}
        raise NotImplementedError
