# v44

## Mobil / UI
- js/34_v44_mobile_fix.js: slayddagi matn ("Sarlavha Kiriting") bosilganda sahifa gorizontal siljib ketishi tuzatildi
  (Fabric yashirin textarea focus -> preventScroll; hujjat skrolli har doim 0 ga qaytariladi; klaviatura/visualViewport).
- v40.css: html/body `overflow-x: clip`; balans bloki (`.ss-meter` min-width 210px) tor ekranga sig'adi; #ssQuotaPop kengligi ekranga moslashadi.
- Sozlamalar oynasida "AI varaqlar" bloki qaytarildi (responsiv) + "Sotib olish".

## Telegram bot
- /start javob bermasligi sababi: Render `generateValue` maxfiy kaliti Telegram talab qilmaydigan belgilar (+ / =) bo'lishi mumkin
  -> setWebhook rad etilardi. Endi kalit har doim HEX. Webhook o'rnatilmasa avtomatik long-polling (TELEGRAM_MODE=auto).
- Webhook har 10 daqiqada tekshiriladi; diagnostika: GET /api/telegram/status.
- Matn -> slayd soni -> AI -> PPTX / PDF / HTML yoki "Hammasi" (3 fayl). Tahrirlash (matn bilan), rang (bepul), /mode, /new.
- Kredit: Telegram akkaunt (tg<ID>@t.me) = Mini App akkaunti; 1 slayd = 1 varaq.
- backend/tg_decks.py (yangi), backend/fonts (DejaVu), requirements: python-pptx, reportlab, pillow.
