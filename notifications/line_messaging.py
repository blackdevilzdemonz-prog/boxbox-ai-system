"""
BoxBox AI — LINE Messaging API Client
Replaces LINE Notify with full two-way Messaging API
- Push messages to owner (reports, alerts, escalations)
- Verify incoming webhook signatures
- Reply to owner queries in real-time
"""
import hashlib
import hmac
import base64
import logging
from typing import Optional

import httpx

from config import (
    LINE_CHANNEL_SECRET,
    LINE_CHANNEL_ACCESS_TOKEN,
    LINE_MESSAGING_API_URL,
    LINE_OWNER_USER_ID,
)

log = logging.getLogger("boxbox.line_messaging")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
}


# ─── Core: Push message to owner ─────────────────────────────────────────────
async def push_to_owner(messages: list[dict]) -> bool:
    """Push one or more message objects to the owner's LINE."""
    if not LINE_OWNER_USER_ID:
        log.warning("LINE_OWNER_USER_ID not set — skipping push")
        return False
    return await _push(LINE_OWNER_USER_ID, messages)


async def _push(user_id: str, messages: list[dict]) -> bool:
    """Raw push to any LINE user ID."""
    if not LINE_CHANNEL_ACCESS_TOKEN:
        log.warning("LINE_CHANNEL_ACCESS_TOKEN not set — skipping")
        return False
    payload = {"to": user_id, "messages": messages[:5]}  # LINE max 5 per push
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{LINE_MESSAGING_API_URL}/push",
                json=payload,
                headers=HEADERS,
            )
        if r.status_code == 200:
            return True
        log.error(f"LINE push failed {r.status_code}: {r.text}")
        return False
    except Exception as e:
        log.error(f"LINE push error: {e}")
        return False


async def reply_message(reply_token: str, messages: list[dict]) -> bool:
    """Reply to an incoming LINE message using reply token."""
    payload = {"replyToken": reply_token, "messages": messages[:5]}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{LINE_MESSAGING_API_URL}/reply",
                json=payload,
                headers=HEADERS,
            )
        return r.status_code == 200
    except Exception as e:
        log.error(f"LINE reply error: {e}")
        return False


# ─── Signature Verification ───────────────────────────────────────────────────
def verify_signature(body: bytes, signature: str) -> bool:
    """Verify X-Line-Signature header from LINE webhook."""
    if not LINE_CHANNEL_SECRET:
        return True  # dev mode — skip
    mac = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature)


# ─── Message Builders ─────────────────────────────────────────────────────────
def _text(msg: str) -> dict:
    return {"type": "text", "text": msg[:2000]}


def _flex_box(alt_text: str, contents: dict) -> dict:
    return {"type": "flex", "altText": alt_text, "contents": contents}


# ─── Notification Functions ───────────────────────────────────────────────────

async def notify_human_escalation(customer: dict, message: str, reason: str):
    """🚨 Real-time alert when AI escalates to human."""
    name = customer.get("name") or customer.get("platform_id", "ไม่ระบุ")
    platform = customer.get("platform", "")
    msg = (
        f"🚨 ESCALATION ALERT\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👤 ลูกค้า: {name}\n"
        f"📱 Platform: {platform}\n"
        f"⚠️ เหตุผล: {reason}\n"
        f"💬 ข้อความ: {message[:200]}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"กรุณาเข้ารับการสนทนาทันที!"
    )
    await push_to_owner([_text(msg)])
    log.info(f"LINE escalation sent for {name}")


async def notify_hot_lead(customer: dict, message: str, product: str, confidence: float):
    """🔥 Real-time alert for hot lead detected."""
    name = customer.get("name") or customer.get("platform_id", "ไม่ระบุ")
    platform = customer.get("platform", "")
    msg = (
        f"🔥 HOT LEAD!\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👤 ลูกค้า: {name}\n"
        f"📱 Platform: {platform}\n"
        f"🛍️ สินค้าที่สนใจ: {product}\n"
        f"📊 Confidence: {confidence:.0%}\n"
        f"💬 ข้อความ: {message[:200]}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"AI กำลังปิดการขาย! 💪"
    )
    await push_to_owner([_text(msg)])
    log.info(f"LINE hot-lead sent: {name} / {product}")


async def notify_sale_closed(customer: dict, product: str, amount: float, ai_closed: bool = True):
    """💰 Real-time alert when a sale is confirmed."""
    name = customer.get("name") or customer.get("platform_id", "ไม่ระบุ")
    closer = "🤖 AI ปิดเอง" if ai_closed else "👤 ทีมงานปิด"
    msg = (
        f"💰 ปิดการขายแล้ว!\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👤 ลูกค้า: {name}\n"
        f"🛍️ สินค้า: {product}\n"
        f"💵 ยอด: ฿{amount:,.0f}\n"
        f"✅ {closer}\n"
        f"━━━━━━━━━━━━━━━━━"
    )
    await push_to_owner([_text(msg)])
    log.info(f"LINE sale-closed sent: {name} / ฿{amount:,.0f}")


async def notify_low_stock(products: list):
    """📦 Daily stock alert for low inventory."""
    lines = ["📦 แจ้งเตือนสต็อกต่ำ\n━━━━━━━━━━━━━━━━━"]
    for p in products[:8]:
        name = p.get("name", "?")
        stock = p.get("tk_stock", "?")
        rev = p.get("rev_7d", 0)
        status = "🔴 วิกฤต" if stock <= 3 else "🟡 ต่ำ"
        lines.append(f"{status} {name}: เหลือ {stock} ชิ้น (Rev 7d: ฿{rev:,.0f})")
    lines.append("━━━━━━━━━━━━━━━━━\nกรุณาสั่งซื้อสินค้าเพิ่ม!")
    await push_to_owner([_text("\n".join(lines))])
    log.info(f"LINE stock-alert sent: {len(products)} products")


async def notify_daily_digest(summary: dict):
    """📊 End-of-day digest at 20:00."""
    revenue    = summary.get("revenue", 0)
    orders     = summary.get("orders", 0)
    new_leads  = summary.get("new_leads", 0)
    ai_resp    = summary.get("ai_responses", 0)
    escalated  = summary.get("escalations", 0)
    hot_leads  = summary.get("hot_leads", 0)
    conv_rate  = summary.get("conversion_rate", 0)
    msg = (
        f"📊 BoxBox Daily Digest\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💰 Revenue: ฿{revenue:,.0f}\n"
        f"🛒 Orders: {orders}\n"
        f"👥 New Leads: {new_leads}\n"
        f"🔥 Hot Leads: {hot_leads}\n"
        f"📈 Conv Rate: {conv_rate}%\n"
        f"🤖 AI Responses: {ai_resp}\n"
        f"🚨 Escalations: {escalated}\n"
        f"━━━━━━━━━━━━━━━━━"
    )
    await push_to_owner([_text(msg)])
    log.info("LINE daily-digest sent")


async def notify_executive_report(period_label: str, kpis: dict, action_items: list, report_path: str):
    """📋 Executive report summary on 1st & 16th."""
    revenue   = kpis.get("revenue", 0)
    orders    = kpis.get("orders", 0)
    conv      = kpis.get("conversion_rate", 0)
    avg_order = kpis.get("avg_order_value", 0)
    repeat    = kpis.get("repeat_customers", 0)

    critical = [i for i in action_items if i["priority"] == "critical"]
    high     = [i for i in action_items if i["priority"] == "high"]

    lines = [
        f"📋 Executive Report\n{period_label}",
        f"━━━━━━━━━━━━━━━━━",
        f"💰 Revenue: ฿{revenue:,.0f}",
        f"🛒 Orders: {orders}",
        f"📈 Conv Rate: {conv}%",
        f"🧾 Avg Order: ฿{avg_order:,.0f}",
        f"🔄 Repeat Customers: {repeat}",
        f"━━━━━━━━━━━━━━━━━",
    ]
    if critical:
        lines.append("🔴 Critical:")
        for i in critical[:2]:
            lines.append(f"  • {i['action'][:80]}")
    if high:
        lines.append("🟠 High Priority:")
        for i in high[:2]:
            lines.append(f"  • {i['action'][:80]}")
    lines.append(f"━━━━━━━━━━━━━━━━━")
    lines.append(f"📄 Report: {report_path}")

    await push_to_owner([_text("\n".join(lines))])
    log.info(f"LINE exec-report sent: {period_label}")


async def notify_promo_result(promo_name: str, sent: int, converted: int):
    """📣 Promotion cycle result notification."""
    rate = round(converted / max(sent, 1) * 100, 1)
    msg = (
        f"📣 Promo Cycle Complete\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🏷️ {promo_name}\n"
        f"📤 ส่งแล้ว: {sent} คน\n"
        f"✅ Convert: {converted} คน ({rate}%)\n"
        f"━━━━━━━━━━━━━━━━━"
    )
    await push_to_owner([_text(msg)])
    log.info(f"LINE promo-result sent: {promo_name}")
