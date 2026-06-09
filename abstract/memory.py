from abc import ABC, abstractmethod

'''
    SD card hardware related functionalities:
    1. Write data
    2. Read data
'''
class Memory(ABC):
    def __init__(
        self,
        config,
    ):
        memory_name = config['Memory']['name']
        self.params = config['Memory']['params'][memory_name]
    



# E = (1/8) * (data_size * V * I_write * T_write) 
# E = (1/8) * (data_size * V * I_read * T_read) 