# v43 — Eksport fayl hajmi tuzatmasi

Sabab: rasmlar asl o'lchamda (3-5 MB) slayd JSON'iga base64 bo'lib yozilgan; eksportda bu JSON
PDF (2 nusxa), PPTX (1 nusxa) va HTML (1 nusxa) ichiga qayta joylanardi; PDF sahifalari PNG x3 edi.

O'zgarishlar
- js/32_v43_slim_images.js (YANGI): rasmlarni ko'rinadigan o'lchamining 2x gacha (max 1920px) JPEG ga siqadi,
  shaffof PNG saqlanadi, GIF tegilmaydi, fabric width/height/scale/crop mos o'zgaradi. Yangi yuklangan rasm max 1600px.
- js/28_v39_fixes.js: embedAll() ichida har eksportdan oldin ssSlimSlideJson() chaqiriladi (PDF, PPTX, HTML, JSON uchun).
- js/10_export_present.js: PDF sahifalari JPEG x2 (q .88); GIF/video fon bo'lsa PNG x2 (avval PNG x3).
- js/14_pptx_io.js: obyekt PNG x3 -> x2; katta rasmlar eksportda siqiladi.
- index.html: yangi modul ulandi, kesh versiyalari yangilandi.
