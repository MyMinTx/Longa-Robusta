"""TRACK 3 (จำลอง): ตลาดปลอมที่มีผู้ซื้อ 4 ราย หน้าตาคล้ายตลาดจริงของ Track 3

- เกรดพาณิชย์ (Commercial): รับเมล็ดเสีย ≤ 7% ความชื้น ≤ 12.5% จ่ายราว 97–106% ของราคาประเมิน
- กาแฟสำเร็จรูป (Instant):  รับเมล็ดเสีย ≤ 15% ความชื้น ≤ 14%  จ่ายราว 82–95%
แต่ละผู้ซื้อมีราคาสูงสุดที่ยอมจ่าย (ซ่อนไว้) ถ้าเสนอไม่เกินนั้นจะซื้อ
"""
import itertools
import random

from .base import RFQ, Market, Offer

BUYERS = [
    ("สยามคอมเมิร์ซ", "commercial"),
    ("ชุมพรคั่วบด", "commercial"),
    ("อินสแตนท์ไทย", "instant"),
    ("ทรีอินวันฟู้ดส์", "instant"),
]
RULES = {"commercial": (7.0, 12.5, (0.97, 1.06)), "instant": (15.0, 14.0, (0.82, 0.95))}


class SimMarket(Market):
    def __init__(self, seed=None):
        self.rnd = random.Random(seed)
        self.round_no = 0
        self._ids = itertools.count(1)
        self._willing = {}   # offer_id -> ราคาสูงสุดที่ผู้ซื้อยอมจ่าย

    def open_round(self):
        self.round_no += 1
        rfqs = []
        for i, (name, btype) in enumerate(self.rnd.sample(BUYERS, k=self.rnd.randint(2, 4)), 1):
            max_d, max_m, _ = RULES[btype]
            rfqs.append(RFQ(f"R{self.round_no}-{i:02d}", name, btype, self.rnd.randint(1, 6), max_d, max_m))
        return rfqs

    def submit(self, rfq, lot, sacks, price):
        oid = f"O{next(self._ids)}"
        d = lot["inspection"]["defect_pct"]
        m = lot["moisture"]["current"]
        lo, hi = RULES[rfq.buyer_type][2]
        eligible = d <= rfq.max_defect and m <= rfq.max_moisture
        self._willing[oid] = lot["pricing"]["value"] * self.rnd.uniform(lo, hi) if eligible else 0
        return Offer(oid, rfq, lot["lot_id"], sacks, price)

    def close_round(self, offers):
        out = {}
        for o in offers:
            ok = o.price <= self._willing.pop(o.offer_id, 0)
            out[o.offer_id] = min(o.sacks, o.rfq.sacks_wanted) if ok else 0
        return out
