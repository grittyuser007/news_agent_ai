"""
Entry point for News Analyzer with Hindi TTS on Hugging Face Spaces
This file handles initialization and launches the Streamlit app
"""
import os
import sys
import nltk
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NewsAnalyzerApp")
logger.info("Initializing News Analyzer application")

# Download required NLTK resources
try:
    logger.info("Setting up NLTK resources")
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    logger.info("NLTK resources downloaded successfully")
except Exception as e:
    logger.warning(f"Error downloading NLTK resources: {e}")
    logger.info("App will try to continue but may have limited functionality")

# Set up content cache directory
cache_dir = Path("./content_cache")
if not cache_dir.exists():
    logger.info("Creating content cache directory")
    cache_dir.mkdir(exist_ok=True)

# Set environment variables for better compatibility
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["PYTHONWARNINGS"] = "ignore"

# Required for Selenium in Spaces environment
os.environ["DISPLAY"] = ":99"
os.environ["PYTHONUNBUFFERED"] = "1"

# Configure Chrome for Selenium
os.environ["CHROMIUM_FLAGS"] = "--no-sandbox --disable-dev-shm-usage --disable-gpu --disable-software-rasterizer --disable-extensions"

# Launch the main application
logger.info("Starting News Analyzer Streamlit app")
try:
    # Import and run the main application
    from news import main
    
    # This is the Streamlit entry point
    if __name__ == "__main__":
        main()
        
except Exception as e:
    logger.error(f"Failed to start application: {e}")
    
    # If there's an import error, show a helpful message in the UI
    import streamlit as st
    st.error("⚠️ Application Error")
    st.write(f"Error: {str(e)}")
    st.info("This may be caused by a missing dependency or configuration issue.")
    st.info("Check the logs in the 'Factory' tab for more details.")