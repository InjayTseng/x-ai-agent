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
3. No more than 100 characters
4. Written in the same language as the original tweet
5. No hastags
"""

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
                
            logger.info(f"Generated reply: {reply_content}")
                
            # Navigate to tweet
            tweet_url = f"https://twitter.com/i/status/{tweet_data['tweet_id']}"
            logger.info(f"Navigating to tweet: {tweet_url}")
            
            # Navigate with a more lenient wait strategy
            try:
                await page.goto(tweet_url, wait_until='load', timeout=30000)
            except Exception as e:
                logger.error(f"Initial navigation failed: {str(e)}")
                # Try again with domcontentloaded
                await page.goto(tweet_url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for main content to be visible
            try:
                await page.wait_for_selector('article', timeout=10000)
            except Exception as e:
                logger.error(f"Could not find article: {str(e)}")
                return False
            
            await page.wait_for_timeout(5000)  # Additional wait for dynamic content
            
            # Take screenshot before interaction
            await page.screenshot(path=f'debug_before_reply_{tweet_data["tweet_id"]}.png')
            
            # Try multiple selectors for the reply button
            reply_button = None
            reply_selectors = [
                '[data-testid="reply"]',
                'div[aria-label="Reply"]',
                'div[role="button"][aria-label*="Reply"]',
                'div[role="button"][aria-label="Reply"]',
                'div[data-testid="reply"][role="button"]'
            ]
            
            for selector in reply_selectors:
                try:
                    logger.info(f"Trying reply button selector: {selector}")
                    reply_button = await page.wait_for_selector(selector, timeout=5000, state='visible')
                    if reply_button:
                        logger.info(f"Found reply button with selector: {selector}")
                        break
                except Exception as e:
                    logger.info(f"Selector {selector} failed: {str(e)}")
                    continue
            
            if not reply_button:
                logger.error("Could not find reply button")
                await page.screenshot(path=f'error_no_reply_button_{tweet_data["tweet_id"]}.png')
                return False
                
            # Try to click the reply button multiple ways
            try:
                await reply_button.click(timeout=5000)
            except Exception as e:
                logger.error(f"Standard click failed: {str(e)}")
                try:
                    # Try force click
                    await reply_button.click(force=True, timeout=5000)
                except Exception as e:
                    logger.error(f"Force click failed: {str(e)}")
                    try:
                        # Try JavaScript click
                        await reply_button.evaluate('node => node.click()')
                    except Exception as e:
                        logger.error(f"JavaScript click failed: {str(e)}")
                        return False
            
            await page.wait_for_timeout(3000)
            
            # Take screenshot after clicking reply
            await page.screenshot(path=f'debug_after_reply_click_{tweet_data["tweet_id"]}.png')
            
            # Find and fill reply input with retries
            reply_input = None
            input_selectors = [
                '[data-testid="tweetTextarea_0"]',
                'div[role="textbox"][aria-label="Tweet text"]',
                'div[data-testid="tweetTextarea_0"] div[role="textbox"]',
                'div[contenteditable="true"]'
            ]
            
            for selector in input_selectors:
                try:
                    logger.info(f"Trying reply input selector: {selector}")
                    reply_input = await page.wait_for_selector(selector, timeout=5000, state='visible')
                    if reply_input:
                        logger.info(f"Found reply input with selector: {selector}")
                        break
                except Exception as e:
                    logger.info(f"Input selector {selector} failed: {str(e)}")
                    continue
            
            if not reply_input:
                logger.error("Could not find reply input")
                await page.screenshot(path=f'error_no_input_{tweet_data["tweet_id"]}.png')
                return False
            
            # Try multiple methods to input text
            try:
                # Method 1: Direct fill
                await reply_input.fill(reply_content)
            except Exception as e:
                logger.error(f"Direct fill failed: {str(e)}")
                try:
                    # Method 2: Click and type
                    await reply_input.click()
                    await page.keyboard.type(reply_content)
                except Exception as e:
                    logger.error(f"Click and type failed: {str(e)}")
                    try:
                        # Method 3: JavaScript
                        await page.evaluate(f'''
                            document.querySelector('[data-testid="tweetTextarea_0"]').innerText = "{reply_content}";
                            document.querySelector('[data-testid="tweetTextarea_0"]').dispatchEvent(new Event('input', {{ bubbles: true }}));
                        ''')
                    except Exception as e:
                        logger.error(f"JavaScript input failed: {str(e)}")
                        return False
            
            await page.wait_for_timeout(2000)
            
            # Take screenshot after typing reply
            await page.screenshot(path=f'debug_after_typing_{tweet_data["tweet_id"]}.png')
            
            # Try multiple selectors for the tweet button
            tweet_button = None
            tweet_button_selectors = [
                '[data-testid="tweetButton"]',
                'div[data-testid="tweetButtonInline"]',
                'div[role="button"][data-testid*="tweet"]',
                'div[role="button"][data-testid="tweetButton"]',
                'div[data-testid="tweetButton"][role="button"]'
            ]
            
            for selector in tweet_button_selectors:
                try:
                    logger.info(f"Trying tweet button selector: {selector}")
                    tweet_button = await page.wait_for_selector(selector, timeout=5000, state='visible')
                    if tweet_button:
                        logger.info(f"Found tweet button with selector: {selector}")
                        break
                except Exception as e:
                    logger.info(f"Tweet button selector {selector} failed: {str(e)}")
                    continue
            
            if not tweet_button:
                logger.error("Could not find tweet button")
                await page.screenshot(path=f'error_no_tweet_button_{tweet_data["tweet_id"]}.png')
                return False
            
            # Check if tweet button is enabled
            is_disabled = await tweet_button.get_attribute('aria-disabled') == 'true'
            if is_disabled:
                logger.error("Tweet button is disabled")
                await page.screenshot(path=f'error_button_disabled_{tweet_data["tweet_id"]}.png')
                return False
            
            # Try multiple methods to click the tweet button
            try:
                await tweet_button.click(timeout=5000)
            except Exception as e:
                logger.error(f"Standard click failed: {str(e)}")
                try:
                    await tweet_button.click(force=True, timeout=5000)
                except Exception as e:
                    logger.error(f"Force click failed: {str(e)}")
                    try:
                        await tweet_button.evaluate('node => node.click()')
                    except Exception as e:
                        logger.error(f"JavaScript click failed: {str(e)}")
                        return False
            
            await page.wait_for_timeout(5000)  # Wait longer for tweet to post
            
            # Take final screenshot
            await page.screenshot(path=f'debug_after_posting_{tweet_data["tweet_id"]}.png')
            
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
