import os
import pickle
import heapq
from platform import node
import numpy as np
from abstract.routing import RoutingProtocol
from utils.save_manager import *
from utils.information import *


class LEACH_IEEE_802_15_4(RoutingProtocol):
    def __init__(self, config, nodes, channel):
        super().__init__(config, nodes, channel)
        self.config         = config
        self.routing_name   = config['Routing']['name']
        self.params         = config['Routing']['params'][self.routing_name]

        self.channel        = channel
        self.nodes          = nodes
        self.base_station   = nodes[0]

        self.p              = float(self.params['p'])


        # per‑round metrics
        self.transmission_results = {}
        self.energy_consumption_results = {}   # aggregated across all phases
        self.phase_energy = {}                # per‑phase breakdown
        self.history = []

        self.current_phase = None
        self.selected_chs = []
        self.data_success_count = 0   

        self.empty_metrics()

    def _add_energy(self, category, amount):
        if self.current_phase is not None:
            self.phase_energy[self.current_phase][category] += amount
        self.energy_consumption_results[category] += amount

    def _add_transmission_result(self, key, increment=1):
        """Increment a transmission counter globally and for the current phase."""
        self.transmission_results[key] += increment
        if self.current_phase is not None:
            self.phase_transmission[self.current_phase][key] += increment

    def run(self, simulation_round):
        self.channel._update_parameter()
        self.empty_metrics()
        self.selected_chs = []          # reset CH list for new round

        # Sensing & logging energy (not phase‑specific)
        total_energy_sensing = self.compute_energy_sensing()
        total_energy_logging = self.compute_energy_logging()
        self.energy_consumption_results['sensing'] += total_energy_sensing
        self.energy_consumption_results['logging'] += total_energy_logging

        self.current_phase = 'guard_time'
        self.guard_time_wakeup()

        self.current_phase = 'advertisement'
        self.ch_broadcast_advertisement_msg(simulation_round)

        self.current_phase = 'join_request'
        self.join_request_msg()

        self.mark_orphan_nodes()

        self.current_phase = 'tdma_schedule'
        self.ch_broadcast_tdma_msg()

        self.current_phase = 'intra_cluster_data'
        self.intra_cluster_data()

        self.current_phase = 'ch_to_bs'
        self.ch_to_bs_transmission()

        self.current_phase = 'sleep'
        self.all_nodes_sleep()

        self.display_metric_results_per_round()
        self.saving_metrics(simulation_round)


    def mark_orphan_nodes(self):
        """Any alive non‑CH node that did not become a member of any CH is an orphan."""
        orphan_count = 0
        for node in self.nodes:
            if node.is_base_station or not node.alive:
                continue
            # A node is orphan if it is not a cluster head AND its cluster_id is still -1
            if not node.is_cluster_head and node.cluster_id == -1 and not node.is_base_station:
                node.is_orphan = True
                node.cluster_id = -1

                orphan_count += 1
            else:
                node.is_orphan = False
        
        self.transmission_results['orphan_nodes'] = orphan_count
        if 'join_request' in self.phase_transmission:
            self.phase_transmission['join_request']['orphan_nodes'] = orphan_count

    # ------------------------------------------------------------------
    # Cluster head selection (unchanged algorithm)
    # ------------------------------------------------------------------
    def cluster_head_selection(self, simulation_round):
        alive_mask = np.array([n.alive and not n.is_base_station for n in self.nodes])
        if not any(alive_mask):
            return []
        r = simulation_round
        threshold = self.p / (1 - self.p * (r % int(1 / self.p)))

        random_vals = np.random.random(len(self.nodes))
        is_ch = random_vals <= threshold
        candidate_ids = np.where(alive_mask & is_ch)[0]

        selected_chs = []
        for idx in candidate_ids:
            ch = self.nodes[idx]
            if ch.eligible_round <= r:
                ch.is_cluster_head = True
                ch.eligible_round = r + int(1 / self.p)
                ch._rf.member_nodes = []
                selected_chs.append(ch)
        return selected_chs

    # ------------------------------------------------------------------
    # Phase 1: Guard time wakeup
    # ------------------------------------------------------------------
    def guard_time_wakeup(self):
        beacon_interval = self.nodes[0]._rf.calculate_beacon_interval()
        guard_duration = 2 * self.nodes[0]._mcu.ppm * beacon_interval
        for node in self.nodes:
            if node.alive and not node.is_base_station:
                listening_energy = node._rf.energy_listening(guard_duration)
                node._remaining_energy(listening_energy)
                self._add_energy('time_guard', listening_energy)

    # ------------------------------------------------------------------
    # Phase 2: CH advertisement (broadcast, no ACK)
    # ------------------------------------------------------------------
    def ch_broadcast_advertisement_msg(self, simulation_round):
        self.selected_chs = self.cluster_head_selection(simulation_round)
        for ch in self.selected_chs:
            ch._rf.P_TX = 0
            node_indices = np.where(self.channel.rssi_matrix_dict[ch._rf.P_TX][ch.id, :] > ch._rf.P_RX_MIN)[0]
            receivers = [self.nodes[i] for i in node_indices if self.nodes[i].alive]
            if not receivers:
                continue
            packet = ch._rf._packet.transmit(ch, receivers, "ADV_MSG")
            ch._rf.state = "INITIALIZATION"
            self._schedule_event(np.random.uniform(0, ch._rf.MAX_JITTER), "INITIALIZATION", ch.id)
        self.processing_event()

    # ------------------------------------------------------------------
    # Phase 3: Join request (unicast to CH, ACK on)
    # ------------------------------------------------------------------
    def join_request_msg(self):
        for ch in self.selected_chs:
            successful_rx = ch._rf.successfull_receivers
            for node in successful_rx:
                if node.id == ch.id or node.is_base_station:
                    continue
                node._rf.P_TX = 0
                packet = node._rf._packet.transmit(node, [ch], "JOIN_REQ")
                node._rf.state = "INITIALIZATION"
                self._schedule_event(np.random.uniform(0, node._rf.MAX_JITTER),
                                     "INITIALIZATION", node.id)
        self.processing_event()

    # ------------------------------------------------------------------
    # Phase 4: CH broadcasts TDMA schedule (broadcast, no ACK)
    # ------------------------------------------------------------------
    def ch_broadcast_tdma_msg(self):
        slot_duration = 0.01   # 10 ms per member – adjustable

        for ch in self.selected_chs:
            ch._rf.P_TX = 0

            members = ch._rf.member_nodes
            if not members:
                continue

            # Create TDMA schedule: (member, start_time_offset)
            schedule = []
            for i, member in enumerate(members):
                schedule.append((member, i * slot_duration))
            ch._rf.tdma_schedule = schedule

            packet = ch._rf._packet.transmit(ch, members, "TDMA_SCHEDULE")
            ch._rf.state = "INITIALIZATION"
            self._schedule_event(np.random.uniform(0, ch._rf.MAX_JITTER),
                                 "INITIALIZATION", ch.id)
        self.processing_event()

    # ------------------------------------------------------------------
    # Phase 5: Intra‑cluster data (member → CH, time‑triggered start)
    # ------------------------------------------------------------------
    def intra_cluster_data(self):
        for ch in self.selected_chs:
            for member in getattr(ch._rf, 'member_nodes', []):
                if member.alive and hasattr(member._rf, 'assigned_tx_time'):
                    member._rf.P_TX = 0
                    packet = member._rf._packet.transmit(member, [ch], "SENSOR_DATA")
                    member._rf.state = "INITIALIZATION"
                    self._schedule_event(member._rf.assigned_tx_time, "INITIALIZATION", member.id)

        self.processing_event()

    # ------------------------------------------------------------------
    # Phase 6: CH → BS (unicast, ACK)
    # ------------------------------------------------------------------
    def ch_to_bs_transmission(self):
        for ch in self.selected_chs:
            if ch.alive:
                ch._rf.P_TX = 20
                packet = ch._rf._packet.transmit(ch, [self.base_station], "SENSOR_DATA_CH")
                ch._rf.state = "INITIALIZATION"
                self._schedule_event(np.random.uniform(0, ch._rf.MAX_JITTER),
                                     "INITIALIZATION", ch.id)
        self.processing_event()

    # ------------------------------------------------------------------
    # Phase 7: All nodes sleep
    # ------------------------------------------------------------------
    def all_nodes_sleep(self):
        beacon_interval = self.nodes[0]._rf.calculate_beacon_interval()
        guard_duration = 2 * self.nodes[0]._mcu.ppm * beacon_interval
        for node in self.nodes:
            if not node.alive:
                continue
            rf = node._rf
            last_active = max(rf.tx_end, self.channel._clock)
            sleep_dur = max(0.0, beacon_interval - guard_duration - last_active)
            if node.is_base_station:
                sleep_energy = node._mcu.energy_sleep(sleep_dur)
            else:
                sleep_energy = node._mcu.energy_sleep(sleep_dur)
            node._remaining_energy(sleep_energy)
            self._add_energy('sleep', sleep_energy)
            rf.state = "SLEEP"

    # ------------------------------------------------------------------
    # Discrete‑event processing loop
    # ------------------------------------------------------------------
    def processing_event(self):
        while self.channel._event_queue:
            time, seq, state, node_id = heapq.heappop(self.channel._event_queue)
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

    def _schedule_event(self, event_time, state, node_id):
        heapq.heappush(
            self.channel._event_queue,
            (event_time, self.channel._event_sequence, state, node_id)
        )
        self.channel._event_sequence += 1

    # ------------------------------------------------------------------
    # CSMA/CA state handlers (with per‑phase energy)
    # ------------------------------------------------------------------
    def _schedule_initialization(self, node_id):
        node = self.nodes[node_id]
        rf = node._rf
        rf.NB = 0
        rf.BE = rf.macMinBE
        rf.state = "INITIALIZATION"
        # Clear successful receivers list for this new transmission
        rf.successfull_receivers = []
        # If a pending packet was set (for time‑triggered transmissions), use it
        # if hasattr(rf, 'pending_packet') and rf.pending_packet is not None:
        #     rf._packet = rf.pending_packet
        #     rf.pending_packet = None

        # print(f"rf.pending_packet: {rf.pending_packet}")
        rf.insert_data()
        self._schedule_backoff(node_id)

    def _schedule_backoff(self, node_id):
        node = self.nodes[node_id]
        rf = node._rf
        rf.state = "BACKOFF"
        max_units = (1 << int(rf.BE)) - 1
        # aUnitBackoffPeriod is already in seconds
        delay = np.random.randint(0, max_units + 1) * rf.aUnitBackoffPeriod * rf.SYMBOL_DURATION

        backoff_energy = rf.energy_listening(delay)
        node._remaining_energy(backoff_energy)

        self._add_transmission_result('total_backoffs')
        self._add_energy('backoff', backoff_energy)

        self._schedule_event(self.channel._clock + delay, "CCA", node_id)

    def _schedule_cca_detection(self, node_id):
        node = self.nodes[node_id]
        rf = node._rf
        rf.state = "CCA"
        cca_energy = rf.energy_listening(rf.ccaDuration)
        node._remaining_energy(cca_energy)
        self._add_energy('cca', cca_energy)

        is_busy = self.channel.is_channel_busy(node, self.channel._clock)
        if is_busy:
            rf.NB += 1
            rf.BE = min(rf.BE + 1, rf.macMaxBE)
            if rf.NB > rf.macMaxCSMABackoffs:
                rf.is_failure = True
                rf.failure_reason = "channel_busy"
                rf.insert_data()
                self._add_transmission_result('channel_busy_failure')
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
            self._add_energy('transmit_packet', tx_energy)

            self._schedule_event(self.channel._clock + tx_duration, "TRANSMIT_END", node_id)

    def _schedule_transmit_end(self, node_id):
        node = self.nodes[node_id]
        rf = node._rf
        self.channel.deregister_transmitter(node)

        any_hidden = False
        successful = []

        for dest in rf._packet.destinations:
            collision_result = self.channel.check_collision(node, dest)
            if collision_result["hidden_node"]:
                any_hidden = True
                self._add_transmission_result('hidden_node_detected')
            else:
                successful.append(dest)
            if collision_result["exposed_node"]:
                self._add_transmission_result('exposed_node_detected')

        if any_hidden:
            rf.retries += 1
            self._add_transmission_result('total_retries')
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
                self._add_transmission_result('collision_failure')
            return

        # Success – record successful receivers
        rf.successfull_receivers = successful
        data_duration = rf.packet_duration()
        for dest in successful:
            rx_energy = dest._rf.energy_receive(data_duration)
            dest._remaining_energy(rx_energy)
            self._add_energy('receive_packet', rx_energy)

        # Track data success for PDR
        if rf._packet.packet_type == 'SENSOR_DATA':
            self.data_success_count += len(successful)

        # --- TDMA schedule handling (assign member transmission times) ---
        if rf._packet.packet_type == 'TDMA_SCHEDULE':
            sender = node   # the CH
            for dest in successful:
                if hasattr(sender._rf, 'tdma_schedule'):
                    for sched_node, offset in sender._rf.tdma_schedule:
                        if sched_node.id == dest.id:
                            dest._rf.assigned_tx_time = self.channel._clock + offset
                            dest._rf.cluster_head = sender
                            break

        # --- ACK handling (only unicast with ack_flag) ---
        if rf._packet.ack_flag and len(rf._packet.destinations) == 1:
            rf.state = "WAITING_ACK"
            rf.ack_wait_start = self.channel._clock
            ack_duration = rf.ackDuration
            # ACK sender is the unique destination
            ack_sender = rf._packet.destinations[0]
            ack_tx_energy = ack_sender._rf.energy_transmit(ack_duration)
            ack_sender._remaining_energy(ack_tx_energy)
            self._add_energy('transmit_ack', ack_tx_energy)

            self._schedule_event(self.channel._clock + rf.ackWaitDuration,
                                 "ACK_TIMEOUT", node_id)
            self._schedule_event(self.channel._clock + ack_duration,
                                 "ACK_RECEIVED", node_id)
        else:
            node.is_failure = False
            self._add_transmission_result('success')
            if rf._packet.packet_type == 'SENSOR_DATA_CH':
                self.metrics_results['total_packet_sent'] += node._rf._packet.packet_size

            rf.insert_data()

            # Join request success – add node to CH's member list
            if self.current_phase == 'join_request' and rf._packet.packet_type == 'JOIN_REQ':
                ch = rf._packet.destinations[0]
                if node not in ch._rf.member_nodes:
                    ch._rf.member_nodes.append(node)

                if node.cluster_id == -1:
                    node.cluster_id = ch.id

    def _schedule_ack_timeout(self, node_id):
        node = self.nodes[node_id]
        rf = node._rf
        if rf.state != "WAITING_ACK":
            return
        listen_dur = self.channel._clock - rf.ack_wait_start
        listen_energy = rf.energy_listening(listen_dur)
        node._remaining_energy(listen_energy)
        self._add_energy('waiting_ack', listen_energy)

        rf.retries += 1
        self._add_transmission_result('total_retries')
        if rf.retries <= rf.macMaxFrameRetries:
            rf.NB = 0
            rf.BE = rf.macMinBE
            rf.state = "INITIALIZATION"
            self._schedule_event(self.channel._clock, "INITIALIZATION", node_id)
        else:
            rf.is_failure = True
            rf.failure_reason = "ack_timeout"
            rf.insert_data()
            self._add_transmission_result('ack_timeout_failure')

    def _schedule_ack_received(self, node_id):
        node = self.nodes[node_id]
        rf = node._rf
        if rf.state != "WAITING_ACK":
            return
        listen_dur = self.channel._clock - rf.ack_wait_start
        listen_energy = rf.energy_listening(listen_dur)
        node._remaining_energy(listen_energy)
        self._add_energy('listening_ack', listen_energy)

        rf.is_failure = False
        rf.insert_data()
        self._add_transmission_result('success')
        if rf._packet.packet_type == 'SENSOR_DATA_CH':
            self.metrics_results['total_packet_sent'] += node._rf._packet.packet_size


        # Join request success – add node to CH's member list
        if self.current_phase == 'join_request' and rf._packet.packet_type == 'JOIN_REQ':
            ch = rf._packet.destinations[0]
            if node not in ch._rf.member_nodes:
                ch._rf.member_nodes.append(node)

            if node.cluster_id == -1:
                node.cluster_id = ch.id 

    # ------------------------------------------------------------------
    # Metrics initialisation & display
    # ------------------------------------------------------------------
    def empty_metrics(self):
        self.metrics_results = {
            'alive_nodes'   : 0,
            'pdr'           : 0,
            'remaining_energy': 0,
            'total_packet_sent': 0,
            'deviation': 0
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
            'orphan_nodes'         : 0,
            
        }
        self.energy_consumption_results = {
            'time_guard': 0, 'sensing': 0, 'logging': 0,
            'backoff': 0, 'cca': 0, 'receive_packet': 0,
            'transmit_packet': 0, 'transmit_ack': 0,
            'waiting_ack': 0, 'listening_ack': 0, 'sleep': 0,
        }

        empty_phase = dict(self.energy_consumption_results)
        empty_transmission = dict(self.transmission_results)

        self.phase_energy = {p: dict(empty_phase) for p in [
            'guard_time', 'advertisement', 'join_request',
            'tdma_schedule', 'intra_cluster_data', 'ch_to_bs', 'sleep'
        ]}
        self.phase_transmission = {p: dict(empty_transmission) for p in [
            'guard_time', 'advertisement', 'join_request',
            'tdma_schedule', 'intra_cluster_data', 'ch_to_bs', 'sleep'
        ]}

        self.data_success_count = 0

        for node in self.nodes:
            if node.is_base_station: continue

            node.cluster_id = -1
            node.is_cluster_head = False
            node.is_orphan = False

            if node.eligible_round > 0:
                node.eligible_round -= 1

    def display_metric_results_per_round(self):
        alive_count = 0
        battery = []
        n_orphan = 0
        for n in self.nodes:
            if n.alive and not n.is_base_station:
                alive_count += 1
                battery.append(n._remaining_battery)

                if n.is_orphan:
                    n_orphan += 1

                # if n.is_cluster_head:
                #     print(f"CH-{n.id}: {[member.id for member in n._rf.member_nodes]}")

        total_alive = max(1, alive_count)
        battery = np.array(battery)
        std_battery    = np.std(battery)

        avg_battery_pct = np.mean(battery) 
        self.channel.n_alive = alive_count
        orphan_percentage = (n_orphan/alive_count) if alive_count > 0 else 0
        
        phase_pdr = {}
        total_success = 0
        total_attempts = 0
        for phase, stats in self.phase_transmission.items():
            succ = stats['success']

            # if channel is busy, if collision or ack doesnt received (if ACK_REQ turn on)
            fail = stats['channel_busy_failure'] + stats['collision_failure'] + stats['ack_timeout_failure']
            attempts = succ + fail
            pdr = (succ / attempts * 100) if attempts > 0 else None   # None if no transmission
            phase_pdr[phase] = pdr
            total_success += succ
            total_attempts += attempts


        global_pdr = (total_success / total_attempts * 100) if total_attempts > 0 else 0.0
        self.metrics_results['alive_nodes'] = alive_count
        self.metrics_results['pdr'] = global_pdr
        self.metrics_results['remaining_energy'] = np.sum(battery)
        self.metrics_results['deviation'] = std_battery

        # Round summary panel
        console.print(
            Panel(
                f"[bold]Alive Nodes                 :[/bold] [red]{alive_count}[/red]\n"
                f"[bold]Global PDR                  :[/bold] [red]{global_pdr:.2f}%[/red]\n"
                f"[bold]Avg Remaining Battery       :[/bold] [red]{avg_battery_pct:.2f} J[/red]\n"
                f"[bold]Deviation Remaining Battery :[/bold] [red]{std_battery:.2f} J[/red]\n"
                f"[bold]Total packet sent           :[/bold] [red]{self.metrics_results['total_packet_sent']:.2f} byte[/red]\n"
                f"[bold]Number of CHs               :[/bold] [red]{len(self.selected_chs)}[/red]\n"
                f"[bold]Number of Orphan            :[/bold] [red]{n_orphan} ({(orphan_percentage) * 100:.2f}%)[/red]"

            ),
            justify="center"
        )


        # Global transmission table
        tx_table = Table(title="Overall Transmission Results", style="cyan")
        tx_table.add_column("Metric", style="magenta")
        tx_table.add_column("Count", justify="right", style="green")
        for k, v in self.transmission_results.items():
            tx_table.add_row(k, str(v))
        console.print(Align.center(tx_table))

        # Phase transmission table
        if any(sum(v.values()) for v in self.phase_transmission.values()):
            phase_tx_table = Table(title="Transmission Results per Phase", style="cyan")
            phases = list(self.phase_transmission.keys())
            # Columns: Metric then one for each phase
            phase_tx_table.add_column("Metric", style="magenta")
            for p in phases:
                phase_tx_table.add_column(p, justify="right", style="green")
            # Get all metric names from one phase dict
            sample_metrics = list(self.phase_transmission[phases[0]].keys())
            for metric in sample_metrics:
                row = [metric]
                for p in phases:
                    row.append(str(self.phase_transmission[p][metric]))
                phase_tx_table.add_row(*row)
            console.print(Align.center(phase_tx_table))

        # Total energy per category
        energy_table = Table(title="Total Energy Consumption", style="yellow")
        energy_table.add_column("Category", style="magenta")
        energy_table.add_column("Total (J)", justify="right", style="green")
        total_energy = sum(self.energy_consumption_results.values())
        for k, v in self.energy_consumption_results.items():
            energy_table.add_row(k, f"{v:.6f}")
        energy_table.add_row("[bold]TOTAL[/bold]", f"[bold]{total_energy:.6f}[/bold]")
        console.print(Align.center(energy_table))

        # Phase breakdown
        phase_table = Table(title="Energy per LEACH Phase", style="yellow")
        phase_table.add_column("Phase", style="magenta")
        phase_table.add_column("Energy (J)", justify="right", style="green")
        for phase, energies in self.phase_energy.items():
            phase_total = sum(energies.values())
            phase_table.add_row(phase, f"{phase_total:.6f}")
        console.print(Align.center(phase_table))

        for phase, energies in self.phase_energy.items():
            phase_table = Table(title=f"Energy for LEACH during {phase}", style="yellow")
            phase_table.add_column("Category", style="magenta")
            phase_table.add_column("Energy (J)", justify="right", style="green")
            for category, energy in energies.items():
                phase_table.add_row(category, f"{energy:.6f}")

            total_energy = sum(energies.values())
            phase_table.add_row("[bold]TOTAL[/bold]", f"[bold]{total_energy:.6f}[/bold]")

            console.print(Align.center(phase_table))


    # ------------------------------------------------------------------
    # Save metrics to disk
    # ------------------------------------------------------------------
    def saving_metrics(self, simulation_round):
        info_name = f"{self.config['Routing']['name']}_N{self.config['Simulation']['number_of_nodes']}_L{self.config['Simulation']['area_dimensions'][0]}"
        SIMULATION_FOLDER_PATH = os.path.join(OUTPUT_FOLDER_PATH, f'TRIAL - {NUMBER_OF_SIMULATION_PERFORMED + 1} - ({datetime.datetime.now().strftime("%d-%m-%Y")}) - {info_name}')
        folder = os.path.join(SIMULATION_FOLDER_PATH, f"Round-{simulation_round}")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "transmission_results.pkl"), "wb") as f:
            pickle.dump(self.transmission_results, f)
        with open(os.path.join(folder, "energy_consumption_results.pkl"), "wb") as f:
            pickle.dump(self.energy_consumption_results, f)
        with open(os.path.join(folder, "phase_energy.pkl"), "wb") as f:
            pickle.dump(self.phase_energy, f)
        with open(os.path.join(folder, "phase_transmission.pkl"), "wb") as f:
            pickle.dump(self.phase_transmission, f)
        with open(os.path.join(folder, "metrics_results.pkl"), "wb") as f:
            pickle.dump(self.metrics_results, f)
        with open(os.path.join(folder, "nodes.pkl"), "wb") as f:
            pickle.dump(self.nodes, f)