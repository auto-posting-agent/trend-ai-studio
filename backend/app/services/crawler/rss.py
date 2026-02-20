from typing import List
from app.services.crawler.base import BaseCrawler
from app.schemas.source import CrawledContent


class RSSCrawler(BaseCrawler):
    """RSS feed crawler."""

    async def crawl(self, url: str, config: dict | None = None) -> List[CrawledContent]:
        """Crawl RSS feed and return list of crawled content."""
        # TODO: Implement RSS parsing with feedparser
        return []

    async def validate_source(self, url: str) -> bool:
        """Validate if the RSS feed URL is accessible."""
        # TODO: Implement validation
        return True
