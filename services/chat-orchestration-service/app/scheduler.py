import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

def setup_scheduler(app):
    @app.on_event("startup")
    async def startup_event():
        logger.info("Starting scheduler...")
        scheduler.start()

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
