import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.database.session import SessionLocal, create_tables
from app.scheduler.publications import ScheduledPublicationWorker
from app.services.telegram_publication import build_publication_service


async def run_due_publications() -> None:
    settings = get_settings()
    session = SessionLocal()
    try:
        service = build_publication_service(settings.telegram_bot_token, settings.telegram_channel_id)
        await ScheduledPublicationWorker(service).publish_due(session)
    finally:
        session.close()


async def main() -> None:
    settings = get_settings()
    create_tables()
    scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
    scheduler.add_job(run_due_publications, "interval", minutes=1, id="scheduled-publications")
    scheduler.start()
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
