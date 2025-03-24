"""
Optimized Content scraper for News Analyzer - with site-specific extractors
"""
import os
import time
import logging
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import random
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import re

# Configure logging
logger = logging.getLogger("ContentScraper")

class ContentScraper:
    """Scrapes content from various news sources with optimized performance"""
    
    def __init__(self, use_selenium=False, cache_dir="./content_cache", cache_duration_days=1):
        """Initialize the content scraper with optimized defaults"""
        self.use_selenium = use_selenium  # Default to False for better performance
        self.cache_dir = Path(cache_dir)
        self.cache_duration_days = cache_duration_days
        self.cache = {}
        self.driver = None
        self.timeout = 10  # Reduced timeout for faster failures
        self._load_cache()
        
        # Initialize BeautifulSoup parser once
        self.parser = "html.parser"  # Lighter than lxml
        
        # Common headers to simulate a real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
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
        # Don't save cache immediately - will be saved periodically
    
    def _extract_domain(self, url):
        """Extract the domain from a URL (optimized)"""
        try:
            domain = urlparse(url).netloc
            return domain
        except:
            # Fallback if parsing fails
            if "://" in url:
                domain = url.split("://")[1].split("/")[0]
                return domain
            return url.split("/")[0]

    def _get_site_specific_extractor(self, domain):
        """Get site-specific extraction function based on domain"""
        extractors = {
            'reuters.com': self._extract_reuters,
            'apnews.com': self._extract_ap,
            'bbc.com': self._extract_bbc,
            'bbc.co.uk': self._extract_bbc,
            'npr.org': self._extract_npr,
            'theguardian.com': self._extract_guardian,
            'aljazeera.com': self._extract_aljazeera,
            'cnbc.com': self._extract_cnbc,
            'usatoday.com': self._extract_usatoday,
            'nytimes.com': self._extract_nytimes,
            'washingtonpost.com': self._extract_wapo,
            'news.yahoo.com': self._extract_yahoo,
            'cnn.com': self._extract_cnn,
            'foxnews.com': self._extract_fox,
            'hindustantimes.com': self._extract_hindustan_times,
            'ndtv.com': self._extract_ndtv,
            'timesofindia.indiatimes.com': self._extract_toi,
            'thehindu.com': self._extract_the_hindu,
            'economictimes.indiatimes.com': self._extract_economic_times
        }
        
        for site_domain, extractor in extractors.items():
            if site_domain in domain:
                return extractor
        
        return None
    
    def _extract_reuters(self, soup):
        """Extract content from Reuters articles"""
        # Try multiple selectors for Reuters articles
        content_div = soup.select_one('[data-testid="article-body"]')
        if not content_div:
            content_div = soup.select_one('.article-body__content__17Yit')
        if not content_div:
            content_div = soup.select_one('.StandardArticleBody_body')
        
        if content_div:
            paragraphs = content_div.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_ap(self, soup):
        """Extract content from AP News articles"""
        content_div = soup.select_one('.Article')
        if not content_div:
            content_div = soup.select_one('article')
        if not content_div:
            content_div = soup.select_one('.RichTextStoryBody')
        
        if content_div:
            paragraphs = content_div.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_bbc(self, soup):
        """Extract content from BBC articles"""
        article_body = soup.select_one('article')
        if article_body:
            paragraphs = article_body.select('p[data-component="text-block"]')
            if not paragraphs:
                paragraphs = article_body.select('div[data-component="text-block"]')
            if not paragraphs:
                # Try alternative selectors for BBC
                paragraphs = article_body.select('.ssrcss-1q0x1qg-Paragraph')
            if not paragraphs:
                paragraphs = article_body.find_all('p')
                
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_npr(self, soup):
        """Extract content from NPR articles"""
        article = soup.select_one('article')
        if article:
            # Try to find the main content area
            content_div = article.select_one('.storytext')
            if not content_div:
                content_div = article
                
            paragraphs = content_div.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_guardian(self, soup):
        """Extract content from The Guardian articles"""
        content_div = soup.select_one('.content__article-body')
        if not content_div:
            content_div = soup.select_one('article')
            
        if content_div:
            paragraphs = content_div.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_aljazeera(self, soup):
        """Extract content from Al Jazeera articles"""
        content_div = soup.select_one('.wysiwyg--all-content')
        if not content_div:
            content_div = soup.select_one('article')
            
        if content_div:
            paragraphs = content_div.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_cnbc(self, soup):
        """Extract content from CNBC articles"""
        article_body = soup.select_one('.ArticleBody-articleBody')
        if not article_body:
            article_body = soup.select_one('article')
            
        if article_body:
            paragraphs = article_body.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_usatoday(self, soup):
        """Extract content from USA Today articles"""
        content_div = soup.select_one('.gnt_ar_b')
        if not content_div:
            content_div = soup.select_one('article')
            
        if content_div:
            paragraphs = content_div.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_nytimes(self, soup):
        """Extract content from NY Times articles (might be behind paywall)"""
        content_div = soup.select_one('article')
        if content_div:
            # Check for paywall
            paywall = soup.select_one('#gateway-content') or soup.select_one('.css-gx5sib')
            if paywall:
                # Try to at least get the first paragraph/summary
                initial_paras = content_div.select('p:nth-child(-n+3)')
                if initial_paras:
                    content = '\n\n'.join([p.get_text().strip() for p in initial_paras if len(p.get_text()) > 20])
                    content += "\n\n[Article continues behind paywall]"
                    return content
                return "Article behind paywall"
            
            paragraphs = content_div.select('p.css-g5piaz')
            if not paragraphs:
                paragraphs = content_div.find_all('p')
                
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_wapo(self, soup):
        """Extract content from Washington Post articles"""
        content_div = soup.select_one('article')
        if content_div:
            # Check for paywall
            paywall = soup.select_one('.paywall')
            if paywall:
                return "Article behind paywall"
                
            paragraphs = content_div.select('.article-body p')
            if not paragraphs:
                paragraphs = content_div.find_all('p')
                
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_yahoo(self, soup):
        """Extract content from Yahoo News articles"""
        content_div = soup.select_one('.caas-body')
        if not content_div:
            content_div = soup.select_one('article')
            
        if content_div:
            paragraphs = content_div.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_cnn(self, soup):
        """Extract content from CNN articles"""
        content_div = soup.select_one('.article__content')
        if not content_div:
            content_div = soup.select_one('.zn-body__paragraph')
            
        if content_div:
            paragraphs = content_div.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        elif soup.select('.zn-body__paragraph'):  # Alternative CNN format
            paragraphs = soup.select('.zn-body__paragraph')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_fox(self, soup):
        """Extract content from Fox News articles"""
        article_body = soup.select_one('.article-body')
        if not article_body:
            article_body = soup.select_one('article')
            
        if article_body:
            paragraphs = article_body.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_hindustan_times(self, soup):
        """Extract content from Hindustan Times articles"""
        content_div = soup.select_one('.storyDetails')
        if not content_div:
            content_div = soup.select_one('article')
            
        if content_div:
            paragraphs = content_div.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_ndtv(self, soup):
        """Extract content from NDTV articles"""
        content_div = soup.select_one('.sp-cn')
        if not content_div:
            content_div = soup.select_one('article')
            
        if content_div:
            paragraphs = content_div.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_toi(self, soup):
        """Extract content from Times of India articles"""
        content_div = soup.select_one('.normal')
        if not content_div:
            content_div = soup.select_one('._s30J')  # New TOI design
        if not content_div:
            content_div = soup.select_one('arttextxml')  # Old TOI format
            
        if content_div:
            paragraphs = content_div.find_all('p')
            if not paragraphs:  # TOI sometimes doesn't use paragraph tags
                content = content_div.get_text().strip()
                # Clean up content
                content = re.sub(r'\s+', ' ', content)
                # Split into paragraphs by double linebreaks or sentences
                content = '\n\n'.join([p.strip() for p in re.split(r'(?:\n\n|\.\s+)', content) if len(p.strip()) > 20])
                return content
                
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_the_hindu(self, soup):
        """Extract content from The Hindu articles"""
        content_div = soup.select_one('.article')
        if not content_div:
            content_div = soup.select_one('.story-content')
            
        if content_div:
            paragraphs = content_div.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def _extract_economic_times(self, soup):
        """Extract content from Economic Times articles"""
        content_div = soup.select_one('.artText')
        if not content_div:
            content_div = soup.select_one('.article-body')
            
        if content_div:
            paragraphs = content_div.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return content
        return ""
    
    def extract_from_multiple_selectors(self, soup):
        """
        Try multiple selector combinations to extract content
        Returns the longest content found
        """
        best_content = ""
        
        # Various selector combinations to try
        selector_groups = [
            # Main article containers
            ['article', '[itemprop="articleBody"]', '.article-content', '.article-body'],
            
            # Content wrappers
            ['.content', '.story-body', '.post-content', '.page-content', '.entry-content'],
            
            # More specific selectors
            ['.main-content', '.story', '.article__body', '.article-text', '.story-text'],
            
            # Very specific selectors for common sites
            ['.story__body', '.article__content', '.entry__body', '.c-entry-content', '.post__content']
        ]
        
        # Try each selector group
        for selectors in selector_groups:
            for selector in selectors:
                try:
                    element = soup.select_one(selector)
                    if element:
                        # Try to get paragraphs within this container
                        paragraphs = element.find_all('p')
                        if paragraphs:
                            content = "\n\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
                            if len(content) > len(best_content):
                                best_content = content
                        
                        # If no paragraphs or content still too short, get all text
                        if len(best_content) < 200:
                            content = element.get_text().strip()
                            # Clean up content (remove extra whitespace)
                            content = re.sub(r'\s+', ' ', content)
                            content = re.sub(r'\n\s*\n', '\n\n', content)
                            if len(content) > len(best_content):
                                best_content = content
                except Exception as e:
                    continue
        
        return best_content

    def _initialize_selenium(self):
        """Initialize Selenium WebDriver for Hugging Face Spaces if needed"""
        if not self.use_selenium:
            return None
            
        if self.driver is not None:
            return self.driver
            
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            
            chrome_options = Options()
            
            # Critical flags for Hugging Face Spaces
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(f"user-agent={self.headers['User-Agent']}")
            
            # Disable automation flags to avoid detection
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            
            # Disable images for performance
            chrome_options.add_experimental_option("prefs", {
                "profile.default_content_settings": {"images": 2},
                "profile.managed_default_content_settings": {"images": 2}
            })
            
            # Determine environment (Hugging Face Spaces vs local)
            is_huggingface = os.environ.get('SPACE_ID') is not None
            
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
                "userAgent": self.headers['User-Agent']
            })
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            return self.driver
            
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {str(e)}")
            self.use_selenium = False  # Disable selenium for future attempts
            return None
    
    def _scrape_with_selenium(self, url):
        """Scrape content using Selenium (only called if use_selenium=True)"""
        driver = self._initialize_selenium()
        if not driver:
            return None
        
        try:
            driver.get(url)
            
            # Give the page minimal time to load
            time.sleep(2)
            
            # Try to extract content using selectors
            selectors = [
                "article", "[itemprop='articleBody']", ".article-content", 
                ".article-body", ".story-body", ".post-content", ".content",
                "#content", ".main-content", ".entry-content"
            ]
            
            for selector in selectors:
                try:
                    from selenium.webdriver.common.by import By
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        article_text = elements[0].text
                        if len(article_text) > 200:  # Meaningful content
                            return {
                                'title': driver.title,
                                'content': article_text,
                                'html': driver.page_source[:20000]  # Limit HTML size
                            }
                except:
                    continue
            
            # Extract paragraphs as a fallback
            try:
                from selenium.webdriver.common.by import By
                paragraphs = driver.find_elements(By.TAG_NAME, "p")
                if paragraphs:
                    content = "\n\n".join([p.text for p in paragraphs if len(p.text) > 30])
                    if content and len(content) > 200:
                        return {
                            'title': driver.title,
                            'content': content,
                            'html': driver.page_source[:20000]
                        }
            except:
                pass
            
            # Return None to fall back to requests method
            return None
            
        except Exception as e:
            logger.error(f"Selenium scraping failed: {e}")
            return None
    
    def scrape_with_enhanced_fallbacks(self, url):
        """
        Enhanced scraping that tries multiple methods to extract content
        """
        try:
            # First try standard request
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code != 200:
                return None
                
            soup = BeautifulSoup(response.text, self.parser)
            
            # Try site-specific extractor first
            domain = self._extract_domain(url)
            site_extractor = self._get_site_specific_extractor(domain)
            
            content = ""
            if site_extractor:
                content = site_extractor(soup)
                
            # If site-specific extractor failed or content is too short
            if not content or len(content) < 300:
                # Try enhanced extraction with multiple selectors
                content = self.extract_from_multiple_selectors(soup)
                
            # If still too short, try a more aggressive approach
            if not content or len(content) < 300:
                content = self._extract_text_content(soup)
                
            # If we've found substantial content
            if content and len(content) > 300:
                title = self._extract_title_from_html(response.text)
                return {
                    'title': title,
                    'content': content,
                    'html': None
                }
                
            return None
            
        except Exception as e:
            logger.error(f"Enhanced scraping failed: {e}")
            return None
    
    def _scrape_with_requests(self, url):
        """Simple requests-based scraper (primary method)"""
        try:
            # Add random sleep to avoid rate limiting
            time.sleep(random.uniform(0.1, 0.3))
            
            # Add additional headers if domain requires them
            domain = self._extract_domain(url)
            special_headers = {}
            
            # Special headers for some sites
            if 'nytimes.com' in domain:
                special_headers = {'Referer': 'https://www.google.com/'}
            elif 'wsj.com' in domain:
                special_headers = {'Referer': 'https://www.facebook.com/'}
            
            # Combine headers
            headers = {**self.headers, **special_headers}
            
            # Make request with timeout
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch {url}: HTTP {response.status_code}")
                return None
            
            # Check for paywalls or subscription notices
            content_lower = response.text.lower()
            paywall_indicators = ['subscribe now', 'subscription required', 'premium content', 
                                'to continue reading', 'create an account', 'sign up to read',
                                'subscribe to read', 'premium subscriber', 'to continue reading']
            
            has_paywall = any(indicator in content_lower for indicator in paywall_indicators)
            
            # Extract the title
            title = self._extract_title_from_html(response.text)
            
            # Create a BeautifulSoup object
            soup = BeautifulSoup(response.text, self.parser)
            
            # First try site-specific extractor
            site_extractor = self._get_site_specific_extractor(domain)
            if site_extractor:
                content = site_extractor(soup)
                if content and len(content) > 200:
                    return {
                        'title': title,
                        'content': content,
                        'html': None  # Don't store HTML to save memory
                    }
            
            # If site-specific extractor failed or if content might be behind paywall
            if has_paywall and (not content or len(content) < 500):
                return {
                    'title': title,
                    'content': "Article behind paywall",
                    'html': None
                }
                
            # Try multiple extraction methods
            content = self.extract_from_multiple_selectors(soup)
            
            if content and len(content) > 200:
                return {
                    'title': title,
                    'content': content,
                    'html': None  # Don't store HTML to save memory
                }
            
            # If we couldn't extract content, try a different approach
            content = self._extract_paragraphs(soup)
            
            if content and len(content) > 200:
                return {
                    'title': title,
                    'content': content,
                    'html': None
                }
                
            # If still no content, use a more aggressive approach
            content = self._extract_text_content(soup)
            
            if content and len(content) > 200:
                return {
                    'title': title,
                    'content': content,
                    'html': None
                }
                
            # If we reach here, extraction failed
            return {
                'title': title,
                'content': "Failed to extract content",
                'html': None
            }
            
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout for {url}")
            return {
                'title': "Timeout Error",
                'content': f"Request timed out for {url}",
                'html': None
            }
        except Exception as e:
            logger.error(f"Request-based scraping failed: {e}")
            return {
                'title': "Error",
                'content': f"Error scraping content: {str(e)}",
                'html': None
            }
    
    def _extract_title_from_html(self, html_text):
        """Extract the title from HTML (optimized)"""
        try:
            # Try to extract title using regex first (faster)
            title_match = re.search('<title[^>]*>(.*?)</title>', html_text, re.IGNORECASE)
            if title_match:
                return title_match.group(1)
            
            # If regex fails, use BeautifulSoup
            soup = BeautifulSoup(html_text, self.parser)
            if soup.title:
                return soup.title.get_text().strip()
                
            # Try meta tags
            meta_title = soup.find("meta", property="og:title")
            if meta_title and meta_title.get("content"):
                return meta_title["content"].strip()
                
            return "Unknown Title"
        except:
            return "Unknown Title"
    
    def _extract_article_content(self, soup):
        """Extract article content using common article containers"""
        # Try to find main content containers
        for selector in ['article', '[itemprop="articleBody"]', '.article-content', 
                        '.article-body', '.story-body', '.post-content', '.content',
                        '#content', '.main-content', '.entry-content']:
            try:
                element = soup.select_one(selector)
                if element:
                    # First try to get all paragraphs within this container
                    paragraphs = element.find_all('p')
                    if paragraphs:
                        content = "\n\n".join([p.get_text().strip() for p in paragraphs 
                                            if len(p.get_text().strip()) > 20])
                        if len(content) > 200:
                            return content
                    
                    # If no paragraphs or content too short, get all text
                    content = element.get_text().strip()
                    if len(content) > 200:
                        # Clean up content (remove extra whitespace)
                        content = re.sub(r'\s+', ' ', content)
                        content = re.sub(r'\n\s*\n', '\n\n', content)
                        return content
            except:
                continue
        
        return ""
    
    def _extract_paragraphs(self, soup):
        """Extract all paragraphs from the page"""
        try:
            paragraphs = soup.find_all('p')
            
            # Filter out short paragraphs and navigation elements
            filtered_paragraphs = []
            for p in paragraphs:
                text = p.get_text().strip()
                if len(text) > 20:
                    # Check if not in a nav, header, or footer element
                    if not any(parent.name in ['nav', 'header', 'footer'] 
                              for parent in p.parents):
                        filtered_paragraphs.append(text)
            
            content = "\n\n".join(filtered_paragraphs)
            return content if len(content) > 200 else ""
        except:
            return ""
    
    def _extract_text_content(self, soup):
        """More aggressive text extraction as a last resort"""
        try:
            # Remove script, style elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
            
            # Get text and split into lines
            text = soup.get_text(separator='\n')
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            
            # Filter out short lines and remove duplicate/similar lines
            filtered_lines = []
            seen_lines = set()
            for line in lines:
                if len(line) > 30:
                    # Simple deduplication - check first 10 chars to avoid similar headers/dates
                    line_start = line[:10].lower()
                    if line_start not in seen_lines:
                        seen_lines.add(line_start)
                        filtered_lines.append(line)
            
            content = "\n\n".join(filtered_lines)
            return content
        except:
            return ""
    
    def get_article_content(self, url):
        """Get the content of an article with enhanced fallbacks"""
        # Try cached version first
        cached_content = self._get_cached_content(url)
        if cached_content:
            return cached_content
        
        # Match domain to scraper
        domain = self._extract_domain(url)
        logger.info(f"Scraping article: {url} from {domain}")
        
        # First try with regular requests method
        content = self._scrape_with_requests(url)
        
        # If content is too short or extraction failed, try the enhanced method
        if (not content or 
            content.get('content') == "Failed to extract content" or 
            content.get('content') == "Article behind paywall" or
            len(content.get('content', '')) < 300):
            
            logger.info(f"Regular extraction failed or content too short, trying enhanced extraction for {url}")
            enhanced_content = self.scrape_with_enhanced_fallbacks(url)
            if enhanced_content and len(enhanced_content.get('content', '')) > 300:
                content = enhanced_content
        
        # Fall back to Selenium only if requests fails AND Selenium is enabled
        if (not content or 
            content.get('content') == "Failed to extract content" or 
            content.get('content') == "Article behind paywall" or
            len(content.get('content', '')) < 300) and self.use_selenium:
            
            logger.info(f"Falling back to Selenium for {url}")
            try:
                selenium_content = self._scrape_with_selenium(url)
                if selenium_content and len(selenium_content.get('content', '')) > 300:
                    content = selenium_content
            except Exception as e:
                logger.warning(f"Selenium fallback failed for {url}: {e}")
        
        # Cache the content if we got something
        if content and content.get('content') != "Failed to extract content" and len(content.get('content', '')) > 300:
            self._cache_content(url, content)
            return content
        
        return content  # May be None or error content
        
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
                
            # Check if URL is properly formatted
            if not url.startswith(('http://', 'https://')):
                if url.startswith('www.'):
                    url = 'https://' + url
                else:
                    url = 'https://www.' + url
                article_data['url'] = url
                logger.info(f"Fixed URL format: {url}")
            
            # Try to get content from the URL
            content_result = self.get_article_content(url)
            
            if content_result:
                # Update the article with the scraped content
                article_data['content'] = content_result.get('content', '')
                
                # Check if content is substantial
                if len(article_data['content']) < 300 and article_data['content'] != "Article behind paywall":
                    # Try one more aggressive attempt
                    enhanced_result = self.scrape_with_enhanced_fallbacks(url)
                    if enhanced_result and len(enhanced_result.get('content', '')) > 300:
                        article_data['content'] = enhanced_result.get('content', '')
                
                # If the article didn't have a title, use the one from content
                if not article_data.get('title') and content_result.get('title'):
                    article_data['title'] = content_result.get('title')
                    
                # Add scraping success indicator
                article_data['scraping_success'] = len(article_data['content']) > 300
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
    
    def generate_simple_content(self, title, url):
        """Generate a simple content object when all scraping methods fail"""
        return {
            'title': title,
            'content': f"Unable to retrieve full content for this article. Please visit the original source: {url}",
            'html': None
        }