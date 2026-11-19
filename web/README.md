# web — หน้าแอป LIFF "ตรวจล็อต · ขายแทน" (TGR-49)

HTML/CSS/JS ล้วน ไม่มีขั้นตอน build · ออนไลน์ที่ https://longa-robusta.vercel.app

## รันบนเครื่อง
```
cd web
python -m http.server 5173
```
เปิด `http://localhost:5173/?mock=ready` (แก้ไฟล์แล้วไม่เปลี่ยน กด Ctrl+Shift+R)

## พารามิเตอร์ใน URL
| พารามิเตอร์ | ใช้ทำอะไร |
|---|---|
| `?mock=<ชื่อ>` | ใช้ `mock/<ชื่อ>.json` ข้าม LIFF และ API: `drying` `drying-priced` `ready` `ready-counts` `selling` `selling-offers` `sold` `alert` `alert-moisture` `stale` |
| `?mock=login` | **โหมดเกษตรกร:** หน้าล็อกอินจำลอง (บัญชีใน `mock/farmer.json` กรอกไว้ให้แล้ว) → รายการ 3 ล็อต: 1 ล็อตจริงจาก backend (`GET /lots/latest` ต้องใช้ตัวตน LINE) + 2 ล็อตตัวอย่างพร้อมขาย → กดเข้าหน้าล็อต |
| `?lot=LOT-…` | เปิดล็อตนั้นตรง ๆ (ปุ่มใน Push) |
| `?demo=1` | แถบปุ่มเดโมล่างจอ (รีเซ็ต / เร่งเวลา / ปกติ) และ "ขอตรวจใหม่" ส่ง `?improved=true` |
| `?demokey=…` | ใส่ X-Demo-Key ครั้งเดียว เครื่องจะจำไว้ (อย่าแชร์ลิงก์นี้) |

## ค่าตั้ง — `config.js`
- `API_BASE`: URL tunnel HTTPS จากธร ไม่มี `/` ท้าย
- `LIFF_ID`: จากกาฟิว

ยังไม่ใส่ `LIFF_ID` แอปจะส่ง `X-Dev-User: dev` แทน (ใช้ได้ตอน backend ยังไม่ตั้ง `LIFF_CHANNEL_ID`)
backend ต้องอนุญาต CORS จาก `https://longa-robusta.vercel.app` (ค่าเริ่มต้น `CORS_ORIGINS=*` ใช้ได้อยู่แล้ว)

## Deploy
โปรเจกต์ Vercel `tgr49-liff` ต่อกับ GitHub แล้ว (Root Directory = `web`)
- **push เข้า `main`** → deploy Production ที่ https://longa-robusta.vercel.app อัตโนมัติ
- push branch อื่น → ได้ลิงก์ Preview (ต้องล็อกอิน Vercel ถึงเปิดได้)
- ไม่ต้องใช้ `npx vercel deploy` (และอย่ารันในโฟลเดอร์นี้ CLI จะไปหา `web/web`)
- พังหลัง deploy: Vercel → Deployments → รุ่นก่อนหน้า → Instant Rollback

ไม่มี build: Vercel เสิร์ฟไฟล์ตามที่อยู่ในโฟลเดอร์ (`.vercelignore` กันไฟล์ `.env*` ไม่ให้ขึ้นเว็บ)

## ส่งต่อ
- กาฟิว: ใส่ `https://longa-robusta.vercel.app` เป็น Endpoint URL ของ LIFF (ขนาด Full)
- ปุ่มใน Push เปิด `https://liff.line.me/<LIFF_ID>?lot=<lot_id>`
