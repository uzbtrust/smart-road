/* Fixtures for the static site.

   PROVENANCE — every figure here appears in SAYT_MATNI.md or comes from the
   repository, and the sources are listed at the foot of that document:
   · S1–S12 PCI, whole street 51.4, A 56.4 / B 46.4 — DATA/docs/YANGIZAMON_PCI.md §2
   · S7 vs S11, deduct 62.6 / 16.9 — same file, §3
   · severity triple 51.5 / 36.5 / 20.5 — measured on the sample named above
   · camera height 1.70 m — app.py:355

   The deduct chain and the boxes were illustrative until the detector was run
   against the frame the figure actually ships; they are its real output now,
   so there is nothing left on this page a reader cannot reproduce. */
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
    /* Every value below is the detector's own output for the sample named in
       the caption, at the app's default settings -- 1.70 m, 25 mm, horizon
       0.139, confidence 0.25, tiling on, medium severity. Open that sample in
       the app and the screen matches this figure. Nothing here is drawn by
       hand, because a figure a reader cannot reproduce is worth less than one
       with fewer boxes in it. */
    boxes: [
      { cls: "alligator_crack", x: 0, y: 63, w: 37, h: 36, label: "alligator 0.87" },
      { cls: "alligator_crack", x: 38, y: 56, w: 40, h: 43, label: "alligator 0.69" },
      { cls: "alligator_crack", x: 41, y: 56, w: 22, h: 26, label: "alligator 0.68" },
      { cls: "longitudinal_transverse_crack", x: 12, y: 61, w: 14, h: 12, label: "long/trans 0.47" },
    ],
    rows: [
      { distress: { uz: "Toʻrsimon (charchoq) yoriq", ru: "Сетка усталостных трещин", en: "Alligator cracking" }, n: 3, quantity: "9.7", unit: { uz: "m²", ru: "м²", en: "m²" }, density: "33.57", deduct: 61.5 },
      { distress: { uz: "Boʻylama va koʻndalang yoriq", ru: "Продольные и поперечные трещины", en: "Longitudinal & transverse cracking" }, n: 1, quantity: "1.6", unit: { uz: "m", ru: "м", en: "m" }, density: "5.49", deduct: 12.4 },
    ],
    q: 2, maxCdv: 63.5, pci: 36.5,
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
