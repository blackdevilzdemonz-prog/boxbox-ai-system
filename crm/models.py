"""
BoxBox CRM — SQLAlchemy Models
Database Schema for Enterprise AI Sales System
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    Text, ForeignKey, JSON, Enum
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


# ─── Enums ────────────────────────────────────────────────────────────────────
class Platform(str, enum.Enum):
    FACEBOOK          = "facebook"
    INSTAGRAM         = "instagram"
    FACEBOOK_COMMENT  = "facebook_comment"
    INSTAGRAM_COMMENT = "instagram_comment"

class LeadStage(str, enum.Enum):
    NEW_LEAD       = "new_lead"
    INTEREST       = "interest"
    CONSIDERATION  = "consideration"
    READY_TO_BUY   = "ready_to_buy"
    PURCHASED      = "purchased"
    FOLLOW_UP      = "follow_up"
    REPEAT_CUSTOMER = "repeat_customer"
    LOST           = "lost"

class Intent(str, enum.Enum):
    HOT     = "hot"       # ready to buy
    WARM    = "warm"      # interested, needs nurturing
    INFO    = "info"      # just asking for info
    SUPPORT = "support"   # post-purchase support
    SPAM    = "spam"      # ignore

class MessageDirection(str, enum.Enum):
    IN  = "in"
    OUT = "out"

class FollowupStatus(str, enum.Enum):
    PENDING  = "pending"
    SENT     = "sent"
    SKIPPED  = "skipped"
    FAILED   = "failed"


# ─── Customers ────────────────────────────────────────────────────────────────
class Customer(Base):
    __tablename__ = "customers"

    id               = Column(Integer, primary_key=True, index=True)
    platform_id      = Column(String(100), unique=True, index=True)  # Meta user ID
    platform         = Column(String(30), default="facebook")
    name             = Column(String(200), nullable=True)
    phone            = Column(String(20), nullable=True)
    email            = Column(String(200), nullable=True)

    # Stage & Scoring
    lead_stage       = Column(String(30), default=LeadStage.NEW_LEAD)
    lead_score       = Column(Integer, default=0)          # 0-100
    product_interest = Column(String(200), nullable=True)  # top interested product
    prescription_info= Column(Text, nullable=True)         # สายตา info from chat

    # Purchase History
    total_purchases  = Column(Integer, default=0)
    lifetime_value   = Column(Float, default=0.0)          # THB
    last_purchase_at = Column(DateTime, nullable=True)

    # Engagement
    first_contact_at = Column(DateTime, default=datetime.utcnow)
    last_contact_at  = Column(DateTime, default=datetime.utcnow)
    total_messages   = Column(Integer, default=0)
    follow_up_count  = Column(Integer, default=0)

    # AI Tags
    tags             = Column(JSON, default=list)          # ["premium", "referred", "vip"]
    notes            = Column(Text, nullable=True)

    # Relationships
    messages         = relationship("Message", back_populates="customer", cascade="all, delete")
    conversations    = relationship("Conversation", back_populates="customer", cascade="all, delete")
    leads            = relationship("Lead", back_populates="customer", cascade="all, delete")
    sales            = relationship("Sale", back_populates="customer", cascade="all, delete")
    followup_tasks   = relationship("FollowupTask", back_populates="customer", cascade="all, delete")


# ─── Conversations ────────────────────────────────────────────────────────────
class Conversation(Base):
    __tablename__ = "conversations"

    id            = Column(Integer, primary_key=True, index=True)
    customer_id   = Column(Integer, ForeignKey("customers.id"), index=True)
    platform      = Column(String(30))
    thread_id     = Column(String(100), index=True)
    started_at    = Column(DateTime, default=datetime.utcnow)
    last_msg_at   = Column(DateTime, default=datetime.utcnow)
    status        = Column(String(20), default="active")  # active/closed/escalated

    # AI Analysis
    dominant_intent  = Column(String(20), nullable=True)
    intent_history   = Column(JSON, default=list)   # [{"intent": "warm", "ts": ...}]
    resolved_by_ai   = Column(Boolean, default=False)
    escalated        = Column(Boolean, default=False)
    escalation_reason= Column(Text, nullable=True)

    customer  = relationship("Customer", back_populates="conversations")
    messages  = relationship("Message", back_populates="conversation", cascade="all, delete")


# ─── Messages ─────────────────────────────────────────────────────────────────
class Message(Base):
    __tablename__ = "messages"

    id              = Column(Integer, primary_key=True, index=True)
    customer_id     = Column(Integer, ForeignKey("customers.id"), index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    direction       = Column(String(5))       # in / out
    platform        = Column(String(30))
    thread_id       = Column(String(100))
    content         = Column(Text)
    timestamp       = Column(Float)           # unix timestamp
    created_at      = Column(DateTime, default=datetime.utcnow)

    # AI Metadata
    intent          = Column(String(20), nullable=True)
    intent_confidence= Column(Float, nullable=True)
    ai_latency_ms   = Column(Integer, nullable=True)

    customer      = relationship("Customer", back_populates="messages")
    conversation  = relationship("Conversation", back_populates="messages")


# ─── Leads ────────────────────────────────────────────────────────────────────
class Lead(Base):
    __tablename__ = "leads"

    id               = Column(Integer, primary_key=True, index=True)
    customer_id      = Column(Integer, ForeignKey("customers.id"), index=True)
    stage            = Column(String(30), default=LeadStage.NEW_LEAD)
    product_interest = Column(String(200), nullable=True)
    score            = Column(Integer, default=0)
    last_action      = Column(String(200), nullable=True)
    next_followup_at = Column(DateTime, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="leads")


# ─── Sales ────────────────────────────────────────────────────────────────────
class Sale(Base):
    __tablename__ = "sales"

    id          = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    product     = Column(String(200))
    sku         = Column(String(100), nullable=True)
    amount      = Column(Float)
    platform    = Column(String(30), default="shopee")  # shopee/tiktok/direct
    order_id    = Column(String(100), nullable=True)
    ordered_at  = Column(DateTime, default=datetime.utcnow)

    # Attribution
    ai_assisted   = Column(Boolean, default=True)   # was this closed by AI?
    followup_sale = Column(Boolean, default=False)  # came from follow-up?

    customer = relationship("Customer", back_populates="sales")


# ─── Follow-up Queue ──────────────────────────────────────────────────────────
class FollowupTask(Base):
    __tablename__ = "followup_tasks"

    id              = Column(Integer, primary_key=True, index=True)
    customer_id     = Column(Integer, ForeignKey("customers.id"), index=True)
    scheduled_at    = Column(DateTime, index=True)
    platform        = Column(String(30))
    thread_id       = Column(String(100))
    message_template= Column(String(100))  # template key, e.g. "followup_day1"
    custom_message  = Column(Text, nullable=True)
    status          = Column(String(20), default=FollowupStatus.PENDING)
    sent_at         = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="followup_tasks")


# ─── Promotions ───────────────────────────────────────────────────────────────
class Promotion(Base):
    __tablename__ = "promotions"

    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String(200))
    trigger_type     = Column(String(50))   # inactive_3d / post_purchase / seasonal / vip
    trigger_condition= Column(JSON)         # {"inactive_days": 3} or {"stage": "purchased"}
    message_template = Column(Text)         # Thai message template with {name} placeholder
    active           = Column(Boolean, default=True)
    sent_count       = Column(Integer, default=0)
    conversion_count = Column(Integer, default=0)
    created_at       = Column(DateTime, default=datetime.utcnow)


# ─── Analytics Snapshots ──────────────────────────────────────────────────────
class DailyAnalytics(Base):
    __tablename__ = "daily_analytics"

    id                   = Column(Integer, primary_key=True)
    date                 = Column(String(10), unique=True, index=True)  # YYYY-MM-DD
    new_leads            = Column(Integer, default=0)
    total_conversations  = Column(Integer, default=0)
    ai_responses_sent    = Column(Integer, default=0)
    human_escalations    = Column(Integer, default=0)
    conversions          = Column(Integer, default=0)
    revenue              = Column(Float, default=0.0)
    avg_response_time_ms = Column(Integer, default=0)
    top_intent           = Column(String(20), nullable=True)
    top_product          = Column(String(200), nullable=True)
    snapshot             = Column(JSON, default=dict)  # full funnel snapshot
