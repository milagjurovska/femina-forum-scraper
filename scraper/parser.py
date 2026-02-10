import logging
from typing import Any, List, Dict
from bs4 import BeautifulSoup
from datetime import datetime

from .models import Record

logger = logging.getLogger(__name__)


class Parser:
    """Parser class for Femina forum threads."""
    
    def __init__(self):
        pass

    def parse(self, raw_data: List[Dict[str, Any]], metadata: Any = None) -> List[Record]:
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
            # XF2: .message-body .bbWrapper
            # XF1: .messageText 
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
                    # If stripping results in empty, maybe it's just one big blockquote or something else
                    main_post_content = BeautifulSoup(raw_post_html, "html.parser").get_text(separator=" ", strip=True)
                
                # Extract date
                # XF2: time.u-dt
                # XF1: .DateTime or [data-datestring]
                time_node = soup.select_one('time.u-dt') or soup.select_one('.DateTime') or soup.select_one('[data-datestring]')
                published_at = None
                if time_node:
                    published_at = time_node.get('datetime') or time_node.get('data-time') or time_node.text.strip()
                
                records.append(Record(
                    id=thread_id,
                    title=title,
                    site_url="https://forum.femina.mk/",
                    page_url=url,
                    content=main_post_content,
                    published_at=published_at,
                    categories=[category]
                ))
            else:
                logger.warning("Could not find post content for thread %s. HTML snippet: %s", url, html[:500].replace('\n', ' '))
        
        return records

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
