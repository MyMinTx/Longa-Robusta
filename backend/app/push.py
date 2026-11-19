"""Push เข้า LINE ด้วย Flex Message
ไม่มี LINE_CHANNEL_ACCESS_TOKEN = ไม่ส่งจริง แค่บันทึกลง push_log (ดูได้ที่ GET /debug/pushes)
"""
import json
import logging
import threading
import uuid
from datetime import timedelta

import httpx

from . import db
from .config import settings
from .timeutil import iso, now

log = logging.getLogger("push")
PUSH_URL = "https://api.line.me/v2/bot/message/push"
GREEN, BROWN, RED, INK, MUTED = "#00813F", "#5A3A26", "#B3261E", "#23180F", "#6B5B4E"
WEB_URL = "https://longa-robusta.vercel.app"  # หน้าเว็บของมิ้น (ใช้เมื่อยังไม่ตั้ง LIFF_ID)
# ชื่อเกรดให้ตรงกับหน้าแอป (handoff/00 ข้อ 5)
GRADE_TH = {"PREMIUM": "พรีเมียม", "GRADE_1": "เกรด 1", "GRADE_2": "เกรด 2", "GRADE_3": "เกรด 3",
            "BELOW_STANDARD": "ต่ำกว่ามาตรฐาน", "REJECT": "ไม่ผ่าน"}


def grade_th(code):
    return GRADE_TH.get(code, code or "-")


def liff_url(lot_id):
    if settings.liff_id:
        return f"https://liff.line.me/{settings.liff_id}?lot={lot_id}"
    return f"{WEB_URL}/?lot={lot_id}"


def _row(label, value, bold=False):
    return {"type": "box", "layout": "horizontal", "contents": [
        {"type": "text", "text": label, "size": "sm", "color": MUTED, "flex": 4},
        {"type": "text", "text": value, "size": "sm", "color": INK, "align": "end", "flex": 6,
         "weight": "bold" if bold else "regular"}]}


def build(kind, lot):
    """คืน (altText, flex bubble)"""
    lid = lot["lot_id"]
    p = lot["pricing"] or {}
    insp = lot["inspection"] or {}
    if kind == "ready":
        alt = f"{lid} พร้อมขาย · {p.get('value', 0):.0f} บ./กก."
        chip, color, title = "พร้อมขาย", GREEN, f"{lid} ตากได้ที่แล้ว"
        rows = [_row("ความชื้น", f"{lot['moisture']['current']:.1f}% ✓"),
                _row("เมล็ดเสีย", f"{insp.get('defect_pct', 0):.1f}% · {grade_th(p.get('grade'))}"),
                _row("ราคาประเมิน", f"{p.get('value', 0):.1f} บ./กก.", bold=True),
                {"type": "text", "text": f"ระบบจะไม่ขายต่ำกว่า {p.get('floor', 0):.1f} บ./กก.",
                 "size": "xs", "color": MUTED, "wrap": True}]
        button = "ดูรายละเอียด"
    elif kind == "sold":
        s = lot["sales"]
        alt = f"{lid} ขายครบแล้ว · เฉลี่ย {s['avg_price']:.1f} บ./กก."
        chip, color, title = "ขายแล้ว", BROWN, f"{lid} ขายครบ {s['sold_sacks']} กระสอบ"
        rows = [_row("ราคาเฉลี่ย", f"{s['avg_price']:.1f} บ./กก.", bold=True),
                _row("ราคาต่ำสุดที่ตั้งไว้", f"{p.get('floor', 0):.1f} บ./กก.")]
        button = "ดูสรุปการขาย"
    else:  # alert
        a = lot["alert"] or {}
        alt = f"{lid} ต้องดูแล · {a.get('message', '')}"
        chip, color, title = "ต้องดูแล", RED, a.get("message", "มีเรื่องต้องดูแล")
        rows = []
        if insp:
            rows.append(_row("เมล็ดเสีย", f"{insp.get('defect_pct', 0):.1f}%"))
        rows.append(_row("ความชื้น", f"{lot['moisture']['current']:.1f}%"))
        button = "ดูวิธีแก้"

    bubble = {
        "type": "bubble",
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
            {"type": "text", "text": chip, "size": "xs", "weight": "bold", "color": color},
            {"type": "text", "text": title, "size": "md", "weight": "bold", "color": INK, "wrap": True},
            {"type": "box", "layout": "vertical", "spacing": "xs", "margin": "md", "contents": rows},
        ]},
        "footer": {"type": "box", "layout": "vertical", "contents": [
            {"type": "button", "style": "primary", "color": GREEN, "height": "md",
             "action": {"type": "uri", "label": button, "uri": liff_url(lid)}}]},
    }
    vis = insp.get("vis_url") or ""
    if vis.startswith("https://"):  # LINE รับเฉพาะภาพ HTTPS
        bubble["hero"] = {"type": "image", "url": vis, "size": "full", "aspectRatio": "20:13",
                          "aspectMode": "cover"}
    return alt, bubble


def _already_sent(lot_id, kind):
    since = "0000" if kind in ("ready", "sold") else iso(now() - timedelta(minutes=10))
    return db.push_sent(lot_id, kind, since)


def notify(lot_id, kind):
    from .lots import get, to_dict  # import ตรงนี้กันวนกัน
    if _already_sent(lot_id, kind):
        return
    row = get(lot_id)
    lot = to_dict(row, with_events=False)
    alt, bubble = build(kind, lot)
    message = {"type": "flex", "altText": alt[:400], "contents": bubble}
    if not settings.line_token or row["owner"].startswith("dev-"):
        db.log_push(lot_id, kind, False, json.dumps({"to": row["owner"], "message": message}, ensure_ascii=False))
        log.info("[push จำลอง] %s → %s", kind, alt)
        return
    db.log_push(lot_id, kind, True, alt)
    threading.Thread(target=_send, args=(row["owner"], message), daemon=True).start()


def _send(to, message):
    try:
        r = httpx.post(PUSH_URL, timeout=10, json={"to": to, "messages": [message]},
                       headers={"Authorization": f"Bearer {settings.line_token}",
                                "X-Line-Retry-Key": str(uuid.uuid4())})
        if r.status_code >= 300:
            log.error("Push ไม่สำเร็จ %s %s", r.status_code, r.text)
    except httpx.HTTPError as e:
        log.error("Push ไม่สำเร็จ: %s", e)
