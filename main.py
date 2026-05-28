"""
BoxBox AI Sales System — FastAPI Entry Point
Handles: FB Messenger + IG DM + FB/IG Comments + LINE Messaging API
"""
import base64
import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse

from config import META_APP_SECRET, META_VERIFY_TOKEN
from crm.database import init_db
from handlers.meta_webhook import handle_messenger_event, handle_ig_dm_event, handle_comment_event
from handlers.line_webhook import handle_line_event
from handlers.scheduler import start_scheduler, stop_scheduler
from notifications.line_messaging import verify_signature as line_verify_signature

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("boxbox")


# ─── Lifespan: DB init + scheduler ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🚀 BoxBox AI System starting...")
    await init_db()
    start_scheduler()
    yield
    stop_scheduler()
    log.info("BoxBox AI System stopped.")


app = FastAPI(
    title="BoxBox AI Sales System",
    description="Enterprise AI Sales: Inbox → AI → Close → CRM → Analytics → Promo",
    version="1.0.0",
    lifespan=lifespan,
)


# ─── Webhook Verification (GET) ───────────────────────────────────────────────
@app.get("/webhook/meta")
async def verify_webhook(request: Request):
    """Meta webhook verification challenge"""
    params = request.query_params
    mode      = params.get("hub.mode")
    token     = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        log.info("✅ Webhook verified by Meta")
        return PlainTextResponse(challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


# ─── Webhook Event Receiver (POST) ────────────────────────────────────────────
@app.post("/webhook/meta")
async def receive_event(request: Request, background_tasks: BackgroundTasks):
    """Main Meta webhook — receives all FB + IG events"""
    body_bytes = await request.body()

    # ── Signature Verification ────────────────────────────────────────────────
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if sig_header and not _verify_meta_signature(body_bytes, sig_header):
        log.warning(f"❌ Signature mismatch. header={sig_header[:30]}...")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload: dict[str, Any] = json.loads(body_bytes)
    log.info(f"📩 Webhook received: object={payload.get('object')}")

    if payload.get("object") == "page":
        for entry in payload.get("entry", []):
            # ── FB Messenger ──────────────────────────────────────────────────
            for msg_event in entry.get("messaging", []):
                background_tasks.add_task(handle_messenger_event, msg_event)

            # ── FB Page Comments ──────────────────────────────────────────────
            for change in entry.get("changes", []):
                if change.get("field") == "feed":
                    background_tasks.add_task(handle_comment_event, change["value"])

    elif payload.get("object") == "instagram":
        for entry in payload.get("entry", []):
            # ── Instagram DM ──────────────────────────────────────────────────
            for msg_event in entry.get("messaging", []):
                background_tasks.add_task(handle_ig_dm_event, msg_event)

            # ── Instagram Comments ────────────────────────────────────────────
            for change in entry.get("changes", []):
                if change.get("field") == "comments":
                    background_tasks.add_task(handle_comment_event, change["value"], platform="instagram")

    return {"status": "ok"}


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "BoxBox AI Sales System"}


# ─── Privacy Policy (required for Meta App Review / Live Mode) ────────────────
@app.get("/privacy")
async def privacy_policy():
    from fastapi.responses import HTMLResponse
    html = """<!DOCTYPE html>
<html lang="th">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BoxBox Glasses — Privacy Policy</title>
<style>
  body{font-family:'Segoe UI',sans-serif;max-width:700px;margin:40px auto;padding:0 20px;color:#1a1a2e;line-height:1.7}
  h1{color:#1a1a2e;border-bottom:2px solid #ec4899;padding-bottom:10px}
  h2{color:#6d28d9;margin-top:28px}
  .updated{color:#64748b;font-size:.9rem}
  a{color:#6d28d9}
</style>
</head>
<body>
<h1>👓 BoxBox Glasses — Privacy Policy</h1>
<p class="updated">Last updated: May 2026</p>

<h2>1. ข้อมูลที่เราเก็บรวบรวม</h2>
<p>BoxBox Glasses เก็บรวบรวมข้อมูลที่คุณให้ไว้โดยตรงเมื่อติดต่อเราผ่านช่องทางต่างๆ ได้แก่ ชื่อ ที่อยู่จัดส่ง เบอร์โทรศัพท์ และข้อมูลการสั่งซื้อ</p>

<h2>2. วัตถุประสงค์การใช้ข้อมูล</h2>
<p>เราใช้ข้อมูลของคุณเพื่อดำเนินการสั่งซื้อ จัดส่งสินค้า ให้บริการลูกค้า และปรับปรุงประสบการณ์การใช้บริการ</p>

<h2>3. การแบ่งปันข้อมูล</h2>
<p>เราไม่ขาย ให้เช่า หรือแบ่งปันข้อมูลส่วนตัวของคุณกับบุคคลภายนอก ยกเว้นบริษัทขนส่งที่จำเป็นสำหรับการจัดส่งสินค้า</p>

<h2>4. การรักษาความปลอดภัย</h2>
<p>เราใช้มาตรการรักษาความปลอดภัยที่เหมาะสมเพื่อปกป้องข้อมูลส่วนตัวของคุณจากการเข้าถึงโดยไม่ได้รับอนุญาต</p>

<h2>5. สิทธิ์ของคุณ</h2>
<p>คุณมีสิทธิ์ขอดู แก้ไข หรือลบข้อมูลส่วนตัวของคุณได้ทุกเมื่อ โดยติดต่อเราที่ blackdevilz.demonz@gmail.com</p>

<h2>6. Cookies และ Facebook Messenger</h2>
<p>บริการ Chatbot ของเราใช้ Facebook Messenger API เพื่อตอบคำถามของลูกค้า ข้อมูลที่ส่งผ่าน Messenger อยู่ภายใต้นโยบายความเป็นส่วนตัวของ Meta ด้วย</p>

<h2>7. ติดต่อเรา</h2>
<p>📧 Email: <a href="mailto:blackdevilz.demonz@gmail.com">blackdevilz.demonz@gmail.com</a><br>
📘 Facebook: <a href="https://www.facebook.com/BoxBoxGlasses" target="_blank">facebook.com/BoxBoxGlasses</a></p>
</body>
</html>"""
    return HTMLResponse(content=html)


# ─── Analytics Endpoint ───────────────────────────────────────────────────────
@app.get("/analytics/summary")
async def analytics_summary():
    from analytics.engine import get_daily_summary
    return await get_daily_summary()


@app.get("/analytics/funnel")
async def analytics_funnel():
    from analytics.engine import get_funnel_stats
    return await get_funnel_stats()


# ─── LINE Messaging API Webhook ───────────────────────────────────────────────
@app.post("/webhook/line")
async def receive_line_event(request: Request, background_tasks: BackgroundTasks):
    """LINE Messaging API webhook — receives messages from owner"""
    body_bytes = await request.body()

    # ── LINE Signature Verification ───────────────────────────────────────────
    sig_header = request.headers.get("X-Line-Signature", "")
    if sig_header and not line_verify_signature(body_bytes, sig_header):
        raise HTTPException(status_code=401, detail="Invalid LINE signature")

    payload = json.loads(body_bytes)
    log.info(f"📲 LINE webhook received: {len(payload.get('events', []))} events")

    for event in payload.get("events", []):
        background_tasks.add_task(handle_line_event, event)

    return {"status": "ok"}


# ─── Meta Signature Verification ─────────────────────────────────────────────
def _verify_meta_signature(body: bytes, sig_header: str) -> bool:
    """Verify X-Hub-Signature-256 header from Meta webhook.

    Meta computes:  HMAC-SHA256(APP_SECRET, raw_body)  → hex-encoded
    Header format:  sha256=<hex_digest>
    """
    if not META_APP_SECRET:
        log.warning("⚠️  META_APP_SECRET not set — skipping signature check")
        return True  # dev mode: no secret configured

    if not sig_header.startswith("sha256="):
        log.warning(f"⚠️  Unexpected signature format: {sig_header[:20]}")
        return False

    received_hex = sig_header[len("sha256="):]
    expected_hex = hmac.new(
        META_APP_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    log.debug(f"sig check — received={received_hex[:16]}... expected={expected_hex[:16]}...")
    return hmac.compare_digest(received_hex, expected_hex)
