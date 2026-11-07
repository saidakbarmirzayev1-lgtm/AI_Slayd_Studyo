"""
Slide Studio — Telegram bot (v45).  FastAPI ichida ishlaydi (aiogram shart emas: to'g'ridan-to'g'ri Bot API, kam RAM).

Oqim:
  1) Foydalanuvchi mavzuni yozadi (yoki «🎨 Yangi slayd yaratish») -> AI darhol slaydlarni yozadi -> PPTX + PDF + HTML birdan yuboriladi.
  2) Tayyor slaydni matn bilan tahrirlash: «3-slaydni qisqartir» — AI faqat kerakli slaydlarni o'zgartiradi (ops), yangi fayllar qaytariladi.
  3) Fayllar FAQAT RAM'da yasaladi, yuborilgach darhol tashlanadi. Bazada (Supabase) faqat foydalanuvchi, balans va qisqa slayd JSON.
  4) Bir baza: balans `user_usage` jadvalida — bot, Mini App va sayt bir xil raqamni ko'radi. Google akkaunt `/link KOD` bilan ulanadi.

Ulanish usullari (TELEGRAM_MODE):  auto (standart) | webhook | polling
Kerakli env:  TELEGRAM_BOT_TOKEN (majburiy), PUBLIC_BASE_URL (https://...), TELEGRAM_WEBHOOK_SECRET (ixtiyoriy)
Jadvallar: SUPABASE_TELEGRAM.sql
"""
from __future__ import annotations

import asyncio
import gc
import hashlib
import hmac
import html
import io
import json
import os
import re
import secrets
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, quote

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse, Response

try:
    from backend import tg_decks as decks
except Exception as _e:  # pragma: no cover
    decks = None
    print(f"[TG] tg_decks yuklanmadi (python-pptx / reportlab / pillow o'rnatilganmi?): {_e}")


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN").strip("\"'")
ENABLED = bool(BOT_TOKEN) and ":" in BOT_TOKEN
SITE_URL = (_env("PUBLIC_BASE_URL") or "https://ai-slaydstudyo.onrender.com").rstrip("/")
WEBHOOK_PATH = "/telegram-webhook"
MODE = (_env("TELEGRAM_MODE", "auto") or "auto").lower()
# Telegram secret_token faqat [A-Za-z0-9_-] (1..256) ni qabul qiladi. Render "generateValue" esa + / = belgili qiymat beradi
# -> setWebhook rad etilib, bot JIM qolardi. Shuning uchun har qanday kirish HEX ga aylantiriladi.
SECRET = hashlib.sha256(("ss-tg-secret|" + (_env("TELEGRAM_WEBHOOK_SECRET") or BOT_TOKEN)).encode()).hexdigest()[:48]
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
TG_EMAIL_DOMAIN = "t.me"
DEV_MODE = _env("SLIDE_STUDIO_DEV_MODE") == "1"

router = APIRouter()
_deps: Dict[str, Any] = {}


def configure(**kw: Any) -> None:
    """main.py dan bog'lanadi (supabase, kredit funksiyalari, AI sozlamalari)."""
    _deps.update(kw)


# ----------------------------------------------------------------------------------------------
# Yordamchilar: log (kam), HTTP klient, Telegram API
# ----------------------------------------------------------------------------------------------
_warned: "OrderedDict[str, float]" = OrderedDict()


def _warn(key: str, msg: str) -> None:
    now = time.time()
    if now - _warned.get(key, 0) < 60:
        return
    _warned[key] = now
    while len(_warned) > 100:
        _warned.popitem(last=False)
    print(f"[TG] {msg}"[:400])


_client: Optional[httpx.AsyncClient] = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=6.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=4, keepalive_expiry=30),
        )
    return _client


async def tg(method: str, **payload: Any) -> Optional[Any]:
    """Telegram Bot API chaqiruvi. Xato bo'lsa None (exception ko'tarmaydi)."""
    if not ENABLED:
        return None
    for attempt in range(2):
        try:
            r = await _http().post(f"{API}/{method}", json=payload)
            data = r.json()
            if data.get("ok"):
                return data.get("result", True)
            if r.status_code == 429 and attempt == 0:
                wait = int((data.get("parameters") or {}).get("retry_after", 1))
                await asyncio.sleep(min(max(wait, 1), 5))
                continue
            desc = str(data.get("description", ""))
            if not any(x in desc.lower() for x in ("blocked", "chat not found", "deactivated", "message is not modified", "query is too old")):
                _warn(f"api:{method}", f"{method}: {desc}")
            return None
        except Exception as e:
            if attempt == 1:
                _warn(f"net:{method}", f"{method} tarmoq xatosi: {type(e).__name__}")
            else:
                await asyncio.sleep(0.6)
    return None


async def tg_send_document(chat_id: int, filename: str, data: bytes, mime: str, caption: str = "") -> bool:
    if not ENABLED:
        return False
    for attempt in range(2):
        try:
            r = await _http().post(
                f"{API}/sendDocument",
                data={"chat_id": str(chat_id), "caption": caption[:900], "parse_mode": "HTML"},
                files={"document": (filename, data, mime.split(";")[0])},
                timeout=httpx.Timeout(90.0, connect=8.0),
            )
            j = r.json()
            if j.get("ok"):
                return True
            _warn("doc", f"sendDocument: {str(j.get('description'))[:150]}")
            if r.status_code != 429:
                return False
            await asyncio.sleep(min(int((j.get("parameters") or {}).get("retry_after", 2)), 6))
        except Exception as e:
            _warn("doc-net", f"sendDocument tarmoq xatosi: {type(e).__name__}")
            await asyncio.sleep(1)
    return False


def esc(s: Any) -> str:
    return html.escape(str(s or ""), quote=False)


# ----------------------------------------------------------------------------------------------
# Matnlar
# ----------------------------------------------------------------------------------------------
BTN_NEW = "🎨 Yangi slayd"
BTN_MY = "📂 Slaydlarim"
BTN_BAL = "💳 Balans"
BTN_SITE = "🌐 Saytga o'tish"
BTN_SET = "⚙️ Sozlamalar"
BTN_ABOUT = "ℹ️ Yordam"
MENU = {BTN_NEW: "new", BTN_MY: "my", BTN_BAL: "bal", BTN_SITE: "site", BTN_SET: "set", BTN_ABOUT: "about",
        # eski klaviaturalar foydalanuvchilarda turgan bo'lishi mumkin (Pro tugmasi endi balansga olib boradi):
        "👑 Pro": "bal", "🎨 Yangi slayd yaratish": "new", "📂 Slaydlarim / Tozalash": "my", "💳 Balans / To'ldirish": "bal", "ℹ️ Bot haqida": "about"}
LINE = "━━━━━━━━━━━━━━━━━━"
DEFAULT_SLIDES = 8

HELP = (
    "<b>Qanday ishlaydi</b>\n"
    "1. Mavzuni yozing — bot slayd tayyorlaydi (PPTX, PDF, HTML).\n"
    "2. Tahrirlash uchun oddiy yozing: <i>«3-slaydni qisqartir»</i>.\n"
    "3. 1 slayd = 1 varaq. Varaq tugasa — «💳 Balans» orqali sotib oling.\n\n"
    "<b>Buyruqlar</b>\n"
    "/new — yangi slayd\n"
    "/my — slaydlarim\n"
    "/credits — balans\n"
    "/buy — varaq sotib olish\n"
    "/settings — Google akkaunt\n"
    "/id — Telegram ID"
)
ABOUT = HELP
GREETING_RE = re.compile(r"^(salom|assalomu\s*alaykum|assalom|hello|hi|hey|привет|здравствуй\w*|qalay|nima gap|start|boshla)[\s!.,?]*$", re.I)
COUNT_RE = re.compile(r"(\d{1,2})\s*(?:ta|tadan|ta\.)?\s*[-–]?\s*(?:slayd\w*|slaid\w*|slide\w*|слайд\w*|varaq\w*|sahifa\w*|page\w*)", re.I)
MIN_SLIDES, MAX_SLIDES = 3, 20


def _app_url(topic: str = "") -> str:
    if topic:
        return f"{SITE_URL}/?src=tg&topic={quote(topic[:200], safe='')}"
    return f"{SITE_URL}/?src=tg"


def _btn(text: str, data: str) -> dict:
    return {"text": text, "callback_data": data}


def _https() -> bool:
    return SITE_URL.startswith("https://") and "localhost" not in SITE_URL and "127.0.0.1" not in SITE_URL


def kb_reply() -> dict:
    """Doimiy pastki menyu: 2 ustunli, tartibli (v47)."""
    last = [{"text": "🚀 Muharrir", "web_app": {"url": _app_url()}}] if _https() else [{"text": BTN_SITE}]
    return {
        "keyboard": [[{"text": BTN_NEW}, {"text": BTN_MY}], [{"text": BTN_BAL}, {"text": BTN_SET}], [{"text": BTN_ABOUT}] + last],
        "resize_keyboard": True, "is_persistent": True, "input_field_placeholder": "Slayd mavzusini yozing…",
    }


def kb_main(topic: str = "") -> dict:
    rows = []
    if _https():
        rows.append([{"text": "🚀 Muharrirda ochish", "web_app": {"url": _app_url(topic)}}])
    rows.append([_btn("💳 Balans", "bal")])
    return {"inline_keyboard": rows}


def kb_count(mode: str) -> dict:
    return {"inline_keyboard": [
        [_btn("5 slayd", "cnt:5"), _btn("8 slayd", "cnt:8"), _btn("10 slayd", "cnt:10"), _btn("12 slayd", "cnt:12")],
        [_btn(("✅ " if mode == "fast" else "") + "⚡ Tez AI", "mode:fast"), _btn(("✅ " if mode == "deep" else "") + "🧠 Chuqur AI", "mode:deep")],
    ]}


def _editor_url(st: dict) -> str:
    """Mini App / brauzer havolasi: shu slaydning o'zini muharrirga ochadi (token bilan; fayl serverda saqlanmaydi)."""
    did, cid = st.get("deck_id"), st.get("cid")
    if did and cid:
        return f"{SITE_URL}/?src=tg&tgdeck={_make_token('D', did, cid, 3 * 86400)}"
    return _app_url(st.get("topic") or "")


def kb_done(arg: Any = "") -> dict:
    st = arg if isinstance(arg, dict) else {"topic": arg}
    url = _editor_url(st)
    return {"inline_keyboard": [
        [_btn("📊 PPTX", "dl:pptx"), _btn("📕 PDF", "dl:pdf"), _btn("🌐 HTML", "dl:html")],
        [_btn("📦 Hammasi — 3 ta fayl birdan", "dl:all")],
        [_btn("✏️ Tahrirlash", "edit"), _btn("🎨 Rang", "theme")],
        [_btn("🆕 Yangi slayd", "new"), _btn("📂 Slaydlarim", "my")],
        [{"text": "🚀 Muharrirda ochish", "web_app": {"url": url}}, {"text": "🌐 Brauzerda", "url": url}],
    ]}


def kb_themes() -> dict:
    names = list(decks.THEMES.keys()) if decks else []
    rows, row = [], []
    for k in names:
        row.append(_btn(decks.THEMES[k]["label"], f"th:{k}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([_btn("⬅️ Orqaga", "back")])
    return {"inline_keyboard": rows}


def kb_balance(linked: bool, info: Optional[dict] = None) -> dict:
    info = info or {}
    rows = []
    if not info.get("unlimited"):
        rows.append([_btn("➕ Varaq sotib olish", "buy")])
    if not linked:
        rows.append([_btn("🔗 Google ulash", "linkinfo")])
    return {"inline_keyboard": rows or [[_btn("⬅️ Menyu", "dismiss")]]}


# ----------------------------------------------------------------------------------------------
# Himoya: dublikat update va spam (xotirasi chegaralangan)
# ----------------------------------------------------------------------------------------------
_seen: "OrderedDict[int, float]" = OrderedDict()
_rl: "OrderedDict[int, list]" = OrderedDict()
RL_MAX, RL_WINDOW = 8, 10.0


def _is_dup(update_id: Any) -> bool:
    if not isinstance(update_id, int):
        return False
    if update_id in _seen:
        return True
    _seen[update_id] = time.time()
    while len(_seen) > 1000:
        _seen.popitem(last=False)
    return False


def _limited(chat_id: int, mx: int = RL_MAX) -> bool:
    now = time.time()
    arr = [t for t in _rl.pop(chat_id, []) if now - t < RL_WINDOW]
    over = len(arr) >= mx
    if not over:
        arr.append(now)
    _rl[chat_id] = arr
    while len(_rl) > 5000:
        _rl.popitem(last=False)
    return over


# ----------------------------------------------------------------------------------------------
# Foydalanuvchi holati (RAM, chegaralangan, 3 soatdan keyin o'chadi)
# ----------------------------------------------------------------------------------------------
_chats: "OrderedDict[int, dict]" = OrderedDict()
MAX_CHATS, CHAT_TTL = 300, 3 * 3600


IMG_TTL = 600
_last_sweep = 0.0


def _sweep_imgs(now: float) -> None:
    """Fayl yuborilmay qolgan rasmlar 10 daqiqadan keyin RAM'dan tashlanadi (xotira o'smasin)."""
    global _last_sweep
    if now - _last_sweep < 60:
        return
    _last_sweep = now
    for v in _chats.values():
        if v.get("imgs") and now - v.get("img_ts", 0) > IMG_TTL and not v.get("busy") and not v.get("sending"):
            v["imgs"] = {}


def _state(chat_id: int) -> dict:
    now = time.time()
    _sweep_imgs(now)
    st = _chats.pop(chat_id, None)
    if st is None or now - st.get("ts", 0) > CHAT_TTL:
        st = {"mode": (st or {}).get("mode", "fast"), "busy": False}
    st["ts"] = now
    st["cid"] = chat_id
    _chats[chat_id] = st
    while len(_chats) > MAX_CHATS:
        k, v = next(iter(_chats.items()))
        if v.get("busy"):
            _chats.move_to_end(k)
            break
        _chats.popitem(last=False)
    return st


# ----------------------------------------------------------------------------------------------
# Akkaunt va kreditlar (Telegram ID -> Supabase akkaunt tg<ID>@t.me; Mini App bilan BIR XIL)
# ----------------------------------------------------------------------------------------------
def _tg_email(tg_id: int) -> str:
    return f"tg{int(tg_id)}@{TG_EMAIL_DOMAIN}"


def _sb():
    return (_deps.get("supabase_getter") or (lambda: None))()


def _provision_sync(user: dict) -> dict:
    """Supabase akkauntini yaratadi/topadi va kredit qatorini ta'minlaydi. {'uid','email','name','hashed'} yoki {'error'}."""
    sb = _sb()
    tid = int(user["id"])
    email = _tg_email(tid)
    name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x)[:80]
    if not sb:
        if DEV_MODE:
            return {"uid": f"dev-tg{tid}", "email": email, "name": name, "hashed": None}
        return {"error": "auth_unavailable"}
    admin = sb.auth.admin
    try:
        admin.create_user({
            "email": email,
            "email_confirm": True,
            "app_metadata": {"provider": "telegram", "telegram_id": tid},
            "user_metadata": {"full_name": name, "telegram_username": user.get("username") or ""},
        })
    except Exception as e:
        m = str(e).lower()
        if not any(x in m for x in ("already", "registered", "exists", "duplicate")):
            _warn("create_user", f"create_user: {str(e)[:150]}")
    link = admin.generate_link({"type": "magiclink", "email": email})
    props = getattr(link, "properties", None)
    hashed = getattr(props, "hashed_token", None)
    u = getattr(link, "user", None)
    if not hashed or not u:
        return {"error": "link_failed"}
    meta = getattr(u, "app_metadata", None) or {}
    if str(meta.get("telegram_id")) != str(tid):   # begona (oldindan ro'yxatdan o'tkazilgan) akkauntdan himoya
        return {"error": "account_conflict"}
    get_usage = _deps.get("get_usage")
    if get_usage:
        try:
            get_usage(str(u.id), email)          # kredit qatori darhol yaratiladi
        except Exception as e:
            _warn("usage_row", f"usage yaratilmadi: {str(e)[:120]}")
    return {"uid": str(u.id), "email": email, "name": name, "hashed": hashed}


_uids: "OrderedDict[int, Tuple[str, str]]" = OrderedDict()      # tg_id -> (uid, email)


def _linked_sync(tid: int) -> Optional[Tuple[str, str]]:
    """Telegram ID sayt (Google) akkauntiga ulangan bo'lsa (uid, email), aks holda None."""
    sb = _sb()
    if not sb:
        return None
    try:
        res = sb.table("tg_links").select("user_id,email").eq("tg_id", int(tid)).limit(1).execute()
        if res.data:
            return str(res.data[0]["user_id"]), str(res.data[0]["email"])
    except Exception as e:
        _warn("links", f"tg_links o'qilmadi (SUPABASE_TELEGRAM.sql ishga tushirilganmi?): {str(e)[:100]}")
    return None


def _ensure_uid_sync(user: dict) -> Tuple[str, str]:
    """(uid, email). Avval ulangan sayt akkaunti, bo'lmasa tg<ID>@t.me akkaunti (Mini App bilan bir xil)."""
    tid = int(user["id"])
    if tid in _uids:
        return _uids[tid]
    res = _linked_sync(tid)
    if not res:
        email = _tg_email(tid)
        sb = _sb()
        uid = ""
        if sb:
            q = sb.table("user_usage").select("user_id").eq("email", email).limit(1).execute()
            if q.data:
                uid = str(q.data[0]["user_id"])
        if not uid:
            r = _provision_sync(user)
            if r.get("error"):
                raise RuntimeError(r["error"])
            uid = r["uid"]
        res = (uid, email)
    _uids[tid] = res
    while len(_uids) > 5000:
        _uids.popitem(last=False)
    return res


async def _ensure_uid(user: dict) -> Tuple[str, str]:
    return await asyncio.to_thread(_ensure_uid_sync, user)


_ulocks: Dict[str, asyncio.Lock] = {}


def _ulock(uid: str) -> asyncio.Lock:
    lk = _ulocks.get(uid)
    if lk is None:
        if len(_ulocks) > 3000:
            _ulocks.clear()
        lk = _ulocks[uid] = asyncio.Lock()
    return lk


def _usage_now_sync(uid: str, email: str) -> dict:
    return _deps["apply_reset"](_deps["get_usage"](uid, email))


def _page_units(mode: str) -> int:
    return int(_deps["MODES"][mode if mode in _deps["MODES"] else "fast"]["page"])


def _pages_left(usage: dict, mode: str) -> float:
    return _deps["total_credits"](usage) / _page_units(mode)


def _fmt_pages(x: float) -> str:
    if float(x) >= 999999:
        return "∞"
    x = round(float(x), 2)
    return str(int(x)) if x == int(x) else f"{x:.2f}".rstrip("0").rstrip(".")


def _fmt_wait(sec: Any) -> str:
    try:
        sec = int(sec)
    except Exception:
        return ""
    if sec <= 0:
        return ""
    h, m = sec // 3600, (sec % 3600) // 60
    return f"{h} soat {m} daqiqa" if h else f"{m} daqiqa"


async def _balance_info(user: dict) -> Optional[dict]:
    """Bazadan HAR SAFAR yangi o'qiladi (keshlanmaydi) — sayt va bot bir xil raqamni ko'radi."""
    try:
        uid, email = await _ensure_uid(user)
        u = await asyncio.to_thread(_usage_now_sync, uid, email)
        p = _deps["usage_payload"](u)
    except Exception as e:
        _warn("credits", f"kredit o'qish xatosi: {str(e)[:120]}")
        return None
    m = p.get("modes") or {}
    fast, deep = m.get("fast") or {}, m.get("deep") or {}
    until = ""
    try:
        if p.get("plan_until"):
            d = datetime.fromisoformat(str(p["plan_until"]).replace("Z", "+00:00"))
            until = d.strftime("%d.%m.%Y")
    except Exception:
        pass
    return {
        "free": fast.get("free_pages", 0), "paid": fast.get("paid_pages", 0),
        "fast": fast.get("pages_exact", 0), "deep": deep.get("pages_exact", 0),
        "daily": fast.get("free_daily_pages", 0),
        "wait": _fmt_wait(p.get("next_reset_in_seconds")) if p.get("window_started") else "",
        "linked": email != _tg_email(int(user["id"])), "email": email,
        "plan": p.get("plan", "free"), "until": until, "unlimited": bool(p.get("unlimited")), "ad_free": bool(p.get("ad_free")),
        "pro_price": p.get("pro_price_usd"), "pro_days": p.get("pro_days"), "pro_daily": (p.get("plans") or [{}, {}])[1].get("pages") if len(p.get("plans") or []) > 1 else None,
    }


def _mask_email(e: str) -> str:
    a, _, d = (e or "").partition("@")
    return (a[:1] + "***@" + d) if d else "***"


def _bar(frac: float, n: int = 10) -> str:
    frac = max(0.0, min(1.0, float(frac)))
    k = int(round(frac * n))
    return "▰" * k + "▱" * (n - k)


def _balance_block(i: dict) -> str:
    if i.get("unlimited"):
        return "♾ Varaqlar: <b>cheksiz</b>"
    daily = float(i.get("daily") or 0)
    lines = [f"💎 Varaqlar: <b>{_fmt_pages(float(i['free']) + float(i['paid']))}</b>"]
    if daily:
        lines.append(f"🎁 Shundan bugungi bepul: <b>{_fmt_pages(i['free'])}</b>/{_fmt_pages(daily)}")
    if i.get("wait"):
        lines.append(f"🔄 Bepul varaqlar <b>{i['wait']}</b> dan keyin yangilanadi")
    return "\n".join(lines)


def _welcome_text(name: str, info: Optional[dict]) -> str:
    hello = f"👋 <b>Salom, {esc(name)}!</b>" if name else "👋 <b>Salom!</b>"
    bal = ("\n\n" + _balance_block(info)) if info else ""
    return f"{hello}\nMavzuni yozing — slayd tayyorlab beraman.{bal}"


async def _credits_text(user: dict) -> str:
    i = await _balance_info(user)
    if not i:
        return "⚠️ Hozir balansni o'qib bo'lmadi. Birozdan keyin qayta urinib ko'ring."
    return f"💳 <b>Balans</b>\n{_balance_block(i)}\n\n<i>1 slayd = 1 varaq</i>"


async def _charge(uid: str, email: str, pages: int, tokens: int, mode: str, details: dict) -> Tuple[dict, int]:
    """Slaydlar uchun yechadi (pages=0 bo'lsa — oddiy chat narxi). (usage, yechilgan_birlik)."""
    async with _ulock(uid):
        usage = await asyncio.to_thread(_usage_now_sync, uid, email)
        usage["total_tokens"] = (usage.get("total_tokens") or 0) + tokens
        usage["daily_tokens"] = (usage.get("daily_tokens") or 0) + tokens
        usage, charged, reason = _deps["charge"](usage, int(pages), 0, mode)
        await asyncio.to_thread(_deps["save_usage"], uid, usage, 0)
        if int(charged) > 0:
            await asyncio.to_thread(_deps["ledger_log"], uid, "tg_" + str(reason), -int(charged), usage, 0, details)
        return usage, int(charged)


# ----------------------------------------------------------------------------------------------
# Supabase: faqat MA'LUMOT (qisqa slayd JSON, ulanish). Fayllar (PPTX/PDF/HTML) HECH QACHON saqlanmaydi.
# Jadvallar: SUPABASE_TELEGRAM.sql. Jadval yo'q bo'lsa bot baribir ishlaydi (faqat RAM, restartda tarix yo'qoladi).
# ----------------------------------------------------------------------------------------------
MAX_SAVED = 5
LINK_TTL = 600


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_uuid(v: Any) -> Optional[str]:
    try:
        return str(uuid.UUID(str(v)))
    except Exception:
        return None


def _sign(p: str) -> str:
    return hmac.new(SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()[:20]


def _make_token(kind: str, a: int, b: int, ttl: int) -> str:
    p = f"{kind}.{int(a)}.{int(b)}.{int(time.time()) + int(ttl)}"
    return f"{p}.{_sign(p)}"


def _check_token(kind: str, tok: str) -> Optional[Tuple[int, int]]:
    try:
        k, a, b, exp, sig = str(tok or "").split(".")
        if k != kind or not hmac.compare_digest(sig, _sign(f"{k}.{a}.{b}.{exp}")) or int(exp) < time.time():
            return None
        return int(a), int(b)
    except Exception:
        return None


def _db_warn(e: Exception) -> None:
    _warn("db", f"Supabase jadval xatosi (SUPABASE_TELEGRAM.sql ishga tushirilganmi?): {str(e)[:120]}")


def _deck_insert_sync(tid: int, uid: str, deck: dict, topic: str, lang: str) -> Optional[int]:
    sb = _sb()
    if not sb:
        return None
    try:
        r = sb.table("tg_decks").insert({
            "tg_id": int(tid), "user_id": _as_uuid(uid), "title": str(deck.get("title") or "")[:120],
            "topic": (topic or "")[:300], "lang": lang or "uz", "deck": deck,
        }).execute()
        new_id = r.data[0]["id"] if r.data else None
        rows = sb.table("tg_decks").select("id").eq("tg_id", int(tid)).order("updated_at", desc=True).limit(60).execute().data or []
        old = [x["id"] for x in rows[MAX_SAVED:]]
        if old:
            sb.table("tg_decks").delete().in_("id", old).execute()
        return new_id
    except Exception as e:
        _db_warn(e)
        return None


def _deck_update_sync(deck_id: int, tid: int, deck: dict) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        sb.table("tg_decks").update({"deck": deck, "title": str(deck.get("title") or "")[:120], "updated_at": _now_iso()}) \
            .eq("id", int(deck_id)).eq("tg_id", int(tid)).execute()
        return True
    except Exception as e:
        _db_warn(e)
        return False


def _deck_list_sync(tid: int) -> List[dict]:
    sb = _sb()
    if not sb:
        return []
    try:
        return sb.table("tg_decks").select("id,title,updated_at").eq("tg_id", int(tid)).order("updated_at", desc=True).limit(MAX_SAVED).execute().data or []
    except Exception as e:
        _db_warn(e)
        return []


def _deck_get_sync(tid: int, deck_id: Optional[int] = None) -> Optional[dict]:
    sb = _sb()
    if not sb:
        return None
    try:
        q = sb.table("tg_decks").select("id,title,topic,lang,deck").eq("tg_id", int(tid))      # tg_id sharti: begona slaydni ochib bo'lmaydi
        q = q.eq("id", int(deck_id)) if deck_id else q.order("updated_at", desc=True).limit(1)
        rows = q.execute().data or []
        return rows[0] if rows else None
    except Exception as e:
        _db_warn(e)
        return None


def _deck_clear_sync(tid: int) -> int:
    sb = _sb()
    if not sb:
        return 0
    try:
        return len(sb.table("tg_decks").delete().eq("tg_id", int(tid)).execute().data or [])
    except Exception as e:
        _db_warn(e)
        return 0


async def _restore_deck(chat_id: int, deck_id: Optional[int] = None) -> bool:
    """RAM'da deck bo'lmasa (restart / eskirgan) — bazadagi oxirgi (yoki tanlangan) slaydni tiklaydi. Private chat: chat_id == tg_id."""
    st = _state(chat_id)
    if st.get("deck") and not deck_id:
        return True
    row = await asyncio.to_thread(_deck_get_sync, chat_id, deck_id)
    if not row or not decks:
        return False
    deck = decks.normalize_deck(row.get("deck"), MAX_SLIDES + 10, row.get("title") or "")
    if not deck:
        return False
    st.update(deck=deck, deck_id=row.get("id"), topic=row.get("topic") or "", lang=row.get("lang") or "uz", imgs={}, awaiting=None)
    return True


# ----------------------------------------------------------------------------------------------
# Sayt akkaunti (Google) <-> Telegram ulash (bir martalik kod orqali). Bir xil balans uchun.
# ----------------------------------------------------------------------------------------------
_BOT_USER = ""


async def _bot_username() -> str:
    global _BOT_USER
    if not _BOT_USER:
        me = await tg("getMe")
        if isinstance(me, dict):
            _BOT_USER = str(me.get("username") or "")
    return _BOT_USER


def _link_code_sync(user_id: str, email: str) -> str:
    sb = _sb()
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    code = "".join(secrets.choice(alphabet) for _ in range(8))
    sb.table("tg_link_codes").delete().eq("user_id", user_id).execute()
    sb.table("tg_link_codes").insert({
        "code": code, "user_id": user_id, "email": email,
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=LINK_TTL)).isoformat(),
    }).execute()
    return code


def _link_consume_sync(user: dict, code: str) -> dict:
    sb = _sb()
    if not sb:
        return {"error": "db"}
    tid = int(user["id"])
    code = re.sub(r"[^A-Za-z0-9]", "", code or "").upper()[:16]
    if not code:
        return {"error": "bad_code"}
    try:
        res = sb.table("tg_link_codes").select("*").eq("code", code).limit(1).execute()
    except Exception as e:
        _db_warn(e)
        return {"error": "db"}
    if not res.data:
        return {"error": "bad_code"}
    row = res.data[0]
    try:
        exp = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        expired = exp < datetime.now(timezone.utc)
    except Exception:
        expired = True
    sb.table("tg_link_codes").delete().eq("code", code).execute()          # bir martalik
    if expired:
        return {"error": "bad_code"}
    return _link_apply_sync(tid, str(row["user_id"]), str(row["email"]))


def _link_apply_sync(tid: int, uid: str, email: str) -> dict:
    """Telegram ID ni sayt akkauntiga bog'laydi (kod orqali ham, havola orqali ham shu yerga keladi)."""
    sb = _sb()
    if not sb:
        return {"error": "db"}

    # Oldin botda sotib olingan PULLIK varaqlar yo'qolmasin: tg<ID>@t.me akkauntidan sayt akkauntiga ko'chiriladi.
    # (Bepul kunlik varaqlar ko'chirilmaydi — ikki akkaunt orqali ko'paytirib bo'lmasin.)
    moved = 0
    try:
        tg_email = _tg_email(tid)
        q = sb.table("user_usage").select("user_id").eq("email", tg_email).limit(1).execute()
        if q.data and str(q.data[0]["user_id"]) != uid:
            src_uid = str(q.data[0]["user_id"])
            src = _deps["apply_reset"](_deps["get_usage"](src_uid, tg_email))
            paid = int(src.get("paid_credits") or 0)
            if paid > 0:
                dst = _deps["apply_reset"](_deps["get_usage"](uid, email))
                dst["paid_credits"] = int(dst.get("paid_credits") or 0) + paid
                src["paid_credits"] = 0
                _deps["save_usage"](uid, dst, 0)
                _deps["save_usage"](src_uid, src, 0)
                moved = paid
                try:
                    _deps["ledger_log"](uid, "tg_link_in", paid, dst, 0, {"from": src_uid})
                    _deps["ledger_log"](src_uid, "tg_link_out", -paid, src, 0, {"to": uid})
                except Exception:
                    pass
    except Exception as e:
        _warn("link-move", f"pullik varaqlarni ko'chirib bo'lmadi: {str(e)[:120]}")

    try:
        sb.table("tg_links").delete().eq("tg_id", tid).execute()
        sb.table("tg_links").delete().eq("user_id", uid).execute()
        sb.table("tg_links").insert({"tg_id": tid, "user_id": uid, "email": email}).execute()
    except Exception as e:
        _db_warn(e)
        return {"error": "db"}
    _uids[tid] = (uid, email)
    pages = 0.0
    try:
        pages = moved / _page_units("fast")
    except Exception:
        pass
    return {"ok": True, "email": email, "moved_pages": pages}


def _unlink_sync(tid: int) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        sb.table("tg_links").delete().eq("tg_id", int(tid)).execute()
        _uids.pop(int(tid), None)
        return True
    except Exception as e:
        _db_warn(e)
        return False


def _tg_for_uid_sync(user_id: str) -> Optional[Tuple[int, str]]:
    sb = _sb()
    if not sb:
        return None
    email = ""
    r = sb.table("user_usage").select("email").eq("user_id", user_id).limit(1).execute()
    if r.data:
        email = str(r.data[0].get("email") or "")
    l = sb.table("tg_links").select("tg_id").eq("user_id", user_id).limit(1).execute()
    if l.data:
        return int(l.data[0]["tg_id"]), email
    m = re.match(r"^tg(\d+)@t\.me$", email)
    return (int(m.group(1)), email) if m else None


async def notify_purchase(user_id: str, pages: int, refund: bool = False, kind: str = "pack") -> None:
    """main.py to'lov webhook'idan: balans/reja bazada yangilangan — foydalanuvchiga darhol xabar."""
    if not ENABLED:
        return
    try:
        hit = await asyncio.to_thread(_tg_for_uid_sync, user_id)
        if not hit:
            return
        tid, email = hit
        if kind == "pro":
            head = f"↩️ Pro to'lovi qaytarildi: <b>−{pages} kun</b>." if refund else f"👑 <b>Pro faollashtirildi!</b> +{pages} kun.\nEndi reklama ko'rinmaydi. Rahmat! 🎉"
            await _send(tid, head, kb_main())
            return
        usage = await asyncio.to_thread(_usage_now_sync, user_id, email)
        left = _pages_left(usage, "fast")
        head = f"↩️ To'lov qaytarildi: <b>−{pages}</b> varaq." if refund else f"✅ To'lov qabul qilindi: <b>+{pages}</b> varaq!"
        await _send(tid, f"{head}\n💳 Balansingiz: <b>{_fmt_pages(left)}</b> varaq", kb_main())
    except Exception as e:
        _warn("notify", f"to'lov xabari yuborilmadi: {str(e)[:100]}")


async def notify_user(user_id: str, text: str) -> None:
    """Admin amali (Pro berildi, varaq qo'shildi...) haqida foydalanuvchiga xabar (HTML)."""
    if not ENABLED:
        return
    try:
        hit = await asyncio.to_thread(_tg_for_uid_sync, str(user_id))
        if hit:
            await _send(hit[0], text, kb_main())
    except Exception as e:
        _warn("notify-user", f"xabar yuborilmadi: {str(e)[:100]}")


async def admin_send(tid: int, text: str) -> bool:
    """Ommaviy xabar (admin paneldan): oddiy matn (HTML belgilar escape qilinadi)."""
    if not ENABLED:
        return False
    r = await tg("sendMessage", chat_id=int(tid), text=esc(text)[:4000], disable_web_page_preview=True)
    return bool(r)


# ----------------------------------------------------------------------------------------------
# Admin: «admin» deb yozilsa — FAQAT tasdiqlangan admin (Telegram ID + ulangan Google email) ga panel ochiladi
# ----------------------------------------------------------------------------------------------
def _is_admin(user: dict) -> bool:
    adm = _deps.get("admin")
    return bool(adm and adm.is_tg_admin((user or {}).get("id")))


async def _google_ok(cid: int, user: dict) -> bool:
    """Slayd yaratishdan oldin Google akkaunt ulangan bo'lishi shart (admin — istisno)."""
    if DEV_MODE or _is_admin(user):
        return True
    try:
        _uid, email = await _ensure_uid(user)
    except Exception:
        return True                       # baza xatosi — keyingi bosqich o'zi tushunarli xabar beradi
    if not email.endswith("@" + TG_EMAIL_DOMAIN):
        return True
    await _send(cid, "🔗 Slayd yaratish uchun avval <b>Google akkauntni ulang</b>.\nBu balansingizni saqlab qolish uchun kerak.",
                {"inline_keyboard": [[_btn("🔗 Google ulash", "linkinfo")]]})
    return False


# ----------------------------------------------------------------------------------------------
# Admin: «admin» yoki /admin — FAQAT ADMIN_TG_IDS dagi Telegram ID ga ochiladi. Boshqalarga: «Bunday buyruq mavjud emas».
# Foydalanuvchi ID / email / UUID bo'yicha topiladi. Hammasi bazada (Supabase) saqlanadi va jurnalga yoziladi.
# ----------------------------------------------------------------------------------------------
ADMIN_CMDS = {"/give", "/take", "/unlimited", "/fill", "/reset", "/block", "/unblock", "/user"}
ADMIN_HELP = (
    "🛡 <b>Admin</b>\n"
    "<code>/give ID 50</code> — varaq qo'shish\n"
    "<code>/take ID 20</code> — varaq ayirish\n"
    "<code>/unlimited ID</code> — cheksiz qilish (<code>/unlimited ID off</code> — olib tashlash)\n"
    "<code>/fill ID</code> — bugungi bepul limitni to'ldirish\n"
    "<code>/reset ID</code> — varaqlarni 0 qilish, cheksizni olib tashlash\n"
    "<code>/block ID</code> · <code>/unblock ID</code>\n"
    "<code>/user ID</code> — foydalanuvchi holati\n\n"
    "<i>ID — Telegram ID, email yoki UUID. Telegram ID ni foydalanuvchi /id orqali biladi.</i>"
)


def _user_line(b: dict) -> str:
    who = b.get("email") or ""
    if b.get("tg_id"):
        who += f" · TG {b['tg_id']}"
    bal = "♾ cheksiz" if b.get("unlimited") else f"{_fmt_pages(float(b.get('free_pages') or 0) + float(b.get('paid_pages') or 0))} varaq"
    return f"👤 {esc(who)}\n💎 {bal}" + (" · ⛔ bloklangan" if b.get("blocked") else "")


async def _admin_command(cid: int, user: dict, cmd: str, arg: str) -> None:
    adm = _deps.get("admin")
    if not adm or not adm.is_tg_admin(user.get("id")):
        await _send(cid, "Bunday buyruq mavjud emas.")            # oddiy foydalanuvchiga hech narsa oshkor bo'lmaydi
        return
    if cmd == "/admin":
        rows = []
        chk = await asyncio.to_thread(adm.check_admin_tg, user["id"])
        if chk.get("ok") and _https():
            url = adm.panel_url(SITE_URL, user["id"], chk["email"])
            rows.append([{"text": "🛡 To'liq panel", "web_app": {"url": url}}])
        await _send(cid, ADMIN_HELP, {"inline_keyboard": rows} if rows else None)
        return
    parts = arg.split()
    if not parts:
        await _send(cid, ADMIN_HELP)
        return
    actor = f"tg:{int(user['id'])}"
    target = parts[0]
    try:
        row = await asyncio.to_thread(adm.resolve_target, target)
        uid = str(row["user_id"])
        body: Dict[str, Any] = {"user_id": uid}
        if cmd in ("/give", "/take"):
            if len(parts) < 2:
                await _send(cid, f"Misol: <code>{cmd} {esc(target)} 50</code>")
                return
            n = abs(float(parts[1].replace(",", ".")))
            body.update(action="add_credits", pages=n if cmd == "/give" else -n)
        elif cmd == "/unlimited":
            body.update(action="unlimited", value=not (len(parts) > 1 and parts[1].lower() in ("off", "0", "yoq", "yo'q", "no")))
        elif cmd == "/fill":
            body.update(action="fill_free")
        elif cmd in ("/block", "/unblock"):
            body.update(action="block", value=cmd == "/block")
        elif cmd == "/reset":
            await asyncio.to_thread(adm.user_action, actor, {"user_id": uid, "action": "set_credits", "free_pages": 0, "paid_pages": 0})
            body.update(action="unlimited", value=False)
        elif cmd == "/user":
            b = (await asyncio.to_thread(adm.user_brief, uid))
            await _send(cid, _user_line(b))
            return
        res = await asyncio.to_thread(adm.user_action, actor, body)
        await _send(cid, f"✅ {esc(res.get('note') or 'Bajarildi')}\n{_user_line(res['user'])}")
    except adm.AdminError as e:
        await _send(cid, f"⚠️ {esc(e.msg)}")
    except ValueError:
        await _send(cid, "⚠️ Son noto'g'ri. Misol: <code>/give 123456789 50</code>")
    except Exception as e:
        _warn("admin", f"admin amali xatosi: {type(e).__name__}: {str(e)[:120]}")
        await _send(cid, "⚠️ Bajarib bo'lmadi. Keyinroq urinib ko'ring.")


# ----------------------------------------------------------------------------------------------
# Reklama (Pro / VIP / admin ko'rmaydi)
# ----------------------------------------------------------------------------------------------
async def _maybe_ad(chat_id: int, uid: str, email: str) -> None:
    """Natija yuborilgach — oraliq (sozlama) o'tgan bo'lsa bitta reklama. Hech qachon asosiy oqimni buzmaydi."""
    try:
        ads = _deps.get("ads")
        if not ads or not ads.surface_enabled("bot") or not ads.bot_due(str(uid)):
            return
        usage = await asyncio.to_thread(_usage_now_sync, uid, email)
        if _deps["usage_payload"](usage).get("ad_free"):
            return
        row = await asyncio.to_thread(ads.pick, "bot", False)
        if not row:
            return
        ads.bot_mark(str(uid))
        pub = ads.public(row, "bot")
        text = ""
        if pub["title"]:
            text += f"<b>{esc(pub['title'])}</b>\n"
        if pub["body"]:
            text += f"{esc(pub['body'])}\n"
        text += "\n<i>📢 Reklama</i>"
        rows = []
        if pub["has_link"]:
            rows.append([{"text": f"🔗 {pub['button_text']}", "url": SITE_URL + pub["click_url"]}])
        kb = {"inline_keyboard": rows} if rows else None
        media = pub["media_url"]
        if media and media.startswith("/"):
            media = SITE_URL + media
        sent = None
        if media and pub["media_type"] == "image":
            sent = await tg("sendPhoto", chat_id=chat_id, photo=media, caption=text[:1000], parse_mode="HTML", reply_markup=kb)
        elif media and pub["media_type"] == "video":
            sent = await tg("sendVideo", chat_id=chat_id, video=media, caption=text[:1000], parse_mode="HTML", reply_markup=kb, supports_streaming=True)
        if not sent:
            sent = await _send(chat_id, text, kb)
        if sent:
            await asyncio.to_thread(ads.bump, int(row["id"]), "impression")
    except Exception as e:
        _warn("ad", f"reklama yuborilmadi: {type(e).__name__}: {str(e)[:100]}")


# ----------------------------------------------------------------------------------------------
# AI
# ----------------------------------------------------------------------------------------------
GEN_SYSTEM = """You are Slide Studio AI, a professional presentation writer and designer.
Return ONLY one valid JSON object (json) — no markdown fences, no commentary.

SCHEMA
{
  "title": "deck title (max 70 chars)",
  "subtitle": "one short line",
  "theme": "ocean | violet | forest | sunset | rose | slate | teal",
  "images": true,
  "slides": [ ... exactly N slides ... ]
}
SLIDE TYPES (field "layout"):
- {"layout":"title","title":"","subtitle":"","image":"english photo query or empty","notes":""}            — ALWAYS the first slide
- {"layout":"bullets","title":"","bullets":["3-5 items, each max 110 chars"],"image":"english photo query or empty","notes":""}
- {"layout":"cards","title":"","cards":[{"heading":"max 30 chars","text":"max 110 chars"}, ... 2 to 4 cards]}
- {"layout":"stats","title":"","stats":[{"value":"72%","label":"what it means"}, ... 2 to 4 items]}
- {"layout":"quote","text":"","author":""}                                                          — only a REAL, well-known quote with the correct author
- {"layout":"closing","title":"Thank you / key takeaway","subtitle":""}                                — ALWAYS the last slide

RULES
- Produce EXACTLY the requested number of slides: 1 title + (N-2) content slides + 1 closing.
- Write all slide text in the language of the user's request. If it is Uzbek, use Latin script. If the language is unclear, use Uzbek.
- Content must be concrete, accurate and useful: real facts, examples, steps — no filler, no repeated points. Never invent precise statistics; use a "stats" slide only for well-known figures, otherwise use "~" approximations or use "cards".
- Vary layouts: never more than 2 identical content layouts in a row. Use at least one "cards" slide when N >= 6.
- "image": a short ENGLISH search query (2-4 words) for a concrete photographable subject. Give it for the title slide and for at most 40% of the "bullets" slides, otherwise "". If the user does not want images set "images": false and every "image" to "".
- "notes": 1-2 sentences of speaker notes (same language as the slides).
- No emoji, no markdown symbols (**, #) inside text.
- Pick the theme that fits the topic, or the colour the user asked for (blue=ocean, purple=violet, green=forest, orange=sunset, pink/red=rose, black/gray=slate, turquoise=teal).
"""

EDIT_SYSTEM = """You are Slide Studio AI, the editor of an existing slide deck. Return ONLY one valid JSON object (json), no markdown fences.
You receive: OUTLINE (every slide, numbered from 1), the FULL JSON of the slides that matter (or of the whole deck), and the user's NEW MESSAGE.
Decide the intent:
1) "edit" — the user wants a change (shorten, rewrite, retitle, translate, add/remove/move slides, change colours, fix a fact...).
   Return {"intent":"edit","reply":"1-2 short sentences saying what you changed","ops":[ ... ]}
   Change ONLY what was asked. Never rewrite untouched slides. Operations (slide numbers = numbering in the OUTLINE; the server applies them in order):
   {"op":"replace","index":3,"slide":{...complete new slide...}}        — rewrite one slide
   {"op":"insert","after":5,"slide":{...}}                              — add a slide after slide 5 (never before the title slide)
   {"op":"delete","index":4}                                            — remove a slide (never the title slide)
   {"op":"move","index":6,"after":2}                                    — move slide 6 right after slide 2
   {"op":"meta","title":"...","subtitle":"...","theme":"ocean|violet|forest|sunset|rose|slate|teal"}  — deck title / subtitle / colour (any subset of the fields)
   For slide 1 use "replace" with layout "title" (that is how «sarlavhasini o'zgartir» works for the deck title: also send a "meta" op with the new title).
   Only if nearly EVERY slide must change (translate the whole deck, rewrite everything) you may return "deck" (the COMPLETE updated deck) instead of "ops".
2) "new_topic" — the message is clearly a NEW presentation topic unrelated to the current deck.   Return {"intent":"new_topic"}
3) "chat" — a question or small talk about the deck, not requesting a change.   Return {"intent":"chat","reply":"helpful answer, max 4 sentences"}
SLIDE SCHEMA (field "layout"): title/closing: title, subtitle · bullets: title, bullets[3-5], image · cards: title, cards[{heading,text}] (2-4) · stats: title, stats[{value,label}] (2-4) · quote: text, author
 - "image" is a short ENGLISH photo search query or "". Keep the language of the deck unless asked to translate. No emoji, no markdown symbols. Reply in the user's language.
"""

_NUM_A = re.compile(r"(\d{1,2})\s*[-–]?\s*(?:chi|nchi|inchi|-chi)?\s*(?:slayd\w*|slaid\w*|slide\w*|слайд\w*|varaq\w*|sahifa\w*|page\w*)", re.I)
_NUM_B = re.compile(r"(?:slayd\w*|slaid\w*|slide\w*|слайд\w*|varaq\w*|sahifa\w*|page\w*)\s*(?:№|#|raqam\w*)?\s*(\d{1,2})\b", re.I)
_LAST_RE = re.compile(r"\b(oxirgi|yakuniy|so'nggi|последн\w*|last)\b", re.I)
_FIRST_RE = re.compile(r"\b(birinchi|muqova|titul|первы\w*|first|cover)\b", re.I)


def _focus_indexes(text: str, total: int) -> List[int]:
    """Xabarda tilga olingan slayd raqamlari (1-based). Bo'sh bo'lsa — butun deck AI'ga beriladi."""
    found = set()
    for rx in (_NUM_A, _NUM_B):
        for m in rx.finditer(text or ""):
            n = int(m.group(1))
            if 1 <= n <= total:
                found.add(n)
    if _LAST_RE.search(text or ""):
        found.add(total)
    if _FIRST_RE.search(text or ""):
        found.add(1)
    return sorted(found)


def _outline(deck: dict) -> str:
    out = []
    for i, s in enumerate(deck.get("slides", []), 1):
        t = s.get("title") or s.get("text") or ""
        out.append(f"{i}. [{s.get('layout')}] {decks.clean(t, 70)}")
    return "\n".join(out)


def _edit_prompt(deck: dict, text: str) -> str:
    slides = deck.get("slides", [])
    focus = _focus_indexes(text, len(slides))
    slim = lambda s: {k: v for k, v in s.items() if v not in ("", None, [])}
    head = f"DECK: title={json.dumps(deck.get('title'), ensure_ascii=False)} theme={deck.get('theme')}\nOUTLINE:\n{_outline(deck)}\n\n"
    if focus:
        body = "FULL JSON OF THE SLIDES THE USER MENTIONED:\n" + json.dumps({str(i): slim(slides[i - 1]) for i in focus}, ensure_ascii=False)
    else:
        body = "FULL DECK JSON:\n" + _deck_for_prompt(deck)
    return f"{head}{body}\n\nNEW MESSAGE:\n{text}"


def _apply_ops(deck: dict, ops: Any) -> Tuple[Optional[dict], int]:
    """AI bergan amallarni deck nusxasiga qo'llaydi. (yangi_deck | None, o'zgargan/qo'shilgan slaydlar soni).
    Tegilmagan slaydlar AYNAN o'zgarishsiz qoladi."""
    if not isinstance(ops, list) or not ops:
        return None, 0
    items: List[List[Any]] = [[i, dict(s)] for i, s in enumerate(deck["slides"], 1)]     # [asl_raqam, slayd]
    title, subtitle, theme = deck.get("title"), deck.get("subtitle"), deck.get("theme")
    changed, applied = 0, 0

    def pos(orig: int) -> int:
        for k, it in enumerate(items):
            if it[0] == orig:
                return k
        return -1

    for op in ops[:30]:
        if not isinstance(op, dict):
            continue
        kind = str(op.get("op") or "").lower()
        try:
            if kind == "replace":
                k = pos(int(op.get("index")))
                new = decks.normalize_slide(op.get("slide"))
                if k < 0 or not new:
                    continue
                if k == 0 and new["layout"] != "title":
                    continue
                if json.dumps(items[k][1], sort_keys=True, ensure_ascii=False) != json.dumps(new, sort_keys=True, ensure_ascii=False):
                    changed += 1
                items[k][1] = new
                applied += 1
            elif kind == "insert":
                after = int(op.get("after"))
                new = decks.normalize_slide(op.get("slide"))
                k = pos(after)
                if not new or k < 0 or len(items) >= MAX_SLIDES + 8:
                    continue
                if items[k][1].get("layout") == "closing":      # yakunlovchi slayddan keyin emas, oldin
                    k -= 1
                items.insert(k + 1, [-len(items) - 1000, new])
                changed += 1
                applied += 1
            elif kind == "delete":
                k = pos(int(op.get("index")))
                if k <= 0 or len(items) <= 2:
                    continue
                items.pop(k)
                applied += 1
            elif kind == "move":
                a, b = pos(int(op.get("index"))), int(op.get("after"))
                if a <= 0 or items[a][1].get("layout") == "closing":      # titul va yakunlovchi slayd joyidan qo'zg'almaydi
                    continue
                it = items.pop(a)
                k = pos(b)
                if k >= 0 and items[k][1].get("layout") == "closing":
                    k -= 1
                items.insert(k + 1 if k >= 0 else a, it)
                applied += 1
            elif kind == "meta":
                if isinstance(op.get("title"), str) and op["title"].strip():
                    title = decks.clean(op["title"], 90)
                if isinstance(op.get("subtitle"), str):
                    subtitle = decks.clean(op["subtitle"], 140)
                th = str(op.get("theme") or "").strip().lower()
                if th in decks.THEMES:
                    theme = th
                applied += 1
        except (TypeError, ValueError):
            continue
    if not applied:
        return None, 0
    raw = {"title": title, "subtitle": subtitle, "theme": theme, "slides": [it[1] for it in items]}
    new_deck = decks.normalize_deck(raw, len(items) + 2, str(title or ""))
    return new_deck, changed


_ai_client = None
_ai_sig: Tuple[str, str] = ("", "")


def _get_ai():
    global _ai_client, _ai_sig
    cfg = (_deps.get("ai") or (lambda: {}))()
    if not cfg.get("api_key"):
        raise RuntimeError("ai_not_configured")
    sig = (cfg["api_key"], cfg.get("base_url") or "")
    if _ai_client is None or sig != _ai_sig:
        from openai import AsyncOpenAI
        _ai_client = AsyncOpenAI(api_key=cfg["api_key"], base_url=cfg.get("base_url") or "https://api.deepseek.com", timeout=170.0, max_retries=1)
        _ai_sig = sig
    return _ai_client, cfg


async def _ai_json(system: str, user: str, mode: str) -> Tuple[Optional[dict], int]:
    client, cfg = _get_ai()
    model = cfg.get("deep_model") if mode == "deep" else cfg.get("fast_model")
    kw: Dict[str, Any] = dict(model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=7500)
    if mode != "deep":
        kw.update(temperature=0.7, response_format={"type": "json_object"})
    resp = await asyncio.wait_for(client.chat.completions.create(**kw), timeout=175)
    text = (resp.choices[0].message.content or "") if resp.choices else ""
    tokens = int(getattr(getattr(resp, "usage", None), "total_tokens", 0) or 0)
    return decks.extract_json(text), tokens


def _parse_count(text: str) -> Optional[int]:
    m = COUNT_RE.search(text or "")
    if not m:
        return None
    try:
        n = int(m.group(1))
    except Exception:
        return None
    return max(MIN_SLIDES, min(MAX_SLIDES, n))


def _deck_for_prompt(deck: dict) -> str:
    slim = {"title": deck.get("title"), "subtitle": deck.get("subtitle"), "theme": deck.get("theme"),
            "slides": [{k: v for k, v in s.items() if v not in ("", None, [])} for s in deck.get("slides", [])]}
    return json.dumps(slim, ensure_ascii=False)


async def _fetch_images(deck: dict, have: Dict[str, bytes], enabled: bool) -> Dict[str, bytes]:
    """Slaydlar uchun rasmlarni (query -> bayt) parallel yuklaydi. Vaqt cheklangan; topilmasa — rasmsiz slayd."""
    out = dict(have)
    if not enabled:
        return out
    queries: List[str] = []
    for s in deck["slides"]:
        q = s.get("image") or ""
        if q and s["layout"] in ("title", "bullets") and q not in out and q not in queries:
            queries.append(q)
    queries = queries[:6]
    if not queries:
        return out
    sem = asyncio.Semaphore(3)

    async def one(q: str):
        async with sem:
            return q, await asyncio.to_thread(decks.find_image, q)

    tasks = [asyncio.create_task(one(q)) for q in queries]
    done, pending = await asyncio.wait(tasks, timeout=28)
    for t in pending:
        t.cancel()
    for t in done:
        try:
            q, data = t.result()
            if data:
                out[q] = data
        except Exception:
            pass
    return out


def _img_index(deck: dict, imgs: Dict[str, bytes]) -> Dict[int, bytes]:
    return {i: imgs[s["image"]] for i, s in enumerate(deck["slides"]) if s.get("image") and s["image"] in imgs}


def _theme_label(deck: dict) -> str:
    return decks.THEMES.get(deck.get("theme"), {}).get("label", "")


def _summary(deck: dict) -> str:
    lines = []
    for i, s in enumerate(deck["slides"][:14], 1):
        t = s.get("title") or s.get("text") or ""
        lines.append(f"{i}. {esc(decks.clean(t, 60))}")
    if len(deck["slides"]) > 14:
        lines.append(f"… va yana {len(deck['slides']) - 14} ta")
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------
# Generatsiya / tahrirlash vazifalari (alohida task'larda — webhook darhol 200 qaytaradi)
# ----------------------------------------------------------------------------------------------
_gen_sem = asyncio.Semaphore(3)
_bg: set = set()


def _spawn(coro) -> None:
    t = asyncio.create_task(coro)
    _bg.add(t)
    t.add_done_callback(_bg.discard)


async def _send(chat_id: int, text: str, kb: Optional[dict] = None) -> Optional[dict]:
    payload: Dict[str, Any] = {"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": True}
    if kb:
        payload["reply_markup"] = kb
    return await tg("sendMessage", **payload)


async def _edit(chat_id: int, msg_id: Optional[int], text: str, kb: Optional[dict] = None) -> None:
    if not msg_id:
        await _send(chat_id, text, kb)
        return
    payload: Dict[str, Any] = {"chat_id": chat_id, "message_id": msg_id, "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": True}
    if kb:
        payload["reply_markup"] = kb
    await tg("editMessageText", **payload)


def _no_credit_text(mode: str, usage: Optional[dict]) -> str:
    w = ""
    try:
        w = _fmt_wait(_deps["usage_payload"](usage).get("next_reset_in_seconds")) if usage else ""
    except Exception:
        pass
    return "😔 <b>Varaqlar tugadi.</b>\n" + (f"Bepul varaqlar <b>{w}</b> dan keyin yangilanadi.\n" if w else "") + "Davom etish uchun varaq sotib oling 👇"


def _kb_buy() -> dict:
    return {"inline_keyboard": [[_btn("➕ Varaq sotib olish", "buy")]]}


STEPS = ["Mavzu tahlili", "Slayd matnlari", "Rasmlar", "Fayllar (PPTX · PDF · HTML)"]
HEADS = ["⏳ AI mavzuni tahlil qilmoqda…", "🧠 Slayd tuzilishi va matnlari yozilmoqda…", "🖼 Rasmlar tanlanmoqda…", "📦 Fayllar tayyorlanmoqda…"]


def _steps(cur: int, extra: str = "") -> str:
    lines = [("✅" if i < cur else ("⏳" if i == cur else "▫️")) + f" {t}" for i, t in enumerate(STEPS)]
    return f"<b>{HEADS[cur]}</b>\n\n" + "\n".join(lines) + extra


async def _run_generate(chat_id: int, user: dict, topic: str, n: int) -> None:
    st = _state(chat_id)
    st["busy"] = True
    msg_id: Optional[int] = None
    try:
        mode = st.get("mode", "fast")
        sent = await _send(chat_id, _steps(0))
        msg_id = (sent or {}).get("message_id") if isinstance(sent, dict) else None
        await tg("sendChatAction", chat_id=chat_id, action="typing")
        uid, email = await _ensure_uid(user)
        usage = await asyncio.to_thread(_usage_now_sync, uid, email)
        if usage.get("blocked"):
            await _edit(chat_id, msg_id, "⛔ Akkauntingiz bloklangan.")
            return
        afford = int(_deps["total_credits"](usage) // _page_units(mode))
        if afford < 1:
            await _edit(chat_id, msg_id, _no_credit_text(mode, usage), _kb_buy())
            return
        note = ""
        if n > afford:
            note = f"\n\nℹ️ Balansingizda {afford} varaq bor — shuncha slayd yaratiladi."
            n = max(1, afford)
        n = max(1, n)
        extra = f"\n\n{n} ta slayd · {'🧠 Chuqur' if mode == 'deep' else '⚡ Tez'} AI" + ("\n<i>Chuqur rejim 1–2 daqiqa olishi mumkin.</i>" if mode == "deep" else "") + note
        await _edit(chat_id, msg_id, _steps(1, extra))

        async with _gen_sem:
            deck, tokens, tries = None, 0, 0
            data: Optional[dict] = None
            prompt = f"User request:\n{topic}\n\nNumber of slides N = {n}"
            while tries < 2 and deck is None:
                tries += 1
                data, tk = await _ai_json(GEN_SYSTEM, prompt if tries == 1 else prompt + "\n\nReturn ONLY the JSON object, strictly following the schema.", mode)
                tokens += tk
                deck = decks.normalize_deck(data, n, topic)
            if deck is None:
                await _edit(chat_id, msg_id, "⚠️ AI to'g'ri javob bermadi. Hech narsa yechilmadi — mavzuni qayta yuboring.")
                return
            imgs_on = (data or {}).get("images", True) is not False
            await _edit(chat_id, msg_id, _steps(2, f"\n\n«{esc(deck['title'])}» — {len(deck['slides'])} ta slayd"))
            await tg("sendChatAction", chat_id=chat_id, action="upload_photo")
            imgs = await _fetch_images(deck, {}, imgs_on)

        usage2, charged = await _charge(uid, email, len(deck["slides"]), tokens, mode, {"src": "telegram", "slides": len(deck["slides"]), "topic": topic[:80]})
        lang = _guess_lang(topic)
        st.update(deck=deck, imgs=imgs, img_ts=time.time(), topic=topic, awaiting=None, uid=uid, email=email, lang=lang)
        st["deck_id"] = await asyncio.to_thread(_deck_insert_sync, chat_id, uid, deck, topic, lang)      # faqat qisqa JSON matn
        left = _pages_left(usage2, mode)
        spent = charged / _page_units(mode)
        await _edit(chat_id, msg_id, _steps(3))
        await _edit(
            chat_id, msg_id,
            f"✅ <b>{esc(deck['title'])}</b> tayyor!\n🎞 {len(deck['slides'])} ta slayd · 🎨 {esc(_theme_label(deck))}\n\n{_summary(deck)}\n\n"
            f"💳 Sarflandi: <b>{_fmt_pages(spent)}</b> varaq · Qoldi: <b>{_fmt_pages(left)}</b>{note}\n\n📦 Fayllar yuborilmoqda…",
        )
        await _send_files(chat_id, "all")
        await _maybe_ad(chat_id, uid, email)
    except asyncio.TimeoutError:
        await _edit(chat_id, msg_id, "⌛ AI juda uzoq o'ylandi. Hech narsa yechilmadi — qayta urinib ko'ring (yoki ⚡ Tez AI rejimini tanlang: /mode).")
    except RuntimeError as e:
        txt = "⚙️ AI xizmati hozircha sozlanmagan." if "ai_not_configured" in str(e) else "⚙️ Akkauntni ochib bo'lmadi. Birozdan keyin urinib ko'ring."
        await _edit(chat_id, msg_id, txt)
    except Exception as e:
        _warn("gen", f"generatsiya xatosi: {type(e).__name__}: {str(e)[:160]}")
        await _edit(chat_id, msg_id, "⚠️ Xatolik yuz berdi. Hech narsa yechilmadi — birozdan keyin qayta urinib ko'ring.")
    finally:
        st["busy"] = False


def _guess_lang(text: str) -> str:
    if re.search(r"[а-яёА-ЯЁ]", text or ""):
        return "ru"
    return "uz"


def _changed_slides(old: dict, new: dict) -> int:
    a, b = old.get("slides", []), new.get("slides", [])
    ch = 0
    for i, s in enumerate(b):
        if i >= len(a) or json.dumps(a[i], sort_keys=True, ensure_ascii=False) != json.dumps(s, sort_keys=True, ensure_ascii=False):
            ch += 1
    return ch


async def _run_edit(chat_id: int, user: dict, text: str) -> None:
    st = _state(chat_id)
    st["busy"] = True
    msg_id: Optional[int] = None
    try:
        mode = st.get("mode", "fast")
        if not st.get("deck") and not await _restore_deck(chat_id):
            await _send(chat_id, "Avval slayd yarating — mavzuni yozing 🙂")
            return
        deck = st["deck"]
        uid, email = await _ensure_uid(user)
        usage = await asyncio.to_thread(_usage_now_sync, uid, email)
        if _deps["total_credits"](usage) < _deps["MODES"][mode]["chat"]:
            await _send(chat_id, _no_credit_text(mode, usage), _kb_buy())
            return
        sent = await _send(chat_id, "✏️ <b>AI o'qimoqda…</b>")
        msg_id = (sent or {}).get("message_id") if isinstance(sent, dict) else None
        await tg("sendChatAction", chat_id=chat_id, action="typing")
        async with _gen_sem:
            data, tokens = await _ai_json(EDIT_SYSTEM, _edit_prompt(deck, text), mode)
        data = data if isinstance(data, dict) else {}
        intent = str(data.get("intent") or "").lower()
        if intent == "new_topic":
            await _edit(chat_id, msg_id, "🆕 Yangi mavzu deb tushundim.")
            st.update(deck=None, deck_id=None, imgs={}, awaiting=None, topic=text[:1500])
            st["busy"] = False
            await _run_generate(chat_id, user, text[:1500], _parse_count(text) or DEFAULT_SLIDES)
            return
        has_change = isinstance(data.get("ops"), list) or isinstance(data.get("deck"), dict)
        if intent == "chat" or not has_change:
            await _charge(uid, email, 0, tokens, mode, {"src": "telegram", "kind": "chat"})
            reply = decks.clean(data.get("reply"), 800) or "Tushunmadim, iltimos aniqroq yozing — masalan: «3-slaydni qisqartir»."
            await _edit(chat_id, msg_id, f"💬 {esc(reply)}", kb_done(st))
            return
        new, changed = None, 0
        if isinstance(data.get("ops"), list):
            new, changed = _apply_ops(deck, data["ops"])            # faqat kerakli slaydlar o'zgaradi
        else:
            new = decks.normalize_deck(data["deck"], len(deck["slides"]) + 8, deck.get("title", ""))
            changed = _changed_slides(deck, new) if new else 0
        if not new:
            await _edit(chat_id, msg_id, "⚠️ O'zgartirishni qo'llab bo'lmadi. Hech narsa yechilmadi — boshqacha yozib ko'ring.", kb_done(st))
            return
        afford = int(_deps["total_credits"](usage) // _page_units(mode))
        if changed > afford:
            await _edit(chat_id, msg_id, f"😔 Bu o'zgarish {changed} varaq talab qiladi, sizda {afford} varaq bor. Kichikroq o'zgarish so'rang yoki varaq oling.", kb_main())
            return
        usage2, charged = await _charge(uid, email, changed, tokens, mode, {"src": "telegram", "kind": "edit", "changed": changed})
        st.update(deck=new, awaiting=None)
        if st.get("deck_id"):
            await asyncio.to_thread(_deck_update_sync, st["deck_id"], chat_id, new)
        else:
            st["deck_id"] = await asyncio.to_thread(_deck_insert_sync, chat_id, uid, new, st.get("topic", ""), st.get("lang", "uz"))
        reply = decks.clean(data.get("reply"), 500)
        left = _pages_left(usage2, mode)
        await _edit(
            chat_id, msg_id,
            "✅ <b>Yangilandi</b>" + (f" — {esc(reply)}" if reply else "") + f"\n🎞 {len(new['slides'])} ta slayd · 🎨 {esc(_theme_label(new))}\n\n{_summary(new)}\n\n"
            f"💳 Sarflandi: <b>{_fmt_pages(charged / _page_units(mode))}</b> varaq · Qoldi: <b>{_fmt_pages(left)}</b>\n\n📦 Yangi fayllar yuborilmoqda…",
        )
        await _send_files(chat_id, "all")
        await _maybe_ad(chat_id, uid, email)
    except asyncio.TimeoutError:
        await _edit(chat_id, msg_id, "⌛ AI juda uzoq o'ylandi. Hech narsa yechilmadi — qayta urinib ko'ring.", kb_done(st))
    except Exception as e:
        _warn("edit", f"tahrir xatosi: {type(e).__name__}: {str(e)[:160]}")
        await _edit(chat_id, msg_id, "⚠️ Xatolik yuz berdi. Hech narsa yechilmadi.", kb_done(st))
    finally:
        st["busy"] = False


async def _send_files(chat_id: int, fmt: str) -> bool:
    """Fayllar FAQAT RAM'da yasaladi, Telegram'ga yuboriladi va darhol tashlab yuboriladi (diskka yozilmaydi)."""
    st = _state(chat_id)
    if not st.get("deck") and not await _restore_deck(chat_id):
        await _send(chat_id, "Slayd topilmadi (bot qayta ishga tushgan bo'lishi mumkin). Mavzuni yozing — yangisini yarataman 🙂")
        return False
    if st.get("sending"):
        return False
    deck = st["deck"]
    st["sending"] = True
    files: Optional[list] = None
    ok_all = False
    try:
        await tg("sendChatAction", chat_id=chat_id, action="upload_document")
        imgs_q = await _fetch_images(deck, st.get("imgs") or {}, True)          # faqat yetishmayotgan rasmlar
        st["imgs"], st["img_ts"] = imgs_q, time.time()
        lang = st.get("lang", "uz")
        if fmt == "all":
            files = await asyncio.to_thread(decks.export_all, deck, _img_index(deck, imgs_q), lang)
        else:
            files = [await asyncio.to_thread(decks.export, deck, _img_index(deck, imgs_q), fmt, lang)]
        total, ok_all, first = len(files), True, True
        while files:
            name, data, mime = files.pop(0)                                     # yuborilgach RAM'dan bo'shaydi
            cap = f"📦 <b>{esc(deck['title'])}</b>" if (first and fmt == "all") else (f"<b>{esc(deck['title'])}</b>" if total == 1 else "")
            if name.endswith(".html") and fmt != "all":
                cap += "\n<i>Brauzerda oching: ← → tugmalar yoki barmoq bilan suring, F — to'liq ekran.</i>"
            ok_all = (await tg_send_document(chat_id, name, data, mime, cap)) and ok_all
            first, data = False, None
        if ok_all:
            await _send(chat_id, "✅ Tayyor! Yana format kerakmi yoki o'zgartirish qilamizmi?\n<i>Masalan: «3-slaydni qisqartir», «sarlavhasini o'zgartir».</i>", kb_done(st))
        else:
            await _send(chat_id, "⚠️ Faylni yuborib bo'lmadi. Qayta urinib ko'ring.", kb_done(st))
    except Exception as e:
        _warn("files", f"fayl yig'ish xatosi: {type(e).__name__}: {str(e)[:160]}")
        await _send(chat_id, "⚠️ Faylni tayyorlashda xatolik. Qayta urinib ko'ring.", kb_done(st))
    finally:
        files = None
        st["imgs"] = {}                                                         # rasmlar ham RAM'dan tozalanadi
        st["sending"] = False
        gc.collect()
    return ok_all


async def _ask_count(chat_id: int, user: dict, topic: str) -> None:
    st = _state(chat_id)
    st["topic"] = topic[:1500]
    bal = ""
    try:
        uid, email = await _ensure_uid(user)
        u = await asyncio.to_thread(_usage_now_sync, uid, email)
        bal = f"\n💳 Balans: <b>{_fmt_pages(_pages_left(u, st.get('mode', 'fast')))}</b> varaq"
    except Exception:
        pass
    shown = decks.clean(topic, 160)
    await _send(
        chat_id,
        f"✅ Mavzu: <b>{esc(shown)}</b>\n\n<b>Nechta slayd kerak?</b> Tugmani bosing (yoki «10 ta slayd» deb yozing).\n"
        f"<i>1 slayd = 1 varaq{' (Chuqur AI — 3 varaq)' if st.get('mode') == 'deep' else ''}</i>{bal}",
        kb_count(st.get("mode", "fast")),
    )


# ----------------------------------------------------------------------------------------------
# Update ishlovi
# ----------------------------------------------------------------------------------------------
PPTX_MAX = 12 * 1024 * 1024


async def _download_tg_file(file_id: str, limit: int = PPTX_MAX) -> Optional[bytes]:
    info = await tg("getFile", file_id=file_id)
    path = (info or {}).get("file_path") if isinstance(info, dict) else None
    if not path or int((info or {}).get("file_size") or 0) > limit:
        return None
    try:
        r = await _http().get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}", timeout=httpx.Timeout(60.0, connect=8.0))
        if r.status_code == 200 and len(r.content) <= limit:
            return r.content
    except Exception as e:
        _warn("dl", f"fayl yuklab olinmadi: {type(e).__name__}")
    return None


def _pptx_to_deck(data: bytes, fname: str = "") -> Tuple[Optional[dict], int]:
    """Yuborilgan PPTX dan matnni (sarlavha, punktlar, jadval) o'qib qisqa deck JSON yasaydi. Rasm/dizayn o'qilmaydi."""
    from pptx import Presentation
    prs = Presentation(io.BytesIO(data))
    raw, skipped = [], 0
    for sl in prs.slides:
        title_shape = None
        try:
            title_shape = sl.shapes.title
        except Exception:
            pass
        title = ""
        if title_shape is not None and getattr(title_shape, "has_text_frame", False):
            title = title_shape.text_frame.text.strip()
        paras: List[str] = []
        for sh in sl.shapes:
            if title_shape is not None and sh.shape_id == title_shape.shape_id:
                continue
            if getattr(sh, "has_text_frame", False) and sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    tx = (p.text or "").strip()
                    if tx:
                        paras.append(tx)
            elif getattr(sh, "has_table", False) and sh.has_table:
                for row in sh.table.rows:
                    cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if cells:
                        paras.append(" — ".join(cells))
        if not title and paras:
            title = paras.pop(0)
        if not title and not paras:
            skipped += 1
            continue
        raw.append((title, paras))
    if not raw:
        return None, skipped
    if len(raw) > MAX_SLIDES:
        skipped += len(raw) - MAX_SLIDES
        raw = raw[:MAX_SLIDES]
    slides = []
    for i, (title, paras) in enumerate(raw):
        if i == 0:
            slides.append({"layout": "title", "title": title, "subtitle": paras[0] if paras else ""})
        elif i == len(raw) - 1 and len(raw) >= 3 and len(paras) <= 1:
            slides.append({"layout": "closing", "title": title, "subtitle": paras[0] if paras else ""})
        elif paras:
            slides.append({"layout": "bullets", "title": title, "bullets": paras[:6]})
        else:
            skipped += 1
    base = os.path.splitext(fname or "")[0]
    deck = decks.normalize_deck({"title": raw[0][0] or base, "subtitle": "", "theme": "ocean", "slides": slides}, MAX_SLIDES + 2, base)
    return deck, skipped


# ----------------------------------------------------------------------------------------------
# «✏️ Redaktorda ochish»: botga yuborilgan fayl VAQTINCHA (15 daqiqa) faqat RAM'da turadi, Mini App/brauzer uni
# imzolangan havola bilan oladi. Diskka yozilmaydi, bazaga tushmaydi.
# ----------------------------------------------------------------------------------------------
FILE_MAX = 15 * 1024 * 1024
FILE_TTL = 900
FILES_KEEP, FILES_BYTES = 40, 160 * 1024 * 1024
EDITABLE_RE = re.compile(r"\.(png|jpe?g|webp|gif|bmp|avif|mp4|webm|mov|m4v|ogv|ogg|pptx|pdf|html?)$", re.I)
_files: "OrderedDict[int, dict]" = OrderedDict()


def _files_sweep() -> None:
    now = time.time()
    for k in [k for k, v in _files.items() if v["exp"] < now]:
        _files.pop(k, None)
    while _files and (len(_files) > FILES_KEEP or sum(len(v["data"]) for v in _files.values()) > FILES_BYTES):
        _files.popitem(last=False)


def _file_put(cid: int, name: str, data: bytes) -> int:
    _files_sweep()
    key = secrets.randbelow(2 ** 31 - 1) + 1
    _files[key] = {"cid": int(cid), "name": name[:120], "data": data, "exp": time.time() + FILE_TTL}
    return key


def _file_url(cid: int, key: int) -> str:
    return f"{SITE_URL}/?src=tg&tgfile={_make_token('F', cid, key, FILE_TTL)}"


def _incoming_file(msg: dict) -> Optional[Tuple[str, str, int]]:
    """Xabardagi rasm/hujjat/video/GIF -> (file_id, fayl_nomi, hajmi) yoki None."""
    doc = msg.get("document")
    if isinstance(doc, dict) and doc.get("file_id"):
        return str(doc["file_id"]), str(doc.get("file_name") or "fayl"), int(doc.get("file_size") or 0)
    ph = msg.get("photo")
    if isinstance(ph, list) and ph and isinstance(ph[-1], dict):
        best = max((p for p in ph if isinstance(p, dict) and p.get("file_id")), key=lambda p: int(p.get("file_size") or 0), default=None)
        if best:
            return str(best["file_id"]), "foto.jpg", int(best.get("file_size") or 0)
    for key, nm in (("animation", "animatsiya.mp4"), ("video", "video.mp4")):
        v = msg.get(key)
        if isinstance(v, dict) and v.get("file_id"):
            return str(v["file_id"]), str(v.get("file_name") or nm), int(v.get("file_size") or 0)
    return None


async def _run_file(chat_id: int, user: dict, file_id: str, fname: str, size: int) -> None:
    st = _state(chat_id)
    st["busy"] = True
    try:
        if not EDITABLE_RE.search(fname):
            await _send(chat_id, "📎 Bu turdagi fayl muharrirda ochilmaydi.\nQo'llanadi: <b>rasm, GIF, video, PPTX, PDF, HTML</b>.", kb_reply())
            return
        if size and size > FILE_MAX:
            await _send(chat_id, "⚠️ Fayl katta — 15 MB gacha yuboring.", kb_reply())
            return
        sent = await _send(chat_id, "📎 <b>Fayl qabul qilinmoqda…</b>")
        mid = (sent or {}).get("message_id") if isinstance(sent, dict) else None
        data = await _download_tg_file(file_id, FILE_MAX)
        if not data:
            await _edit(chat_id, mid, "⚠️ Faylni yuklab bo'lmadi (15 MB dan oshmasin). Qayta yuboring.")
            return
        key = _file_put(chat_id, fname, data)
        n = len(data)
        data = None
        url = _file_url(chat_id, key)
        rows = [[{"text": "✏️ Redaktorda ochish", "web_app": {"url": url}}]]
        if fname.lower().endswith(".pptx"):
            rows.append([_btn("🤖 AI bilan matnini tahrirlash", f"pptxai:{key}")])
        rows.append([{"text": "🌐 Brauzerda ochish", "url": url}])
        size_txt = f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{max(1, n // 1024)} KB"
        await _edit(chat_id, mid, f"✅ <b>{esc(fname)}</b> ({size_txt}) qabul qilindi.\n"
                                  f"Muharrirda ochish uchun tugmani bosing. <i>Fayl {FILE_TTL // 60} daqiqa saqlanadi, so'ng o'chadi.</i>",
                    {"inline_keyboard": rows})
    except Exception as e:
        _warn("file", f"fayl qabuli xatosi: {type(e).__name__}: {str(e)[:140]}")
        await _send(chat_id, "⚠️ Faylni qabul qilib bo'lmadi. Keyinroq qayta urinib ko'ring.")
    finally:
        st["busy"] = False
        gc.collect()


async def _run_import(chat_id: int, user: dict, file_id: str, fname: str, pre: Optional[bytes] = None) -> None:
    st = _state(chat_id)
    st["busy"] = True
    msg_id: Optional[int] = None
    try:
        sent = await _send(chat_id, "📎 <b>PPTX o'qilmoqda…</b>")
        msg_id = (sent or {}).get("message_id") if isinstance(sent, dict) else None
        data = pre or await _download_tg_file(file_id)
        pre = None
        if not data:
            await _edit(chat_id, msg_id, "⚠️ Faylni yuklab bo'lmadi. <b>.pptx</b> bo'lsin va 12 MB dan oshmasin.")
            return
        deck, skipped = await asyncio.to_thread(_pptx_to_deck, data, fname)
        data = None
        if not deck:
            await _edit(chat_id, msg_id, "⚠️ PPTX ichida o'qiladigan matn topilmadi (faqat rasmli slaydlar bo'lishi mumkin).")
            return
        uid, email = await _ensure_uid(user)
        lang = _guess_lang(json.dumps(deck, ensure_ascii=False)[:2000])
        st.update(deck=deck, imgs={}, topic=deck["title"], awaiting=None, lang=lang, uid=uid, email=email)
        st["deck_id"] = await asyncio.to_thread(_deck_insert_sync, chat_id, uid, deck, deck["title"], lang)
        note = f"\n<i>{skipped} ta bo'sh/rasmli slayd o'tkazib yuborildi.</i>" if skipped else ""
        await _edit(
            chat_id, msg_id,
            f"✅ <b>{esc(deck['title'])}</b> o'qildi (bepul)\n🎞 {len(deck['slides'])} ta slayd{note}\n\n{_summary(deck)}\n\n"
            "ℹ️ Matn olindi; asl dizayn va rasmlar o'qilmaydi — yangi fayl bot dizaynida chiqadi.\n"
            "✏️ <b>Endi yozing:</b> <i>«2-slaydni qisqartir»</i>, <i>«ruscha tarjima qil»</i>…",
            kb_done(st),
        )
    except Exception as e:
        _warn("import", f"PPTX import xatosi: {type(e).__name__}: {str(e)[:140]}")
        await _edit(chat_id, msg_id, "⚠️ PPTX ni o'qib bo'lmadi. Boshqa fayl yuboring yoki mavzuni yozing.")
    finally:
        st["busy"] = False
        gc.collect()


async def _show_my(cid: int) -> None:
    rows = await asyncio.to_thread(_deck_list_sync, cid)
    if not rows:
        await _send(cid, "📂 Saqlangan slaydlar yo'q.\nMavzuni yozing — yangisini yarataman 🎨")
        return
    kb = [[_btn(f"📂 {decks.clean(r.get('title') or 'Slayd', 40)}", f"open:{r['id']}")] for r in rows]
    kb.append([_btn("🗑 Hammasini tozalash", "clr")])
    await _send(cid, f"📂 <b>Slaydlarim</b> (oxirgi {len(rows)} ta, faqat matn saqlanadi)\nOchish uchun tanlang:", {"inline_keyboard": kb})


async def _ask_clear(cid: int) -> None:
    await _send(cid, "🗑 <b>Barcha slaydlaringiz tarixi o'chiriladi.</b>\nBalans va akkaunt saqlanib qoladi. Davom etamizmi?",
                {"inline_keyboard": [[_btn("🗑 Ha, tozalash", "clr_yes"), _btn("↩️ Bekor", "clr_no")]]})


async def _do_clear(cid: int) -> None:
    n = await asyncio.to_thread(_deck_clear_sync, cid)
    st = _state(cid)
    st.update(deck=None, deck_id=None, imgs={}, awaiting=None, topic=None, sending=False)
    gc.collect()
    await _send(cid, f"✅ Tozalandi: <b>{n}</b> ta saqlangan slayd o'chirildi.\n💳 Balansingiz va akkauntingiz joyida.")


async def _show_balance(cid: int, user: dict) -> None:
    i = await _balance_info(user)
    if not i:
        await _send(cid, "⚠️ Hozir balansni o'qib bo'lmadi. Birozdan keyin qayta urinib ko'ring.", kb_main())
        return
    await _send(cid, await _credits_text(user), kb_balance(bool(i["linked"]), i))


async def _do_buy(cid: int, user: dict, product: str = "pack") -> None:
    res: Dict[str, Any] = {}
    try:
        uid, email = await _ensure_uid(user)
        fn = _deps.get("checkout")
        res = await fn(uid, "" if email.endswith("@" + TG_EMAIL_DOMAIN) else email, SITE_URL, "pack") if fn else {"error": "no_checkout"}
    except Exception as e:
        _warn("buy", f"checkout xatosi: {type(e).__name__}: {str(e)[:140]}")
        res = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
    if res.get("url"):
        info = f"💎 <b>{res.get('pages')} varaq</b>" + (f" — <b>${res.get('price')}</b>" if res.get("price") else "")
        await _send(cid, f"🧾 {info}\nTo'lovdan so'ng varaqlar darhol qo'shiladi.",
                    {"inline_keyboard": [[{"text": "💳 To'lovga o'tish", "url": res["url"]}], [_btn("⬅️ Orqaga", "bal")]]})
        return
    # xato: oddiy foydalanuvchiga mayin matn, ADMINGA — aniq sabab
    reason = str(res.get("error") or "") + ((" — " + str(res.get("hint"))) if res.get("hint") else "")
    adm = _deps.get("admin")
    if adm and adm.is_tg_admin(user.get("id")):
        await _send(cid, f"🛠 <b>To'lov sozlanmagan</b> (faqat sizga ko'rinadi)\n<code>{esc(reason[:600])}</code>\n\n"
                         "Tekshiring: LEMON_SQUEEZY_API_KEY, _STORE_ID, _VARIANT_ID, _WEBHOOK_SECRET.\n"
                         "Vaqtincha: /give ID SON bilan varaq bering.", kb_main())
        return
    await _send(cid, "⚙️ To'lov hozircha ishlamayapti. Birozdan keyin urinib ko'ring.", kb_main())


async def _link_help(cid: int) -> None:
    url = f"{SITE_URL}/?tglink={_make_token('L', cid, 0, 600)}"
    await _send(
        cid,
        "🔗 <b>Sayt akkauntini ulash</b> (Google)\n\n1️⃣ Pastdagi tugmani bosing — sayt ochiladi\n2️⃣ Google bilan kiring — ulash <b>o'zi</b> tugaydi ✅\n\n"
        "<i>Telegram ichida Google kirishga ruxsat bermasa: havolani ⋮ → «Brauzerda ochish» orqali oching.</i>\n"
        "Yoki saytda: ⚙️ Sozlamalar → <b>«Telegram botni ulash»</b> (bir bosish).",
        {"inline_keyboard": [[{"text": "🌐 Saytda ulash", "url": url}]]},
    )


def _linked_text(res: dict) -> str:
    extra = f"\n💎 Botdagi {_fmt_pages(res['moved_pages'])} pullik varaq sayt akkauntingizga ko'chirildi." if res.get("moved_pages") else ""
    return f"✅ <b>Ulandi!</b> Sayt akkauntingiz ({esc(_mask_email(res['email']))}) bilan balans endi <b>bir xil</b>.{extra}"


async def _do_link(cid: int, user: dict, code: str) -> None:
    res = await asyncio.to_thread(_link_consume_sync, user, code)
    if res.get("ok"):
        await _send(cid, _linked_text(res), kb_main())
    elif res.get("error") == "db":
        await _send(cid, "⚙️ Ulashni hozir bajarib bo'lmadi (baza sozlanmagan). Keyinroq urinib ko'ring.")
    else:
        await _send(cid, "❌ Kod noto'g'ri yoki eskirgan (10 daqiqa yashaydi). Saytda «Telegram botni ulash» ni bosib yangi kod oling.")


async def _show_settings(cid: int, user: dict, mid: Optional[int] = None) -> None:
    st = _state(cid)
    try:
        info = await asyncio.wait_for(_balance_info(user), timeout=6)
    except Exception:
        info = None
    deep = st.get("mode") == "deep"
    if info and info.get("linked"):
        acc = f"🔗 Google: <b>ulangan</b> ({esc(_mask_email(info['email']))})"
        first = [_btn("🔓 Google'ni uzish", "unl")]
    else:
        acc = "🔗 Google: <b>ulanmagan</b>"
        first = [_btn("🔗 Google ulash", "linkinfo")]
    text = f"⚙️ <b>Sozlamalar</b>\n{acc}\n🤖 AI: <b>{'🧠 Chuqur' if deep else '⚡ Tez'}</b>"
    kb = {"inline_keyboard": [
        first,
        [_btn(("✅ " if not deep else "") + "⚡ Tez", "smode:fast"), _btn(("✅ " if deep else "") + "🧠 Chuqur", "smode:deep")],
        [_btn("💳 Balans", "bal")],
    ]}
    await _edit(cid, mid, text, kb)


async def _menu_action(cid: int, user: dict, action: str) -> None:
    st = _state(cid)
    if action == "new":
        st.update(deck=None, deck_id=None, imgs={}, awaiting="topic", topic=None)
        await _send(cid, "🎨 <b>Mavzuni yozing.</b>\nMasalan: <i>«Sun'iy intellekt»</i> yoki <i>«10 ta slayd, tibbiyotda SI»</i>")
    elif action == "my":
        await _show_my(cid)
    elif action == "bal":
        await _show_balance(cid, user)
    elif action == "site":
        await _send(cid, f"🌐 {esc(SITE_URL)}", kb_main())
    elif action == "set":
        await _show_settings(cid, user)
    elif action == "about":
        await _send(cid, ABOUT, kb_main())


async def _handle_callback(cb: dict) -> None:
    cid = (cb.get("message") or {}).get("chat", {}).get("id")
    mid = (cb.get("message") or {}).get("message_id")
    user = cb.get("from") or {}
    data = str(cb.get("data") or "")
    await tg("answerCallbackQuery", callback_query_id=cb.get("id"))
    if not isinstance(cid, int) or not isinstance(user.get("id"), int) or _limited(cid, 14):
        return
    st = _state(cid)
    if data in ("credits", "bal"):
        await _show_balance(cid, user)
    elif data == "buy":
        await _do_buy(cid, user, "pack")
    elif data in ("pro", "buypro"):                      # eski xabarlardagi Pro tugmalari
        await _show_balance(cid, user)
    elif data == "linkinfo":
        await _link_help(cid)
    elif data == "dismiss":
        await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup={"inline_keyboard": []})
    elif data == "about":
        await _send(cid, ABOUT, kb_main())
    elif data.startswith("smode:"):
        st["mode"] = "deep" if data.endswith("deep") else "fast"
        await _show_settings(cid, user, mid)
    elif data == "unl":
        await _send(cid, "🔓 <b>Google akkaunt uzilsinmi?</b>\nBot o'zining Telegram akkauntiga qaytadi. Sayt akkauntingiz va uning balansi o'zgarmaydi.",
                    {"inline_keyboard": [[_btn("✅ Ha, uzish", "unl_yes"), _btn("↩️ Yo'q", "unl_no")]]})
    elif data == "unl_yes":
        ok = await asyncio.to_thread(_unlink_sync, user["id"])
        await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup={"inline_keyboard": []})
        await _send(cid, "🔓 Google akkaunt uzildi. Qayta ulash: «⚙️ Sozlamalar» → «Google akkauntni ulash»." if ok else "⚙️ Hozir bajarib bo'lmadi. Keyinroq urinib ko'ring.")
    elif data == "unl_no":
        await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup={"inline_keyboard": []})
    elif data.startswith("pptxai:") and not await _google_ok(cid, user):
        return
    elif data.startswith("pptxai:"):
        try:
            f = _files.get(int(data.split(":", 1)[1]))
        except Exception:
            f = None
        if not f or f["cid"] != cid or f["exp"] < time.time():
            await _send(cid, "⌛ Fayl muddati tugagan — qayta yuboring.")
        elif st.get("busy"):
            await _send(cid, "⏳ Oldingi so'rov hali bajarilmoqda — biroz kuting.")
        else:
            _spawn(_run_import(cid, user, "", f["name"], f["data"]))
    elif data == "my":
        await _show_my(cid)
    elif data == "clr":
        await _ask_clear(cid)
    elif data == "clr_yes":
        await _do_clear(cid)
        await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup={"inline_keyboard": []})
    elif data == "clr_no":
        await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup={"inline_keyboard": []})
        await _send(cid, "↩️ Bekor qilindi. Hech narsa o'chirilmadi.")
    elif data.startswith("open:"):
        try:
            did = int(data.split(":", 1)[1])
        except Exception:
            return
        if await _restore_deck(cid, did):
            d = st["deck"]
            await _send(cid, f"📂 <b>{esc(d['title'])}</b> ochildi\n🎞 {len(d['slides'])} ta slayd · 🎨 {esc(_theme_label(d))}\n\n{_summary(d)}\n\n<b>Yuklab oling yoki matn bilan tahrirlang:</b>", kb_done(st))
        else:
            await _send(cid, "Bu slayd topilmadi (o'chirilgan bo'lishi mumkin).")
    elif data.startswith("mode:"):
        st["mode"] = "deep" if data.endswith("deep") else "fast"
        if st.get("topic"):
            await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup=kb_count(st["mode"]))
    elif data.startswith("cnt:"):                         # eski xabarlardagi tugmalar uchun
        if st.get("busy"):
            await _send(cid, "⏳ Oldingi so'rov bajarilmoqda, biroz kuting.")
            return
        topic = st.get("topic")
        if not topic:
            await _send(cid, "Mavzu topilmadi — iltimos, mavzuni qayta yozing.")
            return
        if not await _google_ok(cid, user):
            return
        try:
            n = max(MIN_SLIDES, min(MAX_SLIDES, int(data.split(":")[1])))
        except Exception:
            n = DEFAULT_SLIDES
        await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup={"inline_keyboard": []})
        _spawn(_run_generate(cid, user, topic, n))
    elif data.startswith("dl:"):
        fmt = data.split(":", 1)[1]
        if fmt in ("pptx", "pdf", "html", "all"):
            _spawn(_send_files(cid, fmt))
    elif data == "edit":
        if not st.get("deck") and not await _restore_deck(cid):
            await _send(cid, "Avval slayd yarating — mavzuni yozing 🙂")
            return
        st["awaiting"] = "edit"
        await _send(cid, "✏️ <b>Nimani o'zgartiray?</b> Oddiy matn bilan yozing, masalan:\n"
                         "• <i>3-slaydni qisqartir</i>\n• <i>sarlavhasini o'zgartir: «Yangi nom»</i>\n• <i>yana 2 ta slayd qo'sh: xavflar va xulosa</i>\n• <i>ruscha tarjima qil</i>\n• <i>ranglarni yashil qil</i>\n\n"
                         "<i>Faqat kerakli slaydlar o'zgaradi (butun taqdimot qayta yozilmaydi). Narx: o'zgargan slaydlar soni.</i>")
    elif data == "theme":
        if st.get("deck"):
            await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup=kb_themes())
    elif data == "back":
        await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup=kb_done(st))
    elif data.startswith("th:"):
        name = data[3:]
        if st.get("deck") and decks and name in decks.THEMES:
            st["deck"]["theme"] = name
            if st.get("deck_id"):
                await asyncio.to_thread(_deck_update_sync, st["deck_id"], cid, st["deck"])
            await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup=kb_done(st))
            await _send(cid, f"🎨 Rang: <b>{esc(decks.THEMES[name]['label'])}</b> (bepul). Endi yuklab oling 👇", kb_done(st))
    elif data == "new":
        await _menu_action(cid, user, "new")


async def _handle_text(chat_id: int, user: dict, text: str) -> None:
    st = _state(chat_id)
    act = MENU.get(text.strip())
    if act:
        await _menu_action(chat_id, user, act)
        return
    if st.get("busy"):
        await _send(chat_id, "⏳ Oldingi so'rov hali bajarilmoqda — biroz kuting.")
        return
    if GREETING_RE.match(text):
        await _send_welcome(chat_id, user)
        return
    if not await _google_ok(chat_id, user):                # Google ulanmagan bo'lsa slayd yaratilmaydi
        return
    if st.get("awaiting") == "topic":                      # «🎨 Yangi slayd» bosilgan — bu xabar mavzu
        topic = " ".join(text.split())[:1500]
        st.update(awaiting=None, topic=topic)
        _spawn(_run_generate(chat_id, user, topic, _parse_count(topic) or DEFAULT_SLIDES))
        return
    if st.get("deck") or await _restore_deck(chat_id):     # AI o'zi aniqlaydi: tahrir / yangi mavzu / savol
        _spawn(_run_edit(chat_id, user, text[:1500]))
        return
    topic = " ".join(text.split())[:1500]
    st["topic"] = topic
    _spawn(_run_generate(chat_id, user, topic, _parse_count(topic) or DEFAULT_SLIDES))   # mavzu yozildi — darhol tayyorlaymiz


async def _send_welcome(chat_id: int, user: dict) -> None:
    try:
        info = await asyncio.wait_for(_balance_info(user), timeout=6)
    except Exception:
        info = None
    await _send(chat_id, _welcome_text(user.get("first_name") or "", info), kb_reply())
    if info and not info.get("linked") and not _is_admin(user):
        await _send(chat_id, "🔗 Slayd yaratish uchun avval <b>Google akkauntni ulang</b>.", {"inline_keyboard": [[_btn("🔗 Google ulash", "linkinfo")]]})


async def handle_update(data: dict) -> None:
    cb = data.get("callback_query")
    if cb:
        await _handle_callback(cb)
        return

    msg = data.get("message")
    if not msg:
        return
    chat = msg.get("chat") or {}
    if chat.get("type") != "private":          # guruh/kanalda jim turamiz
        return
    chat_id = chat.get("id")
    user = msg.get("from") or {}
    if not isinstance(chat_id, int) or user.get("is_bot") or not isinstance(user.get("id"), int):
        return
    if _limited(chat_id):
        return

    incoming = _incoming_file(msg)
    if incoming:
        if _state(chat_id).get("busy"):
            await _send(chat_id, "⏳ Oldingi so'rov hali bajarilmoqda — biroz kuting.")
        else:
            _spawn(_run_file(chat_id, user, *incoming))
        return

    text = (msg.get("text") or "").strip()
    if not text:
        await _send(chat_id, "Mavzuni <b>matn</b> ko'rinishida yozib yuboring, masalan: <i>«Sun'iy intellekt kelajagi»</i>.\nRasm yoki fayl yuborsangiz — muharrirda ochib beraman.", kb_reply())
        return

    if text.startswith("/"):
        parts = text.split(maxsplit=1)
        cmd = parts[0].split("@")[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        st = _state(chat_id)
        if cmd == "/start":
            if arg.lower().startswith("link_"):               # saytdagi «Telegram» tugmasidan: t.me/bot?start=link_KOD
                await _do_link(chat_id, user, arg[5:])
            await _send_welcome(chat_id, user)
        elif cmd == "/help":
            await _send(chat_id, HELP, kb_reply())
        elif cmd == "/new":
            await _menu_action(chat_id, user, "new")
        elif cmd in ("/my", "/slides"):
            await _show_my(chat_id)
        elif cmd in ("/clear", "/tozalash"):
            await _ask_clear(chat_id)
        elif cmd == "/mode":
            st["mode"] = "deep" if st.get("mode") != "deep" else "fast"
            await _send(chat_id, f"Rejim: <b>{'🧠 Chuqur AI' if st['mode'] == 'deep' else '⚡ Tez AI'}</b>\n"
                                 f"<i>{'Murakkab mavzular uchun, 1 slayd = 3 varaq, sekinroq.' if st['mode'] == 'deep' else 'Tez va tejamkor: 1 slayd = 1 varaq.'}</i>")
        elif cmd in ("/credits", "/kredit", "/kreditlar", "/balance", "/balans"):
            await _show_balance(chat_id, user)
        elif cmd == "/buy":
            await _do_buy(chat_id, user, "pack")
        elif cmd == "/pro":
            await _show_balance(chat_id, user)
        elif cmd == "/id":
            await _send(chat_id, f"🆔 Sizning Telegram ID: <code>{int(user['id'])}</code>")
        elif cmd in ADMIN_CMDS or cmd == "/admin":
            await _admin_command(chat_id, user, cmd, arg)
        elif cmd == "/link":
            if arg:
                await _do_link(chat_id, user, arg)
            else:
                await _link_help(chat_id)
        elif cmd == "/unlink":
            ok = await asyncio.to_thread(_unlink_sync, user["id"])
            await _send(chat_id, "🔓 Sayt akkaunti uzildi. Bot endi o'zining Telegram akkauntidan foydalanadi." if ok else "⚙️ Hozir bajarib bo'lmadi.")
        elif cmd == "/site":
            await _menu_action(chat_id, user, "site")
        elif cmd in ("/settings", "/sozlamalar"):
            await _menu_action(chat_id, user, "set")
        elif cmd in ("/about", "/bot"):
            await _menu_action(chat_id, user, "about")
        else:
            await _send(chat_id, "Bunday buyruq mavjud emas.", kb_reply())
        return

    if re.fullmatch(r"(?i)\s*admin(\s*panel)?\s*[!.]?\s*", text):          # «admin» — faqat haqiqiy adminga menyu ochiladi
        if _is_admin(user):
            await _admin_command(chat_id, user, "/admin", "")
            return
        # admin bo'lmasa — oddiy matn sifatida davom etadi (hech narsa oshkor bo'lmaydi)
    await _handle_text(chat_id, user, text)


async def _warm_account(user: dict) -> None:
    try:
        await _ensure_uid(user)
    except Exception as e:
        _warn("warm", f"akkaunt tayyorlanmadi: {str(e)[:120]}")


async def _safe_handle(data: dict) -> None:
    try:
        await asyncio.wait_for(handle_update(data), timeout=60)
    except asyncio.TimeoutError:
        _warn("timeout", "update ishlovi vaqtdan oshdi")
    except Exception as e:
        _warn("handle", f"update xatosi: {type(e).__name__}: {str(e)[:150]}")


@router.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request, background: BackgroundTasks):
    if not ENABLED:
        raise HTTPException(404)
    got = request.headers.get("x-telegram-bot-api-secret-token", "")
    if not hmac.compare_digest(got.encode(), SECRET.encode()):
        raise HTTPException(403)
    try:
        data = await request.json()
    except Exception:
        return {"ok": True}
    if not isinstance(data, dict) or _is_dup(data.get("update_id")):
        return {"ok": True}
    background.add_task(_safe_handle, data)      # darhol 200 — Telegram qayta yubormaydi
    return {"ok": True}


@router.get("/api/telegram/status")
async def telegram_status():
    """Diagnostika: bot yoqilganmi, webhook to'g'ri o'rnatilganmi (maxfiy ma'lumotsiz)."""
    if not ENABLED:
        return {"enabled": False, "hint": "TELEGRAM_BOT_TOKEN yo'q yoki noto'g'ri (format: 123456:ABC...)"}
    info = await tg("getWebhookInfo") or {}
    want = f"{SITE_URL}{WEBHOOK_PATH}"
    return {
        "enabled": True, "mode": _mode_now, "webhook_ok": info.get("url") == want, "webhook_url_set": bool(info.get("url")),
        "pending": info.get("pending_update_count"), "last_error": str(info.get("last_error_message") or "")[:120] or None,
        "site_url": SITE_URL, "decks": decks is not None,
    }


# ----------------------------------------------------------------------------------------------
# Mini App: Telegram orqali kirish (initData tekshiruvi + Supabase sessiyasi)
# ----------------------------------------------------------------------------------------------
def verify_init_data(init_data: str, max_age: int = 86400) -> Optional[dict]:
    """Telegram WebApp initData imzosini tekshiradi. To'g'ri bo'lsa user dict, aks holda None."""
    try:
        if not init_data or len(init_data) > 4096:
            return None
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        got = pairs.pop("hash", "")
        if not got:
            return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, got):
            return None
        age = time.time() - int(pairs.get("auth_date", "0"))
        if age > max_age or age < -300:
            return None
        user = json.loads(pairs.get("user", "{}"))
        if not isinstance(user, dict) or not isinstance(user.get("id"), int):
            return None
        return user
    except Exception:
        return None


def _login_sync(user: dict) -> dict:
    """Mini App kirishi. Telegram sayt akkauntiga ulangan bo'lsa — SHU akkaunt sessiyasi (balans bir xil)."""
    tid = int(user["id"])
    linked = _linked_sync(tid)
    if linked:
        _uid, email = linked
        try:
            link = _sb().auth.admin.generate_link({"type": "magiclink", "email": email})
            hashed = getattr(getattr(link, "properties", None), "hashed_token", None)
            if hashed:
                return {"token_hash": hashed, "type": "magiclink", "email": email, "name": ""}
        except Exception as e:
            _warn("login-linked", f"ulangan akkaunt bilan kirib bo'lmadi, Telegram akkauntiga o'tildi: {str(e)[:120]}")
    r = _provision_sync(user)
    if r.get("error"):
        return {"error": r["error"]}
    if not r.get("hashed"):
        return {"error": "auth_unavailable"}
    return {"token_hash": r["hashed"], "type": "magiclink", "email": r["email"], "name": r["name"]}


async def _web_user(request: Request) -> Optional[Tuple[str, str]]:
    """Sayt sessiyasi (Supabase access token) -> (user_id, email) yoki None."""
    try:
        body = await request.json()
    except Exception:
        return None
    token = str((body or {}).get("token") or "").strip()
    sb = _sb()
    if not token or token == "dev-token" or not sb:
        return None
    try:
        res = await asyncio.to_thread(sb.auth.get_user, token)
        if res and res.user:
            return str(res.user.id), str(res.user.email or "")
    except Exception:
        pass
    return None


@router.post("/api/telegram/link-code")
async def telegram_link_code(request: Request):
    """Saytdagi «✈️ Telegram» tugmasi: bir martalik kod (10 daqiqa) + botni ochish havolasi."""
    if not ENABLED:
        return JSONResponse({"error": "telegram_disabled"}, status_code=503)
    me = await _web_user(request)
    if not me or not me[1]:
        return JSONResponse({"error": "login_required"}, status_code=401)
    if me[1].endswith("@" + TG_EMAIL_DOMAIN):
        return JSONResponse({"error": "already_telegram"}, status_code=400)
    try:
        code = await asyncio.to_thread(_link_code_sync, me[0], me[1])
    except Exception as e:
        _db_warn(e)
        return JSONResponse({"error": "db_not_ready"}, status_code=503)
    uname = await _bot_username()
    return JSONResponse({"code": code, "bot": uname, "expires_in": LINK_TTL,
                         "url": f"https://t.me/{uname}?start=link_{code}" if uname else ""}, headers={"Cache-Control": "no-store"})


@router.post("/api/telegram/link-status")
async def telegram_link_status(request: Request):
    if not ENABLED:
        return JSONResponse({"linked": False, "enabled": False})
    me = await _web_user(request)
    if not me:
        return JSONResponse({"error": "login_required"}, status_code=401)
    linked = False
    try:
        sb = _sb()
        r = await asyncio.to_thread(lambda: sb.table("tg_links").select("tg_id").eq("user_id", me[0]).limit(1).execute())
        linked = bool(r.data)
    except Exception:
        pass
    return JSONResponse({"linked": linked, "enabled": True}, headers={"Cache-Control": "no-store"})


_used_links: "OrderedDict[str, float]" = OrderedDict()


@router.post("/api/telegram/link-complete")
async def telegram_link_complete(request: Request):
    """Botdagi «Saytda ulash» havolasi (?tglink=TOKEN): sayt Google bilan kirgach shu yerga murojaat qiladi — ulash o'zi tugaydi."""
    if not ENABLED:
        return JSONResponse({"error": "telegram_disabled"}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        body = {}
    key = str((body or {}).get("link") or "")
    ids = _check_token("L", key)
    if not ids:
        return JSONResponse({"error": "expired"}, status_code=410)
    if key in _used_links:
        return JSONResponse({"error": "used"}, status_code=409)
    me = await _web_user(request)
    if not me or not me[1]:
        return JSONResponse({"error": "login_required"}, status_code=401)
    if me[1].endswith("@" + TG_EMAIL_DOMAIN):
        return JSONResponse({"error": "already_telegram"}, status_code=400)
    res = await asyncio.to_thread(_link_apply_sync, ids[0], me[0], me[1])
    if not res.get("ok"):
        return JSONResponse({"error": res.get("error") or "link_failed"}, status_code=503)
    _used_links[key] = time.time()
    while len(_used_links) > 500:
        _used_links.popitem(last=False)
    await _send(ids[0], _linked_text(res), kb_main())
    return JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})


@router.get("/api/telegram/file")
async def telegram_file(t: str = ""):
    """Botga yuborilgan faylni (RAM'da, 15 daqiqa) muharrirga beradi. Havola imzolangan va faqat shu chatga tegishli."""
    if not ENABLED:
        return JSONResponse({"error": "disabled"}, status_code=503)
    ids = _check_token("F", t)
    f = _files.get(ids[1]) if ids else None
    if not ids or not f or f["cid"] != ids[0] or f["exp"] < time.time():
        return JSONResponse({"error": "expired"}, status_code=410)
    return Response(content=f["data"], media_type="application/octet-stream",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "X-File-Name": quote(f["name"])})


@router.get("/api/telegram/deck-file")
async def telegram_deck_file(t: str = ""):
    """Botdagi «Muharrirda ochish»: slaydni bazadagi qisqa JSON'dan RAM'da PPTX qilib beradi (diskka yozilmaydi);
    sayt uni editorga o'zi import qiladi."""
    if not ENABLED or decks is None:
        return JSONResponse({"error": "disabled"}, status_code=503)
    ids = _check_token("D", t)
    if not ids:
        return JSONResponse({"error": "expired"}, status_code=410)
    deck_id, tid = ids
    row = await asyncio.to_thread(_deck_get_sync, tid, deck_id)
    deck = decks.normalize_deck(row.get("deck"), MAX_SLIDES + 10, row.get("title") or "") if row else None
    if not deck:
        return JSONResponse({"error": "not_found"}, status_code=404)
    async with _gen_sem:
        imgs = await _fetch_images(deck, {}, True)
        _name, data, mime = await asyncio.to_thread(decks.export, deck, _img_index(deck, imgs), "pptx", row.get("lang") or "uz")
    imgs = None
    return Response(content=data, media_type=mime.split(";")[0],
                    headers={"Cache-Control": "no-store", "Content-Disposition": 'inline; filename="slayd.pptx"'})


@router.post("/api/telegram/auth")
async def telegram_auth(request: Request):
    if not ENABLED:
        return JSONResponse({"error": "telegram_disabled"}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "bad_request"}, status_code=400)
    user = verify_init_data(str((body or {}).get("init_data") or ""))
    if not user:
        return JSONResponse({"error": "invalid_init_data"}, status_code=401)
    try:
        res = await asyncio.to_thread(_login_sync, user)
    except Exception as e:
        _warn("login", f"login xatosi: {type(e).__name__}: {str(e)[:150]}")
        return JSONResponse({"error": "login_failed"}, status_code=502)
    if res.get("error"):
        return JSONResponse(res, status_code=409 if res["error"] == "account_conflict" else 503)
    return JSONResponse(res, headers={"Cache-Control": "no-store"})


# ----------------------------------------------------------------------------------------------
# Ulanish: webhook (+ nazorat) yoki long-polling (zaxira)
# ----------------------------------------------------------------------------------------------
_mode_now = "off"
ALLOWED = ["message", "callback_query"]


async def _set_commands() -> None:
    await tg("setMyCommands", commands=[
        {"command": "start", "description": "Bosh menyu"},
        {"command": "new", "description": "Yangi slayd yaratish"},
        {"command": "my", "description": "Slaydlarim"},
        {"command": "clear", "description": "Slaydlarimni tozalash"},
        {"command": "credits", "description": "Balans"},
        {"command": "link", "description": "Google akkauntni ulash"},
        {"command": "settings", "description": "Sozlamalar"},
        {"command": "mode", "description": "Tez ⚡ / Chuqur 🧠 AI"},
        {"command": "help", "description": "Yordam"},
    ])
    await tg("setChatMenuButton", menu_button={"type": "web_app", "text": "🚀 Muharrir", "web_app": {"url": _app_url()}})


async def _register_webhook(attempts: int = 4) -> bool:
    if not SITE_URL.startswith("https://") or "localhost" in SITE_URL or "127.0.0.1" in SITE_URL:
        _warn("https", "PUBLIC_BASE_URL https:// bo'lishi kerak — webhook o'rnatilmadi")
        return False
    url = f"{SITE_URL}{WEBHOOK_PATH}"
    for attempt in range(attempts):
        ok = await tg("setWebhook", url=url, secret_token=SECRET, max_connections=20, allowed_updates=ALLOWED)
        if ok:
            await _set_commands()
            print(f"[TG] bot tayyor — webhook: {url}")
            return True
        await asyncio.sleep(2 * (attempt + 1))
    return False


async def _poll_loop() -> None:
    """Webhook o'rnatilmasa ham bot javob bersin: getUpdates (long-polling)."""
    global _mode_now
    await tg("deleteWebhook", drop_pending_updates=False)
    await _set_commands()
    _mode_now = "polling"
    print("[TG] bot tayyor — long-polling rejimi")
    offset = 0
    while True:
        try:
            r = await _http().post(f"{API}/getUpdates", json={"offset": offset, "timeout": 25, "allowed_updates": ALLOWED},
                                   timeout=httpx.Timeout(40.0, connect=8.0))
            j = r.json()
            if not j.get("ok"):
                _warn("poll", f"getUpdates: {str(j.get('description'))[:120]}")
                await asyncio.sleep(5)
                continue
            for upd in j.get("result") or []:
                offset = max(offset, int(upd.get("update_id", 0)) + 1)
                if isinstance(upd, dict) and not _is_dup(upd.get("update_id")):
                    _spawn(_safe_handle(upd))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _warn("poll-net", f"polling xatosi: {type(e).__name__}")
            await asyncio.sleep(4)


async def _watchdog() -> None:
    """Har 10 daqiqada webhook hali o'rnatilganini tekshiradi; yo'qolgan bo'lsa qayta o'rnatadi."""
    want = f"{SITE_URL}{WEBHOOK_PATH}"
    while True:
        await asyncio.sleep(600)
        try:
            info = await tg("getWebhookInfo") or {}
            if info.get("url") != want:
                _warn("wd", "webhook yo'qolgan — qayta o'rnatilmoqda")
                await _register_webhook(2)
            elif info.get("last_error_message"):
                _warn("wd-err", f"webhook xatosi: {str(info.get('last_error_message'))[:120]}")
        except Exception as e:
            _warn("wd-ex", f"watchdog: {str(e)[:100]}")


async def _bootstrap() -> None:
    global _mode_now
    if MODE == "polling" or (MODE == "auto" and not _env("PUBLIC_BASE_URL")):
        # PUBLIC_BASE_URL yo'q (masalan, lokal kompyuter) — webhook Render'ning webhookini buzmasligi uchun polling
        await _poll_loop()
        return
    ok = await _register_webhook()
    if ok:
        _mode_now = "webhook"
        t = asyncio.create_task(_watchdog())
        _bg.add(t)
        t.add_done_callback(_bg.discard)
        return
    if MODE == "webhook":
        _warn("webhook", "setWebhook bajarilmadi — TELEGRAM_BOT_TOKEN va PUBLIC_BASE_URL ni tekshiring")
        return
    _warn("fallback", "webhook o'rnatilmadi -> long-polling rejimiga o'tildi")
    await _poll_loop()


async def startup() -> None:
    if not ENABLED:
        print("[TG] TELEGRAM_BOT_TOKEN yo'q yoki noto'g'ri — bot o'chiq")
        return
    if decks is None:
        print("[TG] ⚠️ tg_decks yuklanmadi — bot slayd yarata olmaydi (requirements.txt o'rnatilganmi?)")
    t = asyncio.create_task(_bootstrap())          # startni bloklamaydi
    _bg.add(t)
    t.add_done_callback(_bg.discard)


async def shutdown() -> None:
    global _client
    for t in list(_bg):
        t.cancel()
    if _client is not None and not _client.is_closed:
        try:
            await _client.aclose()
        except Exception:
            pass
    _client = None
