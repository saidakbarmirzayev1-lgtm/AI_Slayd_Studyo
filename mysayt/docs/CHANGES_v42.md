# Slide Studio v42 — v41 ustiga tuzatishlar

1. **PPTX: galereya videosi** — muharrirdagi galereya videosi `blob:` manzilda turadi; eski kod uni YouTube kabi
   "muqova + havola"ga aylantirardi. Endi `blob:` / `https:` video MP4 faylga aylantirilib PPTX ichiga HAQIQIY video
   sifatida joylanadi (GIF kabi). Onlayn video CORS bermasa — yangi server yo'li `/api/proxy-video` (main.py) ishlatiladi
   (faqat video, 90 MB gacha). WebM/OGG PowerPoint'da ishlamaydi — ular muqova bo'lib qoladi.
   Fayllar: `js/14_pptx_io.js`, `main.py`.
2. **Namoyish** — iframe ichidagi chapga/o'ngga/hisoblagich/to'liq ekran tugmalari va X butunlay yashirildi
   (`js/30_v40_present_persist.js`). Chiqish: Esc.
3. **Tezkor javob** — matn o'lchami/qalin, tugma-link paneli, media paneli va obyektni siljitgandan keyin
   o'zgarish DARHOL ko'rinadi: og'ir saqlash (toJSON + tarix) kadr chizilgandan keyin bajariladi
   (`js/31_v42_responsive.js`, `ssDeferSave`). Katta GIF/video bor slaydlarda kechikish shundan edi.
4. **Balans oynasi** — z-index endi JS ichida ham beriladi; `v40.css` keshi `?v=2` bilan yangilanadi
   (v41 da fayl o'zgargan, lekin `?v=1` qolgani uchun brauzer eski CSS ni ishlatardi).
   Ayrim `.js` fayllar uchun ham `?v=` oshirildi.

## v42.1
5. **Namoyish tugmalari** (oldingi/keyingi, hisoblagich, to'liq ekran, X): boshida chiqmaydi. Sichqoncha qimirlasa chiqadi,
   2 soniya qimirlamasa yo'qoladi, qimirlasa yana chiqadi (`js/29_v40_html_export.js`, ko'rsatgich kodi).
6. **HTML'da YouTube/Vimeo**: fayl `file://` (ikki marta bosib) ochilganda YouTube iframe "Referer" yo'qligi uchun
   ishlamaydi. Endi bunday holatda muqova + "Videoni ochish" havolasi ko'rsatiladi; muqova eksport paytida faylga joylanadi
   (oflayn ham ko'rinadi). Sayt (https) orqali ochilsa — oddiy iframe, avto-ijro bilan.
7. **PPTX'da YouTube/Vimeo/Dailymotion**: endi PowerPoint "Onlayn video" obyekti (internet bo'lsa slaydning o'zida ijro bo'ladi),
   orqa fon videosi ham. Barcha videolar (galereya MP4, GIF-video, onlayn) slayd ochilishi bilan avtomatik boshlanadi
   (`p:timing`, "Start: Automatically"). Avto-ijro o'chirilgan videolar o'tkazib yuboriladi.

## v42.2
8. **Namoyish**: muharrirning eski tugmalari (o'tkazish va X) endi JS orqali ham doim yashirin; ko'rsatgich tugmalari
   ochilgandan keyingi 1,5 soniya ichida sichqoncha qimirlashiga javob bermaydi (shunda boshida chiqib qolmaydi).
9. **PPTX YouTube**: onlayn video ustiga kichik bosiladigan "YouTube'da ochish" belgisi qo'shildi (PowerPoint pleyeri ishlamasa,
   WPS / Google Slides / Keynote'da ham havola ochiladi).
10. **Sozlamalar**: panel tor ekranda sig'adi (kengroq, gorizontal skroll yo'q); "Joriy fonni hamma slaydga" endi fon TURINI
    (GIF/video/rasm) ham ko'chiradi — avval boshqa slaydlar keyingi saqlashda GIF/videoni yo'qotardi; "Tanlash"/"Qo'llash"
    bosilganda Sozlamalar paneli yopilib ketmaydi.

## v42.3
11. **AI: fon takrori** — AI ba'zan bir rasmni ham fon, ham slayd ustidagi obyekt qilib qo'yardi (yoki fon rangidagi butun-slayd
    to'rtburchak qo'shardi). AI buyruqlari tugagach barcha slaydlar tekshiriladi va fon bilan BIR XIL manbali rasm/GIF
    obyektlari hamda fon rangidagi butun-slayd to'rtburchaklar avtomatik olib tashlanadi (`js/31_v42_responsive.js`,
    `ssDedupeBackgrounds`). Konsolda `[v42] fon bilan takrorlangan N ta obyekt...` yoziladi.
    Eslatma: `default_system_prompt.txt` da GIF uchun "bir xil GIF ham element, ham fon bo'lmasin" qoidasi bor edi, rasm uchun yo'q edi.
