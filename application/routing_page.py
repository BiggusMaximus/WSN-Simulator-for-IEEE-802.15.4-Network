"""
pages/routing_page.py
======================
Routing simulation page.

Left frame  : all simulation input parameters
Right frame : 6-tab live result viewer per round:
                Network Lifetime (alive nodes) | PDR | Total Packets Sent |
                Collisions | Energy breakdown | WSN Deployment Map
"""

import os
import sys
import copy
import queue
import threading
import subprocess
import pickle
import glob
from pathlib import Path

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import yaml
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

# ── palette ───────────────────────────────────────────────────────────────────
CLR_BG       = "#1e1e2e"
CLR_PANEL    = "#2a2a3e"
CLR_ACCENT   = "#7c3aed"
CLR_ACCENT2  = "#06b6d4"
CLR_SUCCESS  = "#10b981"
CLR_WARNING  = "#f59e0b"
CLR_DANGER   = "#ef4444"
CLR_TEXT     = "#e2e8f0"
CLR_SUBTEXT  = "#94a3b8"
CLR_BORDER   = "#3f3f5a"
CLR_ENTRY_BG = "#12121e"

FONT_BODY  = ctk.CTkFont(family="Segoe UI", size=12)
FONT_BOLD  = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
FONT_TITLE = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
FONT_SMALL = ctk.CTkFont(family="Segoe UI", size=10)
FONT_MONO  = ctk.CTkFont(family="Consolas", size=9)

PROTOCOLS       = ["DirectUnslottedCSMA"]
PATH_LOSS_MODELS = ["Ideal", "LogDistance", "ITU_P1411",
                    "SUI_TypeA", "SUI_TypeB", "SUI_TypeC", "EricssonUrban"]
DEPLOY_STRATS   = ["Random", "PoissonLineCox"]

ENERGY_CATS = [
    "time_guard", "sensing", "logging", "backoff", "cca",
    "receive_packet", "transmit_packet", "transmit_ack",
    "waiting_ack", "listening_ack", "sleep",
]


# ── module-level draw() ───────────────────────────────────────────────────────
def draw(parent: ctk.CTkFrame, project_root: str, show_page_callback=None):
    """Called by app.py."""
    page = _RoutingSimPage(parent, project_root)
    page.pack(fill="both", expand=True)


# ─────────────────────────────────────────────────────────────────────────────
class _RoutingSimPage(ctk.CTkFrame):

    def __init__(self, master, project_root: str):
        super().__init__(master, fg_color=CLR_BG)
        self.project_root = Path(project_root)
        self._sim_thread: threading.Thread | None = None
        self._log_queue: queue.Queue = queue.Queue()
        self._rounds_data: list[dict] = []
        self._deploy_nodes: list = []
        self._stop_flag = False
        self._proc = None   # subprocess handle for stop

        self._build_header()

        body = ctk.CTkFrame(self, fg_color=CLR_BG)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        self._left = ctk.CTkScrollableFrame(body, width=300,
                                             fg_color=CLR_PANEL,
                                             corner_radius=10)
        self._left.pack(side="left", fill="y", padx=(0, 8))

        right = ctk.CTkFrame(body, fg_color=CLR_BG)
        right.pack(side="left", fill="both", expand=True)

        self._build_left()
        self._build_right(right)
        self._poll_log()

    # ── HEADER ───────────────────────────────────────────────────────────────
    def _build_header(self):
        h = ctk.CTkFrame(self, fg_color=CLR_ACCENT2, height=48,
                          corner_radius=0)
        h.pack(fill="x")
        h.pack_propagate(False)
        ctk.CTkLabel(h, text="📡  Routing Simulation — Full Network Lifetime",
                     font=FONT_TITLE, text_color=CLR_BG).pack(expand=True)

    # ── LEFT PANEL ────────────────────────────────────────────────────────────
    def _build_left(self):
        p = self._left

        def section(title):
            ctk.CTkLabel(p, text=title, font=FONT_BOLD,
                         text_color=CLR_ACCENT2).pack(anchor="w",
                                                       pady=(12, 2), padx=6)
            ctk.CTkFrame(p, height=1, fg_color=CLR_BORDER).pack(
                fill="x", padx=6, pady=(0, 6))

        def field(label, attr, default, widget="entry", values=None):
            ctk.CTkLabel(p, text=label, font=FONT_SMALL,
                         text_color=CLR_TEXT).pack(anchor="w", padx=8)
            if widget == "combo":
                var = ctk.StringVar(value=default)
                setattr(self, attr, var)
                ctk.CTkComboBox(p, variable=var, values=values or [],
                                state="readonly", width=270,
                                font=FONT_SMALL).pack(anchor="w",
                                                       padx=8, pady=(0, 5))
            else:
                var = ctk.StringVar(value=default)
                setattr(self, attr, var)
                ctk.CTkEntry(p, textvariable=var, width=270,
                             font=FONT_SMALL).pack(anchor="w",
                                                    padx=8, pady=(0, 5))

        # ── Simulation ────────────────────────────────────────────────────────
        section("⚙  Simulation Parameters")
        field("Simulation Name",       "v_name",     "RoutingSim")
        field("Number of Nodes",        "v_nodes",    "100")
        field("Area X = Y (m)",         "v_area",     "150")
        field("Area Height Z (m)",      "v_height",   "5")
        field("Simulation Rounds",      "v_rounds",   "200")
        field("Time Step (s)",          "v_timestep", "0.001")
        field("Battery Capacity (Ah)",  "v_battery",  "0.5")
        field("Battery Deviation (Ah)", "v_batt_dev", "0.25")

        # ── Protocol & Channel ────────────────────────────────────────────────
        section("🔌  Protocol & Channel")
        field("Routing Protocol",   "v_protocol", "DirectUnslottedCSMA",
              widget="combo", values=PROTOCOLS)
        field("Path Loss Model",    "v_pathloss",  "Ideal",
              widget="combo", values=PATH_LOSS_MODELS)
        field("Deployment Strategy","v_deploy",    "Random",
              widget="combo", values=DEPLOY_STRATS)

        # ── Options ───────────────────────────────────────────────────────────
        section("🎛  Options")
        self.v_3d      = ctk.BooleanVar(value=False)
        self.v_homog   = ctk.BooleanVar(value=True)
        self.v_sensing = ctk.BooleanVar(value=False)
        self.v_logging = ctk.BooleanVar(value=False)
        for text, var in [("3D Mode",        self.v_3d),
                          ("Homogenous Nodes",self.v_homog),
                          ("Sensing Energy",  self.v_sensing),
                          ("Logging Energy",  self.v_logging)]:
            ctk.CTkCheckBox(p, text=text, variable=var,
                             font=FONT_SMALL,
                             text_color=CLR_TEXT,
                             checkmark_color=CLR_TEXT,
                             fg_color=CLR_ACCENT,
                             hover_color=CLR_BORDER).pack(
                                 anchor="w", padx=16, pady=2)

        # ── Progress ──────────────────────────────────────────────────────────
        section("📊  Progress")
        self.progress_bar = ctk.CTkProgressBar(p, width=270)
        self.progress_bar.set(0)
        self.progress_bar.pack(anchor="w", padx=8, pady=4)

        self.status_lbl = ctk.CTkLabel(p, text="Idle", font=FONT_SMALL,
                                        text_color=CLR_SUBTEXT)
        self.status_lbl.pack(anchor="w", padx=8)

        self.log_box = ctk.CTkTextbox(p, height=130, width=270,
                                       font=FONT_MONO,
                                       fg_color=CLR_ENTRY_BG,
                                       text_color=CLR_SUBTEXT,
                                       state="disabled")
        self.log_box.pack(anchor="w", padx=8, pady=(4, 8))

        # ── Buttons ───────────────────────────────────────────────────────────
        ctk.CTkFrame(p, height=1, fg_color=CLR_BORDER).pack(
            fill="x", padx=6, pady=4)
        br = ctk.CTkFrame(p, fg_color="transparent")
        br.pack(fill="x", padx=8, pady=4)

        ctk.CTkButton(br, text="▶  Run",
                       font=FONT_BOLD, fg_color=CLR_SUCCESS,
                       hover_color="#059669",
                       command=self._run_sim).pack(
                           side="left", expand=True, fill="x", padx=(0, 3))
        ctk.CTkButton(br, text="⏹ Stop",
                       font=FONT_BOLD, fg_color=CLR_DANGER,
                       hover_color="#b91c1c",
                       command=self._stop_sim).pack(side="left", padx=3)
        ctk.CTkButton(br, text="🔄",
                       font=FONT_BOLD, fg_color=CLR_WARNING,
                       hover_color="#d97706",
                       width=40,
                       command=self._reset).pack(side="left")

        ctk.CTkLabel(p, text="").pack(pady=4)

    # ── RIGHT PANEL ───────────────────────────────────────────────────────────
    def _build_right(self, parent):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",        background=CLR_PANEL, borderwidth=0)
        style.configure("TNotebook.Tab",    background=CLR_BORDER,
                        foreground=CLR_SUBTEXT,
                        padding=[12, 5], font=("Segoe UI", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", CLR_ACCENT2)],
                  foreground=[("selected", CLR_BG)])

        self._nb = ttk.Notebook(parent)
        self._nb.pack(fill="both", expand=True)

        tab_defs = [
            ("📡 Lifetime",    "_tab_lifetime"),
            ("📶 PDR",         "_tab_pdr"),
            ("📦 Packets",     "_tab_packets"),
            ("💥 Collisions",  "_tab_collisions"),
            ("⚡ Energy",      "_tab_energy"),
            ("🗺  Deployment", "_tab_deploy"),
        ]
        self._all_tabs = []
        for title, attr in tab_defs:
            frame = tk.Frame(self._nb, bg=CLR_BG)
            self._nb.add(frame, text=title)
            setattr(self, attr, frame)
            self._all_tabs.append((frame, title))
            self._empty_tab(frame, title)

    def _empty_tab(self, frame, title):
        for w in frame.winfo_children():
            w.destroy()
        tk.Label(frame,
                 text=f"{title}\n\nRun a simulation to see per-round metrics here.",
                 fg=CLR_SUBTEXT, bg=CLR_BG,
                 font=("Segoe UI", 13)).pack(expand=True)

    # ── LOGGING ───────────────────────────────────────────────────────────────
    def _log(self, msg: str):
        self._log_queue.put(msg)

    def _poll_log(self):
        while not self._log_queue.empty():
            msg = self._log_queue.get_nowait()
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
            self.status_lbl.configure(text=msg[:65])
        self.after(200, self._poll_log)

    # ── CONTROLS ──────────────────────────────────────────────────────────────
    def _stop_sim(self):
        self._stop_flag = True
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self._log("Stop requested…")

    def _reset(self):
        self._stop_flag = True
        self._rounds_data.clear()
        self._deploy_nodes.clear()
        self.progress_bar.set(0)
        self.status_lbl.configure(text="Reset")
        for frame, title in self._all_tabs:
            self._empty_tab(frame, title)
        self._log("Reset complete.")

    # ── RUN ───────────────────────────────────────────────────────────────────
    def _run_sim(self):
        if self._sim_thread and self._sim_thread.is_alive():
            messagebox.showwarning("Busy", "Simulation already running.")
            return
        self._stop_flag = False
        self._rounds_data.clear()
        self._deploy_nodes.clear()
        self.progress_bar.set(0)
        self._reset_tab_displays()

        self._sim_thread = threading.Thread(
            target=self._worker, daemon=True)
        self._sim_thread.start()

    def _reset_tab_displays(self):
        for frame, title in self._all_tabs:
            self._empty_tab(frame, title)

    def _worker(self):
        root = self.project_root
        tmpl = root / "input" / "config" / "simulation.yaml"
        if not tmpl.exists():
            self._log(f"[ERROR] Template not found: {tmpl}")
            return

        with open(tmpl) as f:
            template = yaml.safe_load(f)

        nodes  = int(self.v_nodes.get())
        area   = int(self.v_area.get())
        height = int(self.v_height.get())
        rounds = int(self.v_rounds.get())

        cfg = copy.deepcopy(template)
        cfg["Simulation"]["name"]               = self.v_name.get()
        cfg["Simulation"]["number_of_nodes"]    = nodes
        cfg["Simulation"]["area_dimensions"]    = [area, area, height]
        cfg["Simulation"]["duration"]           = rounds
        cfg["Simulation"]["rounds"]             = rounds
        cfg["Simulation"]["time_step"]          = float(self.v_timestep.get())
        cfg["Simulation"]["is_3d"]              = bool(self.v_3d.get())
        cfg["Simulation"]["is_homogenous"]      = bool(self.v_homog.get())
        cfg["Simulation"]["is_sensing_enabled"] = bool(self.v_sensing.get())
        cfg["Simulation"]["is_logging_enabled"] = bool(self.v_logging.get())
        cfg["Routing"]["name"]                  = self.v_protocol.get()
        cfg["Channel"]["PathLoss"]["name"]      = self.v_pathloss.get()
        cfg["Deployment"]["name"]               = self.v_deploy.get()
        cfg["Deployment"]["base_station_locations"] = [
            [area / 2, area * 1.25, 5]]
        cfg["Node"]["battery_capacity"]         = float(self.v_battery.get())
        cfg["Node"]["battery_deviation"]        = float(self.v_batt_dev.get())

        yaml_name = "routing_sim.yaml"
        yaml_path = root / "input" / "config" / yaml_name
        with open(yaml_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False)

        self._log(f"Config: {yaml_name} | Nodes={nodes} | "
                  f"Area={area}m | Rounds={rounds}")
        self._log(f"Protocol: {cfg['Routing']['name']}")

        try:
            self._proc = subprocess.Popen(
                [sys.executable, str(root / "main.py"), yaml_name],
                cwd=str(root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in self._proc.stdout:
                line = line.rstrip()
                if line:
                    self._log(line[-120:])
                if self._stop_flag:
                    self._proc.terminate()
                    self._log("Terminated by user.")
                    break
            self._proc.wait()
            if self._proc.returncode not in (0, None, -15):
                self._log(f"[WARN] Process exit code {self._proc.returncode}")
            else:
                self._log("Simulation finished.")
        except Exception as exc:
            self._log(f"[ERROR] {exc}")
        finally:
            self._proc = None

        self._log("Loading results…")
        self._load_rounds(cfg)
        self._log("Rendering plots…")
        self.after(100, self._render_all)

    # ── LOAD ─────────────────────────────────────────────────────────────────
    def _load_rounds(self, cfg):
        out  = self.project_root / "output"
        tag  = (f"{cfg['Routing']['name']}_"
                f"N{cfg['Simulation']['number_of_nodes']}_"
                f"L{cfg['Simulation']['area_dimensions'][0]}")
        dirs = sorted(glob.glob(str(out / f"*{tag}*")))
        if not dirs:
            self._log(f"[WARN] No output folder for *{tag}*")
            return
        sim_folder = Path(dirs[-1])
        self._log(f"Reading: {sim_folder.name}")

        # deployment from Period-1
        dp = sim_folder / "Period-1" / "deployment.pkl"
        if dp.exists():
            self._deploy_nodes = pickle.load(open(dp, "rb"))

        period = 1
        total  = cfg["Simulation"]["duration"]
        while True:
            pdir = sim_folder / f"Period-{period}"
            if not pdir.exists():
                break

            def lpkl(name):
                fp = pdir / name
                return pickle.load(open(fp, "rb")) if fp.exists() else {}

            metrics = lpkl("metrics_results.pkl")
            tx      = lpkl("transmission_results.pkl")
            energy  = lpkl("energy_consumption_results.pkl")
            latency = lpkl("latency_results.pkl")

            total_e = sum(v for v in energy.values()
                          if isinstance(v, (int, float)))
            avg_lat = (latency.get("total_latency", 0) /
                       max(latency.get("latency_samples", 1), 1)) * 1000

            self._rounds_data.append({
                "round":       period,
                "alive":       metrics.get("alive_nodes", 0),
                "pdr":         metrics.get("pdr", 0),
                "packets":     metrics.get("total_packet_sent", 0),
                "collisions":  tx.get("collision_failure", 0),
                "energy":      total_e,
                "latency_ms":  avg_lat,
                "energy_breakdown": energy,
            })
            self.progress_bar.set(min(0.99, period / max(total, 1)))
            period += 1

        self.progress_bar.set(1.0)
        self._log(f"Loaded {len(self._rounds_data)} rounds.")

    # ── RENDER ────────────────────────────────────────────────────────────────
    def _render_all(self):
        if not self._rounds_data:
            self._log("No data to render.")
            return

        rounds = [d["round"]      for d in self._rounds_data]
        alive  = [d["alive"]      for d in self._rounds_data]
        pdr    = [d["pdr"]        for d in self._rounds_data]
        pkts   = [d["packets"]    for d in self._rounds_data]
        cols   = [d["collisions"] for d in self._rounds_data]
        energy = [d["energy"]     for d in self._rounds_data]

        self._line_plot(self._tab_lifetime, rounds, alive,
                        "Network Lifetime — Alive Nodes per Round",
                        "Round", "Alive Nodes", CLR_SUCCESS)
        self._line_plot(self._tab_pdr, rounds, pdr,
                        "PDR per Round (%)",
                        "Round", "PDR (%)", CLR_ACCENT2)
        self._line_plot(self._tab_packets, rounds, pkts,
                        "Total Packets Sent per Round",
                        "Round", "Packets", CLR_WARNING)
        self._line_plot(self._tab_collisions, rounds, cols,
                        "Collisions per Round",
                        "Round", "Collisions", CLR_DANGER)
        self._energy_plot()
        self._deploy_plot()

    def _line_plot(self, frame, xs, ys, title, xlabel, ylabel, color):
        for w in frame.winfo_children():
            w.destroy()
        fig = Figure(figsize=(8, 4.8), facecolor=CLR_BG)
        ax  = fig.add_subplot(111, facecolor=CLR_PANEL)
        ax.plot(xs, ys, color=color, linewidth=2,
                marker=".", markersize=3, markevery=max(1, len(xs)//60))
        ax.fill_between(xs, ys, alpha=0.12, color=color)
        ax.set_title(title,   color=CLR_TEXT, fontsize=12, pad=10)
        ax.set_xlabel(xlabel, color=CLR_TEXT)
        ax.set_ylabel(ylabel, color=CLR_TEXT)
        ax.tick_params(colors=CLR_TEXT)
        ax.grid(True, color=CLR_BORDER, linewidth=0.4, linestyle="--")
        for sp in ax.spines.values():
            sp.set_color(CLR_BORDER)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(canvas, frame).update()
        plt.close(fig)

    def _energy_plot(self):
        frame = self._tab_energy
        for w in frame.winfo_children():
            w.destroy()

        rounds = [d["round"] for d in self._rounds_data]
        cats   = [c for c in ENERGY_CATS
                  if any(d["energy_breakdown"].get(c, 0)
                         for d in self._rounds_data)]

        fig = Figure(figsize=(8, 4.8), facecolor=CLR_BG)
        ax  = fig.add_subplot(111, facecolor=CLR_PANEL)

        if cats:
            cmap   = plt.get_cmap("tab10")
            bottom = np.zeros(len(rounds))
            for i, cat in enumerate(cats):
                vals = np.array([d["energy_breakdown"].get(cat, 0)
                                 for d in self._rounds_data], dtype=float)
                ax.fill_between(rounds, bottom, bottom + vals,
                                label=cat, alpha=0.82,
                                color=cmap(i / len(cats)))
                bottom += vals
            ax.legend(fontsize=8, facecolor=CLR_PANEL,
                      labelcolor=CLR_TEXT, loc="upper right")
        else:
            ax.plot(rounds, [d["energy"] for d in self._rounds_data],
                    color=CLR_WARNING, linewidth=2, label="Total (J)")
            ax.legend(fontsize=8, facecolor=CLR_PANEL, labelcolor=CLR_TEXT)

        ax.set_title("Energy Consumption per Round (J)",
                     color=CLR_TEXT, fontsize=12, pad=10)
        ax.set_xlabel("Round", color=CLR_TEXT)
        ax.set_ylabel("Energy (J)", color=CLR_TEXT)
        ax.tick_params(colors=CLR_TEXT)
        ax.grid(True, color=CLR_BORDER, linewidth=0.4, linestyle="--")
        for sp in ax.spines.values():
            sp.set_color(CLR_BORDER)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(canvas, frame).update()
        plt.close(fig)

    def _deploy_plot(self):
        frame = self._tab_deploy
        for w in frame.winfo_children():
            w.destroy()

        fig = Figure(figsize=(7, 6), facecolor=CLR_BG)
        ax  = fig.add_subplot(111, facecolor=CLR_PANEL)

        if self._deploy_nodes:
            try:
                xs = [n.position[0] for n in self._deploy_nodes
                      if not n.is_base_station]
                ys = [n.position[1] for n in self._deploy_nodes
                      if not n.is_base_station]
                bx = [n.position[0] for n in self._deploy_nodes
                      if n.is_base_station]
                by = [n.position[1] for n in self._deploy_nodes
                      if n.is_base_station]
                ax.scatter(xs, ys, c=CLR_ACCENT2, s=22, alpha=0.75,
                           label=f"Sensors ({len(xs)})")
                ax.scatter(bx, by, c=CLR_DANGER, s=140,
                           marker="*", zorder=5,
                           label=f"Base Stations ({len(bx)})")
                ax.legend(facecolor=CLR_PANEL, labelcolor=CLR_TEXT, fontsize=9)
                ax.set_title("WSN Deployment Coordinates (Round 1)",
                             color=CLR_TEXT, fontsize=12, pad=10)
            except Exception as exc:
                ax.text(0.5, 0.5, f"Deployment error:\n{exc}",
                        transform=ax.transAxes, ha="center",
                        color=CLR_DANGER, fontsize=10)
        else:
            # fallback: show alive-nodes line
            rounds = [d["round"] for d in self._rounds_data]
            alive  = [d["alive"] for d in self._rounds_data]
            ax.plot(rounds, alive, color=CLR_ACCENT2, linewidth=2)
            ax.set_xlabel("Round",       color=CLR_TEXT)
            ax.set_ylabel("Alive Nodes", color=CLR_TEXT)
            ax.set_title("Alive Nodes Over Lifetime\n"
                         "(deployment.pkl not saved — enable in config)",
                         color=CLR_TEXT, fontsize=11)

        ax.tick_params(colors=CLR_TEXT)
        ax.grid(True, color=CLR_BORDER, linewidth=0.4, linestyle="--")
        for sp in ax.spines.values():
            sp.set_color(CLR_BORDER)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(canvas, frame).update()
        plt.close(fig)
