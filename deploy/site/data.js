/* Fixtures for the static site.

   PROVENANCE — every figure here appears in SAYT_MATNI.md or comes from the
   repository, and the sources are listed at the foot of that document:
   · S1–S12 PCI, whole street 51.4, A 56.4 / B 46.4 — DATA/docs/YANGIZAMON_PCI.md §2
   · S7 vs S11, deduct 62.6 / 16.9 — same file, §3
   · severity triple 50.3 / 35.2 / 19.4 — app.py, README.md
   · camera height 1.70 m — app.py:355

   The per-row quantities in the deduct chain and the bounding-box geometry are
   the one exception: they come from the detector at run time. They are
   internally consistent with the score shown (100 − 64.8 = 35.2). Replace them
   with a real detector run before the jury sees this. */
window.SR_DATA = {
  sections: [
    { s: "S1", cdl: 28.37, pci: 52.3 }, { s: "S2", cdl: 28.89, pci: 64.6 },
    { s: "S3", cdl: 29.03, pci: 61.1 }, { s: "S4", cdl: 49.38, pci: 33.1 },
    { s: "S5", cdl: 43.72, pci: 64.8 }, { s: "S6", cdl: 43.28, pci: 62.7 },
    { s: "S7", cdl: 33.98, pci: 26.6 }, { s: "S8", cdl: 60.44, pci: 32.4 },
    { s: "S9", cdl: 16.82, pci: 45.6 }, { s: "S10", cdl: 23.54, pci: 58.3 },
    { s: "S11", cdl: 70.55, pci: 45.6 }, { s: "S12", cdl: 39.44, pci: 69.9 },
  ],
  heroBoxes: [
    { cls: "longitudinal_transverse_crack", x: 53.5, y: 60, w: 3.2, h: 13, label: "long/trans 0.44", seam: true },
    { cls: "longitudinal_transverse_crack", x: 54.2, y: 68, w: 2.6, h: 8 },
    { cls: "longitudinal_transverse_crack", x: 54.6, y: 82, w: 2.4, h: 14 },
    { cls: "alligator_crack", x: 38.5, y: 60, w: 2.6, h: 5, label: "alligator 0.31" },
  ],
  frame: {
    roi: { y: 45, h: 55 },
    boxes: [
      { cls: "alligator_crack", x: 41, y: 60, w: 14, h: 13, label: "alligator 0.62" },
      { cls: "longitudinal_transverse_crack", x: 57, y: 56, w: 21, h: 6, label: "long/trans 0.41" },
      { cls: "longitudinal_transverse_crack", x: 22, y: 72, w: 17, h: 5, label: "long/trans 0.35" },
      { cls: "pothole", x: 2, y: 63, w: 7, h: 6, label: "pothole 0.33", seam: true },
    ],
    rows: [
      { distress: { uz: "Toʻrsimon (charchoq) yoriq", ru: "Сетка усталостных трещин", en: "Alligator cracking" }, n: 1, quantity: "3.4", unit: { uz: "m²", ru: "м²", en: "m²" }, density: "3.18", deduct: 41.2 },
      { distress: { uz: "Chuqurcha", ru: "Выбоины", en: "Potholes" }, n: 1, quantity: "1", unit: "×", density: "0.93", deduct: 32.9 },
      { distress: { uz: "Boʻylama va koʻndalang yoriq", ru: "Продольные и поперечные трещины", en: "Longitudinal & transverse cracking" }, n: 2, quantity: "2.6", unit: { uz: "m", ru: "м", en: "m" }, density: "2.43", deduct: 18.7 },
    ],
    q: 3, maxCdv: 64.8, pci: 35.2,
  },
};

/* The eight classes, named and numbered to the ASTM D6433 catalogue.
   Marking / manhole is detected so the model stops mistaking it for a distress;
   it carries no ASTM number and never enters the PCI. */
window.SR_CLASSES = [
  { cls: "longitudinal_transverse_crack", astm: 10, uz: "Boʻylama va koʻndalang yoriq", ru: "Продольные и поперечные трещины", en: "Longitudinal & transverse cracking" },
  { cls: "alligator_crack", astm: 1, uz: "Toʻrsimon (charchoq) yoriq", ru: "Сетка усталостных трещин", en: "Alligator cracking" },
  { cls: "block_crack", astm: 3, uz: "Bloksimon yoriq", ru: "Блочные трещины", en: "Block cracking" },
  { cls: "patching", astm: 11, uz: "Yamoq", ru: "Заплаты", en: "Patching" },
  { cls: "pothole", astm: 13, uz: "Chuqurcha", ru: "Выбоины", en: "Potholes" },
  { cls: "weathering_raveling", astm: 19, uz: "Yemirilish / tishlashish", ru: "Выкрашивание и шелушение", en: "Weathering / raveling" },
  { cls: "lane_shoulder_drop_off", astm: 9, uz: "Chekka pasayishi", ru: "Уступ обочины", en: "Lane / shoulder drop-off" },
  { cls: "marking_manhole", astm: null, uz: "Yoʻl belgisi / quduq", ru: "Разметка / люк", en: "Marking / manhole" },
];

/* ASTM D6433's rating scale. Order and thresholds are fixed by the standard. */
window.SR_BANDS = [
  { min: 85, key: "good" }, { min: 70, key: "satisfactory" }, { min: 55, key: "fair" },
  { min: 40, key: "poor" }, { min: 25, key: "very-poor" }, { min: 10, key: "serious" }, { min: 0, key: "failed" },
];
window.srBand = function (pci) {
  return (window.SR_BANDS.find(function (b) { return pci >= b.min; }) || window.SR_BANDS[6]).key;
};
