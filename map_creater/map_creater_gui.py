#!/usr/bin/env python3
"""
ROS2 Arena Map Builder v2
──────────────────────────────────────────────────────────────────
Features:
  • Setup window: enter width, height (m) and cell size (cm)
  • Grid editor with scrollable canvas
  • Click to toggle cells  |  Drag to paint/erase
  • Zoom: Ctrl+Scroll  or  +/- keys  or  toolbar buttons
  • Ruler axes on top & left showing real-world metres
  • Live coordinate tooltip: cell (col, row) and real-world (x m, y m)
  • Origin (0,0) = BOTTOM-LEFT  →  X grows right, Y grows UP
    (matches ROS2 Humble nav2 map_server default convention)
  • Fill Border, Clear All tools
  • Press S to save as ROS2-compatible PGM + YAML
──────────────────────────────────────────────────────────────────
"""

import tkinter as tk
from tkinter import messagebox, filedialog
import numpy as np
import yaml
import os
from datetime import datetime

# ── Palette ────────────────────────────────────────────────────────────────────
FREE_COLOR    = "#DDE3EA"
OCC_COLOR     = "#1A1D23"
GRID_COLOR    = "#B0BAC6"
RULER_BG      = "#161B22"
RULER_FG      = "#8B949E"
RULER_TICK    = "#30363D"
BG_COLOR      = "#0D1117"
PANEL_COLOR   = "#161B22"
ACCENT        = "#00D4AA"
ACCENT2       = "#58A6FF"
TEXT_COLOR    = "#E6EDF3"
HOVER_COLOR   = "#FFD700"
ORIGIN_COLOR  = "#FF6B6B"
FONT          = ("Courier New", 9)
FONT_B        = ("Courier New", 9, "bold")
FONT_TITLE    = ("Courier New", 17, "bold")

RULER_W       = 38    # px width of left (Y) ruler
RULER_H       = 24    # px height of top (X) ruler
MIN_ZOOM      = 2
MAX_ZOOM      = 80
ZOOM_STEP     = 1.25


# ══════════════════════════════════════════════════════════════════════════════
# Setup Window
# ══════════════════════════════════════════════════════════════════════════════
class SetupWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Arena Map Builder — Setup")
        self.root.configure(bg=BG_COLOR)
        self.root.resizable(False, False)
        self.result = None
        self._build_ui()
        self._center()
        self.root.mainloop()

    def _center(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth()  - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"+{x}+{y}")

    def _build_ui(self):
        f = tk.Frame(self.root, bg=BG_COLOR, padx=44, pady=40)
        f.pack()

        tk.Label(f, text="ARENA MAP BUILDER", font=FONT_TITLE,
                 fg=ACCENT, bg=BG_COLOR).grid(row=0, columnspan=2, pady=(0, 4))
        tk.Label(f, text="ROS2 Navigation Grid Editor  ·  v2",
                 font=("Courier New", 9), fg="#6E7681", bg=BG_COLOR
                 ).grid(row=1, columnspan=2, pady=(0, 28))

        fields = [
            ("Arena Width   (m) :", "4",  "w"),
            ("Arena Height  (m) :", "4",  "h"),
            ("Cell Size    (cm) :", "10", "c"),
        ]
        self._vars = {}
        for i, (lbl, val, key) in enumerate(fields, start=2):
            tk.Label(f, text=lbl, font=FONT, fg=TEXT_COLOR, bg=BG_COLOR,
                     anchor="w").grid(row=i, column=0, sticky="w", pady=7)
            var = tk.StringVar(value=val)
            self._vars[key] = var
            tk.Entry(f, textvariable=var, font=FONT_B, bg="#21262D",
                     fg=ACCENT, insertbackground=ACCENT, relief="flat",
                     bd=0, width=10, justify="center"
                     ).grid(row=i, column=1, padx=(16, 0), ipady=7)

        tk.Label(f,
                 text="Cell size = map resolution  (e.g. 1 cm = 0.01 m/cell)",
                 font=("Courier New", 8), fg="#6E7681", bg=BG_COLOR
                 ).grid(row=5, columnspan=2, pady=(4, 22))

        tk.Button(f, text="▶   BUILD MAP",
                  font=("Courier New", 12, "bold"),
                  fg=BG_COLOR, bg=ACCENT, activebackground="#00B894",
                  relief="flat", bd=0, padx=20, pady=11,
                  cursor="hand2", command=self._launch
                  ).grid(row=6, columnspan=2, sticky="ew")

        self.root.bind("<Return>", lambda _: self._launch())

    def _launch(self):
        try:
            w = float(self._vars["w"].get())
            h = float(self._vars["h"].get())
            c = float(self._vars["c"].get())
            if w <= 0 or h <= 0 or c <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter positive numbers.")
            return
        if w > 100 or h > 100:
            messagebox.showwarning("Large Arena",
                "Arena > 100 m may create many cells.\nConsider a larger cell size.")
        self.result = (w, h, c / 100.0)
        self.root.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# Map Editor
# ══════════════════════════════════════════════════════════════════════════════
class MapEditor:
    def __init__(self, arena_w, arena_h, resolution):
        self.arena_w    = arena_w
        self.arena_h    = arena_h
        self.resolution = resolution      # m/cell
        self.cols = max(1, round(arena_w  / resolution))
        self.rows = max(1, round(arena_h / resolution))

        # Auto-fit initial zoom
        scr_w, scr_h = 1400, 860
        fit = min((scr_w - RULER_W - 60) // max(self.cols, 1),
                  (scr_h - RULER_H - 140) // max(self.rows, 1))
        self.zoom_px = max(MIN_ZOOM, min(MAX_ZOOM, fit if fit >= 2 else 4))

        self.grid     = np.zeros((self.rows, self.cols), dtype=np.uint8)
        self.rects    = {}
        self.painting = None   # 1 = draw occupied, 0 = erase
        self._hover   = None   # (r, c)

        self._build_window()

    # ── Window ────────────────────────────────────────────────────────────────
    def _build_window(self):
        self.root = tk.Tk()
        self.root.title(
            f"Arena Map Builder  ·  {self.arena_w}×{self.arena_h} m  "
            f"·  {self.cols}×{self.rows} cells  ·  res={self.resolution*100:.3g} cm")
        self.root.configure(bg=BG_COLOR)

        # ── Top toolbar ───────────────────────────────────────────────────────
        bar = tk.Frame(self.root, bg=PANEL_COLOR, pady=7)
        bar.pack(fill="x")

        tk.Label(bar, text="ARENA MAP BUILDER", font=("Courier New", 12, "bold"),
                 fg=ACCENT, bg=PANEL_COLOR).pack(side="left", padx=14)
        tk.Label(bar,
                 text=(f"  {self.arena_w}×{self.arena_h} m  ·  "
                       f"{self.cols}×{self.rows} cells  ·  "
                       f"res = {self.resolution*100:.3g} cm/cell"),
                 font=("Courier New", 8), fg="#6E7681", bg=PANEL_COLOR
                 ).pack(side="left")

        right = tk.Frame(bar, bg=PANEL_COLOR)
        right.pack(side="right", padx=14)

        def tbtn(parent, txt, cmd, color=ACCENT):
            b = tk.Button(parent, text=txt, font=FONT_B, fg=BG_COLOR, bg=color,
                          activebackground=color, relief="flat", bd=0,
                          padx=9, pady=4, cursor="hand2", command=cmd)
            b.pack(side="left", padx=3)
            return b

        tk.Label(right, text="ZOOM:", font=FONT, fg=RULER_FG,
                 bg=PANEL_COLOR).pack(side="left", padx=(0, 3))
        tbtn(right, "−", self._zoom_out, "#21262D")
        self._zoom_lbl = tk.Label(right, text=self._zoom_str(), font=FONT_B,
                                   fg=ACCENT2, bg=PANEL_COLOR, width=5)
        self._zoom_lbl.pack(side="left")
        tbtn(right, "+", self._zoom_in, "#21262D")
        tbtn(right, "FIT", self._zoom_fit, "#21262D")

        tk.Frame(right, bg="#30363D", width=1, height=22).pack(side="left", padx=8)

        tbtn(right, "BORDER", self._fill_border, "#8B949E")
        tbtn(right, "CLEAR",  self._clear_all,   "#C0392B")
        tbtn(right, "[S] SAVE MAP", self._save_map, ACCENT)

        # ── Legend ────────────────────────────────────────────────────────────
        leg = tk.Frame(self.root, bg=BG_COLOR, pady=3)
        leg.pack(fill="x", padx=10)
        for sym, col, desc in [
            ("■", OCC_COLOR,   "Occupied"),
            ("□", FREE_COLOR,  "Free"),
            ("◈", HOVER_COLOR, "Hover"),
            ("Click", ACCENT,  "Toggle"),
            ("Drag",  ACCENT,  "Paint/Erase"),
            ("Ctrl+Scroll", ACCENT2, "Zoom"),
            ("+/−", ACCENT2,   "Zoom"),
            ("S",    ACCENT,   "Save"),
        ]:
            tk.Label(leg, text=sym, font=FONT_B, fg=col,
                     bg=BG_COLOR).pack(side="left", padx=(7, 1))
            tk.Label(leg, text=desc, font=("Courier New", 8),
                     fg="#6E7681", bg=BG_COLOR).pack(side="left", padx=(0, 7))

        # ── Canvas area with rulers ───────────────────────────────────────────
        cf = tk.Frame(self.root, bg=BG_COLOR)
        cf.pack(fill="both", expand=True, padx=8, pady=4)
        self._cf = cf

        # Corner spacer
        tk.Frame(cf, width=RULER_W, height=RULER_H,
                 bg=RULER_BG).grid(row=0, column=0, sticky="nw")

        # X ruler (top)
        self.ruler_x = tk.Canvas(cf, height=RULER_H, bg=RULER_BG,
                                  highlightthickness=0)
        self.ruler_x.grid(row=0, column=1, sticky="ew")

        # Y ruler (left)
        self.ruler_y = tk.Canvas(cf, width=RULER_W, bg=RULER_BG,
                                  highlightthickness=0)
        self.ruler_y.grid(row=1, column=0, sticky="ns")

        # Main grid canvas
        self.canvas = tk.Canvas(cf, bg=FREE_COLOR, highlightthickness=2,
                                 highlightbackground=ACCENT, cursor="crosshair")
        self.canvas.grid(row=1, column=1, sticky="nsew")

        cf.grid_rowconfigure(1, weight=1)
        cf.grid_columnconfigure(1, weight=1)

        # Scrollbars
        hbar = tk.Scrollbar(cf, orient="horizontal",
                             bg=PANEL_COLOR, troughcolor=BG_COLOR)
        vbar = tk.Scrollbar(cf, orient="vertical",
                             bg=PANEL_COLOR, troughcolor=BG_COLOR)
        hbar.grid(row=2, column=1, sticky="ew")
        vbar.grid(row=1, column=2, sticky="ns")

        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.configure(command=self._hscroll)
        vbar.configure(command=self._vscroll)

        # ── Status bar ────────────────────────────────────────────────────────
        self.status = tk.StringVar(
            value="Hover over a cell to see coordinates  ·  "
                  "Click to toggle  ·  Ctrl+Scroll to zoom")
        tk.Label(self.root, textvariable=self.status, font=FONT,
                 fg=RULER_FG, bg=PANEL_COLOR, anchor="w", pady=5, padx=10
                 ).pack(fill="x")

        # ── Key / mouse bindings ──────────────────────────────────────────────
        self.canvas.bind("<ButtonPress-1>",    self._on_press)
        self.canvas.bind("<B1-Motion>",        self._on_drag)
        self.canvas.bind("<ButtonRelease-1>",  self._on_release)
        self.canvas.bind("<Motion>",           self._on_motion)
        self.canvas.bind("<Leave>",            self._on_leave)
        # Zoom via Ctrl+scroll (Windows/macOS)
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_scroll_win)
        # Zoom via Ctrl+scroll (Linux X11 Button4/5)
        self.canvas.bind("<Control-Button-4>", lambda e: self._zoom_at(e, +1))
        self.canvas.bind("<Control-Button-5>", lambda e: self._zoom_at(e, -1))

        self.root.bind("<plus>",   lambda _: self._zoom_in())
        self.root.bind("<equal>",  lambda _: self._zoom_in())
        self.root.bind("<minus>",  lambda _: self._zoom_out())
        self.root.bind("<s>",      lambda _: self._save_map())
        self.root.bind("<S>",      lambda _: self._save_map())
        self.root.bind("<Escape>", lambda _: self.root.destroy())

        # ── Initial render ────────────────────────────────────────────────────
        self.root.update_idletasks()
        self._apply_zoom()
        self._center_window()
        # Center the grid in the viewport after everything is laid out
        self.root.after(50, self._center_grid)
        self.root.mainloop()

    def _center_window(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        ww = self.root.winfo_width()
        wh = self.root.winfo_height()
        self.root.geometry(f"+{max(0,(sw-ww)//2)}+{max(0,(sh-wh)//2)}")

    def _center_grid(self):
        """Scroll canvas so the grid is visually centred in the viewport."""
        self.canvas.update_idletasks()
        grid_w = self.cols * self.zoom_px
        grid_h = self.rows * self.zoom_px
        view_w = self.canvas.winfo_width()
        view_h = self.canvas.winfo_height()

        # We expand the scrollregion with symmetric padding so the grid
        # draws in the middle.  Grid content still starts at canvas (0,0).
        pad_x = max(0, (view_w - grid_w) // 2)
        pad_y = max(0, (view_h - grid_h) // 2)

        # scrollregion: left=-pad_x so that xview_moveto(0) shows the grid centred
        sr_x1 = -pad_x;  sr_x2 = grid_w + pad_x
        sr_y1 = -pad_y;  sr_y2 = grid_h + pad_y

        self.canvas.configure(scrollregion=(sr_x1, sr_y1, sr_x2, sr_y2))
        self.ruler_x.configure(scrollregion=(sr_x1, 0, sr_x2, RULER_H))
        self.ruler_y.configure(scrollregion=(0, sr_y1, RULER_W, sr_y2))

        # Move view so the grid (which lives at 0,0 in canvas space) is centred
        sr_w = sr_x2 - sr_x1
        sr_h = sr_y2 - sr_y1
        xfrac = pad_x / sr_w if sr_w > 0 else 0.0
        yfrac = pad_y / sr_h if sr_h > 0 else 0.0

        self.canvas.xview_moveto(xfrac)
        self.canvas.yview_moveto(yfrac)
        self.ruler_x.xview_moveto(xfrac)
        self.ruler_y.yview_moveto(yfrac)

    # ── Scroll sync ───────────────────────────────────────────────────────────
    def _hscroll(self, *args):
        self.canvas.xview(*args)
        self.ruler_x.xview(*args)

    def _vscroll(self, *args):
        self.canvas.yview(*args)
        self.ruler_y.yview(*args)

    # ── Zoom ──────────────────────────────────────────────────────────────────
    def _zoom_str(self):
        return f"{self.zoom_px}px"

    def _zoom_in(self, pivot_cx=None, pivot_cy=None):
        old = self.zoom_px
        new = min(MAX_ZOOM, int(old * ZOOM_STEP + 0.5))
        if new == old:
            new = min(MAX_ZOOM, old + 1)
        self.zoom_px = new
        self._apply_zoom(pivot_cx, pivot_cy, old)

    def _zoom_out(self, pivot_cx=None, pivot_cy=None):
        old = self.zoom_px
        new = max(MIN_ZOOM, int(old / ZOOM_STEP))
        if new == old:
            new = max(MIN_ZOOM, old - 1)
        self.zoom_px = new
        self._apply_zoom(pivot_cx, pivot_cy, old)

    def _zoom_fit(self):
        self._cf.update_idletasks()
        cw = self._cf.winfo_width()  - RULER_W  - 30
        ch = self._cf.winfo_height() - RULER_H  - 30
        if cw > 10 and ch > 10:
            fit = min(cw // max(self.cols, 1), ch // max(self.rows, 1))
            self.zoom_px = max(MIN_ZOOM, min(MAX_ZOOM, fit))
        self._apply_zoom()
        self.canvas.after(20, self._center_grid)

    def _on_ctrl_scroll_win(self, event):
        if event.delta > 0:
            self._zoom_at(event, +1)
        else:
            self._zoom_at(event, -1)

    def _zoom_at(self, event, direction):
        """Zoom keeping the cell under the cursor in place."""
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        if direction > 0:
            self._zoom_in(cx, cy)
        else:
            self._zoom_out(cx, cy)

    def _apply_zoom(self, pivot_cx=None, pivot_cy=None, old_zoom=None):
        """Rebuild the grid canvas at the current zoom level.
        If pivot_cx/cy provided, try to keep that canvas point under cursor."""
        z  = self.zoom_px
        cw = self.cols * z
        ch = self.rows * z

        # Update scroll regions
        self.canvas.configure(scrollregion=(0, 0, cw, ch))
        self.ruler_x.configure(scrollregion=(0, 0, cw, RULER_H))
        self.ruler_y.configure(scrollregion=(0, 0, RULER_W, ch))

        self._zoom_lbl.configure(text=self._zoom_str())

        # Re-center scroll around pivot
        if pivot_cx is not None and old_zoom and old_zoom != z:
            # pivot in world fraction
            fx = pivot_cx / (self.cols * old_zoom)
            fy = pivot_cy / (self.rows * old_zoom)
            # after zoom the pivot should be at the same screen position
            # → adjust xview so that fraction stays the same
            # canvas width on screen
            sw = self.canvas.winfo_width()
            sh = self.canvas.winfo_height()
            new_cx = fx * cw
            new_cy = fy * ch
            # fraction of scrollregion to put at left edge
            xfrac = max(0.0, min(1.0, (new_cx - sw / 2) / cw))
            yfrac = max(0.0, min(1.0, (new_cy - sh / 2) / ch))
            self.canvas.xview_moveto(xfrac)
            self.canvas.yview_moveto(yfrac)
            self.ruler_x.xview_moveto(xfrac)
            self.ruler_y.yview_moveto(yfrac)

        self._redraw_grid()
        self._draw_rulers()

        # If no pivot point provided, centre the grid in the viewport
        if pivot_cx is None:
            self.canvas.after(10, self._center_grid)

    # ── Grid redraw ───────────────────────────────────────────────────────────
    def _redraw_grid(self):
        self.canvas.delete("all")
        self.rects = {}
        z = self.zoom_px
        outline = GRID_COLOR if z >= 5 else FREE_COLOR  # hide grid lines when tiny
        # Origin (0,0) = bottom-left (ROS2 Humble default).
        # grid row 0 maps to canvas BOTTOM: canvas_r = (rows-1-r)*z
        for r in range(self.rows):
            canvas_r = self.rows - 1 - r        # flip: row 0 drawn at canvas bottom
            y0 = canvas_r * z
            for c in range(self.cols):
                x0 = c * z
                color = OCC_COLOR if self.grid[r, c] else FREE_COLOR
                rect = self.canvas.create_rectangle(
                    x0, y0, x0 + z, y0 + z,
                    fill=color, outline=outline, width=1)
                self.rects[(r, c)] = rect

        self._draw_origin_marker()

    def _draw_origin_marker(self):
        """Red crosshair at bottom-left  (0,0) — ROS2 Humble convention."""
        z   = self.zoom_px
        sz  = max(8, min(z, 20))
        bot = self.rows * z          # canvas y of the bottom edge
        self.canvas.create_line(0, bot, sz, bot,
                                 fill=ORIGIN_COLOR, width=2, tags="origin")
        self.canvas.create_line(0, bot, 0, bot - sz,
                                 fill=ORIGIN_COLOR, width=2, tags="origin")
        if z >= 12:
            self.canvas.create_text(sz + 2, bot - 3, text="(0,0)",
                                     font=("Courier New", 7), fill=ORIGIN_COLOR,
                                     anchor="w", tags="origin")

    # ── Rulers ────────────────────────────────────────────────────────────────
    def _draw_rulers(self):
        self._draw_ruler_x()
        self._draw_ruler_y()

    def _nice_tick_m(self):
        """Tick interval in metres so ticks are ~50–100 px apart."""
        target_px = 60
        target_m  = (target_px / self.zoom_px) * self.resolution
        nices = [0.001, 0.002, 0.005,
                 0.01,  0.02,  0.05,
                 0.1,   0.2,   0.5,
                 1.0,   2.0,   5.0,
                 10.0,  20.0,  50.0]
        for n in nices:
            if n >= target_m:
                return n
        return nices[-1]

    def _draw_ruler_x(self):
        self.ruler_x.delete("all")
        z     = self.zoom_px
        cw    = self.cols * z
        tick  = self._nice_tick_m()
        step  = (tick / self.resolution) * z   # pixels per tick
        x     = 0.0
        m     = 0.0
        while x <= cw + 0.5:
            xi = int(round(x))
            self.ruler_x.create_line(xi, RULER_H - 7, xi, RULER_H,
                                      fill=RULER_TICK, width=1)
            lbl = f"{m:.4g}"
            self.ruler_x.create_text(xi + 2, RULER_H // 2 - 1, text=lbl,
                                      font=("Courier New", 7), fill=RULER_FG,
                                      anchor="w")
            x += step
            m += tick
        self.ruler_x.create_text(cw - 2, 3, text="X (m)",
                                  font=("Courier New", 7, "bold"),
                                  fill=ACCENT2, anchor="e")

    def _draw_ruler_y(self):
        # Y axis: origin at bottom-left, increases upward.
        # Canvas y=ch (bottom) = 0 m,  canvas y=0 (top) = arena_h m.
        self.ruler_y.delete("all")
        z     = self.zoom_px
        ch    = self.rows * z
        tick  = self._nice_tick_m()
        step  = (tick / self.resolution) * z
        y_m   = 0.0
        while y_m <= self.arena_h + 1e-9:
            canvas_y = int(round(ch - (y_m / self.resolution) * z))
            self.ruler_y.create_line(RULER_W - 7, canvas_y, RULER_W, canvas_y,
                                      fill=RULER_TICK, width=1)
            lbl = f"{y_m:.4g}"
            self.ruler_y.create_text(RULER_W - 9, canvas_y - 1, text=lbl,
                                      font=("Courier New", 7), fill=RULER_FG,
                                      anchor="e")
            y_m += tick
        self.ruler_y.create_text(RULER_W // 2, 6, text="Y (m)",
                                  font=("Courier New", 7, "bold"),
                                  fill=ACCENT2, anchor="n")

    # ── Canvas coords ─────────────────────────────────────────────────────────
    def _canvas_pos(self, event):
        return self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def _cell_at(self, cx, cy):
        # Canvas row 0 = top of screen = highest grid row (rows-1).
        # Grid row 0 = bottom of canvas (origin bottom-left).
        c        = int(cx // self.zoom_px)
        canvas_r = int(cy // self.zoom_px)
        r        = self.rows - 1 - canvas_r   # flip back to grid space
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return r, c
        return None

    # ── Cell helpers ──────────────────────────────────────────────────────────
    def _base_color(self, r, c):
        return OCC_COLOR if self.grid[r, c] else FREE_COLOR

    def _refresh(self, r, c):
        self.canvas.itemconfig(self.rects[(r, c)], fill=self._base_color(r, c))

    def _toggle(self, r, c):
        new = 1 - self.grid[r, c]
        self.grid[r, c] = new
        self.canvas.itemconfig(self.rects[(r, c)],
                                fill=OCC_COLOR if new else FREE_COLOR)
        return new

    def _paint(self, r, c, val):
        if self.grid[r, c] != val:
            self.grid[r, c] = val
            self.canvas.itemconfig(self.rects[(r, c)],
                                    fill=OCC_COLOR if val else FREE_COLOR)

    # ── Mouse events ──────────────────────────────────────────────────────────
    def _on_press(self, event):
        cx, cy = self._canvas_pos(event)
        cell = self._cell_at(cx, cy)
        if cell:
            r, c = cell
            self.painting = self._toggle(r, c)
            self._update_status(r, c)

    def _on_drag(self, event):
        if self.painting is None:
            return
        cx, cy = self._canvas_pos(event)
        cell = self._cell_at(cx, cy)
        if cell:
            r, c = cell
            self._paint(r, c, self.painting)
            self._update_status(r, c)

    def _on_release(self, event):
        self.painting = None

    def _on_motion(self, event):
        cx, cy = self._canvas_pos(event)
        cell = self._cell_at(cx, cy)

        # Clear previous hover highlight
        if self._hover and self._hover != cell:
            pr, pc = self._hover
            self._refresh(pr, pc)

        if cell:
            r, c = cell
            self._hover = (r, c)
            if self.painting is None:
                self.canvas.itemconfig(self.rects[(r, c)], fill=HOVER_COLOR)
            self._update_status(r, c)
        else:
            self._hover = None
            occ = int(self.grid.sum())
            self.status.set(
                f"  Cells: {self.cols}×{self.rows}  ·  "
                f"Occupied: {occ}   Free: {self.rows*self.cols - occ}  ·  "
                f"Zoom: {self._zoom_str()}  ·  Ctrl+Scroll to zoom  ·  S to save")

    def _on_leave(self, event):
        if self._hover:
            pr, pc = self._hover
            self._refresh(pr, pc)
            self._hover = None

    def _update_status(self, r, c):
        # Origin (0,0) = bottom-left (ROS2 Humble).
        # X grows right, Y grows up.  r=0 → Y=0 (bottom), r=rows-1 → Y=arena_h (top).
        x_m = c * self.resolution
        y_m = r * self.resolution
        occ  = int(self.grid.sum())
        free = self.rows * self.cols - occ
        state = "OCCUPIED" if self.grid[r, c] else "free"
        self.status.set(
            f"  Cell [ col={c:>4}, row={r:>4} ]"
            f"    ╎  X = {x_m:>7.4f} m"
            f"    Y = {y_m:>7.4f} m"
            f"    ╎  {state:<10}"
            f"  ╎  Occ: {occ}   Free: {free}"
            f"   ╎  Zoom: {self._zoom_str()}")

    # ── Tools ─────────────────────────────────────────────────────────────────
    def _clear_all(self):
        if messagebox.askyesno("Clear All", "Reset entire map to free space?"):
            self.grid[:] = 0
            for rect in self.rects.values():
                self.canvas.itemconfig(rect, fill=FREE_COLOR)
            self._draw_origin_marker()
            self.status.set("Map cleared.")

    def _fill_border(self):
        self.grid[0, :]  = 1
        self.grid[-1, :] = 1
        self.grid[:, 0]  = 1
        self.grid[:, -1] = 1
        for c in range(self.cols):
            self.canvas.itemconfig(self.rects[(0, c)], fill=OCC_COLOR)
            self.canvas.itemconfig(self.rects[(self.rows-1, c)], fill=OCC_COLOR)
        for r in range(self.rows):
            self.canvas.itemconfig(self.rects[(r, 0)], fill=OCC_COLOR)
            self.canvas.itemconfig(self.rects[(r, self.cols-1)], fill=OCC_COLOR)
        self.status.set("Border walls added.")

    # ── Save ──────────────────────────────────────────────────────────────────
    def _save_map(self):
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            title="Save ROS2 Map",
            defaultextension=".pgm",
            initialfile=f"arena_map_{ts}",
            filetypes=[("PGM Map", "*.pgm"), ("All files", "*.*")])
        if not path:
            return

        base      = os.path.splitext(path)[0]
        pgm_path  = base + ".pgm"
        yaml_path = base + ".yaml"

        # PGM: ROS2 convention  254=free  0=occupied
        # Grid row 0 = bottom of arena (origin bottom-left, ROS2 Humble default).
        # map_server reads PGM row 0 as the TOP of the image (highest Y in world).
        # So we flip vertically: PGM row 0 ← grid row (rows-1), PGM last ← grid row 0.
        pgm_data = np.where(self.grid == 1, 0, 254).astype(np.uint8)
        pgm_out  = np.flipud(pgm_data)

        with open(pgm_path, "wb") as f:
            f.write(f"P5\n{self.cols} {self.rows}\n255\n".encode())
            f.write(pgm_out.tobytes())

        # YAML origin = bottom-left corner of the map in world coords (ROS2 default).
        # origin (0,0,0) means the PGM bottom-left pixel = world (0,0).
        meta = {
            "image":           os.path.basename(pgm_path),
            "resolution":      float(self.resolution),
            "origin":          [0.0, 0.0, 0.0],
            "negate":          0,
            "occupied_thresh": 0.65,
            "free_thresh":     0.196,
            "mode":            "trinary",
        }
        with open(yaml_path, "w") as f:
            yaml.dump(meta, f, default_flow_style=False, sort_keys=False)

        occ  = int(self.grid.sum())
        free = self.rows * self.cols - occ
        messagebox.showinfo("Saved ✓",
            f"Map saved!\n\n"
            f"  PGM  :  {pgm_path}\n"
            f"  YAML :  {yaml_path}\n\n"
            f"  Grid size   :  {self.cols} × {self.rows} cells\n"
            f"  Resolution  :  {self.resolution*100:.3g} cm/cell\n"
            f"  Free cells  :  {free}\n"
            f"  Occupied    :  {occ}\n\n"
            f"Load in ROS2:\n"
            f"  ros2 run nav2_map_server map_server \\\n"
            f"    --ros-args -p yaml_filename:={yaml_path}")
        self.status.set(
            f"Saved → {os.path.basename(pgm_path)}  +  {os.path.basename(yaml_path)}")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════
def main():
    setup = SetupWindow()
    if setup.result is None:
        return
    MapEditor(*setup.result)


if __name__ == "__main__":
    main()