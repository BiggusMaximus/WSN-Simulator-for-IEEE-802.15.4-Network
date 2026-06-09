

"""
IEEE 802.15.4 Collision Model
==============================
Implements the hidden-node and exposed-node collision conditions
derived in the thesis (see equations I_1 … I_8).

Hidden-node collision requires all five conditions simultaneously:
    I1: Time overlap          [t_vi_start, t_vi_end] ∩ [t_vk_start, t_vk_end] ≠ ∅
    I2: Mutual non-detection  P_RX(vi,vk) ≤ P_CCA  AND  P_RX(vk,vi) ≤ P_CCA
    I3: Both reachable at vj  P_RX(vi,vj) ≥ P_RX_min  AND  P_RX(vk,vj) ≥ P_RX_min
    I4: SINR below threshold  SINR(vi→vj) < SINR_thresh
    I5: Destination silent    vj ∉ T(t)

Exposed-node condition (wasted opportunity) requires:
    I1: Time overlap (same as above)
    I5: Destination silent
    I6: vi detects vk         P_RX(vk,vi) ≥ P_CCA
    I7: vi reachable at vj    P_RX(vi,vj) ≥ P_RX_min
    I8: SINR above threshold  SINR(vi→vj) ≥ SINR_thresh
        (transmission would have succeeded without CCA-induced deferral)
"""
import numpy as np
from abstract.interference import InterferenceModel

class IEEE_802_15_4(InterferenceModel):
    def __init__(
        self, config
    ):
        self.name           =  config["name"                ]
        self.P_CCA          =  float(config[self.name]["P_CCA"    ])                 
        self.SINR           =  float(config[self.name]["SINR"     ])
        self.N0             =  float(config[self.name]["N0"       ])
        self.P_RX_MIN       =  float(config[self.name]["P_RX_MIN" ])

    def reception_overlap(self, tx_source, tx_other):
        """
            Comparing two node object
        """
        return tx_source._rf.overlaps(tx_other)
    
    def capture_effect(
        self,
        signal_dBm,
        interferer_dBm,
        noise_dBm
    ):
        return self._SINR_dB(signal_dBm, [interferer_dBm], noise_dBm) >= self.SINR
    
    
    def current_concurrent_transmissions(self, current_time):
        return [ 
            other_transmitter 
            for other_transmitter in self.ongoing_transmission 
            if other_transmitter._rf.tx_start <= current_time <= other_transmitter._rf.tx_end
        ]

    def evaluate(
        self,
        initial_transmitter,        # v_i
        other_transmitter,          # v_k
        destination_receiver        # v_j
    ):
        # print(f"check collision evaluate")
        """
            Comparing two other nodes: v_i and v_j based on:
            I1 ∩ I2 ∩ I3 ∩ I4 ∩ I5
        """
        results = {
            'hidden_node': False,
            'exposed_node': False,
            'colliding_node_ids': [],
            'SINR': np.inf,
            'conditions': {}
        }

        # print(f"""
        #     transmitter: {initial_transmitter}
        #     receiver:   {destination_receiver}
        # """)

        # P_vi_vk = self.channel.calculate_RSSI(initial_transmitter , other_transmitter)   # vi → vk
        # P_vk_vi = self.channel.calculate_RSSI(other_transmitter   , initial_transmitter)   # vk → vi
        # P_vi_vj = self.channel.calculate_RSSI(initial_transmitter , destination_receiver)   # vi → vj  (signal)
        # P_vk_vj = self.channel.calculate_RSSI(other_transmitter   , destination_receiver)   # vk → vj  (interferer at vj)

        i = initial_transmitter.id
        k = other_transmitter.id
        j = destination_receiver.id

        if initial_transmitter.is_base_station:
            i = 0

        if other_transmitter.is_base_station:
            k = 0

        if destination_receiver.is_base_station:
            j = 0

        P_vi_vk = self.channel.rssi_matrix_dict[initial_transmitter._rf.P_TX][i, k]
        P_vk_vi = self.channel.rssi_matrix_dict[other_transmitter._rf.P_TX  ][k, i]
        P_vi_vj = self.channel.rssi_matrix_dict[initial_transmitter._rf.P_TX][i, j]
        P_vk_vj = self.channel.rssi_matrix_dict[other_transmitter._rf.P_TX  ][k, j]


        sinr_vi_vj = self._SINR_dB(P_vi_vj, [P_vk_vj], self.N0)
        results['SINR'] = sinr_vi_vj
        self.current_transmission = []

        # ==============================================================================
        # ===============================  Hidden Node  ================================
        # ==============================================================================

        # Time Overlap
        I1 = initial_transmitter._rf.overlaps(other_transmitter)

        # CCA mechanism
        I2 = (P_vi_vk <= self.P_CCA) and (P_vk_vi <= self.P_CCA)

        # Receiver able to receive the packet from both of the transmitters
        # print(f"""
        #     P_vi_vj: {P_vi_vj}
        #     P_vk_vj: {P_vk_vj}
        #     self.P_RX_MIN: {self.P_RX_MIN}
        # """)
        I3 = (P_vi_vj >= self.P_RX_MIN) and (P_vk_vj >= self.P_RX_MIN)

        # Ensure the SINR for each transmitter
        I4 = sinr_vi_vj < self.SINR
        
        # Ensure the destination is not transmitting
        I5 = not any(
            tx.id == destination_receiver.id for tx in self.channel.current_concurrent_transmissions(
                initial_transmitter._rf.tx_start
                )
            )

        if I1 and I2 and I3 and I4 and I5:
            results['hidden_node'] = True
            results['colliding_node_ids'].append(other_transmitter.id)

        # ==============================================================================
        # ==============================  Exposed Node  ================================
        # ==============================================================================

        I6 = P_vk_vi >= self.P_CCA
        I7 = P_vi_vj >= self.P_RX_MIN
        I8 = sinr_vi_vj >= self.SINR

        if I1 and I5 and I6 and I7 and I8:
            results['exposed_node'] = True


        results['conditions']["I1_time_overlap"]       = I1
        results['conditions']["I2_mutual_hidden"]      = I2
        results['conditions']["I3_both_reachable"]     = I3
        results['conditions']["I4_sinr_below_thresh"]  = I4
        results['conditions']["I5_dest_silent"]        = I5
        results['conditions']["I6_vi_detects_vk"]      = I6
        results['conditions']["I7_vi_reachable"]       = I7
        results['conditions']["I8_sinr_above_thresh"]  = I8

        return results
         


    def evaluate_all(
            self,
            initial_transmitter,
            other_concurent_transmitters,
            destination_receiver
        ):
        results = {
            'hidden_node': False,
            'exposed_node': False,
            'colliding_node_ids': [],
            'SINR': np.inf,
            'conditions': {}
        }
        # print(f"""
        #       evaliuae all
        #     transmitter: {initial_transmitter}
        #     receiver:   {destination_receiver}
        # """)
        for other_transmitter in other_concurent_transmitters:
            if other_transmitter.id == initial_transmitter.id:
                continue
            if other_transmitter._rf.channel != initial_transmitter._rf.channel:
                continue

            r = self.evaluate(
                initial_transmitter,        # v_i
                other_transmitter,          # v_k
                destination_receiver        # v_j
            )
            results["SINR"] = min(results["SINR"], r["SINR"])

            if r['hidden_node']:
                results['hidden_node'] = True
                results['colliding_node_ids'].extend(r['colliding_node_ids'])

            if r['exposed_node']:
                results['exposed_node'] = True

            for k, v in r['conditions'].items():
                if k not in results['conditions']:
                    results['conditions'][k] = v
                else:
                    # Logical OR — report True if *any* pair triggers it
                    results['conditions'][k] = results['conditions'][k] or v
        
        return results





