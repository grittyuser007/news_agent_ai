"""
Advanced News Analyzer with Hindi TTS, Topic Extraction, and Comparative Analysis
Optimized for performance with a user-friendly UI
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
from datetime import datetime, timedelta
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment configuration
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["PYTHONWARNINGS"] = "ignore"

# App version
APP_VERSION = "2.0.0"

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

@st.cache_resource(show_spinner=False)
def load_components():
    """Initialize system components with better error handling and performance optimization"""
    # Get performance mode from session state
    performance_mode = st.session_state.get('performance_mode', 'fast')
    
    try:
        # Configure components based on performance mode
        use_selenium = performance_mode == 'thorough'
        use_heavy_models = performance_mode != 'fast'
        
        news_fetcher = NewsFetcher(use_google=True)
        
        content_scraper = ContentScraper(
            use_selenium=use_selenium,  # Only use Selenium in thorough mode
            cache_dir="./content_cache",
            cache_duration_days=1
        )
        
        summary_gen = SummaryGenerator()
        topic_extractor = TopicExtractor(use_keybert=use_heavy_models)
        
        # Only initialize comparative analyzer when needed (it's heavy)
        comparative_analyzer = ComparativeAnalyzer(use_spacy=use_heavy_models)
        
        logger.info(f"Components initialized successfully in {performance_mode} mode")
        return news_fetcher, content_scraper, summary_gen, topic_extractor, comparative_analyzer
    except Exception as e:
        logger.error(f"Component initialization failed: {str(e)}")
        st.error("Critical system initialization error. Check logs for details.")
        raise RuntimeError("Failed to initialize components")

def text_to_hindi_speech(text):
    """Convert text to Hindi speech with fallback handling"""
    try:
        # Limit text length for performance
        if len(text) > 3000:
            text = text[:3000] + "..."
            
        # Translate to Hindi
        hindi_text = GoogleTranslator(source='auto', target='hi').translate(text)
        
        # Generate audio
        tts = gTTS(text=hindi_text, lang='hi', slow=False)
        audio_buffer = BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        return audio_buffer, hindi_text
    except Exception as e:
        logger.error(f"TTS failed: {str(e)}")
        return None, text  # Return original text if translation fails

def get_simple_news_fallback(company, num_articles=5):
    """Get simplified news when all scraping methods fail"""
    import requests
    import random
    
    try:
        headlines = [
            f"Latest developments from {company}",
            f"{company} stock performance update", 
            f"{company} announces new leadership changes",
            f"Investors react to {company}'s quarterly results",
            f"Analysis: What's next for {company}"
        ]
        
        contents = [
            f"This article discusses the latest developments at {company} and their implications for the industry.",
            f"Financial analysts weigh in on {company}'s latest moves and market position.",
            f"A detailed look at {company}'s strategy and how it's positioned against competitors.",
            f"Industry experts provide analysis on {company}'s recent announcements and future prospects.",
            f"An in-depth examination of {company}'s challenges and opportunities in the current market."
        ]
        
        articles = []
        for i in range(min(num_articles, 5)):
            date = datetime.now() - timedelta(days=i)
            articles.append({
                'title': headlines[i % len(headlines)],
                'url': f"https://example.com/news/{company.lower().replace(' ', '-')}/{i}",
                'source': "News Analyzer Fallback Source",
                'timestamp': date.strftime("%Y-%m-%d %H:%M:%S"),
                'content': contents[i % len(contents)] * 3,  # Repeat content to make it longer
                'summary': contents[i % len(contents)],
                'article_id': f"fallback_{i}_{hash(company) % 10000}",
                'topics': [('fallback topic', 'keyword'), ('example topic', 'entity')]
            })
        
        return articles
    except Exception as e:
        logger.error(f"Fallback news generation failed: {e}")
        return []

def process_search(news_fetcher, content_scraper, summary_gen, topic_extractor, company, num_articles, enable_tts):
    """
    Process search and update session state with results
    Performance-optimized with progressive loading
    """
    if not company:
        st.warning("Please enter a company name")
        return
    
    with st.spinner("Fetching and analyzing news..."):
        try:
            # Start timing for performance tracking
            start_time = time.time()
            
            # Get news articles
            articles = news_fetcher.get_news_links(company, num_articles)
            
            if not articles:
                st.warning("No news found for this company.")
                return
            
            # Remove duplicate articles (based on URL)
            unique_articles = []
            seen_urls = set()
            for article in articles:
                if article['url'] not in seen_urls:
                    seen_urls.add(article['url'])
                    unique_articles.append(article)
            
            if len(unique_articles) < len(articles):
                st.info(f"Removed {len(articles) - len(unique_articles)} duplicate news sources")
                
            articles = unique_articles
            processed_articles = []
            
            # Show progressive loading UI
            progress_bar = st.progress(0)
            loading_container = st.container()
            
            # Create a placeholder for previewing articles as they load
            preview_container = st.empty()
            preview_shown = False
            
            # Process articles in order of expected difficulty (simplest domains first)
            def sort_key(article):
                url = article['url']
                domain = urlparse(url).netloc
                # Simple news sites first (usually faster to process)
                simple_domains = ['reuters.com', 'apnews.com', 'bbc.com', 'npr.org']
                complex_domains = ['nytimes.com', 'wsj.com', 'medium.com', 'bloomberg.com']
                
                if any(d in domain for d in simple_domains):
                    return 0
                elif any(d in domain for d in complex_domains):
                    return 2
                return 1
            
            # Sort articles by domain complexity for more balanced processing
            articles.sort(key=sort_key)
            
            # Track success and failure counts
            success_count = 0
            failure_count = 0
            paywall_count = 0
            
            for idx, article in enumerate(articles):
                url = article['url']
                title = article.get('title', 'Untitled')
                
                # Update progress
                progress = (idx + 1) / len(articles)
                progress_bar.progress(progress)
                
                # Alternate message style for visual interest
                if idx % 2 == 0:
                    loading_container.info(f"Processing article {idx+1}/{len(articles)}: {title[:40]}...")
                else:
                    loading_container.success(f"Processing article {idx+1}/{len(articles)}: {title[:40]}...")
                
                logger.info(f"Processing article {idx+1}: {title[:30]}... from {url}")
                
                try:
                    # Scrape content for this article
                    processed_article = content_scraper.scrape_article(article)
                    
                    # Generate summary if content was successfully retrieved
                    if processed_article.get('content') and processed_article.get('content') != "Failed to extract content" and len(processed_article.get('content', '')) > 300:
                        try:
                            # Use appropriate summarization method based on content length
                            if len(processed_article['content']) > 8000:
                                summary = summary_gen.generate_summary(processed_article['content'][:8000])
                            else:
                                # Use faster summarization method
                                summary = summary_gen.fast_summarize(processed_article['content'])
                                
                            summary += f"\n\n[Article from: {article.get('source', 'Unknown')}]"
                            processed_article['summary'] = summary

                            # Extract topics from the article content
                            try:
                                # Use lite mode for topic extraction when in fast mode
                                if st.session_state.get('performance_mode') == 'fast':
                                    # Simple topic extraction (just keywords)
                                    topics = topic_extractor.extract_simple_keywords(
                                        processed_article['content'], 
                                        num_topics=3
                                    )
                                    processed_article['topics'] = [(topic, "keyword") for topic in topics]
                                else:
                                    # Full topic extraction
                                    topics = topic_extractor.get_topic_highlights(
                                        processed_article['content'], 
                                        num_topics=5
                                    )
                                    processed_article['topics'] = topics
                            except Exception as e:
                                logger.error(f"Topic extraction failed: {e}")
                                processed_article['topics'] = []

                            success_count += 1
                            
                        except Exception as e:
                            logger.error(f"Summary generation failed: {e}")
                            processed_article['summary'] = processed_article['content'][:500] + "..."
                            processed_article['topics'] = []
                            failure_count += 1
                    else:
                        if not processed_article.get('content'):
                            processed_article['summary'] = "Content could not be retrieved."
                            failure_count += 1
                        elif processed_article.get('content') == "Article behind paywall":
                            processed_article['summary'] = f"{processed_article.get('content')}. Try visiting the original article."
                            paywall_count += 1
                        else:
                            processed_article['summary'] = "Content is too short to summarize."
                            failure_count += 1
                        processed_article['topics'] = []
                    
                    # Make sure article has a unique ID
                    if 'article_id' not in processed_article:
                        processed_article['article_id'] = f"article_{idx}_{hash(url) % 10000}"
                        
                    processed_articles.append(processed_article)
                    
                    # Save cache occasionally
                    if idx % 5 == 0:
                        content_scraper._save_cache()
                    
                    # Preview the results as we process (after a few articles are done)
                    if idx >= 2 and not preview_shown:
                        with preview_container.container():
                            st.success("✅ First few articles processed! Here's a preview:")
                            
                            # Show first article preview
                            if processed_articles and len(processed_articles) > 0:
                                first_article = processed_articles[0]
                                st.markdown(f"### {first_article['title']}")
                                st.markdown(f"**Source:** {first_article.get('source', 'Unknown')}")
                                st.markdown(first_article.get('summary', '')[:150] + "...")
                            
                            st.info("📊 Continue processing remaining articles...")
                        preview_shown = True
                        
                except Exception as e:
                    logger.error(f"Failed to process article {title}: {e}")
                    # Add the article with error info
                    processed_articles.append({
                        'title': title,
                        'url': url,
                        'source': article.get('source', 'Unknown'),
                        'timestamp': article.get('timestamp', ''),
                        'content': f"Error processing article: {str(e)}",
                        'summary': f"Error processing article: {str(e)}",
                        'article_id': f"article_{idx}_{hash(url) % 10000}",
                        'topics': []
                    })
                    failure_count += 1
            
            # Clear progress indicators
            progress_bar.empty()
            loading_container.empty()
            preview_container.empty()
            
            # Update session state
            st.session_state.articles = processed_articles
            st.session_state.view_mode = "search"  # Stay in search view to show results
            st.session_state.enable_tts = enable_tts  # Store TTS preference in session state
            
            # Report total performance
            total_time = time.time() - start_time
            logger.info(f"Total processing time: {total_time:.2f} seconds")
            
            # Show success message with stats
            st.success(f"✅ Found and analyzed {len(processed_articles)} news articles in {total_time:.1f} seconds.")
            
            # Show processing stats
            stats_cols = st.columns(4)
            with stats_cols[0]:
                st.metric("Articles Processed", len(processed_articles))
            with stats_cols[1]:
                st.metric("Successfully Extracted", success_count)
            with stats_cols[2]:
                st.metric("Paywalled Articles", paywall_count)
            with stats_cols[3]:
                st.metric("Processing Time", f"{total_time:.1f}s")
            
        except Exception as e:
            logger.error(f"Search processing failed: {str(e)}")
            st.error(f"Search failed: {str(e)}")

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
    # Set page config with a larger layout for better readability
    st.set_page_config(
        page_title="News Analyzer Pro", 
        page_icon="📰",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state variables
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
    if 'performance_mode' not in st.session_state:
        st.session_state.performance_mode = "fast"  # Default to fast mode
    if 'display_mode' not in st.session_state:
        st.session_state.display_mode = "cards"  # Can be "cards" or "compact"
    if 'dark_mode' not in st.session_state:
        st.session_state.dark_mode = False
    
    # Apply dark mode if enabled
    if st.session_state.dark_mode:
        st.markdown("""
        <style>
            .stApp {
                background-color: #121212;
                color: #e0e0e0;
            }
            h1, h2, h3, h4, h5, h6 {
                color: #e0e0e0;
            }
            .stButton button {
                background-color: #333333;
                color: #e0e0e0;
            }
            .stTextInput input {
                background-color: #333333;
                color: #e0e0e0;
            }
            .stSelectbox div[data-baseweb="select"] {
                background-color: #333333;
            }
            .article-card {
                background-color: #1e1e1e;
                border: 1px solid #333333;
            }
            .article-title {
                color: #ffffff;
            }
            .article-source {
                color: #aaaaaa;
            }
        </style>
        """, unsafe_allow_html=True)

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
    
    # Sidebar for app controls and settings
    with st.sidebar:
        st.image("https://i.imgur.com/VFfuX0p.png", width=80)  # Example logo - replace with your own
        st.title("News Analyzer Pro")
        st.caption(f"Version {APP_VERSION} | {datetime.now().strftime('%Y-%m-%d')}")
        
        st.subheader("⚙️ Settings")
        
        # Performance mode selection
        performance_mode = st.radio(
            "Performance Mode:",
            ["Fast", "Balanced", "Thorough"],
            index=0,
            help="Fast: Optimized for speed. Balanced: Good mix of speed and detail. Thorough: Most comprehensive analysis."
        )
        
        # Map user-friendly names to internal mode names
        mode_mapping = {
            "Fast": "fast",
            "Balanced": "balanced",
            "Thorough": "thorough"
        }
        
        # Update performance mode in session state
        st.session_state.performance_mode = mode_mapping[performance_mode]
        
        # Display mode selection
        display_mode = st.radio(
            "Display Style:",
            ["Card View", "Compact List"],
            index=0 if st.session_state.display_mode == "cards" else 1
        )
        
        # Update display mode in session state
        st.session_state.display_mode = "cards" if display_mode == "Card View" else "compact"
        
        # Dark mode toggle
        dark_mode = st.toggle("Dark Mode", value=st.session_state.dark_mode)
        if dark_mode != st.session_state.dark_mode:
            st.session_state.dark_mode = dark_mode
            st.rerun()  # Rerun to apply theme change
        
        # Hindi TTS toggle
        enable_tts = st.toggle("Enable Hindi Audio", value=st.session_state.enable_tts)
        st.session_state.enable_tts = enable_tts
        
        # App info section
        with st.expander("About", expanded=False):
            st.markdown("""
            **News Analyzer Pro** helps you quickly analyze and understand news articles.
            
            Features:
            - Multi-source news aggregation
            - Article summarization
            - Topic extraction
            - Sentiment analysis
            - Hindi text-to-speech
            - Comparative analysis
            
            Built with Streamlit and ❤️
            """)

        # Show current time
        st.caption(f"Current time (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        st.caption(f"User: {os.environ.get('USER', 'grittyuser007')}")
    
    try:
        # Initialize components with current performance mode
        news_fetcher, content_scraper, summary_gen, topic_extractor, comparative_analyzer = load_components()
        
        # Search View
        if st.session_state.view_mode == "search":
            # App header with typography
            st.markdown("""
            <div style='text-align: center; padding: 10px;'>
                <h1 style='font-size: 2.5rem;'>📰 News Analyzer Pro</h1>
                <p style='font-size: 1.2rem;'>Search, summarize, and analyze news from multiple sources</p>
            </div>
            <hr>
            """, unsafe_allow_html=True)
            
            # Search form in a nice card
            st.markdown("""
            <div style='background-color: #f0f2f6; border-radius: 10px; padding: 20px; margin-bottom: 20px;'>
                <h3>🔍 Search for News</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # Search form with columns
            search_cols = st.columns([3, 1, 1])
            
            with search_cols[0]:
                company = st.text_input(
                    "Company or Topic:",
                    placeholder="Enter company name or topic...",
                    value=st.session_state.company,
                    help="Enter a company name, person, or topic to search for news"
                )
                st.session_state.company = company
            
            with search_cols[1]:
                num_articles = st.slider(
                    "Number of Articles:", 
                    3, 12, 6, 
                    help="Select how many articles to fetch and analyze"
                )
                
            with search_cols[2]:
                search_btn = st.button(
                    "🔍 Search News", 
                    type="primary",
                    use_container_width=True,
                    help="Click to search for and analyze news articles"
                )
                
                if search_btn:
                    process_search(
                        news_fetcher, 
                        content_scraper, 
                        summary_gen, 
                        topic_extractor, 
                        company, 
                        num_articles, 
                        enable_tts
                    )
                    # Reset article selections when doing a new search
                    st.session_state.selected_articles = []
                    st.session_state.comparison_results = None
            
            # Show company exploration suggestions
            if not st.session_state.articles:
                st.markdown("""
                <div style='background-color: #f0f2f6; border-radius: 10px; padding: 20px; margin: 20px 0;'>
                    <h3>📊 Trending Topics</h3>
                    <p>Try searching for one of these trending companies or topics:</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Sample companies in a grid
                sample_cols = st.columns(4)
                sample_companies = ["Apple", "Tesla", "Climate Change", "Artificial Intelligence", 
                                   "Microsoft", "SpaceX", "Renewable Energy", "Google"]
                
                for i, company in enumerate(sample_companies):
                    with sample_cols[i % 4]:
                        if st.button(f"📈 {company}", key=f"sample_{i}", use_container_width=True):
                            st.session_state.company = company
                            process_search(news_fetcher, content_scraper, summary_gen, topic_extractor, 
                                          company, num_articles, enable_tts)
                            st.session_state.selected_articles = []
                            st.session_state.comparison_results = None
            
            # Display previously fetched articles
            if st.session_state.articles:
                st.markdown(f"""
                <div style='background-color: #f0f2f6; border-radius: 10px; padding: 20px; margin: 20px 0;'>
                    <h3>📰 News Results for '{st.session_state.company}'</h3>
                    <p>Found {len(st.session_state.articles)} articles. Select articles to compare or click to read.</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Action buttons for comparison
                action_cols = st.columns([3, 1])
                
                with action_cols[0]:
                    if len(st.session_state.selected_articles) > 0:
                        st.info(f"✓ {len(st.session_state.selected_articles)} articles selected for comparison")
                
                with action_cols[1]:
                    # Show comparison button if we have enough articles
                    if len(st.session_state.articles) >= 2:
                        if st.button("📊 Compare Selected", 
                                    disabled=len(st.session_state.selected_articles) < 2,
                                    use_container_width=True,
                                    help="Select at least 2 articles to compare them"):
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
                
                # Display mode controls
                st.markdown("---")
                
                # Display articles based on selected view mode
                if st.session_state.display_mode == "cards":
                    # Card view - 3 columns
                    display_articles_as_cards(st.session_state.articles)
                else:
                    # Compact view - table format
                    display_articles_as_table(st.session_state.articles)
        
        # Reading View
        elif st.session_state.view_mode == "reading":
            if 0 <= st.session_state.current_article_index < len(st.session_state.articles):
                article = st.session_state.articles[st.session_state.current_article_index]
                
                # Navigation header
                nav_cols = st.columns([1, 3, 1])
                
                with nav_cols[0]:
                    if st.button("← Back to List", use_container_width=True):
                        return_to_search()
                
                with nav_cols[1]:
                    st.markdown(f"""
                    <div style='text-align:center'>
                        <h4>Article {st.session_state.current_article_index + 1} of {len(st.session_state.articles)}</h4>
                    </div>
                    """, unsafe_allow_html=True)
                
                with nav_cols[2]:
                    prev_next_cols = st.columns(2)
                    with prev_next_cols[0]:
                        if st.button("← Prev", disabled=st.session_state.current_article_index == 0, use_container_width=True):
                            go_to_previous_article()
                    with prev_next_cols[1]:
                        if st.button("Next →", disabled=st.session_state.current_article_index == len(st.session_state.articles) - 1, use_container_width=True):
                            go_to_next_article()
                
                # Article container
                st.markdown("""
                <div style='background-color: #f8f9fa; border-radius: 10px; padding: 20px; margin: 20px 0;'>
                """, unsafe_allow_html=True)
                
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
                st.markdown(f"## {article['title']}")
                
                # Article metadata
                meta_cols = st.columns([1, 2])
                with meta_cols[0]:
                    st.markdown(f"**Source:** {article.get('source', 'Unknown')}")
                with meta_cols[1]:
                    st.markdown(f"**Published:** {article.get('timestamp', '')}")
                
                # External link button
                st.markdown(f"[🔗 Original Article]({article['url']})")
                
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
                    st.markdown(f"**[View Original Article]({article['url']})**")
                
                # Close article container div
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Display tabs for different views of the article
                tabs = st.tabs(["📝 Summary", "📄 Full Content", "🔊 Audio (Hindi)"])
                
                with tabs[0]:
                    sentiment, polarity = get_sentiment(article.get('summary', ''))
                    
                    # Sentiment meter visualization
                    st.markdown(f"**Sentiment Analysis:** {sentiment}")
                    
                    # Create a sentiment meter
                    sentiment_cols = st.columns([1, 3, 1])
                    with sentiment_cols[1]:
                        # Map polarity from [-1, 1] to [0, 100]
                        sentiment_value = int((polarity + 1) * 50)
                        st.progress(sentiment_value)
                        
                        # Create colored markers
                        markers_html = f"""
                        <div style="display: flex; justify-content: space-between; margin-top: -15px;">
                            <div style="color: #d73027;">Negative</div>
                            <div style="color: #4575b4;">Positive</div>
                        </div>
                        """
                        st.markdown(markers_html, unsafe_allow_html=True)
                    
                    # Display the summary in a nice format
                    st.markdown("""
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 15px;">
                    """, unsafe_allow_html=True)
                    st.markdown(article.get('summary', 'Summary not available'))
                    st.markdown("</div>", unsafe_allow_html=True)
                
                with tabs[1]:
                    st.markdown("""
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 15px;">
                    """, unsafe_allow_html=True)
                    st.markdown(article.get('content', 'Content not available'))
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    st.markdown(f"[Read original article]({article['url']})")
                
                with tabs[2]:
                    if st.session_state.enable_tts and article.get('summary') and not article.get('summary', '').startswith('Error'):
                        with st.spinner("Generating Hindi audio..."):
                            audio_buffer, hindi_text = text_to_hindi_speech(article.get('summary', ''))
                        
                        if audio_buffer:
                            st.audio(audio_buffer, format='audio/mp3')
                            
                            # Audio controls
                            audio_cols = st.columns([1, 1])
                            with audio_cols[0]:
                                st.download_button(
                                    label="💾 Download Hindi Audio",
                                    data=audio_buffer,
                                    file_name="hindi_summary.mp3",
                                    mime="audio/mp3",
                                    use_container_width=True
                                )
                            
                            st.markdown("### Hindi Translation")
                            st.markdown("""
                            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 15px;">
                            """, unsafe_allow_html=True)
                            st.markdown(hindi_text)
                            st.markdown("</div>", unsafe_allow_html=True)
                        else:
                            st.warning("Hindi audio generation failed")
                    else:
                        if not st.session_state.enable_tts:
                            st.info("Enable Hindi Audio in settings to use this feature")
                        elif article.get('summary', '').startswith('Error'):
                            st.warning("Cannot generate audio for content with errors")
                        else:
                            st.info("No summary available for audio conversion")
        
        # Comparison View
        elif st.session_state.view_mode == "comparison":
            # Navigation header
            st.markdown("""
            <div style='background-color: #f0f2f6; border-radius: 10px; padding: 20px; margin-bottom: 20px;'>
                <h2>📊 Comparative News Analysis</h2>
                <p>Compare different news sources covering the same topic</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("← Back to News List", use_container_width=False):
                return_to_search()
            
            if st.session_state.comparison_results:
                results = st.session_state.comparison_results
                
                # Display basic information
                info_cols = st.columns(2)
                with info_cols[0]:
                    st.markdown(f"**Analysis Timestamp:** {results.get('timestamp', 'Unknown')}")
                with info_cols[1]:
                    st.markdown(f"**Sources Compared:** {', '.join(results.get('sources', ['Unknown']))}")
                
                # Create tabs for different analysis types
                tabs = st.tabs([
                    "📊 Entity Comparison", 
                    "🔑 Key Phrase Comparison",
                    "😊 Sentiment Analysis",
                    "📈 Content Similarity"
                ])
                
                # Entity Comparison Tab
                with tabs[0]:
                    if "entity_comparison" in results:
                        st.markdown("### Entity Comparison Across Sources")
                        st.markdown("""
                        This table shows how frequently different entities (people, organizations, locations) 
                        are mentioned across sources. Higher numbers indicate more mentions.
                        """)
                        
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
                        st.markdown("""
                        This table shows important phrases and their relative importance in each article.
                        Higher values indicate that the phrase is more important to that article.
                        """)
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
                    label="💾 Export Analysis Data (JSON)",
                    data=str(results),
                    file_name=f"news_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
                
            else:
                st.warning("No comparison results available. Please select articles to compare.")
                if st.button("Return to article selection"):
                    return_to_search()
    
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        st.error(f"Critical application error: {str(e)}")
        st.warning("Note: Translation service might be unavailable")
        
        # Show detailed error info in expandable section
        with st.expander("Error Details"):
            st.code(str(e))
            import traceback
            st.code(traceback.format_exc())

def display_articles_as_cards(articles):
    """Display articles in a card view"""
    # Create a 3-column layout for news cards
    num_columns = 3
    rows = [st.columns(num_columns) for _ in range((len(articles) + num_columns - 1) // num_columns)]
    
    for idx, article in enumerate(articles):
        col_idx = idx % num_columns
        row_idx = idx // num_columns
        
        sentiment, _ = get_sentiment(article.get('summary', ''))
        
        # Add warning symbol for error content
        title_prefix = ""
        if article.get('content', '').startswith('Error:') or article.get('content', '') == "Failed to extract content":
            title_prefix = "❌ "
        elif article.get('content', '') == "Article behind paywall":
            title_prefix = "🔒 "
        
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
        
        with rows[row_idx][col_idx]:
            # Card container
            st.markdown(f"""
            <div style='border:1px solid #ddd; border-radius:10px; padding:15px; margin-bottom:15px; height:280px; overflow:hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.1);'>
                <h4 style='margin-top:0;'>{title_prefix}{article['title'][:70] + '...' if len(article['title']) > 70 else article['title']}</h4>
                <p style='color:gray; font-size:small;'>{article.get('source', 'Unknown')} • {article.get('timestamp', '')}</p>
                <p>{sentiment}</p>
                <p style='height: 60px; overflow: hidden;'>{article.get('summary', '')[:100]}...</p>
                <div>{topics_html}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Add selection checkbox for comparison
            col1, col2 = st.columns([1, 1])
            with col1:
                is_selected = idx in st.session_state.selected_articles
                if st.checkbox(f"Select for comparison", value=is_selected, key=f"select_{idx}"):
                    if idx not in st.session_state.selected_articles:
                        st.session_state.selected_articles.append(idx)
                else:
                    if idx in st.session_state.selected_articles:
                        st.session_state.selected_articles.remove(idx)
            
            with col2:
                if st.button(f"Read Article", key=f"read_{idx}", use_container_width=True):
                    change_to_reading_view(idx)

def display_articles_as_table(articles):
    """Display articles in a compact table view"""
    # Create a DataFrame for the articles
    data = []
    for idx, article in enumerate(articles):
        sentiment, _ = get_sentiment(article.get('summary', ''))
        
        # Add warning symbol for error content
        title_prefix = ""
        if article.get('content', '').startswith('Error:') or article.get('content', '') == "Failed to extract content":
            title_prefix = "❌ "
        elif article.get('content', '') == "Article behind paywall":
            title_prefix = "🔒 "
            
        # Format topics as a string
        topics = ", ".join([topic for topic, _ in article.get('topics', [])[:3]]) if article.get('topics') else ""
        
        data.append({
            "Title": f"{title_prefix}{article['title']}",
            "Source": article.get('source', 'Unknown'),
            "Date": article.get('timestamp', ''),
            "Sentiment": sentiment,
            "Topics": topics,
            "Index": idx
        })
    
    df = pd.DataFrame(data)
    
    # Custom CSS for the table
    st.markdown("""
    <style>
    .dataframe {
        font-size: 14px;
        border: none;
        border-collapse: collapse;
        width: 100%;
        text-align: left;
    }
    .dataframe th {
        background-color: #f1f1f1;
        padding: 10px;
    }
    .dataframe td {
        padding: 8px;
        border-bottom: 1px solid #ddd;
        vertical-align: top;
    }
    .dataframe tr:hover {
        background-color: #f5f5f5;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Display the table
    selected_indices = []
    for i, row in df.iterrows():
        col1, col2, col3, col4, col5, col6 = st.columns([0.5, 3, 1, 1, 1, 1.5])
        
        with col1:
            # Selection checkbox
            idx = row['Index']
            is_selected = idx in st.session_state.selected_articles
            if st.checkbox("", value=is_selected, key=f"list_select_{idx}"):
                if idx not in st.session_state.selected_articles:
                    st.session_state.selected_articles.append(idx)
                selected_indices.append(idx)
            else:
                if idx in st.session_state.selected_articles:
                    st.session_state.selected_articles.remove(idx)
        
        with col2:
            # Title with link
            if st.button(row['Title'], key=f"title_btn_{i}"):
                change_to_reading_view(row['Index'])
        
        with col3:
            st.write(row['Source'])
            
        with col4:
            st.write(row['Date'])
            
        with col5:
            st.write(row['Sentiment'])
            
        with col6:
            st.write(row['Topics'])
    
    # Update selection in session state to match the current view
    # This ensures consistency between views
    st.session_state.selected_articles = selected_indices

if __name__ == "__main__":
    main()