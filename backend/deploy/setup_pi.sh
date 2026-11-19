#!/usr/bin/env bash
# รันบน Pi ในโฟลเดอร์ ~/tgr49-backend : bash deploy/setup_pi.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m pytest -q            # ต้องผ่าน 11/11

if [ ! -f .env ]; then
  cp .env.example .env
  # สุ่มคีย์ใหม่ (ค่าเดิมอยู่ในโค้ดที่แชร์กันแล้ว) — ห้ามวางค่านี้ในแชตกลุ่ม
  sed -i "s|^DEMO_KEY=.*|DEMO_KEY=$(openssl rand -hex 16)|" .env
  sed -i "s|^INGEST_KEY=.*|INGEST_KEY=$(openssl rand -hex 16)|" .env
  sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://longa-robusta.vercel.app,http://localhost:5173|" .env
  echo ".env สร้างแล้ว (DEMO_KEY / INGEST_KEY สุ่มใหม่)"
fi

# systemd
sudo cp deploy/tgr49.service /etc/systemd/system/tgr49.service
sudo sed -i "s|/home/pi|$HOME|g; s|^User=pi|User=$USER|" /etc/systemd/system/tgr49.service
sudo systemctl daemon-reload
sudo systemctl enable --now tgr49
sleep 2 && curl -s localhost:8000/health && echo

# HTTPS ผ่าน Tailscale Funnel
sudo tailscale funnel --bg 8000
URL=$(tailscale funnel status | grep -o 'https://[^ ]*ts\.net' | head -1)
echo "Funnel URL: $URL"
sed -i "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=$URL|" .env
sudo systemctl restart tgr49
echo "เสร็จ · ส่ง $URL ให้มิ้น (API_BASE) · ดู DEMO_KEY ด้วย: grep DEMO_KEY .env"
