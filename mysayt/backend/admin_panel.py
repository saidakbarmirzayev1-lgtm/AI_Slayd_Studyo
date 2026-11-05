"""
Admin panel yordamchilari (bot + sayt).
.env:
  ADMIN_TELEGRAM_IDS=123456789,987654321
  ADMIN_EMAILS=admin@example.com
  AD_ENABLED=1
  AD_TITLE=Slide Studio AI
  AD_TEXT=Professional slaydlar — Slide Studio AI
  AD_URL=https://t.me/your_bot
  AD_BUTTON=Botga o'tish
"""
from __future__ import annotations
import os
import re
from typing import Any, Dict, List, Optional, Set

# PRO uchun beriladigan "cheksiz" varaqlar (tez-varaq hisobida)
PRO_PAGES = 999_999


def _split_ids(raw: str) -> Set[str]:
    out: Set[str] = set()
    for part in re.split(r"[,;\s]+", raw or ""):
        p = part.strip()
        if p:
            out.add(p.lower() if "@" in p or not p.lstrip("-").isdigit() else p)
    return out


def admin_telegram_ids() -> Set[int]:
    ids: Set[int] = set()
    for p in _split_ids(os.getenv("ADMIN_TELEGRAM_IDS", "") or os.getenv("ADMIN_IDS", "")):
        try:
            ids.add(int(p))
        except ValueError:
            pass
    return ids


def admin_emails() -> Set[str]:
    return {e for e in _split_ids(os.getenv("ADMIN_EMAILS", "")) if "@" in e}


def is_admin_tg(tg_id: Any) -> bool:
    try:
        return int(tg_id) in admin_telegram_ids()
    except Exception:
        return False


def is_admin_email(email: str) -> bool:
    e = (email or "").strip().lower()
    return bool(e) and e in admin_emails()


def is_admin(tg_id: Any = None, email: str = "") -> bool:
    return is_admin_tg(tg_id) or is_admin_email(email)


def ad_config() -> Dict[str, Any]:
    enabled = (os.getenv("AD_ENABLED", "1") or "1").strip().lower() not in ("0", "false", "no", "off")
    return {
        "enabled": enabled,
        "title": (os.getenv("AD_TITLE") or "Slide Studio AI").strip()[:80],
        "text": (os.getenv("AD_TEXT") or "Professional slaydlar — Slide Studio AI orqali yarating").strip()[:300],
        "url": (os.getenv("AD_URL") or "").strip()[:500],
        "button": (os.getenv("AD_BUTTON") or "Batafsil").strip()[:40],
    }


def user_is_pro(user: dict) -> bool:
    """PRO: DB flag yoki juda katta paid balans yoki admin."""
    if not user:
        return False
    if user.get("is_pro") is True or str(user.get("is_pro")).lower() in ("1", "true", "yes"):
        return True
    if user.get("unlimited") is True:
        return True
    try:
        if int(user.get("paid_credits") or 0) >= PRO_PAGES * 10:  # taxminan cheksiz
            return True
    except Exception:
        pass
    return False


def should_show_ads(user: dict, tg_id: Any = None, email: str = "") -> bool:
    if is_admin(tg_id, email):
        return False
    if user_is_pro(user):
        return False
    return ad_config().get("enabled", True)


def make_ad_slide(lang: str = "uz") -> dict:
    cfg = ad_config()
    title = cfg["title"] or "Slide Studio AI"
    text = cfg["text"] or ""
    return {
        "layout": "closing",
        "title": title,
        "subtitle": text,
        "notes": "",
        "image": "",
        "_ad": True,
        "_ad_url": cfg.get("url") or "",
        "_ad_button": cfg.get("button") or "Batafsil",
    }
