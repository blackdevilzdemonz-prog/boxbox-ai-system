"""
BoxBox AI — LINE Notify Integration
Sends: Executive Reports, Real-time Escalations, Stock Alerts, Sales Wins

Setup:
  1. ไปที่ https://notify-bot.line.me/
  2. Login ด้วย LINE account
  3. สร้าง Token ใหม่ (เลือก chat หรือ group ที่ต้องการรับ)
  4. ใส่ token ใน .env → LINE_NOTIFY_TOKEN=xxxx
"""
import logging
import os
import httpx
from datetime import datetime
from config import BRAND_NAME

log = logging.getLogger("boxbox.line")

LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"


# ─── Core Send ────────────────────────────────────────────────────────────────
async def send_line(message: str, image_url: str = None, token: str = None) -> bool:
    _token = token or os.getenv("LINE_NOTIFY_TOKEN", "")
    if not _token:
        log.warning("LINE_NOTIFY_TOKEN not set — skipping")
        return False

    data = {"message": message}
    if image_url:
        data["imageFullsize"] = image_url
        data["imageThumbnail"] = image_url

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                LINE_NOTIFY_URL,
                headers={"Authorization": f"Bearer {_token}"},
                data=data,
            )
            if resp.status_code == 200:
                log.info("LINE Notify sent OK")
                return True
            log.error(f"LINE Notify {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        log.error(f"LINE Notify failed: {e}")
        return False


# ─── 🚨 Human Escalation Alert (Real-time) ───────────────────────────────────
async def notify_human_escalation(customer: dict, message: str, reason: str):
    platform = customer.get("platform", "unknown")
    name = customer.get("name") or customer.get("platform_id", "ลูกค้า")
    stage = customer.get("lead_stage", "unknown")
    product = customer.get("product_interest", "ไม่ระบุ")
    lifetime = customer.get("lifetime_value", 0)
    platform_icon = {"facebook": "📘", "instagram": "📸"}.get(platform, "💬")

    text = (
        f"\n🚨 BoxBox — ต้องการ Human ด่วน!\n"
        f"{'─' * 30}\n"
        f"{platform_icon} Platform: {platform.upper()}\n"
        f"👤 ลูกค้า: {name}\n"
        f"💬 ข้อความ: {message[:120]}{'...' if len(message) > 120 else ''}\n"
        f"⚠️  เหตุผล: {reason}\n"
        f"📊 Stage: {stage}\n"
        f"🛍️ สนใจ: {product}\n"
        f"💰 LTV: ฿{lifetime:,.0f}\n"
        f"{'─' * 30}\n"
        f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        f"👉 กรุณาตอบลูกค้าโดยตรงค่ะ"
    )
    await send_line(text)


# ─── 🔥 Hot Lead Alert ────────────────────────────────────────────────────────
async def notify_hot_lead(customer: dict, message: str, product: str, confidence: float):
    if confidence < 0.85:
        return

    platform = customer.get("platform", "")
    name = customer.get("name") or "ลูกค้าใหม่"
    platform_icon = {"facebook": "📘", "instagram": "📸"}.get(platform, "💬")

    text = (
        f"\n🔥 HOT LEAD detected!\n"
        f"{'─' * 28}\n"
        f"{platform_icon} {platform.upper()} · {name}\n"
        f"💬 \"{message[:100]}\"\n"
        f"🛍️ สินค้า: {product}\n"
        f"🎯 Confidence: {confidence:.0%}\n"
        f"🤖 AI กำลังปิดการขาย...\n"
        f"⏰ {datetime.now().strftime('%H:%M')} น."
    )
    await send_line(text)


# ─── ✅ Sale Win ──────────────────────────────────────────────────────────────
async def notify_sale_closed(customer: dict, product: str, amount: float, ai_closed: bool = True):
    name = customer.get("name") or "ลูกค้า"
    platform = customer.get("platform", "")
    total_purchases = customer.get("total_purchases", 0) + 1
    lifetime = customer.get("lifetime_value", 0) + amount

    repeat_tag = "🔄 Repeat Customer!" if total_purchases > 1 else "✨ New Customer"
    ai_tag = "🤖 AI-Closed" if ai_closed else "👤 Human-Closed"

    text = (
        f"\n✅ ขายได้! {BRAND_NAME}\n"
        f"{'─' * 28}\n"
        f"👤 {name} ({platform})\n"
        f"🛍️ {product}\n"
        f"💰 ฿{amount:,.0f}\n"
        f"{repeat_tag}  {ai_tag}\n"
        f"📊 LTV รวม: ฿{lifetime:,.0f}\n"
        f"⏰ {datetime.now().strftime('%H:%M')} น."
    )
    await send_line(text)


# ─── 📦 Stock Alert (Daily 09:00) ────────────────────────────────────────────
async def notify_low_stock(products: list):
    if not products:
        return

    critical = [p for p in products if p.get("tk_stock", 99) <= 3]
    low      = [p for p in products if 3 < p.get("tk_stock", 99) <= 10]

    lines = [
        f"\n📦 BoxBox Stock Alert",
        f"{datetime.now().strftime('%d/%m/%Y')}",
        "─" * 28,
    ]
    if critical:
        lines.append("🚨 วิกฤต (≤3 ชิ้น):")
        for p in critical:
            lines.append(f"  • {p['name']}: {p['tk_stock']} ชิ้น | Rev 7d ฿{p.get('rev_7d', 0):,}")
    if low:
        lines.append("⚠️  ต่ำ (≤10 ชิ้น):")
        for p in low[:4]:
            lines.append(f"  • {p['name']}: {p['tk_stock']} ชิ้น")

    lines += ["─" * 28, "👉 สั่งซื้อเพิ่มก่อนสินค้าหมด"]
    await send_line("\n".join(lines))


# ─── 📋 Executive Report (1st & 16th) ────────────────────────────────────────
async def notify_executive_report(period_label: str, kpis: dict, action_items: list, report_path: str):
    revenue   = kpis.get("revenue", 0)
    orders    = kpis.get("orders", 0)
    leads     = kpis.get("new_leads", 0)
    conv      = kpis.get("conversion_rate", 0)
    avg_order = kpis.get("avg_order_value", 0)
    repeat    = kpis.get("repeat_customers", 0)
    ai_resp   = kpis.get("ai_responses", 0)

    critical = [a for a in action_items if a["priority"] == "critical"]
    high     = [a for a in action_items if a["priority"] == "high"]

    action_lines = []
    for a in (critical + high)[:3]:
        icon = "🚨" if a["priority"] == "critical" else "⚡"
        action_lines.append(f"  {icon} [{a['dept']}] {a['action'][:65]}")

    rev_icon = "🟢" if revenue > 60000 else ("🟡" if revenue > 40000 else "🔴")

    text = (
        f"\n📋 BoxBox Executive Report\n"
        f"📅 {period_label}\n"
        f"{'═' * 30}\n"
        f"\n💰 REVENUE & SALES\n"
        f"  {rev_icon} ยอดขาย: ฿{revenue:,.0f}\n"
        f"  🛒 Orders: {orders} รายการ\n"
        f"  💎 Avg Order: ฿{avg_order:,.0f}\n"
        f"  📈 Conv Rate: {conv}%\n"
        f"\n🤖 AI PERFORMANCE\n"
        f"  💬 AI Responses: {ai_resp:,}\n"
        f"  ⭐ Repeat Customers: {repeat}\n"
        f"  👥 New Leads: {leads}\n"
        f"\n⚡ ACTION ITEMS\n"
        + ("\n".join(action_lines) if action_lines else "  ✅ ทุก KPI ปกติดี")
        + f"\n{'═' * 30}\n"
        f"📄 รายงานเต็ม: {report_path}\n"
        f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    await send_line(text)


# ─── 📊 Daily Digest (Optional) ──────────────────────────────────────────────
async def notify_daily_digest(summary: dict):
    revenue  = summary.get("revenue_thb", 0)
    orders   = summary.get("conversions", 0)
    leads    = summary.get("new_leads", 0)
    ai_resp  = summary.get("ai_responses_sent", 0)
    conv     = summary.get("conversion_rate", 0)

    emoji = "🔥" if revenue > 5000 else "📊"
    text = (
        f"\n{emoji} BoxBox Daily Digest\n"
        f"{datetime.now().strftime('%d/%m/%Y')}\n"
        f"{'─' * 25}\n"
        f"💰 Revenue: ฿{revenue:,.0f}\n"
        f"🛒 Orders: {orders}\n"
        f"👤 New Leads: {leads}\n"
        f"🤖 AI Replies: {ai_resp}\n"
        f"📈 Conv Rate: {conv}%"
    )
    await send_line(text)


# ─── 🎯 Promo Result ──────────────────────────────────────────────────────────
async def notify_promo_result(promo_name: str, sent: int, converted: int):
    rate = round(converted / max(sent, 1) * 100, 1)
    text = (
        f"\n🎯 Promo Blast สำเร็จ!\n"
        f"{'─' * 25}\n"
        f"📣 {promo_name}\n"
        f"📤 ส่งไป: {sent} คน\n"
        f"✅ ปิดได้: {converted} คน ({rate}%)\n"
        f"⏰ {datetime.now().strftime('%H:%M')} น."
    )
    await send_line(text)
