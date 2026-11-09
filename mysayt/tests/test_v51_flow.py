"""v51: bot oqimi testi (soxta Telegram/AI bilan, tarmoqsiz).
Ishga tushirish:  python tests/test_v51_flow.py      (pytest ham mumkin)
"""
import asyncio
import os
import sys
import types

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TESTTOKEN")
os.environ["SLIDE_STUDIO_DEV_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:                                    # fastapi/httpx o'rnatilmagan muhitda ham ishlasin
    import fastapi  # noqa
    import httpx  # noqa
except Exception:
    fa = types.ModuleType("fastapi")
    class _R:
        def __getattr__(self, n):
            return lambda *a, **k: (lambda f: f)
    fa.APIRouter = _R
    fa.BackgroundTasks = fa.Request = object
    fa.HTTPException = Exception
    fr = types.ModuleType("fastapi.responses")
    fr.JSONResponse = fr.Response = object
    hx = types.ModuleType("httpx")
    hx.AsyncClient = object
    hx.Timeout = lambda *a, **k: None
    hx.Limits = lambda *a, **k: None
    sys.modules.update({"fastapi": fa, "fastapi.responses": fr, "httpx": hx})

from backend import telegram_bot as tb  # noqa: E402

SENT = []          # (chat_id, text, reply_markup)
DOCS = []


async def fake_tg(method, **p):
    if method in ("sendMessage", "editMessageText"):
        SENT.append((p.get("chat_id"), p.get("text", ""), p.get("reply_markup")))
        return {"message_id": len(SENT)}
    return True


async def fake_doc(chat_id, name, data, mime, cap=""):
    DOCS.append(name)
    return True


GEN_CALLS = []
AI_REPLIES = []


async def fake_ai(system, user, mode):
    return (AI_REPLIES.pop(0) if AI_REPLIES else None), 10


async def fake_generate(chat_id, user, topic, n):
    GEN_CALLS.append((topic, n))
    st = tb._state(chat_id)
    st["ui"] = None


EDITS = []


async def fake_edit(chat_id, user, text):
    EDITS.append(text)


tb.tg = fake_tg
tb.tg_send_document = fake_doc
tb._ai_json = fake_ai
tb._run_generate = fake_generate
tb._run_edit = fake_edit
tb._deps.update(
    total_credits=lambda u: 100, MODES={"fast": {"chat": 0.1}, "deep": {"chat": 0.1}}, usage_payload=lambda u: {},
    supabase_getter=lambda: None,
    admin=types.SimpleNamespace(is_tg_admin=lambda i: i == 1),
)
tb._usage_now_sync = lambda uid, email: {}
tb._charge = lambda *a, **k: asyncio.sleep(0, result=({}, 0))


async def _balance_info(user):
    return {"linked": True, "email": "a@b.c", "free": 10, "paid": 0, "daily": 10}
tb._balance_info = _balance_info
tb._is_admin = lambda user: user.get("id") == 1
tb._limited = lambda *a, **k: False
tb._ad_sweeper_start = lambda: None


def msg(uid, text):
    return {"message": {"chat": {"id": uid, "type": "private"}, "from": {"id": uid, "is_bot": False, "first_name": "T"}, "text": text}}


async def say(uid, text):
    await tb.handle_update(msg(uid, text))
    await asyncio.sleep(0.05)           # _spawn qilingan vazifalar tugashi uchun


async def cb(uid, data):
    await tb.handle_update({"callback_query": {"id": "1", "data": data, "from": {"id": uid, "is_bot": False}, "message": {"chat": {"id": uid}, "message_id": 5}}})
    await asyncio.sleep(0.05)


def last_text():
    return SENT[-1][1] if SENT else ""


async def main():
    U = 777

    # 1) /start — oddiy foydalanuvchi ham, admin ham bir xil (admin paneli o'zi ochilmaydi)
    for uid in (U, 1):
        SENT.clear()
        await say(uid, "/start")
        assert not any("Admin" in t for _, t, _k in SENT), "admin paneli /start da ochilmasligi kerak"
    # admin «admin» deb yozsagina ochiladi, oddiy odamga ochilmaydi
    SENT.clear()
    await say(1, "admin")
    assert any("Admin" in t for _, t, _k in SENT), "admin uchun panel ochilishi kerak"
    SENT.clear()
    await say(U, "admin")
    assert not any("Admin" in t for _, t, _k in SENT)

    # 2) Tugma bosilmagan — matn AI'ga bormaydi, eski slaydni ham tahrirlamaydi
    GEN_CALLS.clear(); EDITS.clear(); SENT.clear()
    tb._state(U)["deck"] = {"title": "Eski", "slides": [{"title": "a"}]}      # eski slayd xotirada turibdi
    await say(U, "3-slaydni qisqartir")
    assert not GEN_CALLS and not EDITS, "tugmasiz yozilgan matn AI'ga o'tmasligi kerak"
    assert "Yangi slayd" in last_text()

    # 3) «Yangi slayd» -> slayd so'zi bor matn darrov generatsiya
    await say(U, "🎨 Yangi slayd")
    assert tb._state(U)["ui"] == "new"
    await say(U, "Sun'iy intellekt haqida 6 ta slayd")
    assert GEN_CALLS and GEN_CALLS[-1][1] == 6

    # 4) Yangi slayd rejimida oddiy savol — AI slayd yasamasdan javob beradi
    await say(U, "🎨 Yangi slayd")
    GEN_CALLS.clear(); SENT.clear()
    AI_REPLIES.append({"intent": "chat", "reply": "Salom! Qanday yordam beray?"})
    await say(U, "salom, sen kimsan?")
    assert not GEN_CALLS and "Salom! Qanday yordam beray?" in last_text()
    assert tb._state(U)["ui"] == "new", "savoldan keyin rejim saqlanadi"
    AI_REPLIES.append({"intent": "slides", "topic": "Quyosh energiyasi", "count": 0})
    await say(U, "Quyosh energiyasi")
    assert GEN_CALLS and GEN_CALLS[-1][0] == "Quyosh energiyasi"

    # 5) Tayyor slayd kartasi: 3 ta yuklab olish tugmasi + bitta Tahrirlash
    deck = {"title": "Test", "theme": "ocean", "slides": [{"layout": "title", "title": "Test"}, {"layout": "bullets", "title": "Ikki", "bullets": ["a"]}]}
    txt = tb._card_text(deck, "✅")
    kb = tb.kb_done({})["inline_keyboard"]
    flat = [b["callback_data"] for r in kb for b in r]
    assert flat[:3] == ["dl:pptx", "dl:pdf", "dl:html"] and "edit" in flat and "Test" in txt

    # 6) Tahrirlash tugmasi -> tahrirlash oynasi; faqat shundan keyin yozilgan matn _run_edit ga boradi
    st = tb._state(U)
    st["deck"] = deck
    EDITS.clear(); SENT.clear()
    await cb(U, "edit")
    assert st["ui"] == "edit" and "Tahrirlash oynasi" in last_text()
    await say(U, "2-slaydni qisqartir")
    assert EDITS == ["2-slaydni qisqartir"]
    # «Tayyor» -> tugadi
    await cb(U, "back")
    assert st["ui"] is None
    EDITS.clear()
    await say(U, "yana o'zgartir")
    assert not EDITS

    # 7) Yuklab olish tugmasi faylni o'zi yuboradi
    DOCS.clear()
    st["deck"] = deck
    await cb(U, "dl:pptx")
    await asyncio.sleep(1.5)
    assert any(d.endswith(".pptx") for d in DOCS), DOCS

    # 8) Google akkaunt Supabase'dan o'chsa — bot ham to'xtaydi
    calls = {"deleted": 0}

    class Q:
        def __init__(self, data): self.data = data
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def delete(self, *a, **k): calls["deleted"] += 1; return self
        def execute(self): return types.SimpleNamespace(data=self.data)

    class Admin:
        def get_user_by_id(self, uid): raise Exception("User not found")
        def create_user(self, *a, **k): return None
        def generate_link(self, *a, **k):
            return types.SimpleNamespace(properties=types.SimpleNamespace(hashed_token="h"),
                                         user=types.SimpleNamespace(id="11111111-1111-1111-1111-111111111111", app_metadata={"telegram_id": "555"}))

    class SB:
        auth = types.SimpleNamespace(admin=Admin())
        def table(self, name):
            if name == "tg_links":
                return Q([{"user_id": "22222222-2222-2222-2222-222222222222", "email": "me@gmail.com"}] if not calls["deleted"] else [])
            if name == "user_usage":
                return Q([])
            return Q([])

    tb.DEV_MODE = False
    tb._is_admin = lambda user: False
    tb._deps["supabase_getter"] = lambda: SB()
    tb._deps["get_usage"] = lambda *a, **k: {}
    tb._uids.clear(); tb._uid_ts.clear()
    uid, email = await tb._ensure_uid({"id": 555})
    assert calls["deleted"] == 1 and email.endswith("@t.me"), (uid, email, calls)
    SENT.clear()
    ok = await tb._google_ok(555, {"id": 555})
    assert ok is False and "Google" in last_text()
    print("HAMMA TEST O'TDI ✅")


asyncio.run(main())


# ---------------- reklama xabarlari bazada saqlanadi va restartdan keyin ham o'chiriladi ----------------
async def ads_test():
    DB = []                                     # soxta ad_sent jadvali

    class T:
        def __init__(self): self.f = {}; self.op = None; self.payload = None
        def insert(self, rows): self.op, self.payload = "ins", rows; return self
        def select(self, *a, **k): self.op = "sel"; return self
        def delete(self): self.op = "del"; return self
        def eq(self, k, v): self.f[k] = v; return self
        def gte(self, k, v): return self
        def lt(self, k, v): self.f["__lt"] = v; return self
        def order(self, *a, **k): return self
        def range(self, a, b): self.f["__r"] = (a, b); return self
        def execute(self):
            if self.op == "ins":
                DB.extend(self.payload); return types.SimpleNamespace(data=self.payload)
            if self.op == "del":
                if "ad_id" in self.f:
                    DB[:] = [r for r in DB if r["ad_id"] != self.f["ad_id"]]
                return types.SimpleNamespace(data=[])
            rows = [r for r in DB if all(r.get(k) == v for k, v in self.f.items() if not k.startswith("__"))]
            a, b = self.f.get("__r", (0, 999))
            return types.SimpleNamespace(data=rows[a:b + 1])

    class SB2:
        def table(self, n): return T()

    tb._deps["supabase_getter"] = lambda: SB2()
    tb._AD_SENT.clear(); tb._AD_PENDING.clear(); tb._AD_DB_OFF = False
    for cid in range(1, 51):
        tb._ad_sent_add(9, cid, cid * 10)       # 50 kishiga yuborildi
    await asyncio.to_thread(tb._ad_sent_persist)
    assert len(DB) == 50, len(DB)

    tb._AD_SENT.clear()                         # server qayta ishga tushdi — RAM bo'sh
    await asyncio.to_thread(tb._ad_sent_load_db)
    assert len(tb._AD_SENT.get(9, [])) == 50

    deleted = []

    async def fake_tg2(method, **p):
        if method == "deleteMessage":
            deleted.append((p["chat_id"], p["message_id"]))
        return True
    tb.tg = fake_tg2
    tb._AD_SENT.clear()                         # RAM bo'sh bo'lsa ham bazadan topib o'chiradi
    n = await tb._ad_purge(9)
    assert n == 50 and len(deleted) == 50 and DB == [], (n, len(deleted), len(DB))
    print("REKLAMA TESTI O'TDI ✅")

asyncio.run(ads_test())
