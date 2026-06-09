from abstract.mcu import MCU

class STM32L476RG(MCU):
    def __init__(
        self,
        config,
    ):
        super().__init__(config)
        self.I_MS = self.params['I_MS']  
        self.I_LS = self.params['I_LS']
        self.V = self.params['V_MS']

    
    def energy_transmit(duration):
        return 0

    def energy_receive(duration):
        return 0

    def energy_listening(duration):
        return self.I_LS * self.V * duration

    def energy_sleep(duration):
        return self.I_MS * self.V * duration

    def energy_sensing(duration):
        return self.I_MS * self.V * duration
    
    def energy_logging(duration):
        return self.I_MS * self.V * duration
    