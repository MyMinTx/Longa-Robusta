import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _f(name, default):
    return float(os.getenv(name, default))


class Settings:
    def __init__(self):
        self.moisture_source = os.getenv("MOISTURE_SOURCE", "sim")
        self.inspector = os.getenv("INSPECTOR", "sim")
        self.market = os.getenv("MARKET", "sim")
        self.moisture_tick = _f("MOISTURE_TICK_SECONDS", 30)
        self.market_round = _f("MARKET_ROUND_SECONDS", 10)
        self.line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
        self.liff_channel_id = os.getenv("LIFF_CHANNEL_ID", "")
        self.liff_id = os.getenv("LIFF_ID", "")
        self.public_base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
        self.cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]
        self.demo_key = os.getenv("DEMO_KEY", "tgr49-demo")
        self.ingest_key = os.getenv("INGEST_KEY", "tgr49-ingest")
        self.db_path = os.getenv("DB_PATH", "data/tgr49.db")
        self.serial_port = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
        self.static_dir = Path(os.getenv("STATIC_DIR", "static"))
        # เกณฑ์ธุรกิจ
        self.moisture_target = _f("MOISTURE_TARGET", 12.5)  # ความชื้นที่ถือว่าแห้งพอขาย (%)
        self.ready_streak = 3          # ต้องผ่านเกณฑ์ติดกันกี่ครั้ง
        self.commercial_defect_max = 7.0
        self.stale_minutes = 30
        self.market_max_rounds = 12    # เกินนี้ = ตลาดปิด ขายที่ 80%



settings = Settings()
