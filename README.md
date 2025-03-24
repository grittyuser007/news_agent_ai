---
license: apache-2.0
title: News Analyzer Pro - Setup and Usage Instructions
emoji: 🚀
colorFrom: red
colorTo: blue
short_description: 'ai based summarizer for news '
sdk: streamlit
---
# News Analyzer Pro - Setup and Usage Instruction

Overview-
News Analyzer Pro is an advanced web application that helps you quickly analyze news articles from multiple sources. The tool fetches, extracts, summarizes, and performs topic and sentiment analysis on news articles. It also provides comparative analysis between different news sources and offers text-to-speech capabilities in Hindi.

Features--
Multi-source news aggregation - Automatically collects news from reliable sources
Article summarization - Generates concise summaries for quick understanding
Topic extraction - Identifies key topics, entities, and concepts
Sentiment analysis - Determines if an article is positive, negative, or neutral
Comparative analysis - Compare different news sources on the same topic
Hindi text-to-speech - Listen to article summaries in Hindi



# Setup Instructions--
Prerequisites
Python 3.7+ installed
pip package manager
Internet connection
Installation

1)Clone the repository or download source files:
 git clone https://github.com//news-analyzer.git
 cd news-analyzer

3)Create and activate a virtual environment (recommended):
  python -m venv venv

  On Windows
  venv\Scripts\activate

  On macOS/Linux
  source venv/bin/activate
4)Install required dependencies:
  pip install -r requirements.txt

4o)If you don't have a requirements.txt file, install these essential packages:  (optional)
  pip install streamlit beautifulsoup4 requests textblob gtts deep-translator pydub
  
5)Create the necessary directories:
 mkdir -p content_cache

6)File Structure:Ensure your project has the following files:


    news-analyzer
       news.py             # Main application file
       news_fetcher.py     # Fetches news links from various sources
       content_scraper.py  # Extracts content from news articles
       summary.py          # Handles article summarization
       topic_extractor.py  # Extracts key topics from articles
       comparative_analysis.py  # Compares multiple news sources
       README.md           # This file

7)Usage Instructions
  a: Starting the Application
  b: Run the Streamlit application: streamlit run news.py

8)Access the web interface:The application will automatically open in your default web browser.
                           If not, navigate to the URL shown in the terminal (typically http://localhost:8501)

9)Basic Usage:Search for News

Enter a company name, person, or topic in the search box
Select the number of articles to analyze from the dropdown
Check "Enable Hindi Audio" if you want text-to-speech capability
Click "Search News"
Reading Articles:

Browse through the article cards displayed after search
Click "Read Article #X" to read the full article
Navigate between articles using "Prev" and "Next" buttons
Return to the list view by clicking "Back to List"
Article View Tabs:

Summary: Read a concise summary of the article
Full Content: View the complete article text
Audio (Hindi): Listen to the article summary in Hindi
Advanced Features
Comparing Articles:

Select multiple articles using the checkboxes
Click "Compare Selected Articles"
View comparative analysis across different tabs:
Entity Comparison
Key Phrase Comparison
Sentiment Analysis
Content Similarity

10)System Status:

Click on "System Status" at the bottom to see component status
In Debug Mode, additional troubleshooting options are available
Troubleshooting

11)Common Issues  : "Content too short to summarize" Error

Try searching for a different topic
Clear the cache using the "Clear Cache" button in System Status (Debug Mode)
The system will automatically prioritize easily scrapable content sources
Text-to-Speech Not Working:

Check your internet connection
Ensure you have the required TTS libraries installed
The application has fallback mechanisms when Google TTS is unavailable
Slow Performance:

Try selecting a smaller number of articles (3-5)
Check your internet connection speed
Clear the content cache if it's grown very large

12)Features:
Content verification testing
TTS service testing
Cache clearing option
Technical Components

13)The News Analyzer consists of several key components:

NewsFetcher: Gathers news links from Google News and other sources
ContentScraper: Extracts article content using optimized techniques
SummaryGenerator: Creates concise summaries of article content
TopicExtractor: Identifies key topics and entities
ComparativeAnalyzer: Compares articles from different sources
Optimization Notes
The application prioritizes easily scrapable non-JavaScript websites
Content extraction uses site-specific extractors for better accuracy
Multiple fallback mechanisms ensure continuous operation
Caching improves performance for repeated searches



# flow diagram of the model: 
![image/png](https://cdn-uploads.huggingface.co/production/uploads/6759c615f49bea55e35c7215/YTNCqGGa4RG2cxPt1icix.png)













Created by grittyuser007 | Last updated: 2025-03-24
Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference