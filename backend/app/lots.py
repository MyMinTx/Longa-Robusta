"""กฎทางธุรกิจทั้งหมดของล็อตอยู่ที่ไฟล์นี้: แปลงเป็น JSON ตาม contract + state machine

ตัวจำลองและของจริงเรียกฟังก์ชันชุดเดียวกัน:
  - apply_reading()     ← Track 1 (sim หรือ ESP32)
  - apply_inspection()  ← Track 2 (sim หรือกล้อง)
  - record_offer() / record_sale() / close_unsold()  ← Track 3 (Agent)
"""
import json
import random
from datetime import timedelta

from . import db, push
from .config import settings
from .pricing import buyers, price
from .timeutil import iso, now, parse

STATUSES = ("DRYING", "READY", "SELLING", "SOLD", "ALERT")


class LotError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------- serialize
def _json(v):
    return json.loads(v) if v else None


def current_moisture(row):
    r = db.readings(row["lot_id"], limit=1)
    return r[-1]["value"] if r else row["moisture_start"]


def to_dict(row, with_events=True):
    lot_id = row["lot_id"]
    hist = db.readings(lot_id)
    m = hist[-1]["value"] if hist else row["moisture_start"]
    insp = _json(row["inspection"])
    locked = _json(row["locked"])
    pricing = locked or (price(insp["defect_pct"], m) if insp else None)
    evs = db.events(lot_id)
    sold = [e for e in evs if e["kind"] == "sold"]
    sold_sacks = sum(e["sacks"] for e in sold)
    avg = round(sum(e["price"] * e["sacks"] for e in sold) / sold_sacks, 2) if sold_sacks else None
    return {
        "lot_id": lot_id,
        "sacks": row["sacks"],
        "status": row["status"],
        "updated_at": row["updated_at"],
        "moisture": {
            "current": round(m, 2),
            "start": row["moisture_start"],
            "target": settings.moisture_target,
            "history": hist[-60:],
        },
        "inspection": insp,
        "pricing": pricing,
        "buyers": buyers(insp["defect_pct"], m) if insp else None,
        "alert": _json(row["alert"]),
        "sales": {
            "sold_sacks": sold_sacks,
            "avg_price": avg,
            "items": [{"ts": e["ts"], "sacks": e["sacks"], "price": e["price"], "buyer": e["buyer"]}
                      for e in reversed(sold)],
        },
        "events": [_event_out(e) for e in evs] if with_events else [],
        "simulated": {
            "moisture": settings.moisture_source == "sim",
            "inspection": settings.inspector == "sim",
            "market": settings.market == "sim",
        },
    }


def _event_out(e):
    return {k: e[k] for k in ("id", "ts", "kind", "text", "sacks", "price", "buyer", "result")}


def get(lot_id):
    row = db.get_lot_row(lot_id)
    if not row:
        raise LotError(404, "ไม่พบล็อตนี้")
    return row


# ---------------------------------------------------------------- create
def create(owner, sacks=None, moisture_start=None):
    lot_id = db.next_lot_id()
    while db.get_lot_row(lot_id):
        lot_id = lot_id + "x"
    db.create_lot(lot_id, owner, sacks or random.choice([3, 4, 5]),
                  moisture_start or round(random.uniform(17.5, 18.5), 2))
    db.add_event(lot_id, "state", "เริ่มตากล็อตใหม่")
    return db.get_lot_row(lot_id)


# ---------------------------------------------------------------- Track 1
def apply_reading(lot_id, value, source="sim"):
    row = get(lot_id)
    db.add_reading(lot_id, value, source)
    status = row["status"]
    target = settings.moisture_target

    if status == "DRYING":
        streak = row["ready_streak"] + 1 if value <= target else 0
        db.update_lot(lot_id, ready_streak=streak)
        if streak == settings.ready_streak:
            from .providers import inspector
            insp = inspector()
            if insp is not None:            # sim / camera: ตรวจเองตอนนี้เลย
                apply_inspection(lot_id, insp.inspect(lot_id))
            elif row["inspection"]:         # external: Track 2 ส่งผลมาก่อนแล้ว
                _evaluate(lot_id)
            else:                           # external: รอ Track 2 ส่ง /ingest/defect
                db.add_event(lot_id, "state", "แห้งถึงเกณฑ์แล้ว รอผลตรวจเมล็ด")
        return

    if status == "READY" and value > target:
        _to_alert(lot_id, {"kind": "moisture_up", "threshold": target,
                           "message": f"ความชื้นกลับขึ้นเป็น {value:.1f}% ควรตากต่อ"})
    elif status == "ALERT" and value <= target:
        alert = _json(row["alert"]) or {}
        if alert.get("kind") == "moisture_up":
            db.update_lot(lot_id, status="READY", alert=None)
            db.add_event(lot_id, "state", "ความชื้นกลับมาผ่านเกณฑ์แล้ว")
    else:
        db.update_lot(lot_id)  # แค่ขยับ updated_at


# ---------------------------------------------------------------- Track 2
def apply_inspection(lot_id, result):
    """รับผล Track 2 — ค่าที่จำเป็นมีค่าเดียวคือ % เมล็ดเสีย

    result = {
      "defect_pct": 4.8,                 # จำเป็น (หรือส่ง class_counts มาให้คำนวณแทน)
      "image_url": "https://…jpg",       # ไม่บังคับ (ภาพจาก URL ภายนอก)
      "vis_path": "static/vis/x.jpg",    # ไม่บังคับ (ภาพที่เซฟบน Pi)
      "class_counts": {...},             # ไม่บังคับ
    }
    """
    from .pricing import defect_pct as calc_defect
    get(lot_id)
    counts = result.get("class_counts")
    d = result.get("defect_pct")
    if d is None:
        if not counts:
            raise LotError(422, "ต้องมี defect_pct หรือ class_counts")
        d = calc_defect(counts)
    d = round(float(d), 2)
    if not 0 <= d <= 100:
        raise LotError(422, "defect_pct ต้องอยู่ระหว่าง 0–100")
    vis_url = result.get("image_url") or (
        f"{settings.public_base_url}/{result['vis_path']}" if result.get("vis_path") else None)
    insp = {
        "ts": iso(),
        "defect_pct": d,
        "vis_url": vis_url,
        "class_counts": counts,
        "total": sum(counts.values()) if counts else None,
        "grade_hint": result.get("grade_hint"),
    }
    db.update_lot(lot_id, inspection=insp)
    db.add_event(lot_id, "state", f"ได้ผลตรวจเมล็ด เสีย {d:.1f}%")
    _evaluate(lot_id)


def _evaluate(lot_id):
    """ตัดสินสถานะจากความชื้น + % เสีย (เรียกหลังมีข้อมูลใหม่)"""
    row = get(lot_id)
    insp = _json(row["inspection"])
    if not insp or row["status"] not in ("DRYING", "READY", "ALERT"):
        return
    if row["status"] == "DRYING" and row["ready_streak"] < settings.ready_streak:
        return  # ยังไม่แห้งพอ เก็บผลตรวจไว้ก่อน
    alert = _json(row["alert"]) or {}
    if alert.get("kind") == "moisture_up" and current_moisture(row) > settings.moisture_target:
        return  # ยังชื้นอยู่ รอความชื้นกลับมาผ่านเกณฑ์ก่อน
    if insp["defect_pct"] > settings.commercial_defect_max:
        _to_alert(lot_id, {"kind": "defect_high", "threshold": settings.commercial_defect_max,
                           "message": "เมล็ดเสียเกินเกณฑ์ผู้ซื้อเกรดพาณิชย์ (ไม่เกิน 7%)"})
    elif row["status"] != "READY":
        db.update_lot(lot_id, status="READY", alert=None, was_ready=1)
        db.add_event(lot_id, "state", "พร้อมขาย")
        if not row["was_ready"]:
            push.notify(lot_id, "ready")


def request_inspection(lot_id, improved=False):
    """ปุ่ม 'ขอตรวจใหม่' (improved=True จำลองว่าเกษตรกรคัดเมล็ดเสียออกแล้ว)"""
    row = get(lot_id)
    if row["status"] not in ("READY", "ALERT"):
        raise LotError(409, "ตรวจใหม่ได้เฉพาะตอนพร้อมขายหรือต้องดูแล")
    from .providers import inspector
    insp = inspector()
    if insp is None:  # external: ขอให้ Track 2 ส่งผลใหม่มาที่ /ingest/defect
        db.add_event(lot_id, "state", "ขอตรวจใหม่ รอผลจาก Track 2")
        db.update_lot(lot_id)
        return
    apply_inspection(lot_id, insp.inspect(lot_id, improved=improved))


def _to_alert(lot_id, alert):
    row = get(lot_id)
    if row["status"] == "ALERT" and (_json(row["alert"]) or {}).get("kind") == alert["kind"]:
        db.update_lot(lot_id, alert=alert)
        return
    db.update_lot(lot_id, status="ALERT", alert=alert)
    db.add_event(lot_id, "state", alert["message"])
    push.notify(lot_id, "alert")


# ---------------------------------------------------------------- Track 3
def start_selling(lot_id, owner):
    row = get(lot_id)
    if row["owner"] != owner:
        raise LotError(403, "ล็อตนี้ไม่ใช่ของคุณ")
    if row["status"] == "SELLING":
        return row  # กดซ้ำได้ผลเดิม
    if row["status"] not in ("READY", "ALERT"):
        raise LotError(409, "ล็อตนี้ยังขายไม่ได้")
    if (_json(row["alert"]) or {}).get("kind") == "moisture_up":
        raise LotError(409, "ความชื้นเกินเกณฑ์ ต้องตากต่อก่อนขาย")
    if parse(row["updated_at"]) < now() - timedelta(minutes=settings.stale_minutes):
        raise LotError(423, "ข้อมูลไม่อัปเดต รอข้อมูลล่าสุดก่อนขาย")
    lot = to_dict(row, with_events=False)
    if not lot["pricing"]:
        raise LotError(409, "ยังไม่มีผลตรวจเมล็ด")
    db.update_lot(lot_id, status="SELLING", locked=lot["pricing"])
    db.add_event(lot_id, "start", "เริ่มขาย (คุณกดยืนยัน)")
    from .providers import agent_manager
    mgr = agent_manager()
    if mgr is not None:  # sim / real: Agent ของเราขายเอง · external: รอ Track 3 ส่ง /ingest/sale
        mgr.start(lot_id)
    return db.get_lot_row(lot_id)


def record_offer(lot_id, ref, sacks, price_, buyer):
    db.add_event(lot_id, "offer", f"เสนอ {sacks} กระสอบ ให้{buyer} ที่ {price_:.1f}",
                 sacks=sacks, price=price_, buyer=buyer, result="pending", ref=ref)


def record_reject(lot_id, ref):
    db.update_event_result(lot_id, ref, "rejected")


def record_sale(lot_id, ref, sacks, price_, buyer=None):
    """รับผล Track 3 — ค่าที่จำเป็นมีค่าเดียวคือราคาที่ขายออก (บ./กก.)
    sacks=None = ขายทุกกระสอบที่เหลือในราคานี้ · buyer ไม่บังคับ"""
    row = get(lot_id)
    if row["status"] != "SELLING":
        raise LotError(409, "ล็อตนี้ไม่ได้อยู่ระหว่างขาย")
    left = remaining_sacks(lot_id)
    sacks = left if sacks is None else min(int(sacks), left)
    if sacks <= 0 or price_ <= 0:
        raise LotError(422, "ราคาหรือจำนวนกระสอบไม่ถูกต้อง")
    if ref:
        db.update_event_result(lot_id, ref, "sold")
    who = f" ให้{buyer}" if buyer else ""
    db.add_event(lot_id, "sold", f"ขาย {sacks} กระสอบ{who} ที่ {price_:.1f}",
                 sacks=sacks, price=price_, buyer=buyer, result="sold", ref=ref)
    floor = (_json(row["locked"]) or {}).get("floor")
    if floor and price_ < floor:
        db.add_event(lot_id, "state", f"คำเตือน: ราคา {price_:.1f} ต่ำกว่าราคาต่ำสุด {floor:.1f}")
    _check_sold_out(lot_id)


def remaining_sacks(lot_id):
    row = get(lot_id)
    sold = sum(e["sacks"] for e in db.events(lot_id) if e["kind"] == "sold")
    return row["sacks"] - sold


def _check_sold_out(lot_id):
    if remaining_sacks(lot_id) <= 0:
        db.update_lot(lot_id, status="SOLD")
        db.add_event(lot_id, "state", "ขายครบทุกกระสอบแล้ว")
        push.notify(lot_id, "sold")


# ---------------------------------------------------------------- ingest (3 พารามิเตอร์)
def active_lot(statuses, lot_id=None, strict=True):
    """ล็อตที่ค่าใหม่ควรเข้า

    - ระบุ lot_id มา → ใช้อันนั้น (ต้องอยู่ในสถานะที่กำหนด)
    - ไม่ระบุ → ดูเฉพาะล็อตที่ขยับภายใน STALE_MINUTES (ล็อตทิ้งค้างของคนอื่นไม่นับ)
        เหลือ 1 ล็อต = ใช้อันนั้น · ไม่เหลือเลย = ใช้ล็อตใหม่ล่าสุด
        เหลือหลายล็อต = strict: 409 ให้ส่ง lot_id มา · ไม่ strict (ESP32): ใช้ล็อตใหม่ล่าสุด
    """
    if lot_id:
        row = get(lot_id)
        if row["status"] not in statuses:
            raise LotError(409, f"{lot_id} อยู่ในสถานะ {row['status']} รับค่านี้ไม่ได้")
        return row
    rows = db.lots_by_status(*statuses)
    if not rows:
        raise LotError(409, f"ไม่มีล็อตที่อยู่ในสถานะ {', '.join(statuses)}")
    newest = lambda rs: max(rs, key=lambda r: (r["created_at"], r["lot_id"]))
    cutoff = now() - timedelta(minutes=settings.stale_minutes)
    recent = [r for r in rows if parse(r["updated_at"]) >= cutoff]
    if len(recent) == 1:
        return recent[0]
    if not recent:
        return newest(rows)
    if not strict:
        return newest(recent)
    ids = ", ".join(r["lot_id"] for r in sorted(recent, key=lambda r: r["created_at"], reverse=True)[:5])
    raise LotError(409, f"มีหลายล็อตกำลังใช้งาน ({ids}) ต้องส่ง lot_id มาด้วย")
