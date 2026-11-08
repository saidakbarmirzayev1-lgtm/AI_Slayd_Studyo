# v48 — Telegram bot: Pro yo'q, faqat varaqlar; Google majburiy; bot ichida admin

- **Pro/obuna botdan olib tashlandi.** Faqat varaq (kredit) tizimi: bepul kunlik varaq + sotib olingan varaqlar. «Pro» tugmasi/buyrug'i yo'q (eski tugmalar balansga olib boradi).
- **Google majburiy.** Ulanmagan foydalanuvchi slayd yarata/tahrirlay olmaydi — bot «Google ulash» tugmasini ko'rsatadi. Admin bundan istisno.
- **Admin** (faqat `ADMIN_TG_IDS (yoki ADMIN_TELEGRAM_IDS)` dagi Telegram ID): `admin` yoki `/admin`.
  Boshqa odamga: «Bunday buyruq mavjud emas.»
  `/give ID 50` · `/take ID 20` · `/unlimited ID [off]` · `/fill ID` · `/reset ID` · `/block ID` · `/unblock ID` · `/user ID`
  ID = Telegram ID, email yoki UUID. Hammasi Supabase'da saqlanadi (server o'chib yonsa ham yo'qolmaydi), `admin_audit` jurnaliga yoziladi, foydalanuvchiga botda xabar boradi.
- **Sodda matnlar:** /start, yordam, balans, «varaq tugadi» qisqartirildi; reklama faqat sarlavha + matn (Pro eslatmasiz).
- Fayllar: `backend/telegram_bot.py`, `backend/admin_core.py` (`resolve_target`, `user_brief`), `tests/test_v47.py`.
- Sayt (brauzer) tomonidagi Pro/admin panel o'zgarmadi.
- Rang/tahrirdan keyin qayta yuklashda slayd rasmi almashib ketmaydi (tg_decks.find_image tanlangan rasm manzilini eslab qoladi).
- **To'lov:** webhook manzili `/api/payment/lemon-webhook` (muqobil: `/webhook/lemonsqueezy` ham qabul qilinadi). Lemon kalitlaridagi `\n`/bo'shliq/tirnoq/«Bearer » avtomatik tozalanadi.
- Chuqur AI: rasm so'rovlari yozilmasa, bot o'zi to'ldiradi (titul + ~40% bullets slaydlar); «rasmsiz» deyilmasa rasm qo'yiladi.
- **Limitlar:** bepul kunlik 10 varaq, paket 100 varaq. Chuqur varaq = 2 Tez varaq (100 Tez = 50 Chuqur, bepul 10 = 5 Chuqur).
- **Bepul limit qoidasi:** pullik balans 10 varaqdan KO'P yoki teng bo'lsa — kunlik bepul limit to'xtaydi (yangi bepul varaq berilmaydi). Pullik balans 10 dan pastga tushganda bepul limit darhol qaytadi. Yangi paket mavjud balansga to'liq qo'shiladi. (`backend/monitoring.py`: `free_suspended`, `apply_24h_reset`, `charge_for_ai_turn`)
- Sayt, Chuqur AI: deepseek-reasoner tool chaqira olmasligi sabab rasm qidirilmasdi — endi server rasmlarni oldindan topib, tayyor URL ro'yxatini beradi (main.py: _deep_presearch).
- Sayt, Chuqur AI: tool matni (DSML) chiqib javob to'xtab qolishi tuzatildi: reasoner uchun tool eslatmalari olib tashlandi + bir marta avtomatik qayta so'rash.
- Sayt, Chuqur AI: rasm qidirilayotgani chatda Tez AI dagi kabi ko'rinadi (search_start/search_done).
- **Reklama (sayt):** slaydlar ro'yxati eng tagida slayd shaklidagi karta (16:9, «Reklama» belgisi); havola bo'lsa butun rasm bosiladi. Admin panelda «Necha soat ko'rsatilsin?» tugmalari (1 soat … 30 kun, cheksiz). Pro/admin ko'rmaydi. Botda rasm/video + havola tugmasi avvaldan bor.
- **Faqat oxirgi slayd:** botda 1 ta (MAX_SAVED=1); saytda IndexedDB'dagi bitta «current» loyiha qayta yoqildi — sahifa ochilganda tiklanadi, «Rasmni tozalash» bosilganda yangisi eskisini almashtiradi.
- **Slayd o'tish animatsiyasi** (butun slayd): Animatsiya panelida (fade, zoom, flip, pastdan, blur, yo'q; «hammasiga»), Namoyishda o'ynaydi. AI: `set_transition` (bepul).
- **Jadval va grafik:** asboblar panelida «Jadval» / «Grafik» tugmalari; AI `elements[]` ichida `{"type":"table"|"chart"}` yaratadi (ustunli, chiziqli, doira, halqa). PPTX ga rasm bo'lib o'tadi.
- **Chuqur AI:** rasm qidirish darhol «qidirilmoqda» ko'rsatadi.

## v48.1 — jadval, diagramma va slayd o'tishi hamma joyda (bot + sayt + PowerPoint)
- **Bot (`tg_decks.py`)**: yangi `table` va `chart` (bar/line/pie/doughnut) slaydlari, `transition` (fade/zoom/flip/up/blur/none) — deck va har bir slayd uchun.
  - PPTX: **haqiqiy** PowerPoint jadvali va diagrammasi (python-pptx, tahrirlanadi) + `<p:transition>`.
  - PDF: jadval/diagramma vektor chiziladi. HTML: SVG + slayd o'tish animatsiyasi.
  - AI: `GEN_SYSTEM`/`EDIT_SYSTEM` yangilandi; `{"op":"transition"}` va `meta.transition`.
- **Sayt**: jadval/grafik guruhlari `ssSpec` saqlaydi (SERIALIZE_PROPS), PPTX eksportda PptxGenJS `addTable`/`addChart` (haqiqiy obyektlar), har slaydga `<p:transition>` yoziladi; o'tish loyiha faylida (project.json) saqlanadi va tiklanadi.

## v49 — sayt: hech narsa saqlanmaydi
- Sayt slaydlarni brauzerda ham (IndexedDB), window.name orqali ham saqlamaydi: sahifa yangilansa yoki Google'dan qaytsa — hammasi 0 dan. Eski saqlangani ham o'chiriladi.
- Chap panel eng pastida «Hamma varaqni tozalash» tugmasi (ogohlantirish bilan).
- «Google bilan kirish» bosilganda hozir ish bo'lsa — «hammasi o'chadi» ogohlantirishi chiqadi; ish bo'lmasa — chiqmaydi.

## v49.1
- PPTX import: jadval va diagrammalar (statistika) endi native obyekt sifatida ochiladi; botda PPTX qayta o'qilganda matn dublikat bo'lmaydi (`_pptx_to_deck`).
- PDF import: server tomonda (`/api/import/pdf`, pypdfium2) matn/shakllar tahrirlanadigan obyektga aylanadi; o'rnatilmasa rasm zaxirasi.
- Namoyish: boshida boshqaruv tugmalari ko'rinadi, keyin yashirinadi; varaq ochilish effekti ("O'tish") alohida tugmada, viewerda ishlaydi, PPTX'ga `<p:transition>` yoziladi.
- "Izohlar" tugmasi qaytarildi; tepadagi ortiqcha "Sozlamalar" olib tashlandi; bir marta bosganda tahrirga o'tish o'chirildi.
- Botda to'liq tugmali admin panel (/admin): statistika, foydalanuvchilar, reklama (5 qadamli, muddat soat tugmalari bilan; video `tg:` orqali), xabar yuborish, sozlamalar.

## v49.2
- Saytda PPTX ochilganda qo'shimcha "karta" (matn orqasidagi to'rtburchak) qo'shilmaydi — dizayn asl holicha.
- Varaqlarni sidebarda almashtirganda varaq bo'sh qolish xatosi: endi faol varaq obyekt bo'yicha topiladi, kanvas qayta yuklanmaydi.
- O'tish paneli bosilganda yo'qolmaydi, faqat × bilan yopiladi; varaq almashsa tanlov yangilanadi.
- Bot yasagan HTML ichiga PPTX nusxasi joylanadi — muharrirda to'liq tahrirlanadigan ochiladi; sayt HTML'ida o'tish effekti saqlanadi.
- Botda /give, /take… argumentsiz yozilsa tugmali admin panel ochiladi.
