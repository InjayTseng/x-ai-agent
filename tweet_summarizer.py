import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from openai import OpenAI
from database import TwitterDatabase

logger = logging.getLogger(__name__)

class TweetSummarizer:
    def __init__(self, db: TwitterDatabase, api_key: str):
        """Initialize TweetSummarizer with database and OpenAI client"""
        self.db = db
        self.openai_client = OpenAI(api_key=api_key)
        
    def get_recent_learnings(self, hours: int = 24) -> Dict:
        """Get insights from recent replies and interactions"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get time threshold
                time_threshold = (datetime.now() - timedelta(hours=hours)).isoformat()
                
                # Get recent replies with original tweets
                cursor.execute('''
                    SELECT 
                        r.reply_content,
                        t.content as original_tweet,
                        t.author as original_author,
                        t.hashtags,
                        t.mentions,
                        t.summary as tweet_summary
                    FROM replies r
                    JOIN tweets t ON r.original_tweet_id = t.tweet_id
                    WHERE r.timestamp > ?
                    ORDER BY r.timestamp DESC
                ''', (time_threshold,))
                
                interactions = []
                for row in cursor.fetchall():
                    interaction = {
                        'reply': row[0],
                        'original_tweet': row[1],
                        'author': row[2],
                        'hashtags': json.loads(row[3]) if row[3] else [],
                        'mentions': json.loads(row[4]) if row[4] else [],
                        'summary': row[5]
                    }
                    interactions.append(interaction)
                
                # Get topics and themes from interactions
                topics = {}
                for interaction in interactions:
                    # Add hashtags to topics
                    for hashtag in interaction['hashtags']:
                        topics[hashtag] = topics.get(hashtag, 0) + 1
                    
                    # Add key terms from summaries if available
                    if interaction['summary']:
                        terms = interaction['summary'].lower().split()
                        for term in terms:
                            if len(term) > 4:  # Only count meaningful terms
                                topics[term] = topics.get(term, 0) + 1
                
                # Sort topics by frequency
                sorted_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:5]
                
                return {
                    'interactions': interactions,
                    'top_topics': sorted_topics,
                    'period_hours': hours
                }
                
        except Exception as e:
            logger.error(f"Error getting learning insights: {e}")
            return {}
            
    def generate_summary_post(self, learnings: Dict) -> str:
        """Generate an engaging summary post about our learnings and interactions"""
        try:
            # Extract key information
            interactions = learnings['interactions']
            top_topics = learnings['top_topics']
            period = learnings['period_hours']
            
            # Create a thoughtful prompt
            prompt = f"""Based on our recent Twitter interactions over the past {period} hours:

Interactions:
{json.dumps([{
    'content': i['original_tweet'][:100],  
    'summary': i['summary']
} for i in interactions[:3]], indent=2)}

Key topics discussed:
{json.dumps(dict(top_topics), indent=2)}

Generate a casual tweet that:
1. Shares exactly ONE simple insight or learning (no lists or multiple points)
2. Uses casual, everyday language (like chatting with a friend)
3. Keeps it under 150 chars
4. NO emojis, NO mentions, NO hashtags, NO links
5. NO references to specific people, projects, or sources

Example good tweet: 'just realized how much impact community feedback has on project development. pretty cool to see ideas turn into reality'
Example bad tweet: 'Learning from @user about Project X and seeing great progress in the community! #crypto #development'

Make it sound like a random thought or realization, not a formal summary."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content.strip()
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return ""
            
    async def post_summary(self, page, hours: int = 24) -> bool:
        """Post a summary of recent learnings and interactions"""
        try:
            # Get learning insights
            learnings = self.get_recent_learnings(hours)
            if not learnings or not learnings.get('interactions'):
                logger.error("No recent interactions to summarize")
                return False
                
            # Generate summary post
            summary = self.generate_summary_post(learnings)
            if not summary:
                logger.error("Failed to generate summary")
                return False
                
            logger.info(f"Generated learning summary: {summary}")
            
            # Try posting methods with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Method 1: Post from home page
                    logger.info(f"Attempt {attempt + 1}: Posting from home page")
                    
                    # Navigate to home with retry
                    for nav_attempt in range(3):
                        try:
                            await page.goto('https://twitter.com/home', 
                                          wait_until='domcontentloaded',
                                          timeout=10000)
                            break
                        except Exception as e:
                            if nav_attempt == 2:
                                raise e
                            await page.wait_for_timeout(2000)
                    
                    await page.wait_for_timeout(5000)
                    
                    # Ensure page is loaded
                    try:
                        await page.wait_for_selector('div[data-testid="primaryColumn"]', timeout=10000)
                    except Exception:
                        raise Exception("Twitter home page did not load properly")
                    
                    # Click compose tweet button
                    compose_button = await page.wait_for_selector('[data-testid="SideNav_NewTweet_Button"]', timeout=10000)
                    if not compose_button:
                        raise Exception("Could not find compose button")
                    
                    await compose_button.click()
                    await page.wait_for_timeout(3000)
                    
                    # Find and fill tweet input
                    tweet_input = await page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=10000)
                    if not tweet_input:
                        raise Exception("Could not find tweet input")
                    
                    await tweet_input.fill(summary)
                    await page.wait_for_timeout(3000)
                    
                    # Click tweet button
                    tweet_button = await page.wait_for_selector('[data-testid="tweetButtonInline"]', timeout=10000)
                    if not tweet_button:
                        raise Exception("Could not find tweet button")
                    
                    # Ensure button is enabled
                    is_disabled = await tweet_button.get_attribute('aria-disabled') == 'true'
                    if is_disabled:
                        raise Exception("Tweet button is disabled")
                    
                    await tweet_button.click()
                    await page.wait_for_timeout(5000)
                    
                    # Verify post success
                    success = False
                    for selector in ['div[data-testid="toast"]', 'div[role="alert"]']:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                            success = True
                            break
                        except Exception:
                            continue
                    
                    if not success:
                        raise Exception("Could not verify tweet was posted")
                    
                    # Save post to database
                    post_data = {
                        'content': summary,
                        'source_tweets': json.dumps([i['original_tweet'] for i in learnings['interactions']]),
                        'timestamp': datetime.now().isoformat(),
                        'status': 'posted'
                    }
                    self.db.save_post(post_data)
                    
                    logger.info("Successfully posted learning summary")
                    return True
                    
                except Exception as e:
                    logger.error(f"Attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        # Try alternative method as last resort
                        try:
                            logger.info("Trying alternative posting method")
                            # Go directly to compose tweet URL
                            await page.goto('https://twitter.com/compose/tweet', 
                                          wait_until='domcontentloaded',
                                          timeout=10000)
                            await page.wait_for_timeout(5000)
                            
                            # Ensure compose page is loaded
                            try:
                                await page.wait_for_selector('div[data-testid="tweetTextarea_0"]', timeout=10000)
                            except Exception:
                                raise Exception("Compose tweet page did not load properly")
                            
                            # Find and fill tweet input
                            tweet_input = await page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=10000)
                            if not tweet_input:
                                raise Exception("Could not find tweet input in compose view")
                            
                            await tweet_input.fill(summary)
                            await page.wait_for_timeout(3000)
                            
                            # Click tweet button
                            tweet_button = await page.wait_for_selector('[data-testid="tweetButton"]', timeout=10000)
                            if not tweet_button:
                                raise Exception("Could not find tweet button in compose view")
                            
                            await tweet_button.click()
                            await page.wait_for_timeout(5000)
                            
                            # Save post to database
                            post_data = {
                                'content': summary,
                                'source_tweets': json.dumps([i['original_tweet'] for i in learnings['interactions']]),
                                'timestamp': datetime.now().isoformat(),
                                'status': 'posted'
                            }
                            self.db.save_post(post_data)
                            
                            logger.info("Successfully posted learning summary (alternative method)")
                            return True
                            
                        except Exception as e:
                            logger.error(f"Alternative posting method failed: {e}")
                            return False
                    else:
                        # Wait before retrying
                        await page.wait_for_timeout(3000)
                        continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error posting summary: {e}")
            await page.screenshot(path=f'error_summary_post.png')
            return False
