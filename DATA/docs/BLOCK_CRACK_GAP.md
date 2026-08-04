# block_crack — ochiq muammo

**Holat:** butun 113,648 boxli datasetimizda block cracking uchun **61 ta box** bor (Attain 58, RDD2022 3).

**Nega muhim:** professorning Yangizamon tadqiqotida block cracking — **eng ko'p uchraydigan nuqson, umumiy CDL ning 46.33%**. 12 bo'lakning 7 tasida yetakchi nuqson aynan shu. Agar modelimiz uni ko'rmasa, validatsiya barbod bo'ladi.

---

## Muammo faqat yorliqlar sonida emas

QOPLAMA'dagi 100 ta block cracking rasmini ko'rib chiqdim (60 tasi Toshkent, 4000×3000).

Block cracking — **nozik, yuza bo'ylab tarqalgan to'rsimon naqsh**. 4000×3000 rasm detektorga 640px da beriladi, ya'ni **6 barobar siqiladi**. Bu siqilishda naqsh butunlay yo'qoladi — thumbnail'da ham men uni zo'rg'a ko'rdim.

Ya'ni: yorliq qo'shsak ham, **640px kirishda model uni ko'ra olmaydi**.

---

## Uch yo'nalish

### 1. Yuqori aniqlikda inference (eng istiqbolli)
**SAHI** (tiled inference) — rasmni 640×640 bo'laklarga bo'lib, har birini alohida ishlash, keyin natijalarni birlashtirish. 4000×3000 rasm ~30 ta bo'lakka bo'linadi va naqsh o'z o'lchamida qoladi.

Bu **o'qitishni emas, inference'ni** o'zgartiradi — ya'ni mavjud model bilan ham sinash mumkin.

### 2. Weak bbox (zaif yorliq)
QOPLAMA'ning 100 rasmiga yo'l hududini qoplaydigan katta box qo'yish. Block cracking maydon bo'yicha o'lchanadigan nuqson bo'lgani uchun katta box semantik jihatdan to'g'ri.

⚠️ Xavf: model "block_crack = butun yo'lni qoplaydigan katta box" deb o'rganishi va boshqa klasslarni bosib ketishi mumkin.

**Qaror:** baseline train tugagach, shu bilan va shusiz solishtiriladi. Taxmin emas, o'lchov.

### 3. Alohida tekstura klassifikatori
Yo'l hududidan kesilgan yuqori aniqlikdagi parchalarni "block cracking bor/yo'q" deb baholaydigan alohida model. Detektsiya emas, klassifikatsiya.

Bu eng to'g'ri yechim, lekin 4 kunda ulgurish shubhali. Hakatondan keyingi ish.

---

## Hozircha nima qilinadi

1. Baseline detektor 61 ta box bilan o'qitiladi — natija zaif bo'lishi kutiladi
2. Inference'da **SAHI** sinaladi (kod o'zgarishi kichik)
3. Weak bbox varianti alohida o'lchanadi
4. Hisobotda **ochiq aytiladi**: block cracking bizning eng zaif klassimiz

`tests/test_dataset.py::test_block_crack_scarcity_is_visible` bu kamchilikni mahkamlab turadi — yorliqlar qo'shilsa test yiqiladi va rejani yangilashga majbur qiladi.
