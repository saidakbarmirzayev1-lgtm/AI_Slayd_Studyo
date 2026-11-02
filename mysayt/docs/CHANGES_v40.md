# Slide Studio v40 — eksport va namoyish

## PPTX (PowerPoint / Google Slides / WPS)  — `js/14_pptx_io.js`
- **Animatsiyalar** (`animName`, `animDur`, `animDelay`, `animLoop`) PPTX ga o'tkazilmaydi (`ssStripAnimations`).
- **Havolalar**: matn, rasm, GIF va shakllardagi `linkUrl` PowerPoint `hyperlink: { url }` sifatida yoziladi.
- **Tugmalar**: bosiladigan shakl (roundRect). `url` amali — brauzer ochiladi; `next / prev / first / last / goto` — PowerPoint ichida slaydga o'tish (`hlinksldjump`). Havola faqat shakl darajasida, shuning uchun matn tagiga chizilmaydi va rangi o'zgarmaydi. Burchak yumaloqligi to'g'ri (oldin dyuym o'rniga ulush berilgan edi).
- **MP4**: `addMedia({type:'video', data, cover})` — video faylning o'zi PPTX ichida (oflayn ishlaydi); birinchi kadr muqova qilib olinadi. `.mov` ham qabul qilinadi. WebM/OGG PowerPoint'da ishlamaydi — muqova rasm + izoh qo'yiladi va ogohlantirish chiqadi.
- **YouTube / Vimeo / Dailymotion**: muqova (thumbnail) + Play (▶) tugmasi bitta rasm sifatida, ustiga to'g'ridan-to'g'ri havola ulanadi. Internet bo'lmasa — hech qanday xato yo'q. Muqova yuklanmasa gradient fon ishlatiladi.
- **Fon video**: lokal MP4 — to'liq ekran video; onlayn — muqova + Play + havola.
- Ichiga joylangan `slide-studio/project.json` saqlanadi (qayta ochib tahrirlash uchun).

## PDF — `js/29_v40_html_export.js` (5-bo'lim)
- Sahifalar statik chiziladi (animatsiyasiz). Matn qatlami saqlanadi.
- Matn, URL-tugma, rasm va YouTube/Vimeo ustiga **bosiladigan havola** (Link annotation) qo'yiladi.

## HTML namoyish — `js/29_v40_html_export.js` (eski `exportHTML` almashtirildi)
- Matn **haqiqiy matn**: sichqoncha bilan belgilanadi va nusxalanadi (`user-select:text`). Havolali matn bosiladi.
- Matn joylashuvi muharrir (fabric.js) bilan bir xil: qator balandligi `lineHeight × 1.13`, birinchi qator baseline'i shrift o'lchamidan hisoblanadi; belgi-darajadagi uslublar, gradient, soya, kontur, `charSpacing` qo'llab-quvvatlanadi.
- Aylantirilgan va ag'darilgan obyektlar fabric'dagidek (burilish nuqtasi `originX/originY`).
- Shakllar SVG (kontur markazda, gradient, yumaloq burchak), rasm kesish (`cropX/cropY`) va yumaloq maska.
- Animatsiyalar muharrirdagi bilan bir xil (`ssAnimStyle` keyframes, davomiylik, kechikish, takrorlanish); burilgan obyektlarda ham ishlaydi. Slayd o'tish effekti (`presSlideNext/Prev`) ham bir xil.
- Tugmalar (keyingi/oldingi/birinchi/oxirgi/slaydga o'tish/havola/xabar oynasi) ishlaydi.
- MP4 va rasm/GIF fayl ichida (blob'ga aylantiriladi — tez va xotirani tejaydi). **Shriftlar ham fayl ichiga joylanadi** (latin, latin-ext, kirill) — oflayn ham bir xil ko'rinadi. Joylab bo'lmasa — onlayn `<link>` zaxirasi.
- Faylda loyiha ma'lumoti **bir nusxada** (`#project-data`) — oldingiga nisbatan fayl ~2 barobar kichik; qayta tahrirlash uchun ochish ishlaydi.
- Navigatsiya: ← → ↑ ↓ PageUp/PageDown Space Enter Home End, ekrandagi tugmalar, telefonda surish; **F** yoki ⛶ — Fullscreen (Safari uchun webkit zaxirasi bilan); `#3` kabi havola to'g'ridan-to'g'ri 3-slaydni ochadi.
- YouTube/Vimeo faqat internet bilan ishlaydi (oflayn — qorong'u Play maydoni ko'rinadi).
- Qo'llab-quvvatlanmaydigan obyekt turlari (path, polygon, line, guruh) rasm (sprite) sifatida joylanadi.

## Tekshirish ro'yxati
1. Eksport → HTML → faylni internetni o'chirib oching: matnni belgilab nusxalang, o'qlar, F, tugmalar, MP4.
2. Eksport → PPTX → PowerPoint: havola va tugmani Slide Show rejimida bosing; MP4 ijro etilishi; YouTube muqovasi bosilganda brauzer ochilishi.
3. PPTX → Google Slides'ga yuklang: matn va rasm joyida, YouTube muqovasi havola bilan.
4. Eksport → PDF → havolani bosing.
