import os
import logging
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from playwright_setup import TwitterBrowser
from database import TwitterDatabase
from tweet_analyzer import TweetAnalyzer
from tweet_interactor import TweetInteractor
from tweet_summarizer import TweetSummarizer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TwitterAgent:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Initialize components
        self.db = TwitterDatabase()
        self.browser = TwitterBrowser()
        self.analyzer = TweetAnalyzer(self.db, os.getenv('OPENAI_API_KEY'))
        self.interactor = TweetInteractor(self.db, os.getenv('OPENAI_API_KEY'))
        self.summarizer = TweetSummarizer(self.db, os.getenv('OPENAI_API_KEY'))
        
        # Load intervals (convert minutes to seconds)
        self.scan_interval = int(os.getenv('SCAN_INTERVAL', 60)) * 60
        self.reply_interval = int(os.getenv('REPLY_INTERVAL', 120)) * 60
        self.summary_interval = int(os.getenv('SUMMARY_INTERVAL', 1440)) * 60
        
        # Load other settings
        self.max_tweets = int(os.getenv('MAX_TWEETS_SCAN', 50))
        self.max_replies = int(os.getenv('MAX_REPLIES_PER_CYCLE', 3))
        
        # Track last run times
        self.last_reply_time = datetime.now() - timedelta(hours=24)
        self.last_summary_time = datetime.now() - timedelta(hours=24)
    
    async def start(self):
        """Start the Twitter agent"""
        try:
            # Start browser
            if not await self.browser.start(headless=False):  # Set to True for production
                logger.error("Failed to start browser")
                return
            
            # Login to Twitter
            if not await self.browser.login(
                email=os.getenv('TWITTER_EMAIL'),
                password=os.getenv('TWITTER_PASSWORD'),
                account_name=os.getenv('TWITTER_ACCOUNT')
            ):
                logger.error("Failed to login to Twitter")
                return
                
            # Get the browser page
            page = self.browser.page
            
            # Main loop
            while True:
                try:
                    logger.info("Starting new scan cycle...")
                    
                    # Always scan for new tweets
                    await self.analyzer.fetch_and_learn_tweets(page, self.max_tweets)
                    
                    # Check if it's time to reply
                    if (datetime.now() - self.last_reply_time).total_seconds() >= self.reply_interval:
                        await self.interactor.reply_to_recent_tweets(page, max_replies=self.max_replies)
                        self.last_reply_time = datetime.now()
                    
                    # Check if it's time to post summary
                    if (datetime.now() - self.last_summary_time).total_seconds() >= self.summary_interval:
                        await self.summarizer.post_summary(page)
                        self.last_summary_time = datetime.now()
                    
                    # Wait for next scan
                    logger.info(f"Cycle complete. Waiting {self.scan_interval/60:.1f} minutes until next scan...")
                    await asyncio.sleep(self.scan_interval)
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    await asyncio.sleep(300)  # Wait 5 minutes on error
                    
        except Exception as e:
            logger.error(f"Critical error: {e}")
        
        finally:
            # Close browser
            await self.browser.close()

async def main():
    agent = TwitterAgent()
    await agent.start()

if __name__ == "__main__":
    asyncio.run(main())
