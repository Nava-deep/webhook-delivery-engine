# Webhook Delivery Engine

Reliable outbound webhook delivery with signed payloads, retries, dead-letter handling, and manual replay.

## 60-Second Overview

This project is a Django REST backend that lets an application publish events and deliver them to subscribed webhook endpoints.

Example events:

- `order.created`
- `payment.succeeded`
- `user.signup`
- `invoice.failed`

When an event is published, the API creates delivery records for every active endpoint subscribed to that event type. A simple polling worker sends signed HTTP POST requests to those endpoints. If an endpoint fails, the worker retries with backoff. If it keeps failing, the delivery moves to `dead_lettered` so it can be inspected and manually replayed.

This is intentionally a clean backend/SDE project, not a heavy infrastructure project.

## Why Webhook Delivery Is Useful

Many products need to notify external systems when something happens:

- Payment platforms notify merchants after a payment succeeds.
- Order systems notify partner warehouses after an order is created.
- SaaS apps send integration events to customer systems.
- GitHub-style products notify subscribers when repository events happen.

The hard part is not just sending an HTTP request. The useful backend work is tracking delivery state, signing payloads, retrying failures, avoiding duplicate event creation, and giving operators a way to recover failed deliveries.

## Core Features

- Register webhook endpoints with URL, event types, secret, and active status
- Publish events through a REST API
- Create one delivery record per matching subscribed endpoint
- Idempotency keys for event publishing
- HMAC-SHA256 signed outbound webhook payloads
- Required webhook headers:
  - `X-Webhook-Event-Id`
  - `X-Webhook-Delivery-Id`
  - `X-Webhook-Timestamp`
  - `X-Webhook-Signature`
- Delivery states:
  - `pending`
  - `delivering`
  - `delivered`
  - `failed`
  - `dead_lettered`
- Simple polling worker using a Django management command
- Retry scheduling with exponential backoff
- Max retry limit and dead-letter handling
- Manual replay for `failed` and `dead_lettered` deliveries
- Delivery list and detail APIs for debugging
- Stats API
- Mock receiver with `success`, `fail`, `flaky`, and `timeout` modes
- Docker Compose setup
- pytest test suite
- Self-checking local demo scripts

## Architecture

```text
Producer
  |
  v
Django REST API
  |
  v
PostgreSQL
  |
  v
Delivery Worker
  |
  v
Subscriber Webhook Endpoint / Mock Receiver
```

The project runs as a Django monolith plus one worker process. PostgreSQL stores events, endpoints, delivery state, retry timing, and failure information.

## Request Flow

1. Register a webhook endpoint with a URL, event types, and secret.
2. Publish an event such as `order.created`.
3. The API finds active endpoints subscribed to that event type.
4. The API creates delivery rows in PostgreSQL.
5. The worker polls for due deliveries.
6. The worker sends a signed webhook payload to the subscriber.
7. A 2xx response marks the delivery `delivered`.
8. A timeout, network error, or non-2xx response marks it `failed` and schedules a retry.
9. Repeated failures move it to `dead_lettered`.
10. A failed or dead-lettered delivery can be manually replayed.

## Key Reliability Ideas

**What problem does retry solve?**

Subscriber endpoints can be temporarily down, slow, or returning errors. Retry gives those endpoints time to recover instead of losing the event after one failed request.

**What is dead-letter handling?**

Dead-letter handling means the system stops retrying a repeatedly failing delivery and marks it as `dead_lettered`. This keeps the failure visible for debugging instead of retrying forever.

**What is manual replay?**

Manual replay lets an operator reset a failed or dead-lettered delivery back to `pending` after the receiver has been fixed. The original event is reused; no duplicate event is created.

**Why use HMAC signatures?**

HMAC signatures let subscribers verify that the webhook came from this system and that the payload was not changed in transit.

**Why use idempotency keys?**

If a producer retries the same publish request, an idempotency key lets the API return the existing event instead of creating duplicate event records and duplicate deliveries.

**What does at-least-once delivery mean?**

The system tries to deliver each webhook until it succeeds or reaches the retry limit. A subscriber may receive the same delivery more than once, so subscriber endpoints should handle duplicates safely.

## Self-checking Local Demo

Quick start:

```bash
docker compose up --build
```

In another terminal, run one of the self-checking demos:

```bash
make demo-success
make demo-failure-replay
make demo-flaky
```

Reset demo-created rows:

```bash
make reset
```

Stop services while keeping the local database volume:

```bash
make down
```

Stop services and remove the database volume:

```bash
make down-volumes
```

### Demo Scripts

`scripts/demo_success.sh`

- Registers the mock receiver endpoint.
- Sets the mock receiver to `success`.
- Publishes an event.
- Runs a worker cycle.
- Prints deliveries.
- Checks that the delivery became `delivered`.

`scripts/demo_failure_replay.sh`

- Registers the mock receiver endpoint.
- Sets the mock receiver to `fail`.
- Publishes an event.
- Forces worker attempts with `--ignore-schedule` so the demo reaches `dead_lettered` quickly.
- Sets the receiver back to `success`.
- Replays the delivery.
- Checks that the delivery becomes `delivered`.

`scripts/demo_flaky.sh`

- Sets the mock receiver to `flaky`.
- Publishes an event.
- Shows early failed attempts.
- Shows the later successful attempt.

`scripts/reset_demo.sh`

- Local-development only.
- Deletes rows created by the demo scripts.

`scripts/stop_demo.sh`

- Runs `docker compose down`.
- Removes volumes only when called with `--volumes`.

## Make Commands

```bash
make up
make down
make test
make demo-success
make demo-failure-replay
make demo-flaky
make reset
```

## API Examples

Register an endpoint:

```bash
curl -X POST http://localhost:8000/api/endpoints/ \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://mock-receiver:9000/webhook",
    "description": "Test receiver",
    "event_types": ["order.created", "payment.succeeded"]
  }'
```

Publish an event:

```bash
curl -X POST http://localhost:8000/api/events/ \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "order.created",
    "payload": {
      "order_id": "ord_123",
      "amount": 1999,
      "currency": "INR"
    },
    "idempotency_key": "order-created-ord-123"
  }'
```

List deliveries:

```bash
curl http://localhost:8000/api/deliveries/
```

Filter deliveries:

```bash
curl "http://localhost:8000/api/deliveries/?status=failed"
curl "http://localhost:8000/api/deliveries/?event_type=order.created"
curl "http://localhost:8000/api/deliveries/?endpoint_id=<endpoint_id>"
```

View delivery detail:

```bash
curl http://localhost:8000/api/deliveries/<delivery_id>/
```

Replay a failed delivery:

```bash
curl -X POST http://localhost:8000/api/deliveries/<delivery_id>/replay/
```

View stats:

```bash
curl http://localhost:8000/api/stats/
```

Change mock receiver mode:

```bash
curl -X POST http://localhost:9000/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "fail"}'
```

Supported mock receiver modes are `success`, `fail`, `flaky`, and `timeout`.

## How To Run

```bash
docker compose up --build
```

API:

```text
http://localhost:8000
```

Mock receiver:

```text
http://localhost:9000
```

## How To Test

With Docker:

```bash
docker compose exec api pytest
```

With a local virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest
```

## What Reviewers Should Notice

This project is meant to show practical backend engineering, not just basic CRUD endpoints. The main value is in how it handles real delivery failure cases: every webhook attempt is stored, signed, retried, inspected, and recoverable.

The codebase demonstrates:

- REST API design with Django REST Framework
- Data modeling for events, webhook endpoints, and delivery attempts
- Database-backed background processing with a simple polling worker
- Retry scheduling, max-attempt handling, and dead-letter state
- Idempotent event publishing to avoid duplicate delivery creation
- HMAC-SHA256 webhook signing for subscriber verification
- Operational debugging through delivery list/detail APIs and stats
- Local demo tooling with Docker Compose and a configurable mock receiver
- Behavior-focused tests using pytest and pytest-django

## Known Limitations

- The worker uses simple database polling, not Celery or a dedicated queue system.
- Delivery is at-least-once, not exactly-once, so subscriber endpoints should handle duplicate deliveries safely.
- There is no authentication system; this project focuses only on webhook delivery behavior.
- A production version would need recovery for deliveries stuck in delivering state after a worker crash.
- A production version would also need stronger endpoint security, tenant isolation, monitoring, and rate controls.
