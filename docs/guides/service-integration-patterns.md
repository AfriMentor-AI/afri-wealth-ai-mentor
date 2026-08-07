# Service-to-Service Integration Patterns

**Card:** D2.5 — Engineering Leadership  
**Author:** Daniel (Lead Software Engineer)  
**Audience:** Olusegun (Platform Spine), Chukwuebuka (Knowledge & Eval)  
**ADR reference:** [ADR-0001 §6 — Communication](../adr/0001-microservices-architecture.md)

This guide is the written companion to the D2.5 pairing sessions. It covers the three
patterns every service author must know: sync REST calls, async event publishing, and
async event consumption — plus the shared error-handling and retry rules.

---

## 1. Rule of thumb: sync vs async

| Use sync REST when… | Use async events when… |
|---|---|
| The caller needs the answer *now* (user is waiting) | You are broadcasting a fact that happened |
| The operation is a command with a result | Multiple services may care (or none yet) |
| Example: chat-orchestration → persona-prompt | Example: goals-milestones → `goal.created` |

Never call another service's database directly. Never call more than **two** downstream
services synchronously in a single request path — fan-out belongs on the event bus.

---

## 2. Sync REST — service-to-service calls

### 2.1 Client setup (httpx, shared pattern)

```python
# services/<your-service>/app/clients/base.py
import httpx
from app.config import settings

# One shared async client per upstream; reuse across requests.
_clients: dict[str, httpx.AsyncClient] = {}

def get_client(base_url: str) -> httpx.AsyncClient:
    if base_url not in _clients:
        _clients[base_url] = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(connect=2.0, read=10.0, write=5.0, pool=2.0),
            headers={"X-Internal-Service": settings.SERVICE_NAME},
        )
    return _clients[base_url]
```

### 2.2 Retry with exponential back-off

Use **tenacity** (already in shared requirements). Retry on 5xx and network errors only;
never retry 4xx (those are caller bugs).

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))

@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
    reraise=True,
)
async def call_persona(user_id: str, archetype: str) -> dict:
    client = get_client(settings.PERSONA_PROMPT_URL)
    r = await client.post("/internal/persona/render", json={"user_id": user_id, "archetype": archetype})
    r.raise_for_status()
    return r.json()
```

### 2.3 Circuit-breaker (optional, Sprint 2)

For the chat hot-path (chat-orchestration → persona-prompt, → rag-corpus) add a
`circuitbreaker` wrapper in Sprint 2 once traffic patterns are known. For now, the
3-attempt retry with back-off is sufficient.

### 2.4 Propagate identity headers

The gateway injects `X-User-Id` and `X-User-Roles`. When service A calls service B,
forward these headers so B can enforce its own authz:

```python
async def call_rag(query: str, request: Request) -> dict:
    headers = {
        "X-User-Id":    request.headers.get("X-User-Id", ""),
        "X-User-Roles": request.headers.get("X-User-Roles", ""),
    }
    r = await get_client(settings.RAG_CORPUS_URL).post(
        "/internal/retrieve", json={"query": query}, headers=headers
    )
    r.raise_for_status()
    return r.json()
```

---

## 3. Async events — publishing

### 3.1 Event envelope (mandatory)

Every event **must** use this envelope (ADR-0001 §6):

```python
# services/<your-service>/app/events/envelope.py
import uuid, datetime
from pydantic import BaseModel
from typing import Any

class Event(BaseModel):
    event:      str           # e.g. "goal.created"
    version:    str = "1"
    id:         str = ""
    occurredAt: str = ""
    actor:      str           # user_id or "system"
    data:       dict[str, Any]

    def model_post_init(self, _):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.occurredAt:
            self.occurredAt = datetime.datetime.utcnow().isoformat() + "Z"
```

### 3.2 Publisher helper

```python
# services/<your-service>/app/events/publisher.py
import json, aio_pika
from app.config import settings
from app.events.envelope import Event

_connection: aio_pika.RobustConnection | None = None
_channel:    aio_pika.Channel | None = None

async def get_channel() -> aio_pika.Channel:
    global _connection, _channel
    if _connection is None or _connection.is_closed:
        _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    if _channel is None or _channel.is_closed:
        _channel = await _connection.channel()
    return _channel

async def publish(event: Event) -> None:
    channel = await get_channel()
    exchange = await channel.declare_exchange(
        "afrimentor.events", aio_pika.ExchangeType.TOPIC, durable=True
    )
    await exchange.publish(
        aio_pika.Message(
            body=event.model_dump_json().encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=event.event,   # e.g. "goal.created"
    )
```

### 3.3 Usage in a service endpoint

```python
# After persisting the goal to the DB:
await publish(Event(
    event="goal.created",
    actor=str(current_user.id),
    data={"goal_id": str(goal.id), "title": goal.title},
))
```

Publish **after** the DB commit, never before. If the publish fails, log and continue —
the write already succeeded; a dead-letter queue (Sprint 2) will handle replay.

---

## 4. Async events — consuming

### 4.1 Consumer helper

```python
# services/<your-service>/app/events/consumer.py
import asyncio, json, logging
import aio_pika
from app.config import settings

log = logging.getLogger(__name__)

async def consume(
    queue_name: str,
    routing_keys: list[str],
    handler,          # async callable(event_dict) -> None
) -> None:
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel    = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    exchange = await channel.declare_exchange(
        "afrimentor.events", aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(queue_name, durable=True)
    for key in routing_keys:
        await queue.bind(exchange, routing_key=key)

    async with queue.iterator() as it:
        async for message in it:
            async with message.process(requeue=False):
                try:
                    payload = json.loads(message.body)
                    await handler(payload)
                except Exception:
                    log.exception("Failed to handle event %s", message.routing_key)
                    # Message is acked (requeue=False) to avoid poison-pill loops.
                    # A DLQ (Sprint 2) will capture it for replay.
```

### 4.2 Wiring into FastAPI lifespan

```python
# services/<your-service>/app/main.py
from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from app.events.consumer import consume
from app.handlers import on_milestone_completed

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(
        consume(
            queue_name="progress.milestone_completed",
            routing_keys=["milestone.completed"],
            handler=on_milestone_completed,
        )
    )
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)
```

### 4.3 Handler pattern

```python
# services/<your-service>/app/handlers.py
async def on_milestone_completed(event: dict) -> None:
    user_id     = event["actor"]
    milestone_id = event["data"]["milestone_id"]
    # ... award XP, update streak, etc.
```

Handlers must be **idempotent** — the same event may arrive more than once (RabbitMQ
at-least-once delivery). Use the `event["id"]` field to deduplicate if needed.

---

## 5. Error handling summary

| Scenario | Action |
|---|---|
| Upstream 4xx on sync call | Raise immediately; do not retry; surface to caller |
| Upstream 5xx on sync call | Retry up to 3× with exponential back-off; raise after exhaustion |
| Network / timeout on sync call | Same as 5xx retry policy |
| Event publish failure | Log `WARNING`; do not fail the HTTP response; Sprint 2 adds DLQ |
| Event handler exception | Log `ERROR`; ack the message (avoid poison pill); Sprint 2 adds DLQ |

---

## 6. Checklist before opening a PR that touches integration

- [ ] Sync calls use the shared `get_client()` with the standard timeout config
- [ ] Retries use tenacity with `_is_retryable` guard (no retry on 4xx)
- [ ] Identity headers (`X-User-Id`, `X-User-Roles`) are forwarded on service→service calls
- [ ] Published events use the `Event` envelope with all required fields
- [ ] Events are published **after** the DB commit
- [ ] Consumer queues are durable; messages are persistent
- [ ] Handlers are idempotent
- [ ] New routing keys are added to the event catalogue in ADR-0001 §6

---

## 7. Where to find examples

| Pattern | Reference implementation |
|---|---|
| Sync REST client | `services/chat-orchestration-service/app/clients/` |
| Event publisher | `services/goals-milestones-service/app/events/` |
| Event consumer | `services/progress-gamification-service/app/events/` |
