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

        # self.rssi_matrix                    = np.zeros_like(self.distance_matrix)
        
        self.rssi_matrix_dict = {P_TX:np.zeros_like(self.distance_matrix) for P_TX in self.nodes[1]._rf.P_TXs}


        # Since its constant
        self.G_TX_vector        = np.full(self.n_nodes, self.config_interference[self.interference_model]['G_TX'])
        self.G_RX_vector        = np.full(self.n_nodes, self.config_interference[self.interference_model]['G_RX'])
        self.P_RX_MIN_vector    = np.full(self.n_nodes, self.config_interference[self.interference_model]['P_RX_MIN'])

        # After defining the vectors:
        self.G_TX_vector_col = self.G_TX_vector.reshape(-1, 1)    # shape (n_nodes, 1)
        self.G_RX_vector_row = self.G_RX_vector.reshape(1, -1)    # shape (1, n_nodes)


        self._precompute_static_matrices()
        self._update_parameter()


        self.ongoing_transmission = []               # List of node object under concurrent transmission for checking interference and collision


        self._event_queue       = []              # List of an event happening  for MAC protocol
        self._event_sequence    = 0           # Identifier for MAC protocol
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
            Check wether the cchannel is busy based on P_CCA

            Return True if any ongoing transmission is above P_CCA at the transmitter radius (Energy Detection CCA, mode 1).
        """

        for other_transmitter in self.ongoing_transmission:
            if other_transmitter._rf.channel != transmitter._rf.channel:
                continue

            if other_transmitter.id == transmitter.id:
                continue

            if not (
                transmitter._rf.tx_start <= time_sent <= other_transmitter._rf.tx_end
            ):
                continue

            # P_RX = self.calculate_RSSI(transmitter, other_transmitter)
            # print(f"""
            #     transmitter         : {transmitter}
            #     other_transmitter   : {other_transmitter}
            # """)
            P_RX = self.rssi_matrix_dict[transmitter._rf.P_TX][transmitter.id, other_transmitter.id]

            if P_RX >= self._interference.P_CCA:
                return True
            
        return False
    
    def check_collision(
            self,
            transmitter,
            destination
        ):

        """
            Evaluate hidden-node and exposed-node conditions for transmitter
            against all other ongoing or recently completed transmissions.

            Returns a dict with keys 'hidden_node' (bool) and 'exposed_node' (bool).
        """
                
        concurrent = []
        # print(f"self.ongoing_transmission: {self.ongoing_transmission}")
        for other_transmitter in self.ongoing_transmission:
            # print(f"""
            #         1st id cond: { (other_transmitter.id != transmitter.id) }
            #         2nd id cond: { (transmitter._rf.channel == other_transmitter._rf.channel) }
            #         3rd id cond: { (transmitter._rf.overlaps(other_transmitter)) }

            #     """)
            if (
                (other_transmitter.id != transmitter.id) and 
                (transmitter._rf.channel == other_transmitter._rf.channel) and
                (transmitter._rf.overlaps(other_transmitter))
            ):
                
                concurrent.append(other_transmitter)
        
        # print(f"concurrent: {concurrent}")
        # If there are no concurrent transmission

        if not concurrent:
            return {"hidden_node": False, "exposed_node": False, "details": None}
                
        # print(f"\t\t\tThere are concurrent transmission")

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

        for P_TX in self.nodes[0]._rf.P_TXs:
            self.rssi_matrix_dict[P_TX] = (
                P_TX
                + self.G_TX_vector_col     # broadcasts to (n_nodes, n_nodes)
                + self.G_RX_vector_row     # broadcasts to (n_nodes, n_nodes)
            )
            np.fill_diagonal(self.rssi_matrix_dict[P_TX], 0)      # no self‑communication

    def _update_parameter(self):
        self._event_queue       = []              # List of an event happening  for MAC protocol
        self._event_sequence    = 0           # Identifier for MAC protocol
        self._clock             = 0
        self.n_alive            = 0
    
        # Fill shadowing matrix in‑place (or generate into it)
        self.shadowing_matrix[:] = np.random.normal(
            0, self._path_loss.sigma_db, size=(self.n_nodes, self.n_nodes)
        )
        np.fill_diagonal(self.shadowing_matrix, 0)

        # In‑place addition
        np.add(self.path_loss_matrix, self.shadowing_matrix, out=self.total_path_loss_matrix)

        for P_TX in self.nodes[0]._rf.P_TXs:
            self.rssi_matrix_dict[P_TX] = (
                P_TX
                - self.total_path_loss_matrix
            )
            np.fill_diagonal(self.rssi_matrix_dict[P_TX], 0)      # no self‑communication

    
    def _dBm_to_mW(self, dBm):
        return 10.0 ** (dBm / 10.0)

    def _mW_to_dBm(self, mW):
        if mW <= 0:
            return -np.inf
        return 10.0 * np.log10(mW)
    
    # def calculate_RSSI(self, transmitter, receiver):
    #     # print(f"""
    #     #     transmitter: {transmitter}
    #     #     receiver:   {receiver}
    #     # """)
    #     i = transmitter.id
    #     j = receiver.id

    #     if transmitter.is_base_station:
    #         i = 0

    #     if receiver.is_base_station:
    #         j = 0


    #     P_TX = transmitter._rf.P_TX
    #     self.rssi_matrix[i, j] = P_TX + self.G_TX_vector[i] + self.G_RX_vector[j] - self.total_path_loss_matrix[i, j]
    #     np.fill_diagonal(self.rssi_matrix, 0)


    #     # print(f"""
    #     #     TX: {i} | RX{j}
    #     #     P_TX : {P_TX}
    #     #     P_RX: {self.rssi_matrix[i, j]:.2f}
    #     #     Reachable: {self.rssi_matrix[i, j] >= transmitter._rf.P_RX_MIN}
    #     #     self.G_TX_vector[i] : {self.G_TX_vector[i]}
    #     #     self.G_RX_vector[j] : {self.G_RX_vector[j]}
    #     #     self.total_path_loss_matrix[i, j]: {self.total_path_loss_matrix[i, j]}
    #     #     d: {self.distance_matrix[i, j]}
    #     #     PL: {self._path_loss.path_loss(self.distance_matrix[i, j])}
    #     # """)
    #     return self.rssi_matrix[i, j]

    

        
