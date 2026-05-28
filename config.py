"""
BoxBox AI Sales System — Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Meta / Facebook ──────────────────────────────────────────────────────────
META_APP_SECRET        = os.getenv("META_APP_SECRET", "")
META_PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN", "")
META_VERIFY_TOKEN      = os.getenv("META_VERIFY_TOKEN", "boxbox_verify_2026")
META_API_VERSION       = "v19.0"
META_GRAPH_URL         = f"https://graph.facebook.com/{META_API_VERSION}"

# ─── Instagram ────────────────────────────────────────────────────────────────
IG_PAGE_ID             = os.getenv("IG_PAGE_ID", "")

# ─── Claude / Anthropic ───────────────────────────────────────────────────────
ANTHROPIC_API_KEY      = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL           = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS      = 1024

# ─── Database ─────────────────────────────────────────────────────────────────
DATABASE_URL           = os.getenv("DATABASE_URL", "sqlite:///./boxbox_crm.db")

# ─── Business Settings ────────────────────────────────────────────────────────
BRAND_NAME             = "BoxBoxGlasses"
FOLLOW_UP_DAYS         = [1, 3, 7]          # follow-up schedule after first contact
PROMO_INACTIVE_DAYS    = 3                   # days inactive → trigger promo
MAX_FOLLOW_UPS         = 3                   # max follow-up messages per lead
HUMAN_ESCALATION_PHRASES = [
    "โกรธ", "แย่มาก", "ไม่พอใจ", "ร้องเรียน", "ฟ้อง",
    "คืนเงิน", "คืนสินค้า", "เสีย", "พัง"
]

# ─── Product Catalog (quick reference for AI) ─────────────────────────────────
PRODUCTS = [
    {"name": "Blue Block", "price_range": "590-890", "type": "everyday"},
    {"name": "โปรเกรสซีฟ",  "price_range": "1,200-2,500", "type": "multi-focus"},
    {"name": "Bolon",       "price_range": "1,500-3,500", "type": "premium"},
    {"name": "Mira",        "price_range": "790-1,200",   "type": "fashion"},
    {"name": "Aurora",      "price_range": "890-1,500",   "type": "fashion"},
    {"name": "Cooper",      "price_range": "690-990",     "type": "everyday"},
    {"name": "Hikari",      "price_range": "590-890",     "type": "everyday"},
    {"name": "Mago",        "price_range": "1,200-2,000", "type": "premium"},
    {"name": "Pilot",       "price_range": "690-990",     "type": "sport"},
    {"name": "Auto Lens",   "price_range": "1,500-2,500", "type": "photochromic"},
]

# ─── LINE Messaging API ───────────────────────────────────────────────────────
LINE_CHANNEL_SECRET        = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN  = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_OWNER_USER_ID         = os.getenv("LINE_OWNER_USER_ID", "")   # เจ้าของร้าน LINE User ID
LINE_MESSAGING_API_URL     = "https://api.line.me/v2/bot/message"


# ─── Notification Thresholds ──────────────────────────────────────────────────
HOT_LEAD_NOTIFY_THRESHOLD  = 0.75    # confidence >= 75% → notify owner immediately
SALE_NOTIFY_MIN_AMOUNT     = 500     # baht — sales below this skip LINE notify
DAILY_DIGEST_HOUR          = 20      # 8 PM Bangkok time — daily LINE digest