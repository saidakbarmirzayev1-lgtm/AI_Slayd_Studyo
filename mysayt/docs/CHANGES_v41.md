# Slide Studio v41 — v40 ustiga tuzatishlar

## 1. Namoyish (Presentation Mode) — `js/30_v40_present_persist.js`
- Namoyish endi eksport qilinadigan HTML bilan **bir xil ko'rsatgich** (iframe) orqali ishlaydi: orqa fon **GIF ko'rinadi**, orqa fon **video boshidan jonli** (statik rasm bo'lib qolmaydi; YouTube iframe yuklanishi bilan ochiladi), obyekt animatsiyalari, tugmalar, havolalar ishlaydi.
- **Oldindan yuklash**: Namoyish bosilganda barcha rasm, GIF, MP4, YouTube muqovasi va shriftlar yuklanib bo'lguncha "Taqdimot tayyorlanmoqda" oynasi (foiz bilan) chiqadi, keyin namoyish boshlanadi. "Kutmasdan boshlash" tugmasi bor.
- **Keshda saqlash**: tayyor ko'rsatgich xotirada turadi. Slaydlar o'zgarmasa, qayta ochish darhol. Namoyish tugmasi ustiga kelganda fonda oldindan tayyorlanadi. Slayd o'zgarsa — avtomatik qayta tayyorlanadi.
- Namoyish yopilganda GIF/video to'xtatiladi (CPU tejaladi), media keshda qoladi.

## 2. Brauzerni yopib ochganda saqlanish
- Loyiha (slaydlar, sarlavha, faol slayd) **IndexedDB** ga har 3.5 s da (o'zgargan bo'lsa), yashiringanda va yopilganda saqlanadi. `blob:` rasm/videolar `data:` ga aylantirib saqlanadi.
- Sayt ochilganda oxirgi loyiha avtomatik tiklanadi (`03_auth_project.js` → `initProjectFromUrl`). Ishga tushgandan 8 soniya saqlash o'chiq (tiklash tugashi uchun). Tozalash: konsolda `ssClearSavedProject()`.
- v38 qulfi (localStorage'ga yozilmaydi) saqlanadi — faqat IndexedDB ishlatiladi.

## 3. Chap panel
- Orqa fonda GIF/video bo'lgan slayd miniatyurasi **harakatsiz rasm** (GIF birinchi kadri / video plakati); asosiy kanvasda harakatlanadi.
- Slayd almashtirganda sahifa sakrashi tuzatildi (`scrollIntoView` o'rniga faqat panelning o'z skrolli ishlatiladi).

## 4. PPTX
- Galereyadan (onlayn) video: fayl yuklab olinib, PPTX ichiga **haqiqiy MP4** sifatida joylanadi (YouTube kabi havola bo'lib qolmaydi). WebM/OGG PowerPoint'da ishlamaydi.
- **GIF → MP4**: brauzer MP4 yozishni qo'llab-quvvatlasa (Chrome 126+, Safari), GIF video sifatida joylanadi (≈8 soniya takrorlanadi); qo'llab-quvvatlanmasa GIF rasm bo'lib qoladi.
- Animatsiya bo'lsa, yuklangandan keyin qisqa eslatma: PowerPoint'da animatsiyalar ishlamasligi yoki cheklanishi mumkin.

## 5. PDF
- Ogohlantirish **bitta** oyna: "Slaydda animatsiya, video yoki tugma/link bo'lsa, PDF formatida ular ishlamay qolishi mumkin."

## 6. Interfeys
- Takrorlanuvchi tugmalar olib tashlandi: panel va Fayl menyusidagi "Chop etish", Ko'rinish menyusidagi "Namoyish" va "AI paneli", sarlavhadagi "Fikr"/"+15" (menyuda bor).
- **Balans** oynasi (`#ssQuotaPop`) endi har doim eng ustki qatlamda (`z-index: 2147483000`), `v40.css`.
