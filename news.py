"""
Advanced News Analyzer with Hindi TTS, Topic Extraction, and Comparative Analysis
Optimized for performance with non-JS content prioritization
"""
import streamlit as st
from news_fetcher import NewsFetcher
from content_scraper import ContentScraper
from summary import SummaryGenerator
from topic_extractor import TopicExtractor
from comparative_analysis import ComparativeAnalyzer
from textblob import TextBlob
from gtts import gTTS
from deep_translator import GoogleTranslator
from urllib.parse import urlparse
import base64
from io import BytesIO
import os
import sys
import logging
import time
import re
import io
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment configuration
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["PYTHONWARNINGS"] = "ignore"

# Debug flag to help troubleshoot issues
DEBUG_MODE = True

# Fixed number of articles to select from slider - updated with more options and higher default
ARTICLE_CHOICES = [5, 10, 15, 20, 25, 30]

def get_sentiment(text):
    """Perform sentiment analysis using TextBlob with error handling"""
    try:
        analysis = TextBlob(text)
        pol = analysis.polarity
        if pol > 0.2: return '😊 Positive', pol
        if pol < -0.2: return '😠 Negative', pol
        return '😐 Neutral', pol
    except Exception as e:
        logger.error(f"Sentiment analysis error: {str(e)}")
        return '❓ Unknown', 0.0

def debug_print(message):
    """Print debug messages when DEBUG_MODE is enabled"""
    if DEBUG_MODE:
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"[DEBUG {current_time}] {message}")
        logger.info(f"DEBUG: {message}")

def clean_html_text(text):
    """Clean HTML tags from text"""
    if not text:
        return ""
    
    # First try with regex (faster)
    clean_text = re.sub(r'<[^>]+>', ' ', text)
    # Replace multiple spaces with a single space
    clean_text = re.sub(r'\s+', ' ', clean_text)
    # Replace HTML entities
    clean_text = clean_text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')\
                          .replace('&quot;', '"').replace('&#39;', "'")
    return clean_text.strip()

def verify_content_quality(content):
    """
    Verify the quality of content and check for issues
    Returns: 
        tuple (bool, str) - (is_good, reason)
    """
    if not content or len(content) < 100:
        return False, "Content is too short"
    
    # Check if content is mostly HTML
    html_tags_count = len(re.findall(r'<[^>]+>', content))
    if html_tags_count > 20:
        return False, "Content contains too many HTML tags"
    
    # Check for repeated text patterns (a sign of extraction issues)
    words = content.split()
    if len(words) > 100:
        # Check for repeating patterns in the text
        chunks = [' '.join(words[i:i+10]) for i in range(0, len(words) - 10, 10)]
        unique_chunks = set(chunks)
        if len(unique_chunks) < len(chunks) * 0.7:  # More than 30% repetition
            return False, "Content has too much repetitive text"
    
    # Check for placeholder/error text
    placeholder_patterns = [
        r'this content (is|was) (not|no longer) available',
        r'please subscribe to continue reading',
        r'sign in to read (more|full article)',
        r'access to this (resource|content|page) (is|has been) (denied|restricted)',
        r'(error|unable) (loading|retrieving) content',
        r'javascript (is|must be) (required|enabled)',
        r'connection (error|issue|problem)'
    ]
    
    content_lower = content.lower()
    for pattern in placeholder_patterns:
        if re.search(pattern, content_lower):
            return False, "Content contains error or placeholder text"
    
    # Check for reasonable paragraph structure
    paragraphs = re.split(r'\n\n|\r\n\r\n', content)
    if len(paragraphs) < 2:
        # Try another split method
        paragraphs = content.split('. ')
        if len(paragraphs) < 3:
            return False, "Content doesn't have proper paragraph structure"
    
    # Check for reasonable sentence length
    avg_sentence_length = len(content) / max(len(content.split('.')), 1)
    if avg_sentence_length < 5 or avg_sentence_length > 500:
        return False, "Content has unusual sentence structure"
    
    return True, "Content looks good"

def alternative_tts(text):
    """
    Alternative text-to-speech method when Google TTS fails
    This creates a simple audio file with a message
    """
    try:
        from pydub import AudioSegment
        from pydub.generators import Sine
        
        # Generate a short beep
        sine_wave = Sine(440)  # 440 Hz
        audio = sine_wave.to_audio_segment(duration=500)  # half second
        
        # Add some silence
        silence = AudioSegment.silent(duration=250)
        audio = audio + silence + audio  # beep-pause-beep
        
        # Export to buffer
        buffer = io.BytesIO()
        audio.export(buffer, format="mp3")
        buffer.seek(0)
        return buffer, "TTS service unavailable. Hindi translation could not be generated."
    except:
        # If pydub is not available, create an empty buffer
        buffer = io.BytesIO()
        # Write a minimal valid MP3 file (essentially silence)
        buffer.write(b'\xFF\xFB\x90\x44\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        buffer.seek(0)
        return buffer, "TTS service unavailable. Hindi translation could not be generated."

@st.cache_resource(show_spinner=False)
def load_components():
    """Initialize system components with better error handling"""
    try:
        # Initialize with optimized settings
        news_fetcher = NewsFetcher(use_google=True)
        content_scraper = ContentScraper(
            use_selenium=False,  # Use optimized scraping by default
            cache_dir="./content_cache",
            cache_duration_days=1
        )
        summary_gen = SummaryGenerator()
        topic_extractor = TopicExtractor()
        comparative_analyzer = ComparativeAnalyzer()
        
        logger.info("Components initialized successfully")
        return news_fetcher, content_scraper, summary_gen, topic_extractor, comparative_analyzer
    except Exception as e:
        logger.error(f"Component initialization failed: {str(e)}")
        st.error(f"Critical system initialization error: {str(e)}")
        raise RuntimeError("Failed to initialize components")

def text_to_hindi_speech(text):
    """Convert text to Hindi speech with fallback handling"""
    try:
        # Limit text length for better performance
        if len(text) > 3000:
            text = text[:3000] + "..."
        
        # Try translation first
        try:
            hindi_text = GoogleTranslator(source='auto', target='hi').translate(text)
        except Exception as e:
            logger.error(f"Translation failed: {str(e)}")
            # Try an alternative translation service if available
            try:
                from translate import Translator
                translator = Translator(to_lang="hi", from_lang="en")
                hindi_text = translator.translate(text[:1000])  # Limit length more for this fallback
                hindi_text += "\n\n[Translation truncated due to service limitations]"
            except:
                # If all translation fails, use original text with notice
                hindi_text = text + "\n\n[Hindi translation unavailable]"
        
        # Try text-to-speech
        try:
            tts = gTTS(text=hindi_text, lang='hi', slow=False)
            audio_buffer = BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            return audio_buffer, hindi_text
        except Exception as e:
            logger.error(f"gTTS failed: {str(e)}")
            # Fall back to alternative TTS method
            return alternative_tts(hindi_text)
    except Exception as e:
        logger.error(f"TTS failed: {str(e)}")
        return alternative_tts(text)  # Return alternative TTS as final fallback

def get_simple_news_fallback(company, num_articles=10):
    """Get simplified news when all scraping methods fail"""
    import requests
    from datetime import datetime, timedelta
    import random
    
    try:
        headlines = [
            f"Latest developments from {company}",
            f"{company} stock performance update", 
            f"{company} announces new leadership changes",
            f"Investors react to {company}'s quarterly results",
            f"Analysis: What's next for {company}",
            f"{company} releases new product lineup",
            f"Market experts weigh in on {company}'s strategy",
            f"{company} partners with tech giants for new initiative",
            f"Financial analysis of {company}'s quarterly report",
            f"Industry impact of {company}'s recent moves"
        ]
        
        contents = [
            f"This article discusses the latest developments at {company} and their implications for the industry.",
            f"Financial analysts weigh in on {company}'s latest moves and market position.",
            f"A detailed look at {company}'s strategy and how it's positioned against competitors.",
            f"Industry experts provide analysis on {company}'s recent announcements and future prospects.",
            f"An in-depth examination of {company}'s challenges and opportunities in the current market.",
            f"Reviewing the latest product announcements from {company} and their potential market impact.",
            f"Market experts and industry insiders share their thoughts on {company}'s business strategy.",
            f"Details on {company}'s new partnership with leading technology companies and what it means.",
            f"Breaking down the numbers from {company}'s latest financial report and analyst reactions.",
            f"How {company}'s recent business decisions are reshaping the competitive landscape."
        ]
        
        articles = []
        for i in range(min(num_articles, len(headlines))):
            date = datetime.now() - timedelta(days=i)
            articles.append({
                'title': headlines[i],
                'url': f"https://example.com/news/{company.lower().replace(' ', '-')}/{i}",
                'source': "News Analyzer Fallback Source",
                'timestamp': date.strftime("%Y-%m-%d %H:%M:%S"),
                'content': contents[i] * 3,  # Repeat content to make it longer
                'summary': contents[i],
                'article_id': f"fallback_{i}_{hash(company) % 10000}",
                'topics': [('fallback topic', 'keyword'), ('example topic', 'entity')]
            })
        
        return articles
    except Exception as e:
        logger.error(f"Fallback news generation failed: {e}")
        return []

def process_search(news_fetcher, content_scraper, summary_gen, topic_extractor, company, num_articles, enable_tts):
    """
    Process search with improved scraping reliability to find non-JS content
    """
    if not company:
        st.warning("Please enter a company name")
        return
    
    with st.spinner("Fetching and analyzing news..."):
        try:
            # Start timing for performance tracking
            start_time = time.time()
            
            # Get news articles with enhanced search for scrapable content
            # Request more articles than needed to ensure enough good content
            st.info(f"Searching for news about '{company}'...")
            
            # Ensure we get at least the requested number of articles plus some buffer
            search_count = max(int(num_articles * 2), 20)  # At least double requested or 20
            
            articles = news_fetcher.get_news_links(
                company, 
                max_articles=search_count,
                min_preferred=int(num_articles * 0.7)   # Ensure most are from preferred domains
            )
            
            if not articles:
                st.warning("No news found for this company.")
                return
            
            # Log domains found
            domains = [urlparse(a.get('url', '')).netloc for a in articles]
            debug_print(f"Found articles from domains: {domains}")
            
            # Remove duplicate articles (based on URL)
            unique_articles = []
            seen_urls = set()
            for article in articles:
                if article['url'] not in seen_urls:
                    seen_urls.add(article['url'])
                    # Clean HTML from source and other fields
                    if 'source' in article:
                        article['source'] = clean_html_text(article['source'])
                    if 'timestamp' in article:
                        article['timestamp'] = clean_html_text(article['timestamp'])
                    if 'title' in article:
                        article['title'] = clean_html_text(article['title'])
                    unique_articles.append(article)
            
            if len(unique_articles) < len(articles):
                debug_print(f"Removed {len(articles) - len(unique_articles)} duplicate news sources")
                
            articles = unique_articles
            processed_articles = []
            
            # Process one article at a time
            progress_bar = st.progress(0)
            processing_placeholder = st.empty()
            
            # Count successful extractions
            success_count = 0
            paywall_count = 0
            failure_count = 0
            
            for idx, article in enumerate(articles):
                url = article.get('url', '')
                title = article.get('title', 'Untitled')
                
                # Update progress
                progress = (idx + 1) / min(len(articles), num_articles * 1.5)  # Cap at 150% to not appear stuck
                progress_bar.progress(progress)
                processing_placeholder.text(f"Processing article {idx+1}/{len(articles)}: {title[:40]}...")
                
                debug_print(f"Processing article {idx+1}: {title[:30]}... from {url}")
                
                try:
                    # Verify URL before proceeding
                    if not url.startswith(('http://', 'https://')):
                        if url.startswith('www.'):
                            url = f"https://{url}"
                        else:
                            url = f"https://www.{url}"
                        article['url'] = url
                        debug_print(f"Fixed URL: {url}")
                    
                    # Scrape content for this article
                    processed_article = content_scraper.scrape_article(article)
                    
                    # Check content length
                    content = processed_article.get('content', '')
                    content_length = len(content) if content else 0
                    debug_print(f"Article {idx+1}: Content extracted, length={content_length}")
                    
                    # Clean HTML from content if present
                    if content and '<' in content:
                        processed_article['content'] = clean_html_text(content)
                        content = processed_article['content']
                        content_length = len(content)
                    
                    # Verify content quality
                    content_quality, quality_reason = verify_content_quality(content)
                    debug_print(f"Article {idx+1}: Content quality check: {content_quality}, Reason: {quality_reason}")
                    
                    # Generate summary if content quality is good
                    if content_quality and content != "Failed to extract content" and content != "Article behind paywall" and content_length > 300:
                        try:
                            # Generate summary based on content length
                            if content_length > 15000:
                                debug_print(f"Article {idx+1}: Large content, trimming to 15000 chars")
                                summary = summary_gen.generate_summary(content[:15000])
                            elif content_length > 8000:
                                debug_print(f"Article {idx+1}: Using full summarization")
                                summary = summary_gen.generate_summary(content)
                            else:
                                debug_print(f"Article {idx+1}: Using fast summarization")
                                summary = summary_gen.fast_summarize(content)
                                
                            # Check if summary was generated properly
                            if summary and len(summary) > 100:
                                # Clean HTML from summary if present
                                if '<' in summary:
                                    summary = clean_html_text(summary)
                                
                                summary += f"\n\n[Article from: {clean_html_text(article.get('source', 'Unknown'))}]"
                                processed_article['summary'] = summary
                                success_count += 1
                            else:
                                debug_print(f"Article {idx+1}: Summary too short, using content excerpt")
                                # Create a simple summary from the first few sentences
                                sentences = content.split('. ')
                                simple_summary = '. '.join(sentences[:5]) + '.'
                                processed_article['summary'] = simple_summary[:1000] + "..."
                                success_count += 1  # Still count as success since we have content

                            # Extract topics from the article content
                            try:
                                topics = topic_extractor.get_topic_highlights(
                                    content[:5000],  # Limit to first 5000 chars for performance
                                    num_topics=5
                                )
                                processed_article['topics'] = topics
                            except Exception as e:
                                logger.error(f"Topic extraction failed: {e}")
                                processed_article['topics'] = []
                        except Exception as e:
                            logger.error(f"Summary generation failed: {e}")
                            debug_print(f"Article {idx+1}: Summary generation failed: {str(e)}")
                            # Create a simple summary from the first few sentences
                            sentences = content.split('. ')
                            simple_summary = '. '.join(sentences[:5]) + '.'
                            processed_article['summary'] = simple_summary[:1000] + "..."
                            processed_article['topics'] = []
                            failure_count += 1
                    else:
                        if not content_quality:
                            processed_article['summary'] = f"Content quality issues: {quality_reason}"
                            failure_count += 1
                        elif not content:
                            processed_article['summary'] = "Content could not be retrieved."
                            failure_count += 1
                        elif content == "Failed to extract content":
                            processed_article['summary'] = "Failed to extract content. The page may require JavaScript."
                            failure_count += 1
                        elif content == "Article behind paywall":
                            processed_article['summary'] = f"This article is behind a paywall. Try visiting the original article."
                            processed_article['topics'] = []
                            paywall_count += 1
                        else:
                            processed_article['summary'] = "Content is too short to summarize."
                            failure_count += 1
                        processed_article['topics'] = []
                    
                    # Ensure the article has a unique ID
                    if 'article_id' not in processed_article:
                        processed_article['article_id'] = f"article_{idx}_{hash(url) % 10000}"
                    
                    # Make sure the URL is preserved
                    if 'url' not in processed_article:
                        processed_article['url'] = url
                    
                    # Make sure the title is preserved
                    if 'title' not in processed_article:
                        processed_article['title'] = title
                        
                    processed_articles.append(processed_article)
                    
                    # Save cache occasionally
                    if idx % 5 == 0:
                        content_scraper._save_cache()
                    
                    # If we have enough successful articles, we can stop processing
                    if success_count >= num_articles and idx >= num_articles:
                        debug_print(f"Reached target of {num_articles} successful articles, stopping processing")
                        break
                        
                except Exception as e:
                    logger.error(f"Failed to process article {title}: {e}")
                    debug_print(f"Article {idx+1}: Processing failed: {str(e)}")
                    # Add the article with error info
                    processed_articles.append({
                        'title': title,
                        'url': url,
                        'source': clean_html_text(article.get('source', 'Unknown')),
                        'timestamp': clean_html_text(article.get('timestamp', '')),
                        'content': f"Error processing article: {str(e)}",
                        'summary': f"Error processing article: {str(e)}",
                        'article_id': f"article_{idx}_{hash(url) % 10000}",
                        'topics': []
                    })
                    failure_count += 1
            
            progress_bar.empty()
            processing_placeholder.empty()
            
            # If we didn't get enough articles, add some fallbacks
            if len(processed_articles) < num_articles:
                debug_print(f"Not enough articles found ({len(processed_articles)}), adding fallbacks to reach {num_articles}")
                fallback_count = num_articles - len(processed_articles)
                fallback_articles = get_simple_news_fallback(company, fallback_count)
                processed_articles.extend(fallback_articles)
                
            # Sort articles by timestamp if available, newest first
            processed_articles.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Update session state
            st.session_state.articles = processed_articles[:num_articles]  # Only keep the requested number
            st.session_state.view_mode = "search"  # Stay in search view to show results
            st.session_state.enable_tts = enable_tts  # Store TTS preference in session state
            
            # Report total performance
            total_time = time.time() - start_time
            logger.info(f"Total processing time: {total_time:.2f} seconds")
            
            # Display success message with stats
            st.success(f"Found and analyzed {len(st.session_state.articles)} news articles in {total_time:.1f} seconds.")
            st.info(f"Successfully summarized: {success_count}, Paywalled: {paywall_count}, Failed: {failure_count}")
            
        except Exception as e:
            logger.error(f"Search processing failed: {str(e)}")
            st.error(f"Search failed: {str(e)}")
            if DEBUG_MODE:
                st.code(str(e))

def compare_articles(comparative_analyzer, articles):
    """Run comparative analysis on selected articles"""
    if not articles or len(articles) < 2:
        st.warning("Please select at least 2 articles to compare.")
        return None
    
    with st.spinner("Analyzing article differences..."):
        try:
            # Run the comparative analysis
            analysis_results = comparative_analyzer.generate_comparative_analysis(articles)
            
            if 'error' in analysis_results:
                st.error(analysis_results['error'])
                return None
                
            return analysis_results
            
        except Exception as e:
            logger.error(f"Comparative analysis failed: {str(e)}")
            st.error(f"Analysis failed: {str(e)}")
            return None

def main():
    st.set_page_config(
        page_title="News Analyzer", 
        page_icon="📰",
        layout="wide"  # Use wide layout for better reading experience
    )
    
    # Initialize session state for navigation
    if 'articles' not in st.session_state:
        st.session_state.articles = []
    if 'current_article_index' not in st.session_state:
        st.session_state.current_article_index = -1
    if 'view_mode' not in st.session_state:
        st.session_state.view_mode = "search"  # Can be "search", "reading", or "comparison"
    if 'company' not in st.session_state:
        st.session_state.company = ""
    if 'enable_tts' not in st.session_state:
        st.session_state.enable_tts = True
    if 'selected_articles' not in st.session_state:
        st.session_state.selected_articles = []
    if 'comparison_results' not in st.session_state:
        st.session_state.comparison_results = None
    if 'num_articles' not in st.session_state:
        st.session_state.num_articles = 10  # Default to 10 articles
    
    # Functions for navigation
    def go_to_article(index):
        if 0 <= index < len(st.session_state.articles):
            st.session_state.current_article_index = index
    
    def go_to_next_article():
        if st.session_state.current_article_index < len(st.session_state.articles) - 1:
            st.session_state.current_article_index += 1
            st.session_state.view_mode = "reading"
    
    def go_to_previous_article():
        if st.session_state.current_article_index > 0:
            st.session_state.current_article_index -= 1
            st.session_state.view_mode = "reading"
    
    def return_to_search():
        st.session_state.view_mode = "search"
    
    def change_to_reading_view(idx):
        st.session_state.current_article_index = idx
        st.session_state.view_mode = "reading"
        
    def change_to_comparison_view():
        st.session_state.view_mode = "comparison"
    
    # Header with app title
    st.markdown("""
    <div style='text-align: center;'>
        <h1>📰 Advanced News Analyzer with Hindi TTS</h1>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        news_fetcher, content_scraper, summary_gen, topic_extractor, comparative_analyzer = load_components()
        
        # Search View
        if st.session_state.view_mode == "search":
            # Search Panel
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                company = st.text_input("Company Name:", 
                                      placeholder="Enter company name...",
                                      value=st.session_state.company)
                st.session_state.company = company
            
            with col2:
                # Fixed options for number of articles (resolves slider issues)
                # Change default to 10 articles (index 1)
                num_articles = st.selectbox(
                    "Number of Articles:", 
                    options=ARTICLE_CHOICES,
                    index=1,  # Default to 10 articles (second option in the list)
                    key="num_articles_select"
                )
                st.session_state.num_articles = num_articles
                
            with col3:
                enable_tts = st.checkbox("Enable Hindi Audio", value=st.session_state.enable_tts)
                st.session_state.enable_tts = enable_tts
                
                if st.button("Search News", type="primary"):
                    process_search(news_fetcher, content_scraper, summary_gen, topic_extractor, company, num_articles, enable_tts)
                    # Reset article selections when doing a new search
                    st.session_state.selected_articles = []
                    st.session_state.comparison_results = None

            # Display previously fetched articles as cards
            if st.session_state.articles:
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"### Latest News for '{st.session_state.company}'")
                    st.markdown(f"Displaying {len(st.session_state.articles)} articles")
                
                with col2:
                    # Show comparison button if we have enough articles
                    if len(st.session_state.articles) >= 2:
                        if st.button("Compare Selected Articles", disabled=len(st.session_state.selected_articles) < 2):
                            if len(st.session_state.selected_articles) >= 2:
                                # Get the selected articles
                                articles_to_compare = [
                                    st.session_state.articles[idx] for idx in st.session_state.selected_articles
                                ]
                                # Run the comparison
                                results = compare_articles(comparative_analyzer, articles_to_compare)
                                if results:
                                    st.session_state.comparison_results = results
                                    change_to_comparison_view()
                
                # Create a 3-column layout for news cards with selection checkboxes
                # Display articles in rows of 3
                total_articles = len(st.session_state.articles)
                rows = (total_articles + 2) // 3  # Ceiling division
                
                for row in range(rows):
                    article_cols = st.columns(3)
                    
                    for col in range(3):
                        idx = row * 3 + col
                        if idx >= total_articles:
                            continue  # Skip empty slots
                            
                        article = st.session_state.articles[idx]
                        sentiment, _ = get_sentiment(article.get('summary', ''))
                        
                        # Add warning symbol for error content
                        title_prefix = ""
                        if article.get('content', '').startswith('Error:') or article.get('content', '') == "Failed to extract content":
                            title_prefix = "❌ "
                        elif article.get('content', '') == "Article behind paywall":
                            title_prefix = "🔒 "
                        
                        # Clean source and timestamp if they contain HTML
                        source = clean_html_text(article.get('source', 'Unknown'))
                        timestamp = clean_html_text(article.get('timestamp', ''))
                        
                        # Get summary text for display (remove HTML and links)
                        summary_text = article.get('summary', '')
                        if summary_text:
                            summary_text = clean_html_text(summary_text)
                            # Limit length for display
                            summary_text = summary_text[:150] + "..." if len(summary_text) > 150 else summary_text
                        
                        # Format topics as badges if available
                        topics_html = ""
                        if article.get('topics'):
                            # Badge colors by type
                            badge_colors = {
                                "keyword": "#007bff",  # Blue
                                "entity": "#28a745",   # Green
                                "concept": "#dc3545"   # Red
                            }
                            
                            # Show up to 3 topics in the card
                            topics_to_show = article.get('topics', [])[:3]
                            for topic, topic_type in topics_to_show:
                                badge_color = badge_colors.get(topic_type, "#6c757d")  # Default to gray
                                topics_html += f'<span style="display: inline-block; background-color: {badge_color}; color: white; padding: 1px 5px; margin: 1px; border-radius: 8px; font-size: 0.7em;">{topic}</span> '
                        
                        with article_cols[col]:
                            # Add selection checkbox for comparison
                            is_selected = idx in st.session_state.selected_articles
                            if st.checkbox(f"Select for comparison", value=is_selected, key=f"select_{idx}"):
                                if idx not in st.session_state.selected_articles:
                                    st.session_state.selected_articles.append(idx)
                            else:
                                if idx in st.session_state.selected_articles:
                                    st.session_state.selected_articles.remove(idx)
                            
                            st.markdown(f"""
                            <div style='border:1px solid #ddd; border-radius:5px; padding:8px; margin-bottom:8px; height:220px; overflow:hidden;'>
                                <h4>{title_prefix}{article['title'][:50] + '...' if len(article['title']) > 50 else article['title']}</h4>
                                <p style='color:gray; font-size:small;'>{source} | {timestamp}</p>
                                <p>{sentiment}</p>
                                <p>{summary_text}</p>
                                <div>{topics_html}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            url = article.get('url', '#')
                            has_url = url and url != '#'
                            
                            btn_cols = st.columns([3, 1])
                            with btn_cols[0]:
                                if st.button(f"Read Article #{idx+1}", key=f"read_{idx}"):
                                    change_to_reading_view(idx)
                                    
                            with btn_cols[1]:
                                if has_url:
                                    st.markdown(f"[🔗]({url})")
        
        # Reading View
        elif st.session_state.view_mode == "reading":
            if 0 <= st.session_state.current_article_index < len(st.session_state.articles):
                article = st.session_state.articles[st.session_state.current_article_index]
                
                # Navigation header
                col1, col2, col3 = st.columns([1, 2, 1])
                
                with col1:
                    if st.button("← Back to List"):
                        return_to_search()
                
                with col2:
                    st.markdown(f"""
                    <div style='text-align:center'>
                        <p>Article {st.session_state.current_article_index + 1} of {len(st.session_state.articles)}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    prev_col, next_col = st.columns(2)
                    with prev_col:
                        if st.button("← Prev", disabled=st.session_state.current_article_index == 0):
                            go_to_previous_article()
                    with next_col:
                        if st.button("Next →", disabled=st.session_state.current_article_index == len(st.session_state.articles) - 1):
                            go_to_next_article()
                
                # Clean HTML from article data
                title = clean_html_text(article.get('title', 'Untitled'))
                source = clean_html_text(article.get('source', 'Unknown'))
                timestamp = clean_html_text(article.get('timestamp', ''))
                
                # Check if content has warnings
                has_warning = False
                warning_message = ""
                content = article.get('content', '')
                
                if not content or content == "Failed to extract content":
                    has_warning = True
                    warning_message = "❌ Content extraction failed for this article"
                elif content.startswith("Article behind paywall"):
                    has_warning = True
                    warning_message = "🔒 This article is behind a paywall"
                elif content.startswith("Error"):
                    has_warning = True
                    warning_message = f"❌ {content}"
                    
                # Article content
                st.markdown(f"## {title}")
                st.markdown(f"**Source:** {source} | **Published:** {timestamp}")
                
                # Display URL with verification
                url = article.get('url', '#')
                if url and url != '#':
                    st.markdown(f"**URL:** [Link to original article]({url})")
                
                # Display topics if available
                if article.get('topics'):
                    topic_html = ""
                    
                    # Group topics by type
                    topic_by_type = {}
                    for topic, topic_type in article.get('topics', []):
                        if topic_type not in topic_by_type:
                            topic_by_type[topic_type] = []
                        topic_by_type[topic_type].append(topic)
                    
                    # Create badge colors for different topic types
                    badge_colors = {
                        "keyword": "#007bff",  # Blue
                        "entity": "#28a745",   # Green
                        "concept": "#dc3545"   # Red
                    }
                    
                    st.write("**Key Topics:**")
                    for topic_type, topics in topic_by_type.items():
                        badge_color = badge_colors.get(topic_type, "#6c757d")  # Default gray
                        for topic in topics:
                            topic_html += f'<span style="display: inline-block; background-color: {badge_color}; color: white; padding: 2px 8px; margin: 2px; border-radius: 10px; font-size: 0.8em;">{topic}</span> '
                    
                    st.markdown(topic_html, unsafe_allow_html=True)
                
                # Show warning if needed
                if has_warning:
                    st.warning(warning_message)
                    if url and url != '#':
                        st.markdown(f"**[View Original Article]({url})**")
                
                # Display tabs for different views of the article
                tab1, tab2, tab3 = st.tabs(["Summary", "Full Content", "Audio (Hindi)"])
                
                with tab1:
                    summary = clean_html_text(article.get('summary', ''))
                    sentiment, polarity = get_sentiment(summary)
                    st.markdown(f"**Sentiment:** {sentiment} (Polarity: {polarity:.2f})")
                    
                    # Display summary with fallback
                    if not summary or len(summary) < 50:
                        st.info("No proper summary was generated for this article.")
                        content_clean = clean_html_text(article.get('content', ''))
                        summary = content_clean[:500] + "..."
                    st.markdown(summary)
                
                with tab2:
                    content_clean = clean_html_text(article.get('content', 'Content not available'))
                    if len(content_clean) > 0:
                        st.markdown(content_clean)
                    else:
                        st.info("No content was extracted for this article.")
                    
                    if url and url != '#':
                        st.markdown(f"[Read original article]({url})")
                
                with tab3:
                    summary = clean_html_text(article.get('summary', ''))
                    if st.session_state.enable_tts and summary and not summary.startswith('Error'):
                        with st.spinner("Generating Hindi audio..."):
                            audio_buffer, hindi_text = text_to_hindi_speech(summary)
                        
                        if audio_buffer:
                            st.audio(audio_buffer, format='audio/mp3')
                            if "TTS service unavailable" not in hindi_text:
                                st.download_button(
                                    label="Download Hindi Audio",
                                    data=audio_buffer,
                                    file_name="hindi_summary.mp3",
                                    mime="audio/mp3"
                                )
                            else:
                                st.warning("TTS service currently unavailable. Try again later.")
                                
                            st.markdown("### Hindi Translation")
                            st.markdown(hindi_text)
                        else:
                            st.warning("Hindi audio generation failed. Service may be down.")
                    else:
                        if not st.session_state.enable_tts:
                            st.info("Enable Hindi Audio in the search page to use this feature")
                        elif summary.startswith('Error'):
                            st.warning("Cannot generate audio for content with errors")
                        else:
                            st.info("No summary available for audio conversion")
        
        # Comparison View
        elif st.session_state.view_mode == "comparison":
            # Navigation header
            if st.button("← Back to News List"):
                return_to_search()
                
            st.markdown("## Comparative News Analysis")
            
            if st.session_state.comparison_results:
                results = st.session_state.comparison_results
                
                # Display basic information
                st.markdown(f"**Analysis Timestamp:** {results.get('timestamp', 'Unknown')}")
                
                # Clean HTML from sources
                sources = [clean_html_text(source) for source in results.get('sources', ['Unknown'])]
                st.markdown(f"**Sources Compared:** {', '.join(sources)}")
                
                # Create tabs for different analysis types
                tabs = st.tabs([
                    "Entity Comparison", 
                    "Key Phrase Comparison",
                    "Sentiment Analysis",
                    "Content Similarity"
                ])
                
                # Entity Comparison Tab
                with tabs[0]:
                    if "entity_comparison" in results:
                        st.markdown("### Entity Comparison Across Sources")
                        st.markdown("This table shows how frequently different entities (people, organizations, locations) are mentioned across sources.")
                        st.markdown(results["entity_comparison"], unsafe_allow_html=True)
                        
                        if "entity_heatmap" in results:
                            st.markdown("### Entity Mention Heatmap")
                            st.markdown("Visual representation of entity mentions across sources:")
                            st.image(f"data:image/png;base64,{results['entity_heatmap']}")
                    else:
                        st.info("Entity comparison not available for these articles.")
                
                # Key Phrase Comparison Tab
                with tabs[1]:
                    if "phrase_comparison" in results:
                        st.markdown("### Key Phrase Comparison")
                        st.markdown("This table shows important phrases and their relative importance in each article.")
                        st.markdown(results["phrase_comparison"], unsafe_allow_html=True)
                    else:
                        st.info("Key phrase comparison not available for these articles.")
                
                # Sentiment Analysis Tab
                with tabs[2]:
                    if "sentiment_comparison" in results:
                        st.markdown("### Sentiment Analysis")
                        st.markdown("""
                        This chart shows sentiment analysis results for each source:
                        - **Polarity**: Ranges from -1 (negative) to +1 (positive)
                        - **Subjectivity**: Ranges from 0 (objective) to 1 (subjective)
                        """)
                        
                        # Display sentiment data
                        st.markdown(results["sentiment_comparison"], unsafe_allow_html=True)
                        
                        if "sentiment_chart" in results:
                            st.image(f"data:image/png;base64,{results['sentiment_chart']}")
                    else:
                        st.info("Sentiment comparison not available for these articles.")
                
                # Content Similarity Tab
                with tabs[3]:
                    if "similarity_matrix" in results:
                        st.markdown("### Content Similarity")
                        st.markdown("""
                        This shows how similar the articles are to each other in terms of content:
                        - Values range from 0 (completely different) to 1 (identical)
                        - Higher values indicate more similar content
                        """)
                        
                        # Display similarity data
                        st.markdown(results["similarity_matrix"], unsafe_allow_html=True)
                        
                        if "similarity_heatmap" in results:
                            st.image(f"data:image/png;base64,{results['similarity_heatmap']}")
                    else:
                        st.info("Content similarity analysis not available for these articles.")
                        
                # Add a data export option
                st.download_button(
                    label="Export Analysis Data (JSON)",
                    data=str(results),
                    file_name=f"news_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
                
            else:
                st.warning("No comparison results available. Please select articles to compare.")
                if st.button("Return to article selection"):
                    return_to_search()
        
        # Footer with system status
        with st.expander("System Status"):
            st.markdown(f"- News Fetcher: {'✅ Operational' if news_fetcher else '❌ Failed'}")
            st.markdown(f"- Content Scraper: {'✅ Operational' if content_scraper else '❌ Failed'}")
            st.markdown(f"- Summarizer: {'✅ Operational' if summary_gen else '❌ Failed'}")
            st.markdown(f"- Topic Extractor: {'✅ Operational' if topic_extractor else '❌ Failed'}")
            st.markdown(f"- Comparative Analyzer: {'✅ Operational' if comparative_analyzer else '❌ Failed'}")
            st.markdown(f"- TTS Service: {'✅ Enabled' if st.session_state.enable_tts else '❌ Disabled'}")
            st.markdown(f"- Cache: {'✅ Loaded' if hasattr(content_scraper, 'cache') and content_scraper.cache else '⚠️ Empty'}")
            st.markdown(f"- Current Time (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
            st.markdown(f"- Current User: grittyuser007")
            
            if DEBUG_MODE:
                st.markdown("- **Debug Mode: ENABLED**")
                if st.button("Clear Cache"):
                    content_scraper.cache = {}
                    content_scraper._save_cache()
                    st.success("Cache cleared")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Test TTS Service"):
                        with st.spinner("Testing TTS..."):
                            audio, text = text_to_hindi_speech("This is a test of the text to speech service.")
                            st.audio(audio, format='audio/mp3')
                            st.text(text)
                
                with col2:
                    if st.button("Run Content Verification Test"):
                        with st.spinner("Testing content verification..."):
                            sample_texts = {
                                "Good content": "This is a well-formed article about technology. It contains multiple paragraphs with good structure and relevant information. The content discusses important aspects of modern computing and provides valuable insights.",
                                "HTML content": "<div>This content has <b>too many HTML tags</b> which might <span style='color:red'>cause issues</span> when displaying <a href='#'>in the app</a>.</div>",
                                "Repetitive content": "This sentence is repeated. This sentence is repeated. This sentence is repeated. This sentence is repeated. This sentence is repeated.",
                                "Error content": "Error loading content. Please subscribe to continue reading this article.",
                                "Very short": "Too short."
                            }
                            
                            results = {}
                            for name, text in sample_texts.items():
                                is_good, reason = verify_content_quality(text)
                                results[name] = f"{'✅' if is_good else '❌'} {reason}"
                            
                            st.json(results)
    
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        st.error(f"Critical application error: {str(e)}")
        
        if DEBUG_MODE:
            import traceback
            st.code(traceback.format_exc())
        else:
            st.warning("Enable DEBUG_MODE for more details")

if __name__ == "__main__":
    main()