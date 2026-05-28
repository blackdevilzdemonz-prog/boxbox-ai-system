"""
BoxBox AI — Promotion Engine
Triggers: inactive customers, post-purchase upsell, VIP campaigns
"""
import logging
from datetime import datetime

from crm.operations import (
    get_inactive_customers, get_post_purchase_customers,
    get_pending_followups, mark_followup_sent, update_customer_info,
    log_message
)
from ai.followup import render_template
from messenger.meta_api import send_messenger_reply, send_ig_reply
from config import PROMO_INACTIVE_DAYS

log = logging.getLogger("boxbox.promotions")


async def run_promotion_cycle():
    """Daily promotion cycle — runs at 10:00 AM"""
    log.info("🎯 Running promotion cycle...")

    sent = 0

    # ── Inactive customers (3 days) ───────────────────────────────────────────
    inactive = await get_inactive_customers(PROMO_INACTIVE_DAYS)
    for customer in inactive:
        if customer.get("follow_up_count", 0) >= 3:
            continue

        msg = render_template("warm_lead_day3", customer)
        if msg:
            success = await _send_to_customer(customer, msg)
            if success:
                await update_customer_info(
                    customer["id"],
                    follow_up_count=(customer.get("follow_up_count", 0) + 1)
                )
                sent += 1

    # ── Post-purchase day 7 follow-up ─────────────────────────────────────────
    post_purchase = await get_post_purchase_customers(days_after=7)
    for customer in post_purchase:
        msg = render_template("post_purchase_day7", customer)
        if msg:
            success = await _send_to_customer(customer, msg)
            if success:
                sent += 1

    log.info(f"🎯 Promotion cycle complete: {sent} messages sent")
    return sent


async def process_followup_queue():
    """Process all pending follow-up tasks due now — runs every 30 min"""
    tasks = await get_pending_followups()
    if not tasks:
        return

    log.info(f"⏰ Processing {len(tasks)} follow-up tasks...")

    for task in tasks:
        customer_id = task["customer_id"]
        platform = task["platform"]
        thread_id = task["thread_id"]
        template_key = task["message_template"]

        # Get customer for template rendering
        from crm.operations import get_customer_by_id
        customer = await get_customer_by_id(customer_id)
        if not customer:
            await mark_followup_sent(task["id"])
            continue

        # Use custom message if set, otherwise render template
        if task.get("custom_message"):
            msg = task["custom_message"]
        else:
            msg = render_template(template_key, customer)

        if not msg:
            await mark_followup_sent(task["id"])
            continue

        # Send message
        success = await _send_to_platform(platform, thread_id, msg)

        if success:
            await mark_followup_sent(task["id"])
            await log_message(
                customer_id=customer_id,
                direction="out",
                platform=platform,
                thread_id=thread_id,
                content=msg,
                timestamp=datetime.utcnow().timestamp(),
            )
            await update_customer_info(
                customer_id,
                follow_up_count=(customer.get("follow_up_count", 0) + 1),
                last_contact_at=datetime.utcnow(),
            )
            log.info(f"✅ Follow-up sent to customer {customer_id} [{template_key}]")


async def _send_to_customer(customer: dict, message: str) -> bool:
    platform = customer.get("platform", "facebook")
    thread_id = customer["platform_id"]
    return await _send_to_platform(platform, thread_id, message)


async def _send_to_platform(platform: str, thread_id: str, message: str) -> bool:
    try:
        if "instagram" in platform:
            return await send_ig_reply(thread_id, message)
        else:
            return await send_messenger_reply(thread_id, message)
    except Exception as e:
        log.error(f"Promo send failed [{platform}:{thread_id}]: {e}")
        return False
