"""
Slide Studio — Telegram bot (v44).  FastAPI ichida ishlaydi.

Bot nima qiladi (saytdagi kabi):
  1) Foydalanuvchi mavzuni (yoki batafsil topshiriqni) matn qilib yozadi.
  2) Bot slayd sonini so'raydi (yoki matndagi "10 ta slayd" ni o'zi oladi) va AI slaydlarni yozadi.
  3) Tayyor bo'lgach foydalanuvchi XOHLAGAN formatni bosadi: PPTX / PDF / HTML yoki "Hammasi" (3 ta fayl birdan).
  4) Xohlasa "✏️ Tahrirlash" — oddiy matn bilan AI'ga aytadi (saytdagi chat kabi); "🎨 Rang" — mavzu rangi (bepul).
  Telegram akkaunt = sayt akkaunti (tg<ID>@t.me): kreditlar (AI varaqlar) Mini App va bot uchun BITTA.

Ulanish usullari (TELEGRAM_MODE):  auto (standart) | webhook | polling
  auto: avval webhook; o'rnatilmasa avtomatik long-polling ga o'tadi (bot baribir javob beradi).

Kerakli env:  TELEGRAM_BOT_TOKEN (majburiy), PUBLIC_BASE_URL (https://...), TELEGRAM_WEBHOOK_SECRET (ixtiyoriy)
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import json
import os
import re
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, quote

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

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
WELCOME = (
    "Salom! Men <b>Slide Studio AI</b> botiman 🎨\n"
    "Soniyalar ichida professional taqdimot tayyorlab beraman — xuddi saytdagidek.\n\n"
    "<b>Qanday ishlaydi?</b>\n"
    "1️⃣ Mavzuni yozing, masalan: <i>«Sun'iy intellekt kelajagi»</i>\n"
    "    (xohlasangiz batafsil: <i>«10 ta slayd, tibbiyotda SI, rasmsiz»</i>)\n"
    "2️⃣ AI slaydlarni yozadi\n"
    "3️⃣ Xohlagan formatda yuklab oling: <b>PPTX · PDF · HTML</b> yoki <b>hammasini birdan</b> 📦\n\n"
    "Tayyor bo'lgach matn bilan tahrirlashingiz ham mumkin: <i>«3-slaydni qisqartir»</i>."
)
HELP = (
    "<b>Buyruqlar</b>\n"
    "/start — bosh menyu\n"
    "/new — yangi taqdimot\n"
    "/mode — Tez ⚡ / Chuqur 🧠 AI rejimi\n"
    "/credits — kreditlarim (AI varaqlar)\n"
    "/site — saytga havola\n\n"
    "Mavzuni oddiy xabar qilib yozing. Slayd soni, rang, rasm haqida xohishingizni ham yozishingiz mumkin.\n"
    "Narx: <b>1 slayd = 1 varaq</b> (Chuqur AI — 3 baravar). Kuniga bepul varaqlar beriladi."
)
GREETING_RE = re.compile(r"^(salom|assalomu\s*alaykum|assalom|hello|hi|hey|привет|здравствуй\w*|qalay|nima gap|start|boshla)[\s!.,?]*$", re.I)
COUNT_RE = re.compile(r"(\d{1,2})\s*(?:ta|tadan|ta\.)?\s*[-–]?\s*(?:slayd\w*|slaid\w*|slide\w*|слайд\w*|varaq\w*|sahifa\w*|page\w*)", re.I)
MIN_SLIDES, MAX_SLIDES = 3, 20


def _app_url(topic: str = "") -> str:
    if topic:
        return f"{SITE_URL}/?src=tg&topic={quote(topic[:200], safe='')}"
    return f"{SITE_URL}/?src=tg"


def _btn(text: str, data: str) -> dict:
    return {"text": text, "callback_data": data}


def kb_main(topic: str = "") -> dict:
    return {"inline_keyboard": [
        [{"text": "🚀 Muharrirda ochish (Mini App)", "web_app": {"url": _app_url(topic)}}],
        [{"text": "🌐 Saytga o'tish", "url": SITE_URL}, _btn("💳 Kreditlarim", "credits")],
    ]}


def kb_count(mode: str) -> dict:
    return {"inline_keyboard": [
        [_btn("5 slayd", "cnt:5"), _btn("8 slayd", "cnt:8"), _btn("10 slayd", "cnt:10"), _btn("12 slayd", "cnt:12")],
        [_btn(("✅ " if mode == "fast" else "") + "⚡ Tez AI", "mode:fast"), _btn(("✅ " if mode == "deep" else "") + "🧠 Chuqur AI", "mode:deep")],
    ]}


def kb_done(topic: str = "") -> dict:
    return {"inline_keyboard": [
        [_btn("📊 PPTX", "dl:pptx"), _btn("📕 PDF", "dl:pdf"), _btn("🌐 HTML", "dl:html")],
        [_btn("📦 Hammasi — 3 ta fayl birdan", "dl:all")],
        [_btn("✏️ Tahrirlash", "edit"), _btn("🎨 Rang", "theme"), _btn("🆕 Yangi", "new")],
        [{"text": "🚀 Muharrirda ochish (sayt)", "web_app": {"url": _app_url(topic)}}],
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


def _state(chat_id: int) -> dict:
    now = time.time()
    st = _chats.pop(chat_id, None)
    if st is None or now - st.get("ts", 0) > CHAT_TTL:
        st = {"mode": (st or {}).get("mode", "fast"), "busy": False}
    st["ts"] = now
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


_uids: "OrderedDict[int, str]" = OrderedDict()


def _ensure_uid_sync(user: dict) -> Tuple[str, str]:
    tid = int(user["id"])
    email = _tg_email(tid)
    if tid in _uids:
        return _uids[tid], email
    sb = _sb()
    uid = ""
    if sb:
        res = sb.table("user_usage").select("user_id").eq("email", email).limit(1).execute()
        if res.data:
            uid = str(res.data[0]["user_id"])
    if not uid:
        r = _provision_sync(user)
        if r.get("error"):
            raise RuntimeError(r["error"])
        uid = r["uid"]
    _uids[tid] = uid
    while len(_uids) > 5000:
        _uids.popitem(last=False)
    return uid, email


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


async def _credits_text(user: dict) -> str:
    try:
        uid, email = await _ensure_uid(user)
        u = await asyncio.to_thread(_usage_now_sync, uid, email)
        p = _deps["usage_payload"](u)
    except Exception as e:
        _warn("credits", f"kredit o'qish xatosi: {str(e)[:120]}")
        return "⚠️ Hozir balansni o'qib bo'lmadi. Birozdan keyin qayta urinib ko'ring."
    m = p.get("modes") or {}
    fast, deep = m.get("fast") or {}, m.get("deep") or {}
    lines = [
        "💳 <b>Kreditlarim</b>\n",
        f"⚡ Tez AI: <b>{_fmt_pages(fast.get('pages_exact', 0))}</b> varaq",
        f"🧠 Chuqur AI: <b>{_fmt_pages(deep.get('pages_exact', 0))}</b> varaq",
        f"\n🎁 Bepul (kunlik): {_fmt_pages(fast.get('free_pages', 0))}  ·  💎 Pullik: {_fmt_pages(fast.get('paid_pages', 0))}",
    ]
    w = _fmt_wait(p.get("next_reset_in_seconds"))
    if w and p.get("window_started"):
        lines.append(f"🔄 Bepul varaqlar yangilanishiga: {w}")
    lines.append("\n<i>1 slayd = 1 varaq. Ko'proq varaq kerak bo'lsa — saytda «Sotib olish».</i>")
    return "\n".join(lines)


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
You receive the CURRENT DECK (json) and the user's NEW MESSAGE. Decide the intent:
1) "edit"      — the user wants to change the deck (shorten, rewrite, translate, add/remove/reorder slides, change colours, fix a fact...).
   Return {"intent":"edit","reply":"1-2 short sentences saying what you changed","deck":{...the COMPLETE updated deck in the same schema...}}
2) "new_topic" — the message is clearly a NEW presentation topic unrelated to the current deck.
   Return {"intent":"new_topic"}
3) "chat"      — a question or small talk about the deck, not requesting a change.
   Return {"intent":"chat","reply":"helpful answer, max 4 sentences"}
DECK SCHEMA: {"title","subtitle","theme":"ocean|violet|forest|sunset|rose|slate|teal","slides":[{"layout":"title|bullets|cards|stats|quote|closing", ...}]}
 - title/closing: title, subtitle · bullets: title, bullets[3-5], image · cards: title, cards[{heading,text}] (2-4) · stats: title, stats[{value,label}] (2-4) · quote: text, author
 - first slide is "title", last slide is "closing". Keep untouched slides EXACTLY as they are. "image" is a short English search query or "".
 - Keep the language of the deck unless asked to translate. No emoji, no markdown symbols. Reply in the user's language.
"""

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
    return (
        "😔 <b>Varaqlaringiz tugadi.</b>\n"
        + (f"Bepul varaqlar yangilanishiga: <b>{w}</b>.\n" if w else "Bepul varaqlar 24 soatda yangilanadi.\n")
        + "Hoziroq davom etish uchun saytda «Sotib olish» orqali varaq oling."
    )


async def _run_generate(chat_id: int, user: dict, topic: str, n: int) -> None:
    st = _state(chat_id)
    st["busy"] = True
    msg_id: Optional[int] = None
    try:
        mode = st.get("mode", "fast")
        uid, email = await _ensure_uid(user)
        usage = await asyncio.to_thread(_usage_now_sync, uid, email)
        if usage.get("blocked"):
            await _send(chat_id, "⛔ Akkauntingiz bloklangan.")
            return
        afford = int(_deps["total_credits"](usage) // _page_units(mode))
        if afford < 1:
            await _send(chat_id, _no_credit_text(mode, usage), kb_main())
            return
        note = ""
        if n > afford:
            note = f"\n\nℹ️ Balansingizda {afford} varaq bor — shuncha slayd yaratiladi."
            n = max(1, afford)
        n = max(1, n)
        sent = await _send(chat_id, f"⏳ <b>AI slaydlarni yozmoqda…</b>\n{n} ta slayd · {'🧠 Chuqur' if mode == 'deep' else '⚡ Tez'} AI"
                                    + ("\n<i>Chuqur rejim 1–2 daqiqa olishi mumkin.</i>" if mode == "deep" else "") + note)
        msg_id = (sent or {}).get("message_id") if isinstance(sent, dict) else None
        await tg("sendChatAction", chat_id=chat_id, action="typing")

        async with _gen_sem:
            deck, tokens, tries = None, 0, 0
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
            await _edit(chat_id, msg_id, f"🖼 <b>Rasmlar tanlanmoqda…</b>\n«{esc(deck['title'])}» — {len(deck['slides'])} ta slayd")
            await tg("sendChatAction", chat_id=chat_id, action="upload_photo")
            imgs = await _fetch_images(deck, {}, imgs_on)

        usage2, charged = await _charge(uid, email, len(deck["slides"]), tokens, mode, {"src": "telegram", "slides": len(deck["slides"]), "topic": topic[:80]})
        st.update(deck=deck, imgs=imgs, topic=topic, awaiting=None, uid=uid, email=email, lang=_guess_lang(topic))
        left = _pages_left(usage2, mode)
        spent = charged / _page_units(mode)
        text = (
            f"✅ <b>{esc(deck['title'])}</b> tayyor!\n"
            f"🎞 {len(deck['slides'])} ta slayd · 🎨 {esc(_theme_label(deck))}\n\n"
            f"{_summary(deck)}\n\n"
            f"💳 Sarflandi: <b>{_fmt_pages(spent)}</b> varaq · Qoldi: <b>{_fmt_pages(left)}</b>{note}\n\n"
            "<b>Qaysi formatda yuklab olasiz?</b>"
        )
        await _edit(chat_id, msg_id, text, kb_done(topic))
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
        deck = st.get("deck")
        uid, email = await _ensure_uid(user)
        usage = await asyncio.to_thread(_usage_now_sync, uid, email)
        if _deps["total_credits"](usage) < _deps["MODES"][mode]["chat"]:
            await _send(chat_id, _no_credit_text(mode, usage), kb_main())
            return
        sent = await _send(chat_id, "✏️ <b>AI o'qimoqda…</b>")
        msg_id = (sent or {}).get("message_id") if isinstance(sent, dict) else None
        await tg("sendChatAction", chat_id=chat_id, action="typing")
        async with _gen_sem:
            data, tokens = await _ai_json(EDIT_SYSTEM, f"CURRENT DECK:\n{_deck_for_prompt(deck)}\n\nNEW MESSAGE:\n{text}", mode)
        intent = str((data or {}).get("intent") or "").lower()
        if intent == "new_topic":
            await _edit(chat_id, msg_id, "🆕 Yangi mavzu deb tushundim.")
            st.update(deck=None, imgs={}, awaiting=None, topic=text[:1500])
            await _ask_count(chat_id, user, text)
            return
        if intent == "chat" or not isinstance(data, dict) or not isinstance(data.get("deck"), dict):
            usage2, _ = await _charge(uid, email, 0, tokens, mode, {"src": "telegram", "kind": "chat"})
            reply = decks.clean((data or {}).get("reply"), 800) or "Tushunmadim, iltimos aniqroq yozing — masalan: «3-slaydni qisqartir»."
            await _edit(chat_id, msg_id, f"💬 {esc(reply)}", kb_done(st.get("topic", "")))
            return
        new = decks.normalize_deck(data["deck"], len(deck["slides"]) + 8, deck.get("title", ""))
        if not new:
            await _edit(chat_id, msg_id, "⚠️ O'zgartirishni qo'llab bo'lmadi. Hech narsa yechilmadi — boshqacha yozib ko'ring.", kb_done(st.get("topic", "")))
            return
        changed = _changed_slides(deck, new)
        afford = int(_deps["total_credits"](usage) // _page_units(mode))
        if changed > afford:
            await _edit(chat_id, msg_id, f"😔 Bu o'zgarish {changed} varaq talab qiladi, sizda {afford} varaq bor. Kichikroq o'zgarish so'rang yoki varaq oling.", kb_done(st.get("topic", "")))
            return
        imgs = await _fetch_images(new, st.get("imgs") or {}, True)
        usage2, charged = await _charge(uid, email, changed, tokens, mode, {"src": "telegram", "kind": "edit", "changed": changed})
        st.update(deck=new, imgs=imgs, awaiting=None)
        reply = decks.clean(data.get("reply"), 500)
        left = _pages_left(usage2, mode)
        await _edit(
            chat_id, msg_id,
            f"✅ <b>Yangilandi</b>" + (f" — {esc(reply)}" if reply else "") + f"\n🎞 {len(new['slides'])} ta slayd · 🎨 {esc(_theme_label(new))}\n\n{_summary(new)}\n\n"
            f"💳 Sarflandi: <b>{_fmt_pages(charged / _page_units(mode))}</b> varaq · Qoldi: <b>{_fmt_pages(left)}</b>\n\n<b>Yuklab olish:</b>",
            kb_done(st.get("topic", "")),
        )
    except asyncio.TimeoutError:
        await _edit(chat_id, msg_id, "⌛ AI juda uzoq o'ylandi. Hech narsa yechilmadi — qayta urinib ko'ring.", kb_done(st.get("topic", "")))
    except Exception as e:
        _warn("edit", f"tahrir xatosi: {type(e).__name__}: {str(e)[:160]}")
        await _edit(chat_id, msg_id, "⚠️ Xatolik yuz berdi. Hech narsa yechilmadi.", kb_done(st.get("topic", "")))
    finally:
        st["busy"] = False


async def _send_files(chat_id: int, fmt: str) -> None:
    st = _state(chat_id)
    deck = st.get("deck")
    if not deck:
        await _send(chat_id, "Bu taqdimot eskirgan (bot qayta ishga tushgan bo'lishi mumkin). Mavzuni qayta yozing 🙂")
        return
    if st.get("sending"):
        return
    st["sending"] = True
    try:
        await tg("sendChatAction", chat_id=chat_id, action="upload_document")
        imgs = _img_index(deck, st.get("imgs") or {})
        lang = st.get("lang", "uz")
        if fmt == "all":
            files = await asyncio.to_thread(decks.export_all, deck, imgs, lang)
        else:
            files = [await asyncio.to_thread(decks.export, deck, imgs, fmt, lang)]
        ok_all = True
        for i, (name, data, mime) in enumerate(files):
            cap = f"📦 <b>{esc(deck['title'])}</b>" if (i == 0 and fmt == "all") else (f"<b>{esc(deck['title'])}</b>" if len(files) == 1 else "")
            if fmt != "all" and name.endswith(".html"):
                cap += "\n<i>Brauzerda oching: ← → tugmalar yoki barmoq bilan suring, F — to'liq ekran.</i>"
            ok = await tg_send_document(chat_id, name, data, mime, cap)
            ok_all = ok_all and ok
        if not ok_all:
            await _send(chat_id, "⚠️ Faylni yuborib bo'lmadi. Qayta urinib ko'ring.")
        else:
            await _send(chat_id, "Yana format kerakmi yoki o'zgartirish qilamizmi?", kb_done(st.get("topic", "")))
    except Exception as e:
        _warn("files", f"fayl yig'ish xatosi: {type(e).__name__}: {str(e)[:160]}")
        await _send(chat_id, "⚠️ Faylni tayyorlashda xatolik. Qayta urinib ko'ring.")
    finally:
        st["sending"] = False


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
async def _handle_callback(cb: dict) -> None:
    cid = (cb.get("message") or {}).get("chat", {}).get("id")
    mid = (cb.get("message") or {}).get("message_id")
    user = cb.get("from") or {}
    data = str(cb.get("data") or "")
    await tg("answerCallbackQuery", callback_query_id=cb.get("id"))
    if not isinstance(cid, int) or not isinstance(user.get("id"), int) or _limited(cid, 14):
        return
    st = _state(cid)
    if data == "credits":
        await _send(cid, await _credits_text(user), kb_main())
    elif data.startswith("mode:"):
        st["mode"] = "deep" if data.endswith("deep") else "fast"
        if st.get("topic"):
            await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup=kb_count(st["mode"]))
    elif data.startswith("cnt:"):
        if st.get("busy"):
            await _send(cid, "⏳ Oldingi so'rov bajarilmoqda, biroz kuting.")
            return
        topic = st.get("topic")
        if not topic:
            await _send(cid, "Mavzu topilmadi — iltimos, mavzuni qayta yozing.")
            return
        try:
            n = max(MIN_SLIDES, min(MAX_SLIDES, int(data.split(":")[1])))
        except Exception:
            n = 8
        await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup={"inline_keyboard": []})
        _spawn(_run_generate(cid, user, topic, n))
    elif data.startswith("dl:"):
        fmt = data.split(":", 1)[1]
        if fmt in ("pptx", "pdf", "html", "all"):
            _spawn(_send_files(cid, fmt))
    elif data == "edit":
        if not st.get("deck"):
            await _send(cid, "Avval taqdimot yarating — mavzuni yozing 🙂")
            return
        st["awaiting"] = "edit"
        await _send(cid, "✏️ <b>Nimani o'zgartiray?</b> Oddiy matn bilan yozing, masalan:\n"
                         "• <i>3-slaydni qisqartir</i>\n• <i>yana 2 ta slayd qo'sh: xavflar va xulosa</i>\n• <i>ruscha tarjima qil</i>\n• <i>ranglarni yashil qil</i>\n\n"
                         "<i>Narx: o'zgargan slaydlar soni (kamida bitta savol-javob).</i>")
    elif data == "theme":
        if st.get("deck"):
            await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup=kb_themes())
    elif data == "back":
        await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup=kb_done(st.get("topic", "")))
    elif data.startswith("th:"):
        name = data[3:]
        if st.get("deck") and decks and name in decks.THEMES:
            st["deck"]["theme"] = name
            await tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup=kb_done(st.get("topic", "")))
            await _send(cid, f"🎨 Rang: <b>{esc(decks.THEMES[name]['label'])}</b> (bepul). Endi yuklab oling 👇", kb_done(st.get("topic", "")))
    elif data == "new":
        st.update(deck=None, imgs={}, awaiting=None, topic=None)
        await _send(cid, "🆕 Yangi taqdimot uchun mavzuni yozing.")


async def _handle_text(chat_id: int, user: dict, text: str) -> None:
    st = _state(chat_id)
    if st.get("busy"):
        await _send(chat_id, "⏳ Oldingi so'rov hali bajarilmoqda — biroz kuting.")
        return
    if GREETING_RE.match(text):
        await _send(chat_id, WELCOME, kb_main())
        return
    if st.get("deck"):
        _spawn(_run_edit(chat_id, user, text[:1500]))          # AI o'zi aniqlaydi: tahrir / yangi mavzu / savol
        return
    topic = " ".join(text.split())[:1500]
    n = _parse_count(topic)
    if n:
        st["topic"] = topic
        _spawn(_run_generate(chat_id, user, topic, n))
    else:
        await _ask_count(chat_id, user, topic)


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

    text = (msg.get("text") or "").strip()
    if not text:
        await _send(chat_id, "Mavzuni <b>matn</b> ko'rinishida yozib yuboring, masalan: <i>«Sun'iy intellekt kelajagi»</i>.", kb_main())
        return

    if text.startswith("/"):
        cmd = text.split()[0].split("@")[0].lower()
        st = _state(chat_id)
        if cmd == "/start":
            await _send(chat_id, WELCOME, kb_main())
            _spawn(_warm_account(user))                       # akkaunt/kredit qatorini fonda tayyorlaydi (javobni kechiktirmaydi)
        elif cmd == "/help":
            await _send(chat_id, HELP, kb_main())
        elif cmd == "/new":
            st.update(deck=None, imgs={}, awaiting=None, topic=None)
            await _send(chat_id, "🆕 Yangi taqdimot uchun mavzuni yozing.")
        elif cmd == "/mode":
            st["mode"] = "deep" if st.get("mode") != "deep" else "fast"
            await _send(chat_id, f"Rejim: <b>{'🧠 Chuqur AI' if st['mode'] == 'deep' else '⚡ Tez AI'}</b>\n"
                                 f"<i>{'Murakkab mavzular uchun, 1 slayd = 3 varaq, sekinroq.' if st['mode'] == 'deep' else 'Tez va tejamkor: 1 slayd = 1 varaq.'}</i>")
        elif cmd in ("/credits", "/kredit", "/kreditlar", "/balance"):
            await _send(chat_id, await _credits_text(user), kb_main())
        elif cmd == "/site":
            await _send(chat_id, f"🌐 {esc(SITE_URL)}", kb_main())
        else:
            await _send(chat_id, HELP, kb_main())
        return

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
    r = _provision_sync(user)
    if r.get("error"):
        return {"error": r["error"]}
    if not r.get("hashed"):
        return {"error": "auth_unavailable"}
    return {"token_hash": r["hashed"], "type": "magiclink", "email": r["email"], "name": r["name"]}


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
        {"command": "new", "description": "Yangi taqdimot"},
        {"command": "mode", "description": "Tez ⚡ / Chuqur 🧠 AI"},
        {"command": "credits", "description": "Kreditlarim (balans)"},
        {"command": "site", "description": "Saytga havola"},
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
