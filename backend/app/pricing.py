"""สูตรมูลค่าตามที่ตลาด Track 3 ประกาศ (ใช้ไฟล์นี้ไฟล์เดียวทั้ง Pi, Agent และหน้าเว็บอ้างอิง)

มูลค่า (บาท/กก.) = 120 × G × M × S
ราคาต่ำสุด     = 0.8 × มูลค่า   (ขายไม่ออกตอนปิดตลาด ได้ 80% ของมูลค่าจริง)
"""
BASE_PRICE = 120.0
FLOOR_RATIO = 0.8
DEFECT_CLASSES = ("broken", "black", "shell", "parchment", "immature", "husk")
CLASSES = ("good",) + DEFECT_CLASSES

# (เพดาน % เสีย, ชื่อเกรด, ตัวคูณ)
GRADE_TABLE = [
    (1, "PREMIUM", 1.08),
    (3, "GRADE_1", 1.04),
    (5, "GRADE_2", 1.00),
    (7, "GRADE_3", 0.96),
    (15, "BELOW_STANDARD", 0.85),
    (100, "REJECT", 0.60),
]
SIZE_TABLE = {12: 0.92, 13: 0.97, 14: 1.00, 15: 1.00, 16: 1.03, 17: 1.03, 18: 1.06}


def defect_pct(class_counts: dict) -> float:
    total = sum(class_counts.get(c, 0) for c in CLASSES)
    if total == 0:
        raise ValueError("ไม่มีเมล็ดในผลตรวจ")
    bad = sum(class_counts.get(c, 0) for c in DEFECT_CLASSES)
    return 100.0 * bad / total


def grade(d: float):
    for limit, name, mult in GRADE_TABLE:
        if d <= limit:
            return name, mult
    return GRADE_TABLE[-1][1], GRADE_TABLE[-1][2]


def g_factor(d: float) -> float:
    return (1 - d / 100) * grade(d)[1]


def m_factor(m: float) -> float:
    if m <= 12.5:
        return 1.0
    if m <= 15:
        return (1 - m / 100) / (1 - 12.5 / 100) - 0.02 * (m - 12.5)
    return 0.6


def s_factor(screen_size=None) -> float:
    """ยังไม่มีคนวัดขนาด → ใช้ค่ามาตรฐาน 1.0"""
    if screen_size is None:
        return 1.0
    return SIZE_TABLE[int(screen_size)]


def price(d: float, m: float, screen_size=None) -> dict:
    name, mult = grade(d)
    G, M, S = g_factor(d), m_factor(m), s_factor(screen_size)
    value = BASE_PRICE * G * M * S
    return {
        "base": BASE_PRICE, "grade": name, "grade_mult": mult,
        "G": round(G, 4), "M": round(M, 4), "S": S,
        "size_source": "default" if screen_size is None else "measured",
        "value": round(value, 2), "floor": round(value * FLOOR_RATIO, 2),
        "floor_ratio": FLOOR_RATIO,
    }


def buyers(d: float, m: float) -> dict:
    return {"commercial": d <= 7 and m <= 12.5, "instant": d <= 15 and m <= 14}


def is_offer_allowed(offer_price: float, floor: float) -> bool:
    """ตัวกันของ Agent: ห้ามเสนอต่ำกว่าราคาต่ำสุด"""
    return offer_price >= floor
