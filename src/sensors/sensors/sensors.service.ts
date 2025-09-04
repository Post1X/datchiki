import { Injectable, OnModuleInit } from '@nestjs/common';
import { AiService } from '../../ai/ai/ai.service';
import { AlertsGateway } from '../../alerts/alerts/alerts.gateway';

interface Sensor {
  id: string;
  type: string;
  value: number | boolean | string;
  min?: number;
  max?: number;
  unit?: string;
  critical: boolean;
  risk_probability?: number;
  severity?: 'normal' | 'warning' | 'critical';
}

@Injectable()
export class SensorsService implements OnModuleInit {
  constructor(
    private readonly aiService: AiService,
    private readonly alertsGateway: AlertsGateway,
  ) {}

  sensors: Sensor[] = [
    { id: 'rpm', type: 'RPM', value: 0, min: 0, max: 3000, unit: 'об/мин', critical: false },
    { id: 'engine_temp_coolant', type: 'temperature_coolant', value: 0, min: 20, max: 120, unit: '°C', critical: false },
    { id: 'oil_pressure', type: 'pressure_oil', value: 0, min: 1, max: 10, unit: 'bar', critical: false },
    { id: 'fuel_leak', type: 'fuel_leak', value: false, critical: false },
    { id: 'vibration', type: 'vibration', value: 0, min: 0, max: 10, unit: 'm/s²', critical: false },
  ];

  async onModuleInit() {
    console.log('[NEST-BOOT] SensorsService initialized');

    setInterval(async () => {
      const sensors = await this.simulateSensors();
      console.log(`[NEST-SIM-EMIT] count=${sensors.length}`);
      this.alertsGateway.emit('sensors:update', sensors);
    }, 3000); 
  }

  async simulateSensors(): Promise<Sensor[]> {
    // Получаем симулированные данные и риски из Python (Webots/ASL + PySAD/Sintel)
    const simulated = await this.aiService.simulateSensors();

    // Приводим к нашему типу и логируем
    this.sensors = (simulated || []).map((s: any) => {
      const severity = s.severity as 'normal' | 'warning' | 'critical' | undefined;
      const prob = typeof s.risk_probability === 'number' ? s.risk_probability : undefined;
      const critical = severity === 'critical';
      const status = critical ? 'NOT OK' : 'OK';
      console.log(`[${status}] ${s.id}: ${s.value}` + (prob !== undefined ? ` (p=${prob})` : ''));
      return {
        id: s.id,
        type: s.type,
        value: s.value,
        min: s.min,
        max: s.max,
        unit: s.unit,
        critical,
        severity,
        risk_probability: prob,
      } as Sensor;
    });

    return this.sensors;
  }
}
