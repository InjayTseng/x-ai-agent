import os
import logging
import asyncio
from dotenv import load_dotenv
from playwright_setup import TwitterBrowser
from database import TwitterDatabase
from tweet_analyzer import TweetAnalyzer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize components
    db = TwitterDatabase()
    browser = TwitterBrowser()
    analyzer = TweetAnalyzer(db, os.getenv('OPENAI_API_KEY'))
    
    try:
        # Start browser
        if not await browser.start(headless=False):  # Set to True for production
            logger.error("Failed to start browser")
            return
        
        # Login to Twitter
        if not await browser.login(
            email=os.getenv('TWITTER_EMAIL'),
            password=os.getenv('TWITTER_PASSWORD'),
            account_name=os.getenv('TWITTER_ACCOUNT')
        ):
            logger.error("Failed to login to Twitter")
            return
            
        # Fetch and analyze tweets
        await analyzer.fetch_and_learn_tweets(browser.page, max_tweets=5)
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
