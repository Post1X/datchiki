import { Injectable } from '@nestjs/common';
import axios from 'axios';

@Injectable()
export class AiService {
  async simulateSensors(): Promise<any[]> {
    try {
      const res = await axios.get('http://localhost:5000/simulate');
      return res.data?.sensors ?? [];
    } catch (error) {
      console.error('AI simulation error', error);
      return [];
    }
  }
  async analyzeSensor(sensorData: any): Promise<'normal' | 'warning' | 'critical'> {
    try {
      const res = await axios.post('http://localhost:5000/analyze', sensorData);
      return res.data.risk;
    } catch (error) {
      console.error('AI analysis error', error);
      return 'normal';
    }
  }
}
