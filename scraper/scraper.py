import logging

from .fetcher import Fetcher
from .parser import Parser
from store import StoreFactory

logger = logging.getLogger(__name__)


class Scraper:
    """Template class for orchestrating the scraping workflow for a single website"""

    def __init__(self, site_url: str, site_name: str):
        self.site_url = site_url
        self.site_name = site_name

        self._fetcher = Fetcher()
        self._parser = Parser()
        self._store = StoreFactory.create(self.site_name)

    async def run(self):
        """Execute the full scraping pipeline."""

        logger.info("=" * 80)
        logger.info("Starting scraper for %s", self.site_url)
        logger.info("=" * 80)

        logger.info("Loading previously seen IDs...")
        seen_ids = self._store.load_seen_ids()

        logger.info("Fetching metadata...")
        metadata = await self._fetcher.fetch_metadata()
        
        logger.info("Fetching data and saving incrementally...")
        async for chunk in self._fetcher.fetch_data(seen_ids=seen_ids, metadata=metadata):
            logger.info("Parsing chunk of %d threads...", len(chunk))
            parsed_records = self._parser.parse(chunk, metadata=metadata)
            
            if parsed_records:
                logger.info("Saving %d new records...", len(parsed_records))
                self._store.save_records(parsed_records)
                # Update seen_ids in case scraper restarts
                for record in parsed_records:
                    seen_ids.add(record.id)
            else:
                logger.info("No new records in this chunk")
        
        logger.info("=" * 80)
        logger.info("Scraping completed for %s", self.site_url)
        logger.info("=" * 80)
