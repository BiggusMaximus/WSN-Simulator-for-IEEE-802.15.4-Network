from abc import abstractmethod, ABC
from channel.path_loss import create_path_loss
from channel.interference import create_interference
import numpy as np
from utils.information import console


class ChannelModel(ABC):
    def __init__(
        self,
        config,
        nodes
    ):
        self.config                 = config["Channel"]
        self.config_interference    = self.config["Interference"]
        self.config_path_loss       = self.config["PathLoss"]

        self.interference_model     = self.config_interference["name"]
        self.path_loss_model        = self.config_path_loss["name"]

        print(f"self.config_path_loss: {self.config_path_loss['name']}")

        self.nodes          = nodes
        self.n_nodes        = len(nodes)
        self.n_alive        = self.n_nodes - 1

        self._path_loss     = create_path_loss(self.config['PathLoss'])
        self._interference  = create_interference(self.config['Interference'])

        self._interference.channel = self

        # Predefine array to reduce memory allocation
        self.distance_matrix                = np.zeros((self.n_nodes, self.n_nodes))
        self.minimum_power_transmit_matrix  = np.zeros_like(self.distance_matrix)
        self.adjacency_matrix               = np.zeros_like(self.distance_matrix)
        self.shadowing_matrix               = np.zeros_like(self.distance_matrix)
        self.path_loss_matrix               = np.zeros_like(self.distance_matrix)
        self.total_path_loss_matrix         = np.zeros_like(self.distance_matrix)

        # ---------- Build per‑node gain vectors ----------
        # Each node has its own G_TX and G_RX (from _rf)
        self.G_TX_vector = np.array([node._rf.G_TX for node in self.nodes])
        self.G_RX_vector = np.array([node._rf.G_RX for node in self.nodes])

        # Reshape for broadcasting
        self.G_TX_vector_col = self.G_TX_vector.reshape(-1, 1)   # (n_nodes, 1)
        self.G_RX_vector_row = self.G_RX_vector.reshape(1, -1)   # (1, n_nodes)

        # Collect all possible P_TX levels (assume all nodes share the same set)
        # If not, you could take the union, but for simplicity we use node[0]'s list.
        self.p_tx_levels = self.nodes[0]._rf.P_TXs
        self.rssi_matrix_dict = {
            P_TX: np.zeros_like(self.distance_matrix) 
            for P_TX in self.p_tx_levels
        }

        self._precompute_static_matrices()
        self._update_parameter()

        self.ongoing_transmission = []               # List of node object under concurrent transmission
        self._event_queue       = []                 # List of an event happening for MAC protocol
        self._event_sequence    = 0                  # Identifier for MAC protocol
        self._clock             = 0

    def current_concurrent_transmissions(self, current_time):
        return [
            other_transmitter
            for other_transmitter in self.ongoing_transmission
            if other_transmitter._rf.tx_start <= current_time <= other_transmitter._rf.tx_end
        ]

    def register_transmitter(self, transmitter):
        self.ongoing_transmission.append(transmitter)

    def deregister_transmitter(self, transmitter):
        self.ongoing_transmission.remove(transmitter)

    def is_channel_busy(
            self,
            transmitter,
            time_sent
        ):
        """
        Check whether the channel is busy based on the transmitter's own P_CCA.
        Return True if any ongoing transmission is above this node's CCA threshold.
        """
        # Get the CCA threshold of this transmitter (its own hardware)
        p_cca = transmitter._rf.P_CCA

        for other_transmitter in self.ongoing_transmission:
            if other_transmitter._rf.channel != transmitter._rf.channel:
                continue

            if other_transmitter.id == transmitter.id:
                continue

            if not (
                transmitter._rf.tx_start <= time_sent <= other_transmitter._rf.tx_end
            ):
                continue

            # RSSI from other_transmitter to this transmitter (using other's P_TX)
            # We need to look up the correct matrix for the other's transmit power
            p_tx_other = other_transmitter._rf.P_TX
            P_RX = self.rssi_matrix_dict[p_tx_other][other_transmitter.id, transmitter.id]

            if P_RX >= p_cca:
                return True

        return False

    def check_collision(
            self,
            transmitter,
            destination
        ):
        """
        Evaluate hidden-node and exposed-node conditions for transmitter
        against all other ongoing transmissions.
        """
        concurrent = []
        for other_transmitter in self.ongoing_transmission:
            if (
                (other_transmitter.id != transmitter.id) and
                (transmitter._rf.channel == other_transmitter._rf.channel) and
                (transmitter._rf.overlaps(other_transmitter))
            ):
                concurrent.append(other_transmitter)

        if not concurrent:
            return {"hidden_node": False, "exposed_node": False, "details": None}

        result = self._interference.evaluate_all(
            transmitter,
            concurrent,
            destination
        )
        return result

    def _precompute_static_matrices(self):
        console.print("[green]Precomputing static matrices...[/green]")

        positions = np.array([node.position for node in self.nodes])  # shape (n, 3)
        diff = positions[:, None, :] - positions[None, :, :]          # (n, n, 3)
        self.distance_matrix = np.sqrt(np.sum(diff**2, axis=2))

        # Vectorised path loss
        with np.errstate(divide='ignore', invalid='ignore'):
            self.path_loss_matrix = self._path_loss.path_loss(self.distance_matrix)
        np.fill_diagonal(self.path_loss_matrix, 0)

        # Compute RSSI for each possible P_TX using per‑node gains
        for P_TX in self.p_tx_levels:
            self.rssi_matrix_dict[P_TX] = (
                P_TX
                + self.G_TX_vector_col     # broadcasts to (n_nodes, n_nodes)
                + self.G_RX_vector_row     # broadcasts to (n_nodes, n_nodes)
            )
            # Path loss will be subtracted later in _update_parameter
            # (so we leave it as (P_TX + gains) for now)
            np.fill_diagonal(self.rssi_matrix_dict[P_TX], 0)

    def _update_parameter(self):
        self._event_queue       = []
        self._event_sequence    = 0
        self._clock             = 0
        self.n_alive            = 0

        # Generate new shadowing
        self.shadowing_matrix[:] = np.random.normal(
            0, self._path_loss.sigma_db, size=(self.n_nodes, self.n_nodes)
        )
        np.fill_diagonal(self.shadowing_matrix, 0)

        # Total path loss = deterministic + shadowing
        np.add(self.path_loss_matrix, self.shadowing_matrix, out=self.total_path_loss_matrix)

        # Recompute RSSI matrices (subtract total path loss)
        for P_TX in self.p_tx_levels:
            self.rssi_matrix_dict[P_TX] = (
                P_TX
                + self.G_TX_vector_col
                + self.G_RX_vector_row
                - self.total_path_loss_matrix
            )
            np.fill_diagonal(self.rssi_matrix_dict[P_TX], 0)

    def _dBm_to_mW(self, dBm):
        return 10.0 ** (dBm / 10.0)

    def _mW_to_dBm(self, mW):
        if mW <= 0:
            return -np.inf
        return 10.0 * np.log10(mW)