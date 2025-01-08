import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import json

class TwitterDatabase:
    def __init__(self, db_path: str = "twitter_agent.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Create and return a database connection"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create tweets table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tweets (
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
                    media_urls TEXT
                )
            ''')
            
            # Create replies table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS replies (
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
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT,
                    source_tweets TEXT,  -- JSON array of tweet_ids used as source
                    timestamp DATETIME,
                    status TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def save_tweet(self, tweet_data: Dict) -> bool:
        """Save a tweet to the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO tweets 
                    (tweet_id, content, author, timestamp, summary, embedding, hashtags, mentions, urls, media_urls)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    tweet_data['tweet_id'],
                    tweet_data['content'],
                    tweet_data['author'],
                    tweet_data['timestamp'],
                    tweet_data.get('summary'),
                    tweet_data.get('embedding'),
                    json.dumps(tweet_data.get('hashtags', [])),
                    json.dumps(tweet_data.get('mentions', [])),
                    json.dumps(tweet_data.get('urls', [])),
                    json.dumps(tweet_data.get('media_urls', []))
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
            print(f"Error saving reply: {e}")
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
        """Retrieve a specific tweet by its ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tweet_id, content, author, timestamp, summary
                FROM tweets
                WHERE tweet_id = ?
            ''', (tweet_id,))
            
            row = cursor.fetchone()
            if row:
                columns = ['tweet_id', 'content', 'author', 'timestamp', 'summary']
                return dict(zip(columns, row))
            return None
