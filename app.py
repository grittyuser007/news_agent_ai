"""
Entry point for News Analyzer with Hindi TTS on Hugging Face Spaces
"""
import os
import sys
import logging
import nltk
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NewsAnalyzerApp")
logger.info("Initializing News Analyzer application")

# Run the setup script first
import setup
setup.setup_virtual_display()
chromium_available = setup.verify_chromium()

# Download required NLTK resources
try:
    logger.info("Setting up NLTK resources")
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    logger.info("NLTK resources downloaded successfully")
except Exception as e:
    logger.warning(f"Error downloading NLTK resources: {e}")

# Set up content cache directory
cache_dir = Path("./content_cache")
if not cache_dir.exists():
    logger.info("Creating content cache directory")
    cache_dir.mkdir(exist_ok=True)

# Set environment variables for better compatibility
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["PYTHONUNBUFFERED"] = "1"

# Launch the main application
logger.info("Starting News Analyzer Streamlit app")
try:
    # Import and run the main application
    from news import main
    
    if __name__ == "__main__":
        main()
        
except Exception as e:
    logger.error(f"Failed to start application: {e}")
    
    import streamlit as st
    st.error("⚠️ Application Error")
    st.write(f"Error: {str(e)}")
    st.info("Check the logs for more details.")