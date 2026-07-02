"""
WSN Simulation GUI
==================
A Tkinter-based GUI that lets the user edit simulation.yaml parameters
and run/visualise the simulation results – all without touching YAML by hand.

Place this file inside the v7/ folder (next to main.py) and run:
    python wsn_gui.py
"""

import os
import sys
import copy
import threading
import queue
import pickle
import traceback
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path

import yaml
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np

# ── colour palette ─────────────────────────────────────────────────────────────
CLR_BG       = "#1e1e2e"   # main background (dark navy)
CLR_PANEL    = "#2a2a3e"   # panel / frame background
CLR_ACCENT   = "#7c3aed"   # purple accent
CLR_ACCENT2  = "#06b6d4"   # cyan accent
CLR_SUCCESS  = "#10b981"   # green
CLR_WARNING  = "#f59e0b"   # amber
CLR_DANGER   = "#ef4444"   # red
CLR_TEXT     = "#e2e8f0"   # primary text
CLR_SUBTEXT  = "#94a3b8"   # secondary text
CLR_BORDER   = "#3f3f5a"   # border colour
CLR_ENTRY_BG = "#12121e"   # entry/text widget bg
CLR_BTN      = "#7c3aed"   # button face
CLR_BTN_HOV  = "#6d28d9"   # button hover


# ── helpers ────────────────────────────────────────────────────────────────────

def flatten_yaml(d, parent_key="", sep="."):
    """Flatten nested dict: {'Simulation': {'rounds': 200}} → {'Simulation.rounds': 200}"""
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_yaml(v, new_key, sep))
        else:
            items[new_key] = v
    return items


def set_nested(d, keys, value):
    """Set a value deep inside a nested dict using a list of keys."""
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    # Try to preserve original type
    orig = d.get(keys[-1])
    if orig is not None:
        try:
            if isinstance(orig, bool):
                if isinstance(value, str):
                    value = value.lower() in ("true", "1", "yes")
                else:
                    value = bool(value)
            elif isinstance(orig, int):
                value = int(float(value))
            elif isinstance(orig, float):
                value = float(value)
            elif isinstance(orig, list):
                # Parse list-like string e.g. "[150, 150, 5]"
                if isinstance(value, str):
                    import ast
                    value = ast.literal_eval(value)
        except Exception:
            pass
    d[keys[-1]] = value


def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def save_yaml(data, path):
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def styled_btn(parent, text, command, bg=CLR_BTN, fg=CLR_TEXT, **kw):
    btn = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg, activebackground=CLR_BTN_HOV, activeforeground=CLR_TEXT,
        relief="flat", cursor="hand2", padx=12, pady=6,
        font=("Segoe UI", 10, "bold"), **kw
    )
    btn.bind("<Enter>", lambda e: btn.configure(bg=CLR_BTN_HOV))
    btn.bind("<Leave>", lambda e: btn.configure(bg=bg))
    return btn


# ── section definitions ────────────────────────────────────────────────────────
# Each section groups the YAML keys the user is most likely to change.
# key  : dotted path into the YAML
# label: human-friendly label
# type : "text" | "bool" | "choice"
# opts : (optional) list of choices when type=="choice"

SECTIONS = {
    "Simulation": [
        {"key": "Simulation.name",               "label": "Simulation Name",      "type": "text"},
        {"key": "Simulation.rounds",              "label": "Rounds",               "type": "text"},
        {"key": "Simulation.number_of_nodes",     "label": "Number of Nodes",      "type": "text"},
        {"key": "Simulation.duration",            "label": "Duration (s)",         "type": "text"},
        {"key": "Simulation.area_dimensions",     "label": "Area Dimensions [x,y,z]","type": "text"},
        {"key": "Simulation.display_period",      "label": "Display Period",       "type": "text"},
        {"key": "Simulation.time_step",           "label": "Time Step",            "type": "text"},
        {"key": "Simulation.is_3d",               "label": "3D Mode",              "type": "bool"},
        {"key": "Simulation.is_homogenous",       "label": "Homogenous Nodes",     "type": "bool"},
        {"key": "Simulation.use_multiple_sensor", "label": "Multiple Sensors",     "type": "bool"},
    ],
    "Routing": [
        {"key": "Routing.name", "label": "Protocol", "type": "choice",
         "opts": ["DirectUnslottedCSMA"]},
        {"key": "Routing.params.DirectUnslottedCSMA.MAX_JITTER",
         "label": "CSMA Max Jitter (s)", "type": "text"},
    ],
    "Deployment": [
        {"key": "Deployment.name", "label": "Strategy", "type": "choice",
         "opts": ["Random", "PoissonLineCox", "UserInput"]},
        {"key": "Deployment.base_station_locations",
         "label": "Base Station Locations", "type": "text"},
        {"key": "Deployment.save_deployment", "label": "Save Deployment", "type": "bool"},
        {"key": "Deployment.params.Random.deviation",
         "label": "Random – Deviation (m)", "type": "text"},
        {"key": "Deployment.params.Random.height_default",
         "label": "Random – Height Default (m)", "type": "text"},
    ],
    "Node & Battery": [
        {"key": "Node.battery_capacity",  "label": "Battery Capacity (Ah)",  "type": "text"},
        {"key": "Node.battery_deviation", "label": "Battery Deviation (Ah)", "type": "text"},
    ],
    "RF (IEEE 802.15.4)": [
        {"key": "RF.name", "label": "RF Standard", "type": "choice",
         "opts": ["IEEE_802_15_4"]},
        {"key": "RF.params.IEEE_802_15_4.G_TX",  "label": "Tx Antenna Gain (dBi)", "type": "text"},
        {"key": "RF.params.IEEE_802_15_4.G_RX",  "label": "Rx Antenna Gain (dBi)", "type": "text"},
        {"key": "RF.params.IEEE_802_15_4.P_RX_MIN", "label": "Min Rx Power (dBm)", "type": "text"},
        {"key": "RF.params.IEEE_802_15_4.P_RX_MAX", "label": "Max Rx Power (dBm)", "type": "text"},
        {"key": "RF.params.IEEE_802_15_4.Rb",    "label": "Data Rate (kbps)",      "type": "text"},
        {"key": "RF.params.IEEE_802_15_4.macMaxCSMABackoffs", "label": "Max CSMA Backoffs", "type": "text"},
        {"key": "RF.params.IEEE_802_15_4.macMaxFrameRetries", "label": "Max Frame Retries", "type": "text"},
        {"key": "RF.params.IEEE_802_15_4.macMinBE", "label": "Min Backoff Exp", "type": "text"},
        {"key": "RF.params.IEEE_802_15_4.macMaxBE", "label": "Max Backoff Exp", "type": "text"},
        {"key": "RF.params.IEEE_802_15_4.ackEnabled", "label": "ACK Enabled",   "type": "bool"},
        {"key": "RF.params.IEEE_802_15_4.V",     "label": "Supply Voltage (V)", "type": "text"},
        {"key": "RF.params.IEEE_802_15_4.I_RX",  "label": "Rx Current (A)",    "type": "text"},
    ],
    "Channel": [
        {"key": "Channel.PathLoss.name", "label": "Path-Loss Model", "type": "choice",
         "opts": ["ITU_P1411", "LogDistance", "SUI_TypeA"]},
        {"key": "Channel.PathLoss.shadowing_sigma", "label": "Shadowing Sigma (dB)", "type": "text"},
        {"key": "Channel.Interference.name", "label": "Interference Model", "type": "choice",
         "opts": ["IEEE_802_15_4"]},
        {"key": "Channel.Interference.IEEE_802_15_4.SINR",
         "label": "Required SINR (dB)", "type": "text"},
        {"key": "Channel.Interference.IEEE_802_15_4.P_CCA",
         "label": "CCA Threshold (dBm)", "type": "text"},
    ],
    "MCU": [
        {"key": "MCU.name", "label": "MCU", "type": "choice",
         "opts": ["ESP32_C6", "STM32L476RG"]},
        {"key": "MCU.params.ESP32_C6.I_LS", "label": "ESP32 Light-Sleep Current (A)", "type": "text"},
        {"key": "MCU.params.ESP32_C6.I_MS", "label": "ESP32 Modem-Sleep Current (A)", "type": "text"},
        {"key": "MCU.params.ESP32_C6.V",    "label": "ESP32 Supply Voltage (V)",      "type": "text"},
    ],
    "Sensor": [
        {"key": "Sensor.name", "label": "Sensor", "type": "choice",
         "opts": ["BMP280", "DHT22", "DS18B20"]},
        {"key": "Sensor.params.BMP280.I_sensing", "label": "BMP280 Sensing Current (A)", "type": "text"},
        {"key": "Sensor.params.BMP280.T_sensing", "label": "BMP280 Sensing Time (s)",    "type": "text"},
        {"key": "Sensor.params.BMP280.V_sensing", "label": "BMP280 Voltage (V)",         "type": "text"},
    ],
}


# ── main application ───────────────────────────────────────────────────────────

class WSNSimGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WSN Simulation GUI  •  v7")
        self.geometry("1280x820")
        self.minsize(1100, 700)
        self.configure(bg=CLR_BG)

        # State
        self.yaml_path = tk.StringVar(value="")
        self.config_data = {}          # raw parsed YAML dict
        self._widgets = {}             # key → widget (Entry / Checkbutton / OptionMenu)
        self._vars    = {}             # key → tk.Variable
        self._sim_queue = queue.Queue()
        self._sim_thread = None
        self._results = []             # list of per-round metric dicts

        self._build_ui()
        self._try_autoload()
        self._poll_queue()

    # ── autoload ───────────────────────────────────────────────────────────────
    def _try_autoload(self):
        """Attempt to load simulation.yaml from cwd or script directory."""
        candidates = [
            Path("input/config/simulation.yaml"),
            Path(__file__).parent / "input/config/simulation.yaml",
        ]
        for p in candidates:
            if p.exists():
                self._load_yaml_from(str(p))
                return

    # ── UI skeleton ────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── top bar ────────────────────────────────────────────────────────────
        topbar = tk.Frame(self, bg=CLR_PANEL, height=54)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)

        tk.Label(topbar, text="⚡ WSN Simulator", bg=CLR_PANEL, fg=CLR_TEXT,
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=16, pady=10)

        # YAML file selector
        tk.Label(topbar, text="Config:", bg=CLR_PANEL, fg=CLR_SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="left", padx=(24, 4))
        path_entry = tk.Entry(topbar, textvariable=self.yaml_path, width=40,
                              bg=CLR_ENTRY_BG, fg=CLR_TEXT, insertbackground=CLR_TEXT,
                              relief="flat", font=("Segoe UI", 9))
        path_entry.pack(side="left", padx=2, ipady=4)
        styled_btn(topbar, "Browse", self._browse_yaml,
                   bg=CLR_BORDER).pack(side="left", padx=4)
        styled_btn(topbar, "Load", self._load_yaml,
                   bg=CLR_ACCENT2).pack(side="left", padx=4)
        styled_btn(topbar, "💾 Save YAML", self._save_yaml,
                   bg=CLR_SUCCESS).pack(side="left", padx=4)

        self._run_btn = styled_btn(topbar, "▶  Run Simulation", self._run_simulation,
                                   bg=CLR_ACCENT)
        self._run_btn.pack(side="right", padx=16)

        # status bar
        self._status_var = tk.StringVar(value="Ready")
        statusbar = tk.Frame(self, bg=CLR_PANEL, height=28)
        statusbar.pack(fill="x", side="bottom")
        statusbar.pack_propagate(False)
        tk.Label(statusbar, textvariable=self._status_var, bg=CLR_PANEL,
                 fg=CLR_SUBTEXT, font=("Segoe UI", 9), anchor="w").pack(
                     side="left", padx=12, fill="y")
        self._progress = ttk.Progressbar(statusbar, mode="indeterminate", length=180)
        self._progress.pack(side="right", padx=12, pady=4)

        # ── main pane ──────────────────────────────────────────────────────────
        pane = tk.PanedWindow(self, orient="horizontal", bg=CLR_BG,
                              sashwidth=6, sashrelief="flat")
        pane.pack(fill="both", expand=True)

        # LEFT: notebook with parameter sections
        left_frame = tk.Frame(pane, bg=CLR_BG)
        pane.add(left_frame, minsize=420)
        self._build_param_panel(left_frame)

        # RIGHT: tabbed results panel
        right_frame = tk.Frame(pane, bg=CLR_BG)
        pane.add(right_frame, minsize=520)
        self._build_results_panel(right_frame)

    # ── parameter panel ────────────────────────────────────────────────────────
    def _build_param_panel(self, parent):
        tk.Label(parent, text="⚙  Parameters", bg=CLR_BG, fg=CLR_TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(8, 2))

        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True, padx=6, pady=4)

        # ttk style tweaks
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",          background=CLR_PANEL, borderwidth=0)
        style.configure("TNotebook.Tab",      background=CLR_BORDER, foreground=CLR_SUBTEXT,
                        padding=[10, 4], font=("Segoe UI", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", CLR_ACCENT)],
                  foreground=[("selected", CLR_TEXT)])
        style.configure("TScrollbar", background=CLR_BORDER, troughcolor=CLR_PANEL)

        self._nb = nb

        for section_name, fields in SECTIONS.items():
            frame = tk.Frame(nb, bg=CLR_PANEL)
            nb.add(frame, text=section_name)
            self._build_section(frame, fields)

        # Raw YAML preview tab
        raw_frame = tk.Frame(nb, bg=CLR_PANEL)
        nb.add(raw_frame, text="Raw YAML")
        self._yaml_text = scrolledtext.ScrolledText(
            raw_frame, bg=CLR_ENTRY_BG, fg="#a5f3fc",
            insertbackground=CLR_TEXT, font=("Consolas", 9),
            relief="flat", wrap="none")
        self._yaml_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _build_section(self, parent, fields):
        canvas = tk.Canvas(parent, bg=CLR_PANEL, highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=CLR_PANEL)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_resize(e):
            canvas.itemconfig(win_id, width=e.width)
        canvas.bind("<Configure>", _on_resize)

        def _on_frame_configure(_):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _on_frame_configure)

        # Mouse wheel scrolling
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        for row_idx, field in enumerate(fields):
            key   = field["key"]
            label = field["label"]
            ftype = field["type"]
            bg_row = CLR_PANEL if row_idx % 2 == 0 else "#252538"

            row = tk.Frame(inner, bg=bg_row)
            row.pack(fill="x", padx=6, pady=1)

            tk.Label(row, text=label, width=28, anchor="w",
                     bg=bg_row, fg=CLR_TEXT,
                     font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), pady=5)

            if ftype == "bool":
                var = tk.BooleanVar()
                cb  = tk.Checkbutton(row, variable=var, bg=bg_row, fg=CLR_TEXT,
                                     activebackground=bg_row, selectcolor=CLR_ACCENT,
                                     relief="flat")
                cb.pack(side="left")
                self._vars[key]    = var
                self._widgets[key] = cb

            elif ftype == "choice":
                var  = tk.StringVar()
                opts = field.get("opts", [])
                om   = tk.OptionMenu(row, var, *opts)
                om.config(bg=CLR_ENTRY_BG, fg=CLR_TEXT, activebackground=CLR_ACCENT,
                          activeforeground=CLR_TEXT, highlightthickness=0,
                          relief="flat", font=("Segoe UI", 9))
                om["menu"].config(bg=CLR_ENTRY_BG, fg=CLR_TEXT,
                                  activebackground=CLR_ACCENT)
                om.pack(side="left", padx=4, ipadx=4)
                self._vars[key]    = var
                self._widgets[key] = om

            else:  # text
                var = tk.StringVar()
                ent = tk.Entry(row, textvariable=var, width=22,
                               bg=CLR_ENTRY_BG, fg=CLR_TEXT,
                               insertbackground=CLR_TEXT, relief="flat",
                               font=("Consolas", 9))
                ent.pack(side="left", padx=4, ipady=3)
                self._vars[key]    = var
                self._widgets[key] = ent

    # ── results panel ──────────────────────────────────────────────────────────
    def _build_results_panel(self, parent):
        tk.Label(parent, text="📊  Results", bg=CLR_BG, fg=CLR_TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(8, 2))

        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True, padx=6, pady=4)

        # ── Charts tab ────────────────────────────────────────────────────────
        chart_frame = tk.Frame(nb, bg=CLR_PANEL)
        nb.add(chart_frame, text="Charts")

        # chart selector bar
        ctrl = tk.Frame(chart_frame, bg=CLR_PANEL)
        ctrl.pack(fill="x", padx=6, pady=4)
        tk.Label(ctrl, text="Show:", bg=CLR_PANEL, fg=CLR_SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        self._chart_mode = tk.StringVar(value="Overview")
        for m in ("Overview", "Energy", "PDR", "Transmission"):
            rb = tk.Radiobutton(ctrl, text=m, variable=self._chart_mode,
                                value=m, command=self._refresh_charts,
                                bg=CLR_PANEL, fg=CLR_TEXT,
                                activebackground=CLR_PANEL,
                                selectcolor=CLR_ACCENT, relief="flat",
                                font=("Segoe UI", 9))
            rb.pack(side="left", padx=6)
        styled_btn(ctrl, "📂 Load Results", self._load_results_from_folder,
                   bg=CLR_BORDER).pack(side="right", padx=4)
        styled_btn(ctrl, "🔄 Refresh", self._refresh_charts,
                   bg=CLR_ACCENT2).pack(side="right", padx=4)

        self._fig = Figure(figsize=(7, 5), dpi=96)
        self._fig.patch.set_facecolor(CLR_PANEL)
        self._canvas = FigureCanvasTkAgg(self._fig, master=chart_frame)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)
        toolbar_frame = tk.Frame(chart_frame, bg=CLR_PANEL)
        toolbar_frame.pack(fill="x")
        NavigationToolbar2Tk(self._canvas, toolbar_frame)

        # ── Log tab ───────────────────────────────────────────────────────────
        log_frame = tk.Frame(nb, bg=CLR_PANEL)
        nb.add(log_frame, text="Console Log")
        self._log = scrolledtext.ScrolledText(
            log_frame, bg=CLR_ENTRY_BG, fg="#86efac",
            insertbackground=CLR_TEXT, font=("Consolas", 9),
            relief="flat", state="disabled")
        self._log.pack(fill="both", expand=True, padx=4, pady=4)
        styled_btn(log_frame, "Clear", lambda: self._clear_log(),
                   bg=CLR_BORDER).pack(pady=4)

        # ── Node Map tab ──────────────────────────────────────────────────────
        map_frame = tk.Frame(nb, bg=CLR_PANEL)
        nb.add(map_frame, text="Node Map")
        self._map_fig = Figure(figsize=(5, 5), dpi=90)
        self._map_fig.patch.set_facecolor(CLR_PANEL)
        self._map_canvas = FigureCanvasTkAgg(self._map_fig, master=map_frame)
        self._map_canvas.get_tk_widget().pack(fill="both", expand=True)
        styled_btn(map_frame, "🔄 Redraw Map", self._draw_node_map,
                   bg=CLR_ACCENT2).pack(pady=4)

    # ── YAML I/O ───────────────────────────────────────────────────────────────
    def _browse_yaml(self):
        path = filedialog.askopenfilename(
            title="Select simulation.yaml",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
        )
        if path:
            self.yaml_path.set(path)
            self._load_yaml_from(path)

    def _load_yaml(self):
        path = self.yaml_path.get().strip()
        if not path:
            messagebox.showwarning("No file", "Please select a YAML config file first.")
            return
        self._load_yaml_from(path)

    def _load_yaml_from(self, path):
        try:
            self.config_data = load_yaml(path)
            self.yaml_path.set(path)
            self._populate_widgets()
            self._update_raw_yaml()
            self._set_status(f"Loaded: {path}", CLR_SUCCESS)
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc))

    def _populate_widgets(self):
        flat = flatten_yaml(self.config_data)
        for key, var in self._vars.items():
            val = flat.get(key)
            if val is None:
                continue
            if isinstance(var, tk.BooleanVar):
                var.set(bool(val))
            else:
                var.set(str(val))

    def _collect_values(self):
        """Write widget values back into self.config_data (deep copy then mutate)."""
        data = copy.deepcopy(self.config_data)
        for key, var in self._vars.items():
            keys = key.split(".")
            value = var.get()
            set_nested(data, keys, value)
        return data

    def _save_yaml(self):
        path = self.yaml_path.get().strip()
        if not path:
            path = filedialog.asksaveasfilename(
                defaultextension=".yaml",
                filetypes=[("YAML", "*.yaml"), ("All files", "*.*")]
            )
            if not path:
                return
            self.yaml_path.set(path)
        try:
            data = self._collect_values()
            save_yaml(data, path)
            self.config_data = data
            self._update_raw_yaml()
            self._set_status(f"Saved → {path}", CLR_SUCCESS)
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))

    def _update_raw_yaml(self):
        txt = yaml.dump(self.config_data, default_flow_style=False, sort_keys=False)
        self._yaml_text.configure(state="normal")
        self._yaml_text.delete("1.0", "end")
        self._yaml_text.insert("1.0", txt)
        self._yaml_text.configure(state="disabled")

    # ── simulation runner ──────────────────────────────────────────────────────
    def _run_simulation(self):
        if self._sim_thread and self._sim_thread.is_alive():
            messagebox.showinfo("Busy", "Simulation is already running.")
            return

        # Save current YAML first
        self._save_yaml()
        yaml_path = self.yaml_path.get().strip()
        if not yaml_path or not Path(yaml_path).exists():
            messagebox.showerror("Error", "Config YAML not found. Please load/save first.")
            return

        self._results = []
        self._clear_log()
        self._run_btn.configure(state="disabled", text="⏳  Running…")
        self._progress.start(10)
        self._set_status("Running simulation…", CLR_WARNING)

        self._sim_thread = threading.Thread(
            target=self._sim_worker, args=(yaml_path,), daemon=True)
        self._sim_thread.start()

    def _sim_worker(self, yaml_path):
        """Run the simulation in a background thread and post results to queue."""
        try:
            # We need to import from the v7 project
            sim_dir = str(Path(yaml_path).parent.parent.parent)  # …/v7/
            if sim_dir not in sys.path:
                sys.path.insert(0, sim_dir)

            # Re-import fresh each run (important if config changed)
            import importlib
            for mod_name in list(sys.modules.keys()):
                if any(mod_name.startswith(p) for p in
                       ("utils", "abstract", "deployment", "routing",
                        "simulation", "channel", "node", "packet")):
                    del sys.modules[mod_name]

            from utils.config import load
            from utils.information import console
            from utils.save_manager import (
                create_simulation_folder, OUTPUT_FOLDER_PATH,
                NUMBER_OF_SIMULATION_PERFORMED
            )
            from abstract.channel import ChannelModel
            from deployment import create_deployment
            from routing import create_routing_protocol

            # Monkey-patch Engine to stream results back to GUI
            import simulation.simulator as sim_mod

            gui_queue = self._sim_queue
            results_collector = []

            original_run = sim_mod.Engine.run

            def patched_run(engine_self):
                rounds = engine_self.rounds
                for simulation_round in range(1, rounds + 1):
                    gui_queue.put(("log", f"[Round {simulation_round}/{rounds}]"))
                    if engine_self.channel.n_alive == 0 and simulation_round > 1:
                        gui_queue.put(("log", f"All nodes dead at round {simulation_round}!"))
                        break
                    else:
                        from utils.save_manager import create_period_folders
                        create_period_folders(simulation_round, engine_self.config)
                        engine_self.routing.run(simulation_round)

                    # Capture per-round metrics
                    r = engine_self.routing
                    snapshot = {
                        "round": simulation_round,
                        "alive_nodes":      r.metrics_results.get("alive_nodes", 0),
                        "pdr":              r.metrics_results.get("pdr", 0),
                        "remaining_energy": r.metrics_results.get("remaining_energy", 0),
                        "deviation":        r.metrics_results.get("deviation", 0),
                        "total_packet_sent":r.metrics_results.get("total_packet_sent", 0),
                    }
                    snapshot.update({f"tx_{k}": v for k, v in r.transmission_results.items()})
                    snapshot.update({f"e_{k}": v for k, v in r.energy_consumption_results.items()})
                    results_collector.append(snapshot)
                    gui_queue.put(("progress", snapshot))

            sim_mod.Engine.run = patched_run

            config = load(yaml_path)
            orig_cwd = os.getcwd()
            os.chdir(sim_dir)

            try:
                create_simulation_folder(yaml_path, config)
                deployment = create_deployment(config)
                nodes      = deployment.deploy_nodes()
                channel    = ChannelModel(config, nodes)
                routing    = create_routing_protocol(config, nodes, channel)
                sim_mod.Engine(config, channel, routing).run()
            finally:
                os.chdir(orig_cwd)
                sim_mod.Engine.run = original_run

            gui_queue.put(("done", results_collector))

        except Exception:
            gui_queue.put(("error", traceback.format_exc()))

    # ── queue polling ──────────────────────────────────────────────────────────
    def _poll_queue(self):
        try:
            while True:
                msg_type, payload = self._sim_queue.get_nowait()
                if msg_type == "log":
                    self._append_log(payload)
                elif msg_type == "progress":
                    self._results.append(payload)
                    self._refresh_charts()
                    r = payload
                    self._set_status(
                        f"Round {r['round']}  |  Alive: {r['alive_nodes']}  "
                        f"|  PDR: {r['pdr']:.1f}%  |  Energy: {r['remaining_energy']:.4f} J",
                        CLR_ACCENT2)
                elif msg_type == "done":
                    self._results = payload
                    self._refresh_charts()
                    self._draw_node_map()
                    self._run_btn.configure(state="normal", text="▶  Run Simulation")
                    self._progress.stop()
                    self._set_status(
                        f"✔ Simulation complete – {len(payload)} rounds", CLR_SUCCESS)
                elif msg_type == "error":
                    self._append_log("ERROR:\n" + payload, color="#fca5a5")
                    self._run_btn.configure(state="normal", text="▶  Run Simulation")
                    self._progress.stop()
                    self._set_status("Simulation failed – see Console Log", CLR_DANGER)
        except queue.Empty:
            pass
        self.after(150, self._poll_queue)

    # ── charts ─────────────────────────────────────────────────────────────────
    def _refresh_charts(self):
        if not self._results:
            return
        mode  = self._chart_mode.get()
        data  = self._results
        rnds  = [d["round"] for d in data]

        self._fig.clf()
        self._fig.patch.set_facecolor(CLR_PANEL)

        def _ax(pos, title, xlabel="Round", ylabel=""):
            ax = self._fig.add_subplot(pos)
            ax.set_facecolor(CLR_ENTRY_BG)
            ax.set_title(title, color=CLR_TEXT, fontsize=9, pad=6)
            ax.set_xlabel(xlabel, color=CLR_SUBTEXT, fontsize=8)
            ax.set_ylabel(ylabel, color=CLR_SUBTEXT, fontsize=8)
            ax.tick_params(colors=CLR_SUBTEXT, labelsize=7)
            for spine in ax.spines.values():
                spine.set_edgecolor(CLR_BORDER)
            ax.grid(True, color=CLR_BORDER, linewidth=0.4, linestyle="--")
            return ax

        if mode == "Overview":
            ax1 = _ax(221, "Alive Nodes", ylabel="Count")
            ax1.plot(rnds, [d["alive_nodes"] for d in data],
                     color=CLR_SUCCESS, linewidth=1.5)

            ax2 = _ax(222, "PDR (%)", ylabel="%")
            ax2.plot(rnds, [d["pdr"] for d in data],
                     color=CLR_ACCENT2, linewidth=1.5)

            ax3 = _ax(223, "Remaining Energy (J)", ylabel="Joules")
            ax3.plot(rnds, [d["remaining_energy"] for d in data],
                     color=CLR_WARNING, linewidth=1.5)
            ax3.fill_between(rnds, [d["remaining_energy"] for d in data],
                             alpha=0.15, color=CLR_WARNING)

            ax4 = _ax(224, "Battery Deviation (J)", ylabel="Std Dev")
            ax4.plot(rnds, [d["deviation"] for d in data],
                     color=CLR_DANGER, linewidth=1.5)

        elif mode == "Energy":
            energy_keys = [k for k in data[0] if k.startswith("e_")]
            ax = _ax(111, "Per-Component Energy Consumption (J)", ylabel="Joules")
            colours = plt.cm.tab10(np.linspace(0, 1, len(energy_keys)))
            for ek, col in zip(energy_keys, colours):
                label = ek.replace("e_", "").replace("_", " ")
                ax.plot(rnds, [d[ek] for d in data], label=label,
                        color=col, linewidth=1.2)
            ax.legend(fontsize=7, facecolor=CLR_PANEL, edgecolor=CLR_BORDER,
                      labelcolor=CLR_TEXT, loc="best")

        elif mode == "PDR":
            ax1 = _ax(211, "PDR (%)", ylabel="%")
            ax1.plot(rnds, [d["pdr"] for d in data],
                     color=CLR_ACCENT2, linewidth=1.5)
            ax1.axhline(y=90, color=CLR_SUCCESS, linestyle="--",
                        linewidth=0.8, label="90% target")
            ax1.legend(fontsize=7, facecolor=CLR_PANEL, edgecolor=CLR_BORDER,
                       labelcolor=CLR_TEXT)

            ax2 = _ax(212, "Total Packets Sent (bytes)", ylabel="Bytes")
            ax2.bar(rnds, [d["total_packet_sent"] for d in data],
                    color=CLR_ACCENT, alpha=0.7, width=0.8)

        elif mode == "Transmission":
            tx_keys = [k for k in data[0] if k.startswith("tx_")]
            ax = _ax(111, "Transmission Events", ylabel="Count")
            colours = plt.cm.tab10(np.linspace(0, 1, len(tx_keys)))
            for tk_key, col in zip(tx_keys, colours):
                label = tk_key.replace("tx_", "").replace("_", " ")
                ax.plot(rnds, [d[tk_key] for d in data], label=label,
                        color=col, linewidth=1.2)
            ax.legend(fontsize=7, facecolor=CLR_PANEL, edgecolor=CLR_BORDER,
                      labelcolor=CLR_TEXT, loc="best")

        self._fig.tight_layout(pad=1.4)
        self._canvas.draw_idle()

    # ── node map ───────────────────────────────────────────────────────────────
    def _draw_node_map(self):
        """Draw a synthetic node scatter map based on config parameters."""
        if not self.config_data:
            return
        cfg = self._collect_values()
        n_nodes = int(cfg.get("Simulation", {}).get("number_of_nodes", 100))
        dims    = cfg.get("Simulation", {}).get("area_dimensions", [150, 150, 5])
        if isinstance(dims, str):
            import ast; dims = ast.literal_eval(dims)
        w, h = float(dims[0]), float(dims[1])
        bs_locs = cfg.get("Deployment", {}).get("base_station_locations", [[w/2, h, 5]])
        if isinstance(bs_locs, str):
            import ast; bs_locs = ast.literal_eval(bs_locs)
        dev = float(cfg.get("Deployment", {}).get("params", {}).get("Random", {}).get("deviation", 50))

        rng = np.random.default_rng(42)
        cx, cy = w/2, h/2
        xs = np.clip(rng.normal(cx, dev, n_nodes), 0, w)
        ys = np.clip(rng.normal(cy, dev, n_nodes), 0, h)

        self._map_fig.clf()
        self._map_fig.patch.set_facecolor(CLR_PANEL)
        ax = self._map_fig.add_subplot(111)
        ax.set_facecolor(CLR_ENTRY_BG)
        ax.set_title("Node Deployment (Random preview)", color=CLR_TEXT, fontsize=9)
        ax.tick_params(colors=CLR_SUBTEXT, labelsize=7)
        for sp in ax.spines.values():
            sp.set_edgecolor(CLR_BORDER)

        ax.scatter(xs, ys, s=18, c=CLR_ACCENT2, alpha=0.7, label="Sensor node", zorder=2)
        for bs in bs_locs:
            ax.scatter(float(bs[0]), float(bs[1]), s=140, marker="^",
                       c=CLR_DANGER, zorder=5, label="Base station")
        ax.set_xlim(0, w); ax.set_ylim(0, h)
        ax.set_xlabel("X (m)", color=CLR_SUBTEXT, fontsize=8)
        ax.set_ylabel("Y (m)", color=CLR_SUBTEXT, fontsize=8)
        ax.legend(fontsize=7, facecolor=CLR_PANEL, edgecolor=CLR_BORDER, labelcolor=CLR_TEXT)
        ax.grid(True, color=CLR_BORDER, linewidth=0.3, linestyle="--")
        self._map_fig.tight_layout()
        self._map_canvas.draw_idle()

    # ── load results from saved folder ────────────────────────────────────────
    def _load_results_from_folder(self):
        folder = filedialog.askdirectory(title="Select simulation trial folder")
        if not folder:
            return
        folder = Path(folder)
        round_dirs = sorted(
            [d for d in folder.iterdir() if d.is_dir() and d.name.startswith("Round-")],
            key=lambda d: int(d.name.split("-")[1])
        )
        if not round_dirs:
            messagebox.showinfo("Empty", "No Round-N folders found in that directory.")
            return

        self._results = []
        for rdir in round_dirs:
            rnum = int(rdir.name.split("-")[1])
            snap = {"round": rnum}
            for fname, prefix in [
                ("metrics_results.pkl",          ""),
                ("transmission_results.pkl",     "tx_"),
                ("energy_consumption_results.pkl","e_"),
            ]:
                pkl = rdir / fname
                if pkl.exists():
                    with open(pkl, "rb") as f:
                        d = pickle.load(f)
                    snap.update({f"{prefix}{k}": v for k, v in d.items()})
            self._results.append(snap)

        self._refresh_charts()
        self._set_status(
            f"Loaded {len(self._results)} rounds from {folder.name}", CLR_SUCCESS)

    # ── logging ────────────────────────────────────────────────────────────────
    def _append_log(self, msg, color="#86efac"):
        self._log.configure(state="normal")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log.insert("end", f"[{ts}] {msg}\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    # ── status ─────────────────────────────────────────────────────────────────
    def _set_status(self, msg, color=CLR_SUBTEXT):
        self._status_var.set(msg)


# ── entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = WSNSimGUI()
    app.mainloop()