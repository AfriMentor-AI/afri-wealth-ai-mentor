"""Tests for session metrics (card C3.5).

Tests the session metric recording and query functionality for anonymized
logging of pilot quantitative measures.
"""
from datetime import datetime, date, timedelta
import pytest
from sqlalchemy.orm import Session

from app.models import SessionMetric, anonymize_user_id
from app.db.session import SessionLocal, engine, Base


@pytest.fixture
def db():
    """Create a fresh test database session."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    yield db
    
    # Clean up
    db.close()
    Base.metadata.drop_all(bind=engine)


class TestAnonymizeUserId:
    """Tests for user ID anonymization."""
    
    def test_same_user_same_hash(self):
        """Same user ID with same salt should produce same hash."""
        user_id = "user123"
        salt = "test-salt"
        
        hash1 = anonymize_user_id(user_id, salt)
        hash2 = anonymize_user_id(user_id, salt)
        
        assert hash1 == hash2
        assert len(hash1) == 16
    
    def test_different_users_different_hashes(self):
        """Different user IDs should produce different hashes."""
        salt = "test-salt"
        
        hash1 = anonymize_user_id("user123", salt)
        hash2 = anonymize_user_id("user456", salt)
        
        assert hash1 != hash2
    
    def test_hash_is_deterministic(self):
        """Hash should be the same across multiple calls without explicit salt."""
        user_id = "user789"
        
        # Call multiple times (will use default salt from config)
        hash1 = anonymize_user_id(user_id)
        hash2 = anonymize_user_id(user_id)
        
        assert hash1 == hash2
    
    def test_hash_is_16_chars(self):
        """Hash should always be 16 characters."""
        hashes = [
            anonymize_user_id("short"),
            anonymize_user_id("a" * 100),
            anonymize_user_id("user@example.com"),
        ]
        
        for h in hashes:
            assert len(h) == 16


class TestSessionMetricModel:
    """Tests for SessionMetric ORM model."""
    
    def test_create_session_metric(self, db: Session):
        """Can create and persist a session metric."""
        metric = SessionMetric(
            user_hash="abc123def456",
            session_date=date(2024, 8, 15),
            session_duration_seconds=300,
            message_count=5,
            conversation_id="conv-001",
        )
        
        db.add(metric)
        db.commit()
        
        # Verify it was saved
        saved = db.query(SessionMetric).filter_by(conversation_id="conv-001").first()
        assert saved is not None
        assert saved.user_hash == "abc123def456"
        assert saved.session_duration_seconds == 300
        assert saved.message_count == 5
    
    def test_session_metric_has_recorded_at(self, db: Session):
        """SessionMetric should have recorded_at timestamp."""
        metric = SessionMetric(
            user_hash="abc123def456",
            session_date=date(2024, 8, 15),
            session_duration_seconds=300,
            message_count=5,
            conversation_id="conv-001",
        )
        
        db.add(metric)
        db.commit()
        
        saved = db.query(SessionMetric).filter_by(conversation_id="conv-001").first()
        assert saved.recorded_at is not None
        # Should be approximately now
        from datetime import timezone as tz
        now = datetime.now(tz.utc)
        rec = saved.recorded_at.replace(tzinfo=tz.utc) if saved.recorded_at.tzinfo is None else saved.recorded_at
        assert abs((now - rec).total_seconds()) < 10
    
    def test_multiple_sessions_same_user_same_day(self, db: Session):
        """Can record multiple sessions from same user on same day."""
        user_hash = anonymize_user_id("user123", "salt")
        session_date = date(2024, 8, 15)
        
        # Create 3 sessions
        for i in range(3):
            metric = SessionMetric(
                user_hash=user_hash,
                session_date=session_date,
                session_duration_seconds=300 + i * 60,
                message_count=5 + i,
                conversation_id=f"conv-{i:03d}",
            )
            db.add(metric)
        
        db.commit()
        
        # Query all sessions for this user on this day
        sessions = db.query(SessionMetric).filter(
            SessionMetric.user_hash == user_hash,
            SessionMetric.session_date == session_date,
        ).all()
        
        assert len(sessions) == 3
        assert sessions[0].session_duration_seconds == 300
        assert sessions[1].session_duration_seconds == 360
        assert sessions[2].session_duration_seconds == 420


class TestSessionMetricsAggregation:
    """Tests for aggregating session metrics."""
    
    def test_calculate_sessions_per_day(self, db: Session):
        """Can calculate sessions per day from metrics."""
        user_hash = anonymize_user_id("user123", "salt")
        
        # Create 6 sessions across 3 days
        days = [date(2024, 8, 13), date(2024, 8, 14), date(2024, 8, 15)]
        for day in days:
            for i in range(2):
                metric = SessionMetric(
                    user_hash=user_hash,
                    session_date=day,
                    session_duration_seconds=300,
                    message_count=5,
                    conversation_id=f"conv-{day.isoformat()}-{i}",
                )
                db.add(metric)
        
        db.commit()
        
        # Get all metrics
        metrics = db.query(SessionMetric).filter(
            SessionMetric.user_hash == user_hash
        ).all()
        
        # Calculate
        total_sessions = len(metrics)
        unique_days = len(set(m.session_date for m in metrics))
        sessions_per_day = total_sessions / unique_days
        
        assert total_sessions == 6
        assert unique_days == 3
        assert sessions_per_day == 2.0
    
    def test_calculate_average_session_length(self, db: Session):
        """Can calculate average session length."""
        user_hash = anonymize_user_id("user123", "salt")
        
        # Create sessions with different durations
        durations = [300, 600, 900]  # 5, 10, 15 minutes
        for i, duration in enumerate(durations):
            metric = SessionMetric(
                user_hash=user_hash,
                session_date=date(2024, 8, 15),
                session_duration_seconds=duration,
                message_count=5,
                conversation_id=f"conv-{i}",
            )
            db.add(metric)
        
        db.commit()
        
        # Calculate
        metrics = db.query(SessionMetric).filter(
            SessionMetric.user_hash == user_hash
        ).all()
        
        total_duration = sum(m.session_duration_seconds for m in metrics)
        avg_length = total_duration / len(metrics)
        
        assert avg_length == 600.0
    
    def test_calculate_average_time_on_task(self, db: Session):
        """Can calculate average time on-task (message count)."""
        user_hash = anonymize_user_id("user123", "salt")
        
        # Create sessions with different message counts
        message_counts = [3, 5, 7, 9]
        for i, count in enumerate(message_counts):
            metric = SessionMetric(
                user_hash=user_hash,
                session_date=date(2024, 8, 15),
                session_duration_seconds=300,
                message_count=count,
                conversation_id=f"conv-{i}",
            )
            db.add(metric)
        
        db.commit()
        
        # Calculate
        metrics = db.query(SessionMetric).filter(
            SessionMetric.user_hash == user_hash
        ).all()
        
        total_messages = sum(m.message_count for m in metrics)
        avg_messages = total_messages / len(metrics)
        
        assert avg_messages == 6.0


class TestSessionMetricsEndpoint:
    """Tests for the session metrics API endpoints."""
    
    def test_endpoint_exists(self):
        """Session metrics endpoints should be defined."""
        # This is a basic check that the endpoints are registered
        # Full integration tests would use TestClient
        try:
            from app.main import app
            # Check that app has the new endpoints
            routes = [route.path for route in app.routes]
            assert "/api/v1/metrics/sessions" in routes
            assert "/api/v1/metrics/sessions/daily" in routes
        except ImportError:
            pytest.skip("Cannot import app - dependencies may not be installed")
