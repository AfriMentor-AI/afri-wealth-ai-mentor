import logging

import httpx

from .config import get_settings
from .database import SessionLocal
from .llm import generate_daily_action_for_user
from .models import Conversation, DailyAction
from .schemas import DailyActionCreate

logger = logging.getLogger(__name__)

async def generate_daily_actions_job():
    logger.info("Starting daily action generation job...")
    settings = get_settings()
    db = SessionLocal()
    try:
        users = db.query(Conversation.user_id).distinct().all()
        user_ids = [user[0] for user in users]
        logger.info(f"Found {len(user_ids)} users to generate actions for.")

        for user_id in user_ids:
            action_text = await generate_daily_action_for_user(user_id, db)

            daily_action = DailyActionCreate(user_id=user_id, action_text=action_text)
            db_daily_action = DailyAction(**daily_action.dict())
            db.add(db_daily_action)
            db.commit()
            db.refresh(db_daily_action)
            logger.info(f"Saved daily action for user {user_id}: {action_text}")

            if settings.notification_service_url:
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        url = (
                            f"{settings.notification_service_url}"
                            "/api/v1/notifications/trigger/daily-action-reminder"
                        )
                        await client.post(
                            url,
                            json={"user_id": user_id, "action_title": action_text[:80]},
                        )
                except Exception:
                    logger.warning(
                        "Could not notify user %s — notification-service unreachable",
                        user_id,
                    )

    finally:
        db.close()
    logger.info("Daily action generation job finished.")
