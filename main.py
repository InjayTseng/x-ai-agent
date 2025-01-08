import os
from datetime import datetime
import logging
from typing import List, Dict
import openai
from playwright_setup import TwitterBrowser
from database import TwitterDatabase
from scheduler import TwitterScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TwitterAgent:
    def __init__(self):
        # Initialize components
        self.browser = TwitterBrowser()
        self.db = TwitterDatabase()
        self.scheduler = TwitterScheduler()
        
        # Set up OpenAI
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
        # Twitter credentials
        self.email = os.getenv('TWITTER_EMAIL')
        self.password = os.getenv('TWITTER_PASSWORD')
        self.account_name = os.getenv('TWITTER_ACCOUNT')
        
    def start(self):
        """Start the Twitter Agent"""
        try:
            # Start browser and login
            self.browser.start(headless=True)
            if not self.browser.login(self.email, self.password, self.account_name):
                raise Exception("Failed to login to Twitter")
            
            # Start scheduler
            self.scheduler.start(
                reply_func=self.reply_to_tweets,
                post_func=self.create_post,
                learn_func=self.learn_from_tweets
            )
            
            logger.info("Twitter Agent started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Twitter Agent: {str(e)}")
            self.cleanup()
            raise
    
    def learn_from_tweets(self):
        """Learn from tweets in the home timeline"""
        try:
            page = self.browser.get_page()
            # Implement tweet extraction logic here
            tweets = self._extract_tweets(page)
            
            for tweet in tweets:
                # Generate summary using OpenAI
                summary = self._generate_summary(tweet['content'])
                tweet['summary'] = summary
                
                # Save to database
                self.db.save_tweet(tweet)
                
        except Exception as e:
            logger.error(f"Error in learn_from_tweets: {str(e)}")
    
    def reply_to_tweets(self):
        """Reply to relevant tweets"""
        try:
            # Get recent tweets from database
            recent_tweets = self.db.get_recent_tweets(limit=5)
            
            for tweet in recent_tweets:
                # Generate reply using OpenAI
                reply_content = self._generate_reply(tweet)
                
                # Post reply using Playwright
                self._post_reply(tweet['tweet_id'], reply_content)
                
                # Save reply to database
                reply_data = {
                    'original_tweet_id': tweet['tweet_id'],
                    'reply_content': reply_content,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'posted'
                }
                self.db.save_reply(reply_data)
                
        except Exception as e:
            logger.error(f"Error in reply_to_tweets: {str(e)}")
    
    def create_post(self):
        """Create a new post based on learned content"""
        try:
            # Get recent tweets for context
            recent_tweets = self.db.get_recent_tweets(limit=10)
            
            # Generate post content using OpenAI
            post_content = self._generate_post(recent_tweets)
            
            # Post content using Playwright
            self._post_tweet(post_content)
            
            # Save post to database
            post_data = {
                'content': post_content,
                'source_tweets': [t['tweet_id'] for t in recent_tweets],
                'timestamp': datetime.now().isoformat(),
                'status': 'posted'
            }
            self.db.save_post(post_data)
            
        except Exception as e:
            logger.error(f"Error in create_post: {str(e)}")
    
    def cleanup(self):
        """Cleanup resources"""
        self.scheduler.stop()
        self.browser.close()
    
    def _extract_tweets(self, page) -> List[Dict]:
        """Extract tweets from the page"""
        # Implement tweet extraction logic using Playwright
        # Return list of tweet dictionaries
        pass
    
    def _generate_summary(self, content: str) -> str:
        """Generate summary using OpenAI"""
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Summarize the following tweet concisely:"},
                {"role": "user", "content": content}
            ]
        )
        return response.choices[0].message.content
    
    def _generate_reply(self, tweet: Dict) -> str:
        """Generate reply using OpenAI"""
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Generate a relevant and engaging reply to the following tweet:"},
                {"role": "user", "content": tweet['content']}
            ]
        )
        return response.choices[0].message.content
    
    def _generate_post(self, recent_tweets: List[Dict]) -> str:
        """Generate new post content using OpenAI"""
        summaries = "\n".join([t['summary'] for t in recent_tweets if t['summary']])
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Based on the following tweet summaries, generate an insightful new tweet:"},
                {"role": "user", "content": summaries}
            ]
        )
        return response.choices[0].message.content
    
    def _post_reply(self, tweet_id: str, content: str):
        """Post a reply to a tweet"""
        # Implement reply posting logic using Playwright
        pass
    
    def _post_tweet(self, content: str):
        """Post a new tweet"""
        # Implement tweet posting logic using Playwright
        pass

if __name__ == "__main__":
    agent = TwitterAgent()
    try:
        agent.start()
    except KeyboardInterrupt:
        logger.info("Shutting down Twitter Agent...")
        agent.cleanup()
