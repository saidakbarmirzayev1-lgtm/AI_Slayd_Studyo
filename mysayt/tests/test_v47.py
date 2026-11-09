"""v47 sinovlari: Pro / VIP / cheksiz / reklama / admin xavfsizligi / to'lov webhook / bot.
Ishga tushirish:  pip install pytest httpx  &&  python -m pytest tests -q
"""
import asyncio, hashlib, hmac, json, os, sys, time
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.update({
    "ADMIN_EMAILS": "boss@example.com", "ADMIN_TG_IDS": "111", "SLIDE_STUDIO_HMAC_SECRET": "testsecret",
    "PUBLIC_BASE_URL": "https://x.test", "AI_API_KEY": "k-test-key-123456", "SUPABASE_SECRET_KEY": "dummy",
    "LEMON_SQUEEZY_WEBHOOK_SECRET": "whsec", "LEMON_SQUEEZY_VARIANT_ID": "100", "LEMON_SQUEEZY_PRO_VARIANT_ID": "200",
    "LEMON_SQUEEZY_API_KEY": "x", "LEMON_SQUEEZY_STORE_ID": "1", "TELEGRAM_BOT_TOKEN": "",
})
import pytest
from fastapi.testclient import TestClient
from fake_supabase import FakeSB

import main
from backend import admin_core, ads, appsettings
from backend import monitoring as mon
from backend import telegram_bot as bot


@pytest.fixture()
def env():
    sb = FakeSB()
    main.supabase = sb
    appsettings._cache.update(appsettings.DEFAULTS)
    appsettings._loaded_at = time.time()
    ads.invalidate()
    ads._bot_last.clear()
    main._adfree_cache.clear()
    admin_core._vip_cache.clear()
    sb.add_user("u-free", "free@example.com", "tok-free")
    sb.add_user("u-pro", "pro@example.com", "tok-pro", plan="pro", plan_until=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat())
    sb.add_user("u-old", "old@example.com", "tok-old", plan="pro", plan_until=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
    sb.add_user("u-boss", "boss@example.com", "tok-boss")
    sb.tables["tg_links"] = [{"tg_id": 111, "user_id": "u-boss", "email": "boss@example.com"}]
    with TestClient(main.app) as c:
        yield c, sb


def adm_token(tg=111, email="boss@example.com", ttl=600):
    return admin_core.make_token(tg, email, ttl)


def api(c, op, body=None, token=None):
    return c.post(f"/_a/api/{op}", json=body or {}, headers={"X-Admin-Token": token or adm_token()})


# ---------------------------------------------------------------- monitoring
def test_plan_logic():
    u = mon.normalize_user_row({"user_id": "a"})
    assert mon.plan_active(u) == "free" and not mon.is_unlimited(u) and not mon.is_ad_free(u)
    p = mon.extend_pro(u, 30)
    assert mon.plan_active(p) == "pro" and mon.is_ad_free(p) and not mon.is_unlimited(p)
    assert mon.daily_units_for(p) == mon.pro_daily_units()
    expired = dict(p, plan_until=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
    assert mon.plan_active(expired) == "free"
    assert mon.charge_for_ai_turn(dict(u, unlimited=True), 9, 3, "deep")[1] == 0
    assert mon.can_afford(dict(u, vip=True), "deep")
    assert mon.daily_units_for(dict(u, daily_units_override=1000)) == 1000


def test_charging_still_works_for_free_users():
    u = mon.normalize_user_row({"user_id": "a"})
    u2, charged, why = mon.charge_for_ai_turn(u, 2, 0, "fast")
    assert charged == 2 * mon.UNIT and u2["free_credits"] == mon.free_daily_units() - 2 * mon.UNIT


def test_refund_shortens_pro():
    u = mon.extend_pro(mon.normalize_user_row({"user_id": "a"}), 30)
    assert mon.plan_active(mon.shorten_pro(u, 30)) == "free"


# ---------------------------------------------------------------- admin xavfsizligi
def test_panel_hidden_from_everyone_else(env):
    c, sb = env
    assert c.get("/_a/garbage").status_code == 404
    assert c.get("/_a/api/stats").status_code == 404 or c.get("/_a/api/stats").status_code == 405
    assert c.post("/_a/api/stats").status_code == 404
    assert c.post("/_a/api/stats", headers={"X-Admin-Token": "x.y"}).status_code == 404
    assert c.get("/admin").status_code == 404 and c.get("/admin.html").status_code == 404


def test_token_rules(env):
    c, sb = env
    good = adm_token()
    assert c.get(f"/_a/{good}").status_code == 200
    assert "Admin" in c.get(f"/_a/{good}").text
    assert c.post("/_a/api/ping", headers={"X-Admin-Token": good}).json()["ok"]
    assert c.post("/_a/api/ping", headers={"X-Admin-Token": adm_token(tg=999)}).status_code == 404          # admin ro'yxatida yo'q
    assert c.post("/_a/api/ping", headers={"X-Admin-Token": adm_token(email="x@y.com")}).status_code == 404
    assert c.post("/_a/api/ping", headers={"X-Admin-Token": adm_token(ttl=-5)}).status_code == 404        # muddati o'tgan
    body, sig = good.split(".")
    assert c.post("/_a/api/ping", headers={"X-Admin-Token": body + "." + "0" * len(sig)}).status_code == 404  # soxta imzo


def test_admin_requires_both_telegram_and_google(env):
    c, sb = env
    assert admin_core.check_admin_tg(111)["ok"]
    assert admin_core.check_admin_tg(222)["reason"] == "not_admin"
    sb.tables["tg_links"].clear()
    assert admin_core.check_admin_tg(111)["reason"] == "not_linked"
    sb.tables["tg_links"].append({"tg_id": 111, "user_id": "u-free", "email": "free@example.com"})
    assert admin_core.check_admin_tg(111)["reason"] == "email_mismatch"
    # sayt tomoni: admin email bor, lekin Telegram ulanmagan -> 404
    sb.tables["tg_links"].clear()
    assert c.post("/api/me/admin-entry", json={"token": "tok-boss"}).status_code == 404
    sb.tables["tg_links"].append({"tg_id": 111, "user_id": "u-boss", "email": "boss@example.com"})
    r = c.post("/api/me/admin-entry", json={"token": "tok-boss"})
    assert r.status_code == 200 and r.json()["url"].startswith("/_a/")
    assert c.post("/api/me/admin-entry", json={"token": "tok-free"}).status_code == 404
    assert c.post("/api/me/admin-entry", json={"token": "nope"}).status_code == 404


def test_vip_admin_accounts(env):
    c, sb = env
    u = main.get_or_create_user_usage("u-boss", "boss@example.com")
    pl = mon.usage_payload(u)
    assert pl["unlimited"] and pl["plan"] == "vip" and pl["ad_free"] and pl["slide_credits_left"] >= 999999
    sb.auth_meta["tg-uid"] = {"telegram_id": 111}
    sb.add_user("tg-uid", "tg111@t.me")
    assert mon.usage_payload(main.get_or_create_user_usage("tg-uid", "tg111@t.me"))["unlimited"]
    sb.auth_meta["fake-uid"] = {"telegram_id": 5}                       # shu emailni boshqa birov egallagan
    sb.add_user("fake-uid", "tg111@t.me")
    assert not mon.usage_payload(main.get_or_create_user_usage("fake-uid", "tg111@t.me"))["unlimited"]
    assert not mon.usage_payload(main.get_or_create_user_usage("u-free", "free@example.com"))["unlimited"]


# ---------------------------------------------------------------- foydalanuvchini boshqarish
def test_user_management(env):
    c, sb = env
    r = api(c, "users", {"q": "free@"}).json()
    assert [u["email"] for u in r["users"]] == ["free@example.com"]
    r = api(c, "user_action", {"user_id": "u-free", "action": "set_plan", "plan": "pro", "days": 10}).json()
    assert r["user"]["plan"] == "pro" and r["user"]["daily_pages"] == mon.rt("pro_daily_pages")
    r = api(c, "user_action", {"user_id": "u-free", "action": "add_credits", "pages": 50}).json()
    assert r["user"]["paid_pages"] == 50
    r = api(c, "user_action", {"user_id": "u-free", "action": "add_credits", "pages": -999}).json()
    assert r["user"]["paid_pages"] == 0                                         # manfiyga tushmaydi
    r = api(c, "user_action", {"user_id": "u-free", "action": "unlimited", "value": True}).json()
    assert r["user"]["unlimited"] is True
    pl = mon.usage_payload(main.get_or_create_user_usage("u-free", "free@example.com"))
    assert pl["unlimited"] and pl["ad_free"]
    api(c, "user_action", {"user_id": "u-free", "action": "unlimited", "value": False})
    r = api(c, "user_action", {"user_id": "u-free", "action": "daily_override", "pages": 100}).json()
    assert r["user"]["daily_pages"] == 100
    r = api(c, "user_action", {"user_id": "u-free", "action": "set_credits", "free_pages": 7, "paid_pages": 3}).json()
    assert (r["user"]["free_pages"], r["user"]["paid_pages"]) == (7, 3)
    r = api(c, "user_action", {"user_id": "u-free", "action": "block", "value": True}).json()
    assert r["user"]["blocked"]
    assert api(c, "user_action", {"user_id": "nope", "action": "block", "value": True}).status_code == 400
    assert api(c, "user_action", {"user_id": "u-free", "action": "???"}).status_code == 400
    assert api(c, "user_action", {"user_id": "u-free", "action": "add_credits", "pages": "abc"}).status_code == 400
    assert any(a["action"] == "user.add_credits" for a in sb.tables["admin_audit"])    # jurnal yuritiladi
    # tg ID orqali qidirish (ulangan Google akkaunt)
    assert api(c, "users", {"q": "111"}).json()["users"][0]["user_id"] == "u-boss"


def test_missing_migration_is_reported_not_crashing(env):
    c, sb = env
    sb.missing_cols = {"plan", "plan_until", "unlimited", "daily_units_override", "admin_note"}
    r = api(c, "user_action", {"user_id": "u-free", "action": "set_plan", "plan": "pro", "days": 3})
    assert r.status_code == 409 and "SUPABASE_ADMIN.sql" in r.json()["error"]
    r = api(c, "user_action", {"user_id": "u-free", "action": "add_credits", "pages": 5})        # kredit amallari ishlayveradi
    assert r.status_code == 200
    assert api(c, "users", {"q": ""}).status_code == 200
    s = api(c, "system").json()
    assert s["migration"]["plan_columns"] is False


def test_stats_and_system(env):
    c, sb = env
    s = api(c, "stats").json()
    assert s["users_total"] == 4 and s["pro_active"] == 1 and s["linked"] == 1
    sysj = api(c, "system").json()
    assert sysj["ai_key"] and sysj["supabase"] and sysj["admin_tg_ids"] == 1
    assert "k-test" not in json.dumps(sysj)                                    # kalitning o'zi ko'rinmaydi


def test_settings_apply_at_runtime(env):
    c, sb = env
    r = api(c, "settings_set", {"values": {"free_daily_pages": 40, "pro_daily_pages": 90, "ads_enabled": False, "junk": 1}}).json()
    assert r["persisted"] and r["saved"] == {"free_daily_pages": 40, "pro_daily_pages": 90, "ads_enabled": False}
    u = mon.normalize_user_row({"user_id": "z"})
    assert mon.daily_units_for(u) == 40 * mon.UNIT
    assert mon.daily_units_for(mon.extend_pro(u, 5)) == 90 * mon.UNIT
    assert c.get("/api/config/public").json()["free_daily"] == 40
    api(c, "settings_set", {"values": {"free_daily_pages": 15, "pro_daily_pages": 60, "ads_enabled": True}})


# ---------------------------------------------------------------- reklama
AD = {"title": "Kurs", "body": "Chegirma 50%", "media_type": "image", "media_url": "https://img.test/a.jpg",
      "link_url": "https://shop.test/x", "placement": "both", "active": True, "weight": 1}


def test_ads_lifecycle_and_pro_hidden(env):
    c, sb = env
    assert c.get("/api/ads/next").json()["ad"] is None                         # reklama yo'q
    assert api(c, "ad_save", {"ad": dict(AD, link_url="javascript:alert(1)")}).status_code == 400
    assert api(c, "ad_save", {"ad": dict(AD, media_url="ftp://x")}).status_code == 400
    assert api(c, "ad_save", {"ad": {"title": "", "body": ""}}).status_code == 400
    r = api(c, "ad_save", {"ad": AD}).json()
    aid = r["id"]
    ad = c.get("/api/ads/next").json()["ad"]                                   # mehmon ko'radi
    assert ad and ad["title"] == "Kurs" and ad["has_link"] and ad["click_url"].endswith(f"/{aid}?s=site")
    assert c.get("/api/ads/next", headers={"Authorization": "Bearer tok-free"}).json()["ad"]      # oddiy foydalanuvchi ko'radi
    for tok in ("tok-pro", "tok-boss"):                                          # Pro va admin ko'rmaydi
        main._adfree_cache.clear()
        assert c.get("/api/ads/next", headers={"Authorization": f"Bearer {tok}"}).json()["ad"] is None
    assert c.get("/api/ads/next", params={"token": "tok-old"}).json()["ad"]   # Pro muddati tugagan -> yana ko'radi
    sb.tables["user_usage"][0]["unlimited"] = True
    main._adfree_cache.clear()
    assert c.get("/api/ads/next", headers={"Authorization": "Bearer tok-free"}).json()["ad"] is None   # cheksiz -> ko'rmaydi
    # hisoblagich
    time.sleep(0.2)
    row = sb.tables["ads"][0]
    assert row["impressions"] >= 3
    rr = c.get(f"/api/ads/click/{aid}?s=bot", follow_redirects=False)
    assert rr.status_code == 302 and rr.headers["location"] == "https://shop.test/x"
    time.sleep(0.2)
    assert row["clicks"] == 1
    assert c.get("/api/ads/click/9999", follow_redirects=False).status_code == 404
    # o'chirilsa / umumiy kalit o'chsa ko'rinmaydi
    api(c, "ad_toggle", {"id": aid, "active": False})
    assert c.get("/api/ads/next").json()["ad"] is None
    api(c, "ad_toggle", {"id": aid, "active": True})
    api(c, "settings_set", {"values": {"ads_site": False}})
    assert c.get("/api/ads/next").json()["ad"] is None
    api(c, "settings_set", {"values": {"ads_site": True}})
    assert c.get("/api/ads/next").json()["ad"]
    api(c, "ad_delete", {"id": aid})
    assert c.get("/api/ads/next").json()["ad"] is None


def test_ad_schedule_and_placement(env):
    c, sb = env
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    api(c, "ad_save", {"ad": dict(AD, title="eski", ends_at=past)})
    api(c, "ad_save", {"ad": dict(AD, title="kelajak", starts_at=future)})
    api(c, "ad_save", {"ad": dict(AD, title="botda", placement="bot")})
    assert c.get("/api/ads/next").json()["ad"] is None
    api(c, "ad_save", {"ad": dict(AD, title="faol", starts_at=past, ends_at=future, placement="site")})
    assert c.get("/api/ads/next").json()["ad"]["title"] == "faol"
    assert ads.pick("bot", False)["title"] == "botda"
    assert ads.pick("bot", True) is None


def test_uploaded_image_served(env):
    c, sb = env
    png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    aid = api(c, "ad_save", {"ad": dict(AD, media_url=png)}).json()["id"]
    ad = c.get("/api/ads/next").json()["ad"]
    assert ad["media_url"] == f"/api/ads/media/{aid}"
    m = c.get(ad["media_url"])
    assert m.status_code == 200 and m.headers["content-type"] == "image/png" and m.content[:4] == b"\x89PNG"
    listing = api(c, "ads").json()["ads"][0]
    assert listing["media_is_upload"] and not listing["media_url"].startswith("data:")           # ro'yxat og'ir emas
    assert api(c, "ad_save", {"ad": dict(AD, media_url="data:image/svg+xml;base64,AAAA")}).status_code == 400
    assert api(c, "ad_save", {"ad": dict(AD, media_url="data:text/html;base64,AAAA")}).status_code == 400
    # tahrirlashda rasm bo'sh qoldirilsa eskisi saqlanadi
    api(c, "ad_save", {"ad": dict(AD, id=aid, media_url="", title="yangi")})
    assert sb.tables["ads"][0]["media_url"] == png and sb.tables["ads"][0]["title"] == "yangi"


# ---------------------------------------------------------------- to'lov webhook
def hook(c, event, order_id, variant, uid, status="paid", qty=1):
    body = json.dumps({"meta": {"event_name": event, "custom_data": {"user_id": uid}},
                       "data": {"id": order_id, "attributes": {"status": status, "user_email": "x@y.z", "first_order_item": {"variant_id": variant, "quantity": qty}}}}).encode()
    sig = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
    return c.post("/api/payment/lemon-webhook", content=body, headers={"X-Signature": sig, "X-Event-Name": event, "Content-Type": "application/json"})


def test_webhook_pack_pro_refund_duplicates(env):
    c, sb = env
    assert hook(c, "order_created", "o1", 100, "u-free").json()["pages"] == 150
    assert sb.tables["user_usage"][0]["paid_credits"] == 150 * mon.UNIT
    assert hook(c, "order_created", "o1", 100, "u-free").json().get("duplicate")        # ikki marta hisoblanmaydi
    r = hook(c, "order_created", "o2", 200, "u-free").json()
    assert r["plan"] == "pro" and r["days"] == 30
    row = sb.tables["user_usage"][0]
    assert row["plan"] == "pro" and row["paid_credits"] == 150 * mon.UNIT              # Pro kreditga tegmaydi
    first = datetime.fromisoformat(row["plan_until"])
    hook(c, "order_created", "o3", 200, "u-free")                                       # ikkinchi to'lov muddatni uzaytiradi
    assert (datetime.fromisoformat(sb.tables["user_usage"][0]["plan_until"]) - first).days == 30
    hook(c, "order_refunded", "o3", 200, "u-free")
    hook(c, "order_refunded", "o2", 200, "u-free")
    assert mon.plan_active(mon.normalize_user_row(sb.tables["user_usage"][0])) == "free"
    assert hook(c, "order_created", "o9", 777, "u-free").json()["ignored"] == "other_variant"
    assert hook(c, "order_created", "o10", 200, "u-free", status="pending").json()["ignored"].startswith("status")
    bad = c.post("/api/payment/lemon-webhook", content=b"{}", headers={"X-Signature": "00"})
    assert bad.status_code == 401


def test_pro_purchase_without_migration_retries(env):
    c, sb = env
    sb.missing_cols = {"plan", "plan_until"}
    r = hook(c, "order_created", "oo1", 200, "u-free")
    assert r.status_code == 500                       # Lemon qayta yuboradi; buyurtma "ishlangan" deb belgilanmaydi
    sb.missing_cols = set()
    assert hook(c, "order_created", "oo1", 200, "u-free").json()["plan"] == "pro"


def test_checkout_product_selection(env, monkeypatch):
    c, sb = env
    seen = {}

    def fake_post(api_key, body):
        seen["variant"] = body["data"]["relationships"]["variant"]["data"]["id"]
        seen["custom"] = body["data"]["attributes"]["checkout_data"]["custom"]
        return {"status": 201, "json": {"data": {"attributes": {"url": "https://pay.test/c"}}}}
    monkeypatch.setattr(main, "_ls_post_checkout", fake_post)
    r = c.post("/api/payment/create-checkout", json={"token": "tok-free", "product": "pro"}).json()
    assert r["checkout_url"] == "https://pay.test/c" and r["days"] == 30 and seen["variant"] == "200" and seen["custom"]["product"] == "pro"
    r = c.post("/api/payment/create-checkout", json={"token": "tok-free"}).json()
    assert r["pages"] == 150 and seen["variant"] == "100"
    monkeypatch.setenv("LEMON_SQUEEZY_PRO_VARIANT_ID", "")
    r = c.post("/api/payment/create-checkout", json={"token": "tok-free", "product": "pro"})
    assert r.status_code == 503 and "PRO_VARIANT" in r.json()["hint"]


# ---------------------------------------------------------------- bot
class Rec:
    def __init__(self):
        self.calls = []

    async def tg(self, method, **kw):
        self.calls.append((method, kw))
        return {"message_id": 1}


@pytest.fixture()
def tgrec(env, monkeypatch):
    rec = Rec()
    monkeypatch.setattr(bot, "tg", rec.tg)
    monkeypatch.setattr(bot, "SITE_URL", "https://x.test")
    bot._state(1).clear()
    return rec


def msg(uid, text, chat=1):
    return {"message": {"chat": {"id": chat, "type": "private"}, "from": {"id": uid, "is_bot": False, "first_name": "T"}, "text": text}}


def test_bot_admin_command(env, tgrec):
    c, sb = env
    run = lambda m: asyncio.run(bot.handle_update(m))
    run(msg(111, "admin"))
    sent = tgrec.calls[-1][1]
    assert "/give" in sent["text"] and "/unlimited" in sent["text"]
    tgrec.calls.clear()
    run(msg(999, "/admin"))                     # oddiy foydalanuvchi: hech narsa oshkor bo'lmaydi
    assert tgrec.calls[-1][1]["text"] == "Bunday buyruq mavjud emas."
    tgrec.calls.clear()
    run(msg(999, "/give 111 5"))
    assert tgrec.calls[-1][1]["text"] == "Bunday buyruq mavjud emas."


def test_bot_admin_manages_balance(env, tgrec):
    c, sb = env
    bot._deps["supabase_getter"] = lambda: sb
    run = lambda m: asyncio.run(bot.handle_update(m))
    sb.tables["tg_links"].append({"tg_id": 555, "user_id": "u-free", "email": "free@example.com"})
    run(msg(111, "/give 555 40"))
    assert "40" in tgrec.calls[-1][1]["text"]
    assert mon.usage_payload(main.get_or_create_user_usage("u-free", "free@example.com"))["modes"]["fast"]["paid_pages"] >= 40
    run(msg(111, "/take 555 15"))
    run(msg(111, "/unlimited 555"))
    assert main.get_or_create_user_usage("u-free", "free@example.com")["unlimited"] is True
    run(msg(111, "/unlimited 555 off"))
    run(msg(111, "/reset 555"))
    u = mon.usage_payload(main.get_or_create_user_usage("u-free", "free@example.com"))
    assert not u["unlimited"] and u["modes"]["fast"]["paid_pages"] == 0
    run(msg(111, "/give 424242 5"))                                   # noma'lum foydalanuvchi — xato matni, crash yo'q
    assert "Topilmadi" in tgrec.calls[-1][1]["text"]


def test_bot_requires_google_before_slides(env, tgrec):
    c, sb = env
    bot._deps["supabase_getter"] = lambda: sb
    bot._uids[888] = ("u-tg", "tg888@t.me")                              # Google ulanmagan oddiy foydalanuvchi
    asyncio.run(bot.handle_update(msg(888, "🎨 Yangi slayd")))             # v51: avval tugma, keyin mavzu
    asyncio.run(bot.handle_update(msg(888, "Sun'iy intellekt")))
    out = tgrec.calls[-1][1]
    assert "Google" in out["text"] and "linkinfo" in json.dumps(out["reply_markup"])
    assert not bot._state(1).get("busy")


def test_bot_buy_flows(env, tgrec, monkeypatch):
    c, sb = env
    calls = []

    async def fake_checkout(uid, email, base, product):
        calls.append(product)
        return {"url": "https://pay.test/z", "pages": 150, "price": 5.0}
    bot._deps["checkout"] = fake_checkout
    bot._deps["supabase_getter"] = lambda: sb
    bot._uids[777] = ("u-free", "free@example.com")
    asyncio.run(bot._do_buy(1, {"id": 777}, "pack"))
    out = tgrec.calls[-1][1]
    assert calls == ["pack"] and "To'lovga o'tish" in json.dumps(out["reply_markup"], ensure_ascii=False) and "150" in out["text"]

    async def bad_checkout(*a):
        return {"error": "To'lov hali sozlanmagan", "hint": "LEMON_SQUEEZY_VARIANT_ID"}
    bot._deps["checkout"] = bad_checkout
    tgrec.calls.clear()
    asyncio.run(bot._do_buy(1, {"id": 777}, "pack"))                                  # oddiy foydalanuvchi: texnik sabab ko'rinmaydi
    assert "VARIANT" not in tgrec.calls[-1][1]["text"]
    bot._uids[111] = ("u-boss", "boss@example.com")
    tgrec.calls.clear()
    asyncio.run(bot._do_buy(1, {"id": 111}, "pack"))                                  # admin: sabab ko'rinadi
    assert "VARIANT" in tgrec.calls[-1][1]["text"]


def test_bot_balance_and_no_pro_buttons(env, tgrec):
    c, sb = env
    bot._deps["supabase_getter"] = lambda: sb
    bot._uids[111] = ("u-boss", "boss@example.com")
    bot._uids[779] = ("u-free", "free@example.com")
    asyncio.run(bot._show_balance(1, {"id": 111}))
    assert "cheksiz" in tgrec.calls[-1][1]["text"]
    asyncio.run(bot._show_balance(1, {"id": 779}))
    out = tgrec.calls[-1][1]
    assert "Varaqlar" in out["text"] and "Pro" not in out["text"] and "Pro" not in json.dumps(out["reply_markup"], ensure_ascii=False)
    assert bot.kb_reply()["keyboard"] and "Pro" not in json.dumps(bot.kb_reply(), ensure_ascii=False)


def test_bot_ads_respect_plan_and_interval(env, tgrec):
    c, sb = env
    bot._deps["supabase_getter"] = lambda: sb
    api(c, "ad_save", {"ad": dict(AD, placement="bot")})
    ads.invalidate()
    asyncio.run(bot._maybe_ad(1, "u-free", "free@example.com"))
    method, kw = tgrec.calls[-1]
    assert method == "sendPhoto" and "Reklama" in kw["caption"] and "/api/ads/click/" in json.dumps(kw["reply_markup"])
    n = len(tgrec.calls)
    asyncio.run(bot._maybe_ad(1, "u-free", "free@example.com"))                       # oraliq tugamagan -> yana yuborilmaydi
    assert len(tgrec.calls) == n
    for uid, email in (("u-pro", "pro@example.com"), ("u-boss", "boss@example.com")):  # reklamasiz hisoblar va admin hech qachon
        asyncio.run(bot._maybe_ad(1, uid, email))
    assert len(tgrec.calls) == n
    ads._bot_last.clear()
    api(c, "settings_set", {"values": {"ads_bot": False}})
    asyncio.run(bot._maybe_ad(1, "u-free", "free@example.com"))
    assert len(tgrec.calls) == n


def test_broadcast_and_notify(env, monkeypatch):
    c, sb = env
    sent = []

    async def fake_send(tid, text):
        sent.append((tid, text))
        return True
    admin_core._deps["tg_send"] = fake_send
    sb.add_user("tg-a", "tg501@t.me")
    sb.add_user("tg-b", "tg502@t.me", plan="pro", plan_until=(datetime.now(timezone.utc) + timedelta(days=3)).isoformat())
    assert api(c, "broadcast_preview", {"audience": "all"}).json()["count"] == 3          # 501, 502, 111(ulangan)
    assert api(c, "broadcast_preview", {"audience": "pro"}).json()["count"] == 2          # 502 (Pro) va admin (VIP)
    r = api(c, "broadcast", {"audience": "free", "text": "Salom <b>hamma</b>"}).json()
    time.sleep(0.6)
    st = api(c, "broadcast_status", {"job": r["job"]}).json()
    assert st["done"] and st["sent"] == r["total"] == len(sent) == 1 and sent[0][0] == 501
    assert api(c, "broadcast", {"text": "x"}).status_code == 400
