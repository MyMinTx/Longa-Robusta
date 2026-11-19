"""อ่านค่าความชื้นจาก ESP32 (เฟิร์มแวร์แข่ง Track 1) — ใช้ทดสอบข้อ 0.06 และเป็นฐานของข้อ 4.10
pip install pyserial
python3 serial_reader.py /dev/ttyUSB0
"""
import re, sys, time
import serial

PATTERN = re.compile(r'Moisture Level\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*%')


def read_forever(port: str, on_value=print):
    while True:
        try:
            with serial.Serial(port, 9600, timeout=1) as s:
                print(f"เชื่อม {port} แล้ว รอกดปุ่มบน ESP32 ...", file=sys.stderr)
                while True:
                    line = s.readline().decode("utf-8", errors="ignore").strip()
                    m = PATTERN.search(line)
                    if m:
                        on_value(float(m.group(1)))
        except serial.SerialException as e:
            print(f"พอร์ตหลุด ({e}) ลองใหม่ใน 2 วิ", file=sys.stderr)
            time.sleep(2)


if __name__ == "__main__":
    read_forever(sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0",
                 lambda v: print(f"{time.strftime('%H:%M:%S')}  ความชื้น {v:.2f}%"))
