import logging
import json
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from openai import OpenAI
from database import TwitterDatabase
import httpx
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TweetSummarizer:
    def __init__(self, db: TwitterDatabase):
        """Initialize the TweetSummarizer with database and OpenAI client"""
        self.db = db
        self.openai_client = OpenAI(http_client=httpx.Client())
        self._used_tweet_ids: Set[str] = set()  # Track used tweets
        
    def _reset_used_tweets(self):
        """Reset the set of used tweet IDs"""
        self._used_tweet_ids.clear()
        
    def get_fresh_insights(self, limit: int = 5) -> List[Dict]:
        """Get fresh insights that haven't been used before"""
        all_insights = self.db.get_top_insights(limit * 2)  # Get more for filtering
        fresh_insights = []
        
        for insight in all_insights:
            if insight['tweet_id'] not in self._used_tweet_ids:
                fresh_insights.append(insight)
                self._used_tweet_ids.add(insight['tweet_id'])
                if len(fresh_insights) >= limit:
                    break
                    
        return fresh_insights[:limit]
    
    def generate_insight_tweet(self, tweet_data: Dict) -> str:
        """Generate a tweet about a single insight"""
        try:
            prompt = f"""Tweet to analyze:
{tweet_data['content']}

Generate a casual observation that:
1. Highlights the key insight
2. Uses all lowercase (like casual texting)
3. Keeps it under 120 chars
4. Uses Traditional Chinese
5. NO hashtags, NO emojis, NO quotation marks
6. Sounds like sharing a thought (not reporting)

Example good tweet: been noticing how much a single strong coin can influence the whole market
Example bad tweet: "Analysis of recent market trends shows significant correlation between assets"

Make it sound natural and conversational, not like a report.
IMPORTANT: Never use quotation marks in the tweet."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a crypto market observer sharing casual insights. Keep responses concise and engaging. Never use quotation marks."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            tweet = response.choices[0].message.content.strip()
            # Remove any quotation marks that might have slipped through
            tweet = tweet.replace('"', '').replace('"', '').replace('"', '').replace("'", '')
            
            # Ensure tweet is within character limit
            if len(tweet) > 280:
                tweet = tweet[:277] + "..."
                
            return tweet
            
        except Exception as e:
            logger.error(f"Error generating insight tweet: {str(e)}")
            return None
            
    def generate_insight_summary(self, tweets: List[Dict]) -> str:
        """Generate a summary tweet based on multiple insights"""
        try:
            # Create prompt with fresh tweets
            tweets_text = "\n".join([
                f"- {tweet['content']} (Insight: {tweet['insight_score']})"
                for tweet in tweets[:3]  # Limit to 3 tweets
            ])
            
            prompt = f"""Based on these high-insight tweets:

{tweets_text}

Generate an insightful tweet that captures the key trends or insights. 
Requirements:
1. Be original, don't just summarize
2. Add your own insights and perspective
3. Keep it casual and engaging
4. Maximum 120 characters
5. Focus on the highest insight topics
6. No hashtags, no emojis, no quotation marks

Please use Tranditional Chinese by default.
IMPORTANT: Never use quotation marks in the tweet."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a crypto market observer sharing casual insights. Keep responses concise and engaging. Never use quotation marks."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )

            tweet = response.choices[0].message.content.strip()
            # Remove any quotation marks that might have slipped through
            tweet = tweet.replace('"', '').replace('"', '').replace('"', '').replace("'", '')
            
            # Ensure tweet is within character limit
            if len(tweet) > 280:
                tweet = tweet[:277] + "..."
                
            return tweet

        except Exception as e:
            logger.error(f"Error generating summary tweet: {str(e)}")
            return None

    async def _post_tweet(self, page, tweet_content: str) -> bool:
        """Post a tweet using Playwright"""
        try:
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
                raise Exception("Could not find tweet input")
            
            await tweet_input.fill(tweet_content)
            await page.wait_for_timeout(3000)
            
            # Click tweet button
            tweet_button = await page.wait_for_selector('[data-testid="tweetButton"]', timeout=10000)
            if not tweet_button:
                raise Exception("Could not find tweet button")
            
            await tweet_button.click()
            await page.wait_for_timeout(5000)
            
            return True
            
        except Exception as e:
            logger.error(f"Error posting tweet: {str(e)}")
            return False

    async def post_summary(self, page) -> bool:
        """Post a summary of recent insights"""
        try:
            # Reset used tweets at start
            self._reset_used_tweets()
            
            # Get fresh insights
            insights = self.get_fresh_insights(5)
            if not insights:
                logger.info("No new insights to summarize")
                return False
                
            # Generate and post individual insight tweets
            for insight in insights[:1]:  # Post top 1 individual insights
                tweet = self.generate_insight_tweet(insight)
                if tweet:
                    logger.info(f"Posting insight tweet: {tweet}")
                    if await self._post_tweet(page, tweet):
                        # Save post to database
                        post_data = {
                            'content': tweet,
                            'type': 'insight',
                            'reference_tweet_id': insight['tweet_id'],
                            'source_tweets': json.dumps([insight['tweet_id']]),
                            'timestamp': datetime.now().isoformat(),
                            'status': 'posted'
                        }
                        self.db.save_post(post_data)
                    await page.wait_for_timeout(30000)  # Wait between tweets
                    
            # Generate and post summary tweet
            summary_tweet = self.generate_insight_summary(insights[2:])  # Use remaining insights
            if summary_tweet:
                logger.info(f"Posting summary tweet: {summary_tweet}")
                if await self._post_tweet(page, summary_tweet):
                    # Save post to database
                    post_data = {
                        'content': summary_tweet,
                        'type': 'summary',
                        'reference_tweet_id': insights[2]['tweet_id'] if len(insights) > 2 else None,
                        'source_tweets': json.dumps([t['tweet_id'] for t in insights[2:]]),
                        'timestamp': datetime.now().isoformat(),
                        'status': 'posted'
                    }
                    self.db.save_post(post_data)
                
            return True
            
        except Exception as e:
            logger.error(f"Error posting summary: {str(e)}")
            return False
