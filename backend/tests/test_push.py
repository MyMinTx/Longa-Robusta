"""การ์ด Push ต้องใช้คำเดียวกับหน้าแอป (handoff/01_for_backend.md ข้อ 6)"""
import json

from app import push
from app.config import settings


def _lot(grade):
    return {"lot_id": "LOT-T49-1", "moisture": {"current": 12.1},
            "pricing": {"value": 113.4, "floor": 90.7, "grade": grade},
            "inspection": {"defect_pct": 4.8, "vis_url": None}, "alert": None, "sales": None}


def test_ready_card_uses_thai_grade():
    for code, th in push.GRADE_TH.items():
        text = json.dumps(push.build("ready", _lot(code))[1], ensure_ascii=False)
        assert th in text and code not in text


def test_liff_url_falls_back_to_web(monkeypatch):
    monkeypatch.setattr(settings, "liff_id", "")
    assert push.liff_url("LOT-T49-1") == "https://longa-robusta.vercel.app/?lot=LOT-T49-1"
    monkeypatch.setattr(settings, "liff_id", "2000000000-AbCd")
    assert push.liff_url("LOT-T49-1") == "https://liff.line.me/2000000000-AbCd?lot=LOT-T49-1"
