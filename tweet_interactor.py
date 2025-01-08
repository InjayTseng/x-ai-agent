import logging
from typing import Dict, Optional
import json
from datetime import datetime, timedelta
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TweetInteractor:
    def __init__(self, db, api_key: str):
        """Initialize TweetInteractor with database and OpenAI client"""
        self.db = db
        self.openai_client = OpenAI(api_key=api_key)
        
    def generate_reply(self, tweet_data: Dict) -> str:
        """Generate a reply using OpenAI based on tweet content and context"""
        try:
            # Create a prompt that includes tweet context
            prompt = f"""Tweet: {tweet_data['content']}
Author: {tweet_data['author']}
Context: This tweet is about {tweet_data['summary']}

Please generate a thoughtful, engaging reply to this tweet. The reply should be:
1. Relevant to the tweet's content
2. Professional and friendly
3. No more than 180 characters
4. Include relevant hashtags if appropriate
5. Written in the same language as the original tweet
6. No hastags"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates engaging Twitter replies. Keep responses concise and relevant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            reply = response.choices[0].message.content.strip()
            
            # Ensure reply is within Twitter's character limit
            if len(reply) > 280:
                reply = reply[:277] + "..."
                
            return reply
            
        except Exception as e:
            logger.error(f"Error generating reply: {str(e)}")
            return None
            
    async def reply_to_tweet(self, page, tweet_data: Dict) -> bool:
        """Post a reply to a specific tweet"""
        try:
            # Generate reply content
            reply_content = self.generate_reply(tweet_data)
            if not reply_content:
                return False
                
            # Navigate to tweet
            tweet_url = f"https://twitter.com/i/status/{tweet_data['tweet_id']}"
            logger.info(f"Navigating to tweet: {tweet_url}")
            await page.goto(tweet_url)
            await page.wait_for_timeout(5000)  # Wait longer for page to load
            
            # Try multiple selectors for the reply button
            reply_button = None
            reply_selectors = [
                '[data-testid="reply"]',
                'div[aria-label="Reply"]',
                'div[role="button"][aria-label*="Reply"]'
            ]
            
            for selector in reply_selectors:
                try:
                    reply_button = await page.wait_for_selector(selector, timeout=5000)
                    if reply_button:
                        break
                except Exception:
                    continue
            
            if not reply_button:
                logger.error("Could not find reply button")
                return False
                
            # Use JavaScript click to bypass overlay
            await reply_button.evaluate('node => node.click()')
            await page.wait_for_timeout(2000)
            
            # Find and fill reply input
            reply_input = await page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=10000)
            if not reply_input:
                logger.error("Could not find reply input")
                return False
                
            # Use JavaScript to set value and dispatch input event
            await reply_input.evaluate(f'''
                node => {{
                    node.focus();
                    node.value = "{reply_content}";
                    node.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            ''')
            await page.wait_for_timeout(1000)
            
            # Try multiple selectors for the tweet button
            tweet_button = None
            tweet_button_selectors = [
                '[data-testid="tweetButton"]',
                'div[data-testid="tweetButtonInline"]',
                'div[role="button"][data-testid*="tweet"]'
            ]
            
            for selector in tweet_button_selectors:
                try:
                    tweet_button = await page.wait_for_selector(selector, timeout=5000)
                    if tweet_button:
                        break
                except Exception:
                    continue
            
            if not tweet_button:
                logger.error("Could not find tweet button")
                return False
            
            # Use JavaScript click to bypass overlay
            await tweet_button.evaluate('node => node.click()')
            await page.wait_for_timeout(5000)  # Wait longer for tweet to post
            
            # Save reply to database
            reply_data = {
                'original_tweet_id': tweet_data['tweet_id'],
                'reply_content': reply_content,
                'timestamp': datetime.now().isoformat(),
                'status': 'posted'
            }
            self.db.save_reply(reply_data)
            
            logger.info(f"Successfully replied to tweet {tweet_data['tweet_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error replying to tweet: {str(e)}")
            # Take screenshot for debugging
            try:
                await page.screenshot(path=f'reply_error_{tweet_data["tweet_id"]}.png')
            except:
                pass
            return False
            
    async def reply_to_recent_tweets(self, page, max_tweets: int = 5) -> None:
        """Reply to recent tweets from the database"""
        try:
            # Get recent tweets that haven't been replied to
            recent_tweets = self.db.get_recent_unreplied_tweets(limit=max_tweets)
            
            if not recent_tweets:
                logger.info("No new tweets to reply to")
                return
                
            logger.info(f"Found {len(recent_tweets)} tweets to reply to")
            
            for tweet in recent_tweets:
                # Check if we've already replied to this tweet
                if self.db.has_reply(tweet['tweet_id']):
                    logger.info(f"Already replied to tweet {tweet['tweet_id']}, skipping...")
                    continue
                    
                # Add delay between replies to avoid rate limiting
                await page.wait_for_timeout(5000)
                
                # Reply to tweet
                success = await self.reply_to_tweet(page, tweet)
                if success:
                    logger.info(f"Successfully replied to tweet {tweet['tweet_id']}")
                else:
                    logger.error(f"Failed to reply to tweet {tweet['tweet_id']}")
                
        except Exception as e:
            logger.error(f"Error in reply_to_recent_tweets: {str(e)}")
            raise
