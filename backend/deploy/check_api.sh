#!/usr/bin/env bash
# เช็กจากเครื่องอื่นที่ใช้เน็ตมือถือ (ไม่ใช่วง LAN เดียวกับ Pi)
# ใช้: bash deploy/check_api.sh https://<เครื่อง>.<tailnet>.ts.net <DEMO_KEY>
API=${1:?ใส่ URL}; KEY=${2:?ใส่ DEMO_KEY}
D="X-Dev-User: dev"; J="Content-Type: application/json"; ok=0; bad=0
t(){ if [ "$2" = "$3" ]; then echo "✅ $1"; ok=$((ok+1)); else echo "❌ $1 (ได้ $2 ต้องได้ $3)"; bad=$((bad+1)); fi; }
code(){ curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$@"; }

t "health"                 "$(code $API/health)" 200
t "lots/latest (dev-dev)"  "$(code $API/lots/latest -H "$D")" 200
t "CORS preflight vercel"  "$(curl -s -o /dev/null -D - -X OPTIONS $API/lots/latest \
    -H 'Origin: https://longa-robusta.vercel.app' -H 'Access-Control-Request-Method: GET' \
    -H 'Access-Control-Request-Headers: authorization,content-type,x-dev-user' \
    | grep -ci '^access-control-allow-origin: https://longa-robusta.vercel.app')" 1
t "คีย์เก่า tgr49-demo ใช้ไม่ได้" "$(code -X POST $API/demo/speed -H 'X-Demo-Key: tgr49-demo' -H "$J" -d '{}')" 403
t "debug/pushes ด้วยคีย์ใหม่" "$(code $API/debug/pushes -H "X-Demo-Key: $KEY")" 200
vis=$(curl -s $API/lots/latest -H "$D" | grep -o '"vis_url":"[^"]*' | cut -d'"' -f4)
[ -n "$vis" ] && t "vis_url เป็น https" "${vis:0:8}" "https://"
echo "ผ่าน $ok · ไม่ผ่าน $bad"
