import os
from dotenv import load_dotenv
from playwright_setup import TwitterBrowser
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    email = os.getenv('TWITTER_EMAIL')
    password = os.getenv('TWITTER_PASSWORD')
    account = os.getenv('TWITTER_ACCOUNT')
    headless = os.getenv('HEADLESS', 'false').lower() == 'true'
    
    if not all([email, password, account]):
        logger.error("Missing required environment variables. Please check your .env file")
        return
    
    try:
        # Initialize browser
        browser = TwitterBrowser()
        browser.start(headless=headless)
        
        # Attempt login
        logger.info("Attempting to login to Twitter...")
        success = browser.login(email, password, account)
        
        if success:
            logger.info("Successfully logged in to Twitter!")
            # Wait for user input before closing
            input("Press Enter to close the browser...")
        else:
            logger.error("Failed to login to Twitter")
            
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    finally:
        browser.close()

if __name__ == "__main__":
    main()
