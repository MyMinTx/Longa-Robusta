# TGR-49 · Backend ของ LINE Mini App (มีตัวจำลองครบ 3 Track)

ระบบรันได้ทั้งวงจรโดย **ไม่ต้องมี ESP32, กล้อง หรือตลาดจริง** ทุก Track เป็นตัวจำลองที่ส่งข้อมูลหน้าตาเดียวกับของจริง
วันที่ของจริงพร้อม แก้แค่สวิตช์ใน `.env` แอปไม่ต้องเปลี่ยน

แอปรับข้อมูลจาก 3 Track แค่ 3 ค่า: **ความชื้น** · **% เมล็ดเสีย** · **ราคาที่ขายออก** (รายละเอียด `docs/contract.md`)

| Track | ค่าที่ส่ง | `sim` (ตอนนี้) | `external` (ทีมอื่นยิงเข้ามา) | ของจริงในเครื่องนี้ |
|---|---|---|---|---|
| 1 | ความชื้น | `app/sim/moisture.py` ค่าปลอมทุก 30 วิ | `POST /ingest/moisture` | `serial` อ่าน ESP32 (พร้อมใช้) |
| 2 | % เมล็ดเสีย | `app/sim/inspector.py` สุ่มเกรด + ภาพปลอม เมื่อแห้งถึงเกณฑ์ | `POST /ingest/defect` | `camera` (โครงให้กาฟิวเติม) |
| 3 | ราคาที่ขายออก | `app/market/sim_market.py` ตลาดปลอม + Agent | `POST /ingest/sale` | `real` (โครงต่อ API ตลาดจริง) |

สวิตช์: `MOISTURE_SOURCE` · `INSPECTOR` · `MARKET` ใน `.env`

Agent (`app/market/agent.py`) ใช้ได้กับตลาดทั้งสองแบบ และ **ไม่เสนอต่ำกว่าราคาต่ำสุด (80%) เด็ดขาด**

## เริ่มใช้ (5 นาที)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
เปิด http://localhost:8000/docs เพื่อลองเรียก API ทุกตัว

ทดสอบทั้งวงจร ทั้งโหมดจำลองและโหมดรับ 3 ค่า (9 เทสต์) ใน ~1 วินาที:
```bash
python3 -m pytest -q
```

## สิ่งที่เกิดขึ้นเองเมื่อรัน

1. ผู้ใช้เปิดแอป → `GET /lots/latest` สร้างล็อตใหม่ให้ถ้ายังไม่มี (สถานะ `DRYING`)
2. **Track 1** ส่งความชื้นทุก 30 วิ ลดครั้งละ 0.25–0.55%
3. ผ่าน ≤ 12.5% ติดกัน 3 ครั้ง → **Track 2** สุ่มเกรด (premium / good / fair / poor) สร้างผลตรวจ + ภาพ
   - เสีย ≤ 7% → `READY` + Push "พร้อมขาย"
   - เสีย > 7% → `ALERT` + Push "ต้องดูแล" (กด "ขอตรวจใหม่" `?improved=true` = จำลองว่าคัดเมล็ดแล้ว)
4. ผู้ใช้กดยืนยัน → `POST /lots/{id}/sell` → `SELLING` ราคาถูกล็อกไว้
5. **Track 3** Agent เปิดรอบตลาดทุก 10 วิ เสนอ 103% ของราคาประเมินแล้วลดรอบละ 2% (ไม่ต่ำกว่า floor)
6. ขายครบ → `SOLD` + Push "ขายได้แล้ว" · ครบ 12 รอบยังเหลือ = ตลาดรับซื้อที่ 80%

ช่วงที่ยังใช้ตัวจำลอง ทุก lot มี `"simulated": {...}` ให้หน้าเว็บแสดงป้าย "ข้อมูลจำลอง"

## รับค่าจาก Track 1–3 (โหมด external)

```bash
I="X-Ingest-Key: tgr49-ingest"; J="Content-Type: application/json"
curl -X POST localhost:8000/ingest/moisture -H "$I" -H "$J" -d '{"moisture": 12.3}'
curl -X POST localhost:8000/ingest/defect   -H "$I" -H "$J" -d '{"defect_pct": 4.8}'
curl -X POST localhost:8000/ingest/sale     -H "$I" -H "$J" -d '{"price": 113.4}'
```

## API

| | Path | หมายเหตุ |
|---|---|---|
| GET | `/health` | บอกด้วยว่าแต่ละ Track เป็น sim หรือของจริง |
| GET | `/lots/latest` | ล็อตล่าสุดของผู้ใช้ |
| POST | `/lots` | เริ่มล็อตใหม่ |
| GET | `/lots/{id}` · `/lots/{id}/events?since_id=` | หน้ากำลังขายดึง events ทุก 5 วิ |
| POST | `/lots/{id}/sell` | ยืนยันขาย (กดซ้ำได้) · 409 ยังไม่พร้อม · 423 ข้อมูลเก่ากว่า 30 นาที |
| POST | `/lots/{id}/inspect?improved=true` | ขอตรวจใหม่ |

ตัวตนผู้ใช้: ถ้า `LIFF_CHANNEL_ID` ว่าง = โหมดพัฒนา ใช้ header `X-Dev-User` แทน LINE login
ถ้าใส่แล้ว หน้าเว็บต้องส่ง `Authorization: Bearer <liff.getIDToken()>`

### ปุ่มเดโม (ต้องมี header `X-Demo-Key`)

```bash
K="X-Demo-Key: tgr49-demo"; U="X-Dev-User: user"
curl -X POST localhost:8000/demo/reset -H "$K" -H "$U"                                  # ล็อตใหม่ 18%
curl -X POST localhost:8000/demo/speed -H "$K" -H "Content-Type: application/json" \
     -d '{"moisture_tick_seconds": 2, "market_round_seconds": 2}'                        # เร่งเวลา (~40 วิ ถึงพร้อมขาย)
curl -X POST localhost:8000/demo/lots/LOT-T49-1/reading -H "$K" -H "Content-Type: application/json" -d '{"value": 12.1}'
curl localhost:8000/debug/state -H "$K"      # ทุกล็อต
curl localhost:8000/debug/pushes -H "$K"     # Push ที่ส่ง/จำลองส่ง (มี Flex JSON เต็ม)
```

## Push
ไม่มี `LINE_CHANNEL_ACCESS_TOKEN` หรือผู้ใช้เป็น `dev-…` = ไม่ส่งจริง บันทึก Flex JSON ไว้ที่ `/debug/pushes`
(เอาไปวางใน LINE Flex Message Simulator ดูหน้าตาได้) · ภาพใน Flex แสดงเมื่อ `PUBLIC_BASE_URL` เป็น https เท่านั้น

## เปลี่ยนเป็นของจริง

- **ESP32:** `MOISTURE_SOURCE=serial` + `SERIAL_PORT=/dev/ttyUSB0` (ค่าเข้าล็อตล่าสุดที่ยังไม่ขาย เมื่อกดปุ่มบน ESP32)
- **กล้อง:** เติม `CameraInspector.inspect()` ให้คืน `{class_counts, vis_path, ms}` แล้วตั้ง `INSPECTOR=camera`
- **ตลาด:** เติม 3 เมธอดใน `RealMarket` ตาม `docs/market-api.md` แล้วตั้ง `MARKET=real`

## โครงไฟล์
```
app/
  main.py            API + เริ่มตัวจำลองตอนเปิด
  lots.py            กฎทั้งหมด: JSON ตาม contract + state machine
  pricing.py         สูตรตลาด 120×G×M×S, floor 80%
  push.py            Flex Message + ส่ง Push
  auth.py            ตรวจ ID token ของ LIFF
  providers.py       สวิตช์ sim ↔ ของจริง
  sim/               ตัวจำลอง Track 1, 2
  market/            ตลาดจำลอง, ตลาดจริง (โครง), Agent
  real/              ESP32 (พร้อมใช้), กล้อง (โครง)
docs/                contract, serial, แบบฟอร์ม API ตลาด
mock/                JSON ตัวอย่าง 6 สถานะ (ให้หน้าเว็บใช้ระหว่างพัฒนา)
tests/               เทสต์ทั้งวงจร
```
