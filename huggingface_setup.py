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
        os.system("pkill -f Xvfb")
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
        subprocess.run(["which", "chromium-browser"], check=True, capture_output=True)
        subprocess.run(["which", "chromedriver"], check=True, capture_output=True)
        logger.info("Chromium and ChromeDriver found")
        return True
    except subprocess.CalledProcessError:
        logger.error("Chromium or ChromeDriver not found")
        return False

if __name__ == "__main__":
    setup_virtual_display()
    check_chromium()