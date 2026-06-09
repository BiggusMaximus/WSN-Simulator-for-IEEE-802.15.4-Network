from abstract.mcu import MCU

class ESP32_C6(MCU):
    def __init__(
        self,
        config,
    ):
        super().__init__(config)
        self.I_MS = float(self.params['I_MS'])  
        self.I_LS = float(self.params['I_LS'])
        self.V = float(self.params['V'])
        self.ppm = float(self.params['ppm'])


    
    def energy_transmit(self, duration):
        return 0

    def energy_receive(self, duration):
        return 0

    def energy_listening(self, duration):
        return self.I_LS * self.V * duration

    def energy_sleep(self, duration):
        return self.I_LS * self.V * duration

    def energy_sensing(self, duration):
        return self.I_MS * self.V * duration
    
    def energy_writting_and_logging(self, duration):
        return self.I_MS * self.V * duration
    