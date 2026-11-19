"""TRACK 2 (จำลอง): สุ่มเกรดล็อต → จำนวนเมล็ดต่อคลาส + ภาพปลอมที่ต่างกันตามเกรด

คืนค่าหน้าตาเดียวกับ inspect() ของโมเดลจริง:
  {"class_counts": {7 คลาส}, "vis_path": "static/vis/...jpg", "ms": int, "grade_hint": str}
"""
import random
import time
from PIL import Image, ImageDraw

from ..config import settings
from ..pricing import CLASSES, DEFECT_CLASSES

# ช่วง % เมล็ดเสีย, น้ำหนักการสุ่ม, น้ำหนักแต่ละคลาสเสีย
PROFILES = {
    "premium": ((0.0, 1.0), 0.20, {"broken": 3, "shell": 1}),
    "good":    ((1.5, 4.5), 0.40, {"broken": 3, "black": 1, "shell": 1, "parchment": 1}),
    "fair":    ((5.0, 7.0), 0.20, {"broken": 3, "black": 2, "shell": 1, "immature": 1, "parchment": 1}),
    "poor":    ((8.5, 14.0), 0.20, {"black": 3, "broken": 3, "husk": 2, "immature": 2, "shell": 1, "parchment": 1}),
}
CLASS_COLORS = {  # สีเดียวกับหน้า "ผลตรวจจากกล้อง" ในดีไซน์
    "good": (60, 154, 95), "broken": (240, 138, 36), "black": (34, 34, 34), "shell": (156, 106, 222),
    "parchment": (232, 210, 122), "immature": (127, 183, 232), "husk": (140, 74, 47),
}
PAPER = [(237, 230, 220), (232, 236, 240), (238, 233, 244), (235, 240, 230)]


def pick_profile(improved=False):
    if improved:
        return random.choice(["premium", "good"])
    names = list(PROFILES)
    return random.choices(names, weights=[PROFILES[n][1] for n in names])[0]


def make_counts(profile):
    (lo, hi), _, mix = PROFILES[profile]
    total = random.randint(60, 90)
    n_bad = round(total * random.uniform(lo, hi) / 100)
    counts = {c: 0 for c in CLASSES}
    classes, weights = zip(*mix.items())
    for c in random.choices(classes, weights=weights, k=n_bad):
        counts[c] += 1
    counts["good"] = total - n_bad
    return counts


def draw(counts, path, seed=None):
    rnd = random.Random(seed)
    W = 1080
    img = Image.new("RGB", (W, W), rnd.choice(PAPER))
    beans = [c for c in CLASSES for _ in range(counts[c])]
    rnd.shuffle(beans)
    cols = 10
    cell = W // cols
    slots = [(i % cols, i // cols) for i in range(cols * cols)]
    rnd.shuffle(slots)
    for cls, (cx, cy) in zip(beans, slots):
        bw, bh = rnd.randint(70, 86), rnd.randint(48, 58)
        bean = Image.new("RGBA", (bw + 8, bh + 8), (0, 0, 0, 0))
        d = ImageDraw.Draw(bean)
        d.ellipse((4, 4, bw + 4, bh + 4), fill=CLASS_COLORS[cls] + (255,), outline=(255, 255, 255, 255), width=4)
        d.arc((bw * 0.25, 10, bw * 0.75, bh), 200, 340, fill=(255, 255, 255, 110), width=3)  # ร่องกลางเมล็ด
        bean = bean.rotate(rnd.uniform(0, 180), expand=True, resample=Image.BICUBIC)
        x = cx * cell + rnd.randint(0, max(1, cell - bean.width // 2))
        y = cy * cell + rnd.randint(0, max(1, cell - bean.height // 2))
        img.paste(bean, (min(x, W - bean.width), min(y, W - bean.height)), bean)
    ImageDraw.Draw(img).rectangle((W - 230, W - 50, W - 10, W - 10), fill=(35, 24, 15))
    ImageDraw.Draw(img).text((W - 215, W - 40), "SIMULATED IMAGE", fill=(255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=85)


class SimInspector:
    def inspect(self, lot_id, improved=False):
        t0 = time.perf_counter()
        profile = pick_profile(improved)
        counts = make_counts(profile)
        name = f"{lot_id}-{int(time.time() * 1000)}.jpg"
        draw(counts, settings.static_dir / "vis" / name)
        return {"class_counts": counts, "vis_path": f"static/vis/{name}",
                "ms": int((time.perf_counter() - t0) * 1000), "grade_hint": profile}
