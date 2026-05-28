"""
BoxBox AI — Background Scheduler
Runs: follow-up queue, promotion engine, daily analytics, LINE notifications
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import DAILY_DIGEST_HOUR

log = logging.getLogger("boxbox.scheduler")
_scheduler = AsyncIOScheduler(timezone="Asia/Bangkok")


def start_scheduler():
    # ── Follow-up Queue: every 30 min ─────────────────────────────────────────
    _scheduler.add_job(
        _run_followup_queue, trigger="interval", minutes=30,
        id="followup_queue", replace_existing=True
    )
    # ── Promotion Engine: daily 10:00 ─────────────────────────────────────────
    _scheduler.add_job(
        _run_promotions, trigger=CronTrigger(hour=10, minute=0),
        id="daily_promotions", replace_existing=True
    )
    # ── Stock Alert → LINE: daily 09:00 ───────────────────────────────────────
    _scheduler.add_job(
        _run_stock_alert, trigger=CronTrigger(hour=9, minute=0),
        id="daily_stock_alert", replace_existing=True
    )
    # ── Daily Analytics Snapshot: daily 09:05 ────────────────────────────────
    _scheduler.add_job(
        _run_daily_analytics, trigger=CronTrigger(hour=9, minute=5),
        id="daily_analytics", replace_existing=True
    )
    # ── Daily Digest → LINE: configurable hour (default 20:00) ───────────────
    _scheduler.add_job(
        _run_daily_digest, trigger=CronTrigger(hour=DAILY_DIGEST_HOUR, minute=0),
        id="daily_digest_line", replace_existing=True
    )
    # ── Executive Report: 1st of month 09:00 ─────────────────────────────────
    _scheduler.add_job(
        _run_executive_report, trigger=CronTrigger(day=1, hour=9, minute=0),
        id="exec_report_day1", replace_existing=True
    )
    # ── Executive Report: 16th of month 09:00 ────────────────────────────────
    _scheduler.add_job(
        _run_executive_report, trigger=CronTrigger(day=16, hour=9, minute=0),
        id="exec_report_day16", replace_existing=True
    )

    _scheduler.start()
    log.info("⏰ Scheduler started — 7 jobs active")


def stop_scheduler():
    _scheduler.shutdown(wait=False)


# ─── Job Runners ──────────────────────────────────────────────────────────────
async def _run_followup_queue():
    try:
        from promotions.engine import process_followup_queue
        await process_followup_queue()
    except Exception as e:
        log.error(f"Follow-up queue error: {e}")


async def _run_promotions():
    try:
        from promotions.engine import run_promotion_cycle
        sent = await run_promotion_cycle()
        if sent > 0:
            from notifications.line_messaging import notify_promo_result
            await notify_promo_result("Daily Promo Cycle", sent, 0)
    except Exception as e:
        log.error(f"Promotion cycle error: {e}")


async def _run_stock_alert():
    """Pull inventory data and send LINE alert for low/critical stock."""
    try:
        import json
        from pathlib import Path
        from notifications.line_messaging import notify_low_stock

        inv_path = Path("inventory_data.json")
        if inv_path.exists():
            products = json.loads(inv_path.read_text())
            danger = [p for p in products if p.get("warn") or p.get("tk_stock", 99) <= 10]
            if danger:
                await notify_low_stock(danger)
                log.info(f"📦 Stock alert sent: {len(danger)} products")
        else:
            log.info("inventory_data.json not found — skipping stock alert")
    except Exception as e:
        log.error(f"Stock alert error: {e}")


async def _run_daily_analytics():
    try:
        from analytics.engine import generate_and_store_daily_report
        await generate_and_store_daily_report()
    except Exception as e:
        log.error(f"Analytics report error: {e}")


async def _run_daily_digest():
    """Send end-of-day LINE summary."""
    try:
        from analytics.engine import get_daily_summary
        from notifications.line_messaging import notify_daily_digest
        summary = await get_daily_summary()
        await notify_daily_digest(summary)
        log.info("📊 Daily digest sent to LINE")
    except Exception as e:
        log.error(f"Daily digest error: {e}")


async def _run_executive_report():
    """Generate full executive report and send LINE summary."""
    try:
        from analytics.executive_report import generate_executive_report
        report_path = await generate_executive_report()
        log.info(f"📋 Executive report generated: {report_path}")
    except Exception as e:
        log.error(f"Executive report error: {e}")
