"""
    DirectUnslottedCSMA – beacon‑synchronised, unicast to base station,
    full CSMA/CA with energy tracking and per‑round metrics.
"""

import heapq
import numpy as np
import os
import pickle
from abstract.routing import RoutingProtocol
from utils.save_manager import *
from utils.information import *


class DirectUnslottedCSMA(RoutingProtocol):
    def __init__(self, config, nodes, channel):
        super().__init__(config, nodes, channel)

        self.config = config
        self.channel = channel
        self.nodes = nodes
        self.base_station = nodes[0]

        # Safe lookup: node.id → node object
        self._node_map = {n.id: n for n in nodes}

        self.transmission_results = {}
        self.energy_consumption_results = {}
        self.history = []

        self.empty_metrics()

    # ------------------------------------------------------------------
    def run(self, simulation_round):
        self.channel._update_parameter()
        self.empty_metrics()

        total_energy_sensing = self.compute_energy_sensing()
        total_energy_logging = self.compute_energy_logging()
        self.energy_consumption_results['sensing'] += total_energy_sensing
        self.energy_consumption_results['logging'] += total_energy_logging

        beacon_interval = self.nodes[0]._rf.calculate_beacon_interval()
        guard_duration = 2 * self.nodes[0]._mcu.ppm * beacon_interval

        # ---------- Time‑guard listening for beacon ----------
        for node in self.nodes:
            if node.alive and not node.is_base_station:
                listen_energy = node._rf.energy_listening(guard_duration)
                node._remaining_energy(listen_energy)
                self.energy_consumption_results['time_guard'] += listen_energy

        # ---------- Schedule CSMA/CA for all alive sensors ----------
        for node in self.nodes:
            if node.alive and not node.is_base_station:
                jitter = np.random.uniform(0, node._rf.MAX_JITTER)
                packet = node._rf._packet.transmit(node, [self.base_station], "SENSOR_DATA")
                node._rf.state = "INITIALIZATION"
                self._schedule_event(jitter, "INITIALIZATION", node.id)

        # ---------- Discrete‑event loop ----------
        while self.channel._event_queue:
            time, event_sequence, state, node_id = heapq.heappop(self.channel._event_queue)
            self.channel._clock = time

            if state == "INITIALIZATION":
                self._schedule_initialization(node_id)
            elif state == "CCA":
                self._schedule_cca_detection(node_id)
            elif state == "TRANSMIT_END":
                self._schedule_transmit_end(node_id)
            elif state == "ACK_TIMEOUT":
                self._schedule_ack_timeout(node_id)
            elif state == "ACK_RECEIVED":
                self._schedule_ack_received(node_id)

        # ---------- Post‑transmission sleep ----------
        for node in self.nodes:
            if node.alive and not node.is_base_station:
                rf = node._rf
                last_active = max(rf.tx_end, self.channel._clock)
                sleep_duration = max(0.0, beacon_interval - guard_duration - last_active)
                sleep_energy = node._mcu.energy_sleep(sleep_duration)
                node._remaining_energy(sleep_energy)
                self.energy_consumption_results['sleep'] += sleep_energy
                rf.state = "SLEEP"

        # Base station also sleeps
        if self.base_station.alive:
            bs = self.base_station
            bs_rf = bs._rf
            last_active_bs = self.channel._clock
            sleep_duration_bs = max(0.0, beacon_interval - guard_duration - last_active_bs)
            sleep_energy_bs = bs._mcu.energy_sleep(sleep_duration_bs)
            bs._remaining_energy(sleep_energy_bs)
            self.energy_consumption_results['sleep'] += sleep_energy_bs
            bs_rf.state = "SLEEP"

        self.display_metric_results_per_round()
        self.saving_metrics(simulation_round)

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
        rf.successfull_receivers = []   # clear from previous attempts
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
            rf.state = "TRANSMITTING"
            rf.tx_start = self.channel._clock
            tx_duration = rf.packet_duration()
            rf.tx_end = self.channel._clock + tx_duration

            tx_energy = rf.energy_transmit(tx_duration)
            node._remaining_energy(tx_energy)
            self.channel.register_transmitter(node)
            self.energy_consumption_results['transmit_packet'] += tx_energy

            self._schedule_event(self.channel._clock + tx_duration, "TRANSMIT_END", node_id)

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

        # Success – record successful receivers
        rf.successfull_receivers = successful
        data_duration = rf.packet_duration()
        for dest in successful:
            rx_energy = dest._rf.energy_receive(data_duration)
            dest._remaining_energy(rx_energy)
            self.energy_consumption_results['receive_packet'] += rx_energy

        # ACK handling (only for unicast with ack_flag)
        is_ack_required = rf._packet.ack_flag and len(rf._packet.destinations) == 1
        if is_ack_required:
            rf.state = "WAITING_ACK"
            rf.ack_wait_start = self.channel._clock
            ack_duration = rf.ackDuration
            ack_sender = rf._packet.destinations[0]
            ack_tx_energy = ack_sender._rf.energy_transmit(ack_duration)
            ack_sender._remaining_energy(ack_tx_energy)
            self.energy_consumption_results['transmit_ack'] += ack_tx_energy

            self._schedule_event(self.channel._clock + rf.ackWaitDuration, "ACK_TIMEOUT", node_id)
            self._schedule_event(self.channel._clock + ack_duration, "ACK_RECEIVED", node_id)
        else:
            node.is_failure = False
            self.transmission_results['success'] += 1
            self.metrics_results['total_packet_sent'] += rf._packet.packet_size
            rf.insert_data()

    def _schedule_ack_timeout(self, node_id):
        node = self._node_map[node_id]
        rf = node._rf
        if rf.state != "WAITING_ACK":
            return

        listen_dur = self.channel._clock - rf.ack_wait_start
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

        listen_dur = self.channel._clock - rf.ack_wait_start
        listen_energy = rf.energy_listening(listen_dur)
        node._remaining_energy(listen_energy)
        self.energy_consumption_results['listening_ack'] += listen_energy

        rf.is_failure = False
        rf.insert_data()
        self.transmission_results['success'] += 1
        self.metrics_results['total_packet_sent'] += rf._packet.packet_size

    # ------------------------------------------------------------------
    def empty_metrics(self):
        self.metrics_results = {
            'alive_nodes'      : 0,
            'pdr'              : 0,
            'total_packet_sent': 0,
            'remaining_energy' : 0,
            'deviation'        : 0
        }
        self.transmission_results = {
            'success': 0,
            'channel_busy_failure': 0,
            'collision_failure': 0,
            'ack_timeout_failure': 0,
            'hidden_node_detected': 0,
            'exposed_node_detected': 0,
            'total_backoffs': 0,
            'total_retries': 0,
        }
        self.energy_consumption_results = {
            'time_guard': 0,
            'sensing': 0,
            'logging': 0,
            'backoff': 0,
            'cca': 0,
            'receive_packet': 0,
            'transmit_packet': 0,
            'transmit_ack': 0,
            'waiting_ack': 0,
            'listening_ack': 0,
            'sleep': 0,
        }

    def display_metric_results_per_round(self):
        battery = np.array([n._remaining_battery for n in self.nodes
                            if not n.is_base_station and n.alive])
        alive_count = len(battery)
        total_alive = max(1, alive_count)
        std_battery = np.std(battery) if len(battery) > 0 else 0
        avg_battery = np.mean(battery) if len(battery) > 0 else 0
        self.channel.n_alive = alive_count

        succ = self.transmission_results['success']
        fail = (self.transmission_results['channel_busy_failure'] +
                self.transmission_results['collision_failure'] +
                self.transmission_results['ack_timeout_failure'])
        attempts = succ + fail
        pdr = (succ / attempts * 100) if attempts > 0 else 0.0

        self.metrics_results['alive_nodes'] = alive_count
        self.metrics_results['pdr'] = pdr
        self.metrics_results['remaining_energy'] = np.sum(battery) if len(battery) > 0 else 0
        self.metrics_results['deviation'] = std_battery

        console.print(
            Panel(
                f"[bold]Alive Nodes                 :[/bold] [red]{alive_count}[/red]\n"
                f"[bold]Global PDR                  :[/bold] [red]{pdr:.2f}%[/red]\n"
                f"[bold]Avg Remaining Battery       :[/bold] [red]{avg_battery:.2f} J[/red]\n"
                f"[bold]Total packet sent           :[/bold] [red]{self.metrics_results['total_packet_sent']:.2f} B[/red]\n"
                f"[bold]Deviation Remaining Battery :[/bold] [red]{std_battery:.2f} J[/red]"
            ),
            justify="center"
        )

        # Transmission results table
        tx_table = Table(title="Transmission Results", style="cyan")
        tx_table.add_column("Metric", style="magenta")
        tx_table.add_column("Count", justify="right", style="green")
        for k, v in self.transmission_results.items():
            tx_table.add_row(k, str(v))
        console.print(Align.center(tx_table))

        # Energy consumption table
        energy_table = Table(title="Energy Consumption", style="yellow")
        energy_table.add_column("Category", style="magenta")
        energy_table.add_column("Total (J)", justify="right", style="green")
        total_energy = sum(self.energy_consumption_results.values())
        for k, v in self.energy_consumption_results.items():
            energy_table.add_row(k, f"{v:.6f}")
        energy_table.add_row("[bold]TOTAL[/bold]", f"[bold]{total_energy:.6f}[/bold]")
        console.print(Align.center(energy_table))

    def saving_metrics(self, simulation_round):
        info_name = f"{self.config['Routing']['name']}_N{self.config['Simulation']['number_of_nodes']}_L{self.config['Simulation']['area_dimensions'][0]}"
        SIMULATION_FOLDER_PATH = os.path.join(OUTPUT_FOLDER_PATH, f'TRIAL - {NUMBER_OF_SIMULATION_PERFORMED + 1} - ({datetime.datetime.now().strftime("%d-%m-%Y")}) - {info_name}')
        folder = os.path.join(SIMULATION_FOLDER_PATH, f"Round-{simulation_round}")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "transmission_results.pkl"), "wb") as f:
            pickle.dump(self.transmission_results, f)
        with open(os.path.join(folder, "energy_consumption_results.pkl"), "wb") as f:
            pickle.dump(self.energy_consumption_results, f)
        with open(os.path.join(folder, "metrics_results.pkl"), "wb") as f:
            pickle.dump(self.metrics_results, f)