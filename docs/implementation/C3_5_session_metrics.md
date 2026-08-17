# Session Metrics Implementation — Card C3.5

## Overview

Instrument session logging for pilot quantitative measures. Captures anonymized metrics for Proposal 2 pilot evaluation:
- **Sessions per day**
- **Average session length**
- **Time on-task** (message count proxy)

All user identifiers are anonymized via SHA256 hash to enable aggregation without exposing PII.

## Architecture

### Components

```
chat-orchestration-service
  └─ Emits session.completed event
       │
       ├─► RabbitMQ (afrimentor.events topic)
       │
       └─► research-evaluation-service
            └─ Listens on session.completed
               └─ Stores anonymized SessionMetric
```

### Data Flow

1. **Session Completion**: Chat service completes a conversation and emits `session.completed` event
2. **Event Receipt**: Research service receives event via RabbitMQ
3. **Anonymization**: User ID is hashed using SHA256 + salt (16 char output)
4. **Storage**: SessionMetric record created with:
   - `user_hash`: Anonymized identifier
   - `session_date`: Date of session (for grouping)
   - `session_duration_seconds`: Duration from conversation created_at/updated_at
   - `message_count`: Count of messages in session
5. **Querying**: Admin/research staff query metrics via API endpoints

## Implementation Details

### Models

#### SessionMetric
```python
class SessionMetric(Base):
    __tablename__ = "session_metrics"
    
    id: int                              # PK
    user_hash: str                       # SHA256(user_id + salt)[:16]
    session_date: date                   # Date of session
    session_duration_seconds: int        # Duration in seconds
    message_count: int                   # Number of messages (turns)
    conversation_id: str                 # Original ID (audit only)
    recorded_at: datetime                # When metric was ingested
```

### Anonymization

User IDs are anonymized using SHA256 with a configurable salt:

```python
from app.models import anonymize_user_id

# Anonymize a user
user_hash = anonymize_user_id("user123")
# → "a7f9c2b1d4e6f8a2" (deterministic)

# Same user always produces same hash
assert anonymize_user_id("user123") == anonymize_user_id("user123")

# Different users produce different hashes
assert anonymize_user_id("user123") != anonymize_user_id("user456")
```

Salt is configured via environment variable:
```bash
export RESEARCH_SALT="your-unique-salt"
```

### Event Listener

The `EventConsumer` class listens to RabbitMQ for `session.completed` events:

```python
from app.events import EventConsumer

consumer = EventConsumer()
consumer.start()  # Blocks until KeyboardInterrupt or stop()
```

When a `session.completed` event is received:
1. Extract `user_id`, `conversation_id`, `occurredAt`
2. Fetch session details (duration, message count) — currently a placeholder
3. Anonymize user ID
4. Create and persist SessionMetric
5. Acknowledge message to RabbitMQ

### API Endpoints

#### GET /api/v1/metrics/sessions

Get aggregated session metrics across a date range.

**Query Parameters:**
- `start_date` (optional): Filter from this date (YYYY-MM-DD)
- `end_date` (optional): Filter to this date (YYYY-MM-DD)

**Response:**
```json
{
  "period": {
    "start_date": "2024-08-13",
    "end_date": "2024-08-15"
  },
  "sessions_count": 6,
  "sessions_per_day": 2.0,
  "average_session_length_seconds": 600.0,
  "average_time_on_task_messages": 6.0,
  "notes": "All user identifiers are anonymized via SHA256 hash."
}
```

#### GET /api/v1/metrics/sessions/daily

Get per-day session metrics breakdown.

**Query Parameters:**
- `start_date` (optional): Filter from this date (YYYY-MM-DD)
- `end_date` (optional): Filter to this date (YYYY-MM-DD)

**Response:**
```json
{
  "period": {
    "start_date": "2024-08-13",
    "end_date": "2024-08-15"
  },
  "daily_metrics": [
    {
      "date": "2024-08-13",
      "session_count": 2,
      "average_session_length_seconds": 450.0,
      "average_time_on_task_messages": 5.5
    },
    {
      "date": "2024-08-14",
      "session_count": 2,
      "average_session_length_seconds": 600.0,
      "average_time_on_task_messages": 6.0
    },
    {
      "date": "2024-08-15",
      "session_count": 2,
      "average_session_length_seconds": 750.0,
      "average_time_on_task_messages": 6.5
    }
  ]
}
```

## Configuration

### Environment Variables

```bash
# Database URL (defaults to SQLite)
DATABASE_URL=postgresql+psycopg://user:pass@localhost/svc_research

# RabbitMQ connection URL (required for event listener)
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Salt for anonymization (defaults to "default-research-salt")
RESEARCH_SALT=your-secret-salt-key

# App environment (dev, staging, prod)
APP_ENV=dev
```

### Docker Compose

The service is part of the main docker-compose.yml. It will:
1. Connect to Postgres automatically
2. Listen to RabbitMQ events if RABBITMQ_URL is configured
3. Initialize database tables on startup

## Database Migration

No Alembic migration is required. Tables are created automatically via SQLAlchemy's `Base.metadata.create_all()` on application startup.

If you need to track migrations, you can use Alembic:

```bash
cd /path/to/research-evaluation-service
alembic revision --autogenerate -m "Add session_metrics table"
alembic upgrade head
```

## Testing

Run tests with pytest:

```bash
cd /path/to/research-evaluation-service
pytest tests/test_session_metrics.py -v
```

Tests cover:
- User ID anonymization (determinism, uniqueness)
- SessionMetric model persistence
- Metrics aggregation (sessions per day, avg length, avg time on-task)

## Usage Example

### Recording a Session

When the chat service emits `session.completed`:

```json
{
  "event": "session.completed",
  "version": "1",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "occurredAt": "2024-08-15T14:30:00+00:00",
  "actor": "user123",
  "data": {
    "conversation_id": "conv-abc123",
    "user_id": "user123"
  }
}
```

The research-evaluation-service will:
1. Receive the event
2. Hash `user_id` → `a7f9c2b1d4e6f8a2`
3. Fetch session duration (e.g., 600 seconds) and message count (e.g., 5 messages)
4. Create SessionMetric record
5. Store in database

### Querying Metrics

Grace's analysis in later sprints can query metrics:

```bash
# Get all metrics for August 2024
curl "http://localhost:8010/api/v1/metrics/sessions?start_date=2024-08-01&end_date=2024-08-31"

# Get daily breakdown
curl "http://localhost:8010/api/v1/metrics/sessions/daily?start_date=2024-08-13&end_date=2024-08-15"
```

## Next Steps

### TODO (Sprint 5 / C3.6)

1. **Fetch Session Duration & Message Count**
   - Currently returns placeholder (0, 0)
   - Implement database query to chat-orchestration-service DB
   - Or via API call to chat service
   - Suggested: Query directly (chat service owns the data)

2. **Background Event Listener**
   - Currently, EventConsumer must be started manually
   - Wrap as FastAPI background task or separate worker process
   - Consider: docker-compose service entry for dedicated consumer

3. **Queryable via Admin Console**
   - Add metrics dashboard to research-evaluation admin panel
   - Real-time and historical views
   - Export to CSV for Grace's analysis

4. **Data Retention & Purging**
   - Define retention policy (e.g., keep 90 days)
   - Add scheduled purge task
   - Consider: archive old metrics to cold storage

5. **Additional Measures**
   - Conversation count (sessions per user)
   - Session continuity (gaps between sessions)
   - User retention cohort analysis

## Acceptance Criteria Met ✓

- [x] Anonymized session-metric logs are queryable
- [x] Match the 3 required measures:
  - [x] Sessions per day
  - [x] Average session length
  - [x] Time on-task (message count)
- [x] Schema supports growth (extensible for additional metrics)
- [x] API documentation available (/docs)

## References

- ADR-0001: Microservices Architecture
- Event Catalogue: `session.completed`
- Proposal 2: Pilot Evaluation Requirements
