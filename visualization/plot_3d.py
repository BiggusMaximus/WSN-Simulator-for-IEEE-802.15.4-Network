#!/usr/bin/env python3
"""
collect_and_plot.py

Reads all TRIAL folders from ./output, groups them by (N, L),
averages the metrics across replications, and plots smooth 3D surfaces.
"""
import sys
import os
import re
import pickle
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata

# ---------- Configuration ----------
OUTPUT_BASE = "./output/"
OUTPUT_BASE = "./validation/data/ITU-R_1411_CC2420" 
OUTPUT_BASE = "./validation/data/Ideal_CC2420"      
OUTPUT_BASE = "./validation/data/SUI_Type_C_CC2420" 




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

def collect_data():
    """
    Returns a dict: data[N][L] = list of metric_values (one per replication).
    """
    results = {}
    for trial_name in os.listdir(OUTPUT_BASE):
        trial_path = os.path.join(OUTPUT_BASE, trial_name)
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

def plot_metric(metric, X, Y, Z, all_L, all_N):
    """Smooth 3D plot with interpolation."""
    # Interpolate
    L_fine = np.linspace(all_L[0], all_L[-1], 100)
    N_fine = np.linspace(all_N[0], all_N[-1], 100)
    L_grid, N_grid = np.meshgrid(L_fine, N_fine)
    points = np.column_stack((X.ravel(), Y.ravel()))
    values = Z.ravel()
    Z_fine = griddata(points, values, (L_grid, N_grid), method='cubic')

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection='3d')
    surf = ax.plot_surface(L_grid, N_grid, Z_fine, cmap='viridis', edgecolor='none', alpha=0.9)
    zmin = np.nanmin(Z_fine) * (-5) - 5


    ax.set_zlim([zmin, np.nanmax(Z_fine)])

    ax.contourf(
        L_grid, N_grid, Z_fine,
        zdir='z',
        offset=zmin,
        levels=15,
        cmap='viridis',
        alpha=0.5,
        zorder=0
    )


    ax.set_xlabel('Network Width (m)')
    ax.set_ylabel('Number of Nodes')
    ax.set_zlabel(metric)

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

    fig.colorbar(surf, shrink=0.5, aspect=10)
    ax.view_init(elev=25, azim=-135)
    plt.tight_layout()
    plt.show()

def plot_metric_vs_density_poly(metric, results, degree=5):
    densities = []
    values = []

    for (N, L), data in results.items():
        vals = data.get(metric, [])
        if len(vals) == 0:
            continue

        density = N / (L ** 2)
        densities.append(density)
        values.append(np.mean(vals))

    densities = np.array(densities)
    values = np.array(values)

    # sort from high density to low density
    idx = np.argsort(densities)[::-1]
    densities = densities[idx]
    values = values[idx]

    # Fit polynomial on log10(density)
    x_fit = np.log10(densities)
    p = np.poly1d(np.polyfit(x_fit, values, degree))

    x_smooth = np.linspace(x_fit.min(), x_fit.max(), 300)
    y_smooth = p(x_smooth)
    density_smooth = 10 ** x_smooth

    fig, ax = plt.subplots(figsize=(7, 4.5), constrained_layout=True)

    ax.scatter(
        densities,
        values,
        s=35,
        alpha=0.8,
        label="Data"
    )

    ax.plot(
        density_smooth,
        y_smooth,
        linewidth=2.2,
        label=f"Poly fit (deg={degree})"
    )

    ax.set_xscale('log')
    ax.invert_xaxis()  # highest density on the left

    ax.set_xlabel("Network Density (nodes/m²)")
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} vs Network Density")

    ax.grid(True, which='both', linestyle='--', alpha=0.35)
    ax.legend(frameon=False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.show()


def get_pareto_frontier(points, minimize_x=True, maximize_y=True):
    """
    points: list of (x, y)
    Returns nondominated points sorted by x.
    Assumes 2D Pareto frontier.
    """
    points = np.array(points, dtype=float)

    # Remove NaNs
    points = points[~np.isnan(points).any(axis=1)]
    if len(points) == 0:
        return np.empty((0, 2))

    # Sort by x
    if minimize_x:
        points = points[np.argsort(points[:, 0])]
    else:
        points = points[np.argsort(points[:, 0])[::-1]]

    frontier = []
    best_y = -np.inf if maximize_y else np.inf

    for x, y in points:
        if maximize_y:
            if y > best_y:
                frontier.append((x, y))
                best_y = y
        else:
            if y < best_y:
                frontier.append((x, y))
                best_y = y

    return np.array(frontier)


def plot_pareto_scatter(results, x_metric, y_metric,
                        x_label=None, y_label=None,
                        minimize_x=True, maximize_y=True):
    """
    Pareto scatter plot with frontier.
    x_metric: cost metric (usually minimize)
    y_metric: performance metric (usually maximize)
    """

    points = []

    for (N, L), data in results.items():
        x_vals = data.get(x_metric, [])
        y_vals = data.get(y_metric, [])

        if len(x_vals) == 0 or len(y_vals) == 0:
            continue

        x = np.mean(x_vals)
        y = np.mean(y_vals)

        if not np.isnan(x) and not np.isnan(y):
            points.append((x, y))

    if len(points) == 0:
        print(f"No valid data for Pareto plot: {x_metric} vs {y_metric}")
        return

    points = np.array(points)
    frontier = get_pareto_frontier(points, minimize_x=minimize_x, maximize_y=maximize_y)

    fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)

    # All points
    ax.scatter(
        points[:, 0],
        points[:, 1],
        s=45,
        alpha=0.7,
        label="All configurations"
    )

    # Pareto frontier
    if len(frontier) > 0:
        ax.plot(
            frontier[:, 0],
            frontier[:, 1],
            '-o',
            color='r',
            linewidth=2.2,
            markersize=5,
            label="Pareto frontier"
        )

    ax.set_xlabel(x_label if x_label else x_metric)
    ax.set_ylabel(y_label if y_label else y_metric)
    ax.set_title(f"Pareto Scatter: {y_metric} vs {x_metric}")

    ax.grid(True, linestyle='--', alpha=0.35)
    ax.legend(frameon=False)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.show()


if __name__ == "__main__":
    results = collect_data()
    if not results:
        print("No data found!")
        sys.exit(1)

    print(f"Found data for {len(results)} parameter combinations. at : {OUTPUT_BASE}")
    for metric in METRICS:
        X, Y, Z, all_L, all_N = build_grids(results, metric)

        try:
            max_idx = np.nanargmax(Z)   # ignores NaN
            max_row, max_col = np.unravel_index(max_idx, Z.shape)

            max_Z = Z[max_row, max_col]
            max_N = all_N[max_row]
            max_L = all_L[max_col]

            min_idx = np.nanargmin(Z)   # ignores NaN
            min_row, min_col = np.unravel_index(min_idx, Z.shape)

            min_Z = Z[min_row, min_col]
            min_N = all_N[min_row]
            min_L = all_L[min_col]


            print(f'''
                {metric}
                    max:    {max_Z:.2f} | N: {max_N}, L: {max_L}
                    min:    {min_Z:.2f} | N: {min_N}, L: {min_L}
                    sum:    {np.sum(Z):.2f}
                    mean:    {np.mean(Z):.2f}

            ''')
            plot_metric(metric, X, Y, Z, all_L, all_N)
            plot_metric_vs_density_poly(metric, results)
        
        except Exception as e:
            print(f"Error at {metric} caused by {e}")

    plot_pareto_scatter(
        results,
        x_metric='avg_energy_consumption',
        y_metric='pdr',
        x_label='Average Energy Consumption',
        y_label='PDR',
        minimize_x=True,
        maximize_y=True
    )

    plot_pareto_scatter(
        results,
        x_metric='avg_latency_ms',
        y_metric='pdr',
        x_label='Average Latency (ms)',
        y_label='PDR',
        minimize_x=True,
        maximize_y=True
    )

    plot_pareto_scatter(
        results,
        x_metric='avg_energy_consumption',
        y_metric='normalized_throughput',
        x_label='Average Energy Consumption',
        y_label='Throughput (kbps)',
        minimize_x=True,
        maximize_y=True
    )

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    models = [
        ("SUI_Type_C", "tab:red"),
        ("ITU_R_P1411", "tab:blue"),
        ("Ideal", "tab:green"),
    ]
    zorder = 0
    for model_name, color in models:
        SINGLE_CHANNEL_CC2420_PATHS = {
        "ITU_R_P1411"   : "../data/ITU-R_1411_CC2420", 
        "Ideal"         : "../data/Ideal_CC2420"     , 
        "SUI_Type_C"    : "../data/SUI_Type_C_CC2420",     
    }
    ""
    SINGLE_CHANNEL_CC2420_DATA = {}

    for key, val in SINGLE_CHANNEL_CC2420_PATHS.items():
        SINGLE_CHANNEL_CC2420_DATA[key] = collect_data(val)
        
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
        ax.set_zlabel(metric)

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
            loc='upper left',
            frameon=True
        )

        plt.tight_layout()
        plt.show()