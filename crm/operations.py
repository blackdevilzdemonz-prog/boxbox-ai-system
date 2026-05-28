"""
BoxBox CRM — Database Operations (CRUD)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from crm.database import AsyncSessionLocal
from crm.models import Customer, Conversation, Message, Lead, Sale, FollowupTask

log = logging.getLogger("boxbox.crm")


# ─── Customer ─────────────────────────────────────────────────────────────────
async def upsert_customer(platform_id: str, platform: str, meta: dict = None) -> dict:
    """Get existing or create new customer. Returns dict."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Customer).where(Customer.platform_id == platform_id)
        )
        customer = result.scalar_one_or_none()

        if not customer:
            customer = Customer(
                platform_id=platform_id,
                platform=platform,
                lead_stage="new_lead",
                first_contact_at=datetime.utcnow(),
                last_contact_at=datetime.utcnow(),
            )
            db.add(customer)
            await db.commit()
            await db.refresh(customer)
            log.info(f"👤 New customer created: {platform_id} [{platform}]")
        else:
            customer.last_contact_at = datetime.utcnow()
            customer.total_messages = (customer.total_messages or 0) + 1
            await db.commit()
            await db.refresh(customer)

        return _customer_to_dict(customer)


async def get_customer_by_id(customer_id: int) -> Optional[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Customer).where(Customer.id == customer_id))
        c = result.scalar_one_or_none()
        return _customer_to_dict(c) if c else None


async def update_customer_info(customer_id: int, **kwargs):
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Customer).where(Customer.id == customer_id).values(**kwargs)
        )
        await db.commit()


# ─── Messages ─────────────────────────────────────────────────────────────────
async def log_message(
    customer_id: int,
    direction: str,
    platform: str,
    thread_id: str,
    content: str,
    timestamp: float,
    intent: str = None,
    intent_confidence: float = None,
    ai_latency_ms: int = None,
):
    async with AsyncSessionLocal() as db:
        msg = Message(
            customer_id=customer_id,
            direction=direction,
            platform=platform,
            thread_id=thread_id,
            content=content,
            timestamp=timestamp,
            intent=intent,
            intent_confidence=intent_confidence,
            ai_latency_ms=ai_latency_ms,
        )
        db.add(msg)
        await db.commit()


async def get_customer_history(customer_id: int, limit: int = 10) -> list[dict]:
    """Get last N messages for a customer (for AI context)"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Message)
            .where(Message.customer_id == customer_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        return [
            {
                "direction": m.direction,
                "content": m.content,
                "timestamp": m.timestamp,
                "intent": m.intent,
            }
            for m in reversed(messages)  # chronological order
        ]


# ─── Lead Management ──────────────────────────────────────────────────────────
async def update_lead_stage(customer_id: int, stage: str, product_interest: str = None):
    async with AsyncSessionLocal() as db:
        values = {"lead_stage": stage, "last_contact_at": datetime.utcnow()}
        if product_interest:
            values["product_interest"] = product_interest

        # Calculate lead score based on stage
        stage_scores = {
            "new_lead": 10, "interest": 25, "consideration": 45,
            "ready_to_buy": 75, "purchased": 100, "follow_up": 60,
            "repeat_customer": 100, "lost": 0
        }
        values["lead_score"] = stage_scores.get(stage, 0)

        await db.execute(
            update(Customer).where(Customer.id == customer_id).values(**values)
        )
        await db.commit()
        log.info(f"📊 Lead {customer_id} → {stage} (score: {values['lead_score']})")


# ─── Follow-up Queue ──────────────────────────────────────────────────────────
async def create_followup_task(
    customer_id: int,
    delay_days: int,
    template: str,
    platform: str,
    thread_id: str,
    custom_message: str = None,
):
    scheduled_at = datetime.utcnow() + timedelta(days=delay_days)

    async with AsyncSessionLocal() as db:
        # Check: don't double-schedule same customer + template
        existing = await db.execute(
            select(FollowupTask).where(
                FollowupTask.customer_id == customer_id,
                FollowupTask.message_template == template,
                FollowupTask.status == "pending",
            )
        )
        if existing.scalar_one_or_none():
            return  # already scheduled

        task = FollowupTask(
            customer_id=customer_id,
            scheduled_at=scheduled_at,
            platform=platform,
            thread_id=thread_id,
            message_template=template,
            custom_message=custom_message,
            status="pending",
        )
        db.add(task)
        await db.commit()
        log.info(f"⏰ Follow-up scheduled for customer {customer_id} in {delay_days}d [{template}]")


async def get_pending_followups() -> list[dict]:
    """Get all follow-up tasks due now"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FollowupTask)
            .where(
                FollowupTask.status == "pending",
                FollowupTask.scheduled_at <= datetime.utcnow()
            )
            .order_by(FollowupTask.scheduled_at)
        )
        tasks = result.scalars().all()
        return [
            {
                "id": t.id,
                "customer_id": t.customer_id,
                "platform": t.platform,
                "thread_id": t.thread_id,
                "message_template": t.message_template,
                "custom_message": t.custom_message,
            }
            for t in tasks
        ]


async def mark_followup_sent(task_id: int):
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(FollowupTask)
            .where(FollowupTask.id == task_id)
            .values(status="sent", sent_at=datetime.utcnow())
        )
        await db.commit()


# ─── Sales ────────────────────────────────────────────────────────────────────
async def record_sale(
    customer_id: int,
    product: str,
    amount: float,
    platform: str = "shopee",
    order_id: str = None,
    ai_assisted: bool = True,
    followup_sale: bool = False,
):
    async with AsyncSessionLocal() as db:
        sale = Sale(
            customer_id=customer_id,
            product=product,
            amount=amount,
            platform=platform,
            order_id=order_id,
            ai_assisted=ai_assisted,
            followup_sale=followup_sale,
        )
        db.add(sale)

        # Update customer lifetime value
        await db.execute(
            update(Customer)
            .where(Customer.id == customer_id)
            .values(
                total_purchases=Customer.total_purchases + 1,
                lifetime_value=Customer.lifetime_value + amount,
                last_purchase_at=datetime.utcnow(),
                lead_stage="purchased",
            )
        )
        await db.commit()


# ─── Analytics Queries ────────────────────────────────────────────────────────
async def get_funnel_counts() -> dict:
    """Count customers per lead stage"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Customer.lead_stage, func.count(Customer.id))
            .group_by(Customer.lead_stage)
        )
        return dict(result.all())


async def get_inactive_customers(inactive_days: int) -> list[dict]:
    """Get customers inactive for N+ days"""
    cutoff = datetime.utcnow() - timedelta(days=inactive_days)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Customer)
            .where(
                Customer.last_contact_at < cutoff,
                Customer.lead_stage.notin_(["purchased", "repeat_customer", "lost"]),
                Customer.follow_up_count < 3
            )
        )
        customers = result.scalars().all()
        return [_customer_to_dict(c) for c in customers]


async def get_post_purchase_customers(days_after: int) -> list[dict]:
    """Customers who purchased N days ago (for follow-up/upsell)"""
    target_date = datetime.utcnow() - timedelta(days=days_after)
    window_start = target_date - timedelta(hours=12)
    window_end = target_date + timedelta(hours=12)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Customer)
            .where(
                Customer.last_purchase_at.between(window_start, window_end),
                Customer.lead_stage == "purchased"
            )
        )
        customers = result.scalars().all()
        return [_customer_to_dict(c) for c in customers]


# ─── Helper ───────────────────────────────────────────────────────────────────
def _customer_to_dict(c: Customer) -> dict:
    return {
        "id": c.id,
        "platform_id": c.platform_id,
        "platform": c.platform,
        "name": c.name,
        "phone": c.phone,
        "lead_stage": c.lead_stage,
        "lead_score": c.lead_score,
        "product_interest": c.product_interest,
        "prescription_info": c.prescription_info,
        "total_purchases": c.total_purchases,
        "lifetime_value": c.lifetime_value,
        "follow_up_count": c.follow_up_count,
        "tags": c.tags or [],
        "first_contact_at": c.first_contact_at.isoformat() if c.first_contact_at else None,
        "last_contact_at": c.last_contact_at.isoformat() if c.last_contact_at else None,
    }
