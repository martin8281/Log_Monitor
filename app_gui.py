import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import logging
from datetime import datetime

import file_monitor
import usb_monitor

# ─────────────────────────────────────────────────────────────────────────────
#  DARK MODE PALETTE  — deep space dark, electric cyan accent
# ─────────────────────────────────────────────────────────────────────────────
BG          = "#080C14"   # deepest background
SURFACE     = "#0F1624"   # card / panel surface
SURFACE2    = "#182030"   # raised element inside a card
SURFACE3    = "#1E2A40"   # hover state / subtle wells
BORDER      = "#253148"   # border / dividers
ACCENT      = "#00C6FF"   # electric cyan — primary action
ACCENT_DK   = "#0099CC"   # darker cyan on hover
ACCENT_GLOW = "#00C6FF22" # translucent glow wash

TEXT        = "#E8EDF5"   # primary text
TEXT2       = "#7E8BA5"   # secondary / muted text
TEXT3       = "#4A566E"   # disabled / placeholder text

SUCCESS     = "#00E676"
WARNING     = "#FFB300"
DANGER      = "#FF3860"
DANGER_DK   = "#CC2244"
INFO        = "#448AFF"
MODIFY      = "#AA77FF"

FONT_H1     = ("Segoe UI", 16, "bold")
FONT_H2     = ("Segoe UI", 11, "bold")
FONT_BODY   = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 9)
FONT_BTN    = ("Segoe UI", 10, "bold")
FONT_MONO   = ("Consolas", 9)


# ─────────────────────────────────────────────────────────────────────────────
#  Canvas-based rounded primitives
# ─────────────────────────────────────────────────────────────────────────────
def _rr_pts(x1, y1, x2, y2, r):
    r = max(0, min(r, (x2-x1)/2, (y2-y1)/2))
    return [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
            x2,y2-r, x2,y2, x2-r,y2, x1+r,y2,
            x1,y2, x1,y2-r, x1,y1+r, x1,y1]

def rr(canvas, x1, y1, x2, y2, radius, **kw):
    return canvas.create_polygon(_rr_pts(x1,y1,x2,y2,radius),
                                  smooth=True, splinesteps=32, **kw)


class RoundBtn(tk.Canvas):
    """Pill-shaped button drawn on Canvas."""
    def __init__(self, parent, text="", command=None,
                 bg=ACCENT, hover=None, fg=BG,
                 radius=20, w=140, h=40, font=None, outer=BG):
        super().__init__(parent, width=w, height=h,
                         bg=outer, highlightthickness=0, bd=0, cursor="hand2")
        self.cmd = command
        self._txt = text
        self._bg  = bg
        self._hov = hover or bg
        self._fg  = fg
        self._r   = radius
        self._fnt = font or FONT_BTN
        self._on  = False
        self._ena = True
        self.bind("<Configure>",  lambda e: self._draw())
        self.bind("<Enter>",      lambda e: self._hover(True))
        self.bind("<Leave>",      lambda e: self._hover(False))
        self.bind("<Button-1>",   lambda e: self._click())
        self.after(10, self._draw)

    def _hover(self, v):
        self._on = v; self._draw()

    def _click(self):
        if self._ena and self.cmd: self.cmd()

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(),  2)
        h = max(self.winfo_height(), 2)
        if not self._ena:
            col = SURFACE3
        elif self._on:
            col = self._hov
        else:
            col = self._bg
        rr(self, 1, 1, w-1, h-1, self._r, fill=col, outline=col)
        self.create_text(w/2, h/2, text=self._txt, fill=self._fg, font=self._fnt)

    def set_text(self, t):  self._txt = t; self._draw()
    def set_colors(self, bg=None, hov=None, fg=None):
        if bg:  self._bg  = bg
        if hov: self._hov = hov
        if fg:  self._fg  = fg
        self._draw()
    def set_enabled(self, v):
        self._ena = v
        self.configure(cursor="hand2" if v else "arrow")
        self._draw()


class Card(tk.Frame):
    """Dark rounded card.  Pack/grid children into .body."""
    def __init__(self, parent, bg=SURFACE, outer=BG, radius=18, pad=12):
        super().__init__(parent, bg=outer)
        self._bg  = bg
        self._r   = radius
        self._pad = pad
        self._shp = None
        self.cv   = tk.Canvas(self, bg=outer, highlightthickness=0, bd=0)
        self.cv.pack(fill=tk.BOTH, expand=True)
        self.body = tk.Frame(self.cv, bg=bg)
        self._win = self.cv.create_window(pad, pad, anchor="nw", window=self.body)
        self.cv.bind("<Configure>", self._draw)

    def _draw(self, _=None):
        w = self.cv.winfo_width()
        h = self.cv.winfo_height()
        if w < 4 or h < 4: return
        if self._shp: self.cv.delete(self._shp)
        self._shp = rr(self.cv, 1, 1, w-1, h-1, self._r,
                        fill=self._bg, outline=BORDER)
        self.cv.tag_lower(self._shp)
        p = self._pad
        self.cv.coords(self._win, p, p)
        self.cv.itemconfig(self._win,
                            width=max(w-2*p, 1),
                            height=max(h-2*p, 1))


class RoundEntry(tk.Canvas):
    """Pill-shaped search entry."""
    def __init__(self, parent, var, outer=BG, radius=18, w=220, h=36, font=None):
        super().__init__(parent, width=w, height=h,
                         bg=outer, highlightthickness=0, bd=0)
        self._shp = None
        self.entry = tk.Entry(self, textvariable=var,
                               bg=SURFACE2, fg=TEXT, insertbackground=TEXT,
                               relief=tk.FLAT, bd=0, highlightthickness=0,
                               font=font or FONT_BODY)
        self._win = self.create_window(0, 0, anchor="w", window=self.entry)
        self.bind("<Configure>", self._draw)

    def _draw(self, _=None):
        w = max(self.winfo_width(),  2)
        h = max(self.winfo_height(), 2)
        if self._shp: self.delete(self._shp)
        self._shp = rr(self, 1, 1, w-1, h-1, 18,
                        fill=SURFACE2, outline=BORDER)
        self.tag_lower(self._shp)
        ins = max(18 * 0.9, 12)
        self.coords(self._win, ins, h/2)
        self.itemconfig(self._win, width=max(w - 2*ins, 10))


class Badge(tk.Canvas):
    """Rounded status pill."""
    def __init__(self, parent, text="", fg=TEXT, bg=SURFACE,
                 outer=BG, w=200, h=36, font=None):
        super().__init__(parent, width=w, height=h,
                         bg=outer, highlightthickness=0, bd=0)
        self._txt = text
        self._fg  = fg
        self._bg  = bg
        self._fnt = font or FONT_BTN
        self.bind("<Configure>", lambda e: self._draw())
        self.after(10, self._draw)

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(),  2)
        h = max(self.winfo_height(), 2)
        rr(self, 1, 1, w-1, h-1, 18, fill=self._bg, outline=BORDER)
        self.create_text(16, h/2, text=self._txt,
                          fill=self._fg, font=self._fnt, anchor="w")

    def set(self, text, fg=None, bg=None):
        self._txt = text
        if fg: self._fg = fg
        if bg: self._bg = bg
        self._draw()


class Tip:
    def __init__(self, w, text):
        self.w = w; self.text = text; self.tip = None
        w.bind("<Enter>", self.show, add="+")
        w.bind("<Leave>", self.hide, add="+")

    def show(self, _=None):
        if self.tip: return
        x = self.w.winfo_rootx() + 6
        y = self.w.winfo_rooty() + self.w.winfo_height() + 6
        self.tip = tk.Toplevel(self.w)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg=SURFACE3, fg=TEXT,
                  font=FONT_SMALL, padx=10, pady=5,
                  relief=tk.FLAT, bd=0).pack()

    def hide(self, _=None):
        if self.tip: self.tip.destroy(); self.tip = None


# ─────────────────────────────────────────────────────────────────────────────
#  Thin glowing horizontal divider
# ─────────────────────────────────────────────────────────────────────────────
def glow_sep(parent):
    c = tk.Canvas(parent, height=2, bg=BG, highlightthickness=0, bd=0)
    c.pack(fill=tk.X, pady=(0, 14))
    def _draw(_=None):
        w = c.winfo_width()
        if w < 2: return
        c.delete("all")
        c.create_line(0, 1, w, 1, fill=ACCENT, width=1)
    c.bind("<Configure>", _draw)
    return c


# ─────────────────────────────────────────────────────────────────────────────
#  Main Application
# ─────────────────────────────────────────────────────────────────────────────
class FileActivityApp:
    def __init__(self, root):
        self.root = root
        self.root.title("File & USB Activity Monitor")
        self.root.geometry("1200x700")
        self.root.minsize(960, 560)
        self.root.configure(bg=BG)

        self.is_monitoring = False
        self.activities    = []

        self._style()
        self._layout()
        self._shortcuts()
        self.load_folders()

        try:
            usb_monitor.start_usb_monitoring(self.schedule_update,
                                              self.start_usb_drive_monitor)
        except Exception as e:
            logging.error(f"USB monitor start failed: {e}", exc_info=True)
            messagebox.showerror("USB Monitor Error",
                                  f"Failed to start USB device monitoring:\n{e}")

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ── ttk style ────────────────────────────────────────────────────────────
    def _style(self):
        s = ttk.Style(self.root)
        try: s.theme_use("clam")
        except: pass

        s.configure("TPanedwindow",       background=BG)
        s.configure("Treeview",
                    background=SURFACE, fieldbackground=SURFACE,
                    foreground=TEXT, font=FONT_MONO, rowheight=26, borderwidth=0)
        s.configure("Treeview.Heading",
                    background=SURFACE2, foreground=TEXT2,
                    font=FONT_H2, relief="flat")
        s.map("Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", BG)])
        s.map("Treeview.Heading",
              background=[("active", SURFACE2)])

        s.configure("Vertical.TScrollbar",
                    background=SURFACE2, troughcolor=SURFACE,
                    bordercolor=SURFACE, arrowcolor=TEXT3, relief="flat")
        s.configure("TProgressbar",
                    background=ACCENT, troughcolor=SURFACE2,
                    bordercolor=SURFACE, lightcolor=ACCENT, darkcolor=ACCENT)

    # ── layout skeleton ───────────────────────────────────────────────────────
    def _layout(self):
        # ── header ──────────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=SURFACE, padx=20, pady=18)
        hdr.pack(side=tk.TOP, fill=tk.X)

        # left: title
        left = tk.Frame(hdr, bg=SURFACE)
        left.pack(side=tk.LEFT)
        tk.Label(left, text="  File & USB Activity Monitor",
                  bg=SURFACE, fg=TEXT, font=FONT_H1).pack(anchor=tk.W)
        tk.Label(left, text="  Real-time monitoring console",
                  bg=SURFACE, fg=TEXT2, font=FONT_SMALL).pack(anchor=tk.W, pady=(2,0))

        # right: live pill showing monitoring state
        right = tk.Frame(hdr, bg=SURFACE)
        right.pack(side=tk.RIGHT, padx=(0, 4))
        self.hdr_status = Badge(right, text="⬤  Idle", fg=TEXT3,
                                 bg=SURFACE2, outer=SURFACE, w=150, h=34)
        self.hdr_status.pack()

        # cyan accent stripe under header
        stripe = tk.Frame(self.root, bg=ACCENT, height=2)
        stripe.pack(fill=tk.X)

        # ── paned body ───────────────────────────────────────────────────────
        body = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        log_pane  = tk.Frame(body, bg=BG)
        ctrl_pane = tk.Frame(body, bg=BG, width=310)
        body.add(log_pane,  weight=3)
        body.add(ctrl_pane, weight=1)

        self._log_section(log_pane)
        self._ctrl_section(ctrl_pane)

    # ── activity log (left pane) ─────────────────────────────────────────────
    def _log_section(self, p):
        # row: title + count + search
        top = tk.Frame(p, bg=BG)
        top.pack(fill=tk.X, pady=(0, 10))

        tk.Label(top, text="Activity Log", bg=BG,
                  fg=TEXT, font=FONT_H2).pack(side=tk.LEFT)
        self.count_lbl = tk.Label(top, text="0 events",
                                   bg=BG, fg=TEXT3, font=FONT_SMALL)
        self.count_lbl.pack(side=tk.LEFT, padx=(10, 0))

        sf = tk.Frame(top, bg=BG)
        sf.pack(side=tk.RIGHT)
        self.sv = tk.StringVar()
        self.sv.trace_add("write", self._filter_changed)
        self.se = RoundEntry(sf, self.sv, w=230, h=34)
        self.se.pack(side=tk.LEFT)
        self._placeholder(self.se.entry, "Search events…")

        clr = RoundBtn(sf, text="✕", command=lambda: self.sv.set(""),
                        bg=SURFACE3, hover=BORDER,
                        fg=TEXT2, w=34, h=34, radius=17, outer=BG)
        clr.pack(side=tk.LEFT, padx=(8, 0))
        Tip(clr, "Clear search")

        # log card
        lc = Card(p, bg=SURFACE, radius=18, pad=4)
        lc.pack(fill=tk.BOTH, expand=True)

        cols = ("time", "event")
        self.tree = ttk.Treeview(lc.body, columns=cols,
                                   show="headings", selectmode="extended")
        self.tree.heading("time",  text="Time")
        self.tree.heading("event", text="Event")
        self.tree.column("time",  width=85,  anchor=tk.CENTER, stretch=False)
        self.tree.column("event", width=600, anchor=tk.W,      stretch=True)

        for tag, col in (
            ("insert",  SUCCESS), ("remove",  WARNING), ("error",   DANGER),
            ("create",  INFO),    ("modify",  MODIFY),  ("delete",  DANGER),
            ("default", TEXT),
        ):
            self.tree.tag_configure(tag, foreground=col)

        vs = ttk.Scrollbar(lc.body, orient=tk.VERTICAL,
                            command=self.tree.yview, style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._ctx_menu()

        self.prog = ttk.Progressbar(p, orient=tk.HORIZONTAL, mode="determinate")

    def _ctx_menu(self):
        m = tk.Menu(self.root, tearoff=0,
                    bg=SURFACE2, fg=TEXT,
                    activebackground=ACCENT, activeforeground=BG, bd=0)
        m.add_command(label="Copy selected", command=self._copy_rows)

        def popup(e):
            row = self.tree.identify_row(e.y)
            if row:
                if row not in self.tree.selection():
                    self.tree.selection_set(row)
                m.tk_popup(e.x_root, e.y_root)
        self.tree.bind("<Button-3>", popup)

    def _copy_rows(self):
        rows = [self.tree.item(i, "values") for i in self.tree.selection()]
        if not rows: return
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(f"{t}  {e}" for t, e in rows))

    # ── controls (right pane) ─────────────────────────────────────────────────
    def _ctrl_section(self, p):
        # ── section: Monitored Folders ───────────────────────────────────────
        tk.Label(p, text="Monitored Folders",
                  bg=BG, fg=TEXT, font=FONT_H2).pack(anchor=tk.W, pady=(0, 8))

        fc = Card(p, bg=SURFACE, radius=18, pad=4)
        fc.pack(fill=tk.X, pady=(0, 10))
        fc.cv.configure(height=180)

        fw = tk.Frame(fc.body, bg=SURFACE)
        fw.pack(fill=tk.BOTH, expand=True)
        self.fbox = tk.Listbox(
            fw, height=8, bg=SURFACE, fg=TEXT,
            selectbackground=ACCENT, selectforeground=BG,
            highlightthickness=0, relief=tk.FLAT,
            font=FONT_BODY, activestyle="none", bd=0,
        )
        fvs = ttk.Scrollbar(fw, orient=tk.VERTICAL,
                              command=self.fbox.yview, style="Vertical.TScrollbar")
        self.fbox.configure(yscrollcommand=fvs.set)
        fvs.pack(side=tk.RIGHT, fill=tk.Y)
        self.fbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.fbox.bind("<Delete>", lambda e: self.remove_folder())

        # Add / Remove buttons
        br = tk.Frame(p, bg=BG)
        br.pack(fill=tk.X, pady=(0, 16))

        add_btn = RoundBtn(br, text="+  Add", command=self.add_folder,
                            bg=SURFACE2, hover=SURFACE3, fg=TEXT,
                            w=10, h=38, radius=18, outer=BG)
        add_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        rm_btn = RoundBtn(br, text="−  Remove", command=self.remove_folder,
                           bg=SURFACE2, hover=SURFACE3, fg=TEXT,
                           w=10, h=38, radius=18, outer=BG)
        rm_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        Tip(add_btn, "Add a folder to watch")
        Tip(rm_btn,  "Remove selected folder  (Del)")

        glow_sep(p)

        # ── section: Log Actions ─────────────────────────────────────────────
        tk.Label(p, text="Log Actions",
                  bg=BG, fg=TEXT, font=FONT_H2).pack(anchor=tk.W, pady=(0, 8))

        ar = tk.Frame(p, bg=BG)
        ar.pack(fill=tk.X, pady=(0, 16))

        exp_btn = RoundBtn(ar, text="⤓  Export", command=self.export_log_gui,
                            bg=SURFACE2, hover=SURFACE3, fg=TEXT,
                            w=10, h=38, radius=18, outer=BG)
        exp_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.ref_btn = RoundBtn(ar, text="↻  Refresh", command=self.refresh_list,
                                 bg=SURFACE2, hover=SURFACE3, fg=TEXT,
                                 w=10, h=38, radius=18, outer=BG)
        self.ref_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        Tip(exp_btn,      "Export log to file  (Ctrl+E)")
        Tip(self.ref_btn, "Refresh log view  (F5)")

        glow_sep(p)

        # ── primary action button ────────────────────────────────────────────
        self.mon_btn = RoundBtn(
            p, text="▶   Start Monitoring", command=self.toggle_monitoring,
            bg=ACCENT, hover=ACCENT_DK, fg=BG,
            w=10, h=50, radius=25,
            font=("Segoe UI", 11, "bold"), outer=BG,
        )
        self.mon_btn.pack(fill=tk.X, pady=(0, 10))

        # status badge
        self.status = Badge(p, text="⬤  Stopped",
                             fg=DANGER, bg=SURFACE, outer=BG, w=10, h=38)
        self.status.pack(fill=tk.X, pady=(0, 14))

        tk.Label(p,
                  text="Insert a USB drive — it will be\nmonitored automatically.",
                  bg=BG, fg=TEXT3, font=FONT_SMALL,
                  justify=tk.LEFT).pack(anchor=tk.W)

    # ── keyboard shortcuts ─────────────────────────────────────────────────
    def _shortcuts(self):
        self.root.bind("<F5>",      lambda e: self.refresh_list())
        self.root.bind("<Control-e>", lambda e: self.export_log_gui())
        self.root.bind("<Control-E>", lambda e: self.export_log_gui())

    # ── helpers ────────────────────────────────────────────────────────────
    def _placeholder(self, entry, txt):
        entry.insert(0, txt)
        entry.configure(fg=TEXT3)
        def fi(_):
            if entry.get() == txt:
                entry.delete(0, tk.END)
                entry.configure(fg=TEXT)
        def fo(_):
            if not entry.get():
                entry.insert(0, txt)
                entry.configure(fg=TEXT3)
        entry._ph = txt
        entry.bind("<FocusIn>",  fi)
        entry.bind("<FocusOut>", fo)

    def _set_status(self, text, color):
        self.status.set(f"⬤  {text}", fg=color)
        self.hdr_status.set(f"⬤  {text}", fg=color)

    @staticmethod
    def _classify(msg):
        low = msg.lower()
        if "error" in low or "fail" in low:  return "error",  "✖"
        if "insert" in low:                   return "insert", "▸"
        if "remov"  in low and "usb" in low:  return "remove", "⏏"
        if "delet"  in low:                   return "delete", "－"
        if "creat"  in low:                   return "create", "＋"
        if "modif"  in low or "chang" in low: return "modify", "✎"
        return "default", "•"

    def _filt(self):
        t = self.sv.get().strip().lower()
        ph = getattr(self.se.entry, "_ph", "")
        return "" if not t or t == ph.lower() else t

    # ── thread-safe GUI update ──────────────────────────────────────────────
    def schedule_update(self, msg):
        if self.root.winfo_exists():
            self.root.after(0, self.update_activity_list, msg)

    def update_activity_list(self, message):
        try:
            msgs = message if isinstance(message, (list, tuple)) else [message]
            for m in msgs:
                if isinstance(m, str):
                    self.activities.append(m)
                    self._add_row(m)
            self.count_lbl.config(text=f"{len(self.activities)} events")
        except tk.TclError as e:
            if "invalid command name" not in str(e):
                logging.error(f"TclError in update: {e}", exc_info=True)
        except Exception as e:
            logging.error(f"update_activity_list error: {e}", exc_info=True)

    def _add_row(self, msg):
        q = self._filt()
        if q and q not in msg.lower(): return
        tag, icon = self._classify(msg)
        ts = datetime.now().strftime("%H:%M:%S")
        self.tree.insert("", tk.END, values=(ts, f"{icon}  {msg}"), tags=(tag,))
        self.tree.yview_moveto(1.0)

    def _filter_changed(self, *_):
        if not hasattr(self, "tree"): return
        self.tree.delete(*self.tree.get_children())
        q = self._filt()
        for m in self.activities:
            if q and q not in m.lower(): continue
            tag, icon = self._classify(m)
            self.tree.insert("", tk.END, values=("", f"{icon}  {m}"), tags=(tag,))
        self.tree.yview_moveto(1.0)

    def refresh_list(self):
        n = len(self.activities)
        if n == 0:
            self.tree.delete(*self.tree.get_children())
            messagebox.showinfo("Refresh", "Activity log is empty.")
            return

        self.ref_btn.set_enabled(False)
        self.prog.config(maximum=n, value=0)
        self.prog.pack(fill=tk.X, pady=(8, 0))
        self.root.update()

        self.tree.delete(*self.tree.get_children())
        q = self._filt()
        try:
            for i, m in enumerate(self.activities):
                if not self.root.winfo_exists(): break
                if not q or q in m.lower():
                    tag, icon = self._classify(m)
                    self.tree.insert("", tk.END, values=("", f"{icon}  {m}"), tags=(tag,))
                self.prog.config(value=i+1)
                if (i+1) % 100 == 0 or (i+1) == n:
                    self.root.update_idletasks()
        except Exception as e:
            messagebox.showerror("Error", f"Refresh failed:\n{e}")
        finally:
            if self.root.winfo_exists():
                self.prog.pack_forget()
                self.ref_btn.set_enabled(True)
                messagebox.showinfo("Refresh", f"Refreshed {n} events.")
                self.tree.yview_moveto(1.0)

    # ── folder management ──────────────────────────────────────────────────
    def add_folder(self):
        folder = filedialog.askdirectory(title="Select Folder to Monitor")
        if not folder: return
        if file_monitor.add_monitored_folder(folder):
            self.fbox.insert(tk.END, folder)
            self._save_folders()
            messagebox.showinfo("Added", f"Now monitoring:\n{folder}")
            if self.is_monitoring: self.restart_monitoring()
        else:
            if folder in file_monitor.get_monitored_folders():
                messagebox.showwarning("Add Folder", "Already monitoring that folder.")
            else:
                messagebox.showerror("Add Folder", "Failed to add folder.")

    def remove_folder(self):
        sel = self.fbox.curselection()
        if not sel:
            messagebox.showwarning("Remove", "Select a folder first."); return
        idx = sel[0]
        folder = self.fbox.get(idx)
        if not messagebox.askyesno("Confirm", f"Stop monitoring:\n{folder}?"): return
        if file_monitor.remove_monitored_folder(folder):
            self.fbox.delete(idx)
            self._save_folders()
            messagebox.showinfo("Removed", f"Stopped monitoring:\n{folder}")
            if self.is_monitoring: self.restart_monitoring()
        else:
            messagebox.showerror("Error", f"Could not remove:\n{folder}")

    def toggle_monitoring(self):
        if not self.is_monitoring:
            folders = file_monitor.get_monitored_folders()
            if not folders:
                messagebox.showwarning("No Folders", "Add at least one folder first."); return
            try:
                file_monitor.start_file_monitoring(self.schedule_update)
                self.is_monitoring = True
                self.mon_btn.set_text("■   Stop Monitoring")
                self.mon_btn.set_colors(bg=DANGER, hov=DANGER_DK, fg=TEXT)
                self._set_status(f"Monitoring {len(folders)} folder(s)", SUCCESS)
            except Exception as e:
                messagebox.showerror("Error", f"Could not start monitoring:\n{e}")
                self._set_status("Error starting", DANGER)
        else:
            try:
                file_monitor.stop_file_monitoring()
                self.is_monitoring = False
                self.mon_btn.set_text("▶   Start Monitoring")
                self.mon_btn.set_colors(bg=ACCENT, hov=ACCENT_DK, fg=BG)
                self._set_status("Stopped", DANGER)
            except Exception as e:
                messagebox.showerror("Error", f"Could not stop monitoring:\n{e}")
                self._set_status("Error stopping", WARNING)

    def restart_monitoring(self):
        if not self.is_monitoring: return
        self._set_status("Restarting…", WARNING)
        self.root.update()
        try:
            file_monitor.stop_file_monitoring()
            folders = file_monitor.get_monitored_folders()
            if folders:
                file_monitor.start_file_monitoring(self.schedule_update)
                self._set_status(f"Monitoring {len(folders)} folder(s)", SUCCESS)
            else:
                self.is_monitoring = False
                self.mon_btn.set_text("▶   Start Monitoring")
                self.mon_btn.set_colors(bg=ACCENT, hov=ACCENT_DK, fg=BG)
                self._set_status("Stopped", DANGER)
        except Exception as e:
            messagebox.showerror("Restart Error", f"{e}")
            self._set_status("Error", DANGER)

    # ── export ─────────────────────────────────────────────────────────────
    def export_log_gui(self):
        if not self.activities:
            messagebox.showinfo("Export", "Nothing to export."); return
        folder = filedialog.askdirectory(title="Export log to…")
        if not folder: return
        path = os.path.join(folder, "file_usb_activity_log.txt")
        try:
            file_monitor.export_activity_log(self.activities, path)
            messagebox.showinfo("Exported",
                                 f"Saved {len(self.activities)} events to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"{e}")

    # ── persistence ────────────────────────────────────────────────────────
    def _save_folders(self, fn="monitored_folders.txt"):
        try:
            with open(fn, "w", encoding="utf-8") as f:
                f.write("\n".join(file_monitor.get_monitored_folders()))
        except Exception as e:
            logging.error(f"Save folders error: {e}")

    def load_folders(self, fn="monitored_folders.txt"):
        self.fbox.delete(0, tk.END)
        if not os.path.exists(fn): return
        try:
            with open(fn, "r", encoding="utf-8") as f:
                for line in f:
                    folder = line.strip()
                    if folder and os.path.isdir(folder):
                        if file_monitor.add_monitored_folder(folder):
                            self.fbox.insert(tk.END, folder)
        except Exception as e:
            logging.error(f"Load folders error: {e}")

    def start_usb_drive_monitor(self, drive):
        self.schedule_update(f"USB Drive detected: {drive}. Starting file monitoring.")
        try:
            file_monitor.start_usb_file_monitor(drive, self.schedule_update)
        except Exception as e:
            self.schedule_update(f"Error monitoring USB {drive}: {e}")

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Quit and stop all monitoring?"):
            try:
                if self.is_monitoring:
                    file_monitor.stop_file_monitoring()
                usb_monitor.stop_usb_monitoring()
            except Exception as e:
                logging.error(f"Shutdown error: {e}")
            finally:
                self.root.destroy()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s %(levelname)s %(message)s")
    root = tk.Tk()
    app = FileActivityApp(root)
    root.mainloop()
