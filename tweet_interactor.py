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
            prompt = f"""Tweet to reply to:
{tweet_data['content']}

Generate a casual reply that:
1. Stays relevant to the tweet
2. Uses all lowercase (like casual texting)
3. Keeps it under 100 chars
4. Same language as original tweet
5. NO hashtags, NO emojis, NO quotation marks
6. Sounds like a friend chatting (not a formal reply)

Example good reply: never thought about it that way
Example bad reply: "Thank you for sharing! This is a very interesting perspective."

Make it sound natural and conversational, not like an assistant.
IMPORTANT: Never use quotation marks in the reply."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4",
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
            
    async def reply_to_recent_tweets(self, page) -> None:
        """Reply to recent tweets, prioritizing those with high insight scores"""
        try:
            # Get most insightful recent tweets
            tweets = self.db.get_most_insightful_recent_tweets(limit=10)
            
            if not tweets:
                logger.info("No recent insightful tweets found to reply to")
                return
                
            for tweet in tweets:
                try:
                    # Try to check if we've already replied, but don't block on errors
                    try:
                        if self.db.has_replied_to_tweet(tweet['tweet_id']):
                            logger.info(f"Already replied to tweet {tweet['tweet_id']}, skipping...")
                            continue
                    except Exception as e:
                        logger.warning(f"Could not check reply status for tweet {tweet['tweet_id']}: {str(e)}")
                    
                    # Only reply to tweets with insight score above 50
                    if tweet.get('insight_score', 0) <= 50:
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
