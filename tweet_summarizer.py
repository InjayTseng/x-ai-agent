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
            # Get recent interactions
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            # Get tweets and replies from the specified time period
            interactions = self.db.get_recent_interactions(start_time.isoformat())
            
            if not interactions:
                return {}
                
            return {
                'interactions': interactions,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting recent learnings: {str(e)}")
            return {}
            
    def generate_summary_post(self, learnings: Dict) -> str:
        """Generate an engaging summary post about our learnings and interactions"""
        try:
            # Extract key information
            interactions = learnings['interactions']
            period = (datetime.fromisoformat(learnings['end_time']) - datetime.fromisoformat(learnings['start_time'])).total_seconds() / 3600
            
            # Create a thoughtful prompt
            prompt = f"""Based on our recent Twitter interactions over the past {period} hours:

Interactions:
{json.dumps([{
    'content': i['original_tweet'][:100],  
    'summary': i['summary']
} for i in interactions[:3]], indent=2)}

Key topics discussed:
{json.dumps(dict([(i['hashtags'][0], len(i['hashtags'])) for i in interactions[:3]]), indent=2)}

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
            
    def generate_summary_tweet(self, tweets: List[Dict]) -> str:
        """Generate a summary tweet based on recent interactions"""
        try:
            # Format tweets for the prompt
            tweet_texts = []
            for t in tweets:
                # Handle topics that might be either JSON string or list
                topics = t['topics']
                if isinstance(topics, str):
                    topics = json.loads(topics)
                
                tweet_text = f"Tweet: {t['content']}\nTopics: {', '.join(topics)}\nInsight Score: {t['insight_score']}"
                tweet_texts.append(tweet_text)
                
            tweets_context = "\n\n".join(tweet_texts)

            prompt = f"""Based on these recent tweets:

{tweets_context}

Create a casual observation about trends or patterns you notice. The tweet should:
1. Be casual and conversational (like texting a friend)
2. Use lowercase (like casual texting)
3. Keep it under 200 chars
4. NO hashtags, NO emojis, NO quotation marks
5. Focus on insights, not just listing what happened
6. Sound natural, not like a formal summary

Example good tweet: been noticing how much a single strong coin can influence the whole market
Example bad tweet: "Analysis of recent market trends shows significant correlation between assets"

Make it sound natural and conversational, not like a report.
IMPORTANT: Never use quotation marks in the tweet."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates insightful tweets about crypto and market trends. Keep responses casual and natural. Never use quotation marks."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
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
            return ""
            
    async def post_summary(self, page, hours: int = 24) -> bool:
        """Post a summary of recent learnings and interactions"""
        try:
            # Get recent learnings (no await since it's not async)
            learnings = self.get_recent_learnings(hours)
            if not learnings or not learnings.get('interactions'):
                logger.info("No recent interactions to summarize")
                return False
                
            # Generate summary
            summary = self.generate_summary_tweet(learnings['interactions'])
            if not summary:
                logger.error("Failed to generate summary")
                return False
                
            logger.info(f"Generated learning summary: {summary}")
            
            max_retries = 3
            for attempt in range(max_retries):
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
                    
                    await tweet_input.fill(summary)
                    await page.wait_for_timeout(3000)
                    
                    # Click tweet button
                    tweet_button = await page.wait_for_selector('[data-testid="tweetButton"]', timeout=10000)
                    if not tweet_button:
                        raise Exception("Could not find tweet button")
                    
                    await tweet_button.click()
                    await page.wait_for_timeout(5000)
                    
                    # Save post to database
                    post_data = {
                        'content': summary,
                        'source_tweets': json.dumps([i['tweet_id'] for i in learnings['interactions']]),
                        'timestamp': datetime.now().isoformat(),
                        'status': 'posted'
                    }
                    self.db.save_post(post_data)
                    
                    logger.info("Successfully posted learning summary")
                    return True
                    
                except Exception as e:
                    logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        await page.wait_for_timeout(3000)
                        continue
                    return False
                    
            return False
            
        except Exception as e:
            logger.error(f"Error posting summary: {str(e)}")
            return False
