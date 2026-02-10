import logging
import asyncio
from typing import Any, List, Optional, Dict
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from config.scraper_settings import settings

logger = logging.getLogger(__name__)


class Fetcher:
    """Fetcher class for Femina forum using aiohttp."""

    def __init__(self):
        self.base_url = settings.site_url
        self.headers = settings.headers

    async def fetch_metadata(self) -> Optional[List[Dict[str, str]]]:
        """Fetch forum category URLs."""
        logger.info("Fetching forum categories from %s...", self.base_url)
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(self.base_url) as response:
                if response.status != 200:
                    logger.error("Failed to fetch main page: %s", response.status)
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                
                categories = []
                # Try multiple possible selectors for forum links
                selectors = ['.nodeTitle a', '.node-title a', '.forum-title a']
                
                for selector in selectors:
                    for link in soup.select(selector):
                        url = urljoin(self.base_url, link.get('href'))
                        name = link.text.strip()
                        # Avoid duplicate URLs and non-forum links
                        if '/forums/' in url and not any(c['url'] == url for c in categories):
                            categories.append({"name": name, "url": url})
                
                if not categories:
                    logger.info("No categories found with selectors, trying fallback...")
                    # Fallback: look for any link containing /forums/
                    for link in soup.find_all('a', href=True):
                        href = link.get('href')
                        if '/forums/' in href:
                            url = urljoin(self.base_url, href)
                            name = link.text.strip() or url.split('/')[-2]
                            if not any(c['url'] == url for c in categories):
                                categories.append({"name": name, "url": url})

                logger.info("Found %d categories", len(categories))
                return categories

    async def fetch_data(self, seen_ids: set, metadata: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Fetch thread HTML contents from all categories."""
        if not metadata:
            return []

        all_raw_data = []
        async with aiohttp.ClientSession(headers=self.headers) as session:
            for category in metadata:
                # Skip "Kanta" if it's the only one found and potentially empty
                if "Канта" in category['name']:
                    continue
                    
                logger.info("Processing category: %s (%s)", category['name'], category['url'])
                threads_in_cat = await self._fetch_threads_from_category(session, category, seen_ids)
                all_raw_data.extend(threads_in_cat)

        return all_raw_data

    async def _fetch_threads_from_category(self, session, category, seen_ids) -> List[Dict[str, Any]]:
        """Paginate through category and fetch thread links."""
        category_url = category['url']
        threads_data = []
        page = 1
        
        while True:
            url = f"{category_url}page-{page}" if page > 1 else category_url
            logger.info("Fetching thread list from: %s", url)
            
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error("Failed to fetch category page %s: %s", url, response.status)
                    break
                
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                
                # Try multiple selectors for thread titles
                thread_selectors = ['.structItem-title a', '.discussionListItem .title a', '.thread-title a', '.title a']
                
                thread_links = []
                for sel in thread_selectors:
                    thread_links = soup.select(sel)
                    if thread_links:
                        logger.info("Found %d links with selector %s", len(thread_links), sel)
                        break
                
                if not thread_links:
                    logger.warning("No thread links found in %s. HTML snippet: %s", url, html[:500].replace('\n', ' '))
                    break
                
                new_threads_per_page = 0
                for i, link in enumerate(thread_links):
                    href = link.get('href')
                    if i < 5:
                        logger.info("Found link href: %s", href)
                        
                    if not href or 'threads/' not in href:
                        continue
                        
                    thread_url = urljoin(self.base_url, href)
                    # Extract ID from URL
                    parts = href.strip('/').split('.')
                    thread_id = parts[-1] if len(parts) > 1 else href.strip('/').split('/')[-1]
                    
                    if thread_id in seen_ids:
                        continue
                    
                    # Fetch thread content
                    logger.info("Fetching thread content: %s", thread_url)
                    async with session.get(thread_url) as thread_resp:
                        if thread_resp.status == 200:
                            thread_html = await thread_resp.text()
                            threads_data.append({
                                "id": thread_id,
                                "url": thread_url,
                                "html": thread_html,
                                "category": category['name']
                            })
                            new_threads_per_page += 1
                    
                    # Respect rate limits
                    await asyncio.sleep(1 / settings.requests_per_second)
                    
                if new_threads_per_page == 0:
                    break
                page += 1
                
        return threads_data
