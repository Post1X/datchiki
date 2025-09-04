import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { SensorsModule } from './sensors/sensors.module';
import { AlertsModule } from './alerts/alerts.module';
import { AiModule } from './ai/ai.module';

@Module({
  imports: [SensorsModule, AlertsModule, AiModule],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
