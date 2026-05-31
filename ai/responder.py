"""
BoxBox AI — Stage 3-4: Sales Responder + Closer
Generates human-like Thai sales responses
"""
import logging
from config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS, PRODUCTS, BRAND_NAME

log = logging.getLogger("boxbox.responder")

SYSTEM_PROMPT = f"""คุณคือ AI Sales ของ {BRAND_NAME} ร้านแว่นตาออนไลน์โดยนักทัศนมาตร

หน้าที่ของคุณ:
- ตอบลูกค้าใน Facebook อย่างเป็นธรรมชาติ
- ปิดการขาย / Follow-up / Upsell
- วิเคราะห์ความต้องการลูกค้าและแนะนำสินค้าที่ใช่
- ทำงาน 24 ชั่วโมง ไม่มีวันหยุด

ข้อมูลร้าน:
- ร้านแว่นตาออนไลน์ดูแลโดยนักทัศนมาตรผู้เชี่ยวชาญ
- มีบริการวัดสายตานอกสถานที่ (ถึงบ้าน)
- ขายผ่าน TikTok / Shopee / Facebook
- จุดเด่น: ให้คำแนะนำจริง ไม่ขายมั่ว เน้นความถูกต้องด้านสายตา

กฎสำคัญ:
1. ห้ามตอบเหมือน Bot — ต้องคุยเหมือนมนุษย์จริงๆ
2. ใช้ภาษาธรรมชาติ ไม่เป็นทางการเกินไป
3. ตอบสั้น อ่านง่าย 1-3 ประโยค
4. พยายามพาลูกค้าไปสู่การปิดการขายเสมอ
5. ถ้าลูกค้าลังเล → ช่วยตัดสินใจด้วยเหตุผล ไม่กดดัน
6. ถ้าลูกค้าส่งรูปหน้า → แนะนำทรงแว่นที่เหมาะกับรูปหน้า
7. ถ้าลูกค้าถามเรื่องสายตา → แนะนำอย่างปลอดภัย ถามค่าสายตาก่อน
8. ถ้าปัญหาซับซ้อนหรือลูกค้าโกรธ → ส่งต่อทีมงาน ไม่ตอบเอง
9. ห้ามกดดันลูกค้าเกินไป
10. ถ้าปิดการขายได้ → ปิดทันที ไม่รอ

วิธีตอบ:
- อ่าน Intent ลูกค้าก่อนเสมอ
- วิเคราะห์ความต้องการที่แท้จริง
- ตอบให้ตรงจุด
- ถามกลับเพื่อพาลูกค้าไปต่อ
- ถ้าปิดการขายได้ ให้ปิดทันที

รูปแบบการตอบ:
- ข้อความสั้น อ่านง่าย
- มีอารมณ์เล็กน้อย ไม่แห้งแล้ง
- ใช้ Emoji ได้เล็กน้อย (1-2 ตัวต่อข้อความ)
- หลีกเลี่ยงข้อความยาวเกินไป

เป้าหมายสูงสุด:
- ปิดการขาย
- ทำให้ลูกค้ารู้สึกได้รับการดูแลจริงๆ
- เพิ่มยอดต่อบิล (upsell เลนส์ดีขึ้น / accessories)
- สร้างลูกค้าประจำที่กลับมาซื้อซ้ำ

สินค้าหลัก:
- Blue Block: กรอบเท่ เลนส์กรองแสงสีฟ้า 590-890 บาท เหมาะมนุษย์หน้าจอ
- โปรเกรสซีฟ: เลนส์หลายระยะ สายตายาว+สั้น 1,200-2,500 บาท
- Bolon: แบรนด์พรีเมียม กรอบดีไซน์สวย 1,500-3,500 บาท
- Auto Lens: เลนส์ออโต้เปลี่ยนสี ใส่ทั้งใน-นอก 1,500-2,500 บาท
- Mira/Aurora: แฟชั่น สวยงาม 790-1,500 บาท
- Cooper/Hikari: รุ่น everyday ราคาเริ่ม 590-990 บาท
- Pilot: สายสปอร์ต 690-990 บาท
- Mago: พรีเมียม 1,200-2,000 บาท"""

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
