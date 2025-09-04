import { Module } from '@nestjs/common';
import { AiModule } from '../ai/ai.module';
import { AlertsModule } from '../alerts/alerts.module';
import { SensorsService } from './sensors/sensors.service';
import { SensorsController } from './sensors/sensors.controller';

@Module({
  imports: [AiModule, AlertsModule],
  controllers: [SensorsController],
  providers: [SensorsService]
})
export class SensorsModule {}
