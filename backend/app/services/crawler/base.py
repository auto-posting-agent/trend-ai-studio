from abc import ABC, abstractmethod
from typing import List
from app.schemas.source import CrawledContent


class BaseCrawler(ABC):
    """Base class for all crawlers."""

    @abstractmethod
    async def crawl(self, url: str, config: dict | None = None) -> List[CrawledContent]:
        """Crawl the given URL and return list of crawled content."""
        pass

    @abstractmethod
    async def validate_source(self, url: str) -> bool:
        """Validate if the source URL is accessible and valid."""
        pass
