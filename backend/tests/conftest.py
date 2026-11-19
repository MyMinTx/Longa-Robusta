import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.update({
    "DB_PATH": os.path.join(_tmp, "test.db"),
    "STATIC_DIR": os.path.join(_tmp, "static"),
    "MOISTURE_TICK_SECONDS": "0.03",
    "MARKET_ROUND_SECONDS": "0.02",
    "LINE_CHANNEL_ACCESS_TOKEN": "",
    "LIFF_CHANNEL_ID": "",
    # ค่าของเทสต์เอง ไม่ใช้ .env จริงบน Pi
    "LIFF_ID": "",
    "DEMO_KEY": "tgr49-demo",
    "INGEST_KEY": "tgr49-ingest",
    "MOISTURE_SOURCE": "sim",
    "INSPECTOR": "sim",
    "MARKET": "sim",
    "MOISTURE_TARGET": "12.5",
    "PUBLIC_BASE_URL": "http://localhost:8000",
})
