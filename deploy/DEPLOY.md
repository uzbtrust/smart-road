# Deploy — MVP havolasi va sayt

Tanlov formasida ikkita havola soʻraladi: **MVP havolasi** (ishlayotgan ilova) va
**loyiha video havolasi**. Sayt esa alohida — u Vercelda turadi.

Ikkisi bir joyda ishlamaydi, va sababi aniq: **Vercel serverless funksiyasining
chegarasi 250 MB**, faqat `torch` esa ~800 MB. Ya'ni:

| Nima | Qayerda | Nega |
|---|---|---|
| Marketing sayt (statik) | Vercel | Tez, bepul, oʻz domeni |
| Tahlil ilovasi (Streamlit + torch) | Hugging Face Spaces | Python muhiti, CPU, bepul |

Saytdagi "Ishlashini koʻring" tugmasi Space'ga olib boradi.

---

## 1. Hugging Face Space — ✅ jonli

**MVP havolasi: https://huggingface.co/spaces/uzbtrust/smart-road**
Ilovaning bevosita manzili: `https://uzbtrust-smart-road.hf.space`

`app.py` vaznlarni oʻzi yuklab oladi ([app.py:116](../app.py:116) — lokal fayl
boʻlmasa `hf_hub_download` ga tushadi), shuning uchun Space'ga model qoʻyish
shart emas.

Yangilash uchun:

```bash
zsh -ic '.venv/bin/python deploy/push_space.py'
```

### Nega yangi Space yaratilmadi

Ikkita toʻsiq bor edi va ikkalasi ham hujjatlashtirishga arziydi.

**Birinchi:** Hugging Face Streamlit SDK sini olib tashlagan. `space_sdk="streamlit"`
endi `BadRequestError` beradi — ruxsat etilganlari `gradio`, `docker`, `static`.
Shuning uchun ilova Docker Space sifatida ketadi (`deploy/hf_space/Dockerfile`).

**Ikkinchi:** bepul akkaunt endi Docker Space **yarata olmaydi** — `create_repo`
402 qaytaradi. Lekin akkauntda allaqachon bepul `cpu-basic` Docker Space bor edi
(`uzbtrust/triagegeist`), ya'ni eskilari saqlanib qolgan, yangisi taqiqlangan.

Shuning uchun `push_space.py` Space yaratmaydi — mavjudining **nomini
oʻzgartiradi** (`triagegeist` → `smart-road`). Bu 402 chiqadigan joyga umuman
bormaydi. Eski Space'ni oʻchirib yangisini yaratish esa ishlamas edi: eskisidan
ayrilib, baribir 402 ga urilar edik. Eski tarkib Space'ning git tarixida qoldi.

### Nimaga eʼtibor berish kerak

- **Build ~2.5 daqiqa.** Agar build logida `nvidia-*` paketlari yuklanayotgan
  boʻlsa, CPU indeksi ishlamayapti — `requirements.txt` dagi izohga qarang.
- **opencv: GUI emas, headless boʻlishi shart.** `ultralytics` oʻz
  bogʻliqligida `opencv-python` ni eʼlon qiladi, shuning uchun pip uni
  `requirements.txt` dagi headless versiyasi ustidan oʻrnatadi — ikkalasi bir
  xil `cv2` modulini beradi, oxirgi yozilgani ustun chiqadi. GUI versiyasi
  esa importda `libxcb.so.1` topolmay yiqiladi. Dockerfile buni pip oʻrnatib
  boʻlgach headless'ni majburan qaytarish orqali hal qiladi.
- ⚠️ **Space "RUNNING" deyishi ilova ishlayotganini bildirmaydi.** Konteyner
  koʻtarilgan, lekin `app.py` ichida import yiqilgan boʻlishi mumkin — panel
  baribir yashil koʻrsatadi. Har deploydan keyin sahifani **ochib koʻring**.
- **CPU sekin.** Bitta fotosurat bir necha soniya. Video rejimi 15 kadr uchun
  bir necha daqiqa boʻlishi mumkin. Demo yozuvini **lokalda** oling (MPS bilan
  0.19 s/kadr), Space esa hakamlar bosib koʻrishi uchun.
- **Sovuq start.** Bepul Space 48 soat ishlatilmasa uxlaydi va uygʻonishi ~30
  soniya. Ariza topshirishdan oldin bir marta ochib qoʻying.

---

## 2. Vercel

Claude Design saytni eksport qilgach:

```bash
npm i -g vercel
vercel --prod
```

Statik sayt uchun sozlama talab qilinmaydi. Uch tilli boʻlgani uchun marshrut
`/uz`, `/ru`, `/en` koʻrinishida boʻlsa, `vercel.json` da `/` dan `/uz` ga
redirect qoʻyiladi.

### Shriftlar

Design system hozir IBM Plex ni Google Fonts CDN dan oladi. Vercelda bu ishlaydi,
lekin uchinchi tomon soʻrovi qoladi — sekinroq va offlayn koʻrsatuvda sinadi.
Deploydan oldin shriftlarni `public/fonts/` ga koʻchirib, `@font-face` ni lokal
qilish kerak. Claude Design'dan bu blok soʻralgan.
