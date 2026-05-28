"""
BoxBox AI — Follow-up & Upsell Scheduler Logic
Determines if/when/what follow-up to send based on pipeline state
"""
from config import FOLLOW_UP_DAYS, MAX_FOLLOW_UPS


def determine_followup_schedule(
    intent: str,
    current_stage: str,
    customer: dict,
    classification: dict,
) -> dict:
    """
    Returns:
        {
            should_schedule: bool,
            delay_days: int,
            template: str,
        }
    """
    follow_up_count = customer.get("follow_up_count", 0)
    total_purchases = customer.get("total_purchases", 0)

    # Max follow-ups reached
    if follow_up_count >= MAX_FOLLOW_UPS:
        return _no_followup()

    # Don't follow up on spam
    if intent == "spam":
        return _no_followup()

    # ── Post-purchase follow-up ──────────────────────────────────────────────
    if current_stage == "purchased":
        return {
            "should_schedule": True,
            "delay_days": 7,
            "template": "post_purchase_day7",
        }

    # ── Hot lead — follow up next day if no purchase ──────────────────────────
    if intent == "hot" and current_stage != "purchased":
        return {
            "should_schedule": True,
            "delay_days": 1,
            "template": "hot_lead_followup",
        }

    # ── Warm lead — follow up in 3 days ──────────────────────────────────────
    if intent == "warm" and current_stage in ("interest", "consideration"):
        return {
            "should_schedule": True,
            "delay_days": 3,
            "template": "warm_lead_day3",
        }

    # ── Info intent — light follow-up in 3 days ───────────────────────────────
    if intent == "info" and current_stage == "interest":
        return {
            "should_schedule": True,
            "delay_days": 3,
            "template": "info_nurture",
        }

    return _no_followup()


def _no_followup() -> dict:
    return {
        "should_schedule": False,
        "delay_days": 0,
        "template": "",
    }


# ─── Follow-up Message Templates ─────────────────────────────────────────────
FOLLOWUP_TEMPLATES = {
    "hot_lead_followup": (
        "สวัสดีค่ะ {name} 😊 เมื่อวานสนใจแว่น {product} อยู่ใช่มั้ยคะ?\n"
        "ยังมีสต๊อกอยู่นะคะ ถ้าต้องการช่วยจัดได้เลยค่ะ ✨"
    ),
    "warm_lead_day3": (
        "สวัสดีค่ะ {name} 💕 คิดถึงแว่น {product} อยู่บ้างมั้ยคะ?\n"
        "มีคำถามอะไรเพิ่มเติมไหมคะ? ยินดีช่วยเลยนะคะ 😊"
    ),
    "info_nurture": (
        "สวัสดีค่ะ {name} 🌟 เมื่อกี้ถามเรื่อง {product} ไปนะคะ\n"
        "มีโปรพิเศษสำหรับคนใหม่ด้วยนะคะ สนใจให้บอกเลยค่ะ 💙"
    ),
    "post_purchase_day7": (
        "สวัสดีค่ะ {name} 💕 ได้รับแว่นแล้วใส่เป็นยังไงบ้างคะ?\n"
        "ถ้าชอบฝากรีวิวด้วยนะคะ ขอบคุณมากค่ะ 🙏✨"
    ),
    "post_purchase_day14_upsell": (
        "สวัสดีค่ะ {name} 😊 ใส่แว่นใหม่แล้วพอใจไหมคะ?\n"
        "อยากแนะนำ {upsell_product} ที่เข้ากับที่มีอยู่มากเลยค่ะ สนใจดูไหม? 🌟"
    ),
}


def render_template(template_key: str, customer: dict, upsell_product: str = None) -> str:
    """Render a follow-up message template"""
    template = FOLLOWUP_TEMPLATES.get(template_key, "")
    if not template:
        return ""

    name = customer.get("name", "คุณลูกค้า")
    product = customer.get("product_interest", "แว่น")

    return template.format(
        name=name,
        product=product,
        upsell_product=upsell_product or "สินค้าแนะนำ",
    )
