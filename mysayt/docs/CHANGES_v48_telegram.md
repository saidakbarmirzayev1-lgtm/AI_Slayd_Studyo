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
