import pandas as pd
import re
from matplotlib.lines import Line2D
import os
import pickle
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error
from scipy.interpolate import griddata
import numpy as np
import matplotlib.ticker as ticker
from mpl_toolkits.axes_grid1.inset_locator import zoomed_inset_axes, mark_inset
from matplotlib.ticker import AutoMinorLocator
from scipy.interpolate import griddata
from scipy.interpolate import RectBivariateSpline



METRICS = [
    'pdr',
    'total_packet_sent',
    'collision_failure',
    'avg_energy_consumption',
    'avg_latency_ms',
    'alive_nodes',
    'channel_busy_failure',
    'hidden_node_detected',
    'exposed_node_detected',
    'throughput_kbps',
    'throughput_bps',
    'normalized_throughput',
    'total_backoffs'

]


def set_ieee_style(usetex=True, backend=None):
    """
    Apply rcParams and style sheet to mimic an IEEE pgfplots figure.
    
    Parameters
    ----------
    usetex : bool
        Use LaTeX for text rendering (requires a working LaTeX installation).
    backend : str or None
        Matplotlib backend. If 'pgf', the output can be saved as .pgf for
        direct inclusion in LaTeX documents (requires 'pgf' package).
    """
    plt.style.use('seaborn-v0_8-paper')  # clean base style

    rc = {
        # Typography (IEEE standard sizes)
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'Times', 'DejaVu Serif'],
        'font.size': 8,                # base font size (8pt for IEEE)
        'axes.labelsize': 8,
        'axes.titlesize': 8,
        'legend.fontsize': 7,
        'xtick.labelsize': 7,
        'ytick.labelsize': 7,

        'text.usetex': usetex,
        'text.latex.preamble': r'\usepackage{newtxtext,newtxmath}',  # Times math

        # Figure dimensions for single-column IEEE (3.5 in width)
        'figure.dpi': 300,
        'savefig.dpi': 600,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.02,

        # Axes: full box (pgfplots default)
        'axes.linewidth': 0.6,
        'axes.grid': False,
        'axes.spines.top': True,
        'axes.spines.right': True,

        # Grid appearance (minor y grid as in pgfplots)
        'grid.alpha': 0.3,
        'grid.linestyle': ':',
        'grid.linewidth': 0.4,

        # Ticks (inward, pgfplots style)
        'xtick.direction': 'in',
        'ytick.direction': 'in',
        'xtick.major.size': 3.5,
        'ytick.major.size': 3.5,
        'xtick.minor.size': 2.0,
        'ytick.minor.size': 2.0,
        'xtick.major.width': 0.6,
        'ytick.major.width': 0.6,
        'xtick.minor.width': 0.5,
        'ytick.minor.width': 0.5,
        'xtick.top': True,
        'ytick.right': True,

        # Legend: thin black border, no fill (pgfplots legend style)
        'legend.frameon': True,
        'legend.edgecolor': 'black',
        'legend.fancybox': False,
        'legend.framealpha': 1.0,
        'legend.facecolor': 'white',   # or 'none' if you prefer transparent

        # Lines and markers
        'lines.linewidth': 0.8,
        'lines.markersize': 4,
        'lines.markeredgewidth': 0.6,
        'hatch.linewidth': 0.5,
    }

    plt.rcParams.update(rc)

    # Optionally switch to PGF backend for direct .pgf output
    if backend == 'pgf':
        plt.switch_backend('pgf')
        plt.rcParams.update({
            'pgf.texsystem': 'pdflatex',
            'pgf.rcfonts': False,
        })


def apply_pgfplots_style(ax, xlim=None, ylim=None, y_pad=0.08):
    """
    Tune a matplotlib Axes to look like a pgfplots axis.
    
    Parameters
    ----------
    ax : matplotlib.axes.Axes
    xlim, ylim : tuple, optional
        Axis limits. If None, limits are taken from the data.
    y_pad : float
        Fractional padding for the y‑axis (mimics `enlarge y limits`).
    """
    # Minor ticks on both axes
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())

    # Major tick parameters (already set globally, but ensure per-axis)
    ax.tick_params(which='both', direction='in', top=True, right=True)
    ax.tick_params(which='major', length=3.5, width=0.6)
    ax.tick_params(which='minor', length=2.0, width=0.5)

    # Grid: only y axis (typical for this kind of plot), minor grid lines optional
    ax.grid(axis='y', which='major', linestyle=':', linewidth=0.4, color='0.7')
    # Uncomment the next line to add minor y grid (very pgfplots-like)
    # ax.grid(axis='y', which='minor', linestyle=':', linewidth=0.3, color='0.85')

    # Adjust limits with automatic padding (like enlarge y limits)
    if xlim is not None:
        ax.set_xlim(xlim)
    if ylim is None:
        ymin, ymax = ax.get_ylim()
        pad = (ymax - ymin) * y_pad
        ax.set_ylim(ymin - pad, ymax + pad)
    else:
        ax.set_ylim(ylim)

    # Legend style (if legend exists, set border and no fill)
    legend = ax.get_legend()
    if legend is not None:
        legend.get_frame().set_linewidth(0.5)
        legend.get_frame().set_facecolor('none')  # transparent fill


def parse_n_l_from_trial(path):
    """
    Parse N and L from a trial folder name like:
    TRIAL - 1 - (22-06-2026) - Ideal_DirectUnslottedCSMA_N10_L10
    """

    # First try YAML file
    for f in os.listdir(path):
        if f.endswith(".yaml"):
            match = re.search(r'_N(\d+)_L(\d+)', f, re.IGNORECASE)
            if match:
                return int(match.group(1)), int(match.group(2))

    # Fallback: parse folder name
    folder_name = os.path.basename(path)

    match = re.search(r'_N(\d+)_L(\d+)', folder_name, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))

    return None, None

def get_metric_from_trial(trial_path, metric_name):
    """
    Returns the aggregated metric for one trial.
    Assumes the trial folder contains subfolders 'Period-0', 'Period-1', ...
    For each round, load the pickle files and collect the metric.
    If metric_name is 'avg_energy_consumption', we compute it from the energy file.
    """
    periods = sorted([d for d in os.listdir(trial_path)
                      if os.path.isdir(os.path.join(trial_path, d)) and d.startswith("Period-")])

    # For energy consumption, we need to compute per period
    if metric_name == 'avg_energy_consumption':
        total_energy_per_period = []
        for period in periods:
            energy_file = os.path.join(trial_path, period, 'energy_consumption_results.pkl')
            if os.path.exists(energy_file):
                with open(energy_file, 'rb') as f:
                    energies = pickle.load(f)
                total = sum(v * 1e3 for v in energies.values())  # J to mJ?
                total_energy_per_period.append(total / len(energies))  # per-node average?
        if total_energy_per_period:
            return np.mean(total_energy_per_period)
        else:
            return np.nan

    # For all other metrics stored in metrics_results.pkl or transmission_results.pkl
    values = []
    for period in periods:
        # metrics
        metrics_file = os.path.join(trial_path, period, 'metrics_results.pkl')
        if os.path.exists(metrics_file):
            with open(metrics_file, 'rb') as f:
                data = pickle.load(f)
                if metric_name in data:
                    values.append(float(data[metric_name]))

        # transmission results
        trans_file = os.path.join(trial_path, period, 'transmission_results.pkl')
        if os.path.exists(trans_file):
            with open(trans_file, 'rb') as f:
                data = pickle.load(f)
                if metric_name in data:
                    values.append(float(data[metric_name]))

    if values:
        # The user's original aggregation: for PDR they average over rounds,
        # for alive_nodes they take the last round's value.
        # Here we just return the overall mean; adjust if needed.
        if metric_name == 'alive_nodes':
            return values[-1]  # last round only
        return np.mean(values)
    else:
        return np.nan

def collect_data(path):
    """
    Returns a dict: data[N][L] = list of metric_values (one per replication).
    """
    results = {}
    for trial_name in os.listdir(path):
        trial_path = os.path.join(path, trial_name)
        if not os.path.isdir(trial_path) or not trial_name.startswith("TRIAL"):
            continue

        N, L = parse_n_l_from_trial(trial_path)
        if N is None or L is None:
            continue

        # Get all metrics for this trial
        metrics_vals = {}
        for m in METRICS:
            val = get_metric_from_trial(trial_path, m)
            if not np.isnan(val):
                metrics_vals[m] = val

        key = (N, L)
        if key not in results:
            results[key] = {m: [] for m in METRICS}
        for m, v in metrics_vals.items():
            results[key][m].append(v)

    return results


def build_grids(results, metric):
    """Build X, Y, Z (mean) arrays for the chosen metric."""
    # Find unique N and L
    all_N = sorted(set(k[0] for k in results))
    all_L = sorted(set(k[1] for k in results))

    Z_mean = np.zeros((len(all_N), len(all_L)))
    for i, n in enumerate(all_N):
        for j, l in enumerate(all_L):
            vals = results.get((n, l), {}).get(metric, [])
            if vals:
                Z_mean[i, j] = np.mean(vals)
            else:
                Z_mean[i, j] = np.nan

    X, Y = np.meshgrid(all_L, all_N)  # careful: N is y-axis, L is x-axis
    return X, Y, Z_mean, all_L, all_N

set_ieee_style(usetex=True, backend=None)



SINGLE_CHANNEL_CC2420_PATHS = {
    "ITU_R_P1411"   : "../data/ITU-R_1411_CC2420", 
    "Ideal"         : "../data/Ideal_CC2420"     , 
    "SUI_Type_C"    : "../data/SUI_Type_C_CC2420",     
}
""
SINGLE_CHANNEL_CC2420_DATA = {}

for key, val in SINGLE_CHANNEL_CC2420_PATHS.items():
    SINGLE_CHANNEL_CC2420_DATA[key] = collect_data(val)
    


metric = 'pdr'

fig = plt.figure(figsize=(10, 7))
ax = fig.add_subplot(111, projection='3d')
models = [
    ("SUI_Type_C", "tab:red"),
    ("ITU_R_P1411", "tab:blue"),
    ("Ideal", "tab:green"),
]
zorder = 0
for model_name, color in models:

    X, Y, Z, L_values, N_values = build_grids(
        SINGLE_CHANNEL_CC2420_DATA[model_name],
        metric
    )

    # Fine interpolation grid
    L_fine = np.linspace(min(L_values), max(L_values), 100)
    N_fine = np.linspace(min(N_values), max(N_values), 100)

    L_grid, N_grid = np.meshgrid(L_fine, N_fine)

    points = np.column_stack((X.ravel(), Y.ravel()))
    values = Z.ravel()

    Z_fine = griddata(
        points,
        values,
        (L_grid, N_grid),
        method='cubic'
    )

    # Surface
    ax.plot_surface(
        L_grid,
        N_grid,
        Z_fine,
        color=color,
        alpha=0.5,
        linewidth=0,
        antialiased=True,
        zorder=zorder
    )

    # Wireframe
    ax.plot_wireframe(
        L_grid,
        N_grid,
        Z_fine,
        color=color,
        linewidth=0.5,
        rstride=5,
        cstride=5,
        alpha=0.8
    )

    # Original data points
    ax.scatter(
        X,
        Y,
        Z,
        color=color,
        s=25,
        depthshade=True
    )
    zorder += 1
# Labels
ax.set_xlabel('Network Width (m)')
ax.set_ylabel('Number of Nodes')
ax.set_zlabel('PDR [%]')

# Nice viewing angle
ax.view_init(elev=25, azim=-135)

# Cleaner background
ax.xaxis.pane.fill = False
ax.yaxis.pane.fill = False
ax.zaxis.pane.fill = False

# Remove pane borders
ax.xaxis.pane.set_edgecolor('white')
ax.yaxis.pane.set_edgecolor('white')
ax.zaxis.pane.set_edgecolor('white')

# Hide 3D grid completely
ax.xaxis._axinfo["grid"]['linewidth'] = 0
ax.yaxis._axinfo["grid"]['linewidth'] = 0
ax.zaxis._axinfo["grid"]['linewidth'] = 0

# Legend
legend_elements = [
    Line2D([0], [0], color='tab:green', lw=3, label='Ideal'),
    Line2D([0], [0], color='tab:blue', lw=3, label='ITU-R P.1411'),
    Line2D([0], [0], color='tab:red', lw=3, label='SUI Type-C')
]

ax.legend(
    handles=legend_elements,
    loc='best',
)

ax.set_box_aspect(aspect=None, zoom=0.95)

plt.tight_layout()
plt.show()