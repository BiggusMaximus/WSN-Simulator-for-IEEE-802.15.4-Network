"""
    DirectUnslottedCSMA – beacon-synchronised, unicast to base station,
    full CSMA/CA with energy tracking and per-round metrics.

    Latency fixes applied:
        ① aTurnaroundTime added between CCA→TX and TX→ACK
        ② Propagation delay added per hop (d / speed_of_light)
        ③ Rx processing delay (aPhyRxStartDelay) added at receiver
        ④ ackWaitDuration race condition guarded
        ⑤ tx_start_time aligned to beacon edge (t=0), not jitter
        ⑥ guard_duration included in latency window via t=0 start

    Energy fixes applied:
        ⑦ Jitter idle listening energy now tracked (jitter_idle bucket)
        ⑧ Sensor TX→RX turnaround after data TX now tracked (turnaround bucket)
        ⑨ MCU active energy during TX / RX now tracked (mcu_active bucket)

    Interframe space fixes applied:
        ⑩ DIFS (or LIFS/SIFS for 802.15.4) wait added after CCA-clear,
           before backoff counter starts — node listens for DIFS and only
           proceeds if channel is still idle.
        ⑪ SIFS wait added at base station between data-frame receipt and
           ACK transmission — models the mandatory interframe gap before ACK.
"""

import heapq
import numpy as np
import os
import pickle
from abstract.routing import RoutingProtocol
from utils.save_manager import *
from utils.information import *

# IEEE 802.15.4 physical constants
SPEED_OF_LIGHT       = 3e8   # m/s
A_TURNAROUND_SYMBOLS = 12    # aTurnaroundTime in symbols (CCA→TX and TX→RX)
A_PHY_RX_START_DELAY = 8     # aPhyRxStartDelay in symbols (receiver lock-on)

# IEEE 802.15.4 interframe spaces (in symbols, 2.4 GHz O-QPSK)
# SIFS = 12 symbols (frames ≤ 18 bytes)
# LIFS = 40 symbols (frames > 18 bytes)
# For 802.11-style DIFS/SIFS swap these for:
#   DIFS_SYMBOLS = 50  (DIFS = SIFS + 2×slot = 10 + 2×20 µs at 1 Mbps)
#   SIFS_SYMBOLS = 10
SIFS_SYMBOLS = 12    # short interframe space (ACK gap at receiver side)
LIFS_SYMBOLS = 40    # long  interframe space (used when frame > 18 bytes)
DIFS_SYMBOLS = LIFS_SYMBOLS   # in 802.15.4 unslotted CSMA, DIFS ≡ LIFS


class DirectUnslottedCSMA(RoutingProtocol):
    def __init__(self, config, nodes, channel):
        super().__init__(config, nodes, channel)

        self.config = config
        self.P_TX = config['Routing']['params']['DirectUnslottedCSMA']['P_TX']
        self.channel = channel
        self.nodes = nodes
        self.base_station = nodes[0]

        # Safe lookup: node.id → node object
        self._node_map = {n.id: n for n in nodes}

        self.transmission_results = {}
        self.energy_consumption_results = {}
        self.latency_results = {}
        self.throughput_results = {}
        self.history = []

        # Per-node tx_start timestamps for latency calculation.
        # FIX ⑤⑥: starts are anchored to the beacon edge (t=0) so that
        # guard-listening time is included in the end-to-end latency window,
        # matching papers that measure from node wake-up.
        self._tx_start_times = {}

        self.empty_metrics()

    # ------------------------------------------------------------------
    # Physical-layer helpers
    # ------------------------------------------------------------------
    def _turnaround_duration(self, rf):
        """aTurnaroundTime: radio mode-switch delay (CCA→TX or TX→RX).
        FIX ①: 12 symbols × symbol_duration (IEEE 802.15.4 §6.9.1)."""
        return A_TURNAROUND_SYMBOLS * rf.SYMBOL_DURATION

    def _propagation_delay(self, node_a, node_b):
        """One-way propagation delay between two nodes.
        FIX ②: d / speed_of_light."""
        distance = node_a.distance(node_b.position)
        return distance / SPEED_OF_LIGHT

    def _rx_processing_delay(self, rf):
        """Receiver preamble / start-of-frame lock-on delay.
        FIX ③: aPhyRxStartDelay = 8 symbols (IEEE 802.15.4 §6.9.1)."""
        return A_PHY_RX_START_DELAY * rf.SYMBOL_DURATION

    def _difs_duration(self, rf):
        """FIX ⑩: DIFS (802.11) or LIFS (802.15.4) — mandatory idle-channel
        sensing period before the backoff counter may begin.
        IEEE 802.15.4 unslotted CSMA: LIFS = 40 symbols for frames > 18 B,
        SIFS = 12 symbols for frames ≤ 18 B."""
        return DIFS_SYMBOLS * rf.SYMBOL_DURATION

    def _sifs_duration(self, rf):
        """FIX ⑪: SIFS — mandatory gap at the receiver between end of data
        frame and start of ACK transmission.
        IEEE 802.15.4: SIFS = 12 symbols; 802.11: SIFS = 10 µs (2.4 GHz)."""
        return SIFS_SYMBOLS * rf.SYMBOL_DURATION

    def _mcu_active_energy(self, node, duration):
        """FIX ⑨: MCU active energy while the radio is TX-ing or RX-ing.
        Falls back gracefully if the MCU model is minimal."""
        mcu = node._mcu
        if hasattr(mcu, 'energy_active'):
            return mcu.energy_active(duration)
        if hasattr(mcu, 'energy_idle'):
            return mcu.energy_idle(duration)
        return 0.0

    # ------------------------------------------------------------------
    def run(self, duration_period):
        self.channel._update_parameter()
        self.empty_metrics()
        self._tx_start_times = {}

        # --- Initialise per-node last-active timestamps ---
        for node in self.nodes:
            node._rf.P_TX = self.P_TX
            node._last_active = 0.0

        # --- Sensing & logging energy ---
        if self.config['Simulation']['is_sensing_enabled']:
            total_energy_sensing = self.compute_energy_sensing()
            self.energy_consumption_results['sensing'] += total_energy_sensing

        if self.config['Simulation']['is_logging_enabled']:
            total_energy_logging = self.compute_energy_logging()
            self.energy_consumption_results['logging'] += total_energy_logging

        beacon_interval = self.nodes[0]._rf.calculate_beacon_interval()

        # print(f"beacon_interval: {beacon_interval}")
        period_duration = float(self.config['Simulation']['time_step'])
        guard_duration  = 2 * self.nodes[0]._mcu.ppm * beacon_interval

        # Store for throughput calculation
        self._beacon_interval = beacon_interval

        # ---------- Time-guard listening for beacon ----------
        for node in self.nodes:
            if node.alive and not node.is_base_station:
                listen_energy = node._rf.energy_listening(guard_duration)
                node._remaining_energy(listen_energy)
                self.energy_consumption_results['time_guard'] += listen_energy
                node._last_active = guard_duration

        # ---------- Schedule CSMA/CA for all alive sensors ----------
        for node in self.nodes:
            if node.alive and not node.is_base_station:
                jitter = np.random.uniform(0, node._rf.MAX_JITTER)
                packet = node._rf._packet.transmit(node, [self.base_station], "SENSOR_DATA")
                node._rf.state = "INITIALIZATION"

                # FIX ⑦: charge jitter idle listening energy.
                jitter_energy = node._rf.energy_listening(jitter)
                node._remaining_energy(jitter_energy)
                self.energy_consumption_results['jitter_idle'] += jitter_energy

                # FIX ⑤⑥: anchor latency to beacon edge (t=0).
                self._tx_start_times[node.id] = 0.0

                self._schedule_event(jitter, "INITIALIZATION", node.id)

        # ---------- Discrete-event loop ----------
        while self.channel._event_queue:
            time, event_sequence, state, node_id = heapq.heappop(self.channel._event_queue)
            self.channel._clock = time

            node = self._node_map[node_id]
            node._last_active = self.channel._clock

            if state == "INITIALIZATION":
                self._schedule_initialization(node_id)
            elif state == "CCA":
                self._schedule_cca_detection(node_id)
            elif state == "DIFS":
                self._schedule_difs(node_id)
            elif state == "TRANSMIT_END":
                self._schedule_transmit_end(node_id)
            elif state == "ACK_TIMEOUT":
                self._schedule_ack_timeout(node_id)
            elif state == "ACK_RECEIVED":
                self._schedule_ack_received(node_id)

        # ---------- Inter-period sleep ----------
        for node in self.nodes:
            if node.alive and not node.is_base_station:
                sleep_duration = max(0.0, beacon_interval - node._last_active)
                # print(f'\tsleep duration: {sleep_duration} | active: {node._last_active}')
                sleep_energy   = node._mcu.energy_sleep(sleep_duration)
                node._remaining_energy(sleep_energy)
                self.energy_consumption_results['sleep'] += sleep_energy
                node._rf.state = "SLEEP"

        if self.base_station.alive:
            bs = self.base_station
            sleep_duration_bs = max(0.0, beacon_interval - bs._last_active)
            sleep_energy_bs   = bs._mcu.energy_sleep(sleep_duration_bs)
            bs._remaining_energy(sleep_energy_bs)
            self.energy_consumption_results['sleep'] += sleep_energy_bs
            bs._rf.state = "SLEEP"

        self.display_metric_results_per_round()
        self.saving_metrics(duration_period)

    # ------------------------------------------------------------------
    def _schedule_event(self, event_time, state, node_id):
        heapq.heappush(
            self.channel._event_queue,
            (event_time, self.channel._event_sequence, state, node_id)
        )
        self.channel._event_sequence += 1

    # ------------------------------------------------------------------
    # CSMA/CA state handlers
    # ------------------------------------------------------------------
    def _schedule_initialization(self, node_id):
        node = self._node_map[node_id]
        rf = node._rf
        rf.NB = 0
        rf.BE = rf.macMinBE
        rf.state = "INITIALIZATION"
        rf.successfull_receivers = []
        rf.insert_data()
        self._schedule_backoff(node_id)

    def _schedule_backoff(self, node_id):
        node = self._node_map[node_id]
        rf = node._rf
        rf.state = "BACKOFF"

        max_units = (1 << int(rf.BE)) - 1
        delay = np.random.randint(0, max_units + 1) * rf.aUnitBackoffPeriod * rf.SYMBOL_DURATION

        backoff_energy = rf.energy_listening(delay)
        node._remaining_energy(backoff_energy)
        self.transmission_results['total_backoffs'] += 1
        self.energy_consumption_results['backoff'] += backoff_energy

        self._schedule_event(self.channel._clock + delay, "CCA", node_id)

    def _schedule_cca_detection(self, node_id):
        node = self._node_map[node_id]
        rf = node._rf
        rf.state = "CCA"

        cca_energy = rf.energy_listening(rf.ccaDuration)
        node._remaining_energy(cca_energy)
        self.energy_consumption_results['cca'] += cca_energy

        is_busy = self.channel.is_channel_busy(node, self.channel._clock)

        if is_busy:
            rf.NB += 1
            rf.BE = min(rf.BE + 1, rf.macMaxBE)
            if rf.NB > rf.macMaxCSMABackoffs:
                rf.is_failure = True
                rf.failure_reason = "channel_busy"
                rf.insert_data()
                self.transmission_results['channel_busy_failure'] += 1
            else:
                self._schedule_backoff(node_id)
        else:
            # FIX ⑩: channel is idle after CCA — node must now wait DIFS
            # (LIFS in 802.15.4) while continuing to sense the channel idle
            # before it may transmit. Only if still idle after DIFS does the
            # node proceed to the turnaround + TX sequence.
            difs = self._difs_duration(rf)
            difs_energy = rf.energy_listening(difs)
            node._remaining_energy(difs_energy)
            self.energy_consumption_results['difs'] += difs_energy
            rf.state = "DIFS"
            self._schedule_event(self.channel._clock + difs, "DIFS", node_id)

    def _schedule_difs(self, node_id):
        """FIX ⑩: called after DIFS elapses. Re-check channel; if still idle,
        proceed to turnaround + TX. If now busy, increment NB/BE and backoff."""
        node = self._node_map[node_id]
        rf = node._rf

        is_busy = self.channel.is_channel_busy(node, self.channel._clock)

        if is_busy:
            # Channel became busy during DIFS — treat as a CCA failure
            rf.NB += 1
            rf.BE = min(rf.BE + 1, rf.macMaxBE)
            if rf.NB > rf.macMaxCSMABackoffs:
                rf.is_failure = True
                rf.failure_reason = "channel_busy"
                rf.insert_data()
                self.transmission_results['channel_busy_failure'] += 1
            else:
                self._schedule_backoff(node_id)
        else:
            # FIX ①: CCA→TX turnaround (mode switch delay)
            turnaround = self._turnaround_duration(rf)
            turnaround_energy = rf.energy_listening(turnaround)
            node._remaining_energy(turnaround_energy)
            self.energy_consumption_results['turnaround'] += turnaround_energy

            rf.state    = "TRANSMITTING"
            rf.tx_start = self.channel._clock + turnaround
            tx_duration = rf.packet_duration()
            rf.tx_end   = rf.tx_start + tx_duration

            tx_energy = rf.energy_transmit(tx_duration)
            node._remaining_energy(tx_energy)
            self.channel.register_transmitter(node)
            self.energy_consumption_results['transmit_packet'] += tx_energy

            # FIX ⑨: MCU active energy while transmitting the data frame
            mcu_tx_energy = self._mcu_active_energy(node, tx_duration)
            node._remaining_energy(mcu_tx_energy)
            self.energy_consumption_results['mcu_active'] += mcu_tx_energy

            self._schedule_event(rf.tx_end, "TRANSMIT_END", node_id)

    def _schedule_transmit_end(self, node_id):
        node = self._node_map[node_id]
        rf = node._rf
        self.channel.deregister_transmitter(node)

        any_hidden = False
        successful = []

        for dest in rf._packet.destinations:
            collision_result = self.channel.check_collision(node, dest)
            if collision_result["hidden_node"]:
                any_hidden = True
                self.transmission_results['hidden_node_detected'] += 1
            else:
                successful.append(dest)
            if collision_result["exposed_node"]:
                self.transmission_results['exposed_node_detected'] += 1

        if any_hidden:
            rf.retries += 1
            self.transmission_results['total_retries'] += 1
            if rf.retries <= rf.macMaxFrameRetries:
                rf.NB = 0
                rf.BE = rf.macMinBE
                rf.state = "INITIALIZATION"
                self._schedule_event(self.channel._clock, "INITIALIZATION", node_id)
            else:
                rf.is_failure = True
                rf.is_collision = True
                rf.failure_reason = "collision"
                rf.insert_data()
                self.transmission_results['collision_failure'] += 1
            return

        rf.successfull_receivers = successful
        data_duration = rf.packet_duration()

        for dest in successful:
            # FIX ②③: propagation + receiver lock-on delay
            prop_delay    = self._propagation_delay(node, dest)
            rx_proc_delay = self._rx_processing_delay(dest._rf)

            rx_start  = self.channel._clock + prop_delay + rx_proc_delay
            rx_energy = dest._rf.energy_receive(data_duration)
            dest._remaining_energy(rx_energy)
            self.energy_consumption_results['receive_packet'] += rx_energy
            self.energy_consumption_results['propagation']    += 0.0  # time-only

            # FIX ⑨: MCU active energy at base station while receiving
            mcu_rx_energy = self._mcu_active_energy(dest, data_duration)
            dest._remaining_energy(mcu_rx_energy)
            self.energy_consumption_results['mcu_active'] += mcu_rx_energy

            dest._last_active = rx_start + data_duration

        is_ack_required = rf._packet.ack_flag and len(rf._packet.destinations) == 1
        if is_ack_required:
            ack_sender    = rf._packet.destinations[0]
            prop_delay    = self._propagation_delay(node, ack_sender)
            rx_proc_delay = self._rx_processing_delay(rf)

            # FIX ⑪: SIFS — base station waits SIFS after data frame before
            # switching to TX and sending ACK. This is mandatory in both
            # 802.15.4 and 802.11 and adds a fixed gap to the ACK path.
            sifs = self._sifs_duration(ack_sender._rf)
            sifs_energy = ack_sender._rf.energy_listening(sifs)
            ack_sender._remaining_energy(sifs_energy)
            self.energy_consumption_results['sifs'] += sifs_energy

            # FIX ①: BS RX→TX turnaround before sending ACK (after SIFS)
            ack_turnaround        = self._turnaround_duration(ack_sender._rf)
            ack_turnaround_energy = ack_sender._rf.energy_listening(ack_turnaround)
            ack_sender._remaining_energy(ack_turnaround_energy)
            self.energy_consumption_results['turnaround'] += ack_turnaround_energy

            ack_duration  = rf.ackDuration
            ack_tx_energy = ack_sender._rf.energy_transmit(ack_duration)
            ack_sender._remaining_energy(ack_tx_energy)
            self.energy_consumption_results['transmit_ack'] += ack_tx_energy

            # FIX ⑨: MCU active at BS while transmitting ACK
            mcu_ack_energy = self._mcu_active_energy(ack_sender, ack_duration)
            ack_sender._remaining_energy(mcu_ack_energy)
            self.energy_consumption_results['mcu_active'] += mcu_ack_energy

            # FIX ⑧: sensor TX→RX turnaround after data TX
            sensor_turnaround        = self._turnaround_duration(rf)
            sensor_turnaround_energy = rf.energy_listening(sensor_turnaround)
            node._remaining_energy(sensor_turnaround_energy)
            self.energy_consumption_results['turnaround'] += sensor_turnaround_energy

            # ACK arrives at sensor:
            #   clock + SIFS + BS_turnaround + ACK_Tx + prop_return + rx_proc
            ack_arrive_at_sensor = (
                self.channel._clock
                + sifs
                + ack_turnaround
                + ack_duration
                + prop_delay
                + rx_proc_delay
            )
            ack_sender._last_active = (
                self.channel._clock + sifs + ack_turnaround + ack_duration
            )

            rf.state          = "WAITING_ACK"
            rf.ack_wait_start = self.channel._clock

            # FIX ④: ensure ACK_RECEIVED always fires before ACK_TIMEOUT
            min_wait  = sifs + ack_turnaround + ack_duration + 2 * prop_delay + rx_proc_delay
            safe_wait = max(rf.ackWaitDuration, min_wait + rf.SYMBOL_DURATION)

            self._schedule_event(self.channel._clock + safe_wait, "ACK_TIMEOUT",  node_id)
            self._schedule_event(ack_arrive_at_sensor,            "ACK_RECEIVED", node_id)
        else:
            node.is_failure = False
            self.transmission_results['success'] += 1
            self.metrics_results['total_packet_sent'] += rf._packet.packet_size
            self.throughput_results['total_bits_delivered'] += rf._packet.packet_size * 8
            start   = self._tx_start_times.get(node_id, 0.0)
            latency = self.channel._clock - start
            self.latency_results['total_latency']   += latency
            self.latency_results['latency_samples'] += 1
            rf.insert_data()

    def _schedule_ack_timeout(self, node_id):
        node = self._node_map[node_id]
        rf = node._rf
        if rf.state != "WAITING_ACK":
            return

        listen_dur    = self.channel._clock - rf.ack_wait_start
        listen_energy = rf.energy_listening(listen_dur)
        node._remaining_energy(listen_energy)
        self.energy_consumption_results['waiting_ack'] += listen_energy

        rf.retries += 1
        self.transmission_results['total_retries'] += 1
        if rf.retries <= rf.macMaxFrameRetries:
            rf.NB = 0
            rf.BE = rf.macMinBE
            rf.state = "INITIALIZATION"
            self._schedule_event(self.channel._clock, "INITIALIZATION", node_id)
        else:
            rf.is_failure = True
            rf.failure_reason = "ack_timeout"
            rf.insert_data()
            self.transmission_results['ack_timeout_failure'] += 1

    def _schedule_ack_received(self, node_id):
        node = self._node_map[node_id]
        rf = node._rf
        if rf.state != "WAITING_ACK":
            return

        listen_dur    = self.channel._clock - rf.ack_wait_start
        listen_energy = rf.energy_listening(listen_dur)
        node._remaining_energy(listen_energy)
        self.energy_consumption_results['listening_ack'] += listen_energy

        # FIX ⑨: MCU active at sensor while receiving / processing the ACK
        mcu_ack_rx_energy = self._mcu_active_energy(node, rf.ackDuration)
        node._remaining_energy(mcu_ack_rx_energy)
        self.energy_consumption_results['mcu_active'] += mcu_ack_rx_energy

        rf.is_failure = False
        rf.insert_data()
        self.transmission_results['success'] += 1
        self.metrics_results['total_packet_sent'] += rf._packet.packet_size
        self.throughput_results['total_bits_delivered'] += rf._packet.packet_size * 8
        start   = self._tx_start_times.get(node_id, 0.0)
        latency = self.channel._clock - start
        self.latency_results['total_latency']   += latency
        self.latency_results['latency_samples'] += 1

    # ------------------------------------------------------------------
    def empty_metrics(self):
        self.metrics_results = {
            'alive_nodes'      : 0,
            'pdr'              : 0,
            'total_packet_sent': 0,
            'remaining_energy' : 0,
            'deviation'        : 0,
        }
        self.transmission_results = {
            'success'              : 0,
            'channel_busy_failure' : 0,
            'collision_failure'    : 0,
            'ack_timeout_failure'  : 0,
            'hidden_node_detected' : 0,
            'exposed_node_detected': 0,
            'total_backoffs'       : 0,
            'total_retries'        : 0,
        }
        self.energy_consumption_results = {
            # ---- pre-TX phases ----
            'time_guard'     : 0,   # beacon guard listening
            'sensing'        : 0,
            'logging'        : 0,
            'jitter_idle'    : 0,   # FIX ⑦: listening during jitter window
            'backoff'        : 0,   # listening during backoff slots
            'cca'            : 0,   # CCA sensing
            'difs'           : 0,   # FIX ⑩: DIFS/LIFS idle sensing after CCA-clear
            'turnaround'     : 0,   # FIX ①⑧: all radio mode-switch delays
            # ---- data exchange ----
            'transmit_packet': 0,
            'receive_packet' : 0,
            'propagation'    : 0,   # time-only placeholder (no RF energy)
            'mcu_active'     : 0,   # FIX ⑨: MCU during TX / RX frames
            # ---- ACK exchange ----
            'sifs'           : 0,   # FIX ⑪: SIFS gap before ACK at base station
            'transmit_ack'   : 0,
            'waiting_ack'    : 0,   # sensor listening while waiting for ACK
            'listening_ack'  : 0,   # sensor listening while receiving ACK
            # ---- idle / sleep ----
            'sleep'          : 0,
        }
        self.latency_results = {
            'total_latency'  : 0.0,
            'latency_samples': 0,
        }
        self.throughput_results = {
            'total_bits_delivered': 0,
        }

    # ------------------------------------------------------------------
    def display_metric_results_per_round(self):
        battery = np.array([n._remaining_battery for n in self.nodes
                            if not n.is_base_station and n.alive])
        alive_count = len(battery)
        std_battery = np.std(battery)  if alive_count > 0 else 0.0
        avg_battery = np.mean(battery) if alive_count > 0 else 0.0
        self.channel.n_alive = alive_count

        # --- PDR ---
        packets_received  = self.transmission_results['success']
        mac_failures      = (self.transmission_results['channel_busy_failure'] +
                             self.transmission_results['collision_failure']    +
                             self.transmission_results['ack_timeout_failure'])
        mac_attempts      = packets_received + mac_failures
        mac_success_rate  = (packets_received / mac_attempts * 100.0) if mac_attempts > 0 else 0.0
        packets_generated = alive_count
        pdr               = (packets_received / packets_generated * 100.0) if packets_generated > 0 else 0.0

        self.metrics_results['alive_nodes']      = alive_count
        self.metrics_results['pdr']              = pdr
        self.metrics_results['mac_success_rate'] = mac_success_rate
        self.metrics_results['remaining_energy'] = float(np.sum(battery)) if alive_count > 0 else 0.0
        self.metrics_results['deviation']        = std_battery

        # --- Latency ---
        samples        = self.latency_results['latency_samples']
        avg_latency_ms = (self.latency_results['total_latency'] / samples * 1000.0) if samples > 0 else 0.0
        self.metrics_results['avg_latency_ms'] = avg_latency_ms

        # --- Throughput ---
        sim_time        = self.channel._clock
        bits_delivered  = self.throughput_results['total_bits_delivered']
        throughput_bps  = (bits_delivered / sim_time) if sim_time > 0 else 0.0
        throughput_kbps = throughput_bps / 1e3

        packet_size_bits      = self.nodes[1]._rf._packet.packet_size * 8
        offered_bits          = alive_count * packet_size_bits
        normalized_throughput = (bits_delivered / offered_bits) if offered_bits > 0 else 0.0

        channel_bitrate = getattr(self.nodes[1]._rf, 'Rb', 250_000)
        channel_util    = (throughput_bps / channel_bitrate) if channel_bitrate > 0 else 0.0

        self.metrics_results['throughput_kbps']          = throughput_kbps
        self.metrics_results['normalized_throughput']    = normalized_throughput
        self.metrics_results['channel_utilization']      = channel_util
        self.throughput_results['throughput_bps']        = throughput_bps
        self.throughput_results['throughput_kbps']       = throughput_kbps
        self.throughput_results['normalized_throughput'] = normalized_throughput
        self.throughput_results['channel_utilization']   = channel_util

        console.print(
            Panel(
                f"[bold]Alive Nodes                 :[/bold] [red]{alive_count}[/red]\n"
                f"[bold]PDR                         :[/bold] [red]{pdr:.2f}%[/red]\n"
                f"[bold]MAC Success Rate            :[/bold] [red]{mac_success_rate:.2f}%[/red]\n"
                f"[bold]Packets Generated           :[/bold] [red]{packets_generated}[/red]\n"
                f"[bold]Packets Received            :[/bold] [red]{packets_received}[/red]\n"
                f"[bold]Avg Remaining Battery       :[/bold] [red]{avg_battery:.2f} J[/red]\n"
                f"[bold]Deviation Remaining Battery :[/bold] [red]{std_battery:.2f} J[/red]\n"
                f"[bold]Avg Latency (successful tx) :[/bold] [red]{avg_latency_ms:.4f} ms[/red]\n"
                f"[bold]Throughput                  :[/bold] [red]{throughput_kbps:.4f} kbps[/red]\n"
                f"[bold]Normalized Throughput       :[/bold] [red]{normalized_throughput:.4f}  (= PDR/100)[/red]\n"
                f"[bold]Channel Utilization         :[/bold] [red]{channel_util:.4f}  (of 250 kbps)[/red]"
            ),
            justify="center"
        )

        tx_table = Table(title="Transmission Results", style="cyan")
        tx_table.add_column("Metric", style="magenta")
        tx_table.add_column("Count", justify="right", style="green")
        for k, v in self.transmission_results.items():
            tx_table.add_row(k, str(v))
        console.print(Align.center(tx_table))

        energy_table = Table(title="Energy Consumption", style="yellow")
        energy_table.add_column("Category", style="magenta")
        energy_table.add_column("Total (J)", justify="right", style="green")
        total_energy = sum(self.energy_consumption_results.values())
        for k, v in self.energy_consumption_results.items():
            energy_table.add_row(k, f"{v:.6f}")
        energy_table.add_row("[bold]TOTAL[/bold]", f"[bold]{total_energy:.6f}[/bold]")
        console.print(Align.center(energy_table))

    # ------------------------------------------------------------------
    def saving_metrics(self, duration_period):
        info_name = (
            f"{self.config['Channel']["PathLoss"]['name']}"
            f"_{self.config['Routing']['name']}"
            f"_N{self.config['Simulation']['number_of_nodes']}"
            f"_L{self.config['Simulation']['area_dimensions'][0]}"
        )
        SIMULATION_FOLDER_PATH = os.path.join(
            OUTPUT_FOLDER_PATH,
            f'TRIAL - {NUMBER_OF_SIMULATION_PERFORMED + 1}'
            f' - ({datetime.datetime.now().strftime("%d-%m-%Y")})'
            f' - {info_name}'
        )
        folder = os.path.join(SIMULATION_FOLDER_PATH, f"Period-{duration_period}")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "transmission_results.pkl"),       "wb") as f:
            pickle.dump(self.transmission_results, f)
        with open(os.path.join(folder, "energy_consumption_results.pkl"), "wb") as f:
            pickle.dump(self.energy_consumption_results, f)
        with open(os.path.join(folder, "metrics_results.pkl"),            "wb") as f:
            pickle.dump(self.metrics_results, f)
        with open(os.path.join(folder, "latency_results.pkl"),            "wb") as f:
            pickle.dump(self.latency_results, f)
        with open(os.path.join(folder, "throughput_results.pkl"),         "wb") as f:
            pickle.dump(self.throughput_results, f)