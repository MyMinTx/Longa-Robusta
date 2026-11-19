# 04 · ข้อความพร้อมวางให้ Claude (บัญชีของแต่ละคน)

วิธีใช้:
1. เปิดแชตใหม่ใน Claude (หรือ Claude Code ในเครื่องตัวเอง)
2. แนบไฟล์ตามรายการ "แนบ" ของตัวเอง
   - ชุดเดิม = โฟลเดอร์ `TGR49-handoff/` (`00_อ่านก่อน.md` … `06`, `05_API_contract.md`, `code/`, `design/`, `mock/`)
   - ชุดใหม่ = โฟลเดอร์ `handoff/` นี้ และโค้ดหน้าเว็บ `web/` จาก GitHub `MyMinTx/Longa-Robusta` branch `web-liff`
3. ก๊อปข้อความในกรอบของตัวเองไปวาง → ส่ง

**ห้ามวาง** channel access token, DEMO_KEY, INGEST_KEY หรือรหัสผ่านใด ๆ ลงในแชต Claude หรือไฟล์ที่แชร์ — ถ้า Claude ต้องใช้ ให้เขียนว่า `<TOKEN>` แล้วใส่เองตอนรัน

ถ้าทำงานเองไม่ใช้ Claude: อ่านไฟล์ในคอลัมน์ "แนบ" แล้วทำตามหัวข้อ "ลำดับงาน" ในไฟล์ของตัวเอง (`01` ข้อ 7 สำหรับธร · `02` ทั้งไฟล์สำหรับกาฟิว · `03` สำหรับทุกคน)

---

## ธร (Backend)

**แนบ:**
- ชุดเดิม: `00_อ่านก่อน.md` · `01_ภาพรวมโปรเจกต์.md` · `04_ธร_Backend.md` · `05_API_contract.md` · ทั้งโฟลเดอร์ `code/tgr49-backend/` (หรือ zip)
- ชุดใหม่: `handoff/00_README_web_status.md` · `handoff/01_for_backend.md` · `handoff/03_integration_test_and_demo.md`

```
ฉันชื่อธร อยู่ทีม TGR-49 (TESA Top Gun Rally 2026) รับผิดชอบ Backend (FastAPI + SQLite บน Raspberry Pi) ของ LINE Mini App "ตรวจล็อต · ขายแทน"
โค้ดที่แนบรันได้ครบวงจรแล้ว (เทสต์ 9/9) มีตัวจำลองครบ 3 Track และช่องรับค่า /ingest/*
หน้าเว็บ (Frontend) ของมิ้นเสร็จแล้วและ deploy ที่ https://tgr49-liff.vercel.app รอแค่ URL API จากฉัน

อ่านไฟล์ให้ครบก่อน โดยเฉพาะ:
- handoff/01_for_backend.md  (สิ่งที่หน้าเว็บต้องการจาก backend: .env, CORS, PUBLIC_BASE_URL, การสลับ LIFF_CHANNEL_ID, ข้อเสนอแก้ push.py)
- 04_ธร_Backend.md  (วิธีรันบน Pi, Tailscale Funnel, systemd)
- 05_API_contract.md  (ห้ามเปลี่ยนรูปแบบ JSON โดยไม่บอกมิ้นและกาฟิว)

ช่วยฉันทำตาม "ลำดับงานแนะนำ" ใน handoff/01_for_backend.md ข้อ 7 ทีละขั้น:
1. รันบน Pi + Tailscale Funnel ให้ได้ URL https แล้วตั้ง PUBLIC_BASE_URL
2. ตั้ง DEMO_KEY / INGEST_KEY ใหม่ (ฉันจะใส่ค่าเอง ไม่ต้องให้ฉันส่งค่าจริงมา)
3. รันคำสั่งเช็กในข้อ 4 (health, latest, CORS preflight, demo) ถ้าไม่ผ่านฉันจะส่งผลลัพธ์มา
4. ใส่ค่า LINE (token, LIFF_ID, LIFF_CHANNEL_ID) แล้วประสานกับมิ้นให้เปิดพร้อมกัน
5. แก้ app/push.py ตามข้อ 6 (ชื่อเกรดภาษาไทย, liff_url) โดยไม่ทำเทสต์เดิมพัง
6. systemd และทดสอบรวมตาม handoff/03_integration_test_and_demo.md รอบ A และ B
ถ้าเจอ error ฉันจะส่ง log มา ให้บอกสาเหตุและคำสั่งที่ต้องรัน
ตอบเป็นภาษาไทย
```

---

## กาฟิว (LINE + Push + เดโม)

**แนบ:**
- ชุดเดิม: `00_อ่านก่อน.md` · `01_ภาพรวมโปรเจกต์.md` · `03_กาฟิว_LINE_และเดโม.md` · `05_API_contract.md` · `design/screens/01_แชตLINE_Push.png` · `code/tgr49-backend/app/push.py` · `slides/TGR49_LINE_MiniApp_UXUI.pdf`
- ภาพหน้าจอแอปจริง (ถ้าอยากให้ Claude เห็น): `design/screens/02…10_*.png` หรือแคปจาก https://tgr49-liff.vercel.app/?mock=ready
- ชุดใหม่: `handoff/00_README_web_status.md` · `handoff/02_for_line.md` · `handoff/03_integration_test_and_demo.md`

```
ฉันชื่อกาฟิว อยู่ทีม TGR-49 (TESA Top Gun Rally 2026) รับผิดชอบการตั้งค่า LINE (Official Account, Messaging API, LIFF/MINI App), การ์ด Push แบบ Flex Message และการเตรียมเดโม/นำเสนอ ของ LINE Mini App "ตรวจล็อต · ขายแทน"
หน้าเว็บของมิ้นเสร็จแล้วที่ https://tgr49-liff.vercel.app (ดูหน้าจอได้ที่ ?mock=ready, ?mock=sold ฯลฯ) ต้องใช้เป็น Endpoint URL ของ LIFF

อ่านไฟล์ให้ครบก่อน โดยเฉพาะ:
- handoff/02_for_line.md  (ค่าที่ต้องใส่ใน LIFF จริง, ส่งค่าให้ใคร, Push ↔ หน้าแอป, สคริปต์เดโมฉบับกดปุ่มจริง)
- 03_กาฟิว_LINE_และเดโม.md  (ขั้นตอนตั้งค่าเต็ม)
- handoff/03_integration_test_and_demo.md  (ทดสอบรวมรอบ B, ตารางแก้ปัญหา)

สิ่งที่อยากให้ช่วย:
1. พาฉันตั้งค่า LINE ทีละขั้น (Provider เดียวกัน, OA + Messaging API, LIFF ตาม handoff/02 ข้อ 1) ถ้าฉันส่งภาพหน้าจอคอนโซลมา ช่วยบอกว่าต้องกดตรงไหน
2. บอกว่าต้องส่งค่าอะไรให้ธร/มิ้น ทางไหน (token ส่งแชตส่วนตัวเท่านั้น ฉันจะไม่วาง token ในแชตนี้)
3. ปรับ Flex Message 3 แบบ (พร้อมขาย / ต้องดูแล / ขายได้แล้ว) จาก build() ใน push.py ให้ใกล้ดีไซน์ 01_แชตLINE_Push.png และใช้คำ/ตัวเลข/สีเดียวกับหน้าแอป (handoff/02 ข้อ 3 เช่น "เกรด 2" ไม่ใช่ GRADE_2) ให้ทั้ง JSON สำหรับ Flex Message Simulator และโค้ด Python ที่แก้แล้วส่งให้ธร
4. ซ้อมสคริปต์เดโม 3 นาทีใน handoff/02 ข้อ 4 และเตรียมคำตอบคำถามกรรมการ
ตอบเป็นภาษาไทย
```

---

## มิ้น (Frontend) — ใช้ต่อในแชตใหม่

**แนบ:**
- ชุดเดิม: `00_อ่านก่อน.md` · `01_ภาพรวมโปรเจกต์.md` · `02_มิ้น_Frontend.md` · `05_API_contract.md` · `design/screens/`
- โค้ด: ทั้งโฟลเดอร์ `web/` (index.html, style.css, app.js, config.js, mock/)
- ชุดใหม่: ทั้งโฟลเดอร์ `handoff/`

```
ฉันชื่อมิ้น ทีม TGR-49 รับผิดชอบหน้าแอป (Frontend · LIFF) ของ LINE Mini App "ตรวจล็อต · ขายแทน"
หน้าเว็บทำเสร็จครบ 10 หน้าจอแล้ว (HTML/CSS/JS ล้วน โฟลเดอร์ web/) deploy บน Vercel ที่ https://tgr49-liff.vercel.app (โปรเจกต์ tgr49-liff, deploy ด้วย `npx vercel deploy --prod` ในโฟลเดอร์ web)
สถานะ การตัดสินใจ และสิ่งที่ต่างจากดีไซน์ อยู่ใน handoff/00_README_web_status.md อ่านก่อนแก้อะไร
ห้ามเปลี่ยนฟิลด์ใน 05_API_contract.md เอง

งานที่เหลือ:
1. ใส่ API_BASE (จากธร) และ LIFF_ID (จากกาฟิว) ใน web/config.js แล้ว deploy — LIFF_ID ต้องเปิดพร้อมกับที่ธรใส่ LIFF_CHANNEL_ID (handoff/01_for_backend.md ข้อ 3)
2. ทดสอบรวมตาม handoff/03_integration_test_and_demo.md และแก้บั๊กที่เจอ
3. เช็กลิสต์ข้อ 7 ที่ยังเป็น ⏳ ให้ครบ (มือถือจริง iPhone + Android)
4. merge branch web-liff เข้า main และ tag v1.0
ตอบเป็นภาษาไทย
```
