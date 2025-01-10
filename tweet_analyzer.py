import logging
from typing import List, Dict, Optional
from datetime import datetime
import json
import re
from openai import OpenAI
import time
from database import TwitterDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TweetAnalyzer:
    def __init__(self, db: TwitterDatabase, api_key: str):
        """Initialize the TweetAnalyzer with database and OpenAI client"""
        self.db = db
        self.openai_client = OpenAI(api_key=api_key)
        
    async def extract_tweet_data(self, article) -> Dict:
        """Extract relevant data from a tweet article element"""
        try:
            # Get tweet text
            tweet_text = await article.query_selector('[data-testid="tweetText"]')
            content = await tweet_text.inner_text() if tweet_text else ""
            
            # Get tweet ID from article
            tweet_url_elem = await article.query_selector('a[href*="/status/"]')
            tweet_url = await tweet_url_elem.get_attribute('href') if tweet_url_elem else None
            tweet_id = tweet_url.split('/status/')[-1] if tweet_url else None
            
            # Get author
            author_elem = await article.query_selector('[data-testid="User-Name"]')
            author_text = await author_elem.inner_text() if author_elem else ""
            author = author_text.split('·')[0].strip() if author_text else ""
            
            # Get timestamp
            time_elem = await article.query_selector('time')
            timestamp = await time_elem.get_attribute('datetime') if time_elem else None
            
            # Extract hashtags
            hashtags = re.findall(r'#(\w+)', content)
            
            # Extract mentions
            mentions = re.findall(r'@(\w+)', content)
            
            # Extract URLs
            urls = re.findall(r'https?://\S+', content)
            
            # Get media URLs
            media_elements = await article.query_selector_all('img[src*="media"]')
            media_urls = []
            for elem in media_elements:
                if elem:
                    src = await elem.get_attribute('src')
                    if src:
                        media_urls.append(src)
            
            return {
                'tweet_id': tweet_id,
                'content': content,
                'author': author,
                'timestamp': timestamp,
                'hashtags': json.dumps(hashtags),
                'mentions': json.dumps(mentions),
                'urls': json.dumps(urls),
                'media_urls': json.dumps(media_urls)
            }
        except Exception as e:
            logger.error(f"Error extracting tweet data: {str(e)}")
            return None
            
    def summarize_tweet(self, content: str) -> str:
        """Use OpenAI to generate a summary of the tweet"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes tweets. Keep summaries concise and capture the main point."},
                    {"role": "user", "content": f"Please summarize this tweet in one short sentence: {content}"}
                ],
                max_tokens=60,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return ""
            
    def generate_embedding(self, content: str) -> List[float]:
        """Generate embedding for the tweet content using OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=content
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return []

    def generate_insight_score(self, content: str) -> int:
        """Generate an insight score (0-100) for the tweet content using OpenAI"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": """You are an expert at evaluating the insightfulness of tweets.
Rate tweets on a scale of 0-100 based on:
- Uniqueness of perspective (30%)
- Depth of analysis (30%)
- Practical value (20%)
- Clarity of expression (20%)

Return ONLY the numeric score, nothing else."""},
                    {"role": "user", "content": f"Rate this tweet's insightfulness (0-100): {content}"}
                ],
                max_tokens=10,
                temperature=0.3
            )
            
            # Extract numeric score from response
            score_str = response.choices[0].message.content.strip()
            try:
                score = int(score_str)
                return max(0, min(100, score))  # Ensure score is between 0 and 100
            except ValueError:
                logger.error(f"Failed to parse insight score: {score_str}")
                return 50  # Default score if parsing fails
                
        except Exception as e:
            logger.error(f"Error generating insight score: {str(e)}")
            return 50  # Default score if API call fails

    def generate_topics(self, content: str) -> List[str]:
        """Generate a list of topics for the tweet content using OpenAI"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": """You are an expert at identifying specific topics in tweets.
Extract 1-3 main topics. Topics MUST be:
- Single word only
- Extremely specific (no vague terms like 'technology', 'business', 'industry')
- Lowercase with no special characters

Common mappings to use:
- "cryptocurrency trading" -> "crypto"
- "ai technology" -> "ai"
- "bsc ecosystem" -> "bsc"
- "creator community" -> "creator"
- "market trends" -> "trends"
- "web3" -> "web3"
- "nft" -> "nft"
- "defi" -> "defi"

Return ONLY a comma-separated list of topics, no other text.
Example: "crypto, ai, nft"

If no specific topics can be identified, return an empty string."""},
                    {"role": "user", "content": f"Extract specific topics from this tweet: {content}"}
                ],
                max_tokens=50,
                temperature=0.3
            )
            
            # Parse topics from response
            topics_str = response.choices[0].message.content.strip()
            if not topics_str:  # If empty string returned
                return []
                
            topics = [topic.strip() for topic in topics_str.split(',')]
            # Filter out any multi-word topics or empty strings
            topics = [t for t in topics if t and ' ' not in t]
            return topics[:3]  # Ensure we return at most 3 topics
                
        except Exception as e:
            logger.error(f"Error generating topics: {str(e)}")
            return []  # Return empty list if API call fails

    def extract_tokens(self, content: str) -> List[str]:
        """Extract token names and $symbols from tweet content using OpenAI"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": """You are an expert at identifying crypto token names and symbols in tweets.
Extract all token names and $symbols. Rules:
1. Include both explicit symbols (starting with $) and token names
2. Remove any $ prefix
3. Convert all to uppercase
4. Return ONLY the unique token list, no other text
5. If unsure about a token, don't include it

Example tweet: "Just bought some $eth and bitcoin, thinking about Solana too"
Example response: ETH, BTC, SOL

Example tweet: "The PEPE and $WOJAK charts looking bullish"
Example response: PEPE, WOJAK

Return ONLY a comma-separated list of tokens, no other text.
If no tokens found, return an empty string."""},
                    {"role": "user", "content": f"Extract token names and symbols from this tweet: {content}"}
                ],
                max_tokens=50,
                temperature=0.3
            )
            
            tokens_str = response.choices[0].message.content.strip()
            if not tokens_str:
                return []
                
            # Split and clean tokens
            tokens = [token.strip().upper() for token in tokens_str.split(',')]
            # Remove any empty strings
            tokens = [t for t in tokens if t]
            return tokens
            
        except Exception as e:
            logger.error(f"Error extracting tokens: {str(e)}")
            return []

    async def fetch_and_learn_tweets(self, page, max_tweets: int = 50) -> None:
        """Fetch tweets from home page, analyze them, and save to database"""
        try:
            # Navigate to home page
            logger.info("Navigating to Twitter home page...")
            await page.goto("https://twitter.com/home")
            await page.wait_for_timeout(3000)  # Wait for content to load
            
            # Wait for tweet articles to appear
            logger.info("Waiting for tweets to load...")
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
            
            # Scroll a bit to load more tweets
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, 1000)')
                await page.wait_for_timeout(1000)
            
            # Get all tweet articles
            articles = await page.query_selector_all('article[data-testid="tweet"]')
            processed_count = 0
            
            for article in articles[:max_tweets]:
                try:
                    # Extract tweet data
                    tweet_data = await self.extract_tweet_data(article)
                    if not tweet_data or not tweet_data['tweet_id']:
                        continue
                    
                    # Check if tweet already exists
                    if self.db.get_tweet_by_id(tweet_data['tweet_id']):
                        logger.info(f"Tweet {tweet_data['tweet_id']} already exists, skipping...")
                        continue
                    
                    # Generate summary, embedding, insight score, and topics
                    summary = self.summarize_tweet(tweet_data['content'])
                    embedding = self.generate_embedding(tweet_data['content'])
                    insight_score = self.generate_insight_score(tweet_data['content'])
                    topics = self.generate_topics(tweet_data['content'])
                    tokens = self.extract_tokens(tweet_data['content'])
                    
                    # Add to tweet data
                    tweet_data['summary'] = summary
                    tweet_data['embedding'] = json.dumps(embedding)
                    tweet_data['insight_score'] = insight_score
                    tweet_data['topics'] = topics
                    tweet_data['tokens'] = tokens
                    
                    # Save to database
                    self.db.save_tweet(tweet_data)
                    
                    processed_count += 1
                    logger.info(f"Processed and saved tweet {tweet_data['tweet_id']} with topics: {topics}, tokens: {tokens}, and insight score: {insight_score}")
                    
                    # Add small delay between processing
                    await page.wait_for_timeout(500)
                    
                except Exception as e:
                    logger.error(f"Error processing tweet: {str(e)}")
                    continue
            
            logger.info(f"Successfully processed {processed_count} tweets")
            
        except Exception as e:
            logger.error(f"Error in fetch_and_learn_tweets: {str(e)}")
            raise
