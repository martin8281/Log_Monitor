import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import logging
from datetime import datetime

# Assuming other modules are in the same directory or PYTHONPATH
import file_monitor
import usb_monitor
# import event_log_monitor # Import if you add functionality to call it

# ----------------------------------------------------------------------------
# Design tokens — a small "security console" palette: dark slate background,
# a single teal accent for primary actions, and semantic colors (green /
# amber / red) that double as the activity-log color coding.
# ----------------------------------------------------------------------------
COLOR_BG        = "#0F1419"
COLOR_PANEL     = "#161B22"
COLOR_PANEL_ALT = "#1C232C"
COLOR_BORDER    = "#2A313C"
COLOR_TEXT      = "#E6EDF3"
COLOR_TEXT_DIM  = "#8B949E"
COLOR_ACCENT    = "#2DD4BF"
COLOR_ACCENT_HV = "#25C9B5"
COLOR_SUCCESS   = "#3FB950"
COLOR_WARNING   = "#D29922"
COLOR_DANGER    = "#F85149"
COLOR_DANGER_HV = "#FF6B63"
COLOR_INFO      = "#58A6FF"
COLOR_MODIFY    = "#C9A6FF"

FONT_TITLE    = ("Segoe UI", 15, "bold")
FONT_SUBTITLE = ("Segoe UI", 9)
FONT_SECTION  = ("Segoe UI", 10, "bold")
FONT_BASE     = ("Segoe UI", 10)
FONT_SMALL    = ("Segoe UI", 9)
FONT_BUTTON   = ("Segoe UI", 10, "bold")
FONT_MONO     = ("Consolas", 10)
FONT_MONO_SM  = ("Consolas", 9)


class ToolTip:
    """Lightweight hover tooltip for any widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 6
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.tip, text=self.text, bg=COLOR_PANEL_ALT, fg=COLOR_TEXT,
            font=FONT_SMALL, padx=8, pady=4, relief=tk.SOLID, borderwidth=1,
        ).pack()

    def hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class FileActivityApp:
    def __init__(self, root):
        self.root = root
        self.root.title("File & USB Activity Monitor")
        self.root.geometry("1200x680")
        self.root.minsize(940, 560)
        self.root.configure(bg=COLOR_BG)

        self.is_monitoring = False
        self.activities = []  # Internal log data store for the GUI (unchanged contract)

        self._build_style()
        self._build_layout()
        self._bind_shortcuts()

        # --- Initialization ---
        self.load_folders()  # Load saved folders into listbox and file_monitor module

        # Start USB *device* detection immediately.
        try:
            usb_monitor.start_usb_monitoring(self.schedule_update, self.start_usb_drive_monitor)
            logging.info("USB device monitoring initiated.")
        except Exception as e:
            logging.error(f"Failed to start USB device monitoring: {e}", exc_info=True)
            messagebox.showerror("USB Monitor Error", f"Failed to start USB device monitoring:\n{e}")

        # Graceful shutdown handling
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ------------------------------------------------------------------ #
    # Style / theme setup
    # ------------------------------------------------------------------ #
    def _build_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass  # fall back to whatever default theme is available

        style.configure("TFrame", background=COLOR_BG)
        style.configure("Panel.TFrame", background=COLOR_PANEL)
        style.configure("TPanedwindow", background=COLOR_BG)
        style.configure("TSeparator", background=COLOR_BORDER)

        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=FONT_BASE)
        style.configure("Panel.TLabel", background=COLOR_PANEL, foreground=COLOR_TEXT, font=FONT_BASE)
        style.configure("Title.TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=FONT_TITLE)
        style.configure("Subtitle.TLabel", background=COLOR_BG, foreground=COLOR_TEXT_DIM, font=FONT_SUBTITLE)
        style.configure("Section.TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=FONT_SECTION)
        style.configure("Dim.TLabel", background=COLOR_BG, foreground=COLOR_TEXT_DIM, font=FONT_SMALL)

        style.configure(
            "Accent.TButton", background=COLOR_ACCENT, foreground="#04201C",
            font=FONT_BUTTON, padding=(14, 12), borderwidth=0, relief="flat",
        )
        style.map("Accent.TButton",
                  background=[("active", COLOR_ACCENT_HV), ("disabled", COLOR_BORDER)],
                  foreground=[("disabled", COLOR_TEXT_DIM)])

        style.configure(
            "Danger.TButton", background=COLOR_DANGER, foreground="#2B0B0A",
            font=FONT_BUTTON, padding=(14, 12), borderwidth=0, relief="flat",
        )
        style.map("Danger.TButton", background=[("active", COLOR_DANGER_HV)])

        style.configure(
            "Secondary.TButton", background=COLOR_PANEL_ALT, foreground=COLOR_TEXT,
            font=FONT_SMALL, padding=(10, 8), borderwidth=1, relief="flat",
        )
        style.map("Secondary.TButton",
                  background=[("active", COLOR_BORDER)],
                  foreground=[("disabled", COLOR_TEXT_DIM)])

        style.configure(
            "TEntry", fieldbackground=COLOR_PANEL_ALT, foreground=COLOR_TEXT,
            bordercolor=COLOR_BORDER, lightcolor=COLOR_BORDER, darkcolor=COLOR_BORDER,
            insertcolor=COLOR_TEXT, padding=6,
        )

        style.configure(
            "Treeview", background=COLOR_PANEL, fieldbackground=COLOR_PANEL,
            foreground=COLOR_TEXT, font=FONT_MONO_SM, rowheight=24, borderwidth=0,
        )
        style.configure(
            "Treeview.Heading", background=COLOR_PANEL_ALT, foreground=COLOR_TEXT_DIM,
            font=FONT_SECTION, relief="flat",
        )
        style.map("Treeview", background=[("selected", COLOR_ACCENT)],
                  foreground=[("selected", "#04201C")])
        style.map("Treeview.Heading", background=[("active", COLOR_PANEL_ALT)])

        style.configure(
            "TScrollbar", background=COLOR_PANEL_ALT, troughcolor=COLOR_BG,
            bordercolor=COLOR_BG, arrowcolor=COLOR_TEXT_DIM, relief="flat",
        )

        style.configure(
            "TProgressbar", background=COLOR_ACCENT, troughcolor=COLOR_PANEL_ALT,
            bordercolor=COLOR_PANEL_ALT, lightcolor=COLOR_ACCENT, darkcolor=COLOR_ACCENT,
        )

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def _build_layout(self):
        # --- Header bar ---
        header = ttk.Frame(self.root, padding=(16, 14, 16, 10))
        header.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(header, text="File & USB Activity Monitor", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(header, text="Real-time monitoring console", style="Subtitle.TLabel").pack(anchor=tk.W)
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X)

        # --- Resizable split between log and controls ---
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        log_pane = ttk.Frame(paned)
        control_pane = ttk.Frame(paned, width=300)
        paned.add(log_pane, weight=3)
        paned.add(control_pane, weight=1)

        self._build_log_section(log_pane)
        self._build_control_section(control_pane)

    # --- Activity log (left) ------------------------------------------------
    def _build_log_section(self, parent):
        # Header row: title + live count + search box
        head_row = ttk.Frame(parent)
        head_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))

        ttk.Label(head_row, text="Activity Log", style="Section.TLabel").pack(side=tk.LEFT)
        self.count_label = ttk.Label(head_row, text="0 events", style="Dim.TLabel")
        self.count_label.pack(side=tk.LEFT, padx=(8, 0))

        search_frame = ttk.Frame(head_row)
        search_frame.pack(side=tk.RIGHT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=26)
        search_entry.pack(side=tk.LEFT)
        self._set_placeholder(search_entry, "Filter activity log...")
        clear_btn = ttk.Button(search_frame, text="✕", width=3, style="Secondary.TButton",
                                command=lambda: self.search_var.set(""))
        clear_btn.pack(side=tk.LEFT, padx=(4, 0))
        ToolTip(clear_btn, "Clear filter")

        # Treeview + scrollbar
        tree_frame = ttk.Frame(parent, style="Panel.TFrame")
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        columns = ("time", "event")
        self.activity_tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="extended",
        )
        self.activity_tree.heading("time", text="Time")
        self.activity_tree.heading("event", text="Event")
        self.activity_tree.column("time", width=85, anchor=tk.CENTER, stretch=False)
        self.activity_tree.column("event", width=600, anchor=tk.W, stretch=True)

        for tag, color in (
            ("insert", COLOR_SUCCESS), ("remove", COLOR_WARNING), ("error", COLOR_DANGER),
            ("create", COLOR_INFO), ("modify", COLOR_MODIFY), ("delete", COLOR_DANGER),
            ("default", COLOR_TEXT),
        ):
            self.activity_tree.tag_configure(tag, foreground=color)

        vscroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.activity_tree.yview)
        self.activity_tree.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.activity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_tree_context_menu()

        # Progress bar (shown only during refresh)
        self.progress_bar = ttk.Progressbar(parent, orient=tk.HORIZONTAL, mode="determinate")

    def _build_tree_context_menu(self):
        menu = tk.Menu(self.root, tearoff=0, bg=COLOR_PANEL_ALT, fg=COLOR_TEXT,
                        activebackground=COLOR_ACCENT, activeforeground="#04201C", borderwidth=0)
        menu.add_command(label="Copy selected", command=self._copy_selected_rows)

        def popup(event):
            row = self.activity_tree.identify_row(event.y)
            if row:
                if row not in self.activity_tree.selection():
                    self.activity_tree.selection_set(row)
                menu.tk_popup(event.x_root, event.y_root)

        self.activity_tree.bind("<Button-3>", popup)

    def _copy_selected_rows(self):
        rows = [self.activity_tree.item(i, "values") for i in self.activity_tree.selection()]
        if not rows:
            return
        text = "\n".join(f"{t}  {e}" for t, e in rows)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    # --- Controls (right) ----------------------------------------------------
    def _build_control_section(self, parent):
        pad = {"padx": 14, "pady": (12, 0)}

        ttk.Label(parent, text="Monitored Folders", style="Section.TLabel").pack(anchor=tk.W, **pad)

        folder_wrap = ttk.Frame(parent, style="Panel.TFrame")
        folder_wrap.pack(fill=tk.X, padx=14, pady=(6, 6))
        self.folder_listbox = tk.Listbox(
            folder_wrap, height=10, bg=COLOR_PANEL, fg=COLOR_TEXT,
            selectbackground=COLOR_ACCENT, selectforeground="#04201C",
            highlightthickness=1, highlightbackground=COLOR_BORDER, highlightcolor=COLOR_ACCENT,
            relief=tk.FLAT, font=FONT_BASE, activestyle="none", borderwidth=0,
        )
        folder_scroll = ttk.Scrollbar(folder_wrap, orient=tk.VERTICAL, command=self.folder_listbox.yview)
        self.folder_listbox.configure(yscrollcommand=folder_scroll.set)
        folder_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.folder_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.folder_listbox.bind("<Delete>", lambda e: self.remove_folder())

        folder_btns = ttk.Frame(parent)
        folder_btns.pack(fill=tk.X, padx=14, pady=(0, 10))
        folder_btns.columnconfigure((0, 1), weight=1)
        add_btn = ttk.Button(folder_btns, text="+ Add", style="Secondary.TButton", command=self.add_folder)
        add_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        rm_btn = ttk.Button(folder_btns, text="− Remove", style="Secondary.TButton", command=self.remove_folder)
        rm_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ToolTip(add_btn, "Add a folder to monitor")
        ToolTip(rm_btn, "Stop monitoring the selected folder (Del)")

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=14, pady=4)

        ttk.Label(parent, text="Log Actions", style="Section.TLabel").pack(anchor=tk.W, **pad)
        action_btns = ttk.Frame(parent)
        action_btns.pack(fill=tk.X, padx=14, pady=(6, 10))
        action_btns.columnconfigure((0, 1), weight=1)
        export_btn = ttk.Button(action_btns, text="⤓ Export", style="Secondary.TButton", command=self.export_log_gui)
        export_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.refresh_button = ttk.Button(action_btns, text="↻ Refresh", style="Secondary.TButton",
                                          command=self.refresh_activity_list)
        self.refresh_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ToolTip(export_btn, "Export the activity log to a text file (Ctrl+E)")
        ToolTip(self.refresh_button, "Re-render the log from stored events (F5)")

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=14, pady=4)

        self.monitor_button = ttk.Button(
            parent, text="▶  Start File Monitoring", style="Accent.TButton", command=self.toggle_monitoring,
        )
        self.monitor_button.pack(fill=tk.X, padx=14, pady=(14, 8))

        self.status_label = tk.Label(
            parent, text="●  Stopped", fg=COLOR_DANGER, bg=COLOR_PANEL_ALT,
            font=FONT_BUTTON, padx=10, pady=6, anchor=tk.W,
        )
        self.status_label.pack(fill=tk.X, padx=14, pady=(0, 10))

        ttk.Label(
            parent, text="Tip: Insert a USB drive to monitor it automatically.",
            style="Dim.TLabel", wraplength=260, justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=14, pady=(4, 10))

    def _bind_shortcuts(self):
        self.root.bind("<F5>", lambda e: self.refresh_activity_list())
        self.root.bind("<Control-e>", lambda e: self.export_log_gui())
        self.root.bind("<Control-E>", lambda e: self.export_log_gui())

    # --- Small UI helpers -----------------------------------------------------
    def _set_placeholder(self, entry, text):
        entry.insert(0, text)
        entry.configure(foreground=COLOR_TEXT_DIM)

        def on_focus_in(_e):
            if entry.get() == text:
                entry.delete(0, tk.END)
                entry.configure(foreground=COLOR_TEXT)

        def on_focus_out(_e):
            if not entry.get():
                entry.insert(0, text)
                entry.configure(foreground=COLOR_TEXT_DIM)

        entry._placeholder_text = text
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    def _set_status(self, text, color):
        self.status_label.config(text=f"●  {text}", fg=color)

    @staticmethod
    def _classify_event(message):
        """Best-effort classification of a log line for icon + color coding."""
        low = message.lower()
        if "error" in low or "fail" in low:
            return "error", "✖"
        if "usb" in low and "insert" in low:
            return "insert", "⏵"
        if "usb" in low and "remov" in low:
            return "remove", "⏏"
        if "delet" in low:
            return "delete", "－"
        if "creat" in low or "new file" in low:
            return "create", "＋"
        if "modif" in low or "chang" in low:
            return "modify", "✎"
        return "default", "•"

    def _current_filter(self):
        text = self.search_var.get().strip().lower()
        if not text or text == "filter activity log...":
            return ""
        return text

    # ------------------------------------------------------------------ #
    # Thread Safety Wrapper for GUI Updates (unchanged contract)
    # ------------------------------------------------------------------ #
    def schedule_update(self, message):
        """Schedules the update_activity_list method to run in the main GUI thread."""
        if self.root.winfo_exists():  # Check if window exists before scheduling
            self.root.after(0, self.update_activity_list, message)
        else:
            logging.warning(f"GUI window closed, discarding message: {message}")

    def update_activity_list(self, message):
        """Updates the internal list and the log view. MUST run in the main GUI thread."""
        try:
            messages = []
            if isinstance(message, (list, tuple)):
                for msg in message:
                    if isinstance(msg, str):
                        messages.append(msg)
                    else:
                        logging.warning(f"Received non-string message in list: {type(msg)}")
            elif isinstance(message, str):
                messages.append(message)
            else:
                logging.warning(f"Received non-string message: {type(message)}")

            for msg in messages:
                self.activities.append(msg)
                self._append_row(msg)

            self.count_label.config(text=f"{len(self.activities)} events")
        except tk.TclError as e:
            if "invalid command name" in str(e):
                logging.warning(f"Log update failed, widget might be destroyed: {e}")
            else:
                logging.error(f"Tkinter error during log update: {e}", exc_info=True)
        except Exception as e:
            logging.error(f"Unexpected error updating activity list: {e}", exc_info=True)

    def _append_row(self, message):
        """Inserts a single message into the Treeview, respecting the active filter."""
        query = self._current_filter()
        if query and query not in message.lower():
            return
        tag, icon = self._classify_event(message)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.activity_tree.insert("", tk.END, values=(timestamp, f"{icon}  {message}"), tags=(tag,))
        self.activity_tree.yview_moveto(1.0)

    def _on_search_changed(self, *_args):
        # Re-render the visible rows from the underlying store whenever the filter changes.
        self.activity_tree.delete(*self.activity_tree.get_children())
        query = self._current_filter()
        for msg in self.activities:
            if query and query not in msg.lower():
                continue
            tag, icon = self._classify_event(msg)
            self.activity_tree.insert("", tk.END, values=("", f"{icon}  {msg}"), tags=(tag,))
        self.activity_tree.yview_moveto(1.0)

    def refresh_activity_list(self):
        """Refreshes the log view from the internal activities list with progress."""
        total_items = len(self.activities)
        logging.info(f"Refreshing activity list with {total_items} items.")

        if not self.root.winfo_exists():
            return

        if total_items == 0:
            self.activity_tree.delete(*self.activity_tree.get_children())
            messagebox.showinfo("Refresh Complete", "Activity log is empty.")
            return

        # --- Show Progress Bar and Disable Button ---
        self.refresh_button.config(state=tk.DISABLED)
        self.progress_bar.config(maximum=total_items, value=0)
        self.progress_bar.pack(fill=tk.X, pady=(8, 0))
        self.root.update()

        # --- Refresh Logic with Progress Update ---
        self.activity_tree.delete(*self.activity_tree.get_children())
        query = self._current_filter()
        try:
            for i, activity in enumerate(self.activities):
                if not self.root.winfo_exists():
                    break
                if not query or query in activity.lower():
                    tag, icon = self._classify_event(activity)
                    self.activity_tree.insert("", tk.END, values=("", f"{icon}  {activity}"), tags=(tag,))
                self.progress_bar.config(value=i + 1)
                if (i + 1) % 100 == 0 or (i + 1) == total_items:
                    self.root.update_idletasks()
        except Exception as e:
            logging.error(f"Error during log refresh: {e}", exc_info=True)
            messagebox.showerror("Refresh Error", f"An error occurred during refresh:\n{e}")
        finally:
            if self.root.winfo_exists():
                self.progress_bar.pack_forget()
                self.refresh_button.config(state=tk.NORMAL)
                self.root.update()

                logging.info("Activity list refresh completed.")
                messagebox.showinfo("Refresh Complete", f"Activity log refreshed successfully ({total_items} items displayed).")
                self.activity_tree.yview_moveto(1.0)

    def add_folder(self):
        """Adds a folder to monitor via file_monitor module."""
        folder = filedialog.askdirectory(title="Select Folder to Monitor")
        if folder:
            if file_monitor.add_monitored_folder(folder):
                self.folder_listbox.insert(tk.END, folder)
                self._save_folders_to_file()
                logging.info(f"Folder added: {folder}")
                messagebox.showinfo("Folder Added", f"Folder added for monitoring:\n{folder}")
                if self.is_monitoring:
                    self.restart_monitoring()
            else:
                if folder in file_monitor.get_monitored_folders():
                    messagebox.showwarning("Add Folder", f"Folder is already being monitored:\n{folder}")
                else:
                    messagebox.showerror("Add Folder", "Failed to add folder for monitoring.")

    def remove_folder(self):
        """Removes a selected folder from monitoring via file_monitor module."""
        selected_indices = self.folder_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Remove Folder", "Please select a folder to remove.")
            return

        index = selected_indices[0]
        folder = self.folder_listbox.get(index)

        if not messagebox.askyesno("Confirm Removal", f"Are you sure you want to stop monitoring and remove:\n{folder}?"):
            return

        if file_monitor.remove_monitored_folder(folder):
            self.folder_listbox.delete(index)
            self._save_folders_to_file()
            logging.info(f"Folder removed: {folder}")
            messagebox.showinfo("Folder Removed", f"Stopped monitoring folder:\n{folder}")
            if self.is_monitoring:
                self.restart_monitoring()
        else:
            messagebox.showerror("Remove Folder", f"Failed to remove folder:\n{folder}\nIt might have already been removed or an error occurred.")
            try:
                if folder == self.folder_listbox.get(index):
                    self.folder_listbox.delete(index)
                    self._save_folders_to_file()
            except tk.TclError:
                pass

    def toggle_monitoring(self):
        """Starts or stops the file monitoring process."""
        if not self.is_monitoring:
            current_folders = file_monitor.get_monitored_folders()
            if not current_folders:
                messagebox.showwarning("Start Monitoring", "Please add at least one folder to monitor.")
                return

            logging.info("Requesting start of file monitoring.")
            try:
                file_monitor.start_file_monitoring(self.schedule_update)
                self.is_monitoring = True
                self.monitor_button.config(text="■  Stop File Monitoring", style="Danger.TButton")
                self._set_status(f"Monitoring {len(current_folders)} folder(s)", COLOR_SUCCESS)
                messagebox.showinfo("Monitoring Started", f"File Monitoring Started for {len(current_folders)} folder(s).")
            except Exception as e:
                logging.error(f"Failed to start file monitoring: {e}", exc_info=True)
                messagebox.showerror("Monitoring Error", f"Failed to start file monitoring:\n{e}")
                self.is_monitoring = False
                self.monitor_button.config(text="▶  Start File Monitoring", style="Accent.TButton")
                self._set_status("Error starting", COLOR_DANGER)
        else:
            logging.info("Requesting stop of file monitoring.")
            try:
                file_monitor.stop_file_monitoring()
                self.is_monitoring = False
                self.monitor_button.config(text="▶  Start File Monitoring", style="Accent.TButton")
                self._set_status("Stopped", COLOR_DANGER)
                messagebox.showinfo("Monitoring Stopped", "File Monitoring Stopped.")
            except Exception as e:
                logging.error(f"Failed to stop file monitoring properly: {e}", exc_info=True)
                messagebox.showerror("Monitoring Error", f"Failed to stop file monitoring properly:\n{e}")
                self.is_monitoring = False
                self.monitor_button.config(text="▶  Start File Monitoring", style="Accent.TButton")
                self._set_status("Error stopping", COLOR_WARNING)

    def restart_monitoring(self):
        """Stops and restarts monitoring to apply changes (e.g., added/removed folders)."""
        logging.info("Restarting file monitoring due to configuration change.")
        if self.is_monitoring:
            self._set_status("Restarting...", COLOR_WARNING)
            self.root.update()
            try:
                file_monitor.stop_file_monitoring()
                current_folders = file_monitor.get_monitored_folders()
                if current_folders:
                    file_monitor.start_file_monitoring(self.schedule_update)
                    self._set_status(f"Monitoring {len(current_folders)} folder(s)", COLOR_SUCCESS)
                    logging.info("File monitoring restarted successfully.")
                else:
                    self.is_monitoring = False
                    self.monitor_button.config(text="▶  Start File Monitoring", style="Accent.TButton")
                    self._set_status("Stopped (no folders)", COLOR_DANGER)
                    logging.info("Monitoring stopped as no folders remain after restart.")
            except Exception as e:
                logging.error(f"Failed to restart monitoring: {e}", exc_info=True)
                messagebox.showerror("Restart Error", f"Failed to restart monitoring:\n{e}")
                self.is_monitoring = False
                self.monitor_button.config(text="▶  Start File Monitoring", style="Accent.TButton")
                self._set_status("Error restarting", COLOR_DANGER)
        else:
            logging.warning("Restart requested but monitoring was not active.")

    def export_log_gui(self):
        """Handles the GUI part of exporting the ACTIVITY log."""
        log_count = len(self.activities)
        logging.info(f"Initiating export for {log_count} log entries.")

        if not self.activities:
            messagebox.showinfo("Export Log", "Activity log is empty. Nothing to export.")
            return

        export_folder = filedialog.askdirectory(title="Select Folder to Export Activity Log")
        if export_folder:
            file_path = os.path.join(export_folder, "file_usb_activity_log.txt")
            logging.debug(f"Selected export path: {file_path}")

            try:
                file_monitor.export_activity_log(self.activities, file_path)
                logging.info(f"Log export successful to {file_path}")
                messagebox.showinfo("Export Complete", f"Activity log ({log_count} entries) exported successfully to:\n{file_path}")
            except Exception as e:
                logging.error(f"Failed to export activity log: {e}", exc_info=True)
                messagebox.showerror("Export Error", f"Failed to export log:\n{e}")
        else:
            logging.info("Export operation cancelled by user.")

    def _save_folders_to_file(self, filename='monitored_folders.txt'):
        """Helper function to save the current list of monitored folders from file_monitor."""
        logging.debug(f"Saving monitored folders list to {filename}")
        current_folders = file_monitor.get_monitored_folders()
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for folder in current_folders:
                    if folder.strip():
                        f.write(folder.strip() + '\n')
            logging.debug(f"Saved {len(current_folders)} folders.")
        except IOError as e:
            logging.error(f"Could not save monitored folders list to {filename}: {e}")
            messagebox.showerror("File Error", f"Could not save monitored folders list:\n{e}")
        except Exception as e:
            logging.error(f"Unexpected error saving folders list: {e}", exc_info=True)
            messagebox.showerror("File Error", f"An unexpected error occurred saving the folders list:\n{e}")

    def load_folders(self, filename='monitored_folders.txt'):
        """Loads folders from the file, adds them via file_monitor, and updates the listbox."""
        logging.info(f"Loading monitored folders from {filename}")
        self.folder_listbox.delete(0, tk.END)

        loaded_count = 0
        skipped_count = 0
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    for folder in f:
                        folder = folder.strip()
                        if folder:
                            if os.path.isdir(folder):
                                if file_monitor.add_monitored_folder(folder):
                                    self.folder_listbox.insert(tk.END, folder)
                                    loaded_count += 1
                            else:
                                logging.warning(f"Folder '{folder}' from '{filename}' not found or is not a directory. Skipping.")
                                skipped_count += 1
            self._save_folders_to_file(filename)
            logging.info(f"Loaded {loaded_count} folders. Skipped {skipped_count} invalid entries.")
        except IOError as e:
            logging.error(f"Could not load monitored folders list from {filename}: {e}")
            messagebox.showerror("File Error", f"Could not load monitored folders list:\n{e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred loading folders: {e}", exc_info=True)
            messagebox.showerror("Load Error", f"An unexpected error occurred loading folders:\n{e}")

    def start_usb_drive_monitor(self, drive_path):
        """Callback triggered by usb_monitor when a USB drive is connected."""
        logging.info(f"Request received to start monitoring USB drive: {drive_path}")
        self.schedule_update(f"USB Drive detected: {drive_path}. Starting file monitoring on it.")
        try:
            file_monitor.start_usb_file_monitor(drive_path, self.schedule_update)
        except Exception as e:
            log_msg = f"Error starting file monitoring on USB {drive_path}: {e}"
            logging.error(log_msg, exc_info=True)
            self.schedule_update(log_msg)

    # --- Optional: Function to Fetch Windows Events ---
    # def fetch_win_events_gui(self):
    #     """Fetches Windows Event Log entries (runs in background)."""
    #     messagebox.showinfo("Windows Events", "Fetching recent file access events...\nThis may take a moment and requires Admin rights & Audit Policy enabled.")
    #
    #     import threading
    #     def fetch_in_thread():
    #         logging.info("Starting thread to fetch Windows events.")
    #         try:
    #             events = event_log_monitor.fetch_file_access_events(max_events=50)
    #             if events is None:
    #                  self.schedule_update("[WinEvent] Error: Could not fetch events. Check logs/permissions.")
    #             elif not events:
    #                  self.schedule_update("[WinEvent] No recent file access events found (check Audit Policy).")
    #             else:
    #                  formatted_events = ["[WinEvent] " + e for e in events]
    #                  self.schedule_update(formatted_events)
    #             logging.info(f"Finished fetching Windows events. Found: {len(events) if events else 0}")
    #         except Exception as e:
    #              logging.error(f"Error in fetch_win_events thread: {e}", exc_info=True)
    #              self.schedule_update(f"[WinEvent] Error fetching events: {e}")
    #
    #     thread = threading.Thread(target=fetch_in_thread, daemon=True)
    #     thread.start()

    def on_closing(self):
        """Handles graceful shutdown."""
        logging.info("Close window request received.")
        if messagebox.askokcancel("Quit", "Do you want to quit the application?\nThis will stop all monitoring."):
            logging.info("User confirmed quit.")
            try:
                if self.is_monitoring:
                    logging.debug("Attempting to stop file monitoring...")
                    file_monitor.stop_file_monitoring()
                    logging.debug("File monitoring stop requested.")
                else:
                    logging.debug("File monitoring was not active.")

                logging.debug("Attempting to stop USB device monitoring...")
                usb_monitor.stop_usb_monitoring()
                logging.debug("USB device monitoring stop requested.")
            except Exception as e:
                logging.error(f"Error during shutdown cleanup: {e}", exc_info=True)
            finally:
                logging.info("Destroying root window.")
                self.root.destroy()


# --- Main Execution Guard ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    root = tk.Tk()
    app = FileActivityApp(root)
    root.mainloop()