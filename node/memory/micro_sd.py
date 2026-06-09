from abstract.memory import Memory

class microSD(Memory):
    def __init__(
        self,
        config,
    ):
        super().__init__(config)
        self.I_read  = float(self.params['I_read'])
        self.I_write = float(self.params['I_write'])
        self.T_read  = float(self.params['T_read'])
        self.T_write = float(self.params['T_write'])
        self.V_operating = float(self.params['V_operating'])
        self.packet_size = float(self.params['packet_size'])

    
    def energy_writting_and_logging(self) -> float:
        return (1/8) * (self.packet_size * 8 * self.V_operating ) * (self.I_write * self.T_write + self.I_read * self.T_read)
    