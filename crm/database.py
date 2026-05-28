"""
BoxBox CRM — Database Engine + Session
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from config import DATABASE_URL
from crm.models import Base

# Convert sqlite:// → sqlite+aiosqlite://
_async_url = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")

engine = create_async_engine(_async_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    """Create all tables on startup"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _seed_default_promotions()


async def get_db():
    """FastAPI dependency — yields a DB session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _seed_default_promotions():
    """Seed default promotion templates (run once at startup)"""
    import asyncio
    asyncio.create_task(_async_seed())


async def _async_seed():
    from crm.models import Promotion
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Promotion).limit(1))
        if result.scalar():
            return  # already seeded

        promos = [
            Promotion(
                name="Inactive 3 Days",
                trigger_type="inactive_3d",
                trigger_condition={"inactive_days": 3},
                message_template=(
                    "สวัสดีค่ะ {name} 😊 วันก่อนสนใจแว่น {product} อยู่ใช่มั้ยคะ?\n"
                    "ตอนนี้มีโปรพิเศษเลนส์ฟรีเมื่อซื้อกรอบ เหลือไม่กี่ชิ้นแล้วนะคะ ✨"
                ),
                active=True
            ),
            Promotion(
                name="Post-Purchase Day 7",
                trigger_type="post_purchase",
                trigger_condition={"days_after_purchase": 7},
                message_template=(
                    "สวัสดีค่ะ {name} 💕 ได้รับแว่นแล้วเป็นยังไงบ้างคะ?\n"
                    "ถ้าชอบรีวิวให้หน่อยนะคะ รับส่วนลด 50 บาทสำหรับการซื้อครั้งต่อไปเลยค่ะ 🎁"
                ),
                active=True
            ),
            Promotion(
                name="VIP Upsell",
                trigger_type="vip",
                trigger_condition={"lifetime_value_min": 3000},
                message_template=(
                    "คุณ {name} ลูกค้า VIP ของเราค่ะ 👑\n"
                    "มีคอลเลคชันใหม่ {product} เข้ามาแล้ว ราคาพิเศษสำหรับลูกค้า VIP เท่านั้น\n"
                    "สนใจให้แจ้งนะคะ มีแค่ 10 ชิ้นค่ะ ✨"
                ),
                active=True
            ),
            Promotion(
                name="Blue Block Upsell to Auto",
                trigger_type="post_purchase",
                trigger_condition={"purchased_product_contains": "Blue Block", "days_after_purchase": 14},
                message_template=(
                    "สวัสดีค่ะ {name} 😊 ใช้แว่น Blue Block แล้วเป็นยังไงบ้างคะ?\n"
                    "มีเลนส์ Auto (เปลี่ยนสีอัตโนมัติ) ที่ป้องกันได้ดีกว่า Blue Block เลยค่ะ\n"
                    "สนใจดูไหมคะ? 🌟"
                ),
                active=True
            ),
        ]

        for p in promos:
            db.add(p)
        await db.commit()
