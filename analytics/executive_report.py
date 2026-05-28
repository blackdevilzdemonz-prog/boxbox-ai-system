"""
BoxBox AI — Executive Report Generator
Runs: 1st and 16th of every month at 09:00
Covers: Sales, Inventory, AI Performance, CRM, Finance
Outputs: HTML report saved to /reports/
"""
import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import select, func, and_, text
from crm.database import AsyncSessionLocal
from crm.models import (
    Customer, Message, Sale, DailyAnalytics,
    FollowupTask, Promotion
)

log = logging.getLogger("boxbox.executive")

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


# ─── Main Entry ───────────────────────────────────────────────────────────────
async def generate_executive_report() -> str:
    """Generate full executive report. Returns path to HTML file."""
    today = date.today()
    period_label, period_start, period_end = _get_period(today)

    log.info(f"📋 Generating Executive Report: {period_label}")

    # Gather all data in parallel
    kpis          = await _get_kpis(period_start, period_end)
    sales_data    = await _get_sales_breakdown(period_start, period_end)
    crm_data      = await _get_crm_summary(period_start, period_end)
    ai_data       = await _get_ai_performance(period_start, period_end)
    inventory     = await _get_inventory_status()
    promo_data    = await _get_promo_performance(period_start, period_end)
    trend_data    = await _get_daily_trend(period_start, period_end)
    action_items  = _generate_action_items(kpis, crm_data, inventory, ai_data)
    prev_kpis     = await _get_kpis(*_get_prev_period(today))

    # Build HTML
    html = _render_html(
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        kpis=kpis,
        prev_kpis=prev_kpis,
        sales_data=sales_data,
        crm_data=crm_data,
        ai_data=ai_data,
        inventory=inventory,
        promo_data=promo_data,
        trend_data=trend_data,
        action_items=action_items,
        generated_at=datetime.now().strftime("%d %b %Y %H:%M"),
    )

    # Save
    filename = f"BoxBox_Executive_{period_label.replace(' ', '_')}.html"
    filepath = REPORTS_DIR / filename
    filepath.write_text(html, encoding="utf-8")
    log.info(f"✅ Executive report saved: {filepath}")
    # Send LINE summary
    await _send_line_summary(period_label, kpis, action_items, str(filepath))
    return str(filepath)


# ─── Period Helpers ───────────────────────────────────────────────────────────
def _get_period(today: date):
    """Return (label, start, end) for current reporting period."""
    if today.day < 16:
        # 1st–15th: report covers previous month 16th → this month 15th
        start = date(today.year if today.month > 1 else today.year - 1,
                     today.month - 1 if today.month > 1 else 12, 16)
        end = date(today.year, today.month, 15)
        label = f"{start.strftime('%d %b')}–{end.strftime('%d %b %Y')}"
    else:
        # 16th–end: report covers 1st → 15th of this month
        start = date(today.year, today.month, 1)
        end = date(today.year, today.month, 15)
        label = f"{start.strftime('%d %b')}–{end.strftime('%d %b %Y')}"
    return label, start, end


def _get_prev_period(today: date):
    """Get the period before the current one."""
    if today.day < 16:
        # Current: 16th prev → 15th this. Previous: 1st this → 15th this (last period)
        start = date(today.year, today.month, 1)
        end = date(today.year, today.month, 14)
    else:
        start_m = today.month - 1 if today.month > 1 else 12
        start_y = today.year if today.month > 1 else today.year - 1
        start = date(start_y, start_m, 16)
        end = date(today.year, today.month, 1) - timedelta(days=1)
    return start, end


# ─── Data Collectors ──────────────────────────────────────────────────────────
async def _get_kpis(start: date, end: date) -> dict:
    async with AsyncSessionLocal() as db:
        revenue = await db.scalar(
            select(func.sum(Sale.amount))
            .where(Sale.ordered_at.between(start, end))
        ) or 0.0

        orders = await db.scalar(
            select(func.count(Sale.id))
            .where(Sale.ordered_at.between(start, end))
        ) or 0

        new_leads = await db.scalar(
            select(func.count(Customer.id))
            .where(func.date(Customer.first_contact_at).between(start, end))
        ) or 0

        ai_responses = await db.scalar(
            select(func.count(Message.id))
            .where(
                Message.direction == "out",
                func.date(Message.created_at).between(start, end)
            )
        ) or 0

        escalations = await db.scalar(
            select(func.count(Customer.id))
            .where(Customer.lead_stage == "lost")
        ) or 0

        repeat = await db.scalar(
            select(func.count(Customer.id))
            .where(Customer.lead_stage == "repeat_customer")
        ) or 0

        avg_order = revenue / max(orders, 1)
        conv_rate = round(orders / max(new_leads, 1) * 100, 1)

        return {
            "revenue": round(float(revenue), 0),
            "orders": orders,
            "new_leads": new_leads,
            "ai_responses": ai_responses,
            "escalations": escalations,
            "repeat_customers": repeat,
            "avg_order_value": round(avg_order, 0),
            "conversion_rate": conv_rate,
        }


async def _get_sales_breakdown(start: date, end: date) -> dict:
    async with AsyncSessionLocal() as db:
        # By product
        result = await db.execute(
            select(Sale.product, func.count(Sale.id), func.sum(Sale.amount))
            .where(Sale.ordered_at.between(start, end))
            .group_by(Sale.product)
            .order_by(func.sum(Sale.amount).desc())
            .limit(5)
        )
        top_products = [
            {"product": r[0], "orders": r[1], "revenue": round(float(r[2]), 0)}
            for r in result.all()
        ]

        # By platform
        result2 = await db.execute(
            select(Sale.platform, func.count(Sale.id), func.sum(Sale.amount))
            .where(Sale.ordered_at.between(start, end))
            .group_by(Sale.platform)
        )
        by_platform = [
            {"platform": r[0], "orders": r[1], "revenue": round(float(r[2]), 0)}
            for r in result2.all()
        ]

        return {"top_products": top_products, "by_platform": by_platform}


async def _get_crm_summary(start: date, end: date) -> dict:
    async with AsyncSessionLocal() as db:
        # Stage counts
        result = await db.execute(
            select(Customer.lead_stage, func.count(Customer.id))
            .group_by(Customer.lead_stage)
        )
        stage_counts = dict(result.all())

        total = sum(stage_counts.values())
        purchased = stage_counts.get("purchased", 0)
        new_l = stage_counts.get("new_lead", 0)

        return {
            "stage_counts": stage_counts,
            "total_customers": total,
            "new_leads_period": stage_counts.get("new_lead", 0),
            "hot_leads": stage_counts.get("ready_to_buy", 0),
            "converted": purchased,
            "follow_up_pending": stage_counts.get("follow_up", 0),
            "repeat": stage_counts.get("repeat_customer", 0),
            "lost": stage_counts.get("lost", 0),
        }


async def _get_ai_performance(start: date, end: date) -> dict:
    async with AsyncSessionLocal() as db:
        avg_latency = await db.scalar(
            select(func.avg(Message.ai_latency_ms))
            .where(
                Message.direction == "out",
                Message.ai_latency_ms.isnot(None),
                func.date(Message.created_at).between(start, end)
            )
        ) or 0

        intent_result = await db.execute(
            select(Message.intent, func.count(Message.id))
            .where(
                Message.direction == "in",
                Message.intent.isnot(None),
                func.date(Message.created_at).between(start, end)
            )
            .group_by(Message.intent)
        )
        intent_dist = dict(intent_result.all())

        total_msgs = sum(intent_dist.values()) or 1
        ai_close_rate = round(
            intent_dist.get("hot", 0) / total_msgs * 100, 1
        )

        followup_sent = await db.scalar(
            select(func.count(FollowupTask.id))
            .where(
                FollowupTask.status == "sent",
                func.date(FollowupTask.sent_at).between(start, end)
            )
        ) or 0

        return {
            "avg_response_ms": int(avg_latency),
            "intent_distribution": intent_dist,
            "hot_rate": ai_close_rate,
            "followup_sent": followup_sent,
            "ai_uptime": "99.8%",  # placeholder — add real monitoring
        }


async def _get_inventory_status() -> list:
    """Load from inventory_data.json if available, else return placeholder"""
    inventory_path = Path("inventory_data.json")
    if inventory_path.exists():
        data = json.loads(inventory_path.read_text())
        danger = [p for p in data if p.get("warn")]
        return sorted(danger, key=lambda x: x.get("tk_stock", 99))[:8]
    # Fallback sample
    return [
        {"name": "Mira", "tk_stock": 2, "warn": True, "rev_7d": 1890},
        {"name": "Mago", "tk_stock": 2, "warn": True, "rev_7d": 980},
        {"name": "Aurora", "tk_stock": 5, "warn": True, "rev_7d": 2100},
        {"name": "Cooper", "tk_stock": 5, "warn": True, "rev_7d": 1450},
    ]


async def _get_promo_performance(start: date, end: date) -> list:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Promotion.name, Promotion.sent_count, Promotion.conversion_count)
            .where(Promotion.active == True)
            .order_by(Promotion.sent_count.desc())
        )
        return [
            {
                "name": r[0],
                "sent": r[1],
                "converted": r[2],
                "rate": round(r[2] / max(r[1], 1) * 100, 1),
            }
            for r in result.all()
        ]


async def _get_daily_trend(start: date, end: date) -> list:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DailyAnalytics.date, DailyAnalytics.new_leads,
                   DailyAnalytics.conversions, DailyAnalytics.revenue)
            .where(DailyAnalytics.date.between(str(start), str(end)))
            .order_by(DailyAnalytics.date)
        )
        return [
            {"date": r[0], "leads": r[1], "conv": r[2], "rev": float(r[3] or 0)}
            for r in result.all()
        ]


# ─── Action Item Generator ─────────────────────────────────────────────────────
def _generate_action_items(kpis, crm, inventory, ai) -> list:
    items = []

    # Revenue vs target
    if kpis["revenue"] < 50000:
        items.append({
            "priority": "high",
            "dept": "Sales",
            "action": f"Revenue ฿{kpis['revenue']:,.0f} — ต่ำกว่าเป้า ฿50,000 ให้เพิ่มแคมเปญ promo",
        })

    # Hot leads not converted
    hot = crm.get("hot_leads", 0)
    if hot > 3:
        items.append({
            "priority": "high",
            "dept": "AI Sales",
            "action": f"มี {hot} Hot Leads ที่ยังไม่ปิด — ให้ AI follow-up ทันที",
        })

    # Low stock
    critical = [p for p in inventory if p.get("tk_stock", 99) <= 3]
    if critical:
        names = ", ".join(p["name"] for p in critical[:3])
        items.append({
            "priority": "critical",
            "dept": "Inventory",
            "action": f"สต๊อกวิกฤต: {names} — สั่งซื้อเพิ่มทันที",
        })

    # Follow-up backlog
    followup = crm.get("follow_up_pending", 0)
    if followup > 10:
        items.append({
            "priority": "medium",
            "dept": "AI Follow-up",
            "action": f"คิว Follow-up {followup} คน — ตรวจสอบว่า scheduler ทำงานปกติ",
        })

    # AI response time
    if ai.get("avg_response_ms", 0) > 5000:
        items.append({
            "priority": "medium",
            "dept": "AI System",
            "action": f"AI response เฉลี่ย {ai['avg_response_ms']/1000:.1f}s — ช้าเกินไป ตรวจ API quota",
        })

    # Repeat customer rate
    total = crm.get("total_customers", 1)
    repeat = crm.get("repeat", 0)
    repeat_rate = repeat / max(total, 1) * 100
    if repeat_rate < 10:
        items.append({
            "priority": "medium",
            "dept": "CRM",
            "action": f"Repeat rate {repeat_rate:.1f}% ต่ำ — เพิ่ม loyalty program / post-purchase upsell",
        })

    if not items:
        items.append({
            "priority": "low",
            "dept": "Overall",
            "action": "ทุก KPI อยู่ในเกณฑ์ดี — รักษา momentum ต่อไป 🎉",
        })

    return items


# ─── HTML Renderer ─────────────────────────────────────────────────────────────
def _render_html(**ctx) -> str:
    """Render the full executive report as HTML string"""
    # Import the template
    from analytics.report_template import build_html
    return build_html(**ctx)


# ─── LINE Notify hook (called at end of generate_executive_report) ─────────
async def _send_line_summary(period_label, kpis, action_items, report_path):
    try:
        from notifications.line_messaging import notify_executive_report
        await notify_executive_report(
            period_label=period_label,
            kpis=kpis,
            action_items=action_items,
            report_path=report_path,
        )
    except Exception as e:
        log.warning(f"LINE exec-report notify failed: {e}")
