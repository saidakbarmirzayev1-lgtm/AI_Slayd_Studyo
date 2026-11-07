/* =====================================================================
 * 39_v47_pro_ads_admin.js  (v47)
 *
 *  1) SOZLAMALAR: tepada doim ko'rinadigan ⚙️ tugma + ishonchli oyna (bottom-sheet).
 *     Telegram Mini App'da sidebar yopiq paytda ham ishlaydi; ikki marta ochilib qolmaydi.
 *  2) REKLAMA: chap panelda, slaydlar tagida (rasm/video + matn + havola). Server hal qiladi:
 *     Pro / VIP / admin / cheksiz akkauntlarga HECH QACHON ko'rsatilmaydi.
 *  3) PRO: sozlamalarda Pro kartasi va to'lov (Telegram ichida tashqi brauzerda ochiladi).
 *  4) ADMIN: admin akkaunt (Google + ulangan Telegram) bo'lsa — sozlamalarda yashirin tugma.
 *     Boshqalarga hech narsa ko'rinmaydi (server 404 qaytaradi).
 *  5) E'lon: admin paneldan yozilgan e'lon (yopiladigan).
 * ===================================================================== */
(function () {
  'use strict';
  if (window.__ssV47) return;
  window.__ssV47 = true;

  var tgw = null;
  try { tgw = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData ? window.Telegram.WebApp : null; } catch (e) {}

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function token() { try { return (typeof supabaseToken !== 'undefined') ? supabaseToken : ''; } catch (e) { return ''; } }
  function logged() { var t = token(); return !!t && t !== 'dev-token'; }
  function email() { try { return (typeof currentUserEmail !== 'undefined') ? currentUserEmail : ''; } catch (e) { return ''; } }
  function mon() { return window.Monitoring || null; }
  function st() { try { return mon() && mon().getState ? mon().getState() : {}; } catch (e) { return {}; } }
  function toast(m, k) { try { if (typeof showToast === 'function') showToast(m, k || 'info'); } catch (e) {} }
  function openExternal(url) {
    var abs = /^https?:/i.test(url) ? url : location.origin + url;
    try { if (tgw && typeof tgw.openLink === 'function') { tgw.openLink(abs); return; } } catch (e) {}
    var w = null; try { w = window.open(abs, '_blank', 'noopener'); } catch (e) {}
    if (!w) location.href = abs;
  }

  /* ------------------------------------------------------------------ CSS */
  var css = document.createElement('style');
  css.textContent = [
    '#ssTopSet{display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;border:0;border-radius:50%;background:transparent;color:#444746;cursor:pointer;flex:none}',
    '#ssTopSet:hover{background:#e8eaed}#ssTopSet .material-symbols-outlined{font-size:22px}',
    '.ssset-ov{position:fixed;inset:0;z-index:2147483200;background:rgba(15,23,42,.5);display:flex;align-items:flex-end;justify-content:center;animation:ssFade .15s ease}',
    '.ssset{background:#fff;color:#1f2937;width:100%;max-width:460px;max-height:92vh;overflow:auto;border-radius:20px 20px 0 0;padding:18px 18px calc(22px + env(safe-area-inset-bottom,0px));box-shadow:0 -10px 40px rgba(0,0,0,.25);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;animation:ssUp .2s ease}',
    '@media(min-width:560px){.ssset-ov{align-items:center}.ssset{border-radius:20px}}',
    '@keyframes ssUp{from{transform:translateY(24px);opacity:0}to{transform:none;opacity:1}}@keyframes ssFade{from{opacity:0}to{opacity:1}}',
    '.ssset-x{float:right;background:#f1f3f4;border:0;border-radius:50%;width:32px;height:32px;font-size:20px;line-height:1;color:#5f6368;cursor:pointer}',
    '.ssset-head{display:flex;gap:12px;align-items:center;margin-bottom:14px}',
    '.ssset-av{width:46px;height:46px;border-radius:50%;background:linear-gradient(135deg,#4f8cff,#7c5cff);color:#fff;display:grid;place-items:center;font-weight:700;font-size:19px;flex:none}',
    '.ssset-head b{display:block;word-break:break-all}',
    '.ssset-plan{display:inline-block;margin-top:3px;padding:2px 10px;border-radius:99px;font-size:12px;font-weight:700;background:#eef0f3;color:#5f6368}',
    '.ssset-plan.pro{background:#e3edff;color:#1a56db}.ssset-plan.vip{background:#fdf3d0;color:#8a6a00}',
    '.ssset-card{border:1px solid #e5e7eb;border-radius:14px;padding:12px;margin:10px 0}',
    '.ssset-pro{background:linear-gradient(135deg,#f4f7ff,#f7f2ff);border-color:#d9e2ff}',
    '.ssset-pro h4{margin:0 0 6px;font-size:15px}.ssset-pro ul{margin:6px 0 10px;padding-left:18px;color:#4b5563}',
    '.ssset-btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;border:0;border-radius:12px;padding:12px;font:inherit;font-weight:600;cursor:pointer;background:#f1f3f4;color:#1f2937;margin-top:8px}',
    '.ssset-btn.pri{background:#1a73e8;color:#fff}.ssset-btn.gold{background:#f5b301;color:#2b2100}.ssset-btn.adm{background:#111827;color:#fff}',
    '.ssset-btn:disabled{opacity:.6}.ssset small{color:#6b7280}',
    '#ssAdSlot{flex:none;margin:8px;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;background:#fff;font:12px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#1f2937;position:relative}',
    '#ssAdSlot .ad-tag{position:absolute;top:6px;left:6px;z-index:2;background:rgba(0,0,0,.55);color:#fff;border-radius:6px;padding:1px 6px;font-size:10px;letter-spacing:.03em}',
    '#ssAdSlot .ad-media{display:block;width:100%;max-height:112px;object-fit:cover;background:#f1f3f4}',
    '#ssAdSlot .ad-body{padding:9px 10px}#ssAdSlot b{display:block;font-size:13px;margin-bottom:2px}',
    '#ssAdSlot p{margin:0 0 8px;color:#4b5563;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}',
    '#ssAdSlot a.ad-btn{display:block;text-align:center;background:#1a73e8;color:#fff;border-radius:8px;padding:7px;text-decoration:none;font-weight:600}',
    '#ssAdSlot .ad-pro{display:block;width:100%;background:none;border:0;border-top:1px solid #eef0f3;padding:6px;color:#6b7280;font-size:11px;cursor:pointer}',
    '#ssAnn{position:fixed;top:64px;right:12px;z-index:2147482000;max-width:min(360px,calc(100vw - 24px));background:#111827;color:#fff;border-radius:12px;padding:10px 34px 10px 12px;font:13px/1.4 system-ui,sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.3)}',
    '#ssAnn button{position:absolute;top:4px;right:6px;background:none;border:0;color:#9ca3af;font-size:18px;cursor:pointer}'
  ].join('\n');
  document.head.appendChild(css);

  /* ------------------------------------------------------------------ Sozlamalar oynasi */
  var pubCfg = null, adminUrl = null, adminTok = null;
  var oldOpen = (typeof window.openSettingsPanel === 'function') ? window.openSettingsPanel : null;

  fetch('/api/config/public').then(function (r) { return r.ok ? r.json() : null; }).then(function (c) {
    pubCfg = c || {};
    if (pubCfg.announcement) showAnnouncement(pubCfg.announcement);
  }).catch(function () {});

  function showAnnouncement(text) {
    try {
      var key = 'ssAnn:' + text;
      if (sessionStorage.getItem(key) || $('ssAnn')) return;
      var d = document.createElement('div'); d.id = 'ssAnn';
      d.innerHTML = '<span>📢 ' + esc(text) + '</span><button type="button" aria-label="Yopish">×</button>';
      d.querySelector('button').onclick = function () { try { sessionStorage.setItem(key, '1'); } catch (e) {} d.remove(); };
      document.body.appendChild(d);
    } catch (e) {}
  }

  function planLabel(s) {
    if (s.plan === 'vip') return ['VIP · cheksiz', 'vip'];
    if (s.unlimited) return ['Cheksiz', 'vip'];
    if (s.plan === 'pro') {
      var u = '';
      try { if (s.plan_until) u = ' · ' + new Date(s.plan_until).toLocaleDateString('uz') + ' gacha'; } catch (e) {}
      return ['Pro' + u, 'pro'];
    }
    return ['Bepul', ''];
  }

  function closeSettings() { var o = $('ssSet'); if (o) o.remove(); document.removeEventListener('keydown', onKey); }
  function onKey(e) { if (e.key === 'Escape') closeSettings(); }

  function openSettingsV47() {
    if ($('ssSet')) return;                       // ikki marta bosilsa (touch + click) — bitta oyna
    var s = st(), li = logged();
    var pl = planLabel(s);
    var ov = document.createElement('div'); ov.id = 'ssSet'; ov.className = 'ssset-ov';
    var proCfg = pubCfg || {};
    var proPrice = Number(s.pro_price || proCfg.pro_price_usd || 0), proDays = s.pro_days || proCfg.pro_days || 30;
    var html = '<div class="ssset" role="dialog" aria-label="Sozlamalar"><button type="button" class="ssset-x" aria-label="Yopish">×</button>';
    if (li) {
      var em = email() || 'Akkaunt';
      html += '<div class="ssset-head"><div class="ssset-av">' + esc((em[0] || 'S').toUpperCase()) + '</div><div><b>' + esc(em) + '</b><span class="ssset-plan ' + pl[1] + '">' + esc(pl[0]) + '</span></div></div>';
      html += '<div class="ssset-card" id="ssSetMeters">' + (window.ssMetersHTML ? window.ssMetersHTML() : '') + '</div>';
      if (!s.unlimited && s.plan !== 'pro') {
        html += '<div class="ssset-card ssset-pro"><h4>👑 Slide Studio Pro</h4><ul><li>Reklamasiz — sayt va botda</li><li>Kuniga ko\'proq bepul varaq</li><li>Bitta akkaunt: sayt + Telegram</li></ul>' +
          (proCfg.pro_enabled === false ? '<small>Pro to\'lovi tez orada ishga tushadi.</small>' :
            '<button type="button" class="ssset-btn gold" id="ssBuyPro">👑 Pro olish' + (proPrice ? ' — $' + proPrice.toFixed(2) + ' / ' + proDays + ' kun' : '') + '</button>') + '</div>';
      } else if (s.plan === 'pro') {
        html += '<div class="ssset-card ssset-pro"><h4>👑 Pro faol</h4><small>Reklama o\'chirilgan. Muddatni uzaytirish mumkin.</small>' +
          (proCfg.pro_enabled === false ? '' : '<button type="button" class="ssset-btn" id="ssBuyPro">Muddatni uzaytirish</button>') + '</div>';
      }
      if (!s.unlimited) html += '<button type="button" class="ssset-btn pri" id="ssBuyPack">➕ Varaq sotib olish</button>';
      if (window.ssTgLink && !tgw) html += '<button type="button" class="ssset-btn" id="ssTg">✈️ Telegram botni ulash</button>';
      html += '<button type="button" class="ssset-btn" id="ssTools">🛠 Asboblar va tozalash</button>';
      html += '<button type="button" class="ssset-btn adm" id="ssAdmin" style="display:none">🛡 Admin panel</button>';
      if (!tgw) html += '<button type="button" class="ssset-btn" id="ssOut">Chiqish</button>';
    } else {
      html += '<div class="ssset-head"><div class="ssset-av">S</div><div><b>Mehmon</b><span class="ssset-plan">Kirmagansiz</span></div></div>' +
        '<small>Kirsangiz AI, balans va loyihalarni saqlash ishlaydi.</small>' +
        (tgw ? '' : '<button type="button" class="ssset-btn pri" id="ssIn">Google bilan kirish</button>') +
        '<button type="button" class="ssset-btn" id="ssTools">🛠 Asboblar</button>';
    }
    html += '</div>';
    ov.innerHTML = html;
    document.body.appendChild(ov);
    document.addEventListener('keydown', onKey);
    ov.addEventListener('click', function (e) { if (e.target === ov) closeSettings(); });
    function on(id, fn) { var b = ov.querySelector('#' + id); if (b) b.onclick = function (e) { e.preventDefault(); fn(b); }; }
    ov.querySelector('.ssset-x').onclick = closeSettings;
    on('ssBuyPro', function () { closeSettings(); if (mon()) mon().startCheckout('pro'); });
    on('ssBuyPack', function () { closeSettings(); if (mon()) mon().startCheckout('pack'); });
    on('ssTg', function () { closeSettings(); try { window.ssTgLink(); } catch (e) {} });
    on('ssIn', function () { closeSettings(); try { handleGoogleLogin(); } catch (e) {} });
    on('ssOut', function () { closeSettings(); try { handleLogout(); } catch (e) {} });
    on('ssTools', function () {
      closeSettings();
      try { if (typeof toggleSidebarMenu === 'function' && window.innerWidth <= 900) { var sb = $('sidebar'); if (sb && !sb.classList.contains('open')) toggleSidebarMenu(); } } catch (e) {}
      try { if (oldOpen) oldOpen(); } catch (e) { toast('Asboblar oynasini ochib bo\u2018lmadi', 'error'); console.warn('[v47] oldOpen', e); }
    });
    on('ssAdmin', function () { closeSettings(); if (adminUrl) openExternal(adminUrl); });
    try { if (window.ssAnimateMeters) window.ssAnimateMeters(ov); } catch (e) {}
    if (li) checkAdmin(ov);
  }

  /* admin tugmasi: server tasdiqlasagina (Google admin + ulangan Telegram admin) ko'rinadi; aks holda 404 — hech narsa sezilmaydi */
  async function checkAdmin(ov) {
    try {
      var t = token();
      if (adminTok !== t) {
        adminTok = t; adminUrl = null;
        var r = await fetch('/api/me/admin-entry', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: t }) });
        if (r.ok) { var j = await r.json(); adminUrl = j && j.url ? j.url : null; }
      }
      var b = ov.querySelector('#ssAdmin');
      if (b && adminUrl) b.style.display = 'flex';
    } catch (e) {}
  }

  window.openSettingsPanel = openSettingsV47;
  window.openSettingsV47 = openSettingsV47;

  /* yuqori ⚙️ tugma (hamma ekranda, sidebar yopiq bo'lsa ham) */
  function ensureTopButton() {
    if ($('ssTopSet')) return;
    var host = document.querySelector('.header-actions');
    if (!host) return;
    var b = document.createElement('button');
    b.type = 'button'; b.id = 'ssTopSet'; b.title = 'Sozlamalar'; b.setAttribute('aria-label', 'Sozlamalar');
    b.innerHTML = '<span class="material-symbols-outlined">settings</span>';
    host.appendChild(b);
  }

  /* hamma "sozlamalar" tugmalari bitta ishonchli ishlovchi orqali (sidebar qayta chizilsa ham ishlaydi) */
  document.addEventListener('click', function (e) {
    var t = e.target && e.target.closest ? e.target.closest('#ssTopSet,.btn-settings,#sidebarSettingsBtn,[data-ss-open="settings"]') : null;
    if (!t) return;
    e.preventDefault(); e.stopPropagation(); if (e.stopImmediatePropagation) e.stopImmediatePropagation();
    openSettingsV47();
  }, true);


  /* ------------------------------------------------------------------ Tugmalar ishonchliligi */
  // (a) Fayl tanlash (fon rasmi, rasm, video...): DOM'ga ulanmagan <input type=file> Telegram/iOS WebView'da
  //     tanlangan faylni bildirmaydi ("tugma bosiladi, hech narsa bo'lmaydi"). Vaqtincha DOM'ga ulaymiz.
  try {
    var _origInputClick = HTMLInputElement.prototype.click;
    HTMLInputElement.prototype.click = function () {
      var el = this;
      try {
        if (el.type === 'file' && !el.isConnected && document.body) {
          el.style.cssText = 'position:fixed;left:-9999px;top:0;width:1px;height:1px;opacity:0';
          document.body.appendChild(el);
          var done = function () { setTimeout(function () { try { if (el.parentNode) el.remove(); } catch (e) {} }, 1500); };
          el.addEventListener('change', done, { once: true });
          el.addEventListener('cancel', done, { once: true });
          setTimeout(function () { try { if (el.parentNode) el.remove(); } catch (e) {} }, 180000);
        }
      } catch (e) {}
      return _origInputClick.apply(el, arguments);
    };
  } catch (e) {}

  // (b) Allaqachon tanlangan slaydga qayta bosish: qayta chizish/miltillash bo'lmasin
  try {
    var _origSwitch = window.switchSlide;
    if (typeof _origSwitch === 'function' && !_origSwitch.__v47) {
      var wrapped = function (index) {
        try { if (typeof activeIndex !== 'undefined' && Number(index) === activeIndex) return; } catch (e) {}
        return _origSwitch.apply(this, arguments);
      };
      wrapped.__v47 = true;
      window.switchSlide = wrapped;
    }
  } catch (e) {}

  /* ------------------------------------------------------------------ Reklama (chap panel) */
  var curAd = null, lastKey = null, lastFree = null;

  function renderAdInto(el, ad) {
    var media = '';
    if (ad.media_url && ad.media_type === 'image') media = '<img class="ad-media" src="' + esc(ad.media_url) + '" alt="" loading="lazy" referrerpolicy="no-referrer">';
    else if (ad.media_url && ad.media_type === 'video') media = '<video class="ad-media" src="' + esc(ad.media_url) + '" autoplay muted loop playsinline preload="metadata"></video>';
    el.dataset.ad = ad.id;
    el.innerHTML = '<span class="ad-tag">Reklama</span>' + media + '<div class="ad-body">' +
      (ad.title ? '<b>' + esc(ad.title) + '</b>' : '') + (ad.body ? '<p>' + esc(ad.body) + '</p>' : '') +
      (ad.has_link ? '<a class="ad-btn" target="_blank" rel="noopener sponsored" href="' + esc(ad.click_url) + '">' + esc(ad.button_text || 'Batafsil') + '</a>' : '') +
      '</div><button type="button" class="ad-pro">👑 Reklamasiz ishlash — Pro</button>';
    var a = el.querySelector('a.ad-btn');
    if (a && tgw) a.addEventListener('click', function (e) { e.preventDefault(); openExternal(ad.click_url); });
    el.querySelector('.ad-pro').addEventListener('click', function (e) { e.preventDefault(); openSettingsV47(); });
  }

  function ensureSlot() {
    var sb = $('sidebar'); if (!sb) return;
    var el = $('ssAdSlot');
    if (!curAd) { if (el) el.remove(); return; }
    if (!el) { el = document.createElement('div'); el.id = 'ssAdSlot'; }
    if (el.dataset.ad !== String(curAd.id)) renderAdInto(el, curAd);
    var user = sb.querySelector('.sidebar-user-section');
    var wrongSpot = el.parentNode !== sb || (user ? el.nextElementSibling !== user : sb.lastElementChild !== el);
    if (wrongSpot) { if (user) sb.insertBefore(el, user); else sb.appendChild(el); }
  }

  async function fetchAd() {
    var s = st();
    if (logged() && s.ad_free) { curAd = null; ensureSlot(); return; }
    try {
      var h = {}; if (logged()) h.Authorization = 'Bearer ' + token();
      var r = await fetch('/api/ads/next?surface=site' + (curAd ? '&exclude=' + curAd.id : ''), { headers: h, cache: 'no-store' });
      var j = r.ok ? await r.json() : { ad: null };
      curAd = j && j.ad ? j.ad : null;
    } catch (e) { return; }
    ensureSlot();
  }

  var rafPending = false;
  function watchSidebar() {
    var sb = $('sidebar');
    if (!sb || sb.__ssAdObs) return;
    sb.__ssAdObs = true;
    new MutationObserver(function () {
      if (rafPending) return; rafPending = true;
      requestAnimationFrame(function () { rafPending = false; ensureSlot(); });
    }).observe(sb, { childList: true });
  }

  document.addEventListener('ss:usage', function (e) {
    var free = !!(e.detail && e.detail.ad_free);
    if (lastFree === null || free !== lastFree) { lastFree = free; fetchAd(); }
  });

  function boot() {
    ensureTopButton(); watchSidebar();
    setTimeout(fetchAd, 1500);
    var prev = logged() ? token() : '';
    setInterval(function () {                                    // kirish/chiqish o'zgarsa — reklama va holat yangilanadi
      ensureTopButton(); watchSidebar();
      var now = logged() ? token() : '';
      if (now !== prev) {
        var wasLogged = !!prev; prev = now;
        if (wasLogged && !now) { try { if (mon()) mon().applyServerUsage({ plan: 'free', is_pro: false, unlimited: false, ad_free: false }); } catch (e) {} }
        adminTok = null; adminUrl = null;
        fetchAd();
      }
    }, 2500);
    setInterval(fetchAd, 8 * 60 * 1000);                         // 8 daqiqada bir yangi reklama
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
