from abstract.sensor import Sensor
from .temperature import DS18B20, DHT22, BMP280
from utils.information import console

SENSOR_REGISTRY = {
    'DS18B20': DS18B20,
    'DHT22': DHT22,
    'BMP280': BMP280,
}

def create_sensor(config) -> Sensor:
    sensor_name = config["Sensor"]["name"]

    if sensor_name not in SENSOR_REGISTRY:
        console.print(f"[bold red]Unknown Sensor hardware: {sensor_name}. Available: {SENSOR_REGISTRY.keys()}[/bold red]")

    return SENSOR_REGISTRY[sensor_name](config)