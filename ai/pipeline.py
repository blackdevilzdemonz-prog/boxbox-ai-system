"""
BoxBox AI — Master Sales Pipeline
Stages: Triage → Classify → Respond → CRM → Follow-up → Escalate → Notify
"""
import json
import logging
import time
from typing import Optional

import anthropic

from config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS,
    HUMAN_ESCALATION_PHRASES, HOT_LEAD_NOTIFY_THRESHOLD, SALE_NOTIFY_MIN_AMOUNT
)
from ai.classifier import classify_intent
from ai.responder import generate_sales_response
from ai.followup import determine_followup_schedule

log = logging.getLogger("boxbox.ai")
_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def run_ai_pipeline(
    customer: dict,
    message: str,
    attachments: list,
    history: list,
    platform: str,
    thread_id: str,
    is_comment: bool = False,
) -> dict:
    start_time = time.time()

    # ── Stage 1: Triage ──────────────────────────────────────────────────────
    if not message and not attachments:
        return _no_reply("empty message")
    if _is_spam(message):
        return _no_reply("spam detected")

    # ── Stage 2: Intent Classification ──────────────────────────────────────
    classification = await classify_intent(
        message=message, history=history, customer=customer, client=_client,
    )

    intent           = classification.get("intent", "warm")
    confidence       = classification.get("confidence", 0.5)
    _recommended = classification.get("recommended_products", [])
    product_interest = _recommended[0] if _recommended else None
    customer_need    = classification.get("customer_need", "")
    key_concern      = classification.get("key_concern", "")

    log.info(f"🧠 Intent: {intent} ({confidence:.0%}) | Need: {customer_need}")

    # ── Stage 2b: LINE Notify for HOT leads ──────────────────────────────────
    if intent == "hot" and confidence >= HOT_LEAD_NOTIFY_THRESHOLD:
        try:
            from notifications.line_messaging import notify_hot_lead
            await notify_hot_lead(
                customer=customer,
                message=message,
                product=product_interest or "ไม่ระบุ",
                confidence=confidence,
            )
        except Exception as e:
            log.warning(f"LINE hot-lead notify error: {e}")

    # ── Stage 3: Human Escalation Check ─────────────────────────────────────
    escalation_reason = _check_escalation(message, intent)
    if escalation_reason:
        reply = _escalation_handoff_message(customer)
        return {
            **_base_result(),
            "should_reply": True,
            "reply": reply,
            "intent": intent,
            "intent_confidence": confidence,
            "escalate_to_human": True,
            "escalation_reason": escalation_reason,
            "new_stage": customer["lead_stage"],
        }

    # ── Stage 4: Skip spam ───────────────────────────────────────────────────
    if intent == "spam":
        return _no_reply("spam intent")

    # ── Stage 5: Generate Response ───────────────────────────────────────────
    reply = await generate_sales_response(
        customer=customer, message=message, intent=intent,
        customer_need=customer_need, key_concern=key_concern,
        product_interest=product_interest, history=history,
        is_comment=is_comment, client=_client,
    )

    # ── Stage 6: New CRM stage ───────────────────────────────────────────────
    new_stage = _calculate_new_stage(customer["lead_stage"], intent, classification)

    # ── Stage 7: Follow-up scheduling ────────────────────────────────────────
    followup_plan = determine_followup_schedule(
        intent=intent, current_stage=new_stage,
        customer=customer, classification=classification,
    )

    ai_latency = int((time.time() - start_time) * 1000)
    log.info(f"⚡ Pipeline done in {ai_latency}ms | Stage: {new_stage}")

    return {
        "should_reply": True,
        "reply": reply,
        "intent": intent,
        "intent_confidence": confidence,
        "new_stage": new_stage,
        "product_interest": product_interest,
        "schedule_followup": followup_plan["should_schedule"],
        "followup_delay_days": followup_plan["delay_days"],
        "followup_template": followup_plan["template"],
        "escalate_to_human": False,
        "escalation_reason": None,
        "ai_latency_ms": ai_latency,
    }


# ─── Sale Confirmed (call from order webhook / CRM) ──────────────────────────
async def notify_sale_if_worthy(customer: dict, product: str, amount: float):
    """Call this after recording a confirmed sale to send LINE notification."""
    if amount >= SALE_NOTIFY_MIN_AMOUNT:
        try:
            from notifications.line_messaging import notify_sale_closed
            await notify_sale_closed(customer=customer, product=product, amount=amount)
        except Exception as e:
            log.warning(f"LINE sale notify error: {e}")


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _is_spam(message: str) -> bool:
    return any(p in message for p in ["http://", "https://", "bit.ly", "goo.gl"])


def _check_escalation(message: str, intent: str) -> Optional[str]:
    msg_lower = message.lower()
    for phrase in HUMAN_ESCALATION_PHRASES:
        if phrase in msg_lower:
            return f"Anger/complaint keyword: '{phrase}'"
    if intent == "support" and any(
        w in msg_lower for w in ["เสีย", "พัง", "ไม่ได้", "ผิด", "ไม่ตรง"]
    ):
        return "Post-purchase support issue"
    return None


def _calculate_new_stage(current_stage: str, intent: str, classification: dict) -> str:
    stage_progression = {
        "hot":  {"new_lead": "ready_to_buy", "interest": "ready_to_buy", "consideration": "ready_to_buy"},
        "warm": {"new_lead": "interest", "interest": "consideration"},
        "info": {"new_lead": "interest"},
    }
    progression = stage_progression.get(intent, {})
    new_stage = progression.get(current_stage, current_stage)
    if any(s in classification.get("signals", []) for s in ["order_confirmed", "payment_mentioned"]):
        return "purchased"
    return new_stage


def _escalation_handoff_message(customer: dict) -> str:
    name = customer.get("name", "คุณลูกค้า")
    return (
        f"ขอโทษนะคะ {name} 🙏 "
        f"เรื่องนี้ต้องให้ทีมงานของเราดูแลโดยตรงค่ะ "
        f"รอสักครู่นะคะ เจ้าหน้าที่จะติดต่อกลับเร็วๆ นี้เลยค่ะ 💙"
    )


def _no_reply(reason: str) -> dict:
    return {**_base_result(), "should_reply": False, "_skip_reason": reason}


def _base_result() -> dict:
    return {
        "should_reply": False, "reply": None,
        "intent": "spam", "intent_confidence": 0.0,
        "new_stage": None, "product_interest": None,
        "schedule_followup": False, "followup_delay_days": 1,
        "followup_template": "followup_day1",
        "escalate_to_human": False, "escalation_reason": None,
        "ai_latency_ms": 0,
    }
