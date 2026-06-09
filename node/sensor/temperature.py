from abstract.sensor import Sensor

class DS18B20(Sensor):
    def __init__(self, config):
        super().__init__(config)

    def energy_sensing(self):
        return self.power_sensing * self.t_sensing
    
    def power_sensing(self):
        return self.data_size * self.voltage * self.I_sensing

class DHT22(Sensor):
    def __init__(self, config):
        super().__init__(config)

    def energy_sensing(self):
        return self.power_sensing * self.t_sensing
    
    def power_sensing(self):
        return self.data_size * self.voltage * self.I_sensing

class BMP280(Sensor):
    def __init__(self, config):
        super().__init__(config)

    def energy_sensing(self):
        return self.power_sensing() * self.T_sensing
    
    def power_sensing(self):
        return self.V_sensing * self.I_sensing

        