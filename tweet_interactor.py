import logging
from typing import Dict, Optional
import json
from datetime import datetime, timedelta
from openai import OpenAI
import httpx
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TweetInteractor:
    def __init__(self, db):
        """Initialize TweetInteractor with database and OpenAI client"""
        self.db = db
        self.openai_client = OpenAI(http_client=httpx.Client())
        
    def generate_reply(self, tweet_data: Dict) -> str:
        """Generate a reply using OpenAI based on tweet content and context"""
        try:
            # Create a prompt that includes tweet context
            prompt = f"""Tweet to reply to:
{tweet_data['content']}

Generate a casual reply that:
1. Stays relevant to the tweet
2. Uses all lowercase (like casual texting)
3. Keeps it under 70 chars
4. Same language as original tweet
5. NO hashtags, NO emojis, NO quotation marks
6. Sounds like a friend chatting (not a formal reply)

Example good reply: never thought about it that way
Example bad reply: "Thank you for sharing! This is a very interesting perspective."

Make it sound natural and conversational, not like an assistant.
IMPORTANT: Never use quotation marks in the reply."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates engaging Twitter replies. Keep responses concise and relevant. Never use quotation marks."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            reply = response.choices[0].message.content.strip()
            # Remove any quotation marks that might have slipped through
            reply = reply.replace('"', '').replace('"', '').replace('"', '').replace("'", '')
            
            # Ensure reply is within Twitter's character limit
            if len(reply) > 280:
                reply = reply[:277] + "..."
                
            return reply
            
        except Exception as e:
            logger.error(f"Error generating reply: {str(e)}")
            return None
            
    async def reply_to_tweet(self, page, tweet_data: Dict) -> bool:
        """Reply to a specific tweet"""
        try:
            # Generate reply content
            reply_content = self.generate_reply(tweet_data)
            if not reply_content:
                return False
                
            logger.info(f"Generated reply: {reply_content}")
                
            # Navigate to tweet with retry mechanism
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await page.goto(
                        f"https://twitter.com/i/status/{tweet_data['tweet_id']}",
                        wait_until="domcontentloaded",
                        timeout=20000
                    )
                    
                    # Wait for tweet to load
                    await page.wait_for_selector(
                        'article[data-testid="tweet"]',
                        timeout=10000,
                        state="visible"
                    )
                    
                    # Wait for reply button
                    reply_button = await page.wait_for_selector(
                        '[data-testid="reply"]',
                        timeout=10000,
                        state="visible"
                    )
                    
                    if reply_button:
                        await reply_button.click()
                        break
                        
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        await page.wait_for_timeout(3000)
                        continue
                    raise
            
            # Wait for reply input
            await page.wait_for_selector(
                '[data-testid="tweetTextarea_0"]',
                timeout=10000,
                state="visible"
            )
            
            # Type reply
            await page.fill('[data-testid="tweetTextarea_0"]', reply_content)
            await page.wait_for_timeout(1000)
            
            # Click reply button
            await page.click('[data-testid="tweetButton"]')
            await page.wait_for_timeout(3000)
            
            # Verify the reply was posted by checking for success indicators
            success_indicators = [
                'div[data-testid="toast"]',  # Success toast notification
                'div[role="alert"]',         # Success alert
                'div[data-testid="cellInnerDiv"]'  # New tweet in timeline
            ]
            
            posted_successfully = False
            for selector in success_indicators:
                try:
                    success_element = await page.wait_for_selector(selector, timeout=5000)
                    if success_element:
                        posted_successfully = True
                        break
                except Exception:
                    continue
            
            if not posted_successfully:
                logger.error("Could not verify if reply was posted")
                return False
            
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
                await page.screenshot(path=f'error_exception_{tweet_data["tweet_id"]}.png')
            except:
                pass
            return False
            
    async def reply_to_recent_tweets(self, page, max_replies: int = 3) -> None:
        """Reply to recent tweets, prioritizing those with high insight scores"""
        try:
            # Get recent tweets from the last 24 hours
            recent_tweets = self.db.get_recent_tweets(
                start_time=(datetime.now() - timedelta(hours=24)).isoformat()
            )
            
            if not recent_tweets:
                logger.info("No recent tweets found to reply to")
                return
                
            # Sort by insight score (highest first)
            recent_tweets.sort(key=lambda x: x.get('insight_score', 0), reverse=True)
            
            # Only take the specified number of tweets
            tweets_to_reply = recent_tweets[:max_replies]
            
            for tweet in tweets_to_reply:
                try:
                    # Try to check if we've already replied, but don't block on errors
                    try:
                        if self.db.has_replied_to_tweet(tweet['tweet_id']):
                            logger.info(f"Already replied to tweet {tweet['tweet_id']}, skipping...")
                            continue
                    except Exception as e:
                        logger.warning(f"Could not check reply status for tweet {tweet['tweet_id']}: {str(e)}")
                    
                    # Only reply to tweets with insight score above threshold
                    min_score = int(os.getenv('MIN_INSIGHT_SCORE', 7))
                    if tweet.get('insight_score', 0) <= min_score:
                        logger.info(f"Tweet {tweet['tweet_id']} insight score too low ({tweet.get('insight_score')}), skipping...")
                        continue
                        
                    # Generate reply
                    reply_text = self.generate_reply(tweet)
                    if not reply_text:
                        continue
                        
                    # Navigate to tweet
                    tweet_url = f"https://twitter.com/i/status/{tweet['tweet_id']}"
                    await page.goto(tweet_url)
                    await page.wait_for_timeout(3000)  # Wait for page load
                    
                    # Find and click reply button
                    reply_button = await page.wait_for_selector('[data-testid="reply"]', timeout=10000)
                    if not reply_button:
                        logger.error(f"Could not find reply button for tweet {tweet['tweet_id']}")
                        continue
                    await reply_button.click()
                    
                    # Find reply input and type reply
                    reply_input = await page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=10000)
                    if not reply_input:
                        logger.error(f"Could not find reply input for tweet {tweet['tweet_id']}")
                        continue
                    await reply_input.fill(reply_text)
                    
                    # Find and click tweet button
                    tweet_button = await page.wait_for_selector('[data-testid="tweetButton"]', timeout=10000)
                    if not tweet_button:
                        logger.error(f"Could not find tweet button for tweet {tweet['tweet_id']}")
                        continue
                    
                    # Check if button is enabled
                    is_enabled = await tweet_button.is_enabled()
                    if not is_enabled:
                        logger.error(f"Tweet button is disabled for tweet {tweet['tweet_id']}")
                        continue
                        
                    await tweet_button.click()
                    await page.wait_for_timeout(2000)  # Wait for reply to be sent
                    
                    # Try to save reply to database, but don't block on errors
                    try:
                        self.db.save_reply({
                            'original_tweet_id': tweet['tweet_id'],
                            'reply_content': reply_text,
                            'timestamp': datetime.now().isoformat(),
                            'status': 'sent'
                        })
                    except Exception as e:
                        logger.warning(f"Could not save reply for tweet {tweet['tweet_id']}: {str(e)}")
                    
                    logger.info(f"Successfully replied to tweet {tweet['tweet_id']} (insight score: {tweet.get('insight_score')})")
                    
                    # Add delay between replies to avoid rate limiting
                    await page.wait_for_timeout(5000)
                    
                except Exception as e:
                    logger.error(f"Error replying to tweet {tweet['tweet_id']}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in reply_to_recent_tweets: {str(e)}")
            raise
