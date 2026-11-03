/* =====================================================================
 * 35_v45_tglink.js  (v45) — Telegram bot bilan BIR XIL balans
 *  1) Balans panelida «✈️ Telegram» tugmasi: bir martalik kod beradi, botda /link KOD bilan akkaunt ulanadi.
 *  2) Botda varaq sarflansa / to'lov qilinsa — sayt balansi avtomatik yangilanadi
 *     (oynaga qaytganda va ochiq turganda har 30 soniyada; yengil so'rov).
 * Telegram Mini App ichida ishlamaydi (u allaqachon bot akkaunti bilan kirgan).
 * ===================================================================== */
(function () {
  'use strict';
  if (window.__ssTgLinkInit) return;
  window.__ssTgLinkInit = true;
  var tgw = window.Telegram && window.Telegram.WebApp;
  if (tgw && tgw.initData) return;

  function token() { try { return (typeof supabaseToken !== 'undefined') ? supabaseToken : ''; } catch (e) { return ''; } }
  function logged() { var t = token(); return !!t && t !== 'dev-token'; }
  function toast(m, k) { try { if (typeof showToast === 'function') showToast(m, k || 'info'); } catch (e) {} }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  async function post(url) {
    var r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: token() }) });
    var j = {}; try { j = await r.json(); } catch (e) {}
    return { ok: r.ok, status: r.status, data: j };
  }

  var busy = false;
  async function openLink() {
    if (busy) return;
    if (!logged()) { toast('Avval Google bilan tizimga kiring.', 'error'); return; }
    busy = true;
    try {
      var st = await post('/api/telegram/link-status');
      if (st.ok && st.data && st.data.linked) { toast('✅ Telegram allaqachon ulangan. Balans bot bilan bir xil.', 'info'); return; }
      var r = await post('/api/telegram/link-code');
      if (!r.ok || !r.data.code) {
        var m = r.data && r.data.error === 'db_not_ready' ? 'Server sozlanmagan (SUPABASE_TELEGRAM.sql).' : (r.data && r.data.error === 'telegram_disabled' ? 'Telegram bot o‘chiq.' : 'Kod olib bo‘lmadi.');
        toast(m, 'error'); return;
      }
      var code = r.data.code, url = r.data.url || '';
      var html = '<div style="text-align:left;line-height:1.5">1) Pastdagi tugma orqali botni oching (yoki botga yozing: <b>/link ' + esc(code) + '</b>)<br>2) Ulanganingizdan so‘ng balans saytda va botda <b>bir xil</b> bo‘ladi.' +
        '<div style="font:700 28px/1.2 monospace;letter-spacing:4px;text-align:center;margin:14px 0;user-select:all">' + esc(code) + '</div>' +
        '<div style="opacity:.7;font-size:12px;text-align:center">Kod 10 daqiqa amal qiladi</div></div>';
      if (typeof Swal !== 'undefined' && Swal.fire) {
        var res = await Swal.fire({ title: '✈️ Telegram botni ulash', html: html, showCancelButton: true, confirmButtonText: url ? 'Telegramda ochish' : 'Yopish', cancelButtonText: 'Yopish' });
        if (res && res.isConfirmed && url) window.open(url, '_blank');
      } else if (url) { window.open(url, '_blank'); }
      else { alert('Botga yozing: /link ' + code); }
    } catch (e) { toast('Ulab bo‘lmadi. Keyinroq urinib ko‘ring.', 'error'); }
    finally { busy = false; }
  }

  function addBtn() {
    if (document.hidden || document.getElementById('btnTgLink')) return;
    var buy = document.getElementById('btnBuyCredits');
    if (!buy || !buy.parentNode) return;
    var b = document.createElement('button');
    b.type = 'button'; b.id = 'btnTgLink'; b.className = buy.className; b.textContent = '✈️ Telegram';
    b.title = 'Telegram bot bilan balansni birlashtirish';
    b.style.marginLeft = '6px';
    b.addEventListener('click', openLink);
    buy.parentNode.insertBefore(b, buy.nextSibling);
  }
  setInterval(addBtn, 3000);
  setTimeout(addBtn, 800);

  /* Balansni bot bilan sinxron saqlash */
  var last = 0;
  function sync() {
    if (document.hidden || !logged()) return;
    var now = Date.now();
    if (now - last < 15000) return;
    last = now;
    try { if (typeof loadUserStats === 'function') loadUserStats(); } catch (e) {}
  }
  document.addEventListener('visibilitychange', sync);
  window.addEventListener('focus', sync);
  setInterval(sync, 30000);
})();
