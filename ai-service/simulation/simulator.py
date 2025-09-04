import random
from typing import List, Dict, Any


class ASLSimulator:
    """
    Placeholder for an ASL/Webots-backed simulator.
    Currently generates plausible sensor telemetry.
    """

    def __init__(self):
        self.state = {
            'rpm': 1200.0,
            'engine_temp_coolant': 85.0,
            'oil_pressure': 3.0,
            'fuel_leak': False,
            'vibration': 1.2,
        }

    def step(self) -> List[Dict[str, Any]]:
        # basic random walk dynamics similar to what a simulator would output
        def clamp(v, lo, hi):
            return max(lo, min(hi, v))

        self.state['rpm'] = clamp(self.state['rpm'] + random.uniform(-50, 50), 0, 3000)
        self.state['engine_temp_coolant'] = clamp(self.state['engine_temp_coolant'] + random.uniform(-1.0, 1.5), 20, 120)
        self.state['oil_pressure'] = clamp(self.state['oil_pressure'] + random.uniform(-0.1, 0.1), 1, 10)
        if random.random() < 0.01:
            self.state['fuel_leak'] = not self.state['fuel_leak']
        self.state['vibration'] = clamp(self.state['vibration'] + random.uniform(-0.2, 0.3), 0, 10)

        sensors = [
            { 'id': 'rpm', 'type': 'RPM', 'value': round(self.state['rpm'], 1), 'min': 0, 'max': 3000, 'unit': 'об/мин' },
            { 'id': 'engine_temp_coolant', 'type': 'temperature_coolant', 'value': round(self.state['engine_temp_coolant'], 1), 'min': 20, 'max': 120, 'unit': '°C' },
            { 'id': 'oil_pressure', 'type': 'pressure_oil', 'value': round(self.state['oil_pressure'], 2), 'min': 1, 'max': 10, 'unit': 'bar' },
            { 'id': 'fuel_leak', 'type': 'fuel_leak', 'value': self.state['fuel_leak'] },
            { 'id': 'vibration', 'type': 'vibration', 'value': round(self.state['vibration'], 2), 'min': 0, 'max': 10, 'unit': 'm/s²' },
        ]
        return sensors


