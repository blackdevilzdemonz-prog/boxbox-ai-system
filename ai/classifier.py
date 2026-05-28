"""
BoxBox AI — Stage 2: Intent Classifier
Classifies customer messages as: hot / warm / info / support / spam
Returns structured JSON for downstream pipeline stages
"""
import json
import logging
from config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS, PRODUCTS

log = logging.getLogger("boxbox.classifier")

SYSTEM_PROMPT = """คุณเป็น Intent Classifier ของ BoxBoxGlasses

วิเคราะห์ข้อความลูกค้าและตอบกลับเป็น JSON เท่านั้น ห้ามตอบข้อความอื่น

ประเภท intent:
- hot: ลูกค้าพร้อมซื้อ / ถามราคา / ถามสต๊อก / บอกว่าต้องการซื้อ
- warm: ลูกค้าสนใจแต่ยังลังเล / ถามรายละเอียด / เปรียบเทียบสินค้า
- info: ถามข้อมูลทั่วไป / ถามเรื่องสายตา / ถามวิธีการสั่ง
- support: ปัญหาหลังซื้อ / ถามเรื่องส่ง / ต้องการเปลี่ยน/คืน
- spam: โฆษณา / ไม่เกี่ยวกับแว่น / ข้อความไม่มีความหมาย

ตอบกลับ JSON format นี้เท่านั้น:
{
  "intent": "hot|warm|info|support|spam",
  "confidence": 0.0-1.0,
  "signals": ["list", "of", "signals"],
  "customer_need": "สิ่งที่ลูกค้าต้องการ (ภาษาไทย)",
  "recommended_products": ["product1", "product2"],
  "key_concern": "ข้อกังวลหลัก (ภาษาไทย) หรือ null",
  "response_strategy": "วิธีตอบที่ดีที่สุด (ภาษาไทย)"
}"""


async def classify_intent(
    message: str,
    history: list,
    customer: dict,
    client,
) -> dict:
    """Classify customer message intent using Claude"""

    # Build context from history
    history_text = ""
    if history:
        last_msgs = history[-5:]  # last 5 messages for context
        history_text = "\n".join(
            f"{'ลูกค้า' if m['direction'] == 'in' else 'บอท'}: {m['content'][:100]}"
            for m in last_msgs
        )

    product_list = ", ".join(p["name"] for p in PRODUCTS)
    customer_context = (
        f"สินค้าที่สนใจก่อนหน้า: {customer.get('product_interest', 'ไม่ทราบ')}\n"
        f"Stage ปัจจุบัน: {customer.get('lead_stage', 'new_lead')}\n"
        f"ซื้อไปแล้ว: {customer.get('total_purchases', 0)} ครั้ง"
    )

    user_prompt = f"""สินค้าของเรา: {product_list}

ข้อมูลลูกค้า:
{customer_context}

ประวัติการสนทนา:
{history_text}

ข้อความล่าสุดของลูกค้า:
"{message}"

วิเคราะห์ intent และตอบ JSON:"""

    try:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text.strip()

        # Extract JSON (handle markdown code blocks)
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()

        result = json.loads(text)
        return result

    except (json.JSONDecodeError, Exception) as e:
        log.warning(f"Classifier error: {e} | Falling back to 'warm'")
        return {
            "intent": "warm",
            "confidence": 0.5,
            "signals": [],
            "customer_need": "ไม่สามารถวิเคราะห์ได้",
            "recommended_products": [],
            "key_concern": None,
            "response_strategy": "ตอบข้อมูลทั่วไปและถามความต้องการ",
        }
