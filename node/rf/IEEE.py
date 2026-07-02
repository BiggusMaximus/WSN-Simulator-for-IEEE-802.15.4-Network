from abstract.rf import RF
from packet import create_packet
import numpy as np

class IEEE_802_15_4(RF):
    def __init__(self, config):
        super().__init__(config)
        
        self.config             = config['RF']
        self.RF_name            = config['RF']['name']
        self.RF_params          = config['RF']['params'][self.RF_name]['RF_hardware']
        self.RF_hardware_name   = self.RF_params['name']

        self.RF_params          = self.RF_params['params'][self.RF_hardware_name]


        self.V                  = float(self.RF_params['V'               ])
        
        self.G_TX               = float(self.RF_params['G_TX'            ])
        self.G_RX               = float(self.RF_params['G_RX'            ])
        self.P_RX_MIN           = float(self.RF_params['P_RX_MIN'        ])
        self.P_RX_MAX           = float(self.RF_params['P_RX_MAX'        ])
        self.P_CCA              = float(self.RF_params['P_CCA'        ])
        self.SINR_Thresh        = float(self.RF_params['SINR_Thresh'        ])
        self.N0                 = float(self.RF_params['N0'        ])


        self.I_RX               = float(self.RF_params['I_RX'            ])
        self.P_TXs              =       self.RF_params['P_TXs'           ]
        self.I_TXs              =       self.RF_params['I_TXs'           ]
        
        self.Rb                 = float(self.params['Rb'              ])
        self.BYTES_TO_SYMBOLS   = float(self.params['BYTES_TO_SYMBOL' ])
        self.SYMBOL_DURATION    = float(self.params['SYMBOL_DURATION' ])
        self.MAX_JITTER         = float(self.params['MAX_JITTER'])
        self.P_TX               = 20                                   # in dBm

        self.I_TX_dict = {self.P_TXs[i]:self.I_TXs[i] for i in range(len(self.P_TXs))}
        self._packet    = create_packet(config)
        self.tx_start   = 0                                             # in second
        self.tx_end     = 0                                             # in second

        if self.params['RandomChannel']:
            self.channel    = np.random.randint(1, float(self.params['max_random_channel']) + 1)
        else:
            if self.params['is_multi_channel']:
                self.channel    = 0
            else:
                self.channel    = float(self.params['channel'])



        self.ack_wait_start = 0

        """
            Different MAC states
            1. IDLE         
            2. BACKOFF      
            3. CCA          
            4. TRANSMITTING 
            5. WAITING_ACK  
            6. SUCCESS      
            7. FAILURE      
            8. INITIALIZATION
            9. RECEIVING 

        """
        self.macMinBE                   = float(self.params["macMinBE"           ])
        self.macMaxBE                   = float(self.params["macMaxBE"           ])
        self.BO                         = float(self.params["BO"           ])
        self.SO                         = float(self.params["SO"           ])

        self.macMaxCSMABackoffs         = float(self.params["macMaxCSMABackoffs" ])
        self.macMaxFrameRetries         = float(self.params["macMaxFrameRetries" ])
        self.aUnitBackoffPeriod         = float(self.params["aUnitBackoffPeriod" ])
        self.aBaseSuperframeDuration    = float(self.params["aBaseSuperframeDuration"         ])
        self.ccaSymbols                 = float(self.params["ccaSymbols"         ])

        self.ccaDuration                = self.ccaSymbols * self.SYMBOL_DURATION
        self.ackWaitDuration            = float(self.params["ackWaitSymbols"]) * self.SYMBOL_DURATION

        
        # self.ackWaitDuration    = self.params["ackWaitDuration"    ]
        self.ackEnabled         = self.params["ackEnabled"         ]
        self.ackDuration        = self._packet.total_bytes("ACK")  * self.BYTES_TO_SYMBOLS * self.SYMBOL_DURATION

        self.NB             = 0
        self.BE             = 0
        self.retries        = 0
        self.total_failure  = 0
        self.state          = "IDLE"
        self.failure_reason = ""
        self.is_failure     = False
        self.is_collision   = False
        self.successfull_receivers = []
        self.member_nodes = []
        self.tdma_schedule = []
        self.received_advertisements = []


        """
            Store the metrics information for each round, which includes:
            - 
        """

        self.stats = {
            "packet_type"       : [],
            "retries"           : [],
            "tx_start"          : [],
            "tx_end"            : [],
            "is_failure"        : [],
            "is_collision"      : [],
            "state"             : [],
            "failure_reason"    : [],
            "total_failure"     : 0

        }
    
    def insert_data(self):
        self.stats["packet_type"].append(self._packet.packet_type)
        self.stats["retries"].append(self.retries)
        self.stats["tx_start"].append(self.tx_start)
        self.stats["tx_end"].append(self.tx_end)
        self.stats["state"].append(self.state)
        self.stats["is_failure"].append(self.is_failure)
        self.stats["is_collision"].append(self.is_collision)

        self.stats["failure_reason"].append(self.failure_reason)
        self.stats["total_failure"] += 1 if self.is_failure else 0


    
    def packet_duration(self):

     
        duration    = self._packet.total_bytes(self._packet.packet_type) * self.BYTES_TO_SYMBOLS * self.SYMBOL_DURATION
        self.tx_end = self.tx_start + duration

        # if self._packet.packet_type == "ADV_MSG":
        #     print("\n")
        #     print(f"self._packet.packet_type: {self._packet.packet_type}")
        #     print(f"duration: {duration}")


        return duration
    
    def setup_packet_model(self):
        return create_packet(self.config)

    def overlaps(self, other_node):
        """
            Comparing two node wether its overlaps based on the transmission time. 
            The input we used for this function is performed by comparing two node object, and its classes
        
        """
        return (
            self.channel == other_node._rf.channel and
            self.tx_start < other_node._rf.tx_end and
            other_node._rf.tx_start < self.tx_end
        )
    
    def energy_transmit(self, duration):
        return self.V * self.I_TX_dict[self.P_TX] * duration
    
    def energy_receive(self, duration):
        return self.V * self.I_RX * duration
    
    def energy_listening(self, duration):
        return self.V * self.I_RX * duration
    
    
    def calculate_beacon_interval(self):
        return self.aBaseSuperframeDuration * 2**self.BO * self.SYMBOL_DURATION
    
        

    
    # def schedule_transmission(
    #         self,
    #         transmitter,
    #         packet,
    #         time
    # ):
        
        






