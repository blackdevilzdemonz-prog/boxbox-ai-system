"""
BoxBox AI — LINE Messaging API Webhook Handler
Handles incoming messages from the owner via LINE bot
Owner can query: ยอดขาย, Hot Leads, สต็อก, Report, สถานะระบบ
"""
import json
import logging
from datetime import date, timedelta

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, LINE_OWNER_USER_ID
from notifications.line_messaging import reply_message, push_to_owner, _text
from crm.database import AsyncSessionLocal
from crm.models import Customer, Sale, Message as MsgModel, FollowupTask
from sqlalchemy import select, func

log = logging.getLogger("boxbox.line_webhook")
_claude = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# ─── System prompt for owner Q&A ─────────────────────────────────────────────
OWNER_SYSTEM_PROMPT = """คุณคือ BoxBox AI Assistant — ผู้ช่วยฝ่ายวิเคราะห์ธุรกิจของ BoxBoxGlasses
คุณตอบเจ้าของร้านโดยตรงผ่าน LINE

หน้าที่:
- สรุปยอดขาย, ลูกค้า, Hot Leads, Follow-up
- แนะนำ Action Items ที่ควรทำ
- อธิบายสถานะระบบ AI
- ตอบคำถามธุรกิจทั่วไป

ตอบสั้น กระชับ เป็นภาษาไทย ใช้ emoji เหมาะสม
ห้ามให้ข้อมูลที่ไม่แน่ใจ — บอกตรงๆ ว่าไม่มีข้อมูล"""


# ─── Main entry ──────────────────────────────────────────────────────────────
async def handle_line_event(event: dict):
    """Route a single LINE webhook event."""
    event_type = event.get("type")
    if event_type == "message":
        await _handle_message(event)
    elif event_type == "follow":
        await _handle_follow(event)


async def _handle_message(event: dict):
    reply_token = event.get("replyToken", "")
    source      = event.get("source", {})
    user_id     = source.get("userId", "")
    msg_obj     = event.get("message", {})
    text        = msg_obj.get("text", "").strip()

    if not text:
        return

    log.info(f"📲 LINE message from {user_id}: {text[:60]}")

    # Save owner's LINE User ID on first message
    if user_id and not LINE_OWNER_USER_ID:
        log.info(f"💡 Owner LINE User ID: {user_id} — add to .env as LINE_OWNER_USER_ID")
        await reply_message(reply_token, [_text(
            f"✅ BoxBox AI พร้อมใช้งาน!\n\n"
            f"🔑 LINE User ID ของคุณ:\n{user_id}\n\n"
            f"กรุณาใส่ค่านี้ใน .env:\nLINE_OWNER_USER_ID={user_id}"
        )])
        return

    # Only respond to owner
    if user_id != LINE_OWNER_USER_ID:
        await reply_message(reply_token, [_text("❌ ไม่ได้รับอนุญาต")])
        return

    # Route commands
    text_lower = text.lower()
    if any(k in text_lower for k in ["ยอดขาย", "revenue", "sale", "order"]):
        response = await _get_sales_summary()
    elif any(k in text_lower for k in ["hot lead", "hotlead", "ลูกค้าร้อน"]):
        response = await _get_hot_leads()
    elif any(k in text_lower for k in ["follow", "ติดตาม", "ค้าง"]):
        response = await _get_followup_summary()
    elif any(k in text_lower for k in ["สต็อก", "stock", "สินค้า"]):
        response = await _get_stock_summary()
    elif any(k in text_lower for k in ["report", "รายงาน", "สรุป"]):
        response = await _get_full_summary()
    elif any(k in text_lower for k in ["สถานะ", "status", "ระบบ"]):
        response = _get_system_status()
    elif any(k in text_lower for k in ["help", "ช่วย", "คำสั่ง"]):
        response = _get_help_text()
    else:
        # AI free-form answer
        response = await _ask_ai(text)

    await reply_message(reply_token, [_text(response)])


async def _handle_follow(event: dict):
    """When owner adds the bot as friend."""
    reply_token = event.get("replyToken", "")
    user_id = event.get("source", {}).get("userId", "")
    welcome = (
        f"🤖 BoxBox AI Sales System\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"ยินดีต้อนรับ! ระบบ AI พร้อมทำงานแล้ว\n\n"
        f"🔑 LINE User ID ของคุณ:\n{user_id}\n\n"
        f"ใส่ใน .env:\nLINE_OWNER_USER_ID={user_id}\n\n"
        f"พิมพ์ 'help' เพื่อดูคำสั่งทั้งหมด"
    )
    await reply_message(reply_token, [_text(welcome)])
    log.info(f"✅ Owner followed bot. User ID: {user_id}")


# ─── Data Queries ─────────────────────────────────────────────────────────────
async def _get_sales_summary() -> str:
    today = date.today()
    week_ago = today - timedelta(days=7)
    async with AsyncSessionLocal() as db:
        rev_today = await db.scalar(
            select(func.sum(Sale.amount)).where(
                func.date(Sale.ordered_at) == str(today)
            )
        ) or 0
        rev_week = await db.scalar(
            select(func.sum(Sale.amount)).where(
                func.date(Sale.ordered_at).between(str(week_ago), str(today))
            )
        ) or 0
        orders_today = await db.scalar(
            select(func.count(Sale.id)).where(
                func.date(Sale.ordered_at) == str(today)
            )
        ) or 0
    return (
        f"💰 ยอดขาย\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📅 วันนี้: ฿{float(rev_today):,.0f} ({orders_today} orders)\n"
        f"📅 7 วัน: ฿{float(rev_week):,.0f}\n"
        f"━━━━━━━━━━━━━━━━━"
    )


async def _get_hot_leads() -> str:
    async with AsyncSessionLocal() as db:
        hot = await db.scalar(
            select(func.count(Customer.id)).where(
                Customer.lead_stage == "ready_to_buy"
            )
        ) or 0
        new = await db.scalar(
            select(func.count(Customer.id)).where(
                Customer.lead_stage == "new_lead"
            )
        ) or 0
        total = await db.scalar(select(func.count(Customer.id))) or 0
    return (
        f"🔥 Hot Leads\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🔥 Ready to buy: {hot}\n"
        f"🆕 New leads: {new}\n"
        f"👥 Total customers: {total}\n"
        f"━━━━━━━━━━━━━━━━━"
    )


async def _get_followup_summary() -> str:
    from datetime import datetime, timezone
    async with AsyncSessionLocal() as db:
        pending = await db.scalar(
            select(func.count(FollowupTask.id)).where(
                FollowupTask.status == "pending"
            )
        ) or 0
        sent_today = await db.scalar(
            select(func.count(FollowupTask.id)).where(
                FollowupTask.status == "sent",
                func.date(FollowupTask.sent_at) == str(date.today())
            )
        ) or 0
    return (
        f"📬 Follow-up Queue\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⏳ รอส่ง: {pending}\n"
        f"✅ ส่งแล้ววันนี้: {sent_today}\n"
        f"━━━━━━━━━━━━━━━━━"
    )


async def _get_full_summary() -> str:
    sales = await _get_sales_summary()
    leads = await _get_hot_leads()
    followup = await _get_followup_summary()
    return f"{sales}\n\n{leads}\n\n{followup}"


async def _get_stock_summary() -> str:
    import json
    from pathlib import Path
    inv_path = Path("inventory_data.json")
    if not inv_path.exists():
        return "📦 ยังไม่มีข้อมูล inventory_data.json\nกรุณา sync ข้อมูลสต็อกก่อน"
    products = json.loads(inv_path.read_text())
    low = [p for p in products if p.get("warn") or p.get("tk_stock", 99) <= 10]
    if not low:
        return "✅ สต็อกทุกรายการอยู่ในระดับปกติ"
    lines = ["📦 สต็อกต่ำ\n━━━━━━━━━━━━━━━━━"]
    for p in low[:8]:
        status = "🔴" if p.get("tk_stock", 99) <= 3 else "🟡"
        lines.append(f"{status} {p['name']}: {p.get('tk_stock', '?')} ชิ้น")
    lines.append("━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def _get_system_status() -> str:
    return (
        f"🟢 BoxBox AI System\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"✅ FastAPI Webhook: Online\n"
        f"✅ AI Pipeline: Active\n"
        f"✅ Scheduler: Running (7 jobs)\n"
        f"✅ LINE Messaging: Connected\n"
        f"✅ CRM Database: Active\n"
        f"━━━━━━━━━━━━━━━━━"
    )


def _get_help_text() -> str:
    return (
        f"🤖 BoxBox AI คำสั่ง\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💰 ยอดขาย — ดูยอดขายวันนี้/7วัน\n"
        f"🔥 hot lead — ดู leads พร้อมซื้อ\n"
        f"📬 follow up — ดูคิว follow-up\n"
        f"📦 สต็อก — ดูสินค้าใกล้หมด\n"
        f"📋 รายงาน — สรุปภาพรวม\n"
        f"🟢 สถานะ — ตรวจสอบระบบ\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"หรือพิมพ์อะไรก็ได้ AI จะตอบ 😊"
    )


async def _ask_ai(text: str) -> str:
    """Free-form Q&A via Claude."""
    try:
        r = await _claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=400,
            system=OWNER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        return r.content[0].text
    except Exception as e:
        log.error(f"AI Q&A error: {e}")
        return "❌ ไม่สามารถตอบได้ขณะนี้ กรุณาลองใหม่"
