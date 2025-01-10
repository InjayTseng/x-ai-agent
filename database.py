import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import json
import logging

logger = logging.getLogger(__name__)

class TwitterDatabase:
    def __init__(self, db_path: str = "twitter_agent.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Create and return a database connection"""
        return sqlite3.connect(self.db_path)
    
    def recreate_tables(self):
        """Drop and recreate all tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Drop existing tables if they exist
            cursor.execute('DROP TABLE IF EXISTS replies')
            cursor.execute('DROP TABLE IF EXISTS tweets')
            cursor.execute('DROP TABLE IF EXISTS posts')
            
            # Create tweets table
            cursor.execute('''
                CREATE TABLE tweets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT UNIQUE,
                    content TEXT,
                    author TEXT,
                    timestamp DATETIME,
                    summary TEXT,
                    embedding TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    hashtags TEXT,
                    mentions TEXT,
                    urls TEXT,
                    media_urls TEXT,
                    insight_score INTEGER,
                    topics TEXT,
                    tokens TEXT
                )
            ''')
            
            # Create replies table
            cursor.execute('''
                CREATE TABLE replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_tweet_id TEXT,
                    reply_content TEXT,
                    timestamp DATETIME,
                    status TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (original_tweet_id) REFERENCES tweets (tweet_id)
                )
            ''')
            
            # Create posts table
            cursor.execute('''
                CREATE TABLE posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT,
                    source_tweets TEXT,  -- JSON array of tweet_ids used as source
                    timestamp DATETIME,
                    status TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def init_database(self):
        """Initialize database tables"""
        try:
            # Check if tables exist
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if tweets table has all required columns
                cursor.execute('PRAGMA table_info(tweets)')
                columns = {col[1] for col in cursor.fetchall()}
                required_columns = {'insight_score', 'topics', 'tokens'}
                
                # If any required column is missing, recreate tables
                if not required_columns.issubset(columns):
                    logger.info("Database schema outdated, recreating tables...")
                    self.recreate_tables()
                    logger.info("Database tables recreated successfully")
                else:
                    logger.info("Database schema up to date")
                    
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise
    
    def save_tweet(self, tweet_data: Dict) -> bool:
        """Save a tweet to the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO tweets 
                    (tweet_id, content, author, timestamp, summary, embedding, hashtags, mentions, urls, media_urls, insight_score, topics, tokens)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    tweet_data['tweet_id'],
                    tweet_data['content'],
                    tweet_data['author'],
                    tweet_data['timestamp'],
                    tweet_data.get('summary', ''),
                    tweet_data.get('embedding', '[]'),
                    json.dumps(tweet_data.get('hashtags', [])),
                    json.dumps(tweet_data.get('mentions', [])),
                    json.dumps(tweet_data.get('urls', [])),
                    json.dumps(tweet_data.get('media_urls', [])),
                    tweet_data.get('insight_score'),
                    json.dumps(tweet_data.get('topics', [])),
                    json.dumps(tweet_data.get('tokens', []))
                ))
                return True
        except Exception as e:
            print(f"Error saving tweet: {e}")
            return False
    
    def save_reply(self, reply_data: Dict) -> bool:
        """Save a reply to the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO replies 
                    (original_tweet_id, reply_content, timestamp, status)
                    VALUES (?, ?, ?, ?)
                ''', (
                    reply_data['original_tweet_id'],
                    reply_data['reply_content'],
                    reply_data['timestamp'],
                    reply_data['status']
                ))
                return True
        except Exception as e:
            logger.error(f"Error saving reply: {e}")
            return False
    
    def save_post(self, post_data: Dict) -> bool:
        """Save an automated post to the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO posts 
                    (content, source_tweets, timestamp, status)
                    VALUES (?, ?, ?, ?)
                ''', (
                    post_data['content'],
                    json.dumps(post_data['source_tweets']),
                    post_data['timestamp'],
                    post_data['status']
                ))
                return True
        except Exception as e:
            print(f"Error saving post: {e}")
            return False
    
    def get_recent_tweets(self, limit: int = 10) -> List[Dict]:
        """Retrieve recent tweets from the database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tweet_id, content, author, timestamp, summary
                FROM tweets
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            
            columns = ['tweet_id', 'content', 'author', 'timestamp', 'summary']
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_tweet_by_id(self, tweet_id: str) -> Optional[Dict]:
        """Get a tweet by its ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM tweets WHERE tweet_id = ?', (tweet_id,))
                tweet = cursor.fetchone()
                
                if not tweet:
                    return None
                    
                # Convert row to dictionary
                columns = [description[0] for description in cursor.description]
                tweet_dict = dict(zip(columns, tweet))
                
                # Parse JSON fields
                for field in ['hashtags', 'mentions', 'urls', 'media_urls', 'embedding', 'topics', 'tokens']:
                    if tweet_dict.get(field):
                        tweet_dict[field] = json.loads(tweet_dict[field])
                        
                return tweet_dict
                
        except Exception as e:
            logger.error(f"Error getting tweet by ID: {e}")
            return None
    
    def get_recent_unreplied_tweets(self, limit: int = 3, hours: int = 24) -> List[Dict]:
        """Get recent tweets that haven't been replied to, prioritizing based on engagement potential"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get tweets from last 24 hours that don't have replies
                # Prioritize:
                # 1. Tweets from verified accounts (more likely to be influential)
                # 2. Tweets that are questions (more engagement potential)
                # 3. Tweets with fewer replies (better chance of visibility)
                # 4. Recent tweets
                cursor.execute('''
                    SELECT t.* FROM tweets t
                    LEFT JOIN replies r ON t.tweet_id = r.original_tweet_id
                    WHERE r.id IS NULL
                    AND t.timestamp > datetime('now', ?)
                    AND (
                        -- Priority 1: Tweets from specific important authors
                        t.author IN ('elonmusk', 'VitalikButerin', 'SBF_FTX', 'cz_binance')
                        OR
                        -- Priority 2: Tweets that are questions or seek engagement
                        (
                            t.content LIKE '%?%'
                            OR lower(t.content) LIKE '%what%'
                            OR lower(t.content) LIKE '%how%'
                            OR lower(t.content) LIKE '%why%'
                            OR lower(t.content) LIKE '%when%'
                            OR lower(t.content) LIKE '%where%'
                            OR lower(t.content) LIKE '%who%'
                            OR lower(t.content) LIKE '%thoughts%'
                            OR lower(t.content) LIKE '%think%'
                            OR lower(t.content) LIKE '%agree%'
                        )
                    )
                    ORDER BY 
                        CASE 
                            WHEN t.author IN ('elonmusk', 'VitalikButerin', 'SBF_FTX', 'cz_binance') THEN 1
                            WHEN t.content LIKE '%?%' THEN 2
                            ELSE 3
                        END,
                        t.timestamp DESC
                    LIMIT ?
                ''', (f'-{hours} hours', limit))
                
                columns = [description[0] for description in cursor.description]
                tweets = []
                
                for row in cursor.fetchall():
                    tweet_dict = dict(zip(columns, row))
                    # Parse JSON fields
                    for field in ['hashtags', 'mentions', 'urls', 'media_urls', 'embedding', 'topics', 'tokens']:
                        if tweet_dict.get(field):
                            tweet_dict[field] = json.loads(tweet_dict[field])
                    tweets.append(tweet_dict)
                
                return tweets
                
        except Exception as e:
            logger.error(f"Error getting unreplied tweets: {e}")
            return []
            
    def has_reply(self, tweet_id: str) -> bool:
        """Check if a tweet has been replied to"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM replies
                    WHERE original_tweet_id = ?
                ''', (tweet_id,))
                
                count = cursor.fetchone()[0]
                return count > 0
                
        except Exception as e:
            logger.error(f"Error checking reply status: {e}")
            return False

    def has_replied_to_tweet(self, tweet_id: str) -> bool:
        """Check if we have already replied to a tweet"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM replies 
                    WHERE original_tweet_id = ?
                ''', (tweet_id,))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logger.error(f"Error checking if replied to tweet: {str(e)}")
            return False  # If there's an error, assume we haven't replied

    def get_most_insightful_recent_tweets(self, limit: int = 10) -> List[Dict]:
        """Get the most insightful recent tweets, ordered by insight_score DESC"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get column names
                cursor.execute('PRAGMA table_info(tweets)')
                columns = [col[1] for col in cursor.fetchall()]
                
                # Get recent tweets ordered by insight_score
                cursor.execute('''
                    SELECT *
                    FROM tweets
                    WHERE timestamp >= datetime('now', '-1 day')
                    ORDER BY insight_score DESC, timestamp DESC
                    LIMIT ?
                ''', (limit,))
                
                tweets = []
                for row in cursor.fetchall():
                    tweet_dict = dict(zip(columns, row))
                    # Parse JSON fields
                    for field in ['hashtags', 'mentions', 'urls', 'media_urls', 'embedding', 'topics', 'tokens']:
                        if tweet_dict.get(field):
                            tweet_dict[field] = json.loads(tweet_dict[field])
                    tweets.append(tweet_dict)
                
                return tweets
                
        except Exception as e:
            logger.error(f"Error getting most insightful tweets: {str(e)}")
            return []

    def get_recent_interactions(self, start_time: str) -> List[Dict]:
        """Get recent interactions (tweets and replies) from a specific time"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get recent tweets with high insight scores
                cursor.execute('''
                    SELECT 
                        tweet_id,
                        content,
                        author,
                        timestamp,
                        summary,
                        topics,
                        insight_score,
                        hashtags,
                        mentions,
                        urls,
                        media_urls,
                        tokens
                    FROM tweets 
                    WHERE timestamp > ?
                    ORDER BY insight_score DESC, timestamp DESC
                    LIMIT 10
                ''', (start_time,))
                
                interactions = []
                for row in cursor.fetchall():
                    # Parse JSON fields, return empty list if parsing fails
                    def parse_json_field(field):
                        if not field:
                            return []
                        try:
                            if isinstance(field, str):
                                return json.loads(field)
                            return field
                        except:
                            return []
                    
                    interaction = {
                        'tweet_id': row[0],
                        'content': row[1],
                        'author': row[2],
                        'timestamp': row[3],
                        'summary': row[4],
                        'topics': parse_json_field(row[5]),
                        'insight_score': row[6],
                        'hashtags': parse_json_field(row[7]),
                        'mentions': parse_json_field(row[8]),
                        'urls': parse_json_field(row[9]),
                        'media_urls': parse_json_field(row[10]),
                        'tokens': parse_json_field(row[11])
                    }
                    interactions.append(interaction)
                
                return interactions
                
        except Exception as e:
            logger.error(f"Error getting recent interactions: {str(e)}")
            return []
