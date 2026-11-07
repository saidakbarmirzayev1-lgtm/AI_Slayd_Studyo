// jsdom sinovi:  cd tests && npm i jsdom && node frontend_v47.test.js
const { JSDOM } = require(process.env.JSDOM_PATH || 'jsdom');
const fs = require('fs'), path = require('path'), assert = require('assert');
const root = path.join(__dirname, '..');
const read = f => fs.readFileSync(path.join(root, f), 'utf8');

function boot({ token = 'dev-token', ad = null, usage = null }) {
  const dom = new JSDOM(`<body><div class="header-actions"></div><div id="sidebar"><div class="sidebar-slides-scroll"></div><div class="sidebar-user-section"><button class="btn-settings">g</button></div></div></body>`,
    { runScripts: 'outside-only', url: 'https://x.test/', pretendToBeVisual: true });
  const w = dom.window;
  const calls = [];
  w.supabaseToken = token; w.currentUserEmail = 'a@b.c';
  w.showToast = () => {};
  w.matchMedia = () => ({ matches: false, addListener() {}, addEventListener() {} });
  w.fetch = async (url, opt) => {
    calls.push([url, opt]);
    const J = o => ({ ok: true, status: 200, json: async () => o });
    if (url.startsWith('/api/ads/next')) return J({ ad });
    if (url.startsWith('/api/config/public')) return J({ pro_enabled: true, pro_price_usd: 5, pro_days: 30, announcement: 'Yangilik!' });
    if (url.startsWith('/api/me/admin-entry')) return { ok: false, status: 404, json: async () => ({}) };
    return J({});
  };
  // 11_monitoring.js ni haqiqiy holda yuklaymiz
  w.eval(read('js/11_monitoring.js'));
  if (usage) w.Monitoring.applyServerUsage(usage);
  w.eval(read('js/39_v47_pro_ads_admin.js'));
  return { w, calls };
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
const AD = { id: 7, title: 'Kurs <b>x</b>', body: 'Matn', media_type: 'image', media_url: '/api/ads/media/7', button_text: 'Batafsil', has_link: true, click_url: '/api/ads/click/7?s=site' };

(async () => {
  // 1) mehmon: reklama chap panelda, foydalanuvchi bo'limidan oldin; HTML escape qilingan
  let { w, calls } = boot({ ad: AD });
  await sleep(1800);
  const slot = w.document.getElementById('ssAdSlot');
  assert(slot, 'reklama bloki chiqmadi');
  assert.strictEqual(slot.nextElementSibling.className, 'sidebar-user-section', 'reklama foydalanuvchi bo\'limi tepasida emas');
  assert(slot.innerHTML.includes('&lt;b&gt;x'), 'sarlavha escape qilinmagan');
  assert(slot.querySelector('a.ad-btn').getAttribute('href') === '/api/ads/click/7?s=site');
  assert(w.document.getElementById('ssAnn'), 'e\'lon chiqmadi');
  // sidebar qayta chizilsa ham reklama qaytadi
  w.document.getElementById('sidebar').innerHTML = '<div class="sidebar-slides-scroll"></div><div class="sidebar-user-section"><button class="btn-settings">g</button></div>';
  await sleep(100);
  assert(w.document.getElementById('ssAdSlot'), 'sidebar qayta chizilgach reklama yo\'qoldi');

  // 2) ⚙️ tugmalar: yuqoridagi va sidebar'dagi — ikkalasi ham oyna ochadi, ikki marta emas
  assert(w.document.getElementById('ssTopSet'), 'yuqori sozlamalar tugmasi yo\'q');
  w.document.getElementById('ssTopSet').click();
  assert.strictEqual(w.document.querySelectorAll('#ssSet').length, 1);
  w.document.getElementById('ssTopSet').click();
  assert.strictEqual(w.document.querySelectorAll('#ssSet').length, 1, 'ikkinchi bosishda yana ochildi');
  assert(w.document.body.textContent.includes('Mehmon'));
  w.document.querySelector('.ssset-x').click();
  assert(!w.document.getElementById('ssSet'));
  w.document.querySelector('.btn-settings').click();
  assert(w.document.getElementById('ssSet'), 'sidebar tugmasi oyna ochmadi');
  w.document.querySelector('.ssset-x').click();

  // 3) Pro foydalanuvchi: server null qaytaradi -> blok yo'q; modal Pro holatini ko'rsatadi
  ({ w, calls } = boot({ token: 'tok', ad: null, usage: { plan: 'pro', is_pro: true, ad_free: true, plan_until: '2030-01-01T00:00:00Z', free_credits: 100, paid_credits: 0 } }));
  await sleep(1800);
  assert(!w.document.getElementById('ssAdSlot'));
  const adCall = calls.find(c => c[0].startsWith('/api/ads/next'));
  assert(!adCall || adCall[1].headers.Authorization === 'Bearer tok');
  w.openSettingsPanel();
  const txt = w.document.getElementById('ssSet').textContent;
  assert(txt.includes('Pro faol') && txt.includes('Pro'), 'Pro holati ko\'rinmadi');
  assert(!txt.includes('Pro olish'), 'Pro foydalanuvchiga "Pro olish" ko\'rinyapti');
  assert.strictEqual(w.document.getElementById('creditBadge').textContent, 'PRO');
  assert.strictEqual(w.document.getElementById('ssAdmin').style.display, 'none', 'admin tugmasi oddiy foydalanuvchiga ochilib qoldi');

  // 4) cheksiz/VIP: ∞, guardSend hech qachon to'smaydi
  ({ w } = boot({ token: 'tok', usage: { plan: 'vip', is_pro: true, unlimited: true, ad_free: true, free_credits: 0, paid_credits: 0, next_reset_in_seconds: 5000 } }));
  await sleep(200);
  assert.strictEqual(w.document.querySelector('#ssQuota .q-n').textContent, '∞');
  assert.strictEqual(w.document.getElementById('creditBadge').textContent, 'VIP');
  assert.strictEqual(w.Monitoring.guardSend(), true);
  // oddiy foydalanuvchi limiti tugasa to'silishda davom etadi
  ({ w } = boot({ token: 'tok', usage: { plan: 'free', free_credits: 0, paid_credits: 0, next_reset_in_seconds: 5000, window_started: true } }));
  w.showLimitModalCalled = false;
  assert.strictEqual(w.Monitoring.guardSend(), false);

  // 5) admin tugmasi: server 200 qaytarsa ko'rinadi
  ({ w } = boot({ token: 'tok' }));
  w.fetch = async (u) => u.startsWith('/api/me/admin-entry') ? { ok: true, status: 200, json: async () => ({ url: '/_a/abc.def' }) } : { ok: true, status: 200, json: async () => ({}) };
  w.openSettingsPanel();
  await sleep(100);
  assert.strictEqual(w.document.getElementById('ssAdmin').style.display, 'flex');
  console.log('frontend: HAMMASI O\'TDI');
  process.exit(0);
})().catch(e => { console.error('FRONTEND XATO:', e.message); process.exit(1); });
