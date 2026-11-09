# backend/

| Modul | Vazifa |
|-------|--------|
| `scaling.py` | Redis ixtiyoriy scaling |
| `monitoring.py` | **Varaq hisoblash / billing** — AI amallar narxi, tariflar |

`main.py` ikkalasini ham import qiladi. Ishga tushirish: `python main.py`.

## monitoring.py — varaq qoidalari (v18.10)
1 varaq = 1 ta slaydga tegishli o'zgarish (bitta slaydga nechta amal bo'lsa ham — 1 marta).
- slayd qo'shish / nusxalash → 1; o'chirish → 1 (har biri); tahrirlash → 1 (har bir tegilgan slayd)
- 2 slayd tahrirlansa → 2; 2 slayd o'rni almashsa (`swap_slides`) → 2; `move_slide` → 1
- `reset_deck` → o'chirilgan slaydlar + qolgan slaydlar (o'chirishni hisoblamaslik: `RESET_DECK_CHARGES_DELETED=False`)
- navigatsiya (`switch_slide`), `success`/`error` → 0; noma'lum yoki yaroqsiz (mavjud bo'lmagan slayd) amal → 0
- Faqat chat (actions bo'sh): 4 ta prompt = 1 varaq
- Bepul: kuniga 15 Tez-varaq (5 Chuqur); pullik: $1 → 150 Tez-varaq (50 Chuqur). Hisob birlikda, faqat serverda.
