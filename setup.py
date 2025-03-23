import os
import subprocess
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("setup")

def setup_virtual_display():
    """Set up a virtual display for Selenium to use"""
    logger.info("Setting up virtual display with Xvfb")
    try:
        # Kill any existing Xvfb processes
        subprocess.run(["pkill", "Xvfb"], stderr=subprocess.DEVNULL)
        time.sleep(1)
        
        # Start a new Xvfb process
        subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1024x768x24", "-ac"], 
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Set the display environment variable
        os.environ["DISPLAY"] = ":99"
        logger.info("Virtual display set up successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to set up virtual display: {e}")
        return False

def verify_chromium():
    """Verify Chromium and ChromeDriver are installed"""
    logger.info("Verifying Chromium installation")
    try:
        chromium_path = "/usr/bin/chromium"
        chromedriver_path = "/usr/bin/chromedriver"
        
        chromium_exists = os.path.exists(chromium_path)
        chromedriver_exists = os.path.exists(chromedriver_path)
        
        logger.info(f"Chromium exists: {chromium_exists}")
        logger.info(f"ChromeDriver exists: {chromedriver_exists}")
        
        if chromium_exists and chromedriver_exists:
            return True
        return False
    except Exception as e:
        logger.error(f"Error verifying Chromium installation: {e}")
        return False

if __name__ == "__main__":
    setup_virtual_display()
    verify_chromium()