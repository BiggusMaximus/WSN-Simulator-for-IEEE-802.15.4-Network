import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.ticker import AutoMinorLocator
from matplotlib.widgets import Slider

# ---------- IEEE paper style settings ----------
plt.rcParams.update({
    "text.usetex": True,
    "font.family": "serif",
    "font.serif": ["Times New Roman"],
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02
})

# ---------- Generate random 3D positions ----------
def generate_random_positions(n_nodes, seed=42):
    """Generate random 3D positions in [0, 100] cube, fixed seed for reproducibility."""
    np.random.seed(seed)
    pos = {}
    for i in range(n_nodes):
        pos[i] = np.random.uniform(1, 100, size=3)
    return pos

# ---------- Create graph based on connectivity radius ----------
def create_graph(n_nodes, radius, pos):
    G = nx.Graph()
    G.add_nodes_from(range(n_nodes))
    for i in range(n_nodes):
        for j in range(i+1, n_nodes):
            dist = np.linalg.norm(pos[i] - pos[j])
            if dist < radius:
                G.add_edge(i, j)
    return G

# ---------- Main interactive plotting function ----------
def plot_3d_network_interactive():
    # Initial parameters
    init_n_nodes = 50
    init_radius = 50

    # Generate initial positions and graph
    pos = generate_random_positions(init_n_nodes)
    G = create_graph(init_n_nodes, init_radius, pos)

    # Create figure and 3D axes
    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection='3d')
    plt.subplots_adjust(bottom=0.25)  # make room for sliders

    # Store current state
    state = {'pos': pos, 'G': G}

    def draw_graph():
        """Clear axes and redraw the network."""
        ax.clear()
        G = state['G']
        pos = state['pos']

        # Draw edges as bending arcs
        for u, v in G.edges():
            start = np.array(pos[u])
            end = np.array(pos[v])
            midpoint = (start + end) / 2
            vector = end - start
            distance = np.linalg.norm(vector)
            if distance > 0:
                if abs(vector[0]) < 0.1 and abs(vector[1]) < 0.1:
                    perp = np.array([1, 0, 0])
                else:
                    perp = np.array([-vector[1], vector[0], 0])
                perp = perp / np.linalg.norm(perp)
            else:
                perp = np.array([0, 0, 0])
            bulge_factor = 0.25
            control_point = midpoint + perp * (distance * bulge_factor)
            t = np.linspace(0, 1, 50)
            x = (1-t)**2 * start[0] + 2*(1-t)*t * control_point[0] + t**2 * end[0]
            y = (1-t)**2 * start[1] + 2*(1-t)*t * control_point[1] + t**2 * end[1]
            z = (1-t)**2 * start[2] + 2*(1-t)*t * control_point[2] + t**2 * end[2]
            ax.plot(x, y, z, color='blue', linewidth=0.1, alpha=0.8)

        # Draw nodes
        xs = [pos[n][0] for n in G.nodes()]
        ys = [pos[n][1] for n in G.nodes()]
        zs = [pos[n][2] for n in G.nodes()]
        scatter = ax.scatter(xs, ys, zs, s=5, c='white',
                             edgecolors='black', linewidth=0.1)

        # Axes appearance (IEEE style)
        ax.set_xlabel('X', labelpad=5)
        ax.set_ylabel('Y', labelpad=5)
        ax.set_zlabel('Z', labelpad=5)
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor('w')
        ax.yaxis.pane.set_edgecolor('w')
        ax.zaxis.pane.set_edgecolor('w')
        ax.set_axis_off()
        ax.grid(False)

        # Set view angle
        ax.view_init(elev=20, azim=45)
        fig.canvas.draw_idle()

    # Draw initial graph
    draw_graph()

    # ---------- Sliders ----------
    # Slider for number of nodes (integer)
    ax_n = plt.axes([0.2, 0.1, 0.65, 0.03])
    slider_n = Slider(ax_n, 'Nodes', 10, 100, valinit=init_n_nodes, valstep=1)

    # Slider for radius
    ax_r = plt.axes([0.2, 0.05, 0.65, 0.03])
    slider_r = Slider(ax_r, 'Radius', 10, 100, valinit=init_radius, valstep=1)

    def update_nodes(val):
        n = int(slider_n.val)
        state['pos'] = generate_random_positions(n, seed=42)  # fixed seed for consistency
        state['G'] = create_graph(n, slider_r.val, state['pos'])
        draw_graph()

    def update_radius(val):
        r = slider_r.val
        n = len(state['pos'])  # keep same positions
        state['G'] = create_graph(n, r, state['pos'])
        draw_graph()

    slider_n.on_changed(update_nodes)
    slider_r.on_changed(update_radius)

    plt.show()

# ---------- Run ----------
if __name__ == "__main__":
    plot_3d_network_interactive()