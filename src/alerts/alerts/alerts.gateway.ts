import { WebSocketGateway, WebSocketServer } from '@nestjs/websockets';
import { Server } from 'socket.io';

@WebSocketGateway({ path: '/alerts', cors: { origin: '*' } })
export class AlertsGateway {
  @WebSocketServer()
  server!: Server;

  emit(event: string, data: unknown) {
    this.server?.emit(event, data);
  }
}


