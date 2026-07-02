"""
pages/parametric_study_page.py
================================
Parametric study page.

Left frame  : simulation inputs + node-count range + area-dimension range
Right frame : 6-tab result viewer with 3-D contour plots (energy, latency,
              total packets, PDR, collisions) and WSN deployment map.

Round is forced to 1 — we only want the first simulation period.
"""

import os
import sys
import copy
import queue
import threading
import subprocess
import pickle
import itertools
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
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

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

FONT_BODY  = ctk.CTkFont("Segoe UI", size=12)
FONT_BOLD  = ctk.CTkFont("Segoe UI", size=12, weight="bold")
FONT_TITLE = ctk.CTkFont("Segoe UI", size=14, weight="bold")
FONT_SMALL = ctk.CTkFont("Segoe UI", size=10)

PROTOCOLS = [
    "DirectUnslottedCSMA",
]
PATH_LOSS_MODELS = ["Ideal", "LogDistance", "ITU_P1411",
                    "SUI_TypeA", "SUI_TypeB", "SUI_TypeC", "EricssonUrban"]
DEPLOY_STRATEGIES = ["Random", "PoissonLineCox"]


# ── module-level draw() ───────────────────────────────────────────────────────
def draw(parent: ctk.CTkFrame, project_root: str, show_page_callback=None):
    """Called by app.py.  Populates *parent* with the parametric study page."""
    page = _ParametricStudyPage(parent, project_root)
    page.pack(fill="both", expand=True)


# ─────────────────────────────────────────────────────────────────────────────
class _ParametricStudyPage(ctk.CTkFrame):

    def __init__(self, master, project_root: str):
        super().__init__(master, fg_color=CLR_BG)
        self.project_root = Path(project_root)
        self._sim_thread: threading.Thread | None = None
        self._log_queue: queue.Queue = queue.Queue()
        self._results: dict = {}       # key=(nodes, area) → metric dict
        self._deploy_data: dict = {}   # key=(nodes, area) → node list
        self._stop_flag = False

        self._build_header()

        # body: left panel + right notebook
        body = ctk.CTkFrame(self, fg_color=CLR_BG)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        self._left_panel = ctk.CTkScrollableFrame(
            body, width=300, fg_color=CLR_PANEL, corner_radius=10)
        self._left_panel.pack(side="left", fill="y", padx=(0, 8))

        right = ctk.CTkFrame(body, fg_color=CLR_BG)
        right.pack(side="left", fill="both", expand=True)

        self._build_left()
        self._build_right(right)

        self._poll_log()

    # ── header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        h = ctk.CTkFrame(self, fg_color=CLR_ACCENT, height=48, corner_radius=0)
        h.pack(fill="x")
        h.pack_propagate(False)
        ctk.CTkLabel(h, text="📊  Parametric Study — Round 1 Only",
                     font=FONT_TITLE, text_color=CLR_TEXT).pack(expand=True)

    # ── LEFT PANEL ────────────────────────────────────────────────────────────
    def _build_left(self):
        p = self._left_panel

        def section(title):
            ctk.CTkLabel(p, text=title, font=FONT_BOLD,
                         text_color=CLR_ACCENT2).pack(anchor="w",
                                                       pady=(14, 2), padx=6)
            ctk.CTkFrame(p, height=1, fg_color=CLR_BORDER).pack(
                fill="x", padx=6, pady=(0, 6))

        def field(label_text, attr_name, default, widget="entry", values=None):
            ctk.CTkLabel(p, text=label_text, font=FONT_SMALL,
                         text_color=CLR_TEXT).pack(anchor="w", padx=8)
            if widget == "combo":
                var = ctk.StringVar(value=default)
                setattr(self, attr_name, var)
                ctk.CTkComboBox(p, variable=var, values=values or [],
                                state="readonly", width=260,
                                font=FONT_SMALL).pack(anchor="w", padx=8,
                                                       pady=(0, 6))
            else:
                var = ctk.StringVar(value=default)
                setattr(self, attr_name, var)
                ctk.CTkEntry(p, textvariable=var, width=260,
                             font=FONT_SMALL).pack(anchor="w", padx=8,
                                                    pady=(0, 6))

        # ── Simulation Parameters ─────────────────────────────────────────────
        section("⚙  Simulation Parameters")
        field("Simulation Name",    "v_name",       "ParametricStudy")
        field("Routing Protocol",   "v_protocol",   "DirectUnslottedCSMA",
              widget="combo", values=PROTOCOLS)
        field("Path Loss Model",    "v_pathloss",   "Ideal",
              widget="combo", values=PATH_LOSS_MODELS)
        field("Deployment Strategy","v_deploy",     "Random",
              widget="combo", values=DEPLOY_STRATEGIES)
        field("Battery Capacity (Ah)", "v_battery", "0.5")
        field("Time Step (s)",      "v_timestep",   "0.001")

        # ── Node Count Range ──────────────────────────────────────────────────
        section("🔢  Node Count Variations")

        row1 = ctk.CTkFrame(p, fg_color="transparent")
        row1.pack(anchor="w", padx=8, pady=(0, 2))
        for lbl, attr, val in [("From", "v_nfrom", "50"),
                                ("To",   "v_nto",   "250"),
                                ("Step", "v_nstep", "100")]:
            ctk.CTkLabel(row1, text=lbl, font=FONT_SMALL,
                         text_color=CLR_TEXT).pack(side="left")
            var = ctk.StringVar(value=val)
            setattr(self, attr, var)
            ctk.CTkEntry(row1, textvariable=var, width=60,
                         font=FONT_SMALL).pack(side="left", padx=(2, 8))

        ctk.CTkLabel(p, text="Or comma-list (overrides range):",
                     font=FONT_SMALL, text_color=CLR_SUBTEXT).pack(
                         anchor="w", padx=8)
        self.v_nlist = ctk.StringVar(value="")
        ctk.CTkEntry(p, textvariable=self.v_nlist, width=260,
                     font=FONT_SMALL,
                     placeholder_text="e.g. 50,100,200").pack(
                         anchor="w", padx=8, pady=(0, 6))

        # ── Area Dimension Range ──────────────────────────────────────────────
        section("📐  Area Dimension Variations (m)")

        row2 = ctk.CTkFrame(p, fg_color="transparent")
        row2.pack(anchor="w", padx=8, pady=(0, 2))
        for lbl, attr, val in [("From", "v_afrom", "100"),
                                ("To",   "v_ato",   "400"),
                                ("Step", "v_astep", "150")]:
            ctk.CTkLabel(row2, text=lbl, font=FONT_SMALL,
                         text_color=CLR_TEXT).pack(side="left")
            var = ctk.StringVar(value=val)
            setattr(self, attr, var)
            ctk.CTkEntry(row2, textvariable=var, width=60,
                         font=FONT_SMALL).pack(side="left", padx=(2, 8))

        ctk.CTkLabel(p, text="Or comma-list (overrides range):",
                     font=FONT_SMALL, text_color=CLR_SUBTEXT).pack(
                         anchor="w", padx=8)
        self.v_alist = ctk.StringVar(value="")
        ctk.CTkEntry(p, textvariable=self.v_alist, width=260,
                     font=FONT_SMALL,
                     placeholder_text="e.g. 100,200,300").pack(
                         anchor="w", padx=8, pady=(0, 6))

        # ── Progress ──────────────────────────────────────────────────────────
        section("📋  Progress")
        self.progress_bar = ctk.CTkProgressBar(p, width=260)
        self.progress_bar.set(0)
        self.progress_bar.pack(anchor="w", padx=8, pady=4)

        self.status_lbl = ctk.CTkLabel(p, text="Idle", font=FONT_SMALL,
                                        text_color=CLR_SUBTEXT)
        self.status_lbl.pack(anchor="w", padx=8)

        self.log_box = ctk.CTkTextbox(p, height=120, width=260,
                                       font=ctk.CTkFont("Consolas", 9),
                                       fg_color=CLR_ENTRY_BG,
                                       text_color=CLR_SUBTEXT,
                                       state="disabled")
        self.log_box.pack(anchor="w", padx=8, pady=(4, 8))

        # ── Buttons ───────────────────────────────────────────────────────────
        ctk.CTkFrame(p, height=1, fg_color=CLR_BORDER).pack(
            fill="x", padx=6, pady=6)
        btn_row = ctk.CTkFrame(p, fg_color="transparent")
        btn_row.pack(fill="x", padx=8, pady=4)

        ctk.CTkButton(btn_row, text="▶  Run Study",
                       font=FONT_BOLD, fg_color=CLR_SUCCESS,
                       hover_color="#059669",
                       command=self._run_study).pack(
                           side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(btn_row, text="🔄 Clear",
                       font=FONT_BOLD, fg_color=CLR_WARNING,
                       hover_color="#d97706",
                       command=self._clear_results).pack(side="left")

        ctk.CTkLabel(p, text="").pack(pady=4)  # bottom padding

    # ── RIGHT PANEL ───────────────────────────────────────────────────────────
    def _build_right(self, parent):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",        background=CLR_PANEL, borderwidth=0)
        style.configure("TNotebook.Tab",    background=CLR_BORDER,
                        foreground=CLR_SUBTEXT,
                        padding=[12, 5], font=("Segoe UI", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", CLR_ACCENT)],
                  foreground=[("selected", CLR_TEXT)])

        self._notebook = ttk.Notebook(parent)
        self._notebook.pack(fill="both", expand=True)

        self._tab_frames = {}
        tab_defs = [
            ("⚡ Energy",     "energy"),
            ("🕒 Latency",    "latency"),
            ("📦 Packets",    "packets"),
            ("📶 PDR",        "pdr"),
            ("💥 Collisions", "collisions"),
            ("🗺  Deployment","deploy"),
        ]
        for title, key in tab_defs:
            frame = tk.Frame(self._notebook, bg=CLR_BG)
            self._notebook.add(frame, text=title)
            self._tab_frames[key] = frame
            self._show_placeholder(frame, title)

    def _show_placeholder(self, frame, title):
        for w in frame.winfo_children():
            w.destroy()
        tk.Label(frame,
                 text=f"{title}\n\nRun a parametric study to see 3-D results here.",
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

    # ── PARSE RANGES ──────────────────────────────────────────────────────────
    def _parse_range(self, from_v, to_v, step_v, list_v) -> list[int]:
        raw = list_v.get().strip()
        if raw:
            return [int(x.strip()) for x in raw.split(",") if x.strip()]
        return list(range(int(from_v.get()),
                          int(to_v.get()) + 1,
                          int(step_v.get())))

    # ── RUN ───────────────────────────────────────────────────────────────────
    def _run_study(self):
        if self._sim_thread and self._sim_thread.is_alive():
            messagebox.showwarning("Busy", "A study is already running.")
            return
        try:
            node_counts = self._parse_range(
                self.v_nfrom, self.v_nto, self.v_nstep, self.v_nlist)
            area_vals   = self._parse_range(
                self.v_afrom, self.v_ato, self.v_astep, self.v_alist)
        except ValueError as exc:
            messagebox.showerror("Input Error", f"Invalid range: {exc}")
            return
        if not node_counts or not area_vals:
            messagebox.showerror("Input Error", "Ranges must not be empty.")
            return

        self._results.clear()
        self._deploy_data.clear()
        self.progress_bar.set(0)
        self._stop_flag = False

        self._sim_thread = threading.Thread(
            target=self._worker, args=(node_counts, area_vals), daemon=True)
        self._sim_thread.start()

    def _worker(self, node_counts, area_vals):
        root = self.project_root
        tmpl_path = root / "input" / "config" / "simulation.yaml"
        if not tmpl_path.exists():
            self._log(f"[ERROR] Template not found: {tmpl_path}")
            return

        with open(tmpl_path) as f:
            template = yaml.safe_load(f)

        combos = list(itertools.product(node_counts, area_vals))
        total  = len(combos)
        self._log(f"Parametric study: {total} combinations (1 round each)")

        for idx, (nodes, area) in enumerate(combos):
            if self._stop_flag:
                self._log("Stopped by user.")
                break
            self.progress_bar.set(idx / total)
            self._log(f"[{idx+1}/{total}] nodes={nodes}, area={area}m…")

            cfg = copy.deepcopy(template)
            cfg["Simulation"]["name"]               = (
                f"{self.v_name.get()}_n{nodes}_a{area}")
            cfg["Simulation"]["number_of_nodes"]    = nodes
            cfg["Simulation"]["area_dimensions"]    = [area, area, 5]
            cfg["Simulation"]["rounds"]             = 1
            cfg["Simulation"]["duration"]           = 1
            cfg["Routing"]["name"]                  = self.v_protocol.get()
            cfg["Deployment"]["base_station_locations"] = [
                [area / 2, area * 1.25, 5]]
            cfg["Node"]["battery_capacity"]         = float(
                self.v_battery.get())
            cfg["Simulation"]["time_step"]          = float(
                self.v_timestep.get())
            cfg["Channel"]["PathLoss"]["name"]      = self.v_pathloss.get()
            cfg["Deployment"]["name"]               = self.v_deploy.get()

            yaml_name = f"ps_n{nodes}_a{area}.yaml"
            yaml_path = root / "input" / "config" / yaml_name
            with open(yaml_path, "w") as f:
                yaml.dump(cfg, f, default_flow_style=False)

            try:
                result = subprocess.run(
                    [sys.executable, str(root / "main.py"), yaml_name],
                    cwd=str(root), timeout=300,
                    capture_output=True, text=True)
                if result.returncode == 0:
                    self._log(f"  ✓ Done")
                else:
                    err = (result.stderr or result.stdout or "")[-200:]
                    self._log(f"  ✗ Exit {result.returncode}: {err}")
                    continue
            except subprocess.TimeoutExpired:
                self._log("  ✗ Timeout (300 s)")
                continue
            except Exception as exc:
                self._log(f"  ✗ {exc}")
                continue

            self._collect(nodes, area, cfg)

        self.progress_bar.set(1.0)
        self._log("Study complete — rendering plots…")
        self.after(100, self._plot_all)

    def _collect(self, nodes, area, cfg):
        output_dir = self.project_root / "output"
        tag        = f"{cfg['Routing']['name']}_N{nodes}_L{area}"
        matches    = sorted(glob.glob(str(output_dir / f"*{tag}*" / "Period-1")))
        if not matches:
            self._log(f"  ⚠ No Period-1 output for n={nodes}, a={area}")
            return
        pdir = Path(matches[-1])

        def lpkl(name):
            fp = pdir / name
            return pickle.load(open(fp, "rb")) if fp.exists() else {}

        metrics = lpkl("metrics_results.pkl")
        tx      = lpkl("transmission_results.pkl")
        energy  = lpkl("energy_consumption_results.pkl")
        latency = lpkl("latency_results.pkl")

        total_e  = sum(v for v in energy.values()
                       if isinstance(v, (int, float)))
        avg_lat  = (latency.get("total_latency", 0) /
                    max(latency.get("latency_samples", 1), 1)) * 1000
        total_pk = metrics.get("total_packet_sent", 0)
        pdr      = metrics.get("pdr", 0)
        cols     = tx.get("collision_failure", 0)

        self._results[(nodes, area)] = {
            "energy": total_e, "latency_ms": avg_lat,
            "packets": total_pk, "pdr": pdr, "collisions": cols,
        }

        dep_path = pdir.parent / "deployment.pkl"
        if dep_path.exists():
            self._deploy_data[(nodes, area)] = pickle.load(
                open(dep_path, "rb"))

    # ── CLEAR ─────────────────────────────────────────────────────────────────
    def _clear_results(self):
        self._stop_flag = True
        self._results.clear()
        self._deploy_data.clear()
        self.progress_bar.set(0)
        self.status_lbl.configure(text="Cleared")
        label_map = {
            "energy": "⚡ Energy",       "latency": "🕒 Latency",
            "packets": "📦 Packets",      "pdr": "📶 PDR",
            "collisions": "💥 Collisions","deploy": "🗺  Deployment",
        }
        for key, frame in self._tab_frames.items():
            self._show_placeholder(frame, label_map[key])
        self._log("Cleared.")

    # ── PLOT ALL ──────────────────────────────────────────────────────────────
    def _plot_all(self):
        if not self._results:
            self._log("No results to display.")
            return

        keys  = list(self._results.keys())
        nodes = sorted({k[0] for k in keys})
        areas = sorted({k[1] for k in keys})

        specs = {
            "energy":     ("⚡ Total Energy (J)",    "plasma"),
            "latency_ms": ("🕒 Avg Latency (ms)",    "viridis"),
            "packets":    ("📦 Total Packets Sent",  "cool"),
            "pdr":        ("📶 PDR (%)",             "RdYlGn"),
            "collisions": ("💥 Collisions",          "Reds"),
        }
        tab_key_map = {
            "energy": "energy", "latency_ms": "latency",
            "packets": "packets", "pdr": "pdr", "collisions": "collisions",
        }
        for mk, (label, cmap) in specs.items():
            self._plot_3d(self._tab_frames[tab_key_map[mk]],
                          nodes, areas, mk, label, cmap)

        self._plot_deploy(self._tab_frames["deploy"], nodes, areas)
        self._log("All plots rendered.")

    def _plot_3d(self, frame, nodes, areas, metric, label, cmap):
        for w in frame.winfo_children():
            w.destroy()

        fig = plt.Figure(figsize=(7, 5), facecolor=CLR_BG)
        ax  = fig.add_subplot(111, projection="3d", facecolor=CLR_PANEL)

        N, A   = np.meshgrid(np.array(nodes, float), np.array(areas, float))
        Z      = np.zeros_like(N)
        for i, a in enumerate(areas):
            for j, n in enumerate(nodes):
                Z[i, j] = float(self._results.get((n, a), {}).get(metric, 0))

        surf = ax.plot_surface(N, A, Z, cmap=cmap, alpha=0.88,
                               linewidth=0, antialiased=True)
        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10, label=label)
        ax.set_xlabel("Nodes",    color=CLR_TEXT, labelpad=8)
        ax.set_ylabel("Area (m)", color=CLR_TEXT, labelpad=8)
        ax.set_zlabel(label,      color=CLR_TEXT, labelpad=8)
        ax.set_title(label,       color=CLR_TEXT, pad=12)
        ax.tick_params(colors=CLR_TEXT)
        for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
            pane.fill = False
            pane.set_edgecolor(CLR_BORDER)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(canvas, frame).update()
        plt.close(fig)

    def _plot_deploy(self, frame, nodes, areas):
        for w in frame.winfo_children():
            w.destroy()

        rows, cols = len(areas), len(nodes)
        if rows == 0 or cols == 0:
            tk.Label(frame, text="No deployment data.",
                     fg=CLR_SUBTEXT, bg=CLR_BG).pack(expand=True)
            return

        fig, axes = plt.subplots(
            rows, cols,
            figsize=(max(4, cols * 3), max(3, rows * 2.8)),
            facecolor=CLR_BG, squeeze=False,
        )
        for i, a in enumerate(areas):
            for j, n in enumerate(nodes):
                ax = axes[i][j]
                ax.set_facecolor(CLR_PANEL)
                ax.set_title(f"N={n}, A={a}m", color=CLR_TEXT, fontsize=7)
                ax.tick_params(colors=CLR_TEXT, labelsize=5)

                dep = self._deploy_data.get((n, a))
                res = self._results.get((n, a), {})
                if dep:
                    try:
                        xs = [nd.position[0] for nd in dep
                              if not nd.is_base_station]
                        ys = [nd.position[1] for nd in dep
                              if not nd.is_base_station]
                        bx = [nd.position[0] for nd in dep
                              if nd.is_base_station]
                        by = [nd.position[1] for nd in dep
                              if nd.is_base_station]
                        ax.scatter(xs, ys, c=CLR_ACCENT2, s=6, alpha=0.7)
                        ax.scatter(bx, by, c=CLR_DANGER, s=50, marker="*",
                                   zorder=5)
                    except Exception:
                        ax.text(0.5, 0.5, "N/A",
                                transform=ax.transAxes, ha="center",
                                color=CLR_SUBTEXT, fontsize=7)
                else:
                    ax.text(0.5, 0.5,
                            f"E={res.get('energy', 0):.2f}J\n"
                            f"PDR={res.get('pdr', 0):.1f}%",
                            transform=ax.transAxes,
                            ha="center", va="center",
                            color=CLR_TEXT, fontsize=7)

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(canvas, frame).update()
        plt.close(fig)
