import os
import logging
import asyncio
from dotenv import load_dotenv
from playwright_setup import TwitterBrowser
from database import TwitterDatabase
from tweet_analyzer import TweetAnalyzer
from tweet_interactor import TweetInteractor
from tweet_summarizer import TweetSummarizer

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
    interactor = TweetInteractor(db, os.getenv('OPENAI_API_KEY'))
    summarizer = TweetSummarizer(db, os.getenv('OPENAI_API_KEY'))
    
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
            
        # Get the browser page
        page = browser.page
        
        # Analyze recent tweets
        await analyzer.fetch_and_learn_tweets(page)
        
        # Reply to recent tweets
        await interactor.reply_to_recent_tweets(page)
        
        # Post daily summary (if SUMMARY_INTERVAL hours have passed since last summary)
        summary_interval = int(os.getenv('SUMMARY_INTERVAL', 24))
        await summarizer.post_summary(page, hours=summary_interval)
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        
    finally:
        # Close browser
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
