# web — หน้าแอป LIFF "ตรวจล็อต · ขายแทน" (TGR-49)

HTML/CSS/JS ล้วน ไม่มีขั้นตอน build · ออนไลน์ที่ https://tgr49-liff.vercel.app

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
| `?lot=LOT-…` | เปิดล็อตนั้นตรง ๆ (ปุ่มใน Push) |
| `?demo=1` | แถบปุ่มเดโมล่างจอ (รีเซ็ต / เร่งเวลา / ปกติ) และ "ขอตรวจใหม่" ส่ง `?improved=true` |
| `?demokey=…` | ใส่ X-Demo-Key ครั้งเดียว เครื่องจะจำไว้ (อย่าแชร์ลิงก์นี้) |

## ค่าตั้ง — `config.js`
- `API_BASE`: URL tunnel HTTPS จากธร ไม่มี `/` ท้าย
- `LIFF_ID`: จากกาฟิว

ยังไม่ใส่ `LIFF_ID` แอปจะส่ง `X-Dev-User: dev` แทน (ใช้ได้ตอน backend ยังไม่ตั้ง `LIFF_CHANNEL_ID`)
backend ต้องอนุญาต CORS จาก `https://tgr49-liff.vercel.app` (ค่าเริ่มต้น `CORS_ORIGINS=*` ใช้ได้อยู่แล้ว)

## Deploy (Vercel CLI)
โปรเจกต์ `tgr49-liff` ลิงก์กับโฟลเดอร์นี้แล้ว (`.vercel/` ไม่ขึ้น git)
```
cd web
npx vercel deploy --prod
```
ไม่มี build: Vercel เสิร์ฟไฟล์ตามที่อยู่ในโฟลเดอร์ (`.vercelignore` กันไฟล์ `.env*` ไม่ให้ขึ้นเว็บ)

## ส่งต่อ
- กาฟิว: ใส่ `https://tgr49-liff.vercel.app` เป็น Endpoint URL ของ LIFF (ขนาด Full)
- ปุ่มใน Push เปิด `https://liff.line.me/<LIFF_ID>?lot=<lot_id>`
