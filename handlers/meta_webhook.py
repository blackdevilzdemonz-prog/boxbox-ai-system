"""
BoxBox AI — Meta Webhook Event Handlers
Processes: FB Messenger, IG DM, FB/IG Comments
"""
import logging
from datetime import datetime, timezone

from crm.operations import (
    upsert_customer, log_message, get_customer_history,
    update_lead_stage, create_followup_task
)
from ai.pipeline import run_ai_pipeline
from messenger.meta_api import send_messenger_reply, send_ig_reply, send_comment_reply

log = logging.getLogger("boxbox.webhook")


# ─── FB Messenger ─────────────────────────────────────────────────────────────
async def handle_messenger_event(event: dict):
    sender_id    = event.get("sender", {}).get("id")
    recipient_id = event.get("recipient", {}).get("id")
    message      = event.get("message", {})

    if message.get("is_echo"):
        return

    text        = message.get("text", "")
    attachments = message.get("attachments", [])
    timestamp   = event.get("timestamp", datetime.now(timezone.utc).timestamp())

    if not text and not attachments:
        return

    log.info(f"📨 FB Messenger from {sender_id}: {text[:60]}")

    customer = await upsert_customer(
        platform_id=sender_id,
        platform="facebook",
        meta={"page_id": recipient_id, "attachment_count": len(attachments)}
    )

    await log_message(
        customer_id=customer["id"], direction="in", platform="facebook",
        thread_id=sender_id, content=text or f"[{len(attachments)} attachment(s)]",
        timestamp=timestamp
    )

    history = await get_customer_history(customer["id"], limit=10)

    result = await run_ai_pipeline(
        customer=customer, message=text, attachments=attachments,
        history=history, platform="facebook", thread_id=sender_id
    )

    if result["should_reply"] and result.get("reply"):
        await send_messenger_reply(recipient_id=sender_id, text=result["reply"])
        await log_message(
            customer_id=customer["id"], direction="out", platform="facebook",
            thread_id=sender_id, content=result["reply"],
            timestamp=datetime.now(timezone.utc).timestamp()
        )

    if result.get("new_stage"):
        await update_lead_stage(customer["id"], result["new_stage"], result.get("product_interest"))

    if result.get("schedule_followup"):
        await create_followup_task(
            customer_id=customer["id"], delay_days=result["followup_delay_days"],
            template=result["followup_template"], platform="facebook", thread_id=sender_id
        )

    if result.get("escalate_to_human"):
        await _notify_human_escalation(customer, text, result.get("escalation_reason"))


# ─── Instagram DM ─────────────────────────────────────────────────────────────
async def handle_ig_dm_event(event: dict):
    sender_id = event.get("sender", {}).get("id")
    message   = event.get("message", {})

    if message.get("is_echo"):
        return

    text        = message.get("text", "")
    attachments = message.get("attachments", [])

    if not text and not attachments:
        return

    log.info(f"📸 IG DM from {sender_id}: {text[:60]}")

    customer = await upsert_customer(platform_id=sender_id, platform="instagram")
    await log_message(
        customer_id=customer["id"], direction="in", platform="instagram",
        thread_id=sender_id, content=text or "[IG attachment]",
        timestamp=datetime.now(timezone.utc).timestamp()
    )

    history = await get_customer_history(customer["id"], limit=10)
    result  = await run_ai_pipeline(
        customer=customer, message=text, attachments=attachments,
        history=history, platform="instagram", thread_id=sender_id
    )

    if result["should_reply"] and result.get("reply"):
        await send_ig_reply(recipient_id=sender_id, text=result["reply"])
        await log_message(
            customer_id=customer["id"], direction="out", platform="instagram",
            thread_id=sender_id, content=result["reply"],
            timestamp=datetime.now(timezone.utc).timestamp()
        )

    if result.get("new_stage"):
        await update_lead_stage(customer["id"], result["new_stage"], result.get("product_interest"))

    if result.get("schedule_followup"):
        await create_followup_task(
            customer_id=customer["id"], delay_days=result["followup_delay_days"],
            template=result["followup_template"], platform="instagram", thread_id=sender_id
        )

    if result.get("escalate_to_human"):
        await _notify_human_escalation(customer, text, result.get("escalation_reason"))


# ─── Comments (FB + IG) ───────────────────────────────────────────────────────
async def handle_comment_event(value: dict, platform: str = "facebook"):
    commenter_id = value.get("from", {}).get("id")
    comment_text = value.get("message", "")
    comment_id   = value.get("comment_id") or value.get("id")

    if not comment_text or not commenter_id:
        return

    log.info(f"💬 Comment [{platform}] from {commenter_id}: {comment_text[:60]}")

    customer = await upsert_customer(platform_id=commenter_id, platform=platform)
    await log_message(
        customer_id=customer["id"], direction="in",
        platform=f"{platform}_comment", thread_id=comment_id,
        content=comment_text, timestamp=datetime.now(timezone.utc).timestamp()
    )

    history = await get_customer_history(customer["id"], limit=5)
    result  = await run_ai_pipeline(
        customer=customer, message=comment_text, attachments=[],
        history=history, platform=f"{platform}_comment",
        thread_id=comment_id, is_comment=True
    )

    if result["should_reply"] and result.get("reply"):
        await send_comment_reply(comment_id=comment_id, text=result["reply"], platform=platform)
        await log_message(
            customer_id=customer["id"], direction="out",
            platform=f"{platform}_comment", thread_id=comment_id,
            content=result["reply"], timestamp=datetime.now(timezone.utc).timestamp()
        )


# ─── Human Escalation → LINE Notify ─────────────────────────────────────────
async def _notify_human_escalation(customer: dict, message: str, reason: str):
    """Fire LINE Notify immediately when human intervention is needed."""
    log.warning(
        f"🚨 ESCALATION | {customer.get('platform_id')} | {reason}"
    )
    try:
        from notifications.line_messaging import notify_human_escalation
        await notify_human_escalation(customer, message, reason)
    except Exception as e:
        log.error(f"LINE escalation notify failed: {e}")
