# API contract — TGR-49 LINE Mini App (v0.2)

> ใช้ร่วมกัน 3 ฝั่ง: **หน้าแอป (มิ้น)** · **Backend (ธร)** · **LINE/Push (กาฟิว)**
> เปลี่ยนฟิลด์ใดต้องบอกทั้ง 3 คนก่อน · ตัวอย่างจริงทุกสถานะอยู่ใน `mock/*.json` (สร้างจาก backend ตัวจริง)

## 1. หลักการ: แอปรับข้อมูลจาก 3 Track แค่ 3 ค่า

| Track | ค่าที่ส่งเข้า | หน่วย | ใช้ทำอะไร |
|---|---|---|---|
| 1 | `moisture` ความชื้น | % | หน้ากำลังตาก · ตัดสินพร้อมขาย (≤ 12.5% ติดกัน 3 ครั้ง · ตั้งได้ที่ `MOISTURE_TARGET`) · ตัวคูณ M |
| 2 | `defect_pct` % เมล็ดเสีย | % | เกรด · ตัวคูณ G · เกณฑ์ต้องดูแล (> 7%) · ประเภทผู้ซื้อ |
| 3 | `price` ราคาที่ขายออก | บาท/กก. | หน้าขายแล้ว · Push ขายได้แล้ว |

**ราคาประเมินและราคาต่ำสุด backend คำนวณเอง** (ไฟล์ `app/pricing.py`):

```
ราคาประเมิน = 120 × G × M × S
  G = (1 − d/100) × ตัวคูณเกรด   (d ≤1%:1.08 · ≤3%:1.04 · ≤5%:1.00 · ≤7%:0.96 · ≤15%:0.85 · อื่น ๆ:0.60)
  M = 1 ถ้าความชื้น ≤ 12.5 · ≤ 15: (1−m/100)/0.875 − 0.02×(m−12.5) · เกิน 15: 0.6
  S = ขนาดเมล็ด (ยังไม่มีคนวัด ใช้ 1.0)
ราคาต่ำสุด = 0.8 × ราคาประเมิน   (ขายไม่ออกตอนปิดตลาดได้ 80% อยู่แล้ว)
```
ตัวอย่าง: เสีย 4.8%, ชื้น 11.9% → GRADE_2 · ราคาประเมิน **114.24** · ราคาต่ำสุด **91.39**

## 2. ส่งค่าเข้า (Track 1–3 → Backend)

ทุกตัวต้องมี header `X-Ingest-Key: <INGEST_KEY>` · `lot_id` ไม่ใส่ก็ได้ ถ้ามีล็อตที่ใช้งานอยู่ (ขยับภายใน 30 นาที) แค่ล็อตเดียว ระบบเลือกให้เอง
ถ้ามีหลายล็อตจะตอบ **409** พร้อมรายชื่อล็อต → ส่ง `lot_id` มาด้วย · ดูรายการได้ที่ `GET /ingest/lots`

```http
POST /ingest/moisture   {"moisture": 12.31}
POST /ingest/defect     {"defect_pct": 4.8, "image_url": "https://…jpg"}   ← image_url ไม่บังคับ
POST /ingest/sale       {"price": 113.4}                                    ← ขายทุกกระสอบที่เหลือที่ราคานี้
POST /ingest/sale       {"price": 112.0, "sacks": 1, "buyer": "ชุมพรคั่วบด"}  ← หรือส่งทีละกระสอบ
```

| กรณี | ผล |
|---|---|
| ส่ง defect ก่อนแห้ง | เก็บไว้ ยังเป็น DRYING (แสดงราคาประเมินได้แล้ว) |
| แห้งก่อนแต่ยังไม่มี defect | ยังเป็น DRYING รอ defect (event "แห้งถึงเกณฑ์แล้ว รอผลตรวจเมล็ด") |
| ส่ง sale ตอนล็อตไม่ได้อยู่ระหว่างขาย | 409 (ต้องให้ผู้ใช้กดยืนยันขายในแอปก่อน) |
| ไม่ใส่ `lot_id` แต่มีหลายล็อตกำลังใช้งาน | 409 "มีหลายล็อตกำลังใช้งาน (…) ต้องส่ง lot_id มาด้วย" |
| ผู้ใช้กดขายตอน ALERT ชนิด `moisture_up` | 409 "ความชื้นเกินเกณฑ์ ต้องตากต่อก่อนขาย" |
| ราคาขายต่ำกว่าราคาต่ำสุด | รับไว้ แต่บันทึกคำเตือนใน events |

ตัวอย่างยิงด้วย Python (ทีม Track 1/2/3):
```python
import httpx
API = "https://<API_BASE>"; H = {"X-Ingest-Key": "<INGEST_KEY>"}
httpx.post(f"{API}/ingest/moisture", headers=H, json={"moisture": 12.31})
httpx.post(f"{API}/ingest/defect",   headers=H, json={"defect_pct": 4.8})
httpx.post(f"{API}/ingest/sale",     headers=H, json={"price": 113.4})
```

ในแต่ละ Track ตั้งใน `.env` ของ backend ได้ 3 แบบ: `sim` (ตัวจำลองในเครื่อง) · `external` (รอค่าจาก /ingest) · ของจริงในเครื่อง (`serial` / `camera` / `real`)

## 3. Endpoints สำหรับแอป (มิ้นเรียก)

Header: `Authorization: Bearer <liff.getIDToken()>`
(ตอนพัฒนาที่ backend ยังไม่ใส่ `LIFF_CHANNEL_ID` ใช้ `X-Dev-User: <ชื่ออะไรก็ได้>` แทน)

| Method | Path | ใช้เมื่อ | ตอบ |
|---|---|---|---|
| GET | `/health` | เช็กว่า backend ยังอยู่ | `{"ok":true,…}` |
| GET | `/lots/latest` | เปิดแอป (ไม่มีล็อต = สร้างให้) | Lot |
| GET | `/lots/{lot_id}` | เปิดจากลิงก์ใน Push (`?lot=`) | Lot |
| GET | `/lots/{lot_id}/events?since_id=N` | หน้ากำลังขาย ดึงทุก 5 วิ | `[Event]` ใหม่สุดก่อน |
| POST | `/lots/{lot_id}/sell` | กดยืนยันขาย (กดซ้ำได้ผลเดิม) | Lot |
| POST | `/lots/{lot_id}/inspect` | ปุ่ม "ขอตรวจใหม่" | Lot |
| POST | `/lots` | ปุ่ม "เริ่มล็อตใหม่" (หลังขายเสร็จ) | Lot |

Error ทุกตัวตอบ `{"detail": "<ข้อความภาษาไทยพร้อมแสดงผู้ใช้>"}`

| code | ความหมาย | แอปควรทำ |
|---|---|---|
| 401 | ยืนยันตัวตนไม่ผ่าน | `liff.login()` ใหม่ |
| 403 | ไม่ใช่ล็อตของผู้ใช้นี้ | แสดง detail |
| 404 | ไม่พบล็อต | กลับไป `/lots/latest` |
| 409 | สถานะไม่ถูก (เช่น ยังขายไม่ได้) | ดึงล็อตใหม่แล้ววาดหน้าใหม่ |
| 423 | ข้อมูลเก่ากว่า 30 นาที | แสดงหน้าข้อมูลไม่อัปเดต |

## 4. Lot object

| ฟิลด์ | ชนิด | หมายเหตุ |
|---|---|---|
| `lot_id` | string | `LOT-T49-1` |
| `sacks` | int | จำนวนกระสอบ |
| `status` | `DRYING` `READY` `SELLING` `SOLD` `ALERT` | เลือกหน้าจอจากค่านี้ |
| `updated_at` | ISO +07:00 | เก่ากว่า 30 นาที = แสดงแบนเนอร์ข้อมูลไม่อัปเดต + ปิดปุ่มขาย |
| `moisture.current` / `start` / `target` | number | target = 12.5 (จาก `MOISTURE_TARGET`) |
| `moisture.history[]` | `{ts, value, source}` | สูงสุด 60 ค่าล่าสุด เรียงเก่า→ใหม่ |
| `inspection` | object \| **null** | null = ยังไม่มีผลตรวจ |
| `inspection.defect_pct` | number | **ค่าหลักของ Track 2** |
| `inspection.vis_url` | string \| null | ภาพประกอบ (มีหรือไม่มีก็ได้) |
| `inspection.class_counts` / `total` | object \| null | มีเฉพาะตัวจำลองหรือกล้องที่ส่งมา · แอปต้องรองรับ null |
| `pricing` | object \| **null** | null เมื่อยังไม่มีผลตรวจ · `{base, grade, grade_mult, G, M, S, size_source, value, floor, floor_ratio}` |
| `buyers` | `{commercial, instant}` \| null | ขายให้ผู้ซื้อเกรดพาณิชย์ / กาแฟสำเร็จรูปได้ไหม |
| `alert` | null \| `{kind, threshold, message}` | kind = `defect_high` · `moisture_up` |
| `sales` | `{sold_sacks, avg_price, items[]}` | items = `{ts, sacks, price, buyer\|null}` |
| `events[]` | ใหม่สุดก่อน | `{id, ts, kind, text, sacks, price, buyer, result}` · kind = `state` `start` `offer` `sold` · **`text` แสดงได้ทันที** |
| `simulated` | `{moisture, inspection, market}` | มี true ตัวไหน = แสดงป้าย "ข้อมูลจำลอง" |

ค่า `pricing` หลังกดยืนยันขายจะถูกล็อก (ไม่เปลี่ยนตามความชื้นอีก)

## 5. สถานะ และ Push

| จาก | ไป | เมื่อ | Push |
|---|---|---|---|
| (ใหม่) | DRYING | สร้างล็อต | — |
| DRYING | READY | ชื้น ≤ 12.5 ติดกัน 3 ครั้ง **และ** มี defect ≤ 7 | พร้อมขาย (ครั้งแรกครั้งเดียว) |
| DRYING/READY | ALERT | defect > 7 · หรือเคย READY แล้วชื้นกลับ > 12.5 | ต้องดูแล (เว้น 10 นาที) |
| ALERT | READY | ตรวจใหม่ผ่าน · ชื้นกลับมาผ่าน | — |
| READY/ALERT | SELLING | ผู้ใช้กดยืนยันขาย | — |
| SELLING | SOLD | ขายครบทุกกระสอบ | ขายได้แล้ว |

ปุ่มในการ์ด Push เปิด `https://liff.line.me/<LIFF_ID>?lot=<lot_id>`

## 6. ค่าที่เปลี่ยนจาก v0.1
- Track 2 ส่งแค่ `defect_pct` (class_counts / ภาพ ไม่บังคับ) · Track 3 ส่งแค่ `price` (sacks / buyer ไม่บังคับ)
- เพิ่ม `/ingest/*` และโหมด `external`
- ช่วง DRYING `inspection` และ `pricing` เป็น null ได้
