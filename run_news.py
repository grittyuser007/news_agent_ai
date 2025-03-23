import os
import sys

# Set environment variables before any imports
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["PYTHONWARNINGS"] = "ignore"

# Disable Streamlit's file watcher
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

# Launch with proper parameters
if __name__ == "__main__":
    import streamlit.web.cli as stcli
    
    sys.argv = ["streamlit", "run", "news.py", 
                "--server.fileWatcherType=none", 
                "--server.enableXsrfProtection=false",
                "--server.enableCORS=false"]
    
    sys.exit(stcli.main())