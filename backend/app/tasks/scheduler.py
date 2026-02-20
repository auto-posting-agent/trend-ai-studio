from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger


class CrawlScheduler:
    """Background scheduler for crawling tasks."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._is_running = False

    def start(self):
        """Start the scheduler."""
        if not self._is_running:
            self.scheduler.start()
            self._is_running = True

    def stop(self):
        """Stop the scheduler."""
        if self._is_running:
            self.scheduler.shutdown()
            self._is_running = False

    def add_crawl_job(
        self,
        source_id: str,
        crawl_func,
        interval_minutes: int = 5,
    ):
        """Add a new crawling job."""
        self.scheduler.add_job(
            crawl_func,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=f"crawl_{source_id}",
            replace_existing=True,
            kwargs={"source_id": source_id},
        )

    def remove_crawl_job(self, source_id: str):
        """Remove a crawling job."""
        job_id = f"crawl_{source_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

    def get_jobs(self) -> list[dict]:
        """Get all scheduled jobs."""
        return [
            {
                "id": job.id,
                "next_run": str(job.next_run_time),
            }
            for job in self.scheduler.get_jobs()
        ]

    @property
    def is_running(self) -> bool:
        return self._is_running


# Global scheduler instance
scheduler = CrawlScheduler()
