import re
import logging
from typing import Any, List
from bs4 import BeautifulSoup
from datetime import datetime
from vezilka_schemas import Record, RecordMeta, RecordType

logger = logging.getLogger(__name__)


class Parser:
    """Parser class for Femina forum threads."""
    
    def __init__(self):
        pass

    def parse(self, raw_data: List[dict], metadata: Any = None) -> List[Record]:
        """Parse thread raw data into structured Record objects."""
        records = []
        
        for item in raw_data:
            thread_id = item['id']
            url = item['url']
            html = item['html']
            category = item['category']
            
            soup = BeautifulSoup(html, "html.parser")
            
            # Extract title
            title_selectors = ['.p-title-value', 'div.titleBar h1', '.thread-title', 'h1']
            title = "No Title"
            for sel in title_selectors:
                title_node = soup.select_one(sel)
                if title_node:
                    title = title_node.text.strip()
                    break
            
            # Extract main post
            post_selectors = ['.message-body .bbWrapper', '.messageText', '.post-content', '.entry-content']
            post_bodies = []
            for sel in post_selectors:
                post_bodies = soup.select(sel)
                if post_bodies:
                    logger.info("Found %d post bodies with selector %s", len(post_bodies), sel)
                    break
            
            if post_bodies:
                raw_post_html = str(post_bodies[0])
                main_post_content = self._strip_html(raw_post_html)
                
                if not main_post_content:
                    main_post_content = BeautifulSoup(raw_post_html, "html.parser").get_text(separator=" ", strip=True)
                
                # Strict Cyrillic filtering: discard if Latin characters are found
                if self._contains_latin(main_post_content):
                    logger.warning("Discarding record %s: content contains Latin characters.", thread_id)
                    continue

                # Create metadata
                record_meta = RecordMeta(
                    source="https://forum.femina.mk/",
                    url=url,
                    tags=[category],
                    labels=[],
                    scraped_at=datetime.now()
                )
                
                # Create record
                records.append(Record(
                    id=thread_id,
                    text=main_post_content,
                    type=RecordType.NARRATIVE,
                    last_modified_at=datetime.now(),
                    meta=record_meta
                ))
            else:
                logger.warning("Could not find post content for thread %s. HTML snippet: %s", url, html[:500].replace('\n', ' '))
        
        return records

    def _contains_latin(self, text: str) -> bool:
        """Check if the text contains any Latin letters."""
        return bool(re.search(r'[a-zA-Z]', text))

    def _strip_html(self, raw_html: str) -> str:
        """Convert HTML content into plain text by removing tags and normalizing whitespace."""

        if not raw_html:
            return ""

        soup = BeautifulSoup(raw_html, "html.parser")
        
        # Remove unwanted elements like quotes in forum posts
        for quote in soup.select('blockquote'):
            quote.decompose()
            
        text = soup.get_text(separator=" ", strip=True)

        return " ".join(text.split())
