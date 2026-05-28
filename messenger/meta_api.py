"""
BoxBox AI — Meta Graph API Client
Sends messages via: FB Messenger, IG DM, FB/IG Comments
"""
import logging
import httpx
from config import META_PAGE_ACCESS_TOKEN, META_GRAPH_URL

log = logging.getLogger("boxbox.meta")


async def send_messenger_reply(recipient_id: str, text: str) -> bool:
    """Send a Facebook Messenger message"""
    url = f"{META_GRAPH_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }
    return await _post(url, payload)


async def send_ig_reply(recipient_id: str, text: str) -> bool:
    """Send an Instagram DM"""
    url = f"{META_GRAPH_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
    }
    return await _post(url, payload)


async def send_comment_reply(comment_id: str, text: str, platform: str = "facebook") -> bool:
    """Reply to a FB or IG comment"""
    url = f"{META_GRAPH_URL}/{comment_id}/comments"
    payload = {"message": text}
    return await _post(url, payload)


async def send_messenger_image(recipient_id: str, image_url: str) -> bool:
    """Send an image attachment via Messenger"""
    url = f"{META_GRAPH_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {"url": image_url, "is_reusable": True},
            }
        },
    }
    return await _post(url, payload)


async def send_quick_replies(recipient_id: str, text: str, options: list[str]) -> bool:
    """Send message with quick reply buttons (max 13)"""
    url = f"{META_GRAPH_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "text": text,
            "quick_replies": [
                {"content_type": "text", "title": opt, "payload": f"QR_{opt.upper()}"}
                for opt in options[:13]
            ],
        },
    }
    return await _post(url, payload)


async def get_user_profile(user_id: str) -> dict:
    """Fetch Meta user profile (name, picture)"""
    url = f"{META_GRAPH_URL}/{user_id}"
    params = {
        "fields": "name,first_name,profile_pic",
        "access_token": META_PAGE_ACCESS_TOKEN,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        log.warning(f"Profile fetch error for {user_id}: {e}")
    return {}


# ─── Internal HTTP Helper ─────────────────────────────────────────────────────
async def _post(url: str, payload: dict) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json=payload,
                params={"access_token": META_PAGE_ACCESS_TOKEN},
            )
            if resp.status_code == 200:
                return True
            log.error(f"Meta API error {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        log.error(f"Meta API request failed: {e}")
        return False
