"""
BoxBox AI — Analytics Engine
Daily summaries, funnel stats, AI performance metrics
"""
import logging
from datetime import datetime, date, timedelta

from sqlalchemy import select, func, and_
from crm.database import AsyncSessionLocal
from crm.models import Customer, Message, Sale, DailyAnalytics, FollowupTask

log = logging.getLogger("boxbox.analytics")


async def get_daily_summary() -> dict:
    """Current day summary for the /analytics/summary endpoint"""
    today = date.today().isoformat()

    async with AsyncSessionLocal() as db:
        # New customers today
        new_leads = await db.scalar(
            select(func.count(Customer.id))
            .where(func.date(Customer.first_contact_at) == today)
        ) or 0

        # Messages today
        total_messages = await db.scalar(
            select(func.count(Message.id))
            .where(func.date(Message.created_at) == today)
        ) or 0

        # AI responses (outgoing)
        ai_responses = await db.scalar(
            select(func.count(Message.id))
            .where(
                Message.direction == "out",
                func.date(Message.created_at) == today
            )
        ) or 0

        # Revenue today
        revenue = await db.scalar(
            select(func.sum(Sale.amount))
            .where(func.date(Sale.ordered_at) == today)
        ) or 0.0

        # Conversions (purchases today)
        conversions = await db.scalar(
            select(func.count(Sale.id))
            .where(func.date(Sale.ordered_at) == today)
        ) or 0

        # Avg response time
        avg_latency = await db.scalar(
            select(func.avg(Message.ai_latency_ms))
            .where(
                Message.direction == "out",
                Message.ai_latency_ms.isnot(None),
                func.date(Message.created_at) == today
            )
        ) or 0

        return {
            "date": today,
            "new_leads": new_leads,
            "total_messages": total_messages,
            "ai_responses_sent": ai_responses,
            "conversions": conversions,
            "revenue_thb": round(float(revenue), 2),
            "avg_ai_response_ms": int(avg_latency),
            "conversion_rate": round(conversions / max(new_leads, 1) * 100, 1),
        }


async def get_funnel_stats() -> dict:
    """Full lead funnel breakdown"""
    from crm.operations import get_funnel_counts
    stage_counts = await get_funnel_counts()

    stages = [
        "new_lead", "interest", "consideration",
        "ready_to_buy", "purchased", "follow_up",
        "repeat_customer", "lost"
    ]

    funnel = {s: stage_counts.get(s, 0) for s in stages}
    total = sum(funnel.values())

    # Conversion rates between stages
    def conv_rate(a, b):
        return round(funnel[b] / max(funnel[a], 1) * 100, 1)

    return {
        "funnel": funnel,
        "total_leads": total,
        "conversion_rates": {
            "new_to_interest":      conv_rate("new_lead", "interest"),
            "interest_to_consider": conv_rate("interest", "consideration"),
            "consider_to_ready":    conv_rate("consideration", "ready_to_buy"),
            "ready_to_purchased":   conv_rate("ready_to_buy", "purchased"),
            "purchased_to_repeat":  conv_rate("purchased", "repeat_customer"),
            "overall":              conv_rate("new_lead", "purchased"),
        }
    }


async def get_7day_trend() -> list[dict]:
    """Last 7 days of daily snapshots"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DailyAnalytics)
            .order_by(DailyAnalytics.date.desc())
            .limit(7)
        )
        rows = result.scalars().all()
        return [
            {
                "date": r.date,
                "new_leads": r.new_leads,
                "conversions": r.conversions,
                "revenue": r.revenue,
                "ai_responses": r.ai_responses_sent,
            }
            for r in reversed(rows)
        ]


async def generate_and_store_daily_report():
    """Called daily at 09:00 — stores analytics snapshot"""
    summary = await get_daily_summary()
    funnel = await get_funnel_stats()
    today = date.today().isoformat()

    async with AsyncSessionLocal() as db:
        # Check if today's record exists
        existing = await db.scalar(
            select(DailyAnalytics).where(DailyAnalytics.date == today)
        )

        if existing:
            existing.new_leads = summary["new_leads"]
            existing.total_conversations = summary["total_messages"]
            existing.ai_responses_sent = summary["ai_responses_sent"]
            existing.conversions = summary["conversions"]
            existing.revenue = summary["revenue_thb"]
            existing.avg_response_time_ms = summary["avg_ai_response_ms"]
            existing.snapshot = funnel
        else:
            record = DailyAnalytics(
                date=today,
                new_leads=summary["new_leads"],
                total_conversations=summary["total_messages"],
                ai_responses_sent=summary["ai_responses_sent"],
                conversions=summary["conversions"],
                revenue=summary["revenue_thb"],
                avg_response_time_ms=summary["avg_ai_response_ms"],
                snapshot=funnel,
            )
            db.add(record)

        await db.commit()
        log.info(f"📊 Daily analytics stored for {today}: {summary['conversions']} conversions, ฿{summary['revenue_thb']:.0f}")
