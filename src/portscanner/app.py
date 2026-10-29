"""Tkinter GUI for PortScanner."""

from __future__ import annotations

import csv
import json
import os
import queue
import sys
import time
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    _TK_IMPORT_ERROR: ImportError | None = None
except ImportError as exc:  # pragma: no cover - depends on the system
    tk = None  # type: ignore[assignment]
    filedialog = messagebox = ttk = None  # type: ignore[assignment]
    _TK_IMPORT_ERROR = exc

from . import __version__
from .engine import PortResult, ScanConfig, ScanEngine, ScanFinished, ScanProgress
from .ports import PRESETS, PortError, parse_ports
from .targets import MAX_HOSTS, TargetError, estimate_targets, expand_targets

BG = "#0f1117"
PANEL = "#161a23"
FIELD = "#0b0d12"
FG = "#e8eaf0"
MUTED = "#98a2b3"
ACCENT = "#3b82f6"
ACCENT_ACTIVE = "#2563eb"
GREEN = "#34d399"
AMBER = "#fbbf24"
RED = "#f87171"
BORDER = "#2a3040"


def _config_directory() -> Path:
    """Return the per-user config directory for the current platform."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "").strip()
        base = (
            Path(appdata).expanduser()
            if appdata
            else Path.home() / "AppData" / "Roaming"
        )
        return base / "portscanner"

    override = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if override:
        base = Path(override).expanduser()
        if base.is_absolute():
            return base / "portscanner"
    return Path.home() / ".config" / "portscanner"


CONFIG_DIR = _config_directory()
CONFIG_FILE = CONFIG_DIR / "config.json"

PROTOCOL_CHOICES = ("TCP", "UDP", "TCP + UDP")

USAGE = """portscanner - fast TCP/UDP port scanner with a graphical interface

Usage:
  portscanner            Start the graphical interface
  portscanner --version  Print the version
  portscanner --help     Show this help

Targets accept single addresses, CIDR networks, ranges and hostnames, e.g.:
  192.168.1.10
  192.168.1.0/24
  10.0.0.5-10.0.0.25
  example.com

Only scan systems you own or are authorized to test.
"""


class PortScannerApp:
    def __init__(self, root: "tk.Tk") -> None:
        self.root = root
        self.engine: ScanEngine | None = None
        self.events: "queue.Queue[object] | None" = None
        self.results: list[PortResult] = []
        self.open_count = 0
        self._sort_column: str | None = None
        self._sort_reverse = False
        self._searching = False
        self._stopping = False

        self._build_styles()
        self._build_ui()
        self._load_config()
        self._bind_traces()
        self._update_estimate()

        root.title("PortScanner")
        root.geometry("1120x760")
        root.minsize(900, 620)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind("<Return>", lambda _event: self._start_scan())
        root.bind("<Escape>", lambda _event: self._stop_scan())
        self.target_entry.focus_set()

    # ------------------------------------------------------------- styling

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.root.option_add("*TCombobox*Listbox.font", "TkDefaultFont")

        style.configure(
            ".",
            background=BG,
            foreground=FG,
            fieldbackground=FIELD,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            troughcolor=FIELD,
            font=("TkDefaultFont", 10),
        )
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Panel.TLabel", background=PANEL, foreground=FG)
        style.configure(
            "Title.TLabel", background=BG, foreground=FG,
            font=("TkDefaultFont", 22, "bold"),
        )
        style.configure(
            "Subtitle.TLabel", background=BG, foreground=MUTED,
            font=("TkDefaultFont", 10),
        )
        style.configure(
            "FieldLabel.TLabel", background=PANEL, foreground=MUTED,
            font=("TkDefaultFont", 9, "bold"),
        )
        style.configure(
            "Hint.TLabel", background=PANEL, foreground="#6f7a8d",
            font=("TkDefaultFont", 9),
        )
        style.configure(
            "Stat.TLabel", background=BG, foreground=MUTED,
            font=("TkDefaultFont", 9),
        )
        style.configure(
            "Status.TLabel", background=BG, foreground=FG,
            font=("TkDefaultFont", 10),
        )
        style.configure(
            "Accent.TButton", background=ACCENT, foreground="#ffffff",
            borderwidth=0, focusthickness=0, padding=(20, 9),
            font=("TkDefaultFont", 10, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[("active", ACCENT_ACTIVE), ("disabled", "#26344d")],
            foreground=[("disabled", "#78849a")],
        )
        style.configure(
            "TButton", background="#232a3b", foreground=FG, borderwidth=0,
            padding=(14, 9),
        )
        style.map(
            "TButton",
            background=[("active", "#2e374c"), ("disabled", "#191d27")],
            foreground=[("disabled", "#5c6577")],
        )
        style.configure(
            "TEntry", fieldbackground=FIELD, foreground=FG, insertcolor=FG,
            borderwidth=1, relief="flat", padding=7,
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", ACCENT)],
            lightcolor=[("focus", ACCENT)],
            darkcolor=[("focus", ACCENT)],
        )
        style.configure(
            "TCombobox", fieldbackground=FIELD, background="#232a3b",
            foreground=FG, arrowcolor=FG, padding=5,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", FIELD), ("disabled", "#11141b")],
            foreground=[("readonly", FG), ("disabled", "#5c6577")],
            selectbackground=[("readonly", FIELD)],
            selectforeground=[("readonly", FG)],
            background=[("active", "#2e374c")],
            arrowcolor=[("disabled", "#5c6577")],
        )
        style.configure(
            "TSpinbox", fieldbackground=FIELD, foreground=FG, arrowcolor=FG,
            borderwidth=1, padding=5,
        )
        style.map(
            "TSpinbox",
            fieldbackground=[("disabled", "#11141b")],
            foreground=[("disabled", "#5c6577")],
        )
        style.configure(
            "TCheckbutton", background=PANEL, foreground=FG,
            focuscolor=PANEL, padding=2,
        )
        style.map(
            "TCheckbutton",
            background=[("active", PANEL)],
            foreground=[("disabled", "#5c6577")],
            indicatorcolor=[("selected", ACCENT), ("!selected", FIELD)],
        )
        style.configure(
            "Treeview", background=FIELD, fieldbackground=FIELD, foreground=FG,
            borderwidth=0, rowheight=27,
        )
        style.configure(
            "Treeview.Heading", background="#1b2130", foreground=MUTED,
            borderwidth=0, padding=(8, 7),
            font=("TkDefaultFont", 9, "bold"),
        )
        style.map(
            "Treeview.Heading",
            background=[("active", "#252d3f")],
            foreground=[("active", FG)],
        )
        style.map(
            "Treeview",
            background=[("selected", "#1d4ed8")],
            foreground=[("selected", "#ffffff")],
        )
        style.configure(
            "TProgressbar", background=ACCENT, troughcolor=FIELD,
            borderwidth=0, thickness=9,
        )

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(3, weight=1)

        header = ttk.Frame(self.root, padding=(24, 20, 24, 4))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="PortScanner", style="Title.TLabel").pack(side="left")
        ttk.Label(
            header, text=f"v{__version__}", style="Subtitle.TLabel"
        ).pack(side="left", padx=(10, 0), pady=(12, 0))
        ttk.Label(
            header,
            text="Fast TCP/UDP discovery for Linux",
            style="Subtitle.TLabel",
        ).pack(side="right", pady=(12, 0))

        form = ttk.Frame(self.root, style="Panel.TFrame", padding=(20, 16, 20, 16))
        form.grid(row=1, column=0, sticky="ew", padx=24, pady=(10, 8))
        form.grid_columnconfigure(1, weight=1)

        ttk.Label(form, text="TARGETS", style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 16), pady=(0, 2)
        )
        self.target_var = tk.StringVar()
        self.target_entry = ttk.Entry(form, textvariable=self.target_var)
        self.target_entry.grid(row=0, column=1, columnspan=3, sticky="ew", pady=(0, 2))
        ttk.Label(
            form,
            text="IP address, CIDR network, range or hostname — separate multiple entries with commas.",
            style="Hint.TLabel",
        ).grid(row=1, column=1, columnspan=3, sticky="w", pady=(0, 12))

        ttk.Label(form, text="PORTS", style="FieldLabel.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 16), pady=2
        )
        self.ports_var = tk.StringVar(value="22,80,443")
        self.ports_entry = ttk.Entry(form, textvariable=self.ports_var)
        self.ports_entry.grid(row=2, column=1, sticky="ew", pady=2)

        self.all_ports_var = tk.BooleanVar(value=False)
        self.all_ports_check = ttk.Checkbutton(
            form,
            text="All 65,535",
            variable=self.all_ports_var,
            command=self._toggle_all_ports,
        )
        self.all_ports_check.grid(row=2, column=2, sticky="w", padx=(14, 14))

        self.preset_var = tk.StringVar(value="Custom")
        self.preset_combo = ttk.Combobox(
            form,
            textvariable=self.preset_var,
            values=list(PRESETS),
            state="readonly",
            width=23,
        )
        self.preset_combo.grid(row=2, column=3, sticky="ew")
        self.preset_combo.bind("<<ComboboxSelected>>", self._apply_preset)

        ttk.Label(form, text="OPTIONS", style="FieldLabel.TLabel").grid(
            row=3, column=0, sticky="w", padx=(0, 16), pady=(14, 2)
        )
        options = ttk.Frame(form, style="Panel.TFrame")
        options.grid(row=3, column=1, columnspan=3, sticky="ew", pady=(14, 2))

        ttk.Label(options, text="Protocol", style="Panel.TLabel").pack(side="left")
        self.protocol_var = tk.StringVar(value="TCP")
        self.protocol_combo = ttk.Combobox(
            options,
            textvariable=self.protocol_var,
            values=list(PROTOCOL_CHOICES),
            state="readonly",
            width=10,
        )
        self.protocol_combo.pack(side="left", padx=(6, 18))

        ttk.Label(options, text="Timeout (s)", style="Panel.TLabel").pack(side="left")
        self.timeout_var = tk.StringVar(value="1.0")
        self.timeout_spin = ttk.Spinbox(
            options,
            from_=0.05,
            to=10.0,
            increment=0.1,
            textvariable=self.timeout_var,
            width=6,
        )
        self.timeout_spin.pack(side="left", padx=(6, 18))

        ttk.Label(options, text="Concurrency", style="Panel.TLabel").pack(side="left")
        self.concurrency_var = tk.StringVar(value="1000")
        self.concurrency_spin = ttk.Spinbox(
            options,
            from_=1,
            to=5000,
            increment=50,
            textvariable=self.concurrency_var,
            width=7,
        )
        self.concurrency_spin.pack(side="left", padx=(6, 18))

        self.filtered_var = tk.BooleanVar(value=False)
        self.filtered_check = ttk.Checkbutton(
            options,
            text="Show UDP open|filtered",
            variable=self.filtered_var,
        )
        self.filtered_check.pack(side="left")

        actions = ttk.Frame(form, style="Panel.TFrame")
        actions.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(16, 0))
        self.start_button = ttk.Button(
            actions, text="Start scan", style="Accent.TButton", command=self._start_scan
        )
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(
            actions, text="Stop", command=self._stop_scan, state="disabled"
        )
        self.stop_button.pack(side="left", padx=(8, 0))
        self.clear_button = ttk.Button(
            actions, text="Clear results", command=self._clear_results
        )
        self.clear_button.pack(side="left", padx=(8, 0))
        self.save_button = ttk.Button(
            actions, text="Save CSV…", command=self._save_csv
        )
        self.save_button.pack(side="left", padx=(8, 0))
        self.estimate_label = ttk.Label(
            actions, text="", style="Hint.TLabel", anchor="e"
        )
        self.estimate_label.pack(side="right")

        progress_frame = ttk.Frame(self.root, padding=(24, 4, 24, 4))
        progress_frame.grid(row=2, column=0, sticky="ew")
        progress_frame.grid_columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(
            progress_frame, mode="determinate", maximum=100.0
        )
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.percent_var = tk.StringVar(value="0%")
        ttk.Label(
            progress_frame, textvariable=self.percent_var, style="Stat.TLabel",
            width=6, anchor="e",
        ).grid(row=0, column=1, sticky="e")

        self.status_var = tk.StringVar(value="Ready — enter targets and ports, then start a scan.")
        ttk.Label(
            progress_frame, textvariable=self.status_var, style="Status.TLabel",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))
        self.stats_var = tk.StringVar(value="0 open")
        ttk.Label(
            progress_frame, textvariable=self.stats_var, style="Stat.TLabel",
            anchor="e",
        ).grid(row=1, column=1, sticky="e", pady=(5, 0))

        results_frame = ttk.Frame(self.root, padding=(24, 6, 24, 6))
        results_frame.grid(row=3, column=0, sticky="nsew")
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            results_frame,
            columns=("host", "port", "protocol", "state", "service"),
            show="headings",
            selectmode="extended",
        )
        headings = {
            "host": "Host",
            "port": "Port",
            "protocol": "Protocol",
            "state": "State",
            "service": "Service",
        }
        self._headings = headings
        widths = {"host": 240, "port": 80, "protocol": 100, "state": 130, "service": 220}
        for column, label in headings.items():
            self.tree.heading(
                column,
                text=label,
                command=lambda col=column: self._sort_by(col),
            )
            self.tree.column(
                column,
                width=widths[column],
                minwidth=60,
                anchor="e" if column == "port" else "w",
                stretch=column in ("host", "service"),
            )
        self.tree.tag_configure("odd", background="#0b0d12")
        self.tree.tag_configure("even", background="#11151e")
        self.tree.tag_configure("open", foreground=GREEN)
        self.tree.tag_configure("filtered", foreground=AMBER)

        scrollbar = ttk.Scrollbar(
            results_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self._build_context_menu()

        footer = ttk.Frame(self.root, padding=(24, 2, 24, 12))
        footer.grid(row=4, column=0, sticky="ew")
        ttk.Label(
            footer,
            text="Only scan systems you own or are explicitly authorized to test.",
            style="Hint.TLabel",
        ).pack(side="left")

        self._lockable: list[tuple[tk.Widget, str]] = [
            (self.target_entry, "normal"),
            (self.ports_entry, "normal"),
            (self.all_ports_check, "normal"),
            (self.preset_combo, "readonly"),
            (self.protocol_combo, "readonly"),
            (self.timeout_spin, "normal"),
            (self.concurrency_spin, "normal"),
            (self.filtered_check, "normal"),
        ]

    def _build_context_menu(self) -> None:
        self.context_menu = tk.Menu(
            self.root, tearoff=0, background=PANEL, foreground=FG,
            activebackground=ACCENT, activeforeground="#ffffff", borderwidth=0,
        )
        self.context_menu.add_command(
            label="Copy address", command=self._copy_selected
        )
        self.context_menu.add_command(
            label="Save results as CSV…", command=self._save_csv
        )
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Button-1>", self._maybe_clear_selection, add="+")
        self.tree.bind("<Control-c>", lambda _event: self._copy_selected())

    def _show_context_menu(self, event: "tk.Event") -> None:
        row = self.tree.identify_row(event.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
        if not self.tree.selection():
            return
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _maybe_clear_selection(self, event: "tk.Event") -> None:
        if not self.tree.identify_row(event.y):
            selection = self.tree.selection()
            if selection:
                self.tree.selection_remove(*selection)

    # ------------------------------------------------------------ scan flow

    def _toggle_all_ports(self) -> None:
        if self.all_ports_var.get():
            self.ports_var.set("1-65535")
            self.ports_entry.configure(state="disabled")
            self.preset_var.set("All ports (1-65535)")
        else:
            self.ports_entry.configure(state="normal")
            if self.preset_var.get() == "All ports (1-65535)":
                self.preset_var.set("Custom")
                if self.ports_var.get() == "1-65535":
                    self.ports_var.set("22,80,443")
        self._update_estimate()

    def _apply_preset(self, _event: object = None) -> None:
        preset = PRESETS.get(self.preset_var.get())
        if preset is None:
            self.all_ports_var.set(False)
            self.ports_entry.configure(state="normal")
            self._update_estimate()
            return
        if self.preset_var.get().startswith("All ports"):
            self.all_ports_var.set(True)
            self.ports_var.set("1-65535")
            self.ports_entry.configure(state="disabled")
        else:
            self.all_ports_var.set(False)
            self.ports_entry.configure(state="normal")
            self.ports_var.set(",".join(str(port) for port in preset))
        self._update_estimate()

    def _protocols(self) -> tuple[str, ...]:
        choice = self.protocol_var.get()
        if choice == "UDP":
            return ("udp",)
        if choice == "TCP + UDP":
            return ("tcp", "udp")
        return ("tcp",)

    def _update_estimate(self) -> None:
        spec = self.target_var.get().strip()
        if not spec:
            self.estimate_label.configure(
                text="Enter targets to see the scan size", foreground="#6f7a8d"
            )
            return

        hosts = estimate_targets(spec)
        try:
            ports = parse_ports(self.ports_var.get(), all_ports=self.all_ports_var.get())
            port_count = len(ports)
        except PortError:
            port_count = 0
        protocol_count = len(self._protocols())
        probes = hosts * port_count * protocol_count

        if hosts > MAX_HOSTS:
            text = f"{hosts:,} hosts — above the {MAX_HOSTS:,} host limit"
            color = RED
        elif probes > 2_000_000:
            text = f"{hosts:,} hosts × {port_count:,} ports × {protocol_count} = {probes:,} probes (large scan)"
            color = AMBER
        elif hosts == 0:
            text = "Check the target specification"
            color = RED
        elif port_count == 0:
            text = "Check the port specification"
            color = RED
        else:
            text = f"{hosts:,} hosts × {port_count:,} ports × {protocol_count} = {probes:,} probes"
            color = "#6f7a8d"
        self.estimate_label.configure(text=text, foreground=color)

    def _start_scan(self) -> None:
        if self.engine is not None:
            return
        if self._searching:
            return

        self._stopping = False
        self._searching = True
        self.root.configure(cursor="watch")
        self.root.update_idletasks()
        try:
            hosts = expand_targets(self.target_var.get())
        except TargetError as exc:
            messagebox.showerror("Invalid target", str(exc), parent=self.root)
            return
        finally:
            self._searching = False
            self.root.configure(cursor="")

        try:
            ports = parse_ports(
                self.ports_var.get(), all_ports=self.all_ports_var.get()
            )
        except PortError as exc:
            messagebox.showerror("Invalid ports", str(exc), parent=self.root)
            return

        try:
            timeout = float(self.timeout_var.get().replace(",", "."))
        except ValueError:
            messagebox.showerror(
                "Invalid timeout", "Timeout must be a number between 0.05 and 10 seconds.",
                parent=self.root,
            )
            return
        if not 0.05 <= timeout <= 10.0:
            messagebox.showerror(
                "Invalid timeout", "Timeout must be between 0.05 and 10 seconds.",
                parent=self.root,
            )
            return

        try:
            concurrency = int(self.concurrency_var.get())
        except ValueError:
            messagebox.showerror(
                "Invalid concurrency", "Concurrency must be a whole number between 1 and 5000.",
                parent=self.root,
            )
            return
        if not 1 <= concurrency <= 5000:
            messagebox.showerror(
                "Invalid concurrency", "Concurrency must be between 1 and 5000.",
                parent=self.root,
            )
            return

        protocols = self._protocols()
        total = len(hosts) * len(ports) * len(protocols)
        if total > 2_000_000:
            proceed = messagebox.askyesno(
                "Large scan",
                f"This scan will perform {total:,} probes against {len(hosts):,} host(s).\n\n"
                "It can take a long time. Continue?",
                parent=self.root,
            )
            if not proceed:
                return

        self._save_config()
        self._clear_results()

        config = ScanConfig(
            hosts=hosts,
            ports=ports,
            protocols=protocols,
            timeout=timeout,
            concurrency=concurrency,
            show_filtered=self.filtered_var.get(),
        )
        self.events = queue.Queue()
        self.engine = ScanEngine(config, self.events.put)

        self.progress["value"] = 0.0
        self.percent_var.set("0%")
        self.status_var.set(
            f"Scanning {len(hosts):,} host(s), {len(ports):,} port(s) "
            f"({', '.join(protocol.upper() for protocol in protocols)})…"
        )
        self.stats_var.set(f"0 / {total:,} probes · 0 open")
        self._set_scanning(True)
        self.engine.start()
        self.root.after(60, self._poll_events)

    def _stop_scan(self) -> None:
        if self.engine is None:
            return
        self._stopping = True
        self.engine.stop()
        self.stop_button.configure(state="disabled")
        self.status_var.set("Stopping scan…")

    def _poll_events(self) -> None:
        if self.events is None:
            return

        finished: ScanFinished | None = None
        for _ in range(600):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if isinstance(event, PortResult):
                self._add_result(event)
            elif isinstance(event, ScanProgress):
                self._show_progress(event)
            elif isinstance(event, ScanFinished):
                finished = event
                break

        if finished is not None:
            self.events = None
            self._finish_scan(finished)
            return
        if self.engine is not None:
            self.root.after(60, self._poll_events)

    def _show_progress(self, event: ScanProgress) -> None:
        percent = (event.scanned / event.total * 100.0) if event.total else 0.0
        self.progress["value"] = percent
        self.percent_var.set(f"{percent:.0f}%")
        if event.current and not self._stopping:
            self.status_var.set(f"Scanning {event.current}…")
        self.stats_var.set(
            f"{event.scanned:,} / {event.total:,} probes · "
            f"{event.rate:,.0f}/s · {event.open_ports:,} open"
        )

    def _finish_scan(self, event: ScanFinished) -> None:
        self._stopping = False
        engine = self.engine
        if engine is not None:
            engine.join(timeout=1.0)
        self.engine = None
        self._set_scanning(False)

        if event.error:
            self.status_var.set(f"Scan failed: {event.error}")
            self.stats_var.set("")
            messagebox.showerror("Scan failed", event.error, parent=self.root)
            return

        if event.stopped:
            self.progress["value"] = (
                event.scanned / event.total * 100.0 if event.total else 0.0
            )
            self.percent_var.set(f"{self.progress['value']:.0f}%")
            self.status_var.set(
                f"Scan stopped after {event.elapsed:.1f}s — "
                f"{event.scanned:,} of {event.total:,} probes completed."
            )
        else:
            self.progress["value"] = 100.0
            self.percent_var.set("100%")
            self.status_var.set(
                f"Scan complete in {event.elapsed:.1f}s — "
                f"{event.scanned:,} probes, {event.open_ports:,} open port(s) found."
            )
        self.stats_var.set(
            f"{event.open_ports:,} open · {event.elapsed:.1f}s · "
            f"{event.scanned / event.elapsed:,.0f}/s"
            if event.elapsed > 0
            else f"{event.open_ports:,} open"
        )

    def _set_scanning(self, scanning: bool) -> None:
        self.start_button.configure(state="disabled" if scanning else "normal")
        self.stop_button.configure(state="normal" if scanning else "disabled")
        self.clear_button.configure(state="disabled" if scanning else "normal")
        for widget, normal_state in self._lockable:
            widget.configure(state="disabled" if scanning else normal_state)
        if not scanning:
            if self.all_ports_var.get():
                self.ports_entry.configure(state="disabled")

    # -------------------------------------------------------------- results

    def _clear_results(self) -> None:
        if self.engine is not None:
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.results.clear()
        self.open_count = 0
        self.progress["value"] = 0.0
        self.percent_var.set("0%")
        self.stats_var.set("0 open")
        if self.status_var.get().startswith(("Scan complete", "Scan stopped", "Scan failed")):
            self.status_var.set("Ready.")

    def _add_result(self, result: PortResult) -> None:
        self.results.append(result)
        if result.state == "open":
            self.open_count += 1
        tag = "open" if result.state == "open" else "filtered"
        index = len(self.results) - 1
        self._insert_row(result, "odd" if index % 2 else "even", tag, scroll=True)
        self.stats_var.set(
            f"{len(self.results):,} result(s) · {self.open_count:,} open"
        )

    def _insert_row(
        self, result: PortResult, stripe: str, state_tag: str, *, scroll: bool
    ) -> None:
        near_bottom = True
        if scroll:
            view = self.tree.yview()
            near_bottom = bool(view) and view[1] >= 0.995
        self.tree.insert(
            "",
            "end",
            values=(
                result.host,
                result.port,
                result.protocol.upper(),
                result.state,
                result.service or "—",
            ),
            tags=(stripe, state_tag),
        )
        if scroll and near_bottom:
            self.tree.see(self.tree.get_children()[-1])

    def _sort_by(self, column: str) -> None:
        if not self.results:
            return
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
        for name, label in self._headings.items():
            if name == self._sort_column:
                label += " ▼" if self._sort_reverse else " ▲"
            self.tree.heading(name, text=label)

        keys = {
            "host": lambda result: result.host,
            "port": lambda result: result.port,
            "protocol": lambda result: result.protocol,
            "state": lambda result: result.state,
            "service": lambda result: result.service,
        }
        ordered = sorted(
            self.results, key=keys[column], reverse=self._sort_reverse
        )
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, result in enumerate(ordered):
            tag = "open" if result.state == "open" else "filtered"
            self._insert_row(
                result, "odd" if index % 2 else "even", tag, scroll=False
            )

    def _copy_selected(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        lines: list[str] = []
        for item in selection:
            values = self.tree.item(item, "values")
            if len(values) >= 3:
                lines.append(f"{values[0]}:{values[1]}/{str(values[2]).lower()}")
        if not lines:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))
        self.status_var.set(f"Copied {len(lines)} result(s) to the clipboard.")

    def _save_csv(self) -> None:
        if not self.results:
            messagebox.showinfo(
                "No results", "There are no results to save yet.", parent=self.root
            )
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save scan results",
            defaultextension=".csv",
            initialfile=time.strftime("portscan-%Y%m%d-%H%M%S.csv"),
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["host", "port", "protocol", "state", "service"])
                for item in self.tree.get_children():
                    values = self.tree.item(item, "values")
                    writer.writerow(
                        [
                            values[0],
                            values[1],
                            values[2],
                            values[3],
                            "" if values[4] == "—" else values[4],
                        ]
                    )
        except OSError as exc:
            messagebox.showerror(
                "Could not save", f"Failed to write the CSV file:\n{exc}",
                parent=self.root,
            )
            return
        self.status_var.set(f"Saved {len(self.results):,} result(s) to {path}")

    # ------------------------------------------------------------- settings

    def _load_config(self) -> None:
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return

        self.target_var.set(str(data.get("targets", "")))
        self.ports_var.set(str(data.get("ports", "22,80,443")))
        protocol = str(data.get("protocol", "TCP"))
        if protocol in PROTOCOL_CHOICES:
            self.protocol_var.set(protocol)
        self.timeout_var.set(str(data.get("timeout", "1.0")))
        self.concurrency_var.set(str(data.get("concurrency", "1000")))
        self.filtered_var.set(bool(data.get("show_filtered", False)))

        all_ports = bool(data.get("all_ports", False))
        self.all_ports_var.set(all_ports)
        if all_ports:
            self.ports_entry.configure(state="disabled")
            self.preset_var.set("All ports (1-65535)")
        else:
            preset_name = str(data.get("preset", "Custom"))
            if preset_name in PRESETS:
                self.preset_var.set(preset_name)

    def _bind_traces(self) -> None:
        self.target_var.trace_add("write", lambda *_: self._update_estimate())
        self.ports_var.trace_add("write", lambda *_: self._update_estimate())
        self.all_ports_var.trace_add("write", lambda *_: self._update_estimate())
        self.protocol_var.trace_add("write", lambda *_: self._update_estimate())

    def _save_config(self) -> None:
        data = {
            "targets": self.target_var.get(),
            "ports": self.ports_var.get(),
            "all_ports": self.all_ports_var.get(),
            "preset": self.preset_var.get(),
            "protocol": self.protocol_var.get(),
            "timeout": self.timeout_var.get(),
            "concurrency": self.concurrency_var.get(),
            "show_filtered": self.filtered_var.get(),
        }
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
        except OSError:
            # Settings are a convenience; never block a scan over them.
            pass

    def _on_close(self) -> None:
        if self.engine is not None:
            should_quit = messagebox.askyesno(
                "Scan in progress",
                "A scan is still running. Stop it and quit?",
                parent=self.root,
            )
            if not should_quit:
                return
            self.engine.stop()
            self.engine.join(timeout=1.5)
            self.engine = None
        self._save_config()
        self.root.destroy()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    unknown = [arg for arg in args if arg not in ("-h", "--help", "--version")]
    if unknown:
        print(f"portscanner: unrecognized argument: {unknown[0]}", file=sys.stderr)
        print("Try 'portscanner --help' for usage.", file=sys.stderr)
        return 2
    if "--version" in args:
        print(f"portscanner {__version__}")
        return 0
    if "-h" in args or "--help" in args:
        print(USAGE)
        return 0

    if sys.version_info < (3, 11):
        print(
            "portscanner: Python 3.11 or newer is required "
            f"(found {sys.version.split()[0]}).",
            file=sys.stderr,
        )
        return 1

    if _TK_IMPORT_ERROR is not None:
        print(
            "portscanner: Tkinter is not available. Install it with your package "
            "manager (for example: sudo dnf install python3-tkinter).",
            file=sys.stderr,
        )
        return 1

    if sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        print(
            "portscanner: no graphical display found. "
            "Start it from a desktop session (DISPLAY or WAYLAND_DISPLAY must be set).",
            file=sys.stderr,
        )
        return 1

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"portscanner: could not start the GUI: {exc}", file=sys.stderr)
        return 1

    PortScannerApp(root)
    root.mainloop()
    return 0


def cli() -> None:
    """Zipapp entry point that preserves main()'s exit status."""
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    cli()
