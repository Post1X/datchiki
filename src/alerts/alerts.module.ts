import { Module } from '@nestjs/common';
import { AlertsService } from './alerts/alerts.service';
import { AlertsGateway } from './alerts/alerts.gateway';

@Module({
  providers: [AlertsService, AlertsGateway],
  exports: [AlertsService, AlertsGateway]
})
export class AlertsModule {}
