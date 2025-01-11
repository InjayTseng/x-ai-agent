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
        self.analyzer = TweetAnalyzer(self.db)
        self.summarizer = TweetSummarizer(self.db)
        self.interactor = TweetInteractor(self.db)
        
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
            
            # 主循環：持續運行機器人的核心功能
            while True:
                try:
                    logger.info("Starting new scan cycle...")
                    
                    # 1. 掃描和分析新推文
                    # - 獲取最新的推文
                    # - 分析推文內容和見解
                    # - 將結果保存到數據庫
                    await self.analyzer.fetch_and_learn_tweets(page, self.max_tweets)
                    
                    # 2. 檢查是否需要回覆推文
                    # - 檢查距離上次回覆的時間間隔
                    # - 如果超過設定的間隔(REPLY_INTERVAL)，則進行回覆
                    if (datetime.now() - self.last_reply_time).total_seconds() >= self.reply_interval:
                        # 回覆最近的推文，限制最大回覆數量
                        await self.interactor.reply_to_recent_tweets(page, max_replies=self.max_replies)
                        # 更新上次回覆時間
                        self.last_reply_time = datetime.now()
                    
                    # 3. 檢查是否需要發布摘要
                    # - 檢查距離上次發布摘要的時間間隔
                    # - 如果超過設定的間隔(SUMMARY_INTERVAL)，則生成並發布摘要
                    if (datetime.now() - self.last_summary_time).total_seconds() >= self.summary_interval:
                        # 生成並發布見解摘要
                        await self.summarizer.post_summary(page)
                        # 更新上次摘要時間
                        self.last_summary_time = datetime.now()
                    
                    # 4. 等待下一個掃描週期
                    # - 記錄完成當前週期
                    # - 等待設定的時間間隔(SCAN_INTERVAL)後再次執行
                    logger.info(f"Cycle complete. Waiting {self.scan_interval/60:.1f} minutes until next scan...")
                    await asyncio.sleep(self.scan_interval)
                    
                except Exception as e:
                    # 錯誤處理：記錄錯誤並等待一段時間後重試
                    # - 記錄錯誤信息到日誌
                    # - 等待5分鐘後重試，避免立即重試可能導致的問題
                    logger.error(f"Error in main loop: {e}")
                    await asyncio.sleep(300)  # 5分鐘 = 300秒
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
