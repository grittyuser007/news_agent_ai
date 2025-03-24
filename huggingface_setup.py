#!/usr/bin/env python3
"""
Setup script for News Analyzer in Hugging Face Spaces
"""
import os
import subprocess
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hf-setup")

def setup_virtual_display():
    """Set up virtual display for Selenium"""
    try:
        logger.info("Setting up virtual display with Xvfb")
        # Kill any existing Xvfb processes
        os.system("pkill -f Xvfb || true")
        # Start Xvfb
        subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1024x768x24", "-ac"], 
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.environ["DISPLAY"] = ":99"
        logger.info("Virtual display set up successfully")
    except Exception as e:
        logger.error(f"Failed to set up virtual display: {e}")

def check_chromium():
    """Verify chromium and chromedriver installation"""
    try:
        logger.info("Checking Chromium installation")
        result = subprocess.run(["which", "chromium-browser"], check=False, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Found chromium-browser at: {result.stdout.strip()}")
        else:
            logger.warning("chromium-browser not found, trying chromium")
            result = subprocess.run(["which", "chromium"], check=False, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Found chromium at: {result.stdout.strip()}")
                # Create a symlink to chromium-browser for compatibility
                if not os.path.exists("/usr/bin/chromium-browser"):
                    try:
                        os.symlink(result.stdout.strip(), "/usr/bin/chromium-browser")
                        logger.info("Created symlink for chromium-browser")
                    except:
                        logger.warning("Could not create symlink")
            else:
                logger.error("No chromium binary found")
                
        result = subprocess.run(["which", "chromedriver"], check=False, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Found chromedriver at: {result.stdout.strip()}")
        else:
            logger.error("chromedriver not found")
            
        # List the packages installed
        logger.info("Listing installed Chrome-related packages:")
        subprocess.run(["dpkg", "-l", "*chrom*"], check=False)
        
        return True
    except Exception as e:
        logger.error(f"Error checking chromium: {e}")
        return False

def setup_fallback():
    """Set up fallback methods if selenium can't be used"""
    logger.info("Setting up fallback scraping methods")
    try:
        import requests
        import bs4
        logger.info("Required fallback packages are available")
    except ImportError as e:
        logger.error(f"Missing fallback package: {e}")

if __name__ == "__main__":
    setup_virtual_display()
    check_chromium()
    setup_fallback()