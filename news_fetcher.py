"""
Enhanced News fetcher for News Analyzer - focuses on finding easily scrapable content sources
"""
import logging
import re
import time
import random
import requests
from datetime import datetime
from urllib.parse import quote_plus, urlparse

# Configure logging
logger = logging.getLogger(__name__)

class NewsFetcher:
    """Fetches news links from various sources with focus on non-JS content"""
    
    def __init__(self, use_google=True):
        """Initialize the news fetcher with optimized defaults"""
        self.use_google = use_google
        self.timeout = 8  # Reduced timeout
        
        # Common headers to simulate a real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        # Google News base URL
        self.google_news_url = "https://news.google.com/search?q="
        
        # Bing News base URL (added as alternative)
        self.bing_news_url = "https://www.bing.com/news/search?q="
        
        # Define easily scrapable domains (known to work well with BeautifulSoup)
        self.preferred_domains = [
            'reuters.com',
            'apnews.com',
            'bbc.com',
            'npr.org',
            'theguardian.com',
            'aljazeera.com',
            'cnbc.com',
            'usatoday.com',
            'cnn.com',
            'foxnews.com',
            'abc.net.au',
            'news.yahoo.com',
            'euronews.com',
            'hindustantimes.com',
            'ndtv.com',
            'timesofindia.indiatimes.com',
            'thehindu.com'
        ]
        
        # Define domains that are difficult to scrape (JS-heavy or paywalled)
        self.difficult_domains = [
            'nytimes.com',
            'wsj.com',
            'ft.com',
            'bloomberg.com',
            'washingtonpost.com',
            'economist.com',
            'newyorker.com',
            'businessinsider.com',
            'medium.com',
            'techcrunch.com'
        ]
    
    def is_preferred_domain(self, url):
        """Check if URL belongs to a preferred (easily scrapable) domain"""
        domain = urlparse(url).netloc.lower()
        return any(preferred in domain for preferred in self.preferred_domains)
    
    def is_difficult_domain(self, url):
        """Check if URL belongs to a difficult to scrape domain"""
        domain = urlparse(url).netloc.lower()
        return any(difficult in domain for difficult in self.difficult_domains)
    
    def get_news_links(self, query, max_articles=5, max_attempts=3, min_preferred=3):
        """
        Get news links for a query, prioritizing non-JS sites
        
        Parameters:
        - query: Search query
        - max_articles: Maximum number of articles to return
        - max_attempts: Maximum number of search attempts to make
        - min_preferred: Minimum number of preferred domain articles to find
        
        Returns:
        - list: List of article dictionaries
        """
        all_articles = []
        preferred_count = 0
        attempts = 0
        
        while attempts < max_attempts and (len(all_articles) < max_articles or preferred_count < min_preferred):
            try:
                # Try different sources with each attempt
                if attempts == 0:
                    # First try Google News
                    new_articles = self._get_google_news(query, max_articles * 2)
                elif attempts == 1:
                    # Then try Bing News
                    new_articles = self._get_bing_news(query, max_articles * 2)
                else:
                    # On last attempt, try with a more specific query
                    specific_query = f"{query} latest news"
                    new_articles = self._get_google_news(specific_query, max_articles * 3)
                
                # Count new unique articles
                if new_articles:
                    # Filter out duplicates
                    existing_urls = {article['url'] for article in all_articles}
                    unique_articles = [a for a in new_articles if a['url'] not in existing_urls]
                    
                    # Count preferred domains
                    for article in unique_articles:
                        if self.is_preferred_domain(article['url']):
                            preferred_count += 1
                            # Prioritize preferred articles by adding them first
                            all_articles.insert(0, article)
                        elif not self.is_difficult_domain(article['url']):
                            # Add non-difficult domains next
                            all_articles.append(article)
                        else:
                            # Add difficult domains only if we need more articles
                            if len(all_articles) < max_articles:
                                all_articles.append(article)
                
                # Debug info
                logger.info(f"Attempt {attempts+1}: Found {len(new_articles)} articles, "
                           f"{preferred_count} preferred domains out of {len(all_articles)} total")
            except Exception as e:
                logger.error(f"Search attempt {attempts+1} failed: {e}")
            
            # Increment attempt counter
            attempts += 1
        
        # If we still don't have enough articles, generate some samples
        if not all_articles or len(all_articles) < max_articles // 2:
            logger.warning(f"Failed to get enough real news for {query}, using fallback")
            fallback_articles = self._generate_sample_news(query, max_articles)
            all_articles.extend(fallback_articles)
        
        # Sort final set: preferred domains first, then by timestamp
        sorted_articles = sorted(all_articles, 
                               key=lambda x: (not self.is_preferred_domain(x['url']), 
                                              x.get('timestamp', '2000-01-01')))
        
        return sorted_articles[:max_articles]
    
    def _clean_link(self, link):
        """Clean Google News link to get the actual article URL"""
        if not link:
            return None
            
        # Handle Google News links
        if './articles/' in link:
            link = link.replace('./articles/', 'https://news.google.com/articles/')
        elif link.startswith('./'):
            link = 'https://news.google.com' + link[1:]
            
        # Follow Google redirect to get the actual news URL
        if 'news.google.com/articles' in link:
            try:
                response = requests.head(link, headers=self.headers, allow_redirects=True, timeout=5)
                if response.url and 'news.google.com' not in response.url:
                    # Verify the URL is properly formed
                    if not response.url.startswith(('http://', 'https://')):
                        return None
                    return response.url
            except:
                pass
                
        return link
    
    def _get_google_news(self, query, max_articles=10):
        """
        Get news from Google News
        
        Parameters:
        - query: Search query
        - max_articles: Maximum number of articles to return
        
        Returns:
        - list: List of article dictionaries
        """
        try:
            # Optimize search query to get more relevant results
            search_query = f"{query} when:7d"  # last 7 days
            
            # Add preferred domains to query to boost them
            preferred_domains_str = " OR ".join([f"site:{domain}" for domain in self.preferred_domains[:5]])
            if preferred_domains_str:
                search_query = f"({search_query}) ({preferred_domains_str})"
            
            # Encode the search query for URL
            encoded_query = quote_plus(search_query)
            
            # Make the request to Google News
            url = f"{self.google_news_url}{encoded_query}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch news from Google: {response.status_code}")
                return []
            
            # Extract article data
            articles = []
            
            # Use regex for faster parsing (much faster than BeautifulSoup for this case)
            
            # Find article sections
            article_sections = re.findall(r'<article[^>]*>(.*?)</article>', response.text, re.DOTALL)
            
            for section in article_sections[:max_articles * 2]:  # Get more than needed in case some fail
                try:
                    # Extract title
                    title_match = re.search(r'<h3[^>]*><a[^>]*>(.*?)</a>', section, re.DOTALL)
                    if not title_match:
                        continue
                    title = title_match.group(1).strip()
                    title = re.sub(r'<[^>]*>', '', title)  # Remove any HTML tags
                    
                    # Extract URL
                    url_match = re.search(r'<a[^>]*href="([^"]*)"', section)
                    if not url_match:
                        continue
                    url = self._clean_link(url_match.group(1))
                    
                    # Skip if URL cleaning failed
                    if not url or not url.startswith(('http://', 'https://')):
                        continue
                    
                    # Extract source
                    source_match = re.search(r'<div[^>]*data-n-tid="9"[^>]*>(.*?)</div>', section, re.DOTALL)
                    source = "Google News"
                    if source_match:
                        source = re.sub(r'<[^>]*>', '', source_match.group(1)).strip()
                    
                    # Extract timestamp
                    time_match = re.search(r'<time[^>]*>(.*?)</time>', section, re.DOTALL)
                    timestamp = datetime.now().strftime("%Y-%m-%d")
                    if time_match:
                        timestamp_text = time_match.group(1).strip()
                        # Convert relative time to absolute (approximate)
                        if "hour" in timestamp_text or "min" in timestamp_text:
                            timestamp = datetime.now().strftime("%Y-%m-%d")
                        elif "day" in timestamp_text:
                            days = 1
                            if timestamp_text[0].isdigit():
                                days = int(timestamp_text[0])
                            # Calculate days ago
                            from datetime import datetime, timedelta
                            timestamp = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                    
                    if url and title and len(title) > 10:
                        articles.append({
                            'title': title,
                            'url': url,
                            'source': source,
                            'timestamp': timestamp,
                            'article_id': f"gn_{hash(url) % 100000}",
                            'is_preferred': self.is_preferred_domain(url)
                        })
                        
                        if len(articles) >= max_articles:
                            break
                except Exception as e:
                    logger.error(f"Error parsing Google News article: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"Error fetching Google News: {e}")
            return []
    
    def _get_bing_news(self, query, max_articles=10):
        """
        Get news from Bing News
        
        Parameters:
        - query: Search query
        - max_articles: Maximum number of articles to return
        
        Returns:
        - list: List of article dictionaries
        """
        try:
            # Encode the search query for URL
            encoded_query = quote_plus(query)
            
            # Make the request to Bing News
            url = f"{self.bing_news_url}{encoded_query}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch news from Bing: {response.status_code}")
                return []
            
            # Extract article data
            articles = []
            
            # Use regex for faster parsing
            # Find article cards
            article_sections = re.findall(r'<div class="news-card[^>]*>(.*?)</div>\s*</div>\s*</div>', 
                                         response.text, re.DOTALL)
            
            for section in article_sections[:max_articles * 2]:
                try:
                    # Extract title
                    title_match = re.search(r'<a[^>]*aria-label="([^"]*)"', section)
                    if not title_match:
                        continue
                    title = title_match.group(1).strip()
                    
                    # Extract URL
                    url_match = re.search(r'<a[^>]*href="([^"]*)"', section)
                    if not url_match:
                        continue
                    url = url_match.group(1)
                    
                    # Ensure URL is valid
                    if not url.startswith(('http://', 'https://')):
                        continue
                    
                    # Extract source
                    source_match = re.search(r'<div class="source[^>]*>(.*?)</div>', section)
                    source = "Bing News"
                    if source_match:
                        source = source_match.group(1).strip()
                    
                    # Extract timestamp
                    time_match = re.search(r'<div class="time[^>]*>(.*?)</div>', section)
                    timestamp = datetime.now().strftime("%Y-%m-%d")
                    
                    if url and title and len(title) > 10:
                        articles.append({
                            'title': title,
                            'url': url,
                            'source': source,
                            'timestamp': timestamp,
                            'article_id': f"bn_{hash(url) % 100000}",
                            'is_preferred': self.is_preferred_domain(url)
                        })
                        
                        if len(articles) >= max_articles:
                            break
                except Exception as e:
                    logger.error(f"Error parsing Bing News article: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"Error fetching Bing News: {e}")
            return []
    
    def verify_article_scrapability(self, url):
        """
        Quickly check if an article's content is likely to be scrapable
        
        Parameters:
        - url: Article URL to check
        
        Returns:
        - bool: True if likely scrapable, False otherwise
        """
        try:
            # Check if it's a preferred domain first
            if self.is_preferred_domain(url):
                return True
                
            # Check if it's a difficult domain
            if self.is_difficult_domain(url):
                return False
                
            # Make a quick HEAD request first
            head_response = requests.head(url, headers=self.headers, timeout=3)
            
            # Check content type
            content_type = head_response.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                return False
                
            # Check for paywalls or subscription indicators in URL path
            path = urlparse(url).path.lower()
            paywall_indicators = ['/subscribe', '/subscription', '/premium', '/signin', '/login', '/register']
            if any(indicator in path for indicator in paywall_indicators):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking scrapability for {url}: {e}")
            return False
    
    def _generate_sample_news(self, query, max_articles=5):
        """
        Generate sample news articles when real news fetching fails
        
        Parameters:
        - query: Search query
        - max_articles: Maximum number of articles to generate
        
        Returns:
        - list: List of article dictionaries with sample data
        """
        # Generate realistic fallback URLs from preferred domains
        domains = self.preferred_domains[:10]  # Use only first 10 preferred domains
        
        # Generate sample headlines
        headlines = [
            f"Latest developments for {query}",
            f"{query} announces new strategic initiative",
            f"Analysis: What's next for {query}",
            f"Report: {query} facing new market challenges",
            f"Experts weigh in on {query}'s future prospects",
            f"{query} releases quarterly performance results",
            f"Industry impact: How {query} is changing the landscape",
            f"Breaking: {query} in talks for major partnership"
        ]
        
        # Generate articles
        articles = []
        for i in range(min(max_articles, len(headlines))):
            domain = random.choice(domains)
            title = headlines[i]
            slug = title.lower().replace(' ', '-').replace(':', '').replace("'", '')[:30]
            url = f"https://www.{domain}/business/{int(time.time())}-{slug}"
            
            # Generate a date within the last week
            from datetime import datetime, timedelta
            days_ago = random.randint(0, 6)
            date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            
            articles.append({
                'title': title,
                'url': url,
                'source': domain.split('.')[0].capitalize(),
                'timestamp': date,
                'article_id': f"sample_{i}_{hash(query) % 10000}",
                'is_preferred': True,  # Mark as preferred to ensure processing
                'is_sample': True  # Flag to indicate this is a sample article
            })
        
        return articles