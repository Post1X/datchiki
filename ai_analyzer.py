from flask import Flask, request, jsonify
import os, sys
# Make 'ai-service' modules importable despite hyphen in directory name
sys.path.append(os.path.join(os.path.dirname(__file__), 'ai-service'))
from simulation.simulator import ASLSimulator
from simulation.webots_adapter import WebotsAdapter
from analysis.analyzer import RiskAnalyzer
from analysis.pysad_adapter import PySADAdapter
import threading
import requests

app = Flask(__name__)
webots = WebotsAdapter()
pysad = PySADAdapter()
sim = ASLSimulator()
analyzer = RiskAnalyzer()
latest_ingested = None  # type: ignore
SENSOR_MAPPING = {
    'rpm':            { 'id': 'rpm', 'type': 'RPM', 'min': 0,  'max': 3000, 'unit': 'об/мин' },
    'coolant_temp':   { 'id': 'engine_temp_coolant', 'type': 'temperature_coolant', 'min': 20, 'max': 120, 'unit': '°C' },
    'oil_temp':       { 'id': 'oil_temp', 'type': 'temperature_oil', 'min': 20, 'max': 150, 'unit': '°C' },
    'oil_pressure':   { 'id': 'oil_pressure', 'type': 'pressure_oil', 'min': 1,  'max': 10,  'unit': 'bar' },
    'fuel_pressure':  { 'id': 'fuel_pressure', 'type': 'pressure_fuel', 'min': 1,  'max': 8,   'unit': 'bar' },
    'fuel_level':     { 'id': 'fuel_level', 'type': 'level_fuel', 'min': 0,  'max': 100, 'unit': '%' },
    'fuel_consumption': { 'id': 'fuel_consumption', 'type': 'consumption_fuel', 'min': 0, 'max': 60, 'unit': 'l/h' },
    'voltage':        { 'id': 'voltage', 'type': 'voltage', 'min': 10, 'max': 32, 'unit': 'V' },
    'current':        { 'id': 'current', 'type': 'current', 'min': 0,  'max': 500, 'unit': 'A' },
    'ecu_errors':     { 'id': 'ecu_errors', 'type': 'ecu_errors' },
    'fuel_leak':      { 'id': 'fuel_leak', 'type': 'fuel_leak' },
    'coolant_pressure': { 'id': 'coolant_pressure', 'type': 'pressure_coolant', 'min': 0.5, 'max': 3, 'unit': 'bar' },
    'overheat':       { 'id': 'overheat', 'type': 'overheat' },
    'vibration':      { 'id': 'vibration', 'type': 'vibration', 'min': 0, 'max': 10, 'unit': 'm/s²' },
    'emergency_stop': { 'id': 'emergency_stop', 'type': 'emergency_stop' },
}

if webots.is_available():
    try:
        webots.connect()
        sim_backend = webots
    except Exception:
        sim_backend = sim
else:
    sim_backend = sim

if pysad.is_available():
    try:
        pysad.load_or_fit()
        analyzer_backend = pysad
    except Exception:
        analyzer_backend = analyzer
else:
    analyzer_backend = analyzer

@app.route('/simulate', methods=['GET'])
def simulate():
    global latest_ingested
    if latest_ingested:
        sensors = latest_ingested
    else:
        sensors = sim_backend.step()
    try:
        if hasattr(analyzer_backend, 'analyze_frame'):
            analyzed = analyzer_backend.analyze_frame(sensors)
        else:
            analyzed = []
            for s in sensors:
                try:
                    res = analyzer_backend.score(s)
                except Exception:
                    res = analyzer.score(s)
                analyzed.append({ **s, **res })
    except Exception:
        analyzed = []
        for s in sensors:
            try:
                res = analyzer.score(s)
            except Exception:
                res = { 'id': s.get('id'), 'severity': 'normal', 'risk_probability': 0.1 }
            analyzed.append({ **s, **res })
    return jsonify({ 'sensors': analyzed })

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json or {}
    try:
        res = analyzer_backend.score(data)
    except Exception:
        res = analyzer.score(data)
    return jsonify({'risk': res.get('severity'), 'probability': res.get('risk_probability')})

@app.route('/ingest', methods=['POST'])
def ingest():
    """
    Accept telemetry from external Webots supervisor controller.
    Body: { "sensors": [ {id, type, value, min?, max?, unit?}, ... ] }
    """
    global latest_ingested
    body = request.get_json(force=True, silent=True) or {}
    sensors = body.get('sensors')
    if isinstance(sensors, list):
        pass
    elif isinstance(body, dict):
        # Map flat telemetry dict into sensors array
        sensors = []
        for k, v in body.items():
            meta = SENSOR_MAPPING.get(k)
            if not meta:
                continue
            item = { **meta, 'value': v }
            sensors.append(item)
    else:
        sensors = []
    # basic logging of incoming Webots payload
    try:
        ids = [str(s.get('id')) for s in sensors if isinstance(s, dict)]
        print(f"[PY-INGEST] count={len(sensors)} ids={ids}", flush=True)
        if sensors:
            sample = sensors[0].copy()
            # avoid dumping huge payloads
            print(f"[PY-INGEST-SAMPLE] {sample}", flush=True)
    except Exception:
        pass

    # score now for instant forwarding
    analyzed = []
    for s in sensors:
        try:
            res = analyzer_backend.score(s)
        except Exception:
            res = analyzer.score(s)
        analyzed.append({ **s, **res })
    latest_ingested = analyzed

    # forward immediately to Nest for instant logging and socket emit
    def _forward():
        try:
            resp = requests.post('http://localhost:3000/sensors/ingest', json={'sensors': analyzed}, timeout=1.5)
            print(f"[PY-FWD->NEST] status={getattr(resp, 'status_code', 'n/a')} count={len(analyzed)}", flush=True)
        except Exception:
            print("[PY-FWD->NEST] error forwarding to Nest", flush=True)
    threading.Thread(target=_forward, daemon=True).start()

    return jsonify({ 'ok': True, 'count': len(sensors) })

@app.route('/telemetry', methods=['POST'])
def telemetry():
    # Alias for legacy/external clients sending to /telemetry
    return ingest()

if __name__ == '__main__':
    app.run(port=5000)
