import requests
from bs4 import BeautifulSoup
import re
import random
import time
import json
import logging
import os
import pickle
from urllib.parse import urlparse
from datetime import datetime, timedelta
from requests.exceptions import RequestException
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import cloudscraper
import backoff

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ContentScraper")

class ContentScraper:
    def __init__(self, use_selenium=True, cache_dir="./cache", cache_duration_days=1):
        """
        Initialize the ContentScraper with optimized configuration
        
        Args:
            use_selenium: Whether to use Selenium (default True)
            cache_dir: Directory for persistent cache storage
            cache_duration_days: How long to keep cache entries valid (in days)
        """
        self.use_selenium = use_selenium
        
        # Basic configuration
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
        ]
        
        # Request configuration
        self.timeout = 15  # Reduced timeout for faster response
        self.max_retries = 2  # Limit retries to avoid long waits
        
        # Selenium components
        self.driver = None
        
        # For cloudflare bypass
        self.cloudscraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        
        # Site-specific parsers
        self.site_parsers = self._load_site_parsers()
        
        # Setup persistent cache
        self.cache = {}
        self.cache_dir = cache_dir
        self.cache_duration = timedelta(days=cache_duration_days)
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        # Domain-specific method selection patterns
        self.domain_patterns = {
            # Simple news sites - use requests
            'requests': ['reuters.com', 'apnews.com', 'bbc.com', 'npr.org', 'cnn.com', 'washingtonpost.com'],
            
            # Sites with Cloudflare - use cloudscraper
            'cloudscraper': ['bloomberg.com', 'businessinsider.com'],
            
            # JS-heavy sites - use Selenium
            'selenium': ['nytimes.com', 'wsj.com', 'medium.com', 'theverge.com', 'techcrunch.com', 'wired.com']
        }
        
        # Load cache from disk
        self._load_cache()
        
        # Initialize WebDriver at startup if using Selenium
        if self.use_selenium:
            self._initialize_selenium()
    
    def _load_site_parsers(self):
        """Load site-specific parsing rules with fallback to defaults"""
        try:
            with open('site_parsers.json', 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Default rules if file doesn't exist
            return {
                "nytimes.com": {
                    "content_selector": "section[name='articleBody']",
                    "paywall_indicators": ["subscribe", "subscription", "create your free account"],
                    "cleanup_selectors": [".ad", ".newsletter-signup", ".comments"]
                },
                "medium.com": {
                    "content_selector": "article",
                    "paywall_indicators": ["Members only story", "Your membership"],
                    "cleanup_selectors": [".metabar", ".js-postMetaLockup", ".js-stickyFooter"]
                },
                "bbc.com": {
                    "content_selector": ".article__body-content",
                    "cleanup_selectors": [".related-content", ".with-extracted-share-icons"]
                },
                "reuters.com": {
                    "content_selector": ".article-body",
                    "cleanup_selectors": [".article-related", ".trust-badge"]
                }
            }
    
    def _load_cache(self):
        """Load cache from disk with error handling"""
        try:
            cache_file = os.path.join(self.cache_dir, "content_cache.pkl")
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    cached_data = pickle.load(f)
                    # Filter out expired entries
                    now = datetime.now()
                    self.cache = {
                        url: (content, timestamp) 
                        for url, (content, timestamp) in cached_data.items()
                        if now - timestamp < self.cache_duration
                    }
                logger.info(f"Loaded {len(self.cache)} cached items from disk")
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            # Continue with empty cache if loading fails
            self.cache = {}

    def _save_cache(self):
        """Save cache to disk with error handling"""
        try:
            cache_file = os.path.join(self.cache_dir, "content_cache.pkl")
            with open(cache_file, "wb") as f:
                pickle.dump(self.cache, f)
            logger.info(f"Saved {len(self.cache)} cached items to disk")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    def _initialize_selenium(self):
        """Initialize Selenium WebDriver with more aggressive optimizations"""
        if self.driver is not None:
            return self.driver
            
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Additional speed optimizations
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-geolocation")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-browser-side-navigation")
        chrome_options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        
        # Even more aggressive resource blocking
        chrome_prefs = {
            "profile.default_content_settings": {"images": 2, "javascript": 1},
            "profile.managed_default_content_settings": {"images": 2},
            "permissions.default.stylesheet": 2,
            # Disable save password popup
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            # Disable downloads
            "download_restrictions": 3,
        }
        chrome_options.add_experimental_option("prefs", chrome_prefs)
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
        
        # Initialize the WebDriver with service
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(self.timeout)
            return self.driver
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            return None
        
    def close(self):
        """Close WebDriver and save cache before exiting"""
        # Save cache
        self._save_cache()
        
        # Close WebDriver
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except Exception as e:
                logger.error(f"Error closing driver: {e}")
            
    def __del__(self):
        """Ensure cleanup on object destruction"""
        self.close()
    
    def _select_method_for_domain(self, domain):
        """Select the appropriate scraping method based on domain patterns"""
        for method, patterns in self.domain_patterns.items():
            if any(pattern in domain for pattern in patterns):
                return method
        # Default to requests as fastest method
        return 'requests'
    
    def scrape_article(self, url, force_method=None, bypass_cache=False):
        """
        Scrape article content with smart method selection and caching
        
        Args:
            url: URL to scrape
            force_method: Force a specific method ('requests', 'cloudscraper', 'selenium')
            bypass_cache: Whether to bypass the cache
            
        Returns:
            str: Extracted content or None if failed
        """
        # Check cache first
        if not bypass_cache and url in self.cache:
            content, timestamp = self.cache[url]
            # Check if cache entry is still valid
            if datetime.now() - timestamp < self.cache_duration:
                logger.info(f"Using cached content for {url}")
                return content
            
        domain = urlparse(url).netloc
        logger.info(f"Scraping article: {url} with domain: {domain}")
        
        # Smart method selection based on domain
        method = force_method if force_method else self._select_method_for_domain(domain)
        
        # Try selected method first
        try:
            content = self._get_content_with_method(url, method)
            if content and len(content) > 500 and not content.startswith("Article behind paywall"):
                # Store in cache with timestamp
                self.cache[url] = (content, datetime.now())
                # Save cache periodically
                if len(self.cache) % 10 == 0:
                    self._save_cache()
                return content
        except Exception as e:
            logger.warning(f"Primary method {method} failed for {url}: {e}")
        
        # Try ONE fallback method if primary method fails
        if method == 'requests':
            fallback = 'selenium'
        elif method == 'cloudscraper':
            fallback = 'requests'
        else:
            fallback = 'requests'
            
        logger.info(f"Trying fallback method: {fallback} for {url}")
        
        try:
            content = self._get_content_with_method(url, fallback)
            if content and len(content) > 500 and not content.startswith("Article behind paywall"):
                # Store in cache with timestamp
                self.cache[url] = (content, datetime.now())
                return content
        except Exception as e:
            logger.warning(f"Fallback method {fallback} failed for {url}: {e}")
        
        return "Failed to extract content"
    
    def _get_content_with_method(self, url, method):
        """Execute a specific scraping method"""
        if method == 'requests':
            html = self._scrape_with_requests(url)
        elif method == 'cloudscraper':
            html = self._scrape_with_cloudscraper(url)
        elif method == 'selenium':
            html = self._scrape_with_selenium(url)
        else:
            raise ValueError(f"Unknown method: {method}")
            
        # Check if content is behind paywall
        if self._is_behind_paywall(html):
            return "Article behind paywall"
            
        # Parse content
        return self._parse_content(html, urlparse(url).netloc)

    @backoff.on_exception(
        backoff.expo,
        (RequestException),
        max_tries=2,
        factor=1.5
    )
    def _scrape_with_requests(self, url):
        """Scrape using requests with optimized headers"""
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        
        response = requests.get(url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        
        return response.text
        
    @backoff.on_exception(
        backoff.expo,
        (Exception),
        max_tries=2,
        factor=1.5
    )
    def _scrape_with_cloudscraper(self, url):
        """Scrape using cloudscraper (Cloudflare bypass)"""
        response = self.cloudscraper.get(url, timeout=self.timeout)
        response.raise_for_status()
        
        return response.text
            
    @backoff.on_exception(
        backoff.expo,
        (Exception),
        max_tries=2,
        factor=1.5
    )
    def _scrape_with_selenium(self, url):
        """Scrape using Selenium with optimized load strategy"""
        driver = self._initialize_selenium()
        if not driver:
            raise RuntimeError("WebDriver initialization failed")
            
        try:
            # Set script timeout lower to abort scripts faster
            driver.set_script_timeout(5)
            
            # Faster page load strategy
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": random.choice(self.user_agents)})
            driver.execute_cdp_cmd('Network.enable', {})
            
            # Abort unnecessary requests
            driver.execute_cdp_cmd('Network.setBlockedURLs', {"urls": [
                "*.gif", "*.png", "*.jpg", "*.jpeg", "*.svg", "*.webp", 
                "fonts.googleapis.com", "*.doubleclick.net", "*.analytics", 
                "*.adservice.", "*.ads.", "pagead", 
            ]})
            
            driver.get(url)
            
            # Wait for the page to load (reduced timeout further)
            try:
                WebDriverWait(driver, 6).until(
                    EC.presence_of_element_located((By.TAG_NAME, "p"))
                )
            except:
                pass  # Continue even if timeout, we might still have enough content
            
            # No scroll, just grab content quickly
            return driver.page_source
                
        except Exception as e:
            logger.error(f"Selenium method failed for {url}: {e}")
            raise
        finally:
            # Clear cookies for next attempt
            try:
                driver.delete_all_cookies()
            except:
                pass
            
    def _expand_content(self, driver):
        """Try to expand "read more" buttons with simplified approach"""
        expand_buttons = [
            '//button[contains(text(), "Read more")]',
            '//button[contains(text(), "Show more")]',
            '//a[contains(text(), "Read more")]'
        ]
        
        for xpath in expand_buttons:
            try:
                buttons = driver.find_elements(By.XPATH, xpath)
                for button in buttons[:2]:  # Limit to first 2 buttons
                    try:
                        driver.execute_script("arguments[0].click();", button)
                    except:
                        pass
            except:
                pass
                
        # Simple scroll to load lazy content
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        except:
            pass
    
    def _is_behind_paywall(self, html):
        """Check if content is behind a paywall with streamlined approach"""
        if not html:
            return False
            
        soup = BeautifulSoup(html, 'lxml')
        
        # Check for obvious paywall indicators
        paywall_selectors = [".paywall", ".subscription", ".paid-content", "#paywall"]
        for selector in paywall_selectors:
            if soup.select_one(selector):
                return True
        
        # Check for paywall keywords in key areas
        paywall_texts = ["subscribe", "subscription", "paid member", "premium content"]
        
        # Check in first 5000 chars (higher concentration of paywall notices)
        text_sample = soup.get_text()[:5000].lower()
        keyword_count = sum(1 for keyword in paywall_texts if keyword in text_sample)
        
        # If multiple paywall indicators are found, it's likely a paywall
        if keyword_count >= 3:
            return True
                
        return False

    def _parse_content(self, html, domain=None):
        """Enhanced content parsing with fallbacks for difficult sites"""
        if not html or len(html) < 100:
            return None
            
        # Use lxml parser which is faster than html.parser
        soup = BeautifulSoup(html, 'lxml')
        
        # Try site-specific parsing rules first
        if domain and domain in self.site_parsers:
            content = self._parse_with_site_rules(soup, domain)
            if content and len(content) > 300:
                return content
        
        # Extract article with prioritized selectors
        content = self._extract_with_selectors(soup)
        if content and len(content) > 300:
            return content
        
        # If standard approach fails, try more aggressive extraction
        if not content or len(content) < 300:
            # Use density-based extraction - find the block with highest
            # text density and fewest HTML tags
            content = self._extract_by_density(soup)
            if content and len(content) > 300:
                return content
        
        # Last resort: try to get all paragraphs with reasonable length
        paragraphs = [p.text.strip() for p in soup.find_all('p') if len(p.text.strip()) > 60]
        if paragraphs and len(' '.join(paragraphs)) > 300:
            return self._clean_text(' '.join(paragraphs))
        
        # Nothing worked - return a clear error
        return "Could not extract meaningful content from this article."
        
    def _extract_with_selectors(self, soup):
        """Extract content using prioritized selectors"""
        # These selectors target typical article content areas
        selectors = [
            'article', 
            'div[itemprop="articleBody"]', 
            '.post-content',
            '.article-content',
            '.entry-content', 
            '.story-content',
            'main .content',
            '#article-body',
            '[data-testid="article-body"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                # Get the element with the most text content
                element = max(elements, key=lambda el: len(el.get_text()))
                
                # Clean up unwanted elements
                for tag in ['script', 'style', 'nav', 'header', 'footer', 'aside']:
                    for unwanted in element.find_all(tag):
                        unwanted.decompose()
                        
                # Also remove common ad/subscription related classes
                for cls in ['ad', 'ads', 'subscription', 'newsletter', 'related', 'social']:
                    for unwanted in element.select(f'[class*="{cls}"]'):
                        unwanted.decompose()
                
                text = ' '.join(element.stripped_strings)
                if len(text) > 300:
                    return self._clean_text(text)
        
        return None

    def _extract_by_density(self, soup):
        """Extract content by finding the area with highest text density"""
        # Find all divs with substantial text
        candidates = []
        
        # Find all divs with some content
        for div in soup.find_all(['div', 'section']):
            text = div.get_text().strip()
            if len(text) < 200:
                continue
                
            # Count text chars and HTML tags to calculate density
            html_length = len(str(div))
            text_length = len(text)
            
            if html_length == 0:
                continue
                
            # Calculate text density (higher is better)
            density = text_length / html_length
            
            # Count the number of paragraph tags (more is better)
            p_count = len(div.find_all('p'))
            
            # Ignore likely navigation, header, or sidebar elements
            if any(cls in (div.get('class', []) or []) for cls in ['nav', 'menu', 'header', 'footer', 'sidebar']):
                continue
                
            # Calculate a score based on density and paragraph count
            score = density * (1 + (0.1 * p_count))
            
            candidates.append((div, score, text_length))
        
        # Sort by score and take the best
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_div, _, _ = candidates[0]
            
            # Clean any remaining unwanted elements
            for tag in ['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']:
                for unwanted in best_div.find_all(tag):
                    unwanted.decompose()
                    
            text = ' '.join(best_div.stripped_strings)
            return self._clean_text(text)
        
        return None

    def _parse_with_site_rules(self, soup, domain):
        """Optimized site-specific parsing"""
        rules = self.site_parsers.get(domain, {})
        if not rules:
            return None
            
        # Apply site-specific clean-up
        for selector in rules.get('cleanup_selectors', [])[:5]:  # Limit cleanup operations
            for element in soup.select(selector):
                element.decompose()
                
        # Extract content with site-specific selector
        content_selector = rules.get('content_selector')
        if content_selector:
            element = soup.select_one(content_selector)
            if element:
                return self._clean_text(' '.join(element.stripped_strings))
                
        return None
    
    def _clean_text(self, text):
        """Clean extracted text with simplified processing"""
        if not text:
            return ""
            
        # Replace multiple spaces, newlines, tabs with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Simple boilerplate removal
        boilerplates = [
            "please enable JavaScript",
            "cookies are disabled",
            "please subscribe to continue reading",
            "turn off your ad blocker"
        ]
        
        for phrase in boilerplates:
            text = re.sub(re.escape(phrase), '', text, flags=re.IGNORECASE)
            
        return text.strip()