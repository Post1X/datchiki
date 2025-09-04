import os
import random
from typing import List, Dict, Any


RANGES = {
    "rpm": { "unit": "об/мин", "normal": (600, 800), "nominal": 1500, "warningPct": 0.08, "criticalPct": 0.12, "min": 0, "max": 3000 },
    "engine_temp_coolant": { "unit": "°C", "normal": (80, 95), "warning": (96, 104), "critical": (105, 120), "min": 20, "max": 120 },
    "oil_temp": { "unit": "°C", "normal": (80, 110), "warning": (111, 120), "critical": (121, 150), "min": 20, "max": 150 },
    "oil_pressure": { "unit": "bar", "normal": (2.5, 5.0), "idleMin": 1.0, "warning": (2.0, 2.5), "criticalBelowIdle": 0.8, "criticalBelowLoad": 2.0, "min": 0.5, "max": 10 },
    "fuel_pressure": { "unit": "bar", "normal": (2.5, 5.0), "warningLow": 2.0, "warningHigh": 6.0, "criticalLow": 2.0, "criticalHigh": 6.0, "min": 0.5, "max": 8 },
    "fuel_level": { "unit": "%", "normal": (30, 100), "warning": (15, 30), "critical": (0, 15), "min": 0, "max": 100 },
    "fuel_consumption": { "unit": "л/ч", "normal": (10, 120), "min": 0, "max": 150 },
    "voltage": { "unit": "В", "rest": (24.0, 25.5), "charge": (27.2, 28.4), "warningLow": 22.5, "warningHigh": 29.5, "criticalLow": 22.5, "criticalHigh": 29.5, "min": 20, "max": 32 },
    "current": { "unit": "А", "normal": (10, 150), "warning": (150, 220), "criticalAbove": 220, "min": 0, "max": 400 },
    "coolant_pressure": { "unit": "bar", "normal": (0.8, 1.5), "warningLow": 0.6, "warningHigh": 1.8, "criticalLow": 0.6, "criticalHigh": 1.8, "min": 0.3, "max": 2.5 },
    "vibration": { "unit": "м/с²", "normal": (0.1, 3.0), "warning": (3.0, 5.0), "criticalAbove": 5.0, "min": 0, "max": 10 },
}


class RuleSimulator:
    """
    Генератор телеметрии на основе нормативов. Вероятности режимов настраиваются:
    - SIM_P_NORMAL (default 0.92)
    - SIM_P_WARNING (default 0.07)
    - SIM_P_CRITICAL (default 0.01)
    Можно быстро инвертировать профиль, установив SIM_PROFILE=stress (0.6/0.3/0.1)
    """

    def __init__(self):
        profile = os.getenv('SIM_PROFILE', 'safe').lower()
        if profile == 'stress':
            p_n, p_w, p_c = 0.6, 0.3, 0.1
        else:
            p_n = float(os.getenv('SIM_P_NORMAL', '0.92'))
            p_w = float(os.getenv('SIM_P_WARNING', '0.07'))
            p_c = float(os.getenv('SIM_P_CRITICAL', '0.01'))
        s = max(1e-6, p_n + p_w + p_c)
        self.p_normal, self.p_warning, self.p_critical = p_n / s, p_w / s, p_c / s

        # внутреннее состояние для зависимостей
        self.state = {
            'rpm': 1500.0,
            'fuel_level': 80.0,
        }

    def _pick_mode(self):
        r = random.random()
        if r < self.p_critical:
            return 'critical'
        if r < self.p_critical + self.p_warning:
            return 'warning'
        return 'normal'

    def _sample_range(self, a: float, b: float, jitter: float = 0.02) -> float:
        base = random.uniform(a, b)
        return base * (1.0 + random.uniform(-jitter, jitter))

    def step(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []

        # RPM
        rpm_cfg = RANGES['rpm']
        mode = self._pick_mode()
        if mode == 'normal':
            # около номинала
            value = self._sample_range(rpm_cfg['nominal'] * (1 - rpm_cfg['warningPct']/2), rpm_cfg['nominal'] * (1 + rpm_cfg['warningPct']/2), 0.01)
        elif mode == 'warning':
            value = self._sample_range(rpm_cfg['nominal'] * (1 - rpm_cfg['criticalPct']), rpm_cfg['nominal'] * (1 + rpm_cfg['criticalPct']), 0.02)
        else:
            # сильное отклонение
            side = -1 if random.random() < 0.5 else 1
            value = rpm_cfg['nominal'] * (1 + side * (rpm_cfg['criticalPct'] + random.uniform(0.02, 0.2)))
        value = max(rpm_cfg['min'], min(rpm_cfg['max'], value))
        self.state['rpm'] = value
        out.append({ 'id': 'rpm', 'type': 'RPM', 'value': round(value, 0), 'min': rpm_cfg['min'], 'max': rpm_cfg['max'], 'unit': rpm_cfg['unit'] })

        # Температуры
        def temp_from(cfg_key: str, prev: float | None) -> float:
            cfg = RANGES[cfg_key]
            mode = self._pick_mode()
            if mode == 'normal':
                lo, hi = cfg['normal']
            elif mode == 'warning':
                lo, hi = cfg['warning']
            else:
                lo, hi = cfg['critical']
            val = self._sample_range(lo, hi, 0.01)
            if prev is not None:
                val = prev + (val - prev) * random.uniform(0.1, 0.4)
            return max(cfg['min'], min(cfg['max'], val))

        ect_prev = None
        ect = temp_from('engine_temp_coolant', ect_prev)
        out.append({ 'id': 'engine_temp_coolant', 'type': 'temperature_coolant', 'value': round(ect, 1), 'min': 20, 'max': 120, 'unit': '°C' })

        ot_prev = None
        ot = temp_from('oil_temp', ot_prev)
        out.append({ 'id': 'oil_temp', 'type': 'temperature_oil', 'value': round(ot, 1), 'min': 20, 'max': 150, 'unit': '°C' })

        # Давления
        op_cfg = RANGES['oil_pressure']
        mode = self._pick_mode()
        if mode == 'normal':
            lo, hi = op_cfg['normal']
        elif mode == 'warning':
            lo, hi = op_cfg['warning']
        else:
            lo, hi = (op_cfg['min'], op_cfg['criticalBelowLoad'])
        oil_p = self._sample_range(lo, hi, 0.03)
        out.append({ 'id': 'oil_pressure', 'type': 'pressure_oil', 'value': round(oil_p, 2), 'min': op_cfg['min'], 'max': op_cfg['max'], 'unit': 'bar' })

        fp_cfg = RANGES['fuel_pressure']
        mode = self._pick_mode()
        if mode == 'normal':
            lo, hi = fp_cfg['normal']
        elif mode == 'warning':
            lo, hi = (fp_cfg['warningLow'], fp_cfg['warningHigh'])
        else:
            # за пределами warning
            if random.random() < 0.5:
                lo, hi = (0.3, fp_cfg['criticalLow'])
            else:
                lo, hi = (fp_cfg['criticalHigh'], 8.0)
        fp = self._sample_range(lo, hi, 0.03)
        out.append({ 'id': 'fuel_pressure', 'type': 'pressure_fuel', 'value': round(fp, 2), 'min': fp_cfg['min'], 'max': fp_cfg['max'], 'unit': 'bar' })

        # Уровень/расход топлива
        cons_cfg = RANGES['fuel_consumption']
        # расход зависит от RPM: до 1300 — нижняя половина нормального, выше — верхняя
        if self.state['rpm'] < 1300:
            lo, hi = 10, 40
        else:
            lo, hi = 40, 120
        cons = self._sample_range(lo, hi, 0.08)
        out.append({ 'id': 'fuel_consumption', 'type': 'consumption_fuel', 'value': round(cons, 1), 'min': cons_cfg['min'], 'max': cons_cfg['max'], 'unit': cons_cfg['unit'] })
        # простая модель расхода %/шаг
        drop_pct = cons * 0.005 / 60.0  # эвристика
        if random.random() < 0.01:
            drop_pct *= random.uniform(2, 5)  # редкие скачки/утечки
        self.state['fuel_level'] = max(0.0, self.state['fuel_level'] - drop_pct)
        fl_cfg = RANGES['fuel_level']
        out.append({ 'id': 'fuel_level', 'type': 'level_fuel', 'value': round(self.state['fuel_level'], 1), 'min': fl_cfg['min'], 'max': fl_cfg['max'], 'unit': fl_cfg['unit'] })

        # Напряжение/ток
        v_cfg = RANGES['voltage']
        if random.random() < 0.5:
            lo, hi = v_cfg['rest']
        else:
            lo, hi = v_cfg['charge']
        volt = self._sample_range(lo, hi, 0.01)
        if random.random() < self.p_critical * 0.5:
            volt += random.choice([-1.5, 1.5])  # редкие выбросы
        out.append({ 'id': 'voltage', 'type': 'voltage', 'value': round(volt, 2), 'min': v_cfg['min'], 'max': v_cfg['max'], 'unit': v_cfg['unit'] })

        cur_cfg = RANGES['current']
        cur = self._sample_range(cur_cfg['normal'][0], cur_cfg['normal'][1], 0.05)
        if random.random() < self.p_warning:
            cur = self._sample_range(cur_cfg['warning'][0], cur_cfg['warning'][1], 0.05)
        if random.random() < self.p_critical * 0.3:
            cur = self._sample_range(cur_cfg['criticalAbove'], cur_cfg['criticalAbove'] + 80, 0.05)
        out.append({ 'id': 'current', 'type': 'current', 'value': round(cur, 1), 'min': cur_cfg['min'], 'max': cur_cfg['max'], 'unit': cur_cfg['unit'] })

        # Давление ОЖ
        cp_cfg = RANGES['coolant_pressure']
        if ect >= 100 and random.random() < self.p_warning:
            lo, hi = (cp_cfg['warningLow'], cp_cfg['warningHigh'])
        else:
            lo, hi = cp_cfg['normal']
        cpress = self._sample_range(lo, hi, 0.03)
        out.append({ 'id': 'coolant_pressure', 'type': 'pressure_coolant', 'value': round(cpress, 2), 'min': cp_cfg['min'], 'max': cp_cfg['max'], 'unit': 'bar' })

        # Вибрация
        vib_cfg = RANGES['vibration']
        vib = self._sample_range(vib_cfg['normal'][0], vib_cfg['normal'][1], 0.1)
        if random.random() < self.p_warning:
            vib = self._sample_range(vib_cfg['warning'][0], vib_cfg['warning'][1], 0.1)
        if random.random() < self.p_critical * 0.2:
            vib = self._sample_range(vib_cfg['criticalAbove'], vib_cfg['criticalAbove'] + 3, 0.2)
        out.append({ 'id': 'vibration', 'type': 'vibration', 'value': round(vib, 2), 'min': vib_cfg['min'], 'max': vib_cfg['max'], 'unit': vib_cfg['unit'] })

        # Логические флаги (редкие события)
        fuel_leak = random.random() < (self.p_critical * 0.1)
        overheat = (ect >= 111) or (ot >= 121) or (cpress > 1.5 and ect > 100)
        emergency = False  # финально решает анализатор по кадру

        out.append({ 'id': 'fuel_leak', 'type': 'fuel_leak', 'value': fuel_leak })
        out.append({ 'id': 'overheat', 'type': 'overheat', 'value': overheat })
        out.append({ 'id': 'emergency_stop', 'type': 'emergency_stop', 'value': emergency })
        out.append({ 'id': 'ecu_errors', 'type': 'ecu_errors', 'value': 0 })

        return out


