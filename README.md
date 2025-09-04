# Мониторинг датчиков: Webots → Python AI → NestJS → Web UI

Полная связка для сбора телеметрии из Webots/ASL, анализа (PySAD/Sintel-плейсхолдер), мгновенных уведомлений через Socket.IO и просмотра на веб-дэшборде с мини-графиками.

## Архитектура

- `Webots Supervisor` → отправляет телеметрию в Python-сервис
- `Python (Flask) ai_analyzer.py`:
  - Эндпоинты: `/telemetry` (алиас), `/ingest` (прием), `/simulate` (последний кадр/симуляция), `/analyze` (оценка одного сенсора)
  - Аналитика: `ai-service/analysis/analyzer.py` (нормативы + правила для ecu_errors, fuel_leak, overheat, emergency_stop) и адаптер `pysad_adapter.py` (заглушка под PySAD/Sintel)
  - Симуляция: `ai-service/simulation/simulator.py` (ASL/Webots-плейсхолдер) и адаптер `webots_adapter.py` (каркас)
  - Мгновенно пересылает проанализированный кадр в Nest: `POST http://localhost:3000/sensors/ingest`
- `NestJS`:
  - `src/sensors/sensors.controller.ts` — `POST /sensors/ingest` принимает кадр, логирует и эмитит сокет `sensors:update`
  - `src/alerts/alerts/alerts.gateway.ts` — Socket.IO, путь `/alerts`
  - `src/sensors/sensors/sensors.service.ts` — опциональная периодическая симуляция (включается `SIMULATION_ENABLED=1`)
- `frontend/web`:
  - `index.html`, `app.js` — KPI, карточки, мини-«полоски»-графики для каждого сенсора, Socket.IO клиент

## Быстрый старт

1) Установите зависимости

```bash
cd <корень проекта>
yarn install
pip install flask
```

2) Запустите Python AI сервис

```bash
python ai_analyzer.py
# поднимет http://localhost:5000
```

3) Запустите NestJS

```bash
yarn start:dev
# Socket.IO: ws://localhost:3000/alerts
```

4) Webots Supervisor

- Отправляйте телеметрию (как плоский dict) в Python:

```python
API_URL = "http://localhost:5000/telemetry"
http_post(API_URL, {
  "rpm": 1500,
  "coolant_temp": 90,
  "oil_pressure": 3.5,
  ...
}, timeout=1)
```

Python преобразует и анализирует кадр, затем автоматически отправит его в Nest: `POST /sensors/ingest`.

5) Откройте веб-интерфейс

- Откройте файл `frontend/web/index.html` в браузере
- В реальном времени появятся карточки датчиков и мини-графики-полоски

## Эндпоинты

- Python
  - `POST /telemetry` — алиас на `/ingest`; принимает либо `{ sensors: [...] }`, либо плоский dict телеметрии
  - `POST /ingest` — принимает кадр, анализирует, кэширует и форвардит в Nest
  - `GET /simulate` — отдает последний проанализированный кадр; если нет — генерирует через симулятор
  - `POST /analyze` — анализ одного сенсора `{ id, value, min?, max? }`
- Nest
  - `POST /sensors/ingest` — мгновенный прием кадра, лог и Socket.IO `sensors:update`
  - WebSocket: путь `/alerts`, событие `sensors:update`

## Переменные окружения

- Python
  - `WEBOTS_ENABLED=1` — включить адаптер Webots (реализуйте `connect()` и `step()` в `webots_adapter.py`)
  - `PYSAD_ENABLED=1` — включить PySAD/Sintel адаптер (реализуйте `load_or_fit()` и `score()`)
- Nest
  - `SIMULATION_ENABLED=1` — включить периодический опрос Python `/simulate` каждые 10 сек (по умолчанию выключено)
  - `PORT` — порт Nest (по умолчанию 3000)

## Логика анализа (нормативы и правила)

Реализована в `ai-service/analysis/analyzer.py`:

- Нормативные диапазоны: `rpm`, `engine_temp_coolant`, `oil_temp`, `oil_pressure`, `fuel_pressure`, `fuel_level`, `fuel_consumption`, `voltage`, `current`, `coolant_pressure`, `vibration` и т.д.
- Производные флаги по кадру:
  - `ecu_errors`: накапливается при 2+ одновременных аномалиях (низкое масло при высоких RPM, отклонение напряжения, низкое давление топлива, джиттер RPM при низком давлении топлива, холодная ОЖ при высокой нагрузке). Сбрасывается при нормализации.
  - `fuel_leak`: аномально высокий спад `fuel_level` по сравнению с ожидаемым расходом.
  - `overheat`: по высокой температуре/давлению (ОЖ/масло, давление в контуре ОЖ при высокой температуре).
  - `emergency_stop`: при экстремальных условиях (очень низкое давление масла, перегрев, опасное напряжение, чрезмерная вибрация, подтвержденная утечка при низком уровне топлива), авто-сброс после устойчивой нормализации.

Возвращается для каждого сенсора: `severity` (`normal|warning|critical`) и `risk_probability` `[0..1]`.

## Веб-интерфейс

- KPI (Аварии/Внимание/Норма/Датчики)
- Карточки датчиков (русские названия, единицы, статус, вероятность)
- Мини-графики-полоски на каждый сенсор (DOM-отрисовка, без Chart.js)
  - Ровная линия = стабильность
  - Рост/падение последних баров = отклонения
  - Цвет последнего бара = статус (зеленый/оранжевый/красный)

## Логи

- Python: `[PY-INGEST]`, `[PY-INGEST-SAMPLE]`, `[PY-FWD->NEST]`
- Nest: `[NEST-BOOT]`, `[NEST-INGEST]`, `[NEST-EMIT]`, `[NEST-SIM-EMIT]`

## Дальнейшая интеграция

- Webots/ASL: реализовать реальные источники в `webots_adapter.py`
- PySAD/Sintel: подключить библиотеки и заменить эвристику на модель/детектор в `pysad_adapter.py`
- Авторизация, хранение истории в БД, алертинг по каналам (TG/Email/SMS)

## Скрипт контроллера Webots (пример)

```python
API_URL = "http://localhost:5000/telemetry"
data = {
  "rpm": 1500,
  "coolant_temp": 90,
  "oil_pressure": 3.5,
  # ... остальные метрики
}
http_post(API_URL, data, timeout=1)
```

## Лицензия

MIT

<p align="center">
  <a href="http://nestjs.com/" target="blank"><img src="https://nestjs.com/img/logo-small.svg" width="120" alt="Nest Logo" /></a>
</p>

[circleci-image]: https://img.shields.io/circleci/build/github/nestjs/nest/master?token=abc123def456
[circleci-url]: https://circleci.com/gh/nestjs/nest

  <p align="center">A progressive <a href="http://nodejs.org" target="_blank">Node.js</a> framework for building efficient and scalable server-side applications.</p>
    <p align="center">
<a href="https://www.npmjs.com/~nestjscore" target="_blank"><img src="https://img.shields.io/npm/v/@nestjs/core.svg" alt="NPM Version" /></a>
<a href="https://www.npmjs.com/~nestjscore" target="_blank"><img src="https://img.shields.io/npm/l/@nestjs/core.svg" alt="Package License" /></a>
<a href="https://www.npmjs.com/~nestjscore" target="_blank"><img src="https://img.shields.io/npm/dm/@nestjs/common.svg" alt="NPM Downloads" /></a>
<a href="https://circleci.com/gh/nestjs/nest" target="_blank"><img src="https://img.shields.io/circleci/build/github/nestjs/nest/master" alt="CircleCI" /></a>
<a href="https://discord.gg/G7Qnnhy" target="_blank"><img src="https://img.shields.io/badge/discord-online-brightgreen.svg" alt="Discord"/></a>
<a href="https://opencollective.com/nest#backer" target="_blank"><img src="https://opencollective.com/nest/backers/badge.svg" alt="Backers on Open Collective" /></a>
<a href="https://opencollective.com/nest#sponsor" target="_blank"><img src="https://opencollective.com/nest/sponsors/badge.svg" alt="Sponsors on Open Collective" /></a>
  <a href="https://paypal.me/kamilmysliwiec" target="_blank"><img src="https://img.shields.io/badge/Donate-PayPal-ff3f59.svg" alt="Donate us"/></a>
    <a href="https://opencollective.com/nest#sponsor"  target="_blank"><img src="https://img.shields.io/badge/Support%20us-Open%20Collective-41B883.svg" alt="Support us"></a>
  <a href="https://twitter.com/nestframework" target="_blank"><img src="https://img.shields.io/twitter/follow/nestframework.svg?style=social&label=Follow" alt="Follow us on Twitter"></a>
</p>
  <!--[![Backers on Open Collective](https://opencollective.com/nest/backers/badge.svg)](https://opencollective.com/nest#backer)
  [![Sponsors on Open Collective](https://opencollective.com/nest/sponsors/badge.svg)](https://opencollective.com/nest#sponsor)-->

## Description

[Nest](https://github.com/nestjs/nest) framework TypeScript starter repository.

## Project setup

```bash
$ yarn install
```

## Compile and run the project

```bash
# development
$ yarn run start

# watch mode
$ yarn run start:dev

# production mode
$ yarn run start:prod
```

## Run tests

```bash
# unit tests
$ yarn run test

# e2e tests
$ yarn run test:e2e

# test coverage
$ yarn run test:cov
```

## Deployment

When you're ready to deploy your NestJS application to production, there are some key steps you can take to ensure it runs as efficiently as possible. Check out the [deployment documentation](https://docs.nestjs.com/deployment) for more information.

If you are looking for a cloud-based platform to deploy your NestJS application, check out [Mau](https://mau.nestjs.com), our official platform for deploying NestJS applications on AWS. Mau makes deployment straightforward and fast, requiring just a few simple steps:

```bash
$ yarn install -g @nestjs/mau
$ mau deploy
```

With Mau, you can deploy your application in just a few clicks, allowing you to focus on building features rather than managing infrastructure.

## Resources

Check out a few resources that may come in handy when working with NestJS:

- Visit the [NestJS Documentation](https://docs.nestjs.com) to learn more about the framework.
- For questions and support, please visit our [Discord channel](https://discord.gg/G7Qnnhy).
- To dive deeper and get more hands-on experience, check out our official video [courses](https://courses.nestjs.com/).
- Deploy your application to AWS with the help of [NestJS Mau](https://mau.nestjs.com) in just a few clicks.
- Visualize your application graph and interact with the NestJS application in real-time using [NestJS Devtools](https://devtools.nestjs.com).
- Need help with your project (part-time to full-time)? Check out our official [enterprise support](https://enterprise.nestjs.com).
- To stay in the loop and get updates, follow us on [X](https://x.com/nestframework) and [LinkedIn](https://linkedin.com/company/nestjs).
- Looking for a job, or have a job to offer? Check out our official [Jobs board](https://jobs.nestjs.com).

## Support

Nest is an MIT-licensed open source project. It can grow thanks to the sponsors and support by the amazing backers. If you'd like to join them, please [read more here](https://docs.nestjs.com/support).

## Stay in touch

- Author - [Kamil Myśliwiec](https://twitter.com/kammysliwiec)
- Website - [https://nestjs.com](https://nestjs.com/)
- Twitter - [@nestframework](https://twitter.com/nestframework)

## License

Nest is [MIT licensed](https://github.com/nestjs/nest/blob/master/LICENSE).
