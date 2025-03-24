"""
Content scraper for News Analyzer - optimized for Hugging Face Spaces
"""
import os
import time
import logging
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import random
import backoff

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configure logging
logger = logging.getLogger("ContentScraper")

class ContentScraper:
    """Scrapes content from various news sources"""
    
    def __init__(self, use_selenium=True, cache_dir="./content_cache", cache_duration_days=1):
        """Initialize the content scraper"""
        self.use_selenium = use_selenium
        self.cache_dir = Path(cache_dir)
        self.cache_duration_days = cache_duration_days
        self.cache = {}
        self.driver = None
        self.timeout = 15  # seconds
        self._load_cache()
        
    def __del__(self):
        """Clean up resources"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
    
    def _load_cache(self):
        """Load the cache from disk"""
        try:
            if not self.cache_dir.exists():
                self.cache_dir.mkdir(parents=True)
            
            cache_file = self.cache_dir / "cache.json"
            if cache_file.exists():
                with open(cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                logger.info(f"Loaded {len(self.cache)} cached items from disk")
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            self.cache = {}
    
    def _save_cache(self):
        """Save the cache to disk"""
        try:
            cache_file = self.cache_dir / "cache.json"
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False)
            logger.info(f"Saved {len(self.cache)} cached items to disk")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def _get_cached_content(self, url):
        """Get cached content for a URL"""
        key = hashlib.md5(url.encode()).hexdigest()
        
        if key in self.cache:
            cache_entry = self.cache[key]
            cache_time = datetime.fromisoformat(cache_entry["timestamp"])
            if datetime.now() - cache_time < timedelta(days=self.cache_duration_days):
                logger.info(f"Using cached content for {url}")
                return cache_entry["content"]
        
        return None
    
    def _cache_content(self, url, content):
        """Cache content for a URL"""
        key = hashlib.md5(url.encode()).hexdigest()
        self.cache[key] = {
            "url": url,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        self._save_cache()
    
    def _extract_domain(self, url):
        """Extract the domain from a URL"""
        from urllib.parse import urlparse
        
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            return domain
        except:
            # If parsing fails, extract domain with a simpler approach
            if "://" in url:
                domain = url.split("://")[1].split("/")[0]
                return domain
            return url.split("/")[0]
    
    def _initialize_selenium(self):
        """Initialize Selenium WebDriver for Hugging Face Spaces"""
        if self.driver is not None:
            return self.driver
            
        chrome_options = Options()
        
        # Critical flags for Hugging Face Spaces
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Add random user agent to avoid detection
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.2 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36'
        ]
        chrome_options.add_argument(f"user-agent={random.choice(user_agents)}")
        
        # Disable automation flags to avoid detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        
        # Disable images for performance
        chrome_prefs = {
            "profile.default_content_settings": {"images": 2},
            "profile.managed_default_content_settings": {"images": 2}
        }
        chrome_options.add_experimental_option("prefs", chrome_prefs)
        
        # Determine environment (Hugging Face Spaces vs local)
        is_huggingface = os.environ.get('SPACE_ID') is not None
        
        try:
            if is_huggingface:
                # On Hugging Face Spaces, use system chromium-browser
                chrome_options.binary_location = "/usr/bin/chromium-browser"
                service = Service("/usr/bin/chromedriver")
            else:
                # For local development, use webdriver-manager
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(self.timeout)
            
            # Execute stealth JS to avoid detection
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": random.choice(user_agents)
            })
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            return self.driver
            
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {str(e)}")
            return None
    
    def _scrape_with_domain_rules(self, url, domain):
        """Scrape content using domain-specific rules"""
        # This can be expanded with domain-specific rules
        
        # Google News redirects to actual news sites
        if "news.google.com" in domain:
            return None
            
        # Default: return None to try other methods
        return None
    
    @backoff.on_exception(backoff.expo, RuntimeError, max_tries=2)
    def _scrape_with_selenium(self, url):
        """Scrape content using Selenium"""
        driver = self._initialize_selenium()
        if not driver:
            raise RuntimeError("WebDriver initialization failed")
        
        try:
            driver.get(url)
            
            # Give the page time to load and execute JavaScript
            time.sleep(3)
            
            # Try to dismiss any popups
            try:
                from selenium.webdriver.common.keys import Keys
                from selenium.webdriver.common.action_chains import ActionChains
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            except:
                pass
                
            # Scroll down to load lazy content
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            time.sleep(1)
            
            # Try to extract content using selectors
            content = None
            
            # 1. Look for article content containers
            selectors = [
                "article", "[itemprop='articleBody']", ".article-content", 
                ".article-body", ".story-body", ".post-content", ".content",
                "#content", ".main-content", ".entry-content"
            ]
            
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        article_text = elements[0].text
                        if len(article_text) > 200:  # Meaningful content
                            return {
                                'title': driver.title,
                                'content': article_text,
                                'html': driver.page_source
                            }
                except Exception as e:
                    continue
            
            # 2. Extract all paragraphs as a fallback
            try:
                paragraphs = driver.find_elements(By.TAG_NAME, "p")
                if paragraphs:
                    content = "\n\n".join([p.text for p in paragraphs if len(p.text) > 30])
                    if content and len(content) > 200:
                        return {
                            'title': driver.title,
                            'content': content,
                            'html': driver.page_source
                        }
            except Exception as e:
                pass
                
            # 3. Get main text as a last resort
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if body_text and len(body_text) > 200:
                # Try to clean it up a bit
                lines = body_text.split("\n")
                filtered_lines = [line for line in lines if len(line.strip()) > 30]
                content = "\n\n".join(filtered_lines)
                
                return {
                    'title': driver.title,
                    'content': content,
                    'html': driver.page_source
                }
                
            # If we reach this point, we couldn't extract meaningful content
            return None
            
        except Exception as e:
            logger.error(f"Selenium scraping failed: {e}")
            raise RuntimeError(f"Selenium scraping failed: {e}")
    
    def _scrape_with_requests(self, url):
        """Simple requests-based scraper as final fallback"""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            # Use a realistic user agent
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                return None
                
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
                
            # Try to find main content containers
            content = ""
            selectors = ['article', '.article', '.post', 'main', '#main-content', 
                        '[itemprop="articleBody"]', '.article-body', '.story-body']
            
            for selector in selectors:
                if article := soup.select_one(selector):
                    paragraphs = article.find_all("p")
                    if paragraphs:
                        content = "\n\n".join([p.get_text().strip() for p in paragraphs 
                                            if len(p.get_text().strip()) > 30])
                        if content:
                            break
            
            # If no structured content found, try extracting all paragraphs
            if not content:
                paragraphs = soup.find_all("p")
                good_paragraphs = [p.get_text().strip() for p in paragraphs 
                                if len(p.get_text().strip()) > 30]
                content = "\n\n".join(good_paragraphs)
            
            # If still no content, try as a last resort
            if not content:
                # Strip HTML tags and get text content
                text = soup.get_text(separator='\n')
                # Split into lines and filter out short ones
                lines = text.split('\n')
                content = "\n\n".join([line.strip() for line in lines 
                                    if len(line.strip()) > 50])
                
            # Check if we have meaningful content
            if content and len(content) > 200:
                title = soup.title.get_text() if soup.title else "No title found"
                return {
                    'title': title,
                    'content': content,
                    'html': response.text
                }
                
            return None
        except Exception as e:
            logger.error(f"Request-based scraping failed: {e}")
            return None
    
    def scrape_article(self, article_data):
        """
        Scrape content for an article using its URL and title
        
        Parameters:
        - article_data: dict containing at minimum 'url' and 'title', or a string URL
        
        Returns:
        - dict: The updated article data with content added
        """
        try:
            # Check if article_data is a dictionary or string URL
            if isinstance(article_data, str):
                url = article_data
                article_data = {
                    'url': url,
                    'title': 'Unknown Title'
                }
            else:
                # Make sure article_data is a dictionary
                url = article_data.get('url')
            
            if not url:
                logger.error("Article data missing URL")
                return article_data
                
            # Try to get content from the URL
            content_result = self.get_article_content(url)
            
            if content_result:
                # Update the article with the scraped content
                article_data['content'] = content_result.get('content', '')
                
                # If the article didn't have a title, use the one from content
                if not article_data.get('title') and content_result.get('title'):
                    article_data['title'] = content_result.get('title')
                    
                # Store HTML content if needed for future processing
                article_data['html'] = content_result.get('html', '')
                
                # Add scraping status
                article_data['scraping_success'] = True
            else:
                # If scraping failed, add a placeholder message
                article_data['content'] = (
                    f"Unable to retrieve full content for this article. "
                    f"Please visit the original source: {url}"
                )
                article_data['scraping_success'] = False
                
            return article_data
                
        except Exception as e:
            logger.error(f"Error scraping article: {e}")
            # Return the original article data if scraping fails
            if isinstance(article_data, dict):
                article_data['content'] = f"Error retrieving content: {str(e)}"
                article_data['scraping_success'] = False
            else:
                article_data = {
                    'url': str(article_data),
                    'title': 'Unknown Title',
                    'content': f"Error retrieving content: {str(e)}",
                    'scraping_success': False
                }
            return article_data
    
    def get_article_content(self, url):
        """Get the content of an article with fallbacks for Hugging Face Spaces"""
        # Try cached version first
        cached_content = self._get_cached_content(url)
        if cached_content:
            return cached_content
        
        # Match domain to scraper
        domain = self._extract_domain(url)
        logger.info(f"Scraping article: {url} with domain: {domain}")
        
        # Try several methods in sequence
        # 1. First try using domain-specific rules
        content = self._scrape_with_domain_rules(url, domain)
        
        # 2. If domain rules failed, try Selenium
        if content is None and self.use_selenium:
            logger.info(f"Trying fallback method: selenium for {url}")
            try:
                content = self._scrape_with_selenium(url)
            except Exception as e:
                logger.warning(f"Fallback method selenium failed for {url}: {e}")
        
        # 3. If Selenium failed, try simple requests
        if content is None:
            logger.info(f"Trying final fallback: requests for {url}")
            content = self._scrape_with_requests(url)
        
        # Cache the content if we got something
        if content:
            self._cache_content(url, content)
            return content
        
        return None
        
    def generate_simple_content(self, title, url):
        """Generate a simple content object when all scraping methods fail"""
        return {
            'title': title,
            'content': f"Unable to retrieve full content for this article. Please visit the original source: {url}",
            'html': "<html><body><p>Content not available</p></body></html>"
        }