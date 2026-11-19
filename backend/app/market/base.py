"""หน้าตาของ "ตลาด" ที่ Agent ใช้ ตลาดจำลองและตลาดจริงต้องมีเมธอดชุดนี้เหมือนกัน"""
from dataclasses import dataclass


@dataclass
class RFQ:
    """คำขอซื้อจากผู้ซื้อ 1 ราย ในรอบตลาดนั้น"""
    rfq_id: str
    buyer: str
    buyer_type: str        # "commercial" | "instant"
    sacks_wanted: int
    max_defect: float      # % เมล็ดเสียสูงสุดที่รับ
    max_moisture: float    # % ความชื้นสูงสุดที่รับ


@dataclass
class Offer:
    offer_id: str
    rfq: RFQ
    lot_id: str
    sacks: int
    price: float


class Market:
    def open_round(self) -> list[RFQ]:
        """เปิดรอบใหม่ คืนคำขอซื้อของรอบนี้"""
        raise NotImplementedError

    def submit(self, rfq: RFQ, lot: dict, sacks: int, price: float) -> Offer:
        """ส่งข้อเสนอขาย lot = dict ตาม contract (ใช้ pricing/inspection/moisture)"""
        raise NotImplementedError

    def close_round(self, offers: list[Offer]) -> dict[str, int]:
        """ปิดรอบ คืน {offer_id: จำนวนกระสอบที่ขายได้ (0 = ไม่ได้)}"""
        raise NotImplementedError
