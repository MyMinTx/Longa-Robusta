"""TRACK 2 (ของจริง) — กาฟิวเติม

ตั้ง INSPECTOR=camera ใน .env เมื่อพร้อม
ต้องคืนค่าหน้าตาเดียวกับ SimInspector.inspect():
  {"class_counts": {"good":..,"broken":..,"black":..,"shell":..,"parchment":..,"immature":..,"husk":..},
   "vis_path": "static/vis/<ไฟล์>.jpg",   # ภาพ vis ย่อด้านยาว ~1080px
   "ms": <เวลาประมวลผล>}
"""


class CameraInspector:
    def __init__(self):
        # TODO(กาฟิว): โหลดโมเดล seg + cls (NCNN) ครั้งเดียวตรงนี้ และเปิด picamera2
        pass

    def inspect(self, lot_id, improved=False):
        # TODO(กาฟิว): ถ่ายภาพ → infer → นับคลาส → เซฟ vis → คืน dict ตามด้านบน
        raise NotImplementedError("ยังไม่ได้ต่อกล้องจริง ใช้ INSPECTOR=sim ไปก่อน")
