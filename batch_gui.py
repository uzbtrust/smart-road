"""A desktop window for grading drive videos, with the PCI for every second.

    python batch_gui.py

The alternative to the Streamlit app for footage that is too long, or too many
clips, to grade in a browser. Pick videos, set the camera, press *Grade*: each
second of footage gets a score in the table as soon as it is graded, and the
whole batch can be saved as an Excel workbook -- by default with a *Per second*
sheet holding one PCI per second of every clip.

Nothing is graded here that :mod:`batch_pci` does not grade. The window only
collects the settings and shows the results; detection, the camera, the ASTM
arithmetic and the workbook all come from there, so the GUI, the command line
and the app give the same score for the same frame.

Why one frame a second is the default. Sampling starts half an interval in, so
at a one-second interval the frame for second k is taken at k + 0.5 s and each
second is scored from a frame inside it. Sample less often and the seconds in
between are left empty in the workbook rather than invented.
"""
from __future__ import annotations

import queue
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import (BooleanVar, DoubleVar, IntVar, StringVar, Tk, filedialog,
                     messagebox, ttk)
import tkinter as tk

import batch_pci as bp


#: Settings fields, in the order they appear: (field, label, kind, extra).
FIELDS = [
    ("every_s", "Sample every (s)", float, "1 = one score per second"),
    ("max_frames", "Max frames per video", int, "0 = whole clip"),
    ("severity", "Severity", bp.SEVERITIES, "the model does not predict it"),
    ("conf", "Detection confidence", float, None),
    ("tiled", "Tiled inference", bool, None),
    ("overlap", "Tile overlap", float, None),
    ("sky", "Sky cut-off (fraction)", float, None),
    ("height_m", "Camera height (m)", float, "area goes with height²"),
    ("focal_35mm", "Focal length, 35 mm eq. (mm)", float, "from EXIF"),
    ("horizon", "Horizon row (fraction)", float, None),
    ("far_m", "Measure out to (m)", float, None),
]

#: The CLI option for each setting, so the workbook records a command that
#: repeats the batch without the window.
OPTION = {"every_s": "--every-s", "max_frames": "--max-frames", "severity": "--severity",
          "conf": "--conf", "overlap": "--overlap", "sky": "--sky",
          "height_m": "--height-m", "focal_35mm": "--focal-35mm",
          "horizon": "--horizon", "far_m": "--far-m"}


@dataclass
class Job:
    videos: list[tuple[Path, str]]
    settings: bp.Settings
    out: Path | None              # None: grade only, save later by hand
    per_second: bool
    detections: bool
    save_frames: str
    gps: bool


class App:
    def __init__(self, root: Tk):
        self.root = root
        root.title("smart-road — grade drive videos")
        root.minsize(980, 640)

        self.videos: list[tuple[Path, str]] = []
        self.results: list[bp.VideoResult] = []
        self.last_job: Job | None = None
        self.meta: dict = {}
        self.names: dict[int, str] = {}
        self.model = None
        self.ocr = None                   # OCR engine, made on first use
        self.events: queue.Queue = queue.Queue()
        self.stop = threading.Event()
        self.worker: threading.Thread | None = None

        d = bp.Settings()
        self.vars: dict[str, tk.Variable] = {}
        for name, _, kind, _ in FIELDS:
            value = getattr(d, name)
            if kind is bool:
                self.vars[name] = BooleanVar(value=value)
            elif kind is int:
                self.vars[name] = IntVar(value=value)
            elif kind is float:
                self.vars[name] = DoubleVar(value=value)
            else:
                self.vars[name] = StringVar(value=value)
        self.save_excel = BooleanVar(value=True)
        self.per_second = BooleanVar(value=True)
        self.detections = BooleanVar(value=False)
        self.gps = BooleanVar(value=False)
        self.save_frames = StringVar(value="none")
        self.recursive = BooleanVar(value=False)
        self.out_path = StringVar(
            value=str(Path.cwd() / f"smartroad_batch_{datetime.now():%Y-%m-%d_%H%M}.xlsx"))
        self.status = StringVar(value="Add videos to begin.")

        self._build()
        self.root.after(100, self._drain)
        root.protocol("WM_DELETE_WINDOW", self._close)

    # ───────────────────────────────────────────── layout
    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(0, weight=1)

        left = ttk.Frame(outer)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self._build_videos(left)
        self._build_settings(left)
        self._build_output(left)

        right = ttk.Frame(outer)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=3)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        self._build_table(right)
        self._build_log(right)

        bar = ttk.Frame(outer)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        bar.columnconfigure(3, weight=1)
        self.run_btn = ttk.Button(bar, text="Grade", command=self._start)
        self.run_btn.grid(row=0, column=0)
        self.stop_btn = ttk.Button(bar, text="Stop", command=self._request_stop,
                                   state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=6)
        self.export_btn = ttk.Button(bar, text="Save to Excel…", command=self._export,
                                     state="disabled")
        self.export_btn.grid(row=0, column=2)
        self.progress = ttk.Progressbar(bar, mode="determinate")
        self.progress.grid(row=0, column=3, sticky="ew", padx=10)
        ttk.Label(bar, textvariable=self.status, width=48, anchor="w").grid(row=0, column=4)

    def _build_videos(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Videos", padding=6)
        box.pack(fill="x")
        self.video_list = tk.Listbox(box, height=7, width=46, selectmode="extended")
        self.video_list.pack(fill="x")
        row = ttk.Frame(box)
        row.pack(fill="x", pady=(4, 0))
        ttk.Button(row, text="Add files…", command=self._add_files).pack(side="left")
        ttk.Button(row, text="Add folder…", command=self._add_folder).pack(side="left", padx=4)
        ttk.Button(row, text="Remove", command=self._remove).pack(side="left")
        ttk.Button(row, text="Clear", command=self._clear).pack(side="left", padx=4)
        ttk.Checkbutton(box, text="Include subfolders", variable=self.recursive).pack(anchor="w")

    def _build_settings(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Settings (defaults are the app's)", padding=6)
        box.pack(fill="x", pady=8)
        for r, (name, label, kind, hint) in enumerate(FIELDS):
            ttk.Label(box, text=label).grid(row=r, column=0, sticky="w", pady=1)
            var = self.vars[name]
            if kind is bool:
                w = ttk.Checkbutton(box, variable=var)
            elif isinstance(kind, tuple):
                w = ttk.Combobox(box, textvariable=var, values=kind, state="readonly", width=9)
            else:
                w = ttk.Entry(box, textvariable=var, width=10)
            w.grid(row=r, column=1, sticky="w", padx=6)
            if hint:
                ttk.Label(box, text=hint, foreground="#777").grid(row=r, column=2, sticky="w")

    def _build_output(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Output", padding=6)
        box.pack(fill="x")
        ttk.Checkbutton(box, text="Save as Excel workbook while grading",
                        variable=self.save_excel, command=self._toggle_out).pack(anchor="w")
        row = ttk.Frame(box)
        row.pack(fill="x", pady=2)
        self.out_entry = ttk.Entry(row, textvariable=self.out_path, width=36)
        self.out_entry.pack(side="left", fill="x", expand=True)
        self.out_btn = ttk.Button(row, text="Browse…", command=self._pick_out)
        self.out_btn.pack(side="left", padx=4)
        ttk.Checkbutton(box, text="Per-second sheet (one PCI per second of footage)",
                        variable=self.per_second).pack(anchor="w")
        ttk.Checkbutton(box, text="GPS coordinates (from the video, or printed on it)",
                        variable=self.gps).pack(anchor="w")
        ttk.Checkbutton(box, text="Detections sheet (every box)",
                        variable=self.detections).pack(anchor="w")
        row = ttk.Frame(box)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Annotated frames:").pack(side="left")
        ttk.Combobox(row, textvariable=self.save_frames, values=("none", "worst", "all"),
                     state="readonly", width=7).pack(side="left", padx=4)

    def _build_table(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Score per second", padding=6)
        box.grid(row=0, column=0, sticky="nsew")
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        cols = ("video", "second", "pci", "rating", "low", "high", "distress", "boxes",
                "gps")
        heads = ("Video", "Second", "PCI", "Rating", "if low", "if high",
                 "Main distress", "Boxes", "Lat, Lon")
        widths = (110, 50, 45, 90, 45, 45, 125, 40, 165)
        self.table = ttk.Treeview(box, columns=cols, show="headings")
        for c, h, w in zip(cols, heads, widths):
            self.table.heading(c, text=h)
            self.table.column(c, width=w, anchor="w" if c in ("video", "distress") else "center")
        for _, label, colour in bp.RATING_SCALE:
            self.table.tag_configure(label, background=colour, foreground=bp.ink_for(colour))
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.table.yview)
        across = ttk.Scrollbar(box, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=across.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        across.grid(row=1, column=0, sticky="ew")

    def _build_log(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Log", padding=6)
        box.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        self.log = tk.Text(box, height=7, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")

    # ───────────────────────────────────────────── videos and output
    def _add(self, inputs: list[str], recursive: bool = False) -> None:
        found, unmatched = bp.collect_videos(inputs, recursive=recursive)
        have = {p.resolve() for p, _ in self.videos}
        for path, label in found:
            if path.resolve() not in have:
                self.videos.append((path, label))
                self.video_list.insert("end", label)
        for raw in unmatched:
            self._say(f"No videos in {raw}")

    def _add_files(self) -> None:
        exts = " ".join(f"*{e} *{e.upper()}" for e in sorted(bp.VIDEO_SUFFIXES))
        paths = filedialog.askopenfilenames(title="Choose drive videos",
                                            filetypes=[("Videos", exts), ("All files", "*")])
        self._add(list(paths))

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose a folder of videos")
        if folder:
            self._add([folder], recursive=self.recursive.get())

    def _remove(self) -> None:
        for i in reversed(self.video_list.curselection()):
            self.video_list.delete(i)
            del self.videos[i]

    def _clear(self) -> None:
        self.video_list.delete(0, "end")
        self.videos.clear()

    def _pick_out(self) -> None:
        current = Path(self.out_path.get() or "smartroad_batch.xlsx")
        path = filedialog.asksaveasfilename(
            title="Save the workbook as", defaultextension=".xlsx",
            initialdir=str(current.parent), initialfile=current.name,
            filetypes=[("Excel workbook", "*.xlsx")])
        if path:
            self.out_path.set(path)

    def _toggle_out(self) -> None:
        state = "normal" if self.save_excel.get() else "disabled"
        self.out_entry.configure(state=state)
        self.out_btn.configure(state=state)

    def _resolved_out(self, raw: str) -> Path:
        out = Path(raw).expanduser().resolve()
        if out.suffix.lower() != ".xlsx":
            out = out.with_name(out.name + ".xlsx")
        return out

    # ───────────────────────────────────────────── running
    def _settings(self) -> bp.Settings | None:
        try:
            values = {name: self.vars[name].get() for name, *_ in FIELDS}
        except tk.TclError:
            messagebox.showerror("Settings", "Every setting needs a number.")
            return None
        s = bp.Settings(**values)
        if problems := s.problems():
            messagebox.showerror("Settings", "\n".join(problems))
            return None
        return s

    def _start(self) -> None:
        if not self.videos:
            messagebox.showinfo("No videos", "Add at least one video first.")
            return
        s = self._settings()
        if s is None:
            return
        out = None
        if self.save_excel.get():
            if not self.out_path.get().strip():
                messagebox.showerror("Output", "Choose where to save the workbook.")
                return
            out = self._resolved_out(self.out_path.get())
            if out.exists() and not messagebox.askyesno(
                    "Replace?", f"{out.name} already exists. Replace it?"):
                return
            out.parent.mkdir(parents=True, exist_ok=True)
        if self.gps.get() and not (bp.exiftool() and bp.overlay_gps.available()):
            missing = []
            if not bp.exiftool():
                missing.append("• GPS tracks inside the video need ExifTool "
                               "(https://exiftool.org; Linux: apt install "
                               "libimage-exiftool-perl).")
            if not bp.overlay_gps.available():
                missing.append("• Coordinates printed on the picture need OCR: "
                               + bp.overlay_gps.INSTALL_HINT)
            if not messagebox.askokcancel(
                    "GPS sources missing",
                    "\n".join(missing) + "\n\nVideos whose GPS needs these will get "
                    "blank coordinates. Grade anyway?"):
                return
        if self.per_second.get() and s.every_s > 1:
            self._say(f"Sampling every {s.every_s:g} s: seconds between samples "
                      "will be empty in the per-second sheet.")
        job = Job(list(self.videos), s, out, self.per_second.get(),
                  self.detections.get(), self.save_frames.get(), self.gps.get())
        self.last_job = job
        self.results = []
        self.table.delete(*self.table.get_children())
        self.stop.clear()
        self._busy(True)
        self.worker = threading.Thread(target=self._run, args=(job,), daemon=True)
        self.worker.start()

    def _request_stop(self) -> None:
        self.stop.set()
        self.status.set("Stopping after this frame…")

    def _busy(self, busy: bool) -> None:
        self.run_btn.configure(state="disabled" if busy else "normal")
        self.stop_btn.configure(state="normal" if busy else "disabled")
        self.export_btn.configure(
            state="disabled" if busy or not self.results else "normal")

    def _command(self, job: Job) -> str:
        """The batch_pci.py command that repeats this job without the window."""
        d = bp.Settings()
        argv = [str(p) for p, _ in job.videos]
        if job.out:
            argv += ["-o", str(job.out)]
        for name, opt in OPTION.items():
            value = getattr(job.settings, name)
            if value != getattr(d, name):
                argv += [opt, f"{value:g}" if isinstance(value, float) else str(value)]
        if not job.settings.tiled:
            argv.append("--no-tiled")
        if job.per_second:
            argv.append("--per-second")
        if job.gps:
            argv.append("--gps")
        if job.detections:
            argv.append("--detections")
        if job.save_frames != "none":
            argv += ["--save-frames", job.save_frames]
        return bp._command(argv)

    def _run(self, job: Job) -> None:
        """Worker thread: talks to the window only through `self.events`."""
        emit = self.events.put
        try:
            if self.model is None:
                emit(("status", "Loading the detector…"))
                self.model, weights = bp.load_model()
                self.names = dict(self.model.names)
                self.device = bp.pick_device()
                self.weights = weights
                emit(("log", f"Weights {weights} on {self.device}"))
            self.meta = {"date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                         "command": self._command(job), "commit": bp.git_commit(),
                         "weights": str(self.weights), "device": self.device,
                         "versions": bp._versions(),
                         "exiftool": bp.exiftool_version() if job.gps else None}
            planned = [bp._planned_frames(p, job.settings) for p, _ in job.videos]
            total, done = max(1, sum(planned)), 0
            frames_dir = (job.out.with_name(f"{job.out.stem}_frames")
                          if job.out and job.save_frames != "none" else None)
            stopped = False

            for k, ((path, label), n) in enumerate(zip(job.videos, planned), 1):
                v = bp.VideoResult(path=path, label=label)
                self.results.append(v)
                emit(("log", f"[{k}/{len(job.videos)}] {label}"
                      + (f"  ({n} frames)" if n else "")))

                reader = None
                if job.gps:
                    bp.attach_gps(v)
                    if bp.wants_overlay(v) and bp.overlay_gps.available():
                        if self.ocr is None:
                            self.ocr = bp.overlay_gps.OverlayReader()
                        reader = self.ocr
                        emit(("log", f"      GPS: {v.gps_note}; reading the "
                                     "coordinates printed on the frames"))
                    else:
                        emit(("log", f"      GPS: {v.gps_note}"))

                def tick(i: int, v=v, k=k, n=n, base=done) -> None:
                    fr = v.frames[-1]
                    fix = (bp.Fix(fr.t_s, *fr.overlay) if fr.overlay
                           else v.gps.at(fr.t_s) if v.gps else None)
                    emit(("frame", v.label, v.frames[-1], job.settings.severity, fix))
                    emit(("progress", base + i, total,
                          f"{v.label}: frame {i} of {n or '?'}"))
                    if self.stop.is_set():
                        raise KeyboardInterrupt

                try:
                    bp.grade_video(v, self.model, self.names, job.settings, self.device,
                                   video_no=k, save_frames=job.save_frames,
                                   frames_dir=frames_dir, progress=tick,
                                   overlay=reader)
                except KeyboardInterrupt:
                    v.status = f"Interrupted after {len(v.frames)} frames"
                    stopped = True
                if reader is not None:
                    bp.finish_overlay_gps(v)
                    emit(("log", f"      GPS: {v.gps_note}"))
                done += len(v.frames)

                st = bp.video_stats(v, job.settings.severity)
                if v.ok and st:
                    worst = st.worst.graded[job.settings.severity].pci
                    emit(("log", f"      mean PCI {st.mean:.1f} {bp.rating_of(st.mean)[0]}"
                                 f" | worst {worst:.1f} at {st.worst.t_s:.1f} s"))
                else:
                    emit(("log", f"      {v.status}"))
                if job.out:
                    job.out = self._save(job.out, job)
                if stopped:
                    break
            emit(("done", stopped))
        except Exception as exc:          # noqa: BLE001 -- shown, not swallowed
            emit(("log", traceback.format_exc()))
            emit(("error", f"{type(exc).__name__}: {exc}"))

    def _save(self, out: Path, job: Job) -> Path:
        """Write the workbook; a copy open in Excel gets a new name, not an error."""
        def write(path: Path) -> None:
            bp.write_workbook(path, self.results, job.settings, self.meta, self.names,
                              with_detections=job.detections, per_second=job.per_second,
                              gps=job.gps,
                              warn=lambda m: self.events.put(("log", m.strip())))
        try:
            write(out)
        except PermissionError:
            alt = out.with_name(f"{out.stem}_{datetime.now():%H%M%S}{out.suffix}")
            self.events.put(("log", f"{out.name} is open in another program; "
                                    f"saving to {alt.name}"))
            write(alt)
            out = alt
        self.events.put(("log", f"      saved {out}"))
        return out

    def _export(self) -> None:
        """Save results graded without a workbook, or save them again elsewhere."""
        job = self.last_job
        if not job or not self.results:
            return
        path = filedialog.asksaveasfilename(
            title="Save the workbook as", defaultextension=".xlsx",
            initialfile=Path(self.out_path.get() or "smartroad_batch.xlsx").name,
            filetypes=[("Excel workbook", "*.xlsx")])
        if not path:
            return
        job.per_second = self.per_second.get()
        job.detections = self.detections.get()
        job.gps = self.gps.get()
        if job.gps:                       # ticked after grading: read it now
            self.status.set("Reading GPS…")
            self.root.update_idletasks()
            for v in self.results:
                if v.gps_note is None:
                    bp.attach_gps(v)
            self.meta["exiftool"] = bp.exiftool_version()
        try:
            saved = self._save(self._resolved_out(path), job)
        except Exception as exc:          # noqa: BLE001
            messagebox.showerror("Could not save", str(exc))
            return
        self.status.set(f"Saved {saved.name}")

    # ───────────────────────────────────────────── the window's side
    def _drain(self) -> None:
        try:
            while True:
                self._handle(self.events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    def _handle(self, ev) -> None:
        kind = ev[0]
        if kind == "frame":
            _, label, fr, severity, fix = ev
            a = fr.graded[severity]
            pairs = bp.deducts_by_distress(a)
            main = (bp.DISTRESS_PRETTY.get(pairs[0][0].distress, pairs[0][0].distress)
                    if pairs else "")
            row = self.table.insert("", "end", tags=(a.rating,), values=(
                label, f"{int(fr.t_s)}–{int(fr.t_s) + 1}", f"{a.pci:.1f}", a.rating,
                f"{fr.graded['low'].pci:.1f}", f"{fr.graded['high'].pci:.1f}",
                main, len(fr.detections),
                f"{fix.lat:.6f}, {fix.lon:.6f}" if fix else ""))
            self.table.see(row)
        elif kind == "progress":
            _, done, total, text = ev
            self.progress.configure(maximum=total, value=done)
            self.status.set(text)
        elif kind == "status":
            self.status.set(ev[1])
        elif kind == "log":
            self._say(ev[1])
        elif kind == "done":
            stopped = ev[1]
            ok = sum(1 for v in self.results if v.ok)
            self.status.set(f"{'Stopped' if stopped else 'Done'}: {ok} of "
                            f"{len(self.results)} video(s) graded")
            self._busy(False)
        elif kind == "error":
            self.status.set("Failed")
            self._busy(False)
            messagebox.showerror("Grading failed", ev[1])

    def _say(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Grading", "A batch is running. Stop it and quit? "
                                       "Videos already finished are in the workbook, "
                                       "if one was chosen; the current one is lost."):
                return
            self.stop.set()
        self.root.destroy()


def main() -> None:
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
