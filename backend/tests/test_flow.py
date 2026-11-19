import time

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import settings
from app.main import app
from app.pricing import price
from app.sim.inspector import PROFILES, make_counts
from app.pricing import defect_pct

H = {"X-Dev-User": "farmer1", "X-Demo-Key": "tgr49-demo"}


def wait_for(c, lot_id, statuses, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        lot = c.get(f"/lots/{lot_id}", headers=H).json()
        if lot["status"] in statuses:
            return lot
        time.sleep(0.05)
    raise AssertionError(f"ไม่ถึงสถานะ {statuses} (ตอนนี้ {lot['status']})")


def test_full_flow_drying_to_sold():
    with TestClient(app) as c:
        lot = c.post("/demo/reset", headers=H).json()
        assert lot["status"] == "DRYING" and lot["inspection"] is None and lot["pricing"] is None
        lid = lot["lot_id"]

        # Track 1 + 2: แห้งถึงเกณฑ์ → ตรวจเมล็ด → พร้อมขาย หรือ ต้องดูแล
        lot = wait_for(c, lid, {"READY", "ALERT"})
        hist = [h["value"] for h in lot["moisture"]["history"]]
        assert hist[-3:] and all(v <= settings.moisture_target for v in hist[-3:])
        assert lot["inspection"]["total"] >= 60 and lot["inspection"]["vis_url"].endswith(".jpg")
        if lot["status"] == "ALERT":
            lot = c.post(f"/lots/{lid}/inspect?improved=true", headers=H).json()
        assert lot["status"] == "READY"
        p = lot["pricing"]
        assert p == price(lot["inspection"]["defect_pct"], lot["moisture"]["current"])
        assert c.get("/" + lot["inspection"]["vis_url"].split("/", 3)[3]).status_code == 200

        # Track 3: ยืนยันขาย (กดซ้ำได้) → Agent ขายในตลาดจำลอง → ขายแล้ว
        assert c.post(f"/lots/{lid}/sell", headers=H).json()["status"] == "SELLING"
        assert c.post(f"/lots/{lid}/sell", headers=H).status_code == 200
        lot = wait_for(c, lid, {"SOLD"})
        floor = lot["pricing"]["floor"]
        assert lot["sales"]["sold_sacks"] == lot["sacks"]
        assert all(i["price"] >= floor for i in lot["sales"]["items"])
        offers = [e for e in lot["events"] if e["kind"] == "offer"]
        assert offers and all(e["price"] >= floor for e in offers)
        kinds = {p["kind"] for p in c.get("/debug/pushes", headers=H).json() if lid in p["lot_id"]}
        assert {"ready", "sold"} <= kinds


def test_sell_rules():
    with TestClient(app) as c:
        lid = c.post("/demo/reset", headers=H).json()["lot_id"]
        assert c.post(f"/lots/{lid}/sell", headers=H).status_code == 409          # ยังตากอยู่
        other = {"X-Dev-User": "someone-else"}
        assert c.get(f"/lots/{lid}", headers=other).status_code == 403          # ไม่ใช่เจ้าของ
        db.x("UPDATE lots SET status='READY', inspection=?, updated_at=? WHERE lot_id=?",
             ('{"defect_pct":3,"total":60,"class_counts":{}}', "2026-01-01T00:00:00+07:00", lid))
        assert c.post(f"/lots/{lid}/sell", headers=H).status_code == 423          # ข้อมูลเก่า


@pytest.mark.parametrize("profile", list(PROFILES))
def test_sim_profiles_match_grade(profile):
    (lo, hi), _, _ = PROFILES[profile]
    for _ in range(30):
        d = defect_pct(make_counts(profile))
        assert lo - 1.5 <= d <= hi + 1.5
