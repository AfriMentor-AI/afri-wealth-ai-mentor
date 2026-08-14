import logging
from .database import SessionLocal
from .models import Conversation, DailyAction
from .llm import generate_daily_action_for_user
from .schemas import DailyActionCreate

logger = logging.getLogger(__name__)

async def generate_daily_actions_job():
    """
    Job to generate daily actions for all users.
    """
    logger.info("Starting daily action generation job...")
    db = SessionLocal()
    try:
        users = db.query(Conversation.user_id).distinct().all()
        user_ids = [user[0] for user in users]
        logger.info(f"Found {len(user_ids)} users to generate actions for.")

        for user_id in user_ids:
            logger.info(f"Generating daily action for user {user_id}...")
            action_text = await generate_daily_action_for_user(user_id, db)
            
            daily_action = DailyActionCreate(user_id=user_id, action_text=action_text)
            db_daily_action = DailyAction(**daily_action.dict())
            db.add(db_daily_action)
            db.commit()
            db.refresh(db_daily_action)
            logger.info(f"Saved daily action for user {user_id}: {action_text}")

    finally:
        db.close()
    logger.info("Daily action generation job finished.")

