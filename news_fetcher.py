import urllib.parse
import requests
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import concurrent.futures

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsFetcher:
    def __init__(self):
        self.base_url = "https://news.google.com/rss/search?q="
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        self.cache = {}
        self.cache_duration = 3600  # 1 hour cache
        self.last_request_time = 0
        self.request_delay = 0.5  # seconds between requests
    
    def _rate_limit(self):
        """Simple rate limiting to avoid being blocked"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.request_delay:
            time.sleep(self.request_delay - time_since_last)
            
        self.last_request_time = time.time()
    
    def get_news_links(self, query, max_results=10):
        """Fetch news articles from Google News RSS feed using BeautifulSoup"""
        # Check cache
        cache_key = f"{query}_{max_results}"
        current_time = time.time()
        
        if cache_key in self.cache:
            cache_time, cache_data = self.cache[cache_key]
            if current_time - cache_time < self.cache_duration:
                logger.info(f"Using cached news for query: {query}")
                return cache_data
        
        self._rate_limit()
        encoded_query = urllib.parse.quote(query)
        rss_url = f"{self.base_url}{encoded_query}&hl=en-US&gl=US&ceid=US:en"
        
        try:
            response = requests.get(rss_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # Try lxml parser first (faster)
            try:
                soup = BeautifulSoup(response.content, 'lxml-xml')
            except:
                # Fall back to xml parser
                soup = BeautifulSoup(response.content, 'xml')
                # If that fails too, use the default parser
                if soup is None:
                    soup = BeautifulSoup(response.content, 'html.parser')
            
            # Get all items from the RSS 
            items = soup.find_all('item', limit=max_results)
            
            news_list = []
            for item in items:
                try:
                    # Extract title and link
                    title = item.find('title').text
                    link = item.find('link').text
                    
                    # Extract source (typically included in the title as "Title - Source")
                    source = "Unknown"
                    title_parts = title.split(' - ')
                    if len(title_parts) > 1:
                        source = title_parts[-1]
                        # Clean title by removing the source part
                        title = ' - '.join(title_parts[:-1])
                    
                    # Extract publication date
                    pub_date = ""
                    if item.find('pubDate'):
                        pub_date = item.find('pubDate').text
                    
                    news_list.append({
                        'title': title,
                        'url': link,
                        'source': source,
                        'timestamp': pub_date
                    })
                    
                except Exception as e:
                    logger.error(f"Error parsing item: {e}")
                    continue
            
            # Cache the results
            self.cache[cache_key] = (current_time, news_list)
            
            return news_list
        
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return []
    
    def get_news_for_multiple_queries(self, queries, max_results_per_query=5):
        """Fetch news for multiple search queries with parallel processing"""
        all_news = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all queries to the thread pool
            future_to_query = {
                executor.submit(self.get_news_links, query, max_results_per_query): query
                for query in queries
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    news = future.result()
                    all_news.extend(news)
                    logger.info(f"Retrieved {len(news)} articles for query: '{query}'")
                except Exception as e:
                    logger.error(f"Error processing query '{query}': {e}")
        
        # Remove duplicates based on URL
        unique_news = []
        seen_urls = set()
        
        for item in all_news:
            if item['url'] not in seen_urls:
                seen_urls.add(item['url'])
                unique_news.append(item)
        
        return unique_news
    
    def save_to_file(self, news_list, filename="news_results.txt"):
        """Save fetched news to a text file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for i, item in enumerate(news_list, 1):
                    f.write(f"{i}. {item['title']}\n")
                    f.write(f"   Source: {item['source']}\n")
                    f.write(f"   Published: {item['timestamp']}\n")
                    f.write(f"   URL: {item['url']}\n\n")
            
            logger.info(f"Results saved to {filename}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving to file: {e}")
            return False