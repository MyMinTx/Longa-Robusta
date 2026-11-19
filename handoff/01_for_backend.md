# 01 · สำหรับธร — ต่อ Backend เข้ากับหน้าเว็บ

> อ่าน `00_README_web_status.md` ข้อ 4 ก่อน (หน้าเว็บเรียก endpoint ไหน ส่ง header อะไร)
> ไฟล์นี้อ้างอิงโค้ด `code/tgr49-backend/` ชุดเดิม (`app/main.py`, `auth.py`, `config.py`, `push.py`, `lots.py`)
> หน้าเว็บ **ไม่ได้เปลี่ยน contract** — ใช้ฟิลด์ตาม `05_API_contract.md` ทุกตัว

---

## 1. สิ่งที่มิ้นต้องได้จากธร

| ค่า | ส่งทาง | ใช้ทำอะไร |
|---|---|---|
| `API_BASE` = URL tunnel HTTPS เช่น `https://tgr49-pi.tailxxxx.ts.net` (**ไม่มี / ท้าย**) | แชตกลุ่มได้ | ใส่ใน `web/config.js` |
| `DEMO_KEY` (ค่าที่ตั้งใหม่ใน `.env`) | **แชตส่วนตัวเท่านั้น** | มิ้น/คนกดเดโมใส่ในมือถือครั้งแรกที่กดปุ่มเดโม (ไม่ได้ใส่ในโค้ด) |
| แจ้งเมื่อใส่ `LIFF_CHANNEL_ID` แล้ว | แชตกลุ่ม | ต้องเปิดพร้อมกับที่มิ้นใส่ `LIFF_ID` (ข้อ 3) |

URL tunnel ต้องเป็น **https** — หน้าเว็บอยู่บน https (Vercel) เบราว์เซอร์จะบล็อกการเรียก http

---

## 2. `.env` ที่ต้องตั้งเพื่อให้หน้าเว็บใช้ได้

| ค่า | ตั้งเป็น | ถ้าไม่ตั้ง จะเกิดอะไร |
|---|---|---|
| `CORS_ORIGINS` | `https://tgr49-liff.vercel.app,http://localhost:5173` | ค่าเริ่มต้น `*` ใช้ได้อยู่แล้ว · ถ้าจะจำกัดโดเมน ต้องมี 2 อันนี้ (อันหลังให้มิ้นทดสอบบนเครื่อง) · `allow_headers=["*"]` ในโค้ดรับ `Authorization` `X-Dev-User` `X-Demo-Key` ได้แล้ว |
| `PUBLIC_BASE_URL` | URL tunnel **https** เดียวกับ `API_BASE` | `vis_url` จะเป็น `http://localhost:8000/static/vis/…` → มือถือโหลดภาพไม่ได้ (หน้าเว็บจะใช้ไอคอนแทน) และการ์ด Push ไม่มีภาพ (Flex รับเฉพาะ https) |
| `LIFF_ID` | LIFF ID จากกาฟิว | ปุ่มใน Push จะลิงก์ไป `PUBLIC_BASE_URL/?lot=…` ซึ่งเป็น **backend ไม่ใช่หน้าเว็บ** (`push.py` ฟังก์ชัน `liff_url`) |
| `LIFF_CHANNEL_ID` | Channel ID ของ channel ที่มี LIFF (LINE Login / MINI App) จากกาฟิว | โหมดพัฒนา: ทุกคนที่เปิดผ่าน LINE จะเป็นผู้ใช้เดียวกัน และไม่ได้ Push จริง (ข้อ 3) |
| `LINE_CHANNEL_ACCESS_TOKEN` | token ของ Messaging API จากกาฟิว (แชตส่วนตัว) | Push ไม่ส่งจริง แค่บันทึกที่ `/debug/pushes` |
| `DEMO_KEY` | **ตั้งใหม่** (สุ่มยาว ๆ) | ค่าเริ่มต้น `tgr49-demo` อยู่ในโค้ดที่แชร์กันอยู่ ใครก็ลบล็อตได้ |
| `INGEST_KEY` | **ตั้งใหม่** ส่งให้ทีม Track 1–3 | ค่าเริ่มต้น `tgr49-ingest` อยู่ในโค้ดเช่นกัน |

แก้ `.env` แล้วต้องรีสตาร์ต: `sudo systemctl restart tgr49`

---

## 3. ตัวตนผู้ใช้ — `LIFF_ID` (หน้าเว็บ) กับ `LIFF_CHANNEL_ID` (backend) ต้องเปิดพร้อมกัน

จาก `app/auth.py`:
- `LIFF_CHANNEL_ID` ว่าง → ผู้ใช้ = `"dev-" + X-Dev-User` (ไม่ส่ง = `dev-user`) ไม่สน Authorization
- `LIFF_CHANNEL_ID` มีค่า → ต้องมี `Authorization: Bearer <ID token>` ไม่งั้น 401 "ต้องเข้าผ่าน LINE" · ตรวจกับ `api.line.me/oauth2/v2.1/verify` → ผู้ใช้ = `sub` (userId ของ LINE)
- Push จริงส่งเฉพาะ owner ที่ **ไม่ขึ้นต้นด้วย `dev-`** (`push.py`)

| หน้าเว็บ `LIFF_ID` | backend `LIFF_CHANNEL_ID` | ผล |
|---|---|---|
| ว่าง | ว่าง | **ตอนนี้** · ทุกคนเป็น `dev-dev` · ไม่มี Push จริง · ใช้พัฒนา/ทดสอบหน้าจอได้ |
| ว่าง | มีค่า | ทุกหน้าขึ้น "เชื่อมต่อระบบไม่ได้ · ต้องเข้าผ่าน LINE" ❌ |
| มีค่า | ว่าง | เปิดใน LINE ได้ แต่ backend ไม่สน token → **ทุกคนเป็น `dev-user` ล็อตเดียวกัน** · ไม่มี Push จริง ⚠️ |
| มีค่า | มีค่า | ✅ ของจริง · แต่ละคนเห็นล็อตตัวเอง · Push ถึงคนนั้น |

**ขั้นตอนสลับเป็นของจริง:** ธรใส่ `LIFF_CHANNEL_ID` + `LIFF_ID` + token → restart → บอกมิ้น → มิ้นใส่ `LIFF_ID` → deploy → ทุกคนเปิดผ่าน `https://liff.line.me/<LIFF_ID>` ใหม่

### ระวังตอนทดสอบด้วย curl ในโหมดพัฒนา
หน้าเว็บส่ง `X-Dev-User: dev` → owner = **`dev-dev`**
ตัวอย่าง curl ใน `04_ธร_Backend.md` ใช้ `X-Dev-User: user` → owner = `dev-user` = **คนละคนกับหน้าเว็บ**
ถ้าอยากรีเซ็ตแล้วเห็นผลในหน้าเว็บ (ช่วงยังไม่เปิด LINE) ให้ใช้ `-H "X-Dev-User: dev"`

หลังเปิด LINE แล้ว ผู้ใช้จริงต้องรีเซ็ตจากแถบเดโมในแอป (`?demo=1`) เพราะ curl ไม่มี ID token ของคนนั้น

---

## 4. คำสั่งเช็กจากภายนอก (รันจากโน้ตบุ๊กที่ใช้เน็ตมือถือ ไม่ใช่วง LAN เดียวกับ Pi)

```bash
API=https://<เครื่อง>.<tailnet>.ts.net
K="X-Demo-Key: <DEMO_KEY>"; D="X-Dev-User: dev"; J="Content-Type: application/json"

curl $API/health                                   # {"ok":true,...}
curl $API/lots/latest -H "$D"                      # Lot ของ dev-dev (ผู้ใช้เดียวกับหน้าเว็บ)

# CORS preflight แบบที่เบราว์เซอร์ส่งจริง → ต้องได้ 200 และมี access-control-allow-origin
curl -i -X OPTIONS $API/lots/latest \
  -H "Origin: https://tgr49-liff.vercel.app" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization,content-type,x-dev-user"

curl -X POST $API/demo/reset -H "$K" -H "$D"       # รีเซ็ตล็อตของ dev-dev
curl -X POST $API/demo/speed -H "$K" -H "$J" -d '{"moisture_tick_seconds":2,"market_round_seconds":2}'
curl $API/debug/pushes -H "$K"                     # Push ที่ส่ง/จำลอง + Flex JSON
```

แล้วเปิด https://tgr49-liff.vercel.app (หลังมิ้นใส่ `API_BASE`) ต้องเห็นล็อตเดียวกับ `curl $API/lots/latest -H "X-Dev-User: dev"`

---

## 5. สิ่งที่หน้าเว็บคาดหวังจาก backend (ถ้าเปลี่ยนต้องบอกมิ้น)

1. ทุก endpoint ของแอปตอบ **Lot ทั้งก้อน** (รวม `events`) — POST `/sell` `/inspect` `/lots` `/demo/reset` ก็เช่นกัน แอปเอาไปวาดหน้าใหม่ทันที
2. Error ตอบ `{"detail": "<ภาษาไทย>"}` — แอปเอา `detail` ไปแสดงผู้ใช้ตรง ๆ
3. `updated_at` ต้องขยับทุกครั้งที่มีค่าความชื้นใหม่ — แอปตัดสิน "ข้อมูลไม่อัปเดต" จาก `updated_at` เก่ากว่า 30 นาที (DRYING/READY/ALERT) **ฝั่งมือถือเอง** ถ้านาฬิกามือถือเพี้ยนมากจะผิด
4. เวลาเป็น ISO มี timezone (`+07:00`) — แอปแสดงเวลาแบบ Asia/Bangkok เสมอ
5. `events[].kind` ที่แอปแสดงในหน้า 07: `start` `offer` `sold` · `result`: `pending` (รอตอบ) `sold` (ขายได้) `rejected` (ไม่ได้) · แสดง `text` ตรง ๆ และทำชื่อ `buyer` ไม่ให้ตัดกลางคำ (ชื่อใน `text` ต้องตรงกับ `buyer` ทุกตัวอักษร)
6. `alert.kind` ที่แอปรู้จัก: `defect_high` · `moisture_up` (อย่างอื่นจะแสดงแบบ defect_high) · `alert.message` ใช้เป็นหัวข้อหน้า 09 · `alert.threshold` ใช้ในข้อความ "(ไม่เกิน X%)"
7. `buyers.commercial` / `buyers.instant` เป็น false ทั้งคู่ → แอปซ่อนปุ่ม "ขายเลยที่ราคานี้"
8. `inspection.class_counts` ใช้คีย์ `good broken black shell parchment immature husk` (ตาม `sim/inspector.py`)

### ภาระเครื่อง
มือถือที่เปิดแอปอยู่ 1 เครื่อง = `GET /lots/{id}` ทุก 10 วิ (ทุก 5 วิตอนกำลังขาย) · ไม่ดึงตอนแอปอยู่เบื้องหลัง
เมื่อเปิด LINE แล้ว request แรกของแต่ละ token ต้องไปตรวจที่ `api.line.me` (มี cache ต่อ token) — ถ้า Pi + tunnel ช้าจนเกิน **8 วินาที** หน้าเว็บจะขึ้น "เชื่อมต่อระบบไม่ได้" → บอกมิ้นเพิ่ม timeout

---

## 6. ข้อเสนอแก้ `app/push.py` (เพื่อให้การ์ด Push ตรงกับหน้าแอป)

1. **ชื่อเกรดในการ์ดพร้อมขาย** ตอนนี้แสดง `GRADE_2` ตรง ๆ (`p.get('grade')`) แต่แอปและดีไซน์ใช้ "เกรด 2"
   ```python
   GRADE_TH = {"PREMIUM": "พรีเมียม", "GRADE_1": "เกรด 1", "GRADE_2": "เกรด 2", "GRADE_3": "เกรด 3",
               "BELOW_STANDARD": "ต่ำกว่ามาตรฐาน", "REJECT": "ไม่ผ่าน"}
   # ใน build() กรณี ready:
   _row("เมล็ดเสีย", f"{insp.get('defect_pct', 0):.1f}% · {GRADE_TH.get(p.get('grade'), p.get('grade', '-'))}")
   ```
2. **ลิงก์สำรองเมื่อไม่มี `LIFF_ID`** ชี้ไป backend — ควรชี้หน้าเว็บแทน (หรือแค่ห้ามลืมตั้ง `LIFF_ID`)
   ```python
   def liff_url(lot_id):
       if settings.liff_id:
           return f"https://liff.line.me/{settings.liff_id}?lot={lot_id}"
       return f"https://tgr49-liff.vercel.app/?lot={lot_id}"
   ```
3. หน้าที่ปุ่มในการ์ดพาไป (ตรวจตอนทดสอบรวม): พร้อมขาย → หน้า 03 · ต้องดูแล → หน้า 09 · ขายได้แล้ว → หน้า 08

กาฟิวจะส่ง Flex ที่ปรับหน้าตาแล้วมาให้ใส่ใน `build()` อีกรอบ (ตาม `03_กาฟิว_LINE_และเดโม.md` B2)

---

## 7. ลำดับงานแนะนำ (ต่อจากข้อ H ใน `04_ธร_Backend.md`)
1. Pi + Tailscale Funnel → ส่ง `API_BASE` ให้มิ้น · ตั้ง `PUBLIC_BASE_URL` เป็น URL เดียวกัน
2. ตั้ง `DEMO_KEY` `INGEST_KEY` ใหม่ → ส่ง DEMO_KEY ให้มิ้นทางแชตส่วนตัว
3. รันคำสั่งในข้อ 4 ให้ผ่านทุกข้อ → บอกมิ้น → มิ้นเปิดหน้าเว็บโหมดพัฒนาเช็ก
4. ได้ค่าจากกาฟิว → ใส่ token, `LIFF_ID`, `LIFF_CHANNEL_ID` → restart → บอกมิ้นใส่ `LIFF_ID` (ข้อ 3)
5. แก้ `push.py` ตามข้อ 6 → ทดสอบรวมตาม `03_integration_test_and_demo.md`
6. systemd · Pi รันต่อเนื่อง 30 นาที อุณหภูมิ < 80°C · freeze (tag v1.0)
