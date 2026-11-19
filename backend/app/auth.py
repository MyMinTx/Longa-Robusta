"""ระบุตัวผู้ใช้จาก ID token ของ LIFF

LIFF_CHANNEL_ID ว่าง = โหมดพัฒนา: ใช้ header X-Dev-User (ไม่ใส่ = "dev-user") ไม่ต้องมี LINE
"""
import time

import httpx
from fastapi import Header, HTTPException

from .config import settings

VERIFY_URL = "https://api.line.me/oauth2/v2.1/verify"
_cache = {}  # token -> (user_id, exp)


async def current_user(authorization: str = Header(default=""), x_dev_user: str = Header(default="")):
    if not settings.liff_channel_id:
        return "dev-" + (x_dev_user or "user")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "ต้องเข้าผ่าน LINE")
    hit = _cache.get(token)
    if hit and hit[1] > time.time():
        return hit[0]
    async with httpx.AsyncClient(timeout=8) as c:
        r = await c.post(VERIFY_URL, data={"id_token": token, "client_id": settings.liff_channel_id})
    if r.status_code != 200:
        raise HTTPException(401, "ยืนยันตัวตนไม่ผ่าน")
    body = r.json()
    _cache[token] = (body["sub"], body.get("exp", time.time() + 300))
    return body["sub"]
