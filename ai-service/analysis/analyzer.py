from typing import Dict, Any

try:
    # Placeholder: in a real setup load PySAD/Sintel models
    import numpy as np  # noqa: F401
except Exception:  # keep working even without numpy
    pass


class RiskAnalyzer:
    """
    Placeholder wrapper for PySAD / Sintel-based anomaly & risk scoring.
    Currently computes simple probabilistic-looking scores.
    """
    def __init__(self):
        self.prev_frame = {}
        self.emergency_active = False
        self.emergency_clear_streak = 0

    def score(self, sensor: Dict[str, Any]) -> Dict[str, Any]:
        s_id = str(sensor.get('id'))
        value = sensor.get('value')

        def resp(sev: str, p: float) -> Dict[str, Any]:
            return { 'id': s_id, 'severity': sev, 'risk_probability': round(float(max(0.0, min(1.0, p))), 3) }

        if s_id == 'rpm' and isinstance(value, (int, float)):
            # Assume genset nominal 1500 rpm (50 Hz). Idle band: 600–800.
            nominal = 1500.0
            dev = abs(value - nominal) / nominal
            if 600 <= value <= 800:
                return resp('normal', 0.05)
            if dev <= 0.08:
                return resp('normal', 0.1)
            if dev <= 0.12:
                return resp('warning', 0.5)
            return resp('critical', 0.9)

        if s_id == 'engine_temp_coolant' and isinstance(value, (int, float)):
            if 80 <= value <= 95:
                return resp('normal', 0.05)
            if 96 <= value <= 104:
                return resp('warning', 0.5)
            if value >= 105:
                return resp('critical', 0.92 if value >= 110 else 0.8)
            return resp('warning', 0.4)

        if s_id == 'oil_temp' and isinstance(value, (int, float)):
            if 80 <= value <= 110:
                return resp('normal', 0.05)
            if 111 <= value <= 120:
                return resp('warning', 0.6)
            if value >= 121:
                return resp('critical', 0.92 if value >= 130 else 0.82)
            return resp('warning', 0.4)

        if s_id == 'oil_pressure' and isinstance(value, (int, float)):
            # Норма 2.5–5.0; предупреждение рядом с границами; критика только при явных выходах
            if 2.5 <= value <= 5.0:
                return resp('normal', 0.06)
            if (2.0 <= value < 2.5) or (5.0 < value <= 6.0):
                return resp('warning', 0.5)
            if value < 1.5 or value > 7.0:
                return resp('critical', 0.9)
            return resp('warning', 0.6)

        if s_id == 'fuel_pressure' and isinstance(value, (int, float)):
            if 2.5 <= value <= 5.0:
                return resp('normal', 0.06)
            if (2.0 <= value < 2.5) or (5.0 < value <= 6.0):
                return resp('warning', 0.5)
            if value < 1.8 or value > 7.0:
                return resp('critical', 0.9)
            return resp('warning', 0.6)

        if s_id == 'fuel_level' and isinstance(value, (int, float)):
            if value >= 30:
                return resp('normal', 0.05)
            if 15 <= value < 30:
                return resp('warning', 0.5)
            return resp('critical', 0.9)

        if s_id == 'fuel_consumption' and isinstance(value, (int, float)):
            # Контекст нагрузки по RPM: до ~1300 считаем низкой/средней, выше — высокой
            rpm = self.prev_frame.get('rpm')
            if isinstance(rpm, (int, float)) and rpm >= 1300:
                if value <= 120:
                    return resp('normal', 0.08)
                if value <= 140:
                    return resp('warning', 0.55)
                return resp('critical', 0.9)
            else:
                if value <= 40:
                    return resp('normal', 0.08)
                if value <= 60:
                    return resp('warning', 0.55)
                return resp('critical', 0.9)

        if s_id == 'voltage' and isinstance(value, (int, float)):
            # 24V system typical
            if (24.0 <= value <= 25.5) or (27.2 <= value <= 28.4):
                return resp('normal', 0.06)
            if (22.5 <= value < 24.0) or (28.5 <= value <= 29.5):
                return resp('warning', 0.55)
            return resp('critical', 0.9)

        if s_id == 'current' and isinstance(value, (int, float)):
            if 10 <= value <= 150:
                return resp('normal', 0.08)
            if 150 < value <= 220:
                return resp('warning', 0.55)
            return resp('critical', 0.9)

        if s_id == 'ecu_errors':
            # numeric 0/1 or bool
            is_crit = (value is True) or (isinstance(value, (int, float)) and value >= 2)
            if is_crit:
                return resp('critical', 0.92)
            has_warn = (isinstance(value, (int, float)) and value == 1)
            if has_warn:
                return resp('warning', 0.6)
            return resp('normal', 0.05)

        if s_id in ('fuel_leak', 'oil_leak'):
            if bool(value):
                return resp('critical', 0.97)
            return resp('normal', 0.03)

        if s_id == 'coolant_pressure' and isinstance(value, (int, float)):
            if 0.8 <= value <= 1.5:
                return resp('normal', 0.06)
            if (0.6 <= value < 0.8) or (1.5 < value <= 1.8):
                return resp('warning', 0.55)
            return resp('critical', 0.9)

        if s_id == 'overheat':
            # bool or temperature-like value
            if isinstance(value, (int, float)):
                if value <= 110:
                    return resp('normal', 0.05)
                if value <= 120:
                    return resp('warning', 0.6)
                return resp('critical', 0.92)
            else:
                if bool(value):
                    return resp('critical', 0.95)
                return resp('normal', 0.03)

        if s_id == 'vibration' and isinstance(value, (int, float)):
            if 0.1 <= value <= 3.0:
                return resp('normal', 0.08)
            if 3.0 < value <= 5.0:
                return resp('warning', 0.6)
            return resp('critical', 0.9)

        if s_id == 'emergency_stop':
            if bool(value):
                return resp('critical', 0.99)
            return resp('normal', 0.02)

        # Fallback generic numeric/bool handling
        if isinstance(value, (int, float)):
            vmin = sensor.get('min', 0) or 0
            vmax = sensor.get('max', 1) or 1
            span = max(1e-6, vmax - vmin)
            dist = min(abs(value - vmin), abs(vmax - value)) / span
            p = max(0.0, 1.0 - 2.0 * dist)
            sev = 'critical' if p > 0.85 else 'warning' if p > 0.6 else 'normal'
            return resp(sev, p)
        if isinstance(value, bool):
            return resp('critical' if value else 'normal', 0.95 if value else 0.05)
        return resp('normal', 0.1)

    def analyze_frame(self, sensors: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        # Build map by id for convenience
        by_id = { str(s.get('id')): s for s in sensors if isinstance(s, dict) and s.get('id') }

        # Score base sensors first
        scored = {}
        for sid, s in by_id.items():
            try:
                scored[sid] = self.score(s)
            except Exception:
                scored[sid] = { 'id': sid, 'severity': 'normal', 'risk_probability': 0.1 }

        # Helper getters
        def num(id_: str, default=None):
            v = by_id.get(id_, {}).get('value')
            return v if isinstance(v, (int, float)) else default

        rpm = num('rpm', 0.0)
        fuel_p = num('fuel_pressure')
        oil_p = num('oil_pressure')
        volt = num('voltage')
        vib = num('vibration')
        cool_t = num('engine_temp_coolant')
        oil_t = num('oil_temp')
        cool_p = num('coolant_pressure')
        fuel_level_now = num('fuel_level')
        cons = num('fuel_consumption', 0.0)  # l/h approx

        prev = self.prev_frame
        rpm_prev = prev.get('rpm')
        fuel_level_prev = prev.get('fuel_level')

        # Compute anomalies count for ecu_errors according to rules
        anomalies = 0
        # fuel pressure outside normal
        if scored.get('fuel_pressure', {}).get('severity') in ('warning', 'critical'):
            anomalies += 1
        # too low oil pressure for current RPM
        if isinstance(oil_p, (int, float)) and isinstance(rpm, (int, float)):
            if rpm >= 1200 and oil_p < 2.0:
                anomalies += 1
        # voltage deviation
        if scored.get('voltage', {}).get('severity') in ('warning', 'critical'):
            anomalies += 1
        # strong RPM jitter with low fuel pressure
        if isinstance(rpm, (int, float)) and isinstance(rpm_prev, (int, float)):
            if fuel_p is not None and scored.get('fuel_pressure', {}).get('severity') in ('warning', 'critical'):
                if abs(rpm - rpm_prev) > 150:
                    anomalies += 1
        # too cold coolant at high load
        if isinstance(cool_t, (int, float)) and isinstance(rpm, (int, float)) and isinstance(cons, (int, float)):
            if cool_t < 70 and rpm > 1300 and cons > 20:
                anomalies += 1

        ecu_errors_val = anomalies
        # 0 — норм; 1–2 — внимание; >=3 — авария
        ecu_errors_sev = 'normal' if anomalies == 0 else ('warning' if anomalies <= 2 else 'critical')

        # Fuel leak detection by fuel level drop beyond expected
        fuel_leak_val = None
        if isinstance(fuel_level_prev, (int, float)) and isinstance(fuel_level_now, (int, float)):
            drop = fuel_level_prev - fuel_level_now
            # более консервативные пороги: критично при >3%, предупреждение при >1.2% и малом расходе
            if drop > 3.0:
                fuel_leak_val = 'critical'
            elif drop > 1.2 and (cons is None or cons < 10):
                fuel_leak_val = 'warning'
            else:
                fuel_leak_val = 'normal'
        # if not enough data keep previous state if present
        if fuel_leak_val is None:
            prev_leak = prev.get('fuel_leak')
            fuel_leak_val = bool(prev_leak) if prev_leak is not None else False

        # Overheat determination
        overheat_val = False
        overheat_sev = 'normal'
        if (isinstance(cool_t, (int, float)) and cool_t >= 105) or (isinstance(oil_t, (int, float)) and oil_t >= 121):
            overheat_val = True
            overheat_sev = 'critical' if (cool_t and cool_t >= 110) or (oil_t and oil_t >= 130) else 'warning'
        if isinstance(cool_p, (int, float)) and isinstance(cool_t, (int, float)):
            if cool_p > 1.5 and cool_t > 100:
                overheat_val = True
                overheat_sev = 'critical'

        # Emergency stop logic with auto-clear after stabilization
        emergency = self.emergency_active
        # Сделать триггеры более строгими, чтобы избежать ложных срабатываний
        extreme_oil = isinstance(oil_p, (int, float)) and oil_p < 1.0
        extreme_temp = isinstance(cool_t, (int, float)) and cool_t >= 125
        extreme_volt = isinstance(volt, (int, float)) and (volt < 22.0 or volt > 30.0)
        extreme_vib = isinstance(vib, (int, float)) and vib > 6.5
        low_fuel = isinstance(fuel_level_now, (int, float)) and fuel_level_now < 15
        confirmed_leak = bool(fuel_leak_val)
        triggers = [extreme_oil, extreme_temp, extreme_volt, extreme_vib, (confirmed_leak and low_fuel)]
        if any(triggers):
            emergency = True
            self.emergency_clear_streak = 0
        else:
            # count consecutive stable frames to clear
            all_normal = all(scored.get(k, {}).get('severity') == 'normal' for k in (
                'oil_pressure', 'engine_temp_coolant', 'voltage', 'vibration', 'fuel_pressure')) and not confirmed_leak
            if all_normal:
                self.emergency_clear_streak += 1
                if self.emergency_clear_streak >= 2:
                    emergency = False
                    self.emergency_clear_streak = 0
            else:
                self.emergency_clear_streak = 0

        self.emergency_active = emergency

        # Build enriched output
        enriched = []
        for sid, s in by_id.items():
            base = { **s }
            sev = scored.get(sid, {}).get('severity', 'normal')
            prob = scored.get(sid, {}).get('risk_probability', 0.1)
            base['severity'] = sev
            base['risk_probability'] = prob
            enriched.append(base)

        # Override or append derived signals
        def set_or_add(id_, value, severity, prob):
            found = False
            for it in enriched:
                if it.get('id') == id_:
                    it['value'] = value
                    it['severity'] = severity
                    it['risk_probability'] = prob
                    found = True
                    break
            if not found:
                enriched.append({ 'id': id_, 'type': id_, 'value': value, 'severity': severity, 'risk_probability': prob })

        set_or_add('ecu_errors', ecu_errors_val, ecu_errors_sev, 0.9 if ecu_errors_sev == 'critical' else (0.6 if ecu_errors_sev == 'warning' else 0.05))
        # fuel_leak: различаем warning/critical
        if fuel_leak_val == 'critical':
            set_or_add('fuel_leak', True, 'critical', 0.97)
        elif fuel_leak_val == 'warning':
            set_or_add('fuel_leak', True, 'warning', 0.6)
        else:
            set_or_add('fuel_leak', False, 'normal', 0.03)
        set_or_add('overheat', bool(overheat_val), overheat_sev, 0.9 if overheat_sev == 'critical' else (0.6 if overheat_sev == 'warning' else 0.05))
        set_or_add('emergency_stop', bool(emergency), 'critical' if emergency else 'normal', 0.99 if emergency else 0.02)

        # Save state for next frame
        self.prev_frame = {
            'rpm': rpm,
            'fuel_level': fuel_level_now,
            'fuel_leak': bool(fuel_leak_val),
        }

        return enriched


