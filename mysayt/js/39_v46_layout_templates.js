/* =====================================================================
 * 39_v46_layout_templates.js  (v46.8+)
 * Telegram bot (tg_decks.py) dagi professional layout'larni Fabric.js ga o'tkazish.
 * AI endi dizayn o'ylab o'tirmaydi — tayyor qolipga matn/raqam to'ldiradi.
 *
 * API:
 *   window.ssLayoutThemes
 *   window.ssBuildTemplateSlide(layout, data, themeKey) -> { objects, background }
 *   window.ssApplyTemplateSlide(cmd)  // AI action: template_slide
 *   window.ssApplyTemplateDeck(cmd)   // AI action: template_deck
 * ===================================================================== */
(function () {
  'use strict';
  if (window.ssBuildTemplateSlide) return;

  var THEMES = {
    ocean:  { dark: '#0B1F4D', primary: '#1D4ED8', accent: '#06B6D4', bg: '#F8FAFC', text: '#0F172A', muted: '#64748B', card: '#FFFFFF', tint: '#E0F2FE' },
    violet: { dark: '#2E1065', primary: '#6D28D9', accent: '#F59E0B', bg: '#FAF5FF', text: '#1E1B4B', muted: '#6B7280', card: '#FFFFFF', tint: '#EDE9FE' },
    forest: { dark: '#052E16', primary: '#15803D', accent: '#84CC16', bg: '#F7FEF9', text: '#14281D', muted: '#5B6B61', card: '#FFFFFF', tint: '#DCFCE7' },
    sunset: { dark: '#431407', primary: '#C2410C', accent: '#F59E0B', bg: '#FFFBF5', text: '#2A1608', muted: '#7C6A5C', card: '#FFFFFF', tint: '#FFEDD5' },
    rose:   { dark: '#500724', primary: '#BE185D', accent: '#FB7185', bg: '#FFF7FA', text: '#2D0A1A', muted: '#7A5C69', card: '#FFFFFF', tint: '#FFE4EC' },
    slate:  { dark: '#0B1220', primary: '#1E293B', accent: '#38BDF8', bg: '#F8FAFC', text: '#0F172A', muted: '#64748B', card: '#FFFFFF', tint: '#E2E8F0' },
    teal:   { dark: '#042F2E', primary: '#0F766E', accent: '#F97316', bg: '#F6FFFE', text: '#0B2B29', muted: '#5A7270', card: '#FFFFFF', tint: '#CCFBF1' }
  };
  window.ssLayoutThemes = THEMES;

  function th(key) {
    return THEMES[key] || THEMES.ocean;
  }
  function clean(s, lim) {
    var t = String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
    if (lim && t.length > lim) {
      var cut = t.slice(0, lim).replace(/\s+\S*$/, '');
      t = (cut || t.slice(0, lim)) + '…';
    }
    return t;
  }
  function txt(o) {
    return Object.assign({
      type: 'textbox', originX: 'left', originY: 'top', fontFamily: 'Montserrat',
      fontWeight: 'normal', textAlign: 'left', lineHeight: 1.2, selectable: true, evented: true
    }, o);
  }
  function rect(o) {
    return Object.assign({
      type: 'rect', originX: 'left', originY: 'top', rx: 16, ry: 16,
      strokeWidth: 0, selectable: true, evented: true
    }, o);
  }
  function topbar(t) {
    return rect({ left: 0, top: 0, width: 960, height: 8, fill: t.primary, rx: 0, ry: 0 });
  }
  function footer(t, deckTitle, idx, total) {
    var objs = [];
    if (deckTitle) {
      objs.push(txt({
        text: clean(deckTitle, 60), left: 40, top: 508, width: 700, height: 22,
        fontSize: 11, fill: t.muted, fontFamily: 'Inter'
      }));
    }
    objs.push(txt({
      text: String(idx) + ' / ' + String(total), left: 820, top: 508, width: 100, height: 22,
      fontSize: 11, fill: t.muted, textAlign: 'right', fontFamily: 'Inter'
    }));
    return objs;
  }

  /* ---------- LAYOUT BUILDERS ---------- */

  function buildTitle(data, t, meta) {
    var objects = [];
    var hasImg = !!(data.imageUrl && /^https?:\/\//i.test(data.imageUrl));
    // Left dark panel (bot style)
    objects.push(rect({ left: 0, top: 0, width: hasImg ? 520 : 960, height: 540, fill: t.dark, rx: 0, ry: 0 }));
    if (hasImg) {
      objects.push({
        type: 'image', src: data.imageUrl,
        left: 520, top: 0, width: 440, height: 540,
        originX: 'left', originY: 'top', selectable: true, evented: true
      });
    }
    objects.push(txt({
      text: 'SLIDE STUDIO AI', left: 56, top: 120, width: 400, height: 24,
      fontSize: 12, fill: t.accent, fontFamily: 'Inter', fontWeight: 'bold'
    }));
    objects.push(rect({ left: 56, top: 152, width: 48, height: 5, fill: t.accent, rx: 3, ry: 3 }));
    var title = clean(data.title || 'Sarlavha', 70);
    objects.push(txt({
      text: title, left: 56, top: 180, width: hasImg ? 430 : 840, height: 140,
      fontSize: title.length > 35 ? 34 : 44, fontWeight: 'bold', fill: '#FFFFFF'
    }));
    var sub = clean(data.subtitle || '', 120);
    if (sub) {
      objects.push(txt({
        text: sub, left: 56, top: 340, width: hasImg ? 420 : 800, height: 80,
        fontSize: 18, fill: 'rgba(255,255,255,0.78)', fontFamily: 'Inter'
      }));
    }
    return { objects: objects, background: t.dark };
  }

  function buildClosing(data, t, meta) {
    var objects = [];
    objects.push(rect({ left: 0, top: 0, width: 960, height: 540, fill: t.dark, rx: 0, ry: 0 }));
    objects.push(rect({ left: 0, top: 0, width: 12, height: 540, fill: t.accent, rx: 0, ry: 0 }));
    var title = clean(data.title || 'Rahmat!', 60);
    var sub = clean(data.subtitle || '', 100);
    objects.push(txt({
      text: title, left: 80, top: 200, width: 800, height: 100,
      fontSize: 44, fontWeight: 'bold', fill: '#FFFFFF', textAlign: 'center'
    }));
    if (sub) {
      objects.push(txt({
        text: sub, left: 120, top: 320, width: 720, height: 60,
        fontSize: 20, fill: 'rgba(255,255,255,0.75)', textAlign: 'center', fontFamily: 'Inter'
      }));
    }
    return { objects: objects, background: t.dark };
  }

  function buildBullets(data, t, meta) {
    var objects = [topbar(t)];
    var title = clean(data.title || '', 70);
    objects.push(txt({
      text: title, left: 48, top: 28, width: 860, height: 48,
      fontSize: 28, fontWeight: 'bold', fill: t.primary
    }));
    objects.push(rect({ left: 48, top: 82, width: 56, height: 5, fill: t.accent, rx: 3, ry: 3 }));

    var bullets = Array.isArray(data.bullets) ? data.bullets : [];
    bullets = bullets.slice(0, 6).map(function (b) { return clean(b, 120); }).filter(Boolean);
    var hasImg = !!(data.imageUrl && /^https?:\/\//i.test(data.imageUrl));
    var textW = hasImg ? 520 : 860;
    var y = 110;
    bullets.forEach(function (b) {
      objects.push(rect({
        left: 52, top: y + 8, width: 10, height: 10, fill: t.primary, rx: 5, ry: 5
      }));
      objects.push(txt({
        text: b, left: 78, top: y, width: textW - 30, height: 52,
        fontSize: 16, fill: t.text, fontFamily: 'Inter'
      }));
      y += 56;
    });
    if (hasImg) {
      objects.push({
        type: 'image', src: data.imageUrl,
        left: 600, top: 120, width: 310, height: 310,
        originX: 'left', originY: 'top', selectable: true, evented: true
      });
      // soft frame
      objects.push(rect({
        left: 600, top: 120, width: 310, height: 310, fill: 'transparent',
        stroke: t.tint, strokeWidth: 0, rx: 18, ry: 18, selectable: false, evented: false
      }));
    }
    objects = objects.concat(footer(t, meta && meta.deckTitle, meta && meta.idx, meta && meta.total));
    return { objects: objects, background: t.bg };
  }

  function buildCards(data, t, meta) {
    var objects = [topbar(t)];
    var title = clean(data.title || '', 70);
    objects.push(txt({
      text: title, left: 48, top: 28, width: 860, height: 48,
      fontSize: 28, fontWeight: 'bold', fill: t.primary
    }));
    objects.push(rect({ left: 48, top: 82, width: 56, height: 5, fill: t.accent, rx: 3, ry: 3 }));

    var cards = Array.isArray(data.cards) ? data.cards : [];
    cards = cards.slice(0, 4).map(function (c) {
      if (typeof c === 'string') return { heading: '', text: clean(c, 120) };
      return { heading: clean(c.heading || c.title, 36), text: clean(c.text || c.body, 130) };
    }).filter(function (c) { return c.heading || c.text; });
    while (cards.length < 2) cards.push({ heading: '…', text: '' });

    var n = cards.length;
    var gap = 18;
    var isGrid = n === 4;
    var cols = isGrid ? 2 : n;
    var rows = isGrid ? 2 : 1;
    var cw = (864 - gap * (cols - 1)) / cols;
    var ch = isGrid ? 170 : 300;
    var top0 = 105;

    cards.forEach(function (c, k) {
      var col = isGrid ? (k % 2) : k;
      var row = isGrid ? Math.floor(k / 2) : 0;
      var x = 48 + col * (cw + gap);
      var y = top0 + row * (ch + gap);
      // Card body
      objects.push(rect({ left: x, top: y, width: cw, height: ch, fill: t.card }));
      // Left accent bar (bot style)
      objects.push(rect({ left: x, top: y, width: 6, height: ch, fill: t.accent, rx: 0, ry: 0 }));
      // Number circle
      objects.push(rect({
        left: x + 22, top: y + 20, width: 34, height: 34, fill: t.primary, rx: 17, ry: 17
      }));
      objects.push(txt({
        text: String(k + 1), left: x + 22, top: y + 24, width: 34, height: 28,
        fontSize: 14, fontWeight: 'bold', fill: '#FFFFFF', textAlign: 'center'
      }));
      if (c.heading) {
        objects.push(txt({
          text: c.heading, left: x + 66, top: y + 22, width: cw - 88, height: 36,
          fontSize: 18, fontWeight: 'bold', fill: t.primary
        }));
      }
      if (c.text) {
        objects.push(txt({
          text: c.text, left: x + 22, top: y + 70, width: cw - 44, height: ch - 90,
          fontSize: 14, fill: t.text, fontFamily: 'Inter'
        }));
      }
    });
    objects = objects.concat(footer(t, meta && meta.deckTitle, meta && meta.idx, meta && meta.total));
    return { objects: objects, background: t.bg };
  }

  function buildStats(data, t, meta) {
    var objects = [topbar(t)];
    var title = clean(data.title || '', 70);
    objects.push(txt({
      text: title, left: 48, top: 32, width: 860, height: 52,
      fontSize: 28, fontWeight: 'bold', fill: t.primary
    }));
    var stats = Array.isArray(data.stats) ? data.stats : [];
    stats = stats.slice(0, 4).map(function (s) {
      if (typeof s === 'string') return { value: s, label: '' };
      return { value: clean(s.value, 16), label: clean(s.label, 60) };
    }).filter(function (s) { return s.value; });
    if (stats.length < 2) {
      while (stats.length < 2) stats.push({ value: '—', label: '' });
    }
    var n = stats.length;
    var gap = 22;
    var cw = (864 - gap * (n - 1)) / n;
    var ch = 280;
    var topY = 120;
    stats.forEach(function (s, k) {
      var x = 48 + k * (cw + gap);
      objects.push(rect({ left: x, top: topY, width: cw, height: ch, fill: t.tint }));
      objects.push(rect({ left: x + 24, top: topY + 28, width: 48, height: 6, fill: t.accent, rx: 3, ry: 3 }));
      objects.push(txt({
        text: s.value, left: x + 20, top: topY + 60, width: cw - 40, height: 80,
        fontSize: n < 4 ? 48 : 36, fontWeight: 'bold', fill: t.primary
      }));
      if (s.label) {
        objects.push(txt({
          text: s.label, left: x + 20, top: topY + 160, width: cw - 40, height: 90,
          fontSize: 16, fill: t.text, fontFamily: 'Inter'
        }));
      }
    });
    objects = objects.concat(footer(t, meta && meta.deckTitle, meta && meta.idx, meta && meta.total));
    return { objects: objects, background: t.bg };
  }

  function buildQuote(data, t, meta) {
    var objects = [];
    objects.push(rect({ left: 0, top: 0, width: 960, height: 540, fill: t.tint, rx: 0, ry: 0 }));
    objects.push(rect({ left: 0, top: 0, width: 14, height: 540, fill: t.primary, rx: 0, ry: 0 }));
    objects.push(txt({
      text: '“', left: 60, top: 40, width: 120, height: 120,
      fontSize: 120, fontWeight: 'bold', fill: t.accent
    }));
    var q = clean(data.text || data.quote || '', 220);
    objects.push(txt({
      text: q, left: 100, top: 180, width: 760, height: 180,
      fontSize: 28, fill: t.text, fontStyle: 'italic', fontFamily: 'Inter'
    }));
    if (data.author) {
      objects.push(txt({
        text: '— ' + clean(data.author, 50), left: 100, top: 400, width: 760, height: 36,
        fontSize: 18, fontWeight: 'bold', fill: t.primary
      }));
    }
    objects = objects.concat(footer(t, meta && meta.deckTitle, meta && meta.idx, meta && meta.total));
    return { objects: objects, background: t.tint };
  }

  function buildTable(data, t, meta) {
    var objects = [topbar(t)];
    var title = clean(data.title || '', 70);
    objects.push(txt({
      text: title, left: 48, top: 28, width: 860, height: 48,
      fontSize: 26, fontWeight: 'bold', fill: t.primary
    }));
    var headers = Array.isArray(data.headers) ? data.headers.map(function (h) { return clean(h, 30); }) : [];
    var rows = Array.isArray(data.rows) ? data.rows : [];
    if (!headers.length && rows.length && Array.isArray(rows[0])) {
      headers = rows[0].map(function (_, i) { return 'Ustun ' + (i + 1); });
    }
    var cols = Math.max(headers.length, 2);
    var maxRows = Math.min(rows.length, 7);
    var gap = 4;
    var tableW = 864;
    var colW = tableW / cols;
    var rowH = 42;
    var startY = 100;
    // Header
    objects.push(rect({
      left: 48, top: startY, width: tableW, height: rowH, fill: t.primary, rx: 8, ry: 8
    }));
    headers.slice(0, cols).forEach(function (h, i) {
      objects.push(txt({
        text: h, left: 48 + i * colW + 10, top: startY + 8, width: colW - 20, height: 28,
        fontSize: 14, fontWeight: 'bold', fill: '#FFFFFF', fontFamily: 'Inter'
      }));
    });
    for (var r = 0; r < maxRows; r++) {
      var y = startY + rowH + gap + r * (rowH + gap);
      var bg = r % 2 === 0 ? t.card : t.tint;
      objects.push(rect({
        left: 48, top: y, width: tableW, height: rowH, fill: bg, rx: 6, ry: 6
      }));
      var row = Array.isArray(rows[r]) ? rows[r] : [String(rows[r] || '')];
      for (var c = 0; c < cols; c++) {
        objects.push(txt({
          text: clean(row[c], 40), left: 48 + c * colW + 10, top: y + 8, width: colW - 20, height: 28,
          fontSize: 13, fill: t.text, fontFamily: 'Inter'
        }));
      }
    }
    objects = objects.concat(footer(t, meta && meta.deckTitle, meta && meta.idx, meta && meta.total));
    return { objects: objects, background: t.bg };
  }

  var BUILDERS = {
    title: buildTitle,
    closing: buildClosing,
    bullets: buildBullets,
    cards: buildCards,
    stats: buildStats,
    quote: buildQuote,
    table: buildTable
  };

  window.ssBuildTemplateSlide = function (layout, data, themeKey, meta) {
    var t = th(themeKey || (data && data.theme) || 'ocean');
    var fn = BUILDERS[String(layout || '').toLowerCase()] || buildBullets;
    return fn(data || {}, t, meta || {});
  };

  /** AI action: bitta slaydni shablon bilan to'ldirish */
  window.ssApplyTemplateSlide = async function (cmd) {
    if (!cmd || typeof slides === 'undefined') return false;
    var layout = String(cmd.layout || cmd.template || 'bullets').toLowerCase();
    var themeKey = cmd.theme || (window.__ssDeckTheme) || 'ocean';
    if (cmd.theme) window.__ssDeckTheme = cmd.theme;
    var idx = ((cmd.slide != null ? cmd.slide : (activeIndex + 1)) || 1) - 1;
    if (idx < 0) idx = 0;
    while (slides.length <= idx) {
      slides.push({ json: JSON.stringify({ objects: [], background: '#ffffff' }), thumb: '', imageNumbers: [] });
    }
    var built = window.ssBuildTemplateSlide(layout, cmd, themeKey, {
      deckTitle: cmd.deckTitle || window.__ssDeckTitle || '',
      idx: idx + 1,
      total: Math.max(slides.length, idx + 1)
    });
    // Optional image on the side (url)
    if (cmd.imageUrl && /^https?:\/\//i.test(cmd.imageUrl) && (layout === 'bullets' || layout === 'title')) {
      try {
        built.objects.push({
          type: 'image', src: cmd.imageUrl,
          left: layout === 'title' ? 640 : 560, top: layout === 'title' ? 160 : 130,
          width: layout === 'title' ? 280 : 340, height: layout === 'title' ? 280 : 300,
          originX: 'left', originY: 'top', selectable: true, evented: true
        });
      } catch (e) {}
    }
    var jsonStr = JSON.stringify(built);
    slides[idx] = {
      json: jsonStr,
      thumb: '',
      imageNumbers: [],
      bgType: 'color',
      bgVal: built.background
    };
    try { if (typeof markSlideAsNew === 'function') markSlideAsNew(slides[idx]); } catch (e) {}
    activeIndex = idx;
    try { renderSidebar(); } catch (e) {}
    try { updateSlideCounterUI(); } catch (e) {}
    try { await loadSlideCanvasAsync(idx); } catch (e) {}
    try { if (typeof refreshSlideThumb === 'function') await refreshSlideThumb(idx); } catch (e) {}
    return true;
  };

  /** AI action: butun deck ni shablonlar bilan yaratish */
  window.ssApplyTemplateDeck = async function (cmd) {
    if (!cmd || !Array.isArray(cmd.slides) || !cmd.slides.length) return false;
    var themeKey = cmd.theme || 'ocean';
    window.__ssDeckTheme = themeKey;
    window.__ssDeckTitle = clean(cmd.title || '', 70);
    var list = cmd.slides.slice(0, 20);
    // Ensure title first / closing last
    if (list[0] && list[0].layout !== 'title') {
      list.unshift({ layout: 'title', title: window.__ssDeckTitle || 'Taqdimot', subtitle: clean(cmd.subtitle || '', 100) });
    }
    if (list.length >= 2 && list[list.length - 1].layout !== 'closing') {
      list.push({ layout: 'closing', title: 'Rahmat!', subtitle: window.__ssDeckTitle || '' });
    }
    try { if (typeof saveCurrentSlideState === 'function') saveCurrentSlideState(); } catch (e) {}
    slides.length = 0;
    for (var i = 0; i < list.length; i++) {
      var s = list[i] || {};
      var lay = String(s.layout || 'bullets').toLowerCase();
      var built = window.ssBuildTemplateSlide(lay, s, themeKey, {
        deckTitle: window.__ssDeckTitle,
        idx: i + 1,
        total: list.length
      });
      var slide = {
        json: JSON.stringify(built),
        thumb: '',
        imageNumbers: [],
        bgType: 'color',
        bgVal: built.background
      };
      try { if (typeof markSlideAsNew === 'function') markSlideAsNew(slide); } catch (e) {}
      slides.push(slide);
    }
    activeIndex = 0;
    try { if (typeof bumpObjectIdCounterFromSlides === 'function') bumpObjectIdCounterFromSlides(); } catch (e) {}
    try { renderSidebar(); } catch (e) {}
    try { updateSlideCounterUI(); } catch (e) {}
    try { await loadSlideCanvasAsync(0); } catch (e) {}
    for (var j = 0; j < slides.length; j++) {
      try { if (typeof refreshSlideThumb === 'function') await refreshSlideThumb(j); } catch (e) {}
    }
    try { if (typeof showToast === 'function') showToast(slides.length + ' ta professional slayd (shablon) yaratildi'); } catch (e) {}
    return true;
  };
})();
