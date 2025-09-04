import { Controller, Get, Post, Body } from '@nestjs/common';
import { SensorsService } from './sensors.service';
import { AlertsGateway } from '../../alerts/alerts/alerts.gateway';

@Controller('sensors')
export class SensorsController {
  constructor(
    private readonly sensorsService: SensorsService,
    private readonly alertsGateway: AlertsGateway,
  ) {}

  @Get('test')
  async testSensors(): Promise<any> {
    await this.sensorsService.simulateSensors();
    return this.sensorsService.sensors;
  }

  @Post('ingest')
  async ingest(@Body() body: any): Promise<{ ok: boolean; count: number }>{
    const sensors = Array.isArray(body?.sensors) ? body.sensors : [];
    // Map incoming analyzed sensors to service state and emit immediately
    this.sensorsService.sensors = sensors.map((s: any) => ({
      id: s.id,
      type: s.type,
      value: s.value,
      min: s.min,
      max: s.max,
      unit: s.unit,
      critical: s.severity === 'critical',
    }));
    // Log and emit
    for (const s of sensors) {
      const status = s.severity === 'critical' ? 'NOT OK' : 'OK';
      const probStr = typeof s.risk_probability === 'number' ? ` p=${s.risk_probability}` : '';
      console.log(`[NEST-INGEST] ${s.id}=${s.value} status=${status}${probStr}`);
    }
    console.log(`[NEST-EMIT] sensors:update count=${sensors.length}`);
    this.alertsGateway.emit('sensors:update', sensors);
    return { ok: true, count: sensors.length };
  }
}


