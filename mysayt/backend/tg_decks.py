"""
backend/tg_decks.py — Telegram bot uchun slayd yaratish (server tomonda).

AI (JSON) -> bitta "sahna" (scene) tavsifi -> uchta fayl:  PPTX  /  PDF  /  HTML (mustaqil namoyish).
Uchala format BIR XIL sahnadan chiziladi, shuning uchun ko'rinishi bir xil bo'ladi.

Koordinatalar: 960 x 540 (sayt bilan bir xil). PPTX da 1 px = 1 pt (13.333in x 7.5in).
Matn o'lchami DejaVu Sans (eng keng shrift) bilan o'lchanadi — boshqa shriftlarda (Arial, brauzer shrifti) ham sig'adi.
"""
from __future__ import annotations

from collections import OrderedDict
import base64
import html as _html
import io
import ipaddress
import json
import os
import re
import socket
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

W, H = 960, 540
LH = 1.22                                   # qator balandligi (o'lcham ko'paytmasi)
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
SYS_FONT_DIR = "/usr/share/fonts/truetype/dejavu"

LAYOUTS = ("title", "bullets", "cards", "stats", "quote", "closing")

THEMES: Dict[str, Dict[str, str]] = {
    #            qora/to'q   asosiy      urg'u       fon        matn       xira       kartochka   och ton
    "ocean":  dict(dark="#0B1F4D", primary="#1D4ED8", accent="#06B6D4", bg="#F8FAFC", text="#0F172A", muted="#64748B", card="#FFFFFF", tint="#E0F2FE", label="🔵 Okean"),
    "violet": dict(dark="#2E1065", primary="#6D28D9", accent="#F59E0B", bg="#FAF5FF", text="#1E1B4B", muted="#6B7280", card="#FFFFFF", tint="#EDE9FE", label="🟣 Binafsha"),
    "forest": dict(dark="#052E16", primary="#15803D", accent="#84CC16", bg="#F7FEF9", text="#14281D", muted="#5B6B61", card="#FFFFFF", tint="#DCFCE7", label="🟢 O'rmon"),
    "sunset": dict(dark="#431407", primary="#C2410C", accent="#F59E0B", bg="#FFFBF5", text="#2A1608", muted="#7C6A5C", card="#FFFFFF", tint="#FFEDD5", label="🟠 Quyosh"),
    "rose":   dict(dark="#500724", primary="#BE185D", accent="#FB7185", bg="#FFF7FA", text="#2D0A1A", muted="#7A5C69", card="#FFFFFF", tint="#FFE4EC", label="🌸 Atirgul"),
    "slate":  dict(dark="#0B1220", primary="#1E293B", accent="#38BDF8", bg="#F8FAFC", text="#0F172A", muted="#64748B", card="#FFFFFF", tint="#E2E8F0", label="⚫ Grafit"),
    "teal":   dict(dark="#042F2E", primary="#0F766E", accent="#F97316", bg="#F6FFFE", text="#0B2B29", muted="#5A7270", card="#FFFFFF", tint="#CCFBF1", label="🩵 Zumrad"),
}
DEFAULT_THEME = "ocean"

# ---------------------------------------------------------------------------------------------
# Matnni tozalash
# ---------------------------------------------------------------------------------------------
_EMOJI_RE = re.compile("[\U00010000-\U0010FFFF☀-⛿✀-➿⬀-⯿︀-️​-‍⁠]")
_MD_RE = re.compile(r"(\*\*|__|`|^#+\s*)")


def clean(s: Any, limit: int = 0) -> str:
    t = "" if s is None else str(s)
    t = _EMOJI_RE.sub("", t)
    t = _MD_RE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    if limit and len(t) > limit:
        cut = t[:limit].rsplit(" ", 1)[0].rstrip(",;:-– ")
        t = (cut or t[:limit]) + "…"
    return t


# ---------------------------------------------------------------------------------------------
# Shriftlar va o'lchash
# ---------------------------------------------------------------------------------------------
_FONT: Optional[Dict[str, str]] = None


def fonts() -> Dict[str, str]:
    """reportlab shriftlarini ro'yxatdan o'tkazadi. DejaVu topilmasa Helvetica (faqat lotin)."""
    global _FONT
    if _FONT is not None:
        return _FONT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    files = {"r": ("SS", "DejaVuSans.ttf"), "b": ("SS-B", "DejaVuSans-Bold.ttf"), "i": ("SS-I", "DejaVuSans-Oblique.ttf")}
    out: Dict[str, str] = {}
    fallback = {"r": "Helvetica", "b": "Helvetica-Bold", "i": "Helvetica-Oblique"}
    for k, (name, fn) in files.items():
        path = next((p for p in (os.path.join(FONT_DIR, fn), os.path.join(SYS_FONT_DIR, fn)) if os.path.isfile(p)), None)
        try:
            if path:
                pdfmetrics.registerFont(TTFont(name, path))
                out[k] = name
                continue
        except Exception as e:  # pragma: no cover
            print(f"[DECK] shrift yuklanmadi {fn}: {e}")
        out[k] = fallback[k]
    _FONT = out
    return out


def _fk(bold: bool, italic: bool) -> str:
    f = fonts()
    return f["b"] if bold else (f["i"] if italic else f["r"])


def text_w(s: str, size: float, bold: bool = False, italic: bool = False) -> float:
    from reportlab.pdfbase.pdfmetrics import stringWidth
    return stringWidth(s, _fk(bold, italic), size)


def wrap(text: str, size: float, width: float, bold: bool = False, italic: bool = False) -> List[str]:
    words = text.split(" ")
    lines: List[str] = []
    cur = ""
    for w in words:
        if not w:
            continue
        cand = (cur + " " + w) if cur else w
        if text_w(cand, size, bold, italic) <= width:
            cur = cand
            continue
        if cur:
            lines.append(cur)
            cur = ""
        while text_w(w, size, bold, italic) > width and len(w) > 1:     # juda uzun so'z — harf bo'yicha bo'lamiz
            k = len(w)
            while k > 1 and text_w(w[:k], size, bold, italic) > width:
                k -= 1
            lines.append(w[:k])
            w = w[k:]
        cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def fit(text: str, width: float, height: float, max_size: int, min_size: int, bold: bool = False, italic: bool = False,
        lh: float = LH) -> Tuple[int, List[str]]:
    """Matn (width x height) ga sig'adigan eng katta o'lchamni tanlaydi."""
    size = max_size
    longest = max((len(w) for w in text.split(" ")), default=0)
    while size >= min_size:
        lines = wrap(text, size, width, bold, italic)
        whole = all(text_w(w, size, bold, italic) <= width for w in text.split(" ") if w) if longest > 6 else True
        if whole and len(lines) * size * lh <= height + 0.5:
            return size, lines
        size -= 1
    return min_size, wrap(text, min_size, width, bold, italic)


# ---------------------------------------------------------------------------------------------
# Ranglar
# ---------------------------------------------------------------------------------------------
def _rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return "#%02X%02X%02X" % tuple(round(ra[i] + (rb[i] - ra[i]) * t) for i in range(3))


# ---------------------------------------------------------------------------------------------
# AI javobini tozalash va tekshirish
# ---------------------------------------------------------------------------------------------
def extract_json(text: str) -> Optional[dict]:
    """AI javobidan birinchi to'liq JSON obyektini oladi (```json``` va <think> bloklari bilan ham)."""
    if not text:
        return None
    t = re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", text, flags=re.I).strip()
    try:
        v = json.loads(t)
        return v if isinstance(v, dict) else None
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if m:
        try:
            v = json.loads(m.group(1))
            if isinstance(v, dict):
                return v
        except Exception:
            pass
    start = t.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(t)):
            ch = t[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        v = json.loads(t[start:i + 1])
                        if isinstance(v, dict):
                            return v
                    except Exception:
                        pass
                    break
        start = t.find("{", start + 1)
    return None


def _as_list(v: Any) -> list:
    return v if isinstance(v, list) else []


def normalize_slide(s: Any) -> Optional[dict]:
    if not isinstance(s, dict):
        return None
    lay = str(s.get("layout") or "").strip().lower()
    if lay not in LAYOUTS:
        lay = "bullets" if (s.get("bullets") or s.get("points")) else ("cards" if s.get("cards") else "")
    out: Dict[str, Any] = {"layout": lay, "notes": clean(s.get("notes"), 400), "image": clean(s.get("image"), 80)}
    title = clean(s.get("title"), 90)
    if lay in ("title", "closing"):
        out.update(title=title or "…", subtitle=clean(s.get("subtitle"), 140))
    elif lay == "bullets":
        items = [clean(b, 150) for b in _as_list(s.get("bullets") or s.get("points"))]
        items = [b for b in items if b][:6]
        if not items:
            return None
        out.update(title=title, bullets=items)
    elif lay == "cards":
        cards = []
        for c in _as_list(s.get("cards")):
            if isinstance(c, dict):
                hd, tx = clean(c.get("heading") or c.get("title"), 42), clean(c.get("text") or c.get("body"), 150)
            else:
                hd, tx = "", clean(c, 150)
            if hd or tx:
                cards.append({"heading": hd, "text": tx})
        cards = cards[:4]
        if len(cards) < 2:
            return None
        out.update(title=title, cards=cards)
        out["image"] = ""
    elif lay == "stats":
        stats = []
        for c in _as_list(s.get("stats")):
            if isinstance(c, dict):
                v, lb = clean(c.get("value"), 14), clean(c.get("label"), 70)
                if v:
                    stats.append({"value": v, "label": lb})
        stats = stats[:4]
        if len(stats) < 2:
            return None
        out.update(title=title, stats=stats)
        out["image"] = ""
    elif lay == "quote":
        q = clean(s.get("text") or s.get("quote"), 220)
        if not q:
            return None
        out.update(text=q, author=clean(s.get("author"), 60), title=title)
        out["image"] = ""
    else:
        return None
    return out


def normalize_deck(raw: Any, n: int, topic: str = "") -> Optional[dict]:
    """AI chiqargan JSON ni xavfsiz, sig'adigan ko'rinishga keltiradi. n = so'ralgan slaydlar soni."""
    if not isinstance(raw, dict):
        return None
    slides_raw = raw.get("slides")
    if not isinstance(slides_raw, list):
        return None
    slides = [x for x in (normalize_slide(s) for s in slides_raw) if x]
    if not slides:
        return None
    title = clean(raw.get("title"), 90) or clean(topic, 90) or slides[0].get("title") or "Taqdimot"
    theme = str(raw.get("theme") or "").strip().lower()
    if theme not in THEMES:
        theme = DEFAULT_THEME
    if slides[0]["layout"] != "title":
        slides.insert(0, {"layout": "title", "title": title, "subtitle": clean(raw.get("subtitle"), 140), "notes": "", "image": ""})
    n = max(1, int(n or len(slides)))
    if len(slides) > n:
        closing = next((s for s in reversed(slides) if s["layout"] == "closing"), None)
        slides = slides[:n]
        if closing is not None and n >= 3 and slides[-1]["layout"] != "closing":
            slides[-1] = closing
    return {"title": title, "subtitle": clean(raw.get("subtitle"), 140), "theme": theme, "slides": slides}


# ---------------------------------------------------------------------------------------------
# Rasm tayyorlash (Pillow)
# ---------------------------------------------------------------------------------------------
def cover_jpeg(data: bytes, w: int, h: int, scale: float = 1.6, quality: int = 80) -> Optional[bytes]:
    """Rasmni (w:h) nisbatga 'cover' usulida kesib, JPEG qiladi. Buzuq rasm bo'lsa None."""
    try:
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im)
        if im.width < 200 or im.height < 120:
            return None
        if im.mode not in ("RGB",):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            try:
                rgba = im.convert("RGBA")
                bg.paste(rgba, mask=rgba.split()[-1])
                im = bg
            except Exception:
                im = im.convert("RGB")
        tw, th = max(2, int(w * scale)), max(2, int(h * scale))
        im = ImageOps.fit(im, (tw, th), method=Image.LANCZOS, centering=(0.5, 0.4))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality, optimize=True)
        return buf.getvalue()
    except Exception:
        return None


# ---------------------------------------------------------------------------------------------
# Sahna (scene)
# ---------------------------------------------------------------------------------------------
class Scene:
    def __init__(self, bg: str):
        self.bg = bg
        self.items: List[dict] = []
        self.notes = ""

    def rect(self, x, y, w, h, fill, r=0, line=None, lw=1):
        self.items.append(dict(t="rect", x=x, y=y, w=w, h=h, fill=fill, r=r, line=line, lw=lw))

    def oval(self, x, y, w, h, fill):
        self.items.append(dict(t="oval", x=x, y=y, w=w, h=h, fill=fill))

    def image(self, x, y, w, h, data, r=0):
        self.items.append(dict(t="img", x=x, y=y, w=w, h=h, data=data, r=r))

    def text(self, x, y, w, h, text, size, color, bold=False, italic=False, align="l", anchor="t", lines=None):
        size = int(round(size))
        if lines is None:
            lines = wrap(text, size, w, bold, italic)
        self.items.append(dict(t="text", x=x, y=y, w=w, h=h, text=text, size=size, color=color, bold=bold, italic=italic,
                               align=align, anchor=anchor, lines=lines))


def _footer(sc: Scene, th: dict, deck_title: str, idx: int, total: int):
    sc.text(56, 502, 640, 20, deck_title, 12, th["muted"], lines=[deck_title[:90]])
    num = f"{idx} / {total}"
    sc.text(804, 502, 100, 20, num, 12, th["muted"], align="r", lines=[num])


def _topbar(sc: Scene, th: dict):
    sc.rect(0, 0, W, 10, th["primary"])
    sc.rect(0, 0, 140, 10, th["accent"])


def _heading(sc: Scene, th: dict, title: str, width: float) -> None:
    size, lines = fit(title, width, 84, 34, 22, bold=True)
    sc.text(56, 38, width, 84, title, size, th["primary"], bold=True, lines=lines)
    sc.rect(56, 128, 64, 5, th["accent"], r=2)


def _dark_slide(sc: Scene, th: dict, title: str, subtitle: str, img: Optional[bytes], kicker: str) -> None:
    dark, prim, acc = th["dark"], th["primary"], th["accent"]
    text_w_ = 500 if img else 700
    if img:
        sc.rect(0, 0, W, H, dark)
        sc.image(580, 0, 380, 540, img, 0)
        sc.rect(572, 0, 8, 540, acc)
    else:
        sc.oval(600, -170, 600, 600, mix(dark, prim, 0.55))
        sc.oval(720, 330, 320, 320, mix(dark, acc, 0.45))
        sc.oval(520, 380, 90, 90, mix(dark, acc, 0.7))
    sc.rect(64, 168, 70, 6, acc, r=3)
    if kicker:
        sc.text(64, 130, text_w_, 26, kicker, 15, mix("#FFFFFF", dark, 0.35), bold=True, lines=[kicker])
    size, lines = fit(title, text_w_, 190, 54, 28, bold=True)
    sc.text(64, 196, text_w_, 190, title, size, "#FFFFFF", bold=True, lines=lines)
    used = len(lines) * size * LH
    if subtitle:
        ssz, slines = fit(subtitle, text_w_, 110, 22, 14)
        sc.text(64, 196 + used + 14, text_w_, 110, subtitle, ssz, mix("#FFFFFF", dark, 0.28), lines=slines)


def build_scenes(deck: dict, images: Optional[Dict[int, bytes]] = None, lang: str = "uz") -> List[Scene]:
    th = THEMES.get(deck.get("theme"), THEMES[DEFAULT_THEME])
    slides = deck["slides"]
    total = len(slides)
    deck_title = deck.get("title") or ""
    images = images or {}
    scenes: List[Scene] = []
    for i, s in enumerate(slides):
        lay = s["layout"]
        idx = i + 1
        raw_img = images.get(i)
        if lay in ("title", "closing"):
            sc = Scene(th["dark"])
            img = cover_jpeg(raw_img, 380, 540) if (raw_img and lay == "title") else None
            _dark_slide(sc, th, s.get("title") or deck_title, s.get("subtitle", ""), img, "SLIDE STUDIO AI" if lay == "title" else "")
        elif lay == "bullets":
            sc = Scene(th["bg"])
            _topbar(sc, th)
            img = cover_jpeg(raw_img, 304, 330) if raw_img else None
            body_w = 512 if img else 848
            _heading(sc, th, s["title"], body_w if img else 848)
            if img:
                sc.image(600, 150, 304, 330, img, 18)
            blocks = None
            top_size = 30 if (len(s["bullets"]) <= 3 and not img) else 26
            for size in range(top_size, 15, -1):
                tmp = [wrap(b, size, body_w - 28) for b in s["bullets"]]
                gap = 14 if size >= 20 else 10
                h = sum(len(l) * size * LH for l in tmp) + gap * (len(tmp) - 1)
                if h <= 330:
                    blocks = (size, tmp, gap)
                    break
            if blocks is None:
                size = 16
                blocks = (size, [wrap(b, size, body_w - 28) for b in s["bullets"]], 8)
            size, tmp, gap = blocks
            total_h = sum(len(l) * size * LH for l in tmp) + gap * (len(tmp) - 1)
            y = 152 + (max(0.0, 326 - total_h) / 2 if total_h < 260 else 0)
            for b, lines in zip(s["bullets"], tmp):
                hh = len(lines) * size * LH
                d = max(8, round(size * 0.4))
                sc.oval(56, y + (size * LH - d) / 2, d, d, th["accent"])
                sc.text(56 + 28, y, body_w - 28, hh, b, size, th["text"], lines=lines)
                y += hh + gap
            _footer(sc, th, deck_title, idx, total)
        elif lay == "cards":
            sc = Scene(th["bg"])
            _topbar(sc, th)
            _heading(sc, th, s["title"], 848)
            n = len(s["cards"])
            gap = 22
            if n == 4:                                   # 2 x 2 to'r — so'zlar bo'linmaydi
                cw, ch = (848 - gap) / 2, 150
                cells = [(56 + (k % 2) * (cw + gap), 154 + (k // 2) * (ch + 16)) for k in range(4)]
                for (x, y), (k, c) in zip(cells, enumerate(s["cards"])):
                    sc.rect(x, y, cw, ch, th["card"], r=16, line=mix(th["tint"], th["primary"], 0.12), lw=1.2)
                    sc.rect(x, y + 14, 6, ch - 28, th["accent"], r=3)
                    sc.oval(x + 22, y + 20, 40, 40, th["primary"])
                    sc.text(x + 22, y + 20, 40, 40, str(k + 1), 19, "#FFFFFF", bold=True, align="c", anchor="m", lines=[str(k + 1)])
                    inner = cw - 92
                    hs, hl = fit(c["heading"] or " ", inner, 52, 21, 15, bold=True)
                    hh = len(hl) * hs * LH if c["heading"] else 0
                    if c["heading"]:
                        sc.text(x + 78, y + 18, inner, hh, c["heading"], hs, th["primary"], bold=True, lines=hl)
                    ty = y + 18 + hh + 6
                    bs, bl = fit(c["text"] or " ", inner, y + ch - 12 - ty, 17, 12)
                    if c["text"]:
                        sc.text(x + 78, ty, inner, len(bl) * bs * LH, c["text"], bs, th["text"], lines=bl)
            else:
                cw = (848 - gap * (n - 1)) / n
                ch = 316
                for k, c in enumerate(s["cards"]):
                    x = 56 + k * (cw + gap)
                    y = 156
                    sc.rect(x, y, cw, ch, th["card"], r=18, line=mix(th["tint"], th["primary"], 0.12), lw=1.2)
                    sc.rect(x, y, cw, 7, th["accent"], r=0)
                    sc.oval(x + 20, y + 26, 42, 42, th["primary"])
                    sc.text(x + 20, y + 26, 42, 42, str(k + 1), 20, "#FFFFFF", bold=True, align="c", anchor="m", lines=[str(k + 1)])
                    inner = cw - 40
                    hs, hl = fit(c["heading"] or " ", inner, 70, 24 if n == 2 else 22, 15, bold=True)
                    hh = len(hl) * hs * LH if c["heading"] else 0
                    if c["heading"]:
                        sc.text(x + 20, y + 84, inner, hh, c["heading"], hs, th["primary"], bold=True, lines=hl)
                    ty = y + 84 + hh + 10
                    bs, bl = fit(c["text"] or " ", inner, y + ch - 18 - ty, 20 if n == 2 else 18, 12)
                    if c["text"]:
                        sc.text(x + 20, ty, inner, len(bl) * bs * LH, c["text"], bs, th["text"], lines=bl)
            _footer(sc, th, deck_title, idx, total)
        elif lay == "stats":
            sc = Scene(th["bg"])
            _topbar(sc, th)
            _heading(sc, th, s["title"], 848)
            n = len(s["stats"])
            gap = 22
            cw = (848 - gap * (n - 1)) / n
            ch = 280
            for k, c in enumerate(s["stats"]):
                x, y = 56 + k * (cw + gap), 170
                sc.rect(x, y, cw, ch, th["tint"], r=20)
                sc.rect(x + 24, y + 28, 44, 6, th["accent"], r=3)
                vs, vl = fit(c["value"], cw - 40, 80, 58 if n < 4 else 44, 24, bold=True)
                sc.text(x + 20, y + 64, cw - 40, 80, c["value"], vs, th["primary"], bold=True, align="l", anchor="m", lines=vl)
                ls, ll = fit(c["label"] or " ", cw - 40, ch - 170, 19, 12)
                if c["label"]:
                    sc.text(x + 20, y + 160, cw - 40, len(ll) * ls * LH, c["label"], ls, th["text"], lines=ll)
            _footer(sc, th, deck_title, idx, total)
        elif lay == "quote":
            sc = Scene(th["tint"])
            sc.rect(0, 0, 14, H, th["primary"])
            sc.text(70, 40, 160, 150, "“", 150, th["accent"], bold=True, lines=["“"])
            qs, ql = fit(s["text"], 760, 250, 38, 20, italic=True)
            qh = len(ql) * qs * LH
            block = qh + (52 if s.get("author") else 0)
            qy = max(150, 120 + (360 - block) / 2)
            sc.text(100, qy, 760, qh, s["text"], qs, th["text"], italic=True, lines=ql)
            if s.get("author"):
                a = "— " + s["author"]
                sc.text(100, qy + qh + 24, 760, 28, a, 20, th["primary"], bold=True, lines=[a])
            _footer(sc, th, deck_title, idx, total)
        else:  # pragma: no cover
            sc = Scene(th["bg"])
        sc.notes = s.get("notes", "")
        scenes.append(sc)
    return scenes


# ---------------------------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------------------------
def render_pdf(scenes: List[Scene], title: str) -> bytes:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    f = fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H), pageCompression=1)
    c.setTitle(title or "Taqdimot")
    c.setAuthor("Slide Studio AI")
    for sc in scenes:
        c.setFillColor(HexColor(sc.bg))
        c.rect(0, 0, W, H, stroke=0, fill=1)
        for it in sc.items:
            t = it["t"]
            if t in ("rect", "oval"):
                x, w, h = it["x"], it["w"], it["h"]
                y = H - it["y"] - h
                c.setFillColor(HexColor(it["fill"]))
                if t == "oval":
                    c.ellipse(x, y, x + w, y + h, stroke=0, fill=1)
                else:
                    line = it.get("line")
                    if line:
                        c.setStrokeColor(HexColor(line))
                        c.setLineWidth(it.get("lw", 1))
                    r = min(it.get("r", 0), min(w, h) / 2)
                    if r > 0:
                        c.roundRect(x, y, w, h, r, stroke=1 if line else 0, fill=1)
                    else:
                        c.rect(x, y, w, h, stroke=1 if line else 0, fill=1)
            elif t == "img":
                x, w, h = it["x"], it["w"], it["h"]
                y = H - it["y"] - h
                c.saveState()
                if it.get("r"):
                    p = c.beginPath()
                    p.roundRect(x, y, w, h, it["r"])
                    c.clipPath(p, stroke=0, fill=0)
                c.drawImage(ImageReader(io.BytesIO(it["data"])), x, y, w, h)
                c.restoreState()
            elif t == "text":
                size = it["size"]
                font = f["b"] if it["bold"] else (f["i"] if it["italic"] else f["r"])
                c.setFont(font, size)
                c.setFillColor(HexColor(it["color"]))
                lines = it["lines"]
                block = len(lines) * size * LH
                top = it["y"]
                if it["anchor"] == "m":
                    top = it["y"] + (it["h"] - block) / 2
                for k, ln in enumerate(lines):
                    base = H - (top + k * size * LH + size * (LH / 2 + 0.346))
                    if it["align"] == "c":
                        c.drawCentredString(it["x"] + it["w"] / 2, base, ln)
                    elif it["align"] == "r":
                        c.drawRightString(it["x"] + it["w"], base, ln)
                    else:
                        c.drawString(it["x"], base, ln)
        c.showPage()
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------------------------------------
# PPTX
# ---------------------------------------------------------------------------------------------
def render_pptx(scenes: List[Scene], title: str) -> bytes:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
    from pptx.oxml.ns import qn
    from pptx.util import Emu, Pt
    from lxml import etree

    E = 12700                                    # 1 px = 1 pt = 12700 EMU
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(W * E), Emu(H * E)
    try:
        prs.core_properties.title = title or "Taqdimot"
        prs.core_properties.author = "Slide Studio AI"
    except Exception:
        pass
    blank = prs.slide_layouts[6]
    align_map = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}

    def rgb(h: str) -> RGBColor:
        return RGBColor.from_string(h.lstrip("#").upper())

    for sc in scenes:
        slide = prs.slides.add_slide(blank)
        bgf = slide.background.fill
        bgf.solid()
        bgf.fore_color.rgb = rgb(sc.bg)
        for it in sc.items:
            t = it["t"]
            x, y, w, h = (int(round(it[k] * E)) for k in ("x", "y", "w", "h"))
            if t in ("rect", "oval"):
                rr = it.get("r", 0) if t == "rect" else 0
                kind = MSO_SHAPE.OVAL if t == "oval" else (MSO_SHAPE.ROUNDED_RECTANGLE if rr > 0 else MSO_SHAPE.RECTANGLE)
                shp = slide.shapes.add_shape(kind, Emu(x), Emu(y), Emu(w), Emu(h))
                if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
                    shp.adjustments[0] = min(0.5, rr / max(1.0, min(it["w"], it["h"])))
                shp.fill.solid()
                shp.fill.fore_color.rgb = rgb(it["fill"])
                if it.get("line"):
                    shp.line.color.rgb = rgb(it["line"])
                    shp.line.width = Pt(it.get("lw", 1))
                else:
                    shp.line.fill.background()
                try:
                    shp.shadow.inherit = False
                    st_el = shp._element.find(qn("p:style"))
                    if st_el is not None:
                        shp._element.remove(st_el)
                except Exception:
                    pass
            elif t == "img":
                pic = slide.shapes.add_picture(io.BytesIO(it["data"]), Emu(x), Emu(y), Emu(w), Emu(h))
                if it.get("r"):
                    try:
                        pic.auto_shape_type = MSO_SHAPE.ROUNDED_RECTANGLE
                        geom = pic._element.spPr.find(qn("a:prstGeom"))
                        av = geom.find(qn("a:avLst"))
                        if av is None:
                            av = etree.SubElement(geom, qn("a:avLst"))
                        for ch in list(av):
                            av.remove(ch)
                        gd = etree.SubElement(av, qn("a:gd"))
                        gd.set("name", "adj")
                        gd.set("fmla", "val %d" % int(min(0.5, it["r"] / max(1.0, min(it["w"], it["h"]))) * 100000))
                    except Exception:
                        pass
            elif t == "text":
                tb = slide.shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
                tf = tb.text_frame
                tf.word_wrap = True
                tf.auto_size = MSO_AUTO_SIZE.NONE
                tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
                tf.vertical_anchor = MSO_ANCHOR.MIDDLE if it["anchor"] == "m" else MSO_ANCHOR.TOP
                p = tf.paragraphs[0]
                p.alignment = align_map.get(it["align"], PP_ALIGN.LEFT)
                p.line_spacing = Pt(it["size"] * LH)
                r = p.add_run()
                r.text = it["text"]
                r.font.size = Pt(it["size"])
                r.font.bold = bool(it["bold"])
                r.font.italic = bool(it["italic"])
                r.font.name = "Arial"
                r.font.color.rgb = rgb(it["color"])
        if sc.notes:
            try:
                slide.notes_slide.notes_text_frame.text = sc.notes
            except Exception:
                pass
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------------------------
# HTML (mustaqil namoyish)
# ---------------------------------------------------------------------------------------------
_HTML_HEAD = """<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:100%;height:100%;background:#0b0f19;overflow:hidden;font-family:"Segoe UI",Roboto,"Helvetica Neue",Arial,"DejaVu Sans",sans-serif;-webkit-tap-highlight-color:transparent}}
#view{{position:fixed;inset:0;display:flex;align-items:center;justify-content:center}}
#stage{{position:relative;width:960px;height:540px;transform-origin:center center;flex:none}}
.slide{{position:absolute;inset:0;width:960px;height:540px;overflow:hidden;opacity:0;visibility:hidden;transition:opacity .35s ease}}
.slide.on{{opacity:1;visibility:visible}}
.slide>*{{position:absolute}}
.t{{display:flex;flex-direction:column;overflow:visible}}
.t>div{{width:100%}}
.slide img{{object-fit:cover;display:block}}
#bar{{position:fixed;left:0;bottom:0;height:3px;background:#38bdf8;width:0;transition:width .3s}}
#ui{{position:fixed;right:12px;bottom:10px;display:flex;gap:8px;align-items:center;color:#cbd5e1;font:600 12px system-ui,sans-serif;opacity:.0;transition:opacity .25s}}
body:hover #ui,body.touch #ui{{opacity:.9}}
#ui button{{background:rgba(255,255,255,.12);border:0;color:#fff;border-radius:8px;padding:6px 10px;font:600 13px system-ui;cursor:pointer}}
@media print{{
  @page{{size:960px 540px;margin:0}}
  html,body{{background:#fff;overflow:visible;height:auto}}
  #view{{position:static;display:block}}
  #stage{{transform:none!important;width:960px;height:auto}}
  .slide{{position:relative;opacity:1;visibility:visible;page-break-after:always;break-after:page}}
  #bar,#ui{{display:none}}
}}
</style></head><body>
<div id="view"><div id="stage">
"""
_HTML_TAIL = """</div></div>
<div id="bar"></div>
<div id="ui"><button id="pv">&#8592;</button><span id="ct"></span><button id="nx">&#8594;</button><button id="fs">&#x26F6;</button></div>
<script>
(function(){{
var S=[].slice.call(document.querySelectorAll('.slide')),i=0,st=document.getElementById('stage');
function fitStage(){{var k=Math.min(innerWidth/960,innerHeight/540);st.style.transform='scale('+k+')';}}
function show(n){{i=Math.max(0,Math.min(S.length-1,n));S.forEach(function(s,k){{s.classList.toggle('on',k===i)}});
document.getElementById('ct').textContent=(i+1)+' / '+S.length;document.getElementById('bar').style.width=((i+1)/S.length*100)+'%';
try{{history.replaceState(null,'','#'+(i+1))}}catch(e){{}}}}
function next(){{show(i+1)}}function prev(){{show(i-1)}}
addEventListener('resize',fitStage);fitStage();
addEventListener('keydown',function(e){{var k=e.key;
if(k==='ArrowRight'||k==='PageDown'||k===' '||k==='Enter'){{e.preventDefault();next()}}
else if(k==='ArrowLeft'||k==='PageUp'||k==='Backspace'){{e.preventDefault();prev()}}
else if(k==='Home')show(0);else if(k==='End')show(S.length-1);
else if(k==='f'||k==='F')fs();}});
function fs(){{var d=document.documentElement;if(!document.fullscreenElement){{(d.requestFullscreen||d.webkitRequestFullscreen||function(){{}}).call(d)}}else{{(document.exitFullscreen||document.webkitExitFullscreen||function(){{}}).call(document)}}}}
document.getElementById('nx').onclick=function(e){{e.stopPropagation();next()}};
document.getElementById('pv').onclick=function(e){{e.stopPropagation();prev()}};
document.getElementById('fs').onclick=function(e){{e.stopPropagation();fs()}};
var x0=null;
addEventListener('touchstart',function(e){{document.body.classList.add('touch');x0=e.touches[0].clientX}},{{passive:true}});
addEventListener('touchend',function(e){{if(x0===null)return;var dx=e.changedTouches[0].clientX-x0;x0=null;if(Math.abs(dx)>40){{dx<0?next():prev()}}}},{{passive:true}});
document.getElementById('view').addEventListener('click',function(e){{if(e.clientX>innerWidth*0.35)next();else prev()}});
var h=parseInt((location.hash||'').slice(1),10);show(isNaN(h)?0:h-1);
}})();
</script></body></html>
""".replace("{{", "{").replace("}}", "}")


def render_html(scenes: List[Scene], title: str, lang: str = "uz") -> bytes:
    e = _html.escape
    out = [_HTML_HEAD.format(title=e(title or "Taqdimot"), lang=e(lang or "uz"))]
    for sc in scenes:
        out.append(f'<section class="slide" style="background:{sc.bg}">')
        for it in sc.items:
            t = it["t"]
            pos = f'left:{it["x"]:.1f}px;top:{it["y"]:.1f}px;width:{it["w"]:.1f}px;height:{it["h"]:.1f}px;'
            if t == "rect":
                st = pos + f'background:{it["fill"]};'
                if it.get("r"):
                    st += f'border-radius:{it["r"]}px;'
                if it.get("line"):
                    st += f'border:{it.get("lw", 1)}px solid {it["line"]};'
                out.append(f'<div style="{st}"></div>')
            elif t == "oval":
                out.append(f'<div style="{pos}background:{it["fill"]};border-radius:50%"></div>')
            elif t == "img":
                b64 = base64.b64encode(it["data"]).decode("ascii")
                rad = f'border-radius:{it["r"]}px;' if it.get("r") else ""
                out.append(f'<img alt="" src="data:image/jpeg;base64,{b64}" style="{pos}{rad}">')
            elif t == "text":
                jc = "center" if it["anchor"] == "m" else "flex-start"
                st = (pos + f'justify-content:{jc};font-size:{it["size"]}px;line-height:{it["size"] * LH:.1f}px;color:{it["color"]};'
                      f'font-weight:{700 if it["bold"] else 400};text-align:{ {"l": "left", "c": "center", "r": "right"}[it["align"]] };')
                if it["italic"]:
                    st += "font-style:italic;"
                out.append(f'<div class="t" style="{st}"><div>{e(it["text"])}</div></div>')
        out.append("</section>")
    out.append(_HTML_TAIL)
    return "".join(out).encode("utf-8")


# ---------------------------------------------------------------------------------------------
# Yagona kirish nuqtasi
# ---------------------------------------------------------------------------------------------
def safe_filename(title: str, ext: str) -> str:
    base = re.sub(r"[^\w\-]+", "_", clean(title, 40), flags=re.U).strip("_") or "taqdimot"
    return f"{base}.{ext}"


def export(deck: dict, images: Optional[Dict[int, bytes]], fmt: str, lang: str = "uz") -> Tuple[str, bytes, str]:
    """(fayl_nomi, bayt, mime) qaytaradi. fmt: pptx | pdf | html."""
    scenes = build_scenes(deck, images, lang)
    title = deck.get("title") or "Taqdimot"
    if fmt == "pptx":
        return safe_filename(title, "pptx"), render_pptx(scenes, title), "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if fmt == "pdf":
        return safe_filename(title, "pdf"), render_pdf(scenes, title), "application/pdf"
    if fmt == "html":
        return safe_filename(title, "html"), render_html(scenes, title, lang), "text/html; charset=utf-8"
    raise ValueError("noma'lum format")


def export_all(deck: dict, images: Optional[Dict[int, bytes]], lang: str = "uz") -> List[Tuple[str, bytes, str]]:
    scenes = build_scenes(deck, images, lang)          # sahna bir marta quriladi (rasm kesish qimmat)
    title = deck.get("title") or "Taqdimot"
    return [
        (safe_filename(title, "pptx"), render_pptx(scenes, title), "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        (safe_filename(title, "pdf"), render_pdf(scenes, title), "application/pdf"),
        (safe_filename(title, "html"), render_html(scenes, title, lang), "text/html; charset=utf-8"),
    ]


# ---------------------------------------------------------------------------------------------
# Rasmlarni internetdan olish (xavfsiz: faqat ommaviy hostlar, hajm cheklangan)
# ---------------------------------------------------------------------------------------------
MAX_IMG_BYTES = 6 * 1024 * 1024


def _public_host(host: str) -> bool:
    try:
        for fam, _t, _p, _c, sa in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(sa[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                return False
        return True
    except Exception:
        return False


def download_image(url: str, timeout: float = 8.0) -> Optional[bytes]:
    """Sinxron (thread ichida chaqiriladi). Redirect'lar qo'lda tekshiriladi."""
    import httpx
    cur = url
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, headers={"User-Agent": "SlideStudio/1.0"}) as cl:
            for _ in range(4):
                u = urlparse(cur)
                if u.scheme not in ("http", "https") or not u.hostname or not _public_host(u.hostname):
                    return None
                with cl.stream("GET", cur) as r:
                    if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                        nxt = r.headers["location"]
                        cur = str(httpx.URL(cur).join(nxt))
                        continue
                    if r.status_code != 200:
                        return None
                    ct = (r.headers.get("content-type") or "").lower()
                    if ct and not ct.startswith("image/"):
                        return None
                    buf = bytearray()
                    for chunk in r.iter_bytes(65536):
                        buf.extend(chunk)
                        if len(buf) > MAX_IMG_BYTES:
                            return None
                    return bytes(buf)
    except Exception:
        return None
    return None


_IMG_URL_CACHE: "OrderedDict[str, str]" = OrderedDict()   # query -> tanlangan rasm manzili (faqat qisqa matn, fayl emas)


def find_image(query: str) -> Optional[bytes]:
    """Sinxron: qidiruv + yuklash. Bir mavzu uchun BIR XIL rasm: oldin tanlangan manzil eslab qolinadi,
    shuning uchun rang o'zgartirib qayta yuklaganda rasm almashib ketmaydi."""
    key = (query or "").strip().lower()
    cached = _IMG_URL_CACHE.get(key)
    if cached:
        data = download_image(cached)
        if data and cover_jpeg(data, 100, 100, scale=1.0) is not None:
            return data
    try:
        from backend.image_search import search_images
        res = search_images(query, "photo", 8) or []
    except Exception:
        return None
    tried = 0
    for r in res:
        u = (r or {}).get("url") or ""
        if not u or u.lower().split("?")[0].endswith(".gif"):
            continue
        tried += 1
        data = download_image(u)
        if data and cover_jpeg(data, 100, 100, scale=1.0) is not None:
            _IMG_URL_CACHE[key] = u
            while len(_IMG_URL_CACHE) > 800:
                _IMG_URL_CACHE.popitem(last=False)
            return data
        if tried >= 4:
            break
    return None
