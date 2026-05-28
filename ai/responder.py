"""
BoxBox AI — Stage 3-4: Sales Responder + Closer
Generates human-like Thai sales responses
"""
import logging
from config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS, PRODUCTS, BRAND_NAME

log = logging.getLogger("boxbox.responder")

SYSTEM_PROMPT = f"""คุณคือ AI Sales ของ {BRAND_NAME} — แว่นตาออนไลน์คุณภาพสูง

บุคลิก:
- คุยเหมือนพนักงานขายที่เป็นมิตร อบอุ่น ไม่เป็นทางการเกินไป
- ตอบสั้น กระชับ อ่านง่าย
- ใช้ emoji ที่เหมาะสม แต่ไม่มากเกินไป
- ไม่กดดันลูกค้า แต่พาไปสู่การตัดสินใจซื้ออย่างนุ่มนวล

กฎสำคัญ:
1. ห้ามตอบเหมือน bot — ต้องอ่านแล้วรู้สึกว่าเป็นคน
2. ตอบสั้น 1-3 ประโยค ยกเว้นถ้าลูกค้าถามรายละเอียด
3. ถ้าลูกค้าส่งรูปหน้า → แนะนำทรงแว่นที่เหมาะกับรูปหน้า
4. ถ้าลูกค้าถามสายตา → ถามค่าสายตาเพื่อแนะนำเลนส์ที่ถูกต้อง
5. ถ้า Hot lead → แนะนำให้สั่งทันที มีโปรหรือสต๊อกจำกัด
6. ถ้าลังเล → ช่วยตัดสินใจด้วยข้อดีของสินค้า ไม่ใช่กดดัน
7. ถ้าคอมเม้นต์ → ตอบสั้นๆ และ DM เพื่อรายละเอียด

สินค้าหลัก:
- Blue Block: กรอบเท่ เลนส์กรองแสง ราคา 590-890 บาท เหมาะมนุษย์หน้าจอ
- โปรเกรสซีฟ: เลนส์หลายระยะ สำหรับสายตายาว+สั้น 1,200-2,500 บาท
- Bolon: แบรนด์พรีเมียม กรอบดีไซน์ 1,500-3,500 บาท
- Auto Lens: เปลี่ยนสีอัตโนมัติ ใส่ทั้งใน-นอก 1,500-2,500 บาท
- Mira/Aurora: แฟชั่น สวยงาม 790-1,500 บาท"""

COMMENT_SYSTEM_PROMPT = f"""คุณคือ AI Sales ของ {BRAND_NAME} ตอบคอมเม้นต์

กฎ:
1. ตอบสั้น 1-2 ประโยค
2. ต้องแนะนำให้ส่ง DM เสมอเพื่อรับข้อมูลเพิ่มเติม
3. ใช้ emoji เพิ่มความน่าสนใจ
4. ห้ามบอกราคาในคอมเม้นต์ ให้ DM แทน"""


async def generate_sales_response(
    customer: dict,
    message: str,
    intent: str,
    customer_need: str,
    key_concern: str,
    product_interest: str,
    history: list,
    is_comment: bool,
    client,
) -> str:
    """Generate contextual sales response"""

    system = COMMENT_SYSTEM_PROMPT if is_comment else SYSTEM_PROMPT

    # Build conversation history for Claude
    claude_messages = []

    # Add recent history as context
    for h in history[-6:]:
        role = "user" if h["direction"] == "in" else "assistant"
        claude_messages.append({"role": role, "content": h["content"]})

    # Ensure last message is from user
    if not claude_messages or claude_messages[-1]["role"] != "user":
        claude_messages.append({"role": "user", "content": message})
    elif claude_messages[-1]["content"] != message:
        claude_messages.append({"role": "user", "content": message})

    # Add context prefix for AI
    context_note = _build_context_note(intent, customer_need, key_concern, product_interest, customer, is_comment)
    if context_note:
        # Inject as system addendum (appended to system prompt)
        system = f"{system}\n\n[CONTEXT สำหรับการตอบครั้งนี้]\n{context_note}"

    try:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=system,
            messages=claude_messages,
        )
        return response.content[0].text.strip()

    except Exception as e:
        log.error(f"Responder error: {e}")
        return "ขอโทษนะคะ รอสักครู่แล้วลองใหม่อีกทีนะคะ 🙏"


def _build_context_note(
    intent: str,
    customer_need: str,
    key_concern: str,
    product_interest: str,
    customer: dict,
    is_comment: bool,
) -> str:
    """Build context injection for the responder"""
    parts = []

    if customer_need:
        parts.append(f"ความต้องการลูกค้า: {customer_need}")

    if key_concern:
        parts.append(f"ข้อกังวลหลัก: {key_concern}")

    if product_interest:
        parts.append(f"สินค้าที่น่าแนะนำ: {product_interest}")

    if intent == "hot":
        parts.append("⚡ HOT LEAD — ช่วยปิดการขายทันที แนะนำให้สั่งซื้อ")
    elif intent == "warm":
        parts.append("💛 WARM LEAD — สร้างความมั่นใจ ช่วยตัดสินใจ")
    elif intent == "info":
        parts.append("ℹ️ INFO — ให้ข้อมูลที่เป็นประโยชน์ พาไปสู่การสนใจสินค้า")
    elif intent == "support":
        parts.append("🔧 SUPPORT — ให้ความช่วยเหลืออย่างเต็มที่ สร้างความพึงพอใจ")

    if customer.get("total_purchases", 0) > 0:
        parts.append(f"ลูกค้าเก่า ซื้อมาแล้ว {customer['total_purchases']} ครั้ง — ให้ความพิเศษ")

    if is_comment:
        parts.append("นี่คือคอมเม้นต์ ตอบสั้น + แนะนำ DM")

    return "\n".join(parts)
