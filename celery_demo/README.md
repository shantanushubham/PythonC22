# Celery demo

A small Celery app that sends an `add` task through Redis and runs it in a worker.

`producer.py` calls `add.delay(22, 33)`. That publishes a message to Redis. The worker in `consumer.py` picks it up, prints the numbers, and returns their sum. The return value is logged by the worker. There is no result backend, so the producer only prints the task id.

## Layout

| File | Role |
| --- | --- |
| `app.py` | Celery app. Broker is `redis://localhost:6379/0`. |
| `consumer.py` | Defines the `add` task. |
| `producer.py` | Enqueues `add(22, 33)`. |
| `docker-compose.yml` | Runs Redis. |

## Setup

Requires Python 3.12+ and Docker.

```bash
uv sync
docker compose up -d
```

## Run

Start the worker in one terminal. On macOS, pass `--pool=solo`. The default prefork pool spawns child processes that crash before the task runs (`ValueError: not enough values to unpack`).

```bash
celery -A consumer worker --loglevel=INFO --pool=solo
```

In a second terminal, send a task:

```bash
python producer.py
```

The worker log should show `Adding 22 and 33` and a success line with the result `55`.

Stop the worker with Ctrl+C. Stop Redis with `docker compose down`.
