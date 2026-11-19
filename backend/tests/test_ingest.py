"""โหมด external: ทีม Track 1–3 ยิงค่าเข้ามาเองแค่ 3 พารามิเตอร์"""
import pytest
from fastapi.testclient import TestClient

from app import db, providers
from app.config import settings
from app.main import app

H = {"X-Dev-User": "farmer-ext", "X-Demo-Key": "tgr49-demo"}
I = {"X-Ingest-Key": "tgr49-ingest"}


@pytest.fixture
def external(monkeypatch):
    for k in ("moisture_source", "inspector", "market"):
        monkeypatch.setattr(settings, k, "external")
    providers.inspector.cache_clear()
    providers.agent_manager.cache_clear()
    yield
    providers.inspector.cache_clear()
    providers.agent_manager.cache_clear()


def test_three_params_defect_first(external):
    with TestClient(app) as c:
        lot = c.post("/demo/reset", headers=H).json()
        assert lot["simulated"] == {"moisture": False, "inspection": False, "market": False}
        assert c.post("/ingest/moisture", json={"moisture": 15}).status_code == 403   # ไม่มี key

        # Track 2 ส่ง % เสียมาก่อน → เก็บไว้ ยังไม่พร้อมขายเพราะยังชื้น
        lot = c.post("/ingest/defect", headers=I, json={"defect_pct": 4.8}).json()
        assert lot["status"] == "DRYING" and lot["pricing"]["value"] > 0

        # Track 1 ความชื้นผ่านเกณฑ์ 3 ครั้ง → พร้อมขาย
        for v in (14.0, 12.4, 12.2, 12.1):
            lot = c.post("/ingest/moisture", headers=I, json={"moisture": v}).json()
        assert lot["status"] == "READY"
        assert lot["pricing"]["value"] == 114.24 and lot["pricing"]["floor"] == 91.39

        # ผู้ใช้กดยืนยัน → รอ Track 3 ส่งราคาขาย
        lid = lot["lot_id"]
        assert c.post(f"/lots/{lid}/sell", headers=H).json()["status"] == "SELLING"
        lot = c.post("/ingest/sale", headers=I, json={"price": 113.4}).json()
        assert lot["status"] == "SOLD"
        assert lot["sales"]["sold_sacks"] == lot["sacks"] and lot["sales"]["avg_price"] == 113.4
        kinds = {p["kind"] for p in c.get("/debug/pushes", headers=H).json() if p["lot_id"] == lid}
        assert {"ready", "sold"} <= kinds


def test_three_params_moisture_first_then_bad_defect(external):
    with TestClient(app) as c:
        c.post("/demo/reset", headers=H)
        for v in (12.4, 12.3, 12.2):
            lot = c.post("/ingest/moisture", headers=I, json={"moisture": v}).json()
        assert lot["status"] == "DRYING"                       # แห้งแล้วแต่รอผลตรวจ
        lot = c.post("/ingest/defect", headers=I, json={"defect_pct": 9.1}).json()
        assert lot["status"] == "ALERT" and lot["alert"]["kind"] == "defect_high"
        lot = c.post("/ingest/defect", headers=I, json={"defect_pct": 3.0}).json()  # คัดแล้วตรวจใหม่
        assert lot["status"] == "READY" and lot["pricing"]["grade"] == "GRADE_1"


def test_sale_per_sack(external):
    with TestClient(app) as c:
        lid = c.post("/demo/reset", headers=H).json()["lot_id"]
        c.post("/ingest/defect", headers=I, json={"defect_pct": 2.0})
        for v in (12.4, 12.3, 12.2):
            c.post("/ingest/moisture", headers=I, json={"moisture": v})
        c.post(f"/lots/{lid}/sell", headers=H)
        sacks = c.get(f"/lots/{lid}", headers=H).json()["sacks"]
        for i in range(sacks):
            lot = c.post("/ingest/sale", headers=I, json={"price": 110 + i, "sacks": 1}).json()
        assert lot["status"] == "SOLD" and lot["sales"]["sold_sacks"] == sacks
        assert c.post("/ingest/sale", headers=I, json={"price": 100}).status_code == 409


def test_threshold_is_12_5(external):
    assert settings.moisture_target == 12.5
    with TestClient(app) as c:
        c.post("/demo/reset", headers=H)
        for v in (12.6, 12.55, 12.51):                         # เกิน 12.5 นิดเดียวก็ยังไม่ผ่าน
            lot = c.post("/ingest/moisture", headers=I, json={"moisture": v}).json()
        assert lot["moisture"]["target"] == 12.5 and "แห้งถึงเกณฑ์" not in str(lot)
        c.post("/ingest/defect", headers=I, json={"defect_pct": 2.0})
        for v in (12.0, 11.9, 11.8):
            lot = c.post("/ingest/moisture", headers=I, json={"moisture": v}).json()
        assert lot["status"] == "READY"


def test_cannot_sell_while_moisture_up(external):
    with TestClient(app) as c:
        lid = c.post("/demo/reset", headers=H).json()["lot_id"]
        c.post("/ingest/defect", headers=I, json={"defect_pct": 2.0})
        for v in (12.0, 11.9, 11.8, 12.6):                     # พร้อมขายแล้วความชื้นกลับขึ้น
            lot = c.post("/ingest/moisture", headers=I, json={"moisture": v}).json()
        assert lot["status"] == "ALERT" and lot["alert"]["kind"] == "moisture_up"
        r = c.post(f"/lots/{lid}/sell", headers=H)
        assert r.status_code == 409 and "ตากต่อ" in r.json()["detail"]


def test_ingest_picks_lot_safely(external):
    with TestClient(app) as c:
        a = c.post("/demo/reset", headers=H).json()["lot_id"]
        b = c.post("/demo/reset", headers={**H, "X-Dev-User": "farmer-b"}).json()["lot_id"]
        r = c.post("/ingest/moisture", headers=I, json={"moisture": 15})
        assert r.status_code == 409 and a in r.json()["detail"] and b in r.json()["detail"]
        assert {l["lot_id"] for l in c.get("/ingest/lots", headers=I).json()} >= {a, b}
        lot = c.post("/ingest/moisture", headers=I, json={"moisture": 15, "lot_id": b}).json()
        assert lot["lot_id"] == b and lot["moisture"]["current"] == 15
        # ล็อตที่ทิ้งไว้เกิน 30 นาทีไม่นับ → ไม่ต้องส่ง lot_id
        db.x("UPDATE lots SET updated_at='2026-01-01T00:00:00+07:00' WHERE lot_id=?", (a,))
        assert c.post("/ingest/moisture", headers=I, json={"moisture": 14}).json()["lot_id"] == b
        for lid in (a, b):                                      # เก็บกวาด ไม่ให้กวนเทสต์อื่น
            db.delete_lot(lid)
